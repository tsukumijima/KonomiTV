
import json
import pathlib
from ariblib.sections import TimeOffsetSection
from datetime import datetime
from email.utils import parsedate
from typing import Annotated, Any, Literal

import anyio
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from starlette.datastructures import Headers
from tortoise import connections

from app import logging, schemas
from app.constants import STATIC_DIR, THUMBNAILS_DIR
from app.metadata.RecordedScanTask import RecordedScanTask
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.metadata.TSInfoAnalyzer import TSInfoAnalyzer
from app.models.RecordedProgram import RecordedProgram
from app.models.User import User
from app.routers.UsersRouter import GetCurrentAdminUser
from app.utils.DriveIOLimiter import DriveIOLimiter
from app.utils.JikkyoClient import JikkyoClient


# ルーター
router = APIRouter(
    tags = ['Videos'],
    prefix = '/api/videos',
)

# ページングで一度に取得する録画番組の数
PAGE_SIZE = 30


async def ConvertRowToRecordedProgram(row: dict[str, Any]) -> schemas.RecordedProgram:
    """ データベースの行データを RecordedProgram Pydantic モデルに変換する共通処理 """

    # key_frames の存在確認
    # 高速化のため、SQL で計算された has_key_frames を直接参照する
    has_key_frames: bool = bool(row['has_key_frames'])

    # cm_sections は小さいので、通常通りパースする
    cm_sections: list[schemas.CMSection] | None = None
    if row['cm_sections'] is not None:
        cm_sections = json.loads(row['cm_sections'])

    # thumbnail_info は小さいので、通常通りパースする
    thumbnail_info: schemas.ThumbnailInfo | None = None
    if row['thumbnail_info'] is not None:
        if isinstance(row['thumbnail_info'], str):
            thumbnail_info = json.loads(row['thumbnail_info'])
        else:
            thumbnail_info = row['thumbnail_info']

    # recorded_video のデータを構築
    recorded_video_dict = {
        'id': row['rv_id'],
        'status': row['status'],
        'file_path': row['file_path'],
        'file_hash': row['file_hash'],
        'file_size': row['file_size'],
        'file_created_at': row['file_created_at'],
        'file_modified_at': row['file_modified_at'],
        'recording_start_time': row['recording_start_time'],
        'recording_end_time': row['recording_end_time'],
        'duration': row['video_duration'],
        'container_format': row['container_format'],
        'video_codec': row['video_codec'],
        'video_codec_profile': row['video_codec_profile'],
        'video_scan_type': row['video_scan_type'],
        'video_frame_rate': row['video_frame_rate'],
        'video_resolution_width': row['video_resolution_width'],
        'video_resolution_height': row['video_resolution_height'],
        'primary_audio_codec': row['primary_audio_codec'],
        'primary_audio_channel': row['primary_audio_channel'],
        'primary_audio_sampling_rate': row['primary_audio_sampling_rate'],
        'secondary_audio_codec': row['secondary_audio_codec'],
        'secondary_audio_channel': row['secondary_audio_channel'],
        'secondary_audio_sampling_rate': row['secondary_audio_sampling_rate'],
        'has_key_frames': has_key_frames,
        'cm_sections': cm_sections,
        'thumbnail_info': thumbnail_info,
        'created_at': row['rv_created_at'],
        'updated_at': row['rv_updated_at'],
    }

    # channel のデータを構築 (channel_id が存在する場合のみ)
    channel_dict: dict[str, Any] | None = None
    if row['ch_id'] is not None:
        channel_dict = {
            'id': row['ch_id'],
            'display_channel_id': row['display_channel_id'],
            'network_id': row['ch_network_id'],
            'service_id': row['ch_service_id'],
            'transport_stream_id': row['transport_stream_id'],
            'remocon_id': row['remocon_id'],
            'channel_number': row['channel_number'],
            'type': row['type'],
            'name': row['ch_name'],
            'jikkyo_force': row['jikkyo_force'],
            'is_subchannel': bool(row['is_subchannel']),
            'is_radiochannel': bool(row['is_radiochannel']),
            'is_watchable': bool(row['is_watchable']),
        }

    # recorded_program のデータを構築
    recorded_program_dict = {
        'id': row['rp_id'],
        'recorded_video': recorded_video_dict,
        'recording_start_margin': row['recording_start_margin'],
        'recording_end_margin': row['recording_end_margin'],
        'is_partially_recorded': bool(row['is_partially_recorded']),
        'channel': channel_dict,  # channel_id が存在しない場合は None
        'channel_id': row['channel_id'],
        'network_id': row['network_id'],
        'service_id': row['service_id'],
        'event_id': row['event_id'],
        'series_id': row['series_id'],
        'series_broadcast_period_id': row['series_broadcast_period_id'],
        'title': row['title'],
        'series_title': row['series_title'],
        'episode_number': row['episode_number'],
        'subtitle': row['subtitle'],
        'description': row['description'],
        'detail': json.loads(row['detail']),
        'start_time': row['start_time'],
        'end_time': row['end_time'],
        'duration': row['duration'],
        'is_free': bool(row['is_free']),
        'genres': json.loads(row['genres']),
        'primary_audio_type': row['primary_audio_type'],
        'primary_audio_language': row['primary_audio_language'],
        'secondary_audio_type': row['secondary_audio_type'],
        'secondary_audio_language': row['secondary_audio_language'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }

    # Pydantic モデルに変換して返す
    return schemas.RecordedProgram.model_validate(recorded_program_dict)


async def GetRecordedProgram(video_id: Annotated[int, Path(description='録画番組の ID 。')]) -> RecordedProgram:
    """ 録画番組 ID から録画番組情報を取得する """

    # 録画番組情報を取得
    recorded_program = await RecordedProgram.all() \
        .select_related('recorded_video') \
        .select_related('channel') \
        .get_or_none(id=video_id)
    if recorded_program is None:
        logging.error(f'[VideosRouter][GetRecordedProgram] Specified video_id was not found. [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    return recorded_program


async def GetThumbnailResponse(
    request: Request,
    recorded_program: RecordedProgram,
    return_tiled: bool = False,
) -> FileResponse | Response:
    """
    サムネイル画像のレスポンスを生成する共通処理
    ETags と Last-Modified を使ったキャッシュ制御を行う

    Args:
        request (Request): FastAPI のリクエストオブジェクト
        recorded_program (RecordedProgram): 録画番組情報
        is_tile (bool, optional): シークバー用タイル画像かどうか. Defaults to False.

    Returns:
        Union[FileResponse, Response]: サムネイル画像のレスポンス
    """

    def IsContentNotModified(response_headers: Headers, request_headers: Headers) -> bool:
        """
        リクエストヘッダーとレスポンスヘッダーから、304 を返すべきかどうかを判定する

        Args:
            response_headers (Headers): レスポンスヘッダー
            request_headers (Headers): リクエストヘッダー

        Returns:
            bool: 304 を返すべき場合は True
        """

        def ParseIfNoneMatch(header_value: str) -> set[str]:
            """ If-None-Match ヘッダーを RFC 準拠の形で解析してタグ集合に変換する """

            tags: set[str] = set()
            for raw_tag in header_value.split(','):
                tag = raw_tag.strip()
                if not tag:
                    continue
                if tag == '*':
                    tags.add('*')
                    continue
                if tag.startswith('W/'):
                    tag = tag[2:]
                if len(tag) >= 2 and tag[0] == '"' and tag[-1] == '"':
                    tag = tag[1:-1]
                tags.add(tag)
            return tags

        # If-None-Match による判定 (優先度が最も高い)
        if_none_match = request_headers.get('if-none-match')
        etag = response_headers.get('etag')
        if if_none_match is not None:
            request_tags = ParseIfNoneMatch(if_none_match)
            if '*' in request_tags:
                # * はリソースが存在するなら常に 304 を返す
                return etag is not None
            if etag is not None:
                normalized_etag = etag.strip('"')
                if normalized_etag in request_tags or etag in request_tags:
                    return True
            # If-None-Match が存在する場合は If-Modified-Since を無視する (RFC 準拠)
            return False

        # If-Modified-Since による判定 (If-None-Match が無い場合のみ評価)
        try:
            if_modified_since = parsedate(request_headers['if-modified-since'])
            last_modified = parsedate(response_headers['last-modified'])
            if (
                if_modified_since is not None and
                last_modified is not None and
                if_modified_since >= last_modified
            ):
                return True
        except KeyError:
            pass

        return False

    def CreateDefaultThumbnailResponse() -> FileResponse:
        """ 録画中 or サムネイル画像が存在しない場合に返すデフォルトのレスポンスを返す """

        default_thumbnail_path = STATIC_DIR / 'thumbnails/default.webp'
        # キャッシュさせないようにヘッダーを設定
        headers = {
            'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        }
        return FileResponse(
            path = default_thumbnail_path,
            media_type = 'image/webp',
            headers = headers,
        )

    # 録画中のファイルは常にデフォルトのサムネイル画像を返す
    if recorded_program.recorded_video.status == 'Recording':
        return CreateDefaultThumbnailResponse()

    # サムネイル画像のパスを生成
    suffix = '_tile' if return_tiled else ''
    base_path = anyio.Path(str(THUMBNAILS_DIR)) / f'{recorded_program.recorded_video.file_hash}{suffix}'

    # WebP のみを試す
    thumbnail_path = None
    media_type = None
    path = base_path.with_suffix('.webp')
    if await path.is_file():
        thumbnail_path = path
        media_type = 'image/webp'

    # サムネイル画像が存在しない場合はデフォルトのサムネイル画像を返す
    if thumbnail_path is None:
        return CreateDefaultThumbnailResponse()

    # サムネイル画像のファイル情報を取得
    stat_result = await thumbnail_path.stat()

    # FileResponse を生成
    ## 事前に stat_result を渡すことで、返却前に ETag を含む返却予定のレスポンスヘッダーを確認できる
    response = FileResponse(
        path = thumbnail_path,
        media_type = media_type,
        stat_result = stat_result,
        headers = {
            'Cache-Control': 'public, no-transform, immutable, max-age=2592000',  # 30日間キャッシュ
        },
    )

    # If-None-Match と If-Modified-Since の検証
    # FileResponse が実装していない 304 判定を行う
    if IsContentNotModified(response.headers, request.headers):
        # 304 レスポンスでは Content-Length ヘッダーを除外する必要がある
        # （大文字小文字を区別せずにフィルタリング）
        headers_304 = {
            key: value for key, value in response.headers.items()
            if key.lower() != 'content-length'
        }
        return Response(
            status_code = 304,
            headers = headers_304,
        )

    return response


@router.get(
    '',
    summary = '録画番組一覧 API',
    response_description = '録画番組の情報のリスト。',
    response_model = schemas.RecordedPrograms,
)
async def VideosAPI(
    order: Annotated[Literal['desc', 'asc', 'ids'], Query(description='ソート順序 (desc or asc or ids) 。ids を指定すると、ids パラメータで指定された順序を維持する。')] = 'desc',
    page: Annotated[int, Query(description='ページ番号。')] = 1,
    ids: Annotated[list[int] | None, Query(description='録画番組 ID のリスト。指定時は指定された ID の録画番組のみを返す。')] = None,
):
    """
    すべての録画番組を一度に 30 件ずつ取得する。<br>
    order には "desc" か "asc" か "ids" を指定する。"ids" を指定すると、ids パラメータで指定された順序を維持する。<br>
    page (ページ番号) には 1 以上の整数を指定する。<br>
    ids には録画番組 ID のリストを指定できる。指定時は指定された ID の録画番組のみを返す。
    """

    # 生 SQL クエリを構築
    base_query = """
        SELECT
            rp.id AS rp_id,
            rp.recording_start_margin,
            rp.recording_end_margin,
            rp.is_partially_recorded,
            rp.channel_id,
            rp.network_id,
            rp.service_id,
            rp.event_id,
            rp.series_id,
            rp.series_broadcast_period_id,
            rp.title,
            rp.series_title,
            rp.episode_number,
            rp.subtitle,
            rp.description,
            rp.detail,
            rp.start_time,
            rp.end_time,
            rp.duration,
            rp.is_free,
            rp.genres,
            rp.primary_audio_type,
            rp.primary_audio_language,
            rp.secondary_audio_type,
            rp.secondary_audio_language,
            rp.created_at,
            rp.updated_at,
            rv.id AS rv_id,
            rv.status,
            rv.file_path,
            rv.file_hash,
            rv.file_size,
            rv.file_created_at,
            rv.file_modified_at,
            rv.recording_start_time,
            rv.recording_end_time,
            rv.duration AS video_duration,
            rv.container_format,
            rv.video_codec,
            rv.video_codec_profile,
            rv.video_scan_type,
            rv.video_frame_rate,
            rv.video_resolution_width,
            rv.video_resolution_height,
            rv.primary_audio_codec,
            rv.primary_audio_channel,
            rv.primary_audio_sampling_rate,
            rv.secondary_audio_codec,
            rv.secondary_audio_channel,
            rv.secondary_audio_sampling_rate,
            -- key_frames は巨大なデータなので実際のデータは取得せず
            -- 空かどうかの判定結果だけを取得する
            CASE WHEN rv.key_frames != '[]' THEN 1 ELSE 0 END AS has_key_frames,
            rv.cm_sections,
            rv.thumbnail_info,
            rv.created_at AS rv_created_at,
            rv.updated_at AS rv_updated_at,
            ch.id AS ch_id,
            ch.display_channel_id,
            ch.network_id AS ch_network_id,
            ch.service_id AS ch_service_id,
            ch.transport_stream_id,
            ch.remocon_id,
            ch.channel_number,
            ch.type,
            ch.name AS ch_name,
            ch.jikkyo_force,
            ch.is_subchannel,
            ch.is_radiochannel,
            ch.is_watchable
        FROM recorded_programs rp
        JOIN recorded_videos rv ON rp.id = rv.recorded_program_id
        LEFT JOIN channels ch ON rp.channel_id = ch.id
        WHERE 1=1
        {where_clause}
        ORDER BY rp.start_time {order}, rp.id {order}
        LIMIT ? OFFSET ?
    """

    # ids が指定されている場合は、指定された ID の録画番組のみを返す
    target_ids: list[int] | None = None
    if ids is not None:
        # order が 'ids' の場合は、指定された順序を維持する
        if order == 'ids':
            # ページングを考慮して必要な範囲の ID のみを使用
            target_ids = ids[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
            if not target_ids:
                return schemas.RecordedPrograms(
                    total = await RecordedProgram.all().filter(id__in=ids).count(),
                    recorded_programs = [],
                )

            # IN 句のプレースホルダーを生成
            placeholders = ','.join(['?' for _ in target_ids])
            query = base_query.format(
                where_clause = f'AND rp.id IN ({placeholders})',
                order = 'DESC'  # order は無視されるが、SQL の構文上必要
            )
            params = [*target_ids, str(PAGE_SIZE), '0']  # OFFSET は 0 固定

            # 総数を取得
            total_query = 'SELECT COUNT(*) as count FROM recorded_programs WHERE id IN ({})'.format(
                ','.join(['?' for _ in ids])
            )
            total_params = ids

        else:
            # 通常のソート順で取得
            query = base_query.format(
                where_clause = f'AND rp.id IN ({",".join(["?" for _ in ids])})',
                order = 'DESC' if order == 'desc' else 'ASC'
            )
            params = [*ids, str(PAGE_SIZE), str((page - 1) * PAGE_SIZE)]

            # 総数を取得
            total_query = 'SELECT COUNT(*) as count FROM recorded_programs WHERE id IN ({})'.format(
                ','.join(['?' for _ in ids])
            )
            total_params = ids

    else:
        # すべての録画番組を返す
        query = base_query.format(
            where_clause = '',
            order = 'DESC' if order == 'desc' else 'ASC'
        )
        params = [str(PAGE_SIZE), str((page - 1) * PAGE_SIZE)]

        # 総数を取得
        total_query = 'SELECT COUNT(*) as count FROM recorded_programs'
        total_params = []

    try:
        # データベースから直接クエリを実行
        conn = connections.get('default')
        rows = await conn.execute_query(query, params)
        total_result = await conn.execute_query(total_query, total_params)
        total = total_result[1][0]['count']

        # 結果を Pydantic モデルに変換
        recorded_programs: list[schemas.RecordedProgram] = []
        for row in rows[1]:  # rows[0] はカラム情報、rows[1] が実際のデータ
            recorded_programs.append(await ConvertRowToRecordedProgram(row))

        # order が 'ids' の場合は、指定された順序を維持する
        if ids is not None and order == 'ids':
            # 指定された順序でソート
            assert target_ids is not None
            id_to_index = {id: index for index, id in enumerate(target_ids)}
            recorded_programs = sorted(recorded_programs, key=lambda x: id_to_index[x.id])

        return schemas.RecordedPrograms(
            total = total,
            recorded_programs = recorded_programs,
        )

    except Exception as ex:
        logging.error('[VideosAPI] Failed to execute raw SQL query:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to execute raw SQL query',
        )


@router.get(
    '/search',
    summary = '録画番組検索 API',
    response_description = '検索条件に一致する録画番組の情報のリスト。',
    response_model = schemas.RecordedPrograms,
)
async def VideosSearchAPI(
    query: Annotated[str, Query(description='検索キーワード。title または series_title または subtitle のいずれかに部分一致する録画番組を検索する。')] = '',
    order: Annotated[Literal['desc', 'asc'], Query(description='ソート順序 (desc or asc) 。')] = 'desc',
    page: Annotated[int, Query(description='ページ番号。')] = 1,
):
    """
    指定されたキーワードで録画番組を一度に 30 件ずつ検索する。<br>
    キーワードは title または series_title または subtitle のいずれかに部分一致する録画番組を検索する。<br>
    order には "desc" か "asc" を指定する。<br>
    page (ページ番号) には 1 以上の整数を指定する。<br>
    半角または全角スペースで区切ることで、複数のキーワードによる AND 検索が可能。
    """

    def BuildSearchConditions(query: str) -> tuple[str, list[str], list[str]]:
        """
        検索キーワードから SQL の WHERE 句とパラメータを生成する
        半角または全角スペースで区切られた複数のキーワードを AND 検索する

        Returns:
            tuple[str, list[str], list[str]]: (WHERE 句, パラメータ, 検索キーワードのリスト)
        """

        # 半角・全角スペースで分割
        keywords = [keyword.strip() for keyword in query.replace('　', ' ').split(' ') if keyword.strip()]
        if not keywords:
            return '', [], []

        # 各キーワードに対する検索条件を生成
        conditions: list[str] = []
        params: list[str] = []
        for keyword in keywords:
            # LIKE 検索用のパラメータを生成（前後に % を付与）
            param = f'%{keyword.lower()}%'
            conditions.append('''
                (
                    LOWER(ch.name) LIKE ? OR
                    LOWER(rp.title) LIKE ? OR
                    LOWER(rp.series_title) LIKE ? OR
                    LOWER(rp.subtitle) LIKE ?
                )
            '''.strip())
            params.extend([param] * 4)  # 4つの検索対象カラムに同じパラメータを使用

        # AND 検索のために conditions を結合
        where_clause = ' AND '.join(conditions)
        return where_clause, params, keywords

    # クエリが空の場合は全件取得と同じ挙動にする
    if not query:
        return await VideosAPI(order=order, page=page)

    # 検索条件を構築
    where_clause, params, keywords = BuildSearchConditions(query)
    if not keywords:  # キーワードが空の場合は全件取得と同じ挙動にする
        return await VideosAPI(order=order, page=page)

    # 生 SQL クエリを構築
    base_query = """
        SELECT
            rp.id AS rp_id,
            rp.recording_start_margin,
            rp.recording_end_margin,
            rp.is_partially_recorded,
            rp.channel_id,
            rp.network_id,
            rp.service_id,
            rp.event_id,
            rp.series_id,
            rp.series_broadcast_period_id,
            rp.title,
            rp.series_title,
            rp.episode_number,
            rp.subtitle,
            rp.description,
            rp.detail,
            rp.start_time,
            rp.end_time,
            rp.duration,
            rp.is_free,
            rp.genres,
            rp.primary_audio_type,
            rp.primary_audio_language,
            rp.secondary_audio_type,
            rp.secondary_audio_language,
            rp.created_at,
            rp.updated_at,
            rv.id AS rv_id,
            rv.status,
            rv.file_path,
            rv.file_hash,
            rv.file_size,
            rv.file_created_at,
            rv.file_modified_at,
            rv.recording_start_time,
            rv.recording_end_time,
            rv.duration AS video_duration,
            rv.container_format,
            rv.video_codec,
            rv.video_codec_profile,
            rv.video_scan_type,
            rv.video_frame_rate,
            rv.video_resolution_width,
            rv.video_resolution_height,
            rv.primary_audio_codec,
            rv.primary_audio_channel,
            rv.primary_audio_sampling_rate,
            rv.secondary_audio_codec,
            rv.secondary_audio_channel,
            rv.secondary_audio_sampling_rate,
            -- key_frames は巨大なデータなので実際のデータは取得せず
            -- 空かどうかの判定結果だけを取得する
            CASE WHEN rv.key_frames != '[]' THEN 1 ELSE 0 END AS has_key_frames,
            rv.cm_sections,
            rv.thumbnail_info,
            rv.created_at AS rv_created_at,
            rv.updated_at AS rv_updated_at,
            ch.id AS ch_id,
            ch.display_channel_id,
            ch.network_id AS ch_network_id,
            ch.service_id AS ch_service_id,
            ch.transport_stream_id,
            ch.remocon_id,
            ch.channel_number,
            ch.type,
            ch.name AS ch_name,
            ch.jikkyo_force,
            ch.is_subchannel,
            ch.is_radiochannel,
            ch.is_watchable
        FROM recorded_programs rp
        JOIN recorded_videos rv ON rp.id = rv.recorded_program_id
        LEFT JOIN channels ch ON rp.channel_id = ch.id
        WHERE {where_clause}
        ORDER BY rp.start_time {order}, rp.id {order}
        LIMIT ? OFFSET ?
    """

    # クエリとパラメータを構築
    query = base_query.format(
        where_clause = where_clause,
        order = 'DESC' if order == 'desc' else 'ASC'
    )
    params.extend([str(PAGE_SIZE), str((page - 1) * PAGE_SIZE)])

    # 総数を取得するクエリを構築
    total_query = f"""
        SELECT COUNT(*) as count
        FROM recorded_programs rp
        LEFT JOIN channels ch ON rp.channel_id = ch.id
        WHERE {where_clause}
    """
    total_params = params[:-2]  # LIMIT と OFFSET を除外

    try:
        # データベースから直接クエリを実行
        conn = connections.get('default')
        rows = await conn.execute_query(query, params)
        total_result = await conn.execute_query(total_query, total_params)
        total = total_result[1][0]['count']

        # 結果を Pydantic モデルに変換
        recorded_programs: list[schemas.RecordedProgram] = []
        for row in rows[1]:  # rows[0] はカラム情報、rows[1] が実際のデータ
            recorded_programs.append(await ConvertRowToRecordedProgram(row))

        return schemas.RecordedPrograms(
            total = total,
            recorded_programs = recorded_programs,
        )

    except Exception as ex:
        logging.error('[VideosSearchAPI] Failed to execute raw SQL query:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to execute raw SQL query',
        )


@router.get(
    '/{video_id}',
    summary = '録画番組 API',
    response_description = '録画番組の情報。',
    response_model = schemas.RecordedProgram,
)
async def VideoAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組を取得する。
    """

    return recorded_program


@router.get(
    '/{video_id}/download',
    summary = '録画番組ダウンロード API',
    response_description = '録画番組の MPEG-TS ファイル。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'video/mp2t': {}}},
        422: {'description': 'Specified video_id was not found'},
    },
)
async def VideoDownloadAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組の MPEG-TS ファイルをダウンロードする。
    """

    # ファイルパスとファイル名を取得
    file_path = recorded_program.recorded_video.file_path
    filename = pathlib.Path(file_path).name

    # MPEG-TS ファイルをダウンロードさせる
    return FileResponse(
        path = file_path,
        filename = filename,
        media_type = 'video/mp2t',
    )


@router.get(
    '/{video_id}/jikkyo',
    summary = '録画番組過去ログコメント API',
    response_description = '録画番組の放送中に投稿されたニコニコ実況の過去ログコメント。',
    response_model = schemas.JikkyoComments,
)
async def VideoJikkyoCommentsAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組の放送中に投稿されたニコニコ実況の過去ログコメントを取得する。<br>
    ニコニコ実況 過去ログ API をラップし、DPlayer が受け付けるコメント形式に変換して返す。
    """

    # チャンネル情報と録画開始時刻/録画終了時刻の情報がある場合のみ
    if ((recorded_program.channel is not None) and
        (recorded_program.recorded_video.recording_start_time is not None) and
        (recorded_program.recorded_video.recording_end_time is not None)):

        # ニコニコ実況 過去ログ API から一致する過去ログコメントを取得して返す
        jikkyo_client = JikkyoClient(recorded_program.channel.network_id, recorded_program.channel.service_id)
        jikkyo_comments = await jikkyo_client.fetchJikkyoComments(
            recorded_program.recorded_video.recording_start_time,
            recorded_program.recorded_video.recording_end_time,
        )

        if recorded_program.recorded_video.container_format != 'MPEG-TS' and jikkyo_comments.comments:
            # PSI/SI の書庫があればそこから動画のカット編集情報を抽出して過去ログコメントのタイミングを調節する
            # TODO: コメントリストの時刻などは調節前のほうが望ましいので schemas.JikkyoComment に項目を追加すべき
            tot_time_list: list[tuple[float, float, datetime, datetime]] = []
            try:
                psc_path = pathlib.Path(recorded_program.recorded_video.file_path).with_suffix('.psc')
                with open(psc_path, 'rb') as f:
                    def callback(time_sec: float, pid: int, section: bytes):
                        tot = TimeOffsetSection(section)
                        back = tot_time_list and tot_time_list[-1]
                        if (back and (time_sec < back[1] or tot.JST_time < back[3])) or (not back and time_sec > 60):
                            # 時刻の巻き戻り、または間隔が空きすぎている
                            return False
                        if not back or abs((time_sec - back[0]) - (tot.JST_time - back[2]).total_seconds()) > 5:
                            # PCR と TOT の増分量に差があるので分割する
                            tot_time_list.append((time_sec, time_sec, tot.JST_time, tot.JST_time))
                        else:
                            tot_time_list[-1] = (back[0], time_sec, back[2], tot.JST_time)
                        return True
                    # TOT を取り出す
                    if not TSInfoAnalyzer.readPSIData(f, [0x14], callback):
                        logging.warning(f'{psc_path}: File contents may be invalid.')
                        tot_time_list.clear()
            except Exception:
                tot_time_list.clear()

            if len(tot_time_list) >= 2:
                # TOT 時刻を開始時刻からの相対秒数に変換する
                offset_list: list[tuple[float, float]] = []
                first_sec = tot_time_list[0][0]
                first_tot_time = tot_time_list[0][2]
                for tot_time in tot_time_list:
                    offset_list.append(((tot_time[2] - first_tot_time).total_seconds() + first_sec, \
                                        (tot_time[3] - first_tot_time).total_seconds() + first_sec))

                # 分割部分の時刻をずらして結合する
                cut_list: list[tuple[float, float, float]] = []
                shift_sec = tot_time_list[0][0]
                for i in range(len(tot_time_list) - 1):
                    next_shift_sec = (tot_time_list[i + 1][0] - tot_time_list[i][1]) / 2
                    cut_list.append((tot_time_list[i][0] - shift_sec, offset_list[i][0] - shift_sec, offset_list[i][1] + next_shift_sec))
                    shift_sec = next_shift_sec
                cut_list.append((tot_time_list[-1][0] - shift_sec, offset_list[-1][0] - shift_sec, offset_list[-1][1] + 60))

                comment_index = 0
                comments = jikkyo_comments.comments
                for cut in cut_list:
                    while comment_index < len(comments) and comments[comment_index].time < cut[1]:
                        # 範囲外なので消す
                        comments.pop(comment_index)
                    while comment_index < len(comments) and comments[comment_index].time < cut[2]:
                        # タイミングをずらす
                        comments[comment_index].time -= cut[1] - cut[0]
                        comment_index += 1

        return jikkyo_comments

    # それ以外の場合はエラーを返す
    return schemas.JikkyoComments(
        is_success = False,
        comments = [],
        detail = 'チャンネル情報または録画開始時刻/録画終了時刻の情報がない録画番組です。',
    )


@router.post(
    '/{video_id}/reanalyze',
    summary = '録画番組メタデータ再解析 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def VideoReanalyzeAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組のメタデータ（動画情報・番組情報・サムネイル画像・キーフレーム情報・CM 区間情報など）をすべて再解析・再生成する。
    """

    try:
        file_path = anyio.Path(recorded_program.recorded_video.file_path)
        # メタデータ再解析を実行
        ## wait_background_analysis = True 指定時は DriveIOLimiter を掛けるとデッドロックが発生するので、敢えて掛けない
        ## どのみち内部で実行される RecordedScanTask で DriveIOLimiter を掛けているため、ここで掛ける必要はない
        await RecordedScanTask().processRecordedFile(
            file_path = file_path,
            # 既に DB に登録されている録画ファイルのメタデータを強制的に再解析する
            force_update = True,
            # API レスポンスの返却をもってメタデータ再解析が完全に完了したことをユーザーに伝えるため、バックグラウンド解析タスクが完了するまで待つ
            wait_background_analysis = True,
        )

    except Exception as ex:
        logging.error(f'[VideoReanalyzeAPI] Failed to reanalyze the video_id {recorded_program.id}:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f'Failed to reanalyze the video: {ex!s}',
        )


@router.get(
    '/{video_id}/thumbnail',
    summary = '録画番組サムネイル画像取得 API',
    response_description = '録画番組のサムネイル画像 (WebP) 。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'image/webp': {}}},
        304: {'description': 'Not Modified'},
        422: {'description': 'Specified video_id was not found'},
    },
)
async def VideoThumbnailAPI(
    request: Request,
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組のサムネイル画像を取得する。<br>
    サムネイル画像が生成されていない場合はデフォルトのサムネイル画像を返す。
    """

    return await GetThumbnailResponse(request, recorded_program)


@router.get(
    '/{video_id}/thumbnail/tiled',
    summary = '録画番組シークバー用サムネイルタイル画像取得 API',
    response_description = '録画番組のシークバー用サムネイルタイル画像 (WebP) 。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'image/webp': {}}},
        304: {'description': 'Not Modified'},
        422: {'description': 'Specified video_id was not found'},
    },
)
async def VideoThumbnailTileAPI(
    request: Request,
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組のシークバー用サムネイルタイル画像を取得する。<br>
    サムネイル画像が生成されていない場合はデフォルトのサムネイル画像を返す。
    """

    return await GetThumbnailResponse(request, recorded_program, return_tiled=True)


@router.post(
    '/{video_id}/thumbnail/regenerate',
    summary = '録画番組サムネイル画像再生成 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def VideoThumbnailRegenerateAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組のサムネイル画像を再生成する。<br>
    サムネイル画像の再生成には数分程度かかる場合がある。
    """

    try:
        # RecordedProgram モデルを schemas.RecordedProgram に変換
        recorded_program_schema = schemas.RecordedProgram.model_validate(recorded_program, from_attributes=True)

        # DriveIOLimiter で同一 HDD に対してのバックグラウンドタスクの同時実行数を原則1セッションに制限
        file_path = anyio.Path(recorded_program.recorded_video.file_path)
        async with DriveIOLimiter.getSemaphore(file_path):
            # サムネイル画像の再生成を実行
            generator = ThumbnailGenerator.fromRecordedProgram(recorded_program_schema)
            await generator.generateAndSave()

    except Exception as ex:
        logging.error(f'[VideoThumbnailRegenerateAPI] Failed to regenerate thumbnails for video_id {recorded_program.id}:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f'Failed to regenerate thumbnails: {ex!s}',
        )


@router.delete(
    '/{video_id}',
    summary = '録画ファイル削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def VideoDeleteAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
    current_user: Annotated[User, Depends(GetCurrentAdminUser)],
):
    """
    指定された録画番組のファイルとメタデータを削除する。不可逆な処理であるため、慎重に実行すること。
    - データベースから録画番組情報・録画ファイル情報を削除
    - 録画ファイルに紐づくサムネイルファイルを削除
    - 録画ファイルに関連する補助ファイル (.ts.program.txt, .ts.err) を削除
    - 録画ファイル本体を削除

    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されていて、かつ管理者アカウントでないとアクセスできない。
    """

    # 録画ファイルの情報を取得
    file_path = anyio.Path(recorded_program.recorded_video.file_path)
    file_hash = recorded_program.recorded_video.file_hash
    file_name = file_path.name
    file_dir = file_path.parent

    # 万が一処理が失敗してもダメージが比較的少ない順に実行する
    try:
        # 1. データベースから録画番組情報・録画ファイル情報を削除
        # RecordedVideo も CASCADE 制約で削除される
        try:
            # 同じ file_hash を持つ他のレコードが存在するかチェック
            duplicate_records = await RecordedProgram.filter(
                recorded_video__file_hash=file_hash,
            ).exclude(id=recorded_program.id).count()
            has_duplicates = duplicate_records > 0

            # データベースから録画番組情報を削除
            await recorded_program.delete()
        except Exception as ex:
            logging.error('[VideoDeleteAPI] Failed to delete recorded program from database:', exc_info=ex)
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to delete recorded program from database: {ex!s}',
            )

        # 2. サムネイルファイルの削除
        # 同じ file_hash を持つ他のレコードが存在する場合はスキップ
        thumbnails_dir = anyio.Path(str(THUMBNAILS_DIR))
        if await thumbnails_dir.is_dir() and not has_duplicates:
            # 通常サムネイル (.webp、旧仕様の .jpg)
            for ext in ['.webp', '.jpg']:
                thumbnail_path = thumbnails_dir / f'{file_hash}{ext}'
                if await thumbnail_path.is_file():
                    try:
                        await thumbnail_path.unlink()
                    except Exception as ex:
                        logging.error(f'[VideoDeleteAPI] Failed to delete thumbnail file: {thumbnail_path}', exc_info=ex)
                        raise HTTPException(
                            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail = f'Failed to delete thumbnail file: {ex!s}',
                        )
                elif ext == '.webp':  # JPEG はよほど長尺でない限り発生しないので WebP のみチェック
                    logging.warning(f'[VideoDeleteAPI] Thumbnail file does not exist: {thumbnail_path}')

            # タイルサムネイル (.webp、旧仕様の .jpg)
            for ext in ['.webp', '.jpg']:
                tile_thumbnail_path = thumbnails_dir / f'{file_hash}_tile{ext}'
                if await tile_thumbnail_path.is_file():
                    try:
                        await tile_thumbnail_path.unlink()
                    except Exception as ex:
                        logging.error(f'[VideoDeleteAPI] Failed to delete tile thumbnail file: {tile_thumbnail_path}', exc_info=ex)
                        raise HTTPException(
                            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail = f'Failed to delete tile thumbnail file: {ex!s}',
                        )
                elif ext == '.webp':  # JPEG はよほど長尺でない限り発生しないので WebP のみチェック
                    logging.warning(f'[VideoDeleteAPI] Tile thumbnail file does not exist: {tile_thumbnail_path}')
        elif has_duplicates:
            logging.info(f'[VideoDeleteAPI] Skip deleting thumbnail files because other records with the same file_hash exist: {file_hash}')

        # 3. 関連する補助ファイルの削除 (.ts.program.txt, .ts.err)
        ## .ts.program.txt ファイル (録画ファイルが hoge.ts の場合は hoge.ts.program.txt)
        ts_program_txt_path = anyio.Path(f'{file_dir}/{file_name}.program.txt')
        if await ts_program_txt_path.is_file():
            try:
                await ts_program_txt_path.unlink()
            except Exception as ex:
                logging.error(f'[VideoDeleteAPI] Failed to delete .ts.program.txt file: {ts_program_txt_path}', exc_info=ex)
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail = f'Failed to delete .ts.program.txt file: {ex!s}',
                )
        ## .ts.err ファイル (録画ファイルが hoge.ts の場合は hoge.ts.err)
        ts_err_path = anyio.Path(f'{file_dir}/{file_name}.err')
        if await ts_err_path.is_file():
            try:
                await ts_err_path.unlink()
            except Exception as ex:
                logging.error(f'[VideoDeleteAPI] Failed to delete .ts.err file: {ts_err_path}', exc_info=ex)
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail = f'Failed to delete .ts.err file: {ex!s}',
                )

        # 4. 録画ファイル本体の削除
        if await file_path.is_file():
            try:
                await file_path.unlink()
                logging.info(f'[VideoDeleteAPI] Successfully deleted recorded video file: {file_path}')
            except Exception as ex:
                # 録画ファイル本体の削除に失敗した場合はクリティカルなエラー
                logging.error(f'[VideoDeleteAPI] Failed to delete recorded video file: {file_path}', exc_info=ex)
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail = f'Failed to delete recorded video file: {ex!s}',
                )
        else:
            logging.warning(f'[VideoDeleteAPI] Recorded video file does not exist: {file_path}')

    except Exception as ex:
        logging.error('[VideoDeleteAPI] Failed to delete recorded program:', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f'Failed to delete recorded program: {ex!s}',
        )
