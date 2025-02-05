
import anyio
from email.utils import parsedate
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.responses import FileResponse
from starlette.datastructures import Headers
from tortoise.expressions import Q
from typing import Annotated, Literal, Union

from app import logging
from app import schemas
from app.constants import STATIC_DIR, THUMBNAILS_DIR
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.models.RecordedProgram import RecordedProgram
from app.utils.Jikkyo import Jikkyo


# ルーター
router = APIRouter(
    tags = ['Videos'],
    prefix = '/api/videos',
)

# ページングで一度に取得する録画番組の数
PAGE_SIZE = 30


async def GetRecordedProgram(video_id: Annotated[int, Path(description='録画番組の ID 。')]) -> RecordedProgram:
    """ 録画番組 ID から録画番組情報を取得する """

    # 録画番組情報を取得
    recorded_program = await RecordedProgram.all() \
        .select_related('recorded_video') \
        .select_related('channel') \
        .get_or_none(id=video_id)
    if recorded_program is None:
        logging.error(f'[VideosRouter][GetRecordedProgram] Specified video_id was not found [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    return recorded_program


def IsContentNotModified(response_headers: Headers, request_headers: Headers) -> bool:
    """
    リクエストヘッダーとレスポンスヘッダーから、304 を返すべきかどうかを判定する

    Args:
        response_headers (Headers): レスポンスヘッダー
        request_headers (Headers): リクエストヘッダー

    Returns:
        bool: 304 を返すべき場合は True
    """

    # If-None-Match による判定
    try:
        if_none_match = request_headers['if-none-match']
        etag = response_headers['etag']
        if etag in [tag.strip(' W/') for tag in if_none_match.split(',')]:
            return True
    except KeyError:
        pass

    # If-Modified-Since による判定
    try:
        if_modified_since = parsedate(request_headers['if-modified-since'])
        last_modified = parsedate(response_headers['last-modified'])
        if if_modified_since is not None and last_modified is not None and if_modified_since >= last_modified:
            return True
    except KeyError:
        pass

    return False


async def GetThumbnailResponse(
    request: Request,
    recorded_program: RecordedProgram,
    is_tile: bool = False,
) -> Union[FileResponse, Response]:
    """
    サムネイル画像のレスポンスを生成する共通処理
    ETags と Last-Modified を使ったキャッシュ制御を行う
    WebP の最大サイズ制限を超えた場合は JPEG にフォールバックする

    Args:
        request (Request): FastAPI のリクエストオブジェクト
        recorded_program (RecordedProgram): 録画番組情報
        is_tile (bool, optional): シークバー用タイル画像かどうか. Defaults to False.

    Returns:
        Union[FileResponse, Response]: サムネイル画像のレスポンス
    """

    # サムネイル画像のパスを生成
    suffix = '_tile' if is_tile else ''
    base_path = anyio.Path(str(THUMBNAILS_DIR)) / f'{recorded_program.recorded_video.file_hash}{suffix}'

    # WebP と JPEG の両方を試す
    thumbnail_path = None
    media_type = None
    for ext, mime in [('.webp', 'image/webp'), ('.jpg', 'image/jpeg')]:
        path = base_path.with_suffix(ext)
        if await path.exists():
            thumbnail_path = path
            media_type = mime
            break

    # サムネイル画像が存在しない場合はデフォルト画像を返す
    if thumbnail_path is None:
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
    if IsContentNotModified(Headers(dict(response.headers)), Headers(scope=request.scope)):
        return Response(
            status_code = 304,
            headers = dict(response.headers),
        )

    return response


@router.get(
    '',
    summary = '録画番組一覧 API',
    response_description = '録画番組の情報のリスト。',
    response_model = schemas.RecordedPrograms,
)
async def VideosAPI(
    order: Annotated[Literal['desc', 'asc'], Query(description='ソート順序 (desc or asc) 。')] = 'desc',
    page: Annotated[int, Query(description='ページ番号。')] = 1,
):
    """
    すべての録画番組を一度に 100 件ずつ取得する。<br>
    order には "desc" か "asc" を指定する。<br>
    page (ページ番号) には 1 以上の整数を指定する。
    """

    recorded_programs = await RecordedProgram.all() \
        .select_related('recorded_video') \
        .select_related('channel') \
        .order_by('-start_time' if order == 'desc' else 'start_time') \
        .offset((page - 1) * PAGE_SIZE) \
        .limit(PAGE_SIZE) \

    return {
        'total': await RecordedProgram.all().count(),
        'recorded_programs': recorded_programs,
    }


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
    指定されたキーワードで録画番組を一度に 100 件ずつ検索する。<br>
    キーワードは title または series_title または subtitle のいずれかに部分一致する録画番組を検索する。<br>
    order には "desc" か "asc" を指定する。<br>
    page (ページ番号) には 1 以上の整数を指定する。
    """

    # クエリが空の場合は全件取得と同じ挙動にする
    if not query:
        return await VideosAPI(order=order, page=page)

    # 検索条件を構築
    # title または series_title または subtitle のいずれかに部分一致するレコードを検索
    recorded_programs = await RecordedProgram.all() \
        .select_related('recorded_video') \
        .select_related('channel') \
        .filter(
            Q(title__icontains=query) |
            Q(series_title__icontains=query) |
            Q(subtitle__icontains=query)
        ) \
        .order_by('-start_time' if order == 'desc' else 'start_time') \
        .offset((page - 1) * PAGE_SIZE) \
        .limit(PAGE_SIZE)

    # 検索条件に一致する総件数を取得
    total = await RecordedProgram.all() \
        .filter(
            Q(title__icontains=query) |
            Q(series_title__icontains=query) |
            Q(subtitle__icontains=query)
        ) \
        .count()

    return {
        'total': total,
        'recorded_programs': recorded_programs,
    }


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
        jikkyo = Jikkyo(recorded_program.channel.network_id, recorded_program.channel.service_id)
        return await jikkyo.fetchJikkyoComments(
            recorded_program.recorded_video.recording_start_time,
            recorded_program.recorded_video.recording_end_time,
        )

    # それ以外の場合はエラーを返す
    return schemas.JikkyoComments(
        is_success = False,
        comments = [],
        detail = 'チャンネル情報または録画開始時刻/録画終了時刻の情報がない録画番組です。',
    )


@router.get(
    '/{video_id}/thumbnail',
    summary = '録画番組サムネイル API',
    response_description = '録画番組のサムネイル画像 (WebP または JPEG) 。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'image/webp': {}, 'image/jpeg': {}}},
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
    サムネイルが生成されていない場合はデフォルト画像を返す。
    """

    return await GetThumbnailResponse(request, recorded_program)


@router.get(
    '/{video_id}/thumbnail/tiled',
    summary = '録画番組シークバー向けサムネイルタイル API',
    response_description = '録画番組のシークバー向けサムネイルタイル画像 (WebP または JPEG) 。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'image/webp': {}, 'image/jpeg': {}}},
        304: {'description': 'Not Modified'},
        422: {'description': 'Specified video_id was not found'},
    },
)
async def VideoThumbnailTileAPI(
    request: Request,
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
):
    """
    指定された録画番組のシークバーサムネイル画像を取得する。<br>
    サムネイルが生成されていない場合はデフォルト画像を返す。
    """

    return await GetThumbnailResponse(request, recorded_program, is_tile=True)


@router.post(
    '/{video_id}/thumbnail/regenerate',
    summary = 'サムネイル再生成 API',
    response_description = 'サムネイル再生成のステータス。',
    response_model = schemas.ThumbnailRegenerationStatus,
)
async def VideoThumbnailRegenerateAPI(
    recorded_program: Annotated[RecordedProgram, Depends(GetRecordedProgram)],
    skip_tile_if_exists: Annotated[bool, Query(description='既に存在する場合はサムネイルタイルの生成をスキップするかどうか（通常のサムネイルは再度生成する）。')] = False,
):
    """
    指定された録画番組のサムネイルを再生成する。<br>
    サムネイル生成には数分程度かかる場合がある。
    """

    try:
        # RecordedProgram モデルを schemas.RecordedProgram に変換
        recorded_program_schema = schemas.RecordedProgram.model_validate(recorded_program, from_attributes=True)

        # ThumbnailGenerator を初期化
        generator = ThumbnailGenerator.fromRecordedProgram(recorded_program_schema)

        # サムネイル生成を実行
        await generator.generate(skip_tile_if_exists=skip_tile_if_exists)

        return {
            'is_success': True,
            'detail': 'Successfully regenerated thumbnails.',
        }

    except Exception as ex:
        logging.error(f'Failed to regenerate thumbnails for video_id {recorded_program.id}:', exc_info=ex)
        return {
            'is_success': False,
            'detail': f'Failed to regenerate thumbnails: {ex!s}',
        }
