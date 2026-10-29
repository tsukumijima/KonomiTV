
from __future__ import annotations

import asyncio
import base64
import errno
import hashlib
import json
import os
import re
import shutil
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

import anyio
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ValidationError
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app import logging, schemas
from app.config import Config
from app.constants import JST
from app.metadata.CaptureScanTask import (
    CaptureScanTask,
    NormalizeCapturePath,
    ReadCaptureImage,
)
from app.models.Capture import (
    Capture,
    CaptureFavorite,
    CaptureFile,
    CaptureTag,
    CaptureTagItem,
)
from app.models.User import User
from app.routers.UsersRouter import (
    GetCurrentAdminUser,
    GetCurrentUser,
    GetOptionalCurrentUser,
)


# ルーター
router = APIRouter(
    tags = ['Captures'],
    prefix = '/api/captures',
)

# キャプチャの一覧の並び順
CaptureOrder = Literal['CapturedAtDesc', 'CapturedAtAsc', 'BroadcastAtDesc', 'BroadcastAtAsc', 'PlaybackPosition']

# 放送回の一覧の並び順 (値の名前は、キャプチャの一覧の並び順のうち放送日時順のものに合わせる)
CaptureProgramOrder = Literal['BroadcastAtDesc', 'BroadcastAtAsc']

# 検索語を探す範囲 (1つも指定しない場合は、字幕・番組名・番組概要・チャンネル名・ファイル名のすべてから探す)
CaptureQueryTarget = Literal['CaptionText', 'ProgramTitle', 'ProgramDescription']

# アップロードできるキャプチャ画像の最大サイズ (50MiB)
## 4K の PNG でも数十 MB に収まるため、これを超えるファイルは受け付けない
CAPTURE_UPLOAD_MAX_SIZE = 50 * 1024 * 1024

# 利用できる場所 (status が Available の実体ファイル) が1つ以上あるキャプチャだけに絞る条件
## キャプチャの一覧・日付ごとの件数・放送回のアルバム・タグの件数で共通して使う
CAPTURE_AVAILABLE_CONDITION = """
    EXISTS (
        SELECT 1 FROM capture_files f
        WHERE f.capture_id = c.id AND f.status = 'Available'
    )
""".strip()


class CaptureFilters(BaseModel):
    """
    キャプチャの一覧と、日付ごとの件数の集計で共通の絞り込みの条件
    """

    capture_program_id: int | None = None
    recorded_program_id: int | None = None
    network_id: int | None = None
    service_id: int | None = None
    event_id: int | None = None
    start_time: datetime | None = None
    is_favorite: bool | None = None
    tag_id: int | None = None
    is_caption_composited: bool | None = None
    is_comment_composited: bool | None = None
    has_caption_text: bool | None = None
    has_metadata: bool | None = None
    query: str | None = None
    query_targets: list[CaptureQueryTarget] | None = None


class CaptureCursor(BaseModel):
    """
    キーセット方式のページングのカーソル (検索条件のハッシュと、前のページの最後の行の並びのキー)
    """

    signature: str
    keys: list[str | int | float]


async def GetCaptureRows(ids: list[int]) -> list[dict[str, Any]]:
    """
    指定した ID のキャプチャの行を DB から取得する

    Args:
        ids (list[int]): キャプチャの ID

    Returns:
        list[dict[str, Any]]: DB の行
    """

    if len(ids) == 0:
        return []

    placeholders = ', '.join('?' for _ in ids)
    return await connections.get('default').execute_query_dict(f"""
        SELECT * FROM captures
        WHERE id IN ({placeholders})
    """, ids)


async def SerializeCaptures(rows: list[dict[str, Any]], user: User | None) -> list[schemas.Capture]:
    """
    DB から取得したキャプチャの行を API のレスポンスの形にする
    ログインしている場合は、本人のお気に入りとタグの状態をページの分まとめて取得して重ねる

    Args:
        rows (list[dict[str, Any]]): DB から取得したページの行
        user (User | None): 閲覧しているユーザー

    Returns:
        list[schemas.Capture]: ファイルのパスを含まないキャプチャの情報
    """

    # ログインしている場合だけ、ページ内のキャプチャに付いている本人のお気に入りとタグを取得する
    capture_ids = [row['id'] for row in rows]
    favorite_capture_ids: set[int] = set()
    tag_ids_by_capture_id: dict[int, list[int]] = {}
    if user is not None and len(capture_ids) > 0:
        favorite_rows = await CaptureFavorite.filter(
            user_id = user.id,
            capture_id__in = capture_ids,
        ).values('capture_id')
        for favorite_row in favorite_rows:
            favorite_capture_ids.add(favorite_row['capture_id'])
        tag_item_rows = await CaptureTagItem.filter(
            tag__user_id = user.id,
            capture_id__in = capture_ids,
        ).values('capture_id', 'tag_id')
        for tag_item_row in tag_item_rows:
            tag_ids_by_capture_id.setdefault(tag_item_row['capture_id'], []).append(tag_item_row['tag_id'])

    captures: list[schemas.Capture] = []
    for row in rows:

        # 内容のハッシュは16進数の文字列で返す (クライアントは画像の URL に付け、内容が変わったら URL も変わるようにする)
        file_hash = bytes(row['file_hash']).hex()

        # ログインしていない場合、お気に入りとタグの状態は分からないので None にする
        is_favorite: bool | None = None
        tag_ids: list[int] | None = None
        if user is not None:
            is_favorite = row['id'] in favorite_capture_ids
            tag_ids = sorted(tag_ids_by_capture_id.get(row['id'], []))

        captures.append(schemas.Capture.model_validate({
            **row,
            'file_hash': file_hash,
            'is_favorite': is_favorite,
            'tag_ids': tag_ids,
        }))

    return captures


async def BuildCaptureWhere(filters: CaptureFilters, user: User | None) -> tuple[list[str], list[Any]]:
    """
    絞り込みの条件から、キャプチャの一覧の WHERE 句の条件を作る
    場所・お気に入り・タグでの絞り込みは EXISTS で行い、キャプチャの行が増えないようにする

    Args:
        filters (CaptureFilters): 絞り込みの条件
        user (User | None): 閲覧しているユーザー

    Returns:
        tuple[list[str], list[Any]]: WHERE 句の条件と、バインドする値
    """

    conditions: list[str] = []
    params: list[Any] = []

    # 番組キーは4つ揃えて指定させる (ライブ視聴の画面から、その放送回のキャプチャを開くときに使う)
    program_key = (filters.network_id, filters.service_id, filters.event_id, filters.start_time)
    if any(value is not None for value in program_key):
        is_program_key_complete = all(value is not None for value in program_key)
        if is_program_key_complete is False or filters.start_time is None:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail = 'Specify all four program key fields',
            )
        conditions.append('p.network_id = ? AND p.service_id = ? AND p.event_id = ? AND p.start_time = ?')
        params.extend([filters.network_id, filters.service_id, filters.event_id, SQLDateTime(filters.start_time)])

    # 放送回で絞り込む
    if filters.capture_program_id is not None:
        conditions.append('c.capture_program_id = ?')
        params.append(filters.capture_program_id)

    # 録画番組で絞り込む (録画番組とは、番組キーが一致する放送回のキャプチャで結び付ける)
    if filters.recorded_program_id is not None:
        conditions.append("""
            EXISTS (
                SELECT 1 FROM recorded_programs r
                WHERE r.id = ?
                    AND r.network_id = p.network_id
                    AND r.service_id = p.service_id
                    AND r.event_id = p.event_id
                    AND r.start_time = p.start_time
            )
        """.strip())
        params.append(filters.recorded_program_id)

    # お気に入りとタグでの絞り込みはログインが必要
    if filters.is_favorite is True:
        if user is None:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'Not authenticated',
                headers = {'WWW-Authenticate': 'Bearer'},
            )
        conditions.append(await BuildPersonalCaptureCondition('capture_favorites', 'user_id', user.id))
        params.append(user.id)
    if filters.tag_id is not None:
        if user is None:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail = 'Not authenticated',
                headers = {'WWW-Authenticate': 'Bearer'},
            )
        # ほかのユーザーのタグで絞り込めないよう、所有者をチェックしてから条件にする
        await GetOwnedTag(filters.tag_id, user)
        conditions.append(await BuildPersonalCaptureCondition('capture_tag_items', 'tag_id', filters.tag_id))
        params.append(filters.tag_id)

    # 字幕・コメントを画像に合成したかどうかで絞り込む
    if filters.is_caption_composited is not None:
        conditions.append('c.is_caption_composited = ?')
        params.append(filters.is_caption_composited)
    if filters.is_comment_composited is not None:
        conditions.append('c.is_comment_composited = ?')
        params.append(filters.is_comment_composited)

    # 撮影したときに字幕が出ていたかどうかで絞り込む
    if filters.has_caption_text is True:
        conditions.append("(c.caption_text IS NOT NULL AND c.caption_text != '')")
    elif filters.has_caption_text is False:
        conditions.append("(c.caption_text IS NULL OR c.caption_text = '')")

    # 番組の情報があるかどうかで絞り込む
    if filters.has_metadata is True:
        conditions.append("c.metadata_status = 'Parsed'")
    elif filters.has_metadata is False:
        conditions.append("c.metadata_status != 'Parsed'")

    # 検索語は、録画番組の検索と同じく空白で区切った語の AND による部分一致で探す
    ## 範囲の指定がないか、3つの範囲をすべて指定した場合は、字幕・番組名・番組概要・チャンネル名・ファイル名のどれかに含まれていれば当てはまる
    ## 範囲を指定した場合は、指定した範囲のどれかに含まれていれば当てはまる
    query_targets = set(filters.query_targets or [])
    is_all_targets = len(query_targets) == 0 or query_targets == {'CaptionText', 'ProgramTitle', 'ProgramDescription'}
    for keyword in (filters.query or '').split():
        pattern = f'%{keyword.lower()}%'

        # すべての範囲から探す
        if is_all_targets is True:
            conditions.append("""
                (
                    LOWER(c.caption_text) LIKE ? OR
                    LOWER(p.title) LIKE ? OR
                    LOWER(p.description) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM channels ch
                        WHERE ch.network_id = p.network_id AND ch.service_id = p.service_id AND LOWER(ch.name) LIKE ?
                    ) OR
                    EXISTS (
                        SELECT 1 FROM capture_files f
                        WHERE f.capture_id = c.id AND LOWER(f.file_name) LIKE ?
                    )
                )
            """.strip())
            params.extend([pattern] * 5)  # 5つの検索対象に同じパラメータを使う
            continue

        # 指定された範囲の列だけから探す (列の並びは、すべての範囲から探すときと同じ順にする)
        target_conditions: list[str] = []
        if 'CaptionText' in query_targets:
            target_conditions.append('LOWER(c.caption_text) LIKE ?')
        if 'ProgramTitle' in query_targets:
            target_conditions.append('LOWER(p.title) LIKE ?')
        if 'ProgramDescription' in query_targets:
            target_conditions.append('LOWER(p.description) LIKE ?')
        conditions.append(f'({" OR ".join(target_conditions)})')
        params.extend([pattern] * len(target_conditions))

    # 利用できる場所があるかの EXISTS は最後に置き、ほかの条件に当てはまったキャプチャだけで評価させる
    conditions.append(CAPTURE_AVAILABLE_CONDITION)

    return conditions, params


def SQLDateTime(value: datetime) -> str:
    """
    日時を、ORM が DB に保存するのと同じ形の文字列にする (生の SQL で比較するため)

    Args:
        value (datetime): 比較する日時

    Returns:
        str: JST の日時の文字列
    """

    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST).isoformat(' ')


async def BuildPersonalCaptureCondition(
    table: Literal['capture_favorites', 'capture_tag_items'],
    owner_column: Literal['user_id', 'tag_id'],
    owner_id: int,
) -> str:
    """
    お気に入りやタグで絞り込む条件を、付いている件数に合わせて IN と EXISTS から選ぶ
    114.9万件で測ったところ、古い3件だけに付いたタグは IN が速く、半数に付いたタグは EXISTS が速かった
    IN の対象は NOT NULL の主キーなので、結果は EXISTS と同じになり、キャプチャの行も増えない

    Args:
        table (Literal['capture_favorites', 'capture_tag_items']): お気に入りまたはタグの項目のテーブル (持ち主は確認済み)
        owner_column (Literal['user_id', 'tag_id']): 持ち主で絞る列
        owner_id (int): ユーザーまたはタグの ID

    Returns:
        str: プレースホルダーを1つ持つ SQL の条件
    """

    # 全件は数えず、IN で絞り込む上限 (1万件) を超えたかだけを調べる
    rows = await connections.get('default').execute_query_dict(f"""
        SELECT COUNT(*) AS count
        FROM (
            SELECT 1 FROM {table}
            WHERE {owner_column} = ?
            LIMIT 10001
        )
    """, [owner_id])

    # 1万件以下なら、付いているキャプチャの ID を先に取得して絞り込む
    if rows[0]['count'] <= 10000:
        return f'c.id IN (SELECT capture_id FROM {table} WHERE {owner_column} = ?)'

    # 1万件を超えるなら、並びの索引を走査しながら1件ずつチェックする
    return f"""
        EXISTS (
            SELECT 1 FROM {table} personal
            WHERE personal.capture_id = c.id AND personal.{owner_column} = ?
        )
    """.strip()


async def GetOwnedTag(tag_id: int, user: User) -> CaptureTag:
    """
    本人のタグを取得する (ほかのユーザーのタグや存在しないタグは 404 エラーにする)

    Args:
        tag_id (int): タグの ID
        user (User): ログイン中のユーザー

    Returns:
        CaptureTag: 本人のタグ
    """

    tag = await CaptureTag.get_or_none(id=tag_id, user_id=user.id)
    if tag is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Capture tag not found',
        )
    return tag


def CursorSignature(values: object) -> str:
    """
    並び順・絞り込み・閲覧しているユーザーから、カーソルを使える検索条件のハッシュを作る

    Args:
        values (object): JSON にできる検索条件

    Returns:
        str: 検索条件のハッシュ
    """

    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def DecodeCursor(cursor: str, signature: str, key_count: int) -> list[str | int | float]:
    """
    カーソルを読み取り、壊れていたり検索条件が変わっていたりしたら 422 エラーにする

    Args:
        cursor (str): クライアントから渡されたカーソル
        signature (str): 今の検索条件のハッシュ
        key_count (int): 並びのキーの数

    Returns:
        list[str | int | float]: SQL で比較する並びのキー
    """

    try:
        parsed = CaptureCursor.model_validate_json(base64.b64decode(cursor, altchars=b'-_', validate=True))
        # 並び順や絞り込みが変わったあとの古いカーソルは使えない
        if parsed.signature != signature or len(parsed.keys) != key_count:
            raise ValueError('Cursor conditions changed')
        return parsed.keys
    except (ValueError, ValidationError) as ex:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Invalid cursor',
        ) from ex


def EncodeCursor(signature: str, keys: list[str | int | float]) -> str:
    """
    次のページの境目を、URL に渡せるカーソルの文字列にする

    Args:
        signature (str): 検索条件のハッシュ
        keys (list[str | int | float]): ページの最後の行の並びのキー

    Returns:
        str: URL に渡せるカーソル
    """

    cursor = CaptureCursor(signature=signature, keys=keys)
    return base64.urlsafe_b64encode(cursor.model_dump_json().encode()).decode()


async def SerializePrograms(ids: list[int]) -> list[schemas.CaptureProgram]:
    """
    放送回の番組情報に、チャンネルと、番組キーが一致する録画番組の ID を重ねて返す

    Args:
        ids (list[int]): 放送回の ID

    Returns:
        list[schemas.CaptureProgram]: 放送回の番組情報
    """

    if len(ids) == 0:
        return []

    conn = connections.get('default')
    placeholders = ', '.join('?' for _ in ids)

    # 放送回の番組情報を取得する
    program_rows = await conn.execute_query_dict(f"""
        SELECT * FROM capture_programs
        WHERE id IN ({placeholders})
    """, ids)

    # チャンネルと録画番組は、ページ内の放送回の分をまとめて1回ずつ取得する
    channel_rows = await conn.execute_query_dict(f"""
        SELECT
            p.id AS program_id,
            ch.id,
            ch.display_channel_id,
            ch.name,
            ch.type
        FROM capture_programs p
        JOIN channels ch ON ch.network_id = p.network_id AND ch.service_id = p.service_id
        WHERE p.id IN ({placeholders})
        ORDER BY ch.id
    """, ids)
    ## 録画ファイルが見つからなくなった (Missing の) 録画番組は開けないので含めない
    recorded_program_rows = await conn.execute_query_dict(f"""
        SELECT
            p.id AS program_id,
            r.id
        FROM capture_programs p
        JOIN recorded_programs r
            ON r.network_id = p.network_id
            AND r.service_id = p.service_id
            AND r.event_id = p.event_id
            AND r.start_time = p.start_time
        JOIN recorded_videos rv ON rv.recorded_program_id = r.id
        WHERE p.id IN ({placeholders})
            AND rv.status != 'Missing'
        ORDER BY r.id
    """, ids)

    programs: list[schemas.CaptureProgram] = []
    for program_row in program_rows:

        # 同じ番組キーのチャンネルが複数ある場合は、ID の小さいものを使う
        channel: schemas.CaptureChannel | None = None
        for channel_row in channel_rows:
            if channel_row['program_id'] == program_row['id']:
                channel = schemas.CaptureChannel.model_validate(channel_row)
                break

        recorded_program_ids: list[int] = []
        for recorded_program_row in recorded_program_rows:
            if recorded_program_row['program_id'] == program_row['id']:
                recorded_program_ids.append(recorded_program_row['id'])

        programs.append(schemas.CaptureProgram.model_validate({
            **program_row,
            'channel': channel,
            'recorded_program_ids': recorded_program_ids,
        }))

    return programs


async def GetProgramAlbum(program: schemas.CaptureProgram, user: User | None) -> schemas.CaptureProgramAlbum:
    """
    放送回のアルバム (利用できるキャプチャの枚数と代表のキャプチャ) を作る

    Args:
        program (schemas.CaptureProgram): 放送回の番組情報
        user (User | None): 閲覧しているユーザー

    Returns:
        schemas.CaptureProgramAlbum: 放送回のアルバム
    """

    conn = connections.get('default')

    # 利用できるキャプチャの枚数を取得する
    stats_rows = await conn.execute_query_dict(f"""
        SELECT COUNT(*) AS count
        FROM captures c
        WHERE c.capture_program_id = ? AND {CAPTURE_AVAILABLE_CONDITION}
    """, [program.id])
    stats = stats_rows[0]
    if stats['count'] == 0:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Capture program not found',
        )

    # 再生位置のあるキャプチャを先に並べ、その真ん中あたりを代表のキャプチャにする
    positioned_rows = await conn.execute_query_dict(f"""
        SELECT COUNT(*) AS count
        FROM captures c
        WHERE c.capture_program_id = ? AND {CAPTURE_AVAILABLE_CONDITION} AND c.playback_position IS NOT NULL
    """, [program.id])
    cover_offset = positioned_rows[0]['count'] // 2
    cover_rows = await conn.execute_query_dict(f"""
        SELECT c.*
        FROM captures c
        WHERE c.capture_program_id = ? AND {CAPTURE_AVAILABLE_CONDITION}
        ORDER BY (c.playback_position IS NULL), c.playback_position, c.captured_at, c.id
        LIMIT 1 OFFSET ?
    """, [program.id, cover_offset])
    cover_capture = (await SerializeCaptures(cover_rows, user))[0]

    return schemas.CaptureProgramAlbum(
        **program.model_dump(),
        capture_count = stats['count'],
        cover_capture = cover_capture,
    )


async def SerializeTag(tag: CaptureTag) -> schemas.CaptureTag:
    """
    タグを、利用できるキャプチャの件数と一緒に API のレスポンスの形にする

    Args:
        tag (CaptureTag): タグ

    Returns:
        schemas.CaptureTag: タグの情報
    """

    rows = await connections.get('default').execute_query_dict("""
        SELECT COUNT(*) AS count
        FROM capture_tag_items ti
        WHERE ti.tag_id = ? AND EXISTS (
            SELECT 1 FROM capture_files f
            WHERE f.capture_id = ti.capture_id AND f.status = 'Available'
        )
    """, [tag.id])

    return schemas.CaptureTag(
        id = tag.id,
        name = tag.name,
        created_at = tag.created_at,
        updated_at = tag.updated_at,
        capture_count = rows[0]['count'],
    )


async def ValidateCaptureIDs(ids: list[int]) -> list[int]:
    """
    指定されたキャプチャがすべて存在するかを確認する (1つでも存在しなければ、変更する前に 404 エラーにする)

    Args:
        ids (list[int]): リクエストで指定されたキャプチャの ID

    Returns:
        list[int]: 重複を除いたキャプチャの ID
    """

    ids = sorted(set(ids))
    if await Capture.filter(id__in=ids).count() != len(ids):
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Capture not found',
        )
    return ids


@router.get(
    '',
    summary = 'キャプチャ一覧 API',
    response_description = 'ページ内のキャプチャと、それらが参照する放送回の番組情報、次のページのカーソル。',
    response_model = schemas.Captures,
)
async def CapturesAPI(
    response: Response,
    user: Annotated[User | None, Depends(GetOptionalCurrentUser)],
    filters: Annotated[CaptureFilters, Query()],
    order: Annotated[CaptureOrder, Query(description='並び順 (CapturedAtDesc or CapturedAtAsc or BroadcastAtDesc or BroadcastAtAsc or PlaybackPosition) 。')] = 'CapturedAtDesc',
    cursor: Annotated[str | None, Query(description='前のページのレスポンスに含まれる next_cursor 。')] = None,
    limit: Annotated[int, Query(ge=1, le=200, description='1ページに取得する最大枚数。')] = 100,
    date: Annotated[Date | None, Query(description='この日付 (日本時間) に撮影・放送されたキャプチャだけを取得する。')] = None,
    day_start_hour: Annotated[int, Query(ge=0, le=23, description='日付の境目とする時刻 (28時間表記なら 4) 。')] = 0,
):
    """
    キャプチャを、キーセット方式のページングで一覧する。<br>
    同じ時刻に撮影されたキャプチャも、ページの境目で欠けずに取得できる。<br>
    ログインしている場合は、本人のお気に入りとタグの状態も返す。
    """

    # 本人のお気に入りとタグの状態を含むので、共有のキャッシュに入れさせない
    response.headers['Cache-Control'] = 'private, no-store'

    conditions, params = await BuildCaptureWhere(filters, user)

    # 放送日時の順では、放送日時の分からないキャプチャ (番組の情報がないもの) を除く
    if order.startswith('BroadcastAt'):
        axis = 'broadcast_at'
        conditions.append('c.broadcast_at IS NOT NULL')
    else:
        axis = 'captured_at'

    # 日付を指定された場合は、その日の境目の時刻から24時間の範囲に絞る
    if date is not None:
        start = datetime.combine(date, datetime.min.time(), JST) + timedelta(hours=day_start_hour)
        conditions.append(f'c.{axis} >= ? AND c.{axis} < ?')
        params.extend([SQLDateTime(start), SQLDateTime(start + timedelta(days=1))])

    # 並びのキーの式 (再生位置の順では、再生位置のないキャプチャを最後に並べる)
    if order == 'PlaybackPosition':
        sort_expressions = [
            '(c.playback_position IS NULL)',
            'COALESCE(c.playback_position, 0)',
            'c.captured_at',
            'c.id',
        ]
    else:
        sort_expressions = [f'c.{axis}', 'c.id']
    is_descending = order.endswith('Desc')

    # 並びのキーと ID の組で、前のページの続きから取得する
    ## 日時だけを境目にすると、同じ秒に撮ったキャプチャがページの境目で抜ける
    user_id = user.id if user is not None else None
    signature = CursorSignature([order, date, day_start_hour, filters.model_dump(mode='json'), user_id])
    if cursor is not None:
        keys = DecodeCursor(cursor, signature, len(sort_expressions))
        comparison = '<' if is_descending else '>'
        conditions.append(f'({", ".join(sort_expressions)}) {comparison} ({", ".join("?" for _ in keys)})')
        params.extend(keys)

    # キャプチャを取得する (次のページがあるかを知るため、1件多く取得する)
    direction = 'DESC' if is_descending else 'ASC'
    rows = await connections.get('default').execute_query_dict(f"""
        SELECT c.*
        FROM captures c
        LEFT JOIN capture_programs p ON p.id = c.capture_program_id
        WHERE {' AND '.join(conditions)}
        ORDER BY {', '.join(f'{expression} {direction}' for expression in sort_expressions)}
        LIMIT ?
    """, [*params, limit + 1])

    # 1件多く取得できたら次のページがあるので、ページの最後の行の並びのキーをカーソルにする
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last_row = rows[-1]
        if order == 'PlaybackPosition':
            last_keys = [
                int(last_row['playback_position'] is None),
                last_row['playback_position'] or 0,
                last_row['captured_at'],
                last_row['id'],
            ]
        else:
            last_keys = [last_row[axis], last_row['id']]
        next_cursor = EncodeCursor(signature, last_keys)

    # ページ内のキャプチャと、それらが参照する放送回の番組情報を返す
    captures = await SerializeCaptures(rows, user)
    capture_program_ids: set[int] = set()
    for capture in captures:
        if capture.capture_program_id is not None:
            capture_program_ids.add(capture.capture_program_id)
    programs = await SerializePrograms(sorted(capture_program_ids))
    return schemas.Captures(captures=captures, programs=programs, next_cursor=next_cursor)


@router.post(
    '',
    summary = 'キャプチャ画像アップロード API',
    status_code = status.HTTP_201_CREATED,
    response_description = '保存したキャプチャ (同じ内容のキャプチャが既にある場合はそのキャプチャ) 。',
    response_model = schemas.Capture,
)
async def CaptureUploadAPI(
    image: Annotated[UploadFile, File(description='アップロードするキャプチャ画像 (JPEG or PNG)。')],
    user: Annotated[User | None, Depends(GetOptionalCurrentUser)],
    file_modified_at: Annotated[float | None, Form(allow_inf_nan=False, description='元のファイルの更新日時 (UNIX 時間のミリ秒) 。手元のファイルをアップロードするときに指定する。')] = None,
):
    """
    クライアント側でキャプチャした画像や手元の画像をサーバーにアップロードする。<br>
    アップロードされた画像は、サーバー設定で指定されたフォルダに保存し、その場でキャプチャとして登録する。<br>
    同じ内容のキャプチャが既に保存されている場合は、保存せずにそのキャプチャを返す。
    """

    # アップロードされた画像を読み込む
    ## 上限を超える巨大なファイルをメモリに載せないよう、上限より 1 バイトだけ多く読み込み、上限を超えていたらエラーにする
    data = await image.read(CAPTURE_UPLOAD_MAX_SIZE + 1)
    if len(data) > CAPTURE_UPLOAD_MAX_SIZE:
        logging.error('[CapturesRouter][CaptureUploadAPI] Too large image file was uploaded.')
        raise HTTPException(
            status_code = status.HTTP_413_CONTENT_TOO_LARGE,
            detail = 'Image file is too large',
        )

    # 保存するファイルの更新日時 (手元のファイルをアップロードした場合は、元のファイルの更新日時を引き継ぐ)
    modified_at = datetime.now(JST)
    if file_modified_at is not None:
        try:
            modified_at = datetime.fromtimestamp(file_modified_at / 1000, JST)
        except (ValueError, OverflowError, OSError) as ex:
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail = 'Invalid file_modified_at',
            ) from ex

    # ファイルを保存先フォルダの直下だけに作るため、パスの区切り (Windows の区切りを含む) などを含むファイル名はエラーにする
    filename = image.filename or ''
    if filename in ('', '.', '..') or '/' in filename or '\\' in filename or '\x00' in filename or ':' in filename:
        logging.error('[CapturesRouter][CaptureUploadAPI] Invalid filename was specified.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Specified filename is invalid',
        )

    # キャプチャは JPEG か PNG の画像なので、拡張子が .jpg / .jpeg / .png 以外のファイル名はエラーにする
    ## JPEG は末尾に任意のデータを付けても画像として読めるため、中身の検査だけでは .bat のような実行できるファイルとしても保存できてしまう
    if filename.lower().endswith(('.jpg', '.jpeg', '.png')) is False:
        logging.error('[CapturesRouter][CaptureUploadAPI] Filename with unsupported extension was specified.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Please upload JPEG or PNG image',
        )

    # 画像が JPEG または PNG かをチェック
    ## 万が一悪意ある攻撃者から危険なファイルを送り込まれないように
    ## 受け止めるのは画像として読めないことを示す例外だけにし (registerFile() と同じ)、実装側の誤りはそのまま 500 として伝える
    try:
        await asyncio.to_thread(ReadCaptureImage, data, filename, modified_at)
    except (UnidentifiedImageError, SyntaxError, ValueError, Image.DecompressionBombError, OSError) as ex:
        logging.error('[CapturesRouter][CaptureUploadAPI] Invalid image file was uploaded.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Please upload JPEG or PNG image',
        ) from ex

    # 同じ内容のキャプチャが、今も保存先に実在すると確認できたときだけ、保存を省いてそのキャプチャを返す
    scanner = CaptureScanTask()
    existing_capture = await Capture.get_or_none(file_hash=hashlib.sha256(data).digest())
    if existing_capture is not None:
        for existing_file in await CaptureFile.filter(capture_id=existing_capture.id, status='Available'):
            try:
                async with scanner.getPathLock(existing_file.file_path):
                    stat = await anyio.Path(existing_file.file_path).stat()
                    is_unchanged = (
                        stat.st_size == existing_file.file_size and
                        datetime.fromtimestamp(stat.st_ctime, JST) == existing_file.file_created_at and
                        datetime.fromtimestamp(stat.st_mtime, JST) == existing_file.file_modified_at
                    )
                    if is_unchanged is False:
                        continue
                    # 移動の照合で、同じ名前・サイズ・更新日時の別の画像に場所が付け替わっていることがあるので、中身のハッシュも照合する
                    ## 別の画像だったら読んだ内容で登録し直し、ほかの場所を試す (どこにもなければ、このあとで保存する)
                    existing_data = await anyio.Path(existing_file.file_path).read_bytes()
                    existing_digest = await asyncio.to_thread(lambda: hashlib.sha256(existing_data).digest())
                    if existing_digest != bytes(existing_capture.file_hash):
                        await scanner.registerFile(existing_file.file_path, data=existing_data, force=True)
                        continue
                    return (await SerializeCaptures(await GetCaptureRows([existing_capture.id]), user))[0]
            except OSError:
                continue

    # 先頭から順に保存容量が空いている保存先フォルダを探す
    upload_folders = Config().capture.upload_folders
    for index, upload_folder in enumerate(upload_folders):

        # 万が一保存先フォルダが存在しない場合は次の保存先フォルダを探す
        root = anyio.Path(NormalizeCapturePath(upload_folder))
        if not await root.is_dir():
            continue

        # 保存先フォルダの空き容量が 10MB 未満なら、最後のフォルダでなければ次の保存先フォルダを探す
        disk_usage = await asyncio.to_thread(shutil.disk_usage, str(root))
        if disk_usage.free < 10 * 1024 * 1024 and index < len(upload_folders) - 1:
            continue

        # 同じ名前のファイルがあれば、-1 などの連番を付けた名前で保存する
        count = 0
        while True:
            if count == 0:
                name = filename
            else:
                name = f'{Path(filename).stem}-{count}{Path(filename).suffix}'
            path = NormalizeCapturePath(root / name)
            # 実際に作るファイルは、受け取った名前の大文字小文字のままにする (ロックと DB には正規化したパスを使う)
            ## Windows の正規化はパスを小文字にするので、そのまま作ると、保存先のファイル名まで小文字になってしまう
            saved_path = os.path.abspath(os.path.join(os.path.normpath(str(upload_folder)), name))

            async with scanner.getPathLock(path):
                # このリクエストでファイルを作ったかどうか (保存に失敗したときに、作ったファイルだけを消すため)
                is_created = False
                try:
                    # 同じ秒に撮った2枚を同時に受け取っても別の名前で保存できるよう、ファイルの作成そのものを排他的に行う
                    async with await anyio.open_file(saved_path, 'xb') as output:
                        is_created = True
                        await output.write(data)
                    if file_modified_at is not None:
                        await asyncio.to_thread(os.utime, saved_path, (modified_at.timestamp(), modified_at.timestamp()))

                    # 保存したファイルを、スキャンを待たずにその場でキャプチャとして登録する
                    capture = await scanner.registerFile(path, data=data)
                    if capture is None:
                        raise HTTPException(
                            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail = 'Please upload JPEG or PNG image',
                        )
                    return (await SerializeCaptures(await GetCaptureRows([capture.id]), user))[0]

                except FileExistsError:
                    count += 1
                    continue

                except OSError as ex:
                    # 容量不足などで書き込みの途中で失敗したら、書きかけのファイルを消す
                    ## 残しておくと、次のスキャンで画像として読めないファイルとして登録され、保存先に溜まっていく
                    if is_created is True:
                        try:
                            await anyio.Path(saved_path).unlink(missing_ok=True)
                        except OSError as unlink_ex:
                            logging.error(f'Cannot delete partially written capture image: {saved_path}', exc_info=unlink_ex)

                    if isinstance(ex, PermissionError):
                        raise HTTPException(
                            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail = 'Permission denied to save the file',
                        ) from ex

                    # 容量不足 (Windows では ERROR_DISK_FULL = 112) は、ほかのエラーと分けて伝える
                    detail = 'Unexpected error occurred while saving the file'
                    if ex.errno == errno.ENOSPC or (os.name == 'nt' and ex.winerror == 112):
                        detail = 'No space left on the device'
                    logging.error('Cannot save capture image.', exc_info=ex)
                    raise HTTPException(
                        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail = detail,
                    ) from ex

    raise HTTPException(
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail = 'No available folder to save the file',
    )


@router.delete(
    '',
    summary = 'キャプチャ削除 API',
    response_description = '削除できたキャプチャと、削除できなかったキャプチャの ID 。',
    response_model = schemas.CaptureDeleteResult,
)
async def CapturesDeleteAPI(
    body: schemas.CaptureIDsRequest,
    user: Annotated[User, Depends(GetCurrentAdminUser)],
):
    """
    指定されたキャプチャを、実体のファイルごと削除する。<br>
    すべての場所のファイルを削除できたキャプチャだけを DB から削除する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    result = schemas.CaptureDeleteResult(deleted_capture_ids=[], failed_capture_ids=[])
    for id in sorted(set(body.capture_ids)):
        if await CaptureScanTask().deleteCapture(id):
            result.deleted_capture_ids.append(id)
        else:
            result.failed_capture_ids.append(id)
    return result


@router.get(
    '/sections',
    summary = 'キャプチャ日付別件数 API',
    response_description = '新しい順の日付ごとの件数と、全体の件数。',
    response_model = schemas.CaptureSections,
)
async def CaptureSectionsAPI(
    response: Response,
    user: Annotated[User | None, Depends(GetOptionalCurrentUser)],
    filters: Annotated[CaptureFilters, Query()],
    axis: Annotated[Literal['CapturedAt', 'BroadcastAt'], Query(description='日付の軸 (CapturedAt or BroadcastAt) 。')] = 'CapturedAt',
    day_start_hour: Annotated[int, Query(ge=0, le=23, description='日付の境目とする時刻 (28時間表記なら 4) 。')] = 0,
):
    """
    キャプチャの件数を、日本時間の日付ごとに数えて返す。<br>
    タイムラインの右端の年月の目盛り (スクラバー) に使う。絞り込みの条件はキャプチャ一覧 API と同じ。
    """

    # お気に入りやタグで絞り込んだ集計を含むので、共有のキャッシュに入れさせない
    response.headers['Cache-Control'] = 'private, no-store'

    # 絞り込みのない集計は、キャプチャの登録や削除があるまでメモリにキャッシュして使い回す
    scanner = CaptureScanTask()
    cache_key = (axis, day_start_hour)
    can_cache = all(value is None for value in filters.model_dump().values())
    generation = scanner.sections_generation
    if can_cache is True and cache_key in scanner.sections_cache:
        return scanner.sections_cache[cache_key]

    conditions, params = await BuildCaptureWhere(filters, user)

    # 集計する日時の列 (放送日時の軸では、放送日時の分からないキャプチャを除く)
    if axis == 'CapturedAt':
        column = 'captured'
    else:
        column = 'broadcast'
    conditions.append(f'c.{column}_at IS NOT NULL')

    # 日時を日本時間に直してから、日付の境目の時刻の分だけずらした日付で数える
    ## DB の日時は +09:00 付きで保存されていて、SQLite の date() は UTC に直して扱うので、9時間を足して日本時間に戻す
    date_expression = f"date(c.{column}_at, '+9 hours', '-{day_start_hour} hours')"

    # 放送回の列 (p.) を条件に使う場合のみ、capture_programs テーブルを JOIN する
    ## JOIN しない場合は、captures テーブルの行を読み込まずに、日時と ID のインデックスだけを走査して件数を数えられる
    program_join = ''
    if any(re.search(r'\bp\.', condition) is not None for condition in conditions):
        program_join = 'LEFT JOIN capture_programs p ON p.id = c.capture_program_id'

    rows = await connections.get('default').execute_query_dict(f"""
        SELECT
            {date_expression} AS date,
            COUNT(*) AS count
        FROM captures c
        {program_join}
        WHERE {' AND '.join(conditions)}
        GROUP BY {date_expression}
        ORDER BY date DESC
    """, params)
    sections = [schemas.CaptureSection.model_validate(row) for row in rows]
    result = schemas.CaptureSections(sections=sections, total=sum(section.count for section in sections))

    # 集計の途中で DB が変わっていたら、古い集計はキャッシュに入れずに返すだけにする
    if can_cache is True and generation == scanner.sections_generation:
        scanner.sections_cache[cache_key] = result

    return result


@router.get(
    '/programs',
    summary = 'キャプチャ放送回一覧 API',
    response_description = '放送回のアルバムのリストと、次のページのカーソル。',
    response_model = schemas.CapturePrograms,
)
async def CaptureProgramsAPI(
    response: Response,
    user: Annotated[User | None, Depends(GetOptionalCurrentUser)],
    cursor: Annotated[str | None, Query(description='前のページのレスポンスに含まれる next_cursor 。')] = None,
    limit: Annotated[int, Query(ge=1, le=200, description='1ページに取得する最大の放送回の数。')] = 60,
    query: Annotated[str | None, Query(description='検索キーワード。番組名かチャンネル名に部分一致する放送回を検索する。')] = None,
    has_recorded_program: Annotated[bool | None, Query(description='同じ番組の録画番組があるかどうかで絞り込む。')] = None,
    order: Annotated[CaptureProgramOrder, Query(description='並び順 (BroadcastAtDesc or BroadcastAtAsc) 。')] = 'BroadcastAtDesc',
):
    """
    キャプチャのある放送回を、放送日時の順 (既定は新しい順) にアルバムとして一覧する。<br>
    半角または全角スペースで区切ることで、複数のキーワードによる AND 検索が可能。
    """

    # 代表のキャプチャに本人のお気に入りとタグの状態を含むので、共有のキャッシュに入れさせない
    response.headers['Cache-Control'] = 'private, no-store'

    # 利用できるキャプチャが1枚以上ある放送回だけに絞る
    conditions = ["""
        EXISTS (
            SELECT 1 FROM captures c
            WHERE c.capture_program_id = p.id AND EXISTS (
                SELECT 1 FROM capture_files f
                WHERE f.capture_id = c.id AND f.status = 'Available'
            )
        )
    """.strip()]
    params: list[Any] = []

    # 検索語は、番組名とチャンネル名のどちらかに含まれていれば当てはまる
    for keyword in (query or '').split():
        conditions.append("""
            (
                LOWER(p.title) LIKE ? OR
                EXISTS (
                    SELECT 1 FROM channels ch
                    WHERE ch.network_id = p.network_id AND ch.service_id = p.service_id AND LOWER(ch.name) LIKE ?
                )
            )
        """.strip())
        params.extend([f'%{keyword.lower()}%'] * 2)  # 2つの検索対象に同じパラメータを使う

    # 同じ番組キーの録画番組があるかどうかで絞り込む
    ## 録画ファイルが見つからなくなった (Missing の) 録画番組は開けないので、録画番組がないものとして扱う
    recorded_program_condition = """
        EXISTS (
            SELECT 1 FROM recorded_programs r
            JOIN recorded_videos rv ON rv.recorded_program_id = r.id
            WHERE r.network_id = p.network_id
                AND r.service_id = p.service_id
                AND r.event_id = p.event_id
                AND r.start_time = p.start_time
                AND rv.status != 'Missing'
        )
    """.strip()
    if has_recorded_program is True:
        conditions.append(recorded_program_condition)
    elif has_recorded_program is False:
        conditions.append(f'NOT {recorded_program_condition}')

    # 放送開始日時と ID の組で、前のページの続きから取得する
    ## 降順なら前のページの最後の行より前の行を、昇順なら後ろの行を取得する
    is_descending = order == 'BroadcastAtDesc'
    user_id = user.id if user is not None else None
    signature = CursorSignature(['Programs', query, has_recorded_program, order, user_id])
    if cursor is not None:
        if is_descending:
            conditions.append('(p.start_time, p.id) < (?, ?)')
        else:
            conditions.append('(p.start_time, p.id) > (?, ?)')
        params.extend(DecodeCursor(cursor, signature, 2))

    # 放送回を取得する (次のページがあるかを知るため、1件多く取得する)
    direction = 'DESC' if is_descending else 'ASC'
    rows = await connections.get('default').execute_query_dict(f"""
        SELECT p.id, p.start_time
        FROM capture_programs p
        WHERE {' AND '.join(conditions)}
        ORDER BY p.start_time {direction}, p.id {direction}
        LIMIT ?
    """, [*params, limit + 1])

    # 1件多く取得できたら次のページがあるので、ページの最後の行の放送開始日時と ID をカーソルにする
    next_cursor = None
    if len(rows) > limit:
        next_cursor = EncodeCursor(signature, [rows[limit - 1]['start_time'], rows[limit - 1]['id']])

    # 放送回ごとにアルバム (枚数・撮影期間・代表のキャプチャ) を作る
    ids = [row['id'] for row in rows[:limit]]
    programs_by_id = {program.id: program for program in await SerializePrograms(ids)}
    albums = [await GetProgramAlbum(programs_by_id[id], user) for id in ids]
    return schemas.CapturePrograms(programs=albums, next_cursor=next_cursor)


@router.get(
    '/programs/{capture_program_id}',
    summary = 'キャプチャ放送回 API',
    response_description = '放送回のアルバム。',
    response_model = schemas.CaptureProgramAlbum,
)
async def CaptureProgramAPI(
    capture_program_id: int,
    response: Response,
    user: Annotated[User | None, Depends(GetOptionalCurrentUser)],
):
    """
    指定された放送回のアルバムを取得する。
    """

    # 代表のキャプチャに本人のお気に入りとタグの状態を含むので、共有のキャッシュに入れさせない
    response.headers['Cache-Control'] = 'private, no-store'

    programs = await SerializePrograms([capture_program_id])
    if len(programs) == 0:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Capture program not found',
        )
    return await GetProgramAlbum(programs[0], user)


@router.get(
    '/tags',
    summary = 'キャプチャタグ一覧 API',
    response_description = '本人のタグのリスト。',
    response_model = list[schemas.CaptureTag],
)
async def CaptureTagsAPI(
    response: Response,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    ログイン中のユーザーのタグを、名前の順に取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 本人のタグなので、共有のキャッシュに入れさせない
    response.headers['Cache-Control'] = 'private, no-store'

    tags = await CaptureTag.filter(user_id=user.id).order_by('name')
    return [await SerializeTag(tag) for tag in tags]


@router.post(
    '/tags',
    summary = 'キャプチャタグ作成 API',
    status_code = status.HTTP_201_CREATED,
    response_description = '作成したタグ。',
    response_model = schemas.CaptureTag,
)
async def CaptureTagCreateAPI(
    body: schemas.CaptureTagRequest,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    ログイン中のユーザーのタグを作成する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 同じ名前のタグは、ユーザーごとの一意制約に当たるので 422 エラーにする
    try:
        tag = await CaptureTag.create(user_id=user.id, name=body.name)
    except IntegrityError as ex:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Capture tag name already exists',
        ) from ex

    return await SerializeTag(tag)


@router.put(
    '/tags/{tag_id}',
    summary = 'キャプチャタグ更新 API',
    response_description = '名前を変更したタグ。',
    response_model = schemas.CaptureTag,
)
async def CaptureTagUpdateAPI(
    tag_id: int,
    body: schemas.CaptureTagRequest,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    ログイン中のユーザーのタグの名前を変更する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    tag = await GetOwnedTag(tag_id, user)

    # 同じ名前のタグは、ユーザーごとの一意制約に当たるので 422 エラーにする
    tag.name = body.name
    try:
        await tag.save()
    except IntegrityError as ex:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail = 'Capture tag name already exists',
        ) from ex

    return await SerializeTag(tag)


@router.delete(
    '/tags/{tag_id}',
    summary = 'キャプチャタグ削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CaptureTagDeleteAPI(
    tag_id: int,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    ログイン中のユーザーのタグを削除する。タグを付けていたキャプチャはそのまま残る。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    tag = await GetOwnedTag(tag_id, user)
    await tag.delete()


@router.post(
    '/favorites',
    summary = 'キャプチャお気に入り追加 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CaptureFavoritesCreateAPI(
    body: schemas.CaptureIDsRequest,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定されたキャプチャを、ログイン中のユーザーのお気に入りにまとめて追加する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    # 既にお気に入りに追加しているキャプチャは、一意制約に当たっても無視する
    ids = await ValidateCaptureIDs(body.capture_ids)
    favorites = [CaptureFavorite(user_id=user.id, capture_id=id) for id in ids]
    await CaptureFavorite.bulk_create(favorites, ignore_conflicts=True, batch_size=200)


@router.delete(
    '/favorites',
    summary = 'キャプチャお気に入り削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CaptureFavoritesDeleteAPI(
    body: schemas.CaptureIDsRequest,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定されたキャプチャを、ログイン中のユーザーのお気に入りからまとめて外す。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    await CaptureFavorite.filter(user_id=user.id, capture_id__in=body.capture_ids).delete()


@router.post(
    '/tags/{tag_id}/items',
    summary = 'キャプチャタグ付け API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CaptureTagItemsCreateAPI(
    tag_id: int,
    body: schemas.CaptureIDsRequest,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    ログイン中のユーザーのタグを、指定されたキャプチャにまとめて付ける。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    await GetOwnedTag(tag_id, user)

    # 既にタグを付けているキャプチャは、一意制約に当たっても無視する
    ids = await ValidateCaptureIDs(body.capture_ids)
    tag_items = [CaptureTagItem(tag_id=tag_id, capture_id=id) for id in ids]
    await CaptureTagItem.bulk_create(tag_items, ignore_conflicts=True, batch_size=200)


@router.delete(
    '/tags/{tag_id}/items',
    summary = 'キャプチャタグ外し API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CaptureTagItemsDeleteAPI(
    tag_id: int,
    body: schemas.CaptureIDsRequest,
    user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    ログイン中のユーザーのタグを、指定されたキャプチャからまとめて外す。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていないとアクセスできない。
    """

    await GetOwnedTag(tag_id, user)
    await CaptureTagItem.filter(tag_id=tag_id, capture_id__in=body.capture_ids).delete()


@router.get(
    '/{capture_id}',
    summary = 'キャプチャ詳細 API',
    response_description = 'キャプチャの詳細 (放送回の番組情報と保存場所を含む) 。',
    response_model = schemas.CaptureDetail,
)
async def CaptureAPI(
    capture_id: int,
    response: Response,
    user: Annotated[User | None, Depends(GetOptionalCurrentUser)],
):
    """
    指定されたキャプチャの詳細を取得する。
    """

    # 本人のお気に入りとタグの状態を含むので、共有のキャッシュに入れさせない
    response.headers['Cache-Control'] = 'private, no-store'

    rows = await GetCaptureRows([capture_id])
    if len(rows) == 0:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Capture not found',
        )
    capture = (await SerializeCaptures(rows, user))[0]

    # キャプチャを撮った放送回の番組情報
    program: schemas.CaptureProgram | None = None
    if capture.capture_program_id is not None:
        programs = await SerializePrograms([capture.capture_program_id])
        if len(programs) > 0:
            program = programs[0]

    # 保存場所の一覧
    files: list[schemas.CaptureFile] = []
    for file in await CaptureFile.filter(capture_id=capture_id):
        files.append(schemas.CaptureFile.model_validate({
            'file_name': file.file_name,
            'file_path': file.file_path,
            'status': file.status,
        }))

    return schemas.CaptureDetail(**capture.model_dump(), program=program, files=files)


@router.get(
    '/{capture_id}/image',
    summary = 'キャプチャ画像 API',
)
async def CaptureImageAPI(
    capture_id: int,
    hash: Annotated[str, Query(pattern='^[0-9a-f]{64}$', description='キャプチャの内容の SHA-256 (小文字の16進数) 。')],
):
    """
    キャプチャの画像 (原寸) を取得する。<br>
    読み込んだ内容のハッシュが URL の hash と一致したときだけ、長期間キャッシュできる画像として返す。
    """

    capture = await Capture.get_or_none(id=capture_id)
    if capture is None or bytes(capture.file_hash).hex() != hash:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Capture image not found',
            headers = {'Cache-Control': 'no-store'},
        )

    # 利用できる場所を順に読み、内容のハッシュが URL と一致した画像を返す
    scanner = CaptureScanTask()
    for file in await CaptureFile.filter(capture_id=capture_id, status='Available'):
        try:
            async with scanner.getPathLock(file.file_path):
                data = await anyio.Path(file.file_path).read_bytes()
                digest = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())

                # サイズと作成日時・更新日時を変えずに中身だけ置き換わっていたので、読み直して登録し直し、ほかの場所を試す
                if digest != hash:
                    await scanner.registerFile(file.file_path, data=data, force=True)
                    continue

                if data.startswith(b'\x89PNG\r\n\x1a\n'):
                    media_type = 'image/png'
                else:
                    media_type = 'image/jpeg'
                return Response(data, media_type=media_type, headers={
                    'Cache-Control': 'public, max-age=31536000, immutable',
                    'ETag': f'"{hash}"',
                })
        except OSError:
            continue

    raise HTTPException(
        status_code = status.HTTP_404_NOT_FOUND,
        detail = 'Capture image not found',
        headers = {'Cache-Control': 'no-store'},
    )
