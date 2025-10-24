
import hashlib
import json
import pathlib
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
from app.metadata.MetadataAnalyzer import MetadataAnalyzer
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.models.ClipVideo import ClipVideo
from app.models.User import User
from app.routers.UsersRouter import GetCurrentAdminUser
from app.utils.DriveIOLimiter import DriveIOLimiter


# ルーター
router = APIRouter(
    tags = ['ClipVideos'],
    prefix = '/api/clip-videos',
)

# ページングで一度に取得するクリップ動画の数
PAGE_SIZE = 30


async def ConvertRowToClipVideo(row: dict[str, Any]) -> schemas.ClipVideo:
    """ データベースの行データを ClipVideo Pydantic モデルに変換する共通処理 """

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
        }

    # series のデータを構築
    series_dict: dict[str, Any] | None = None
    if row['series_id'] is not None:
        series_dict = {
            'id': row['series_id'],
            'title': row['series_title'],
            'description': row['series_description'],
        }

    # recorded_program のデータを構築
    recorded_program_dict = {
        'id': row['rp_id'],
        'recorded_video': None,  # ClipVideo では不要だが必須フィールド
        'channel_id': row['channel_id'],
        'network_id': row['rp_network_id'],
        'service_id': row['rp_service_id'],
        'event_id': row['event_id'],
        'series_id': row['series_id'],
        'series_broadcast_period_id': row['series_broadcast_period_id'],
        'title': row['rp_title'],
        'description': row['description'],
        'detail': json.loads(row['detail']) if isinstance(row['detail'], str) else row['detail'],
        'start_time': row['start_time'],
        'end_time': row['end_time'],
        'duration': row['rp_duration'],
        'is_free': bool(row['is_free']),
        'genres': json.loads(row['genres']),
        'primary_audio_type': row['primary_audio_type'],
        'primary_audio_language': row['primary_audio_language'],
        'secondary_audio_type': row['secondary_audio_type'],
        'secondary_audio_language': row['secondary_audio_language'],
        'created_at': row['rp_created_at'] if 'rp_created_at' in row.keys() else '2000-01-01T00:00:00+09:00',
        'updated_at': row['rp_updated_at'] if 'rp_updated_at' in row.keys() else '2000-01-01T00:00:00+09:00',
        'channel': channel_dict,
        'series': series_dict,
    }

    # セグメントデータを抽出
    segments_raw = row['segments'] if 'segments' in row.keys() else None
    if isinstance(segments_raw, str) and segments_raw != '':
        try:
            segments_value = json.loads(segments_raw)
        except json.JSONDecodeError:
            segments_value = []
    elif isinstance(segments_raw, list):
        segments_value = segments_raw
    else:
        segments_value = []

    # clip_video のデータを構築
    clip_video_dict = {
        'id': row['cv_id'],
        'recorded_video_id': row['recorded_video_id'],
        'recorded_program': recorded_program_dict,
        'title': row['cv_title'],
        'file_path': row['file_path'],
        'file_hash': row['file_hash'],
        'file_size': row['file_size'],
        'start_time': row['start_time_in_video'],
        'end_time': row['end_time_in_video'],
        'duration': row['cv_duration'],
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
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'segments': segments_value,
    }

    return schemas.ClipVideo(**clip_video_dict)


@router.get(
    '',
    summary = 'クリップ動画一覧 API',
    response_description = 'クリップ動画のリスト。',
    response_model = schemas.ClipVideos,
)
async def ClipVideosAPI(
    sort: Annotated[Literal['desc', 'asc'], Query(description='並び順。desc: 新しい順、asc: 古い順。')] = 'desc',
    page: Annotated[int, Query(description='ページ番号。', ge=1)] = 1,
) -> schemas.ClipVideos:
    """
    クリップ動画のリストを取得する。
    """

    # データベース接続を取得
    conn = connections.get('default')

    # 並び順の設定
    order_clause = 'cv.created_at DESC' if sort == 'desc' else 'cv.created_at ASC'

    # ページング計算
    offset = (page - 1) * PAGE_SIZE

    # 全体のカウントを取得
    count_result = await conn.execute_query(
        'SELECT COUNT(*) as total FROM clip_videos cv WHERE EXISTS (SELECT 1 FROM recorded_videos rv WHERE rv.id = cv.recorded_video_id)'
    )
    total = count_result[1][0]['total']

    # クリップ動画とそれに紐づく録画番組情報を取得
    sql = f'''
        SELECT
            cv.id as cv_id,
            cv.recorded_video_id,
            cv.title as cv_title,
            cv.file_path,
            cv.file_hash,
            cv.file_size,
            cv.start_time as start_time_in_video,
            cv.end_time as end_time_in_video,
            cv.duration as cv_duration,
            cv.segments as segments,
            cv.container_format,
            cv.video_codec,
            cv.video_codec_profile,
            cv.video_scan_type,
            cv.video_frame_rate,
            cv.video_resolution_width,
            cv.video_resolution_height,
            cv.primary_audio_codec,
            cv.primary_audio_channel,
            cv.primary_audio_sampling_rate,
            cv.secondary_audio_codec,
            cv.secondary_audio_channel,
            cv.secondary_audio_sampling_rate,
            cv.created_at,
            cv.updated_at,
            rp.id as rp_id,
            rp.channel_id,
            rp.network_id as rp_network_id,
            rp.service_id as rp_service_id,
            rp.event_id,
            rp.series_id,
            rp.series_broadcast_period_id,
            rp.title as rp_title,
            rp.description,
            rp.detail,
            rp.start_time,
            rp.end_time,
            rp.duration as rp_duration,
            rp.is_free,
            rp.genres,
            rp.primary_audio_type,
            rp.primary_audio_language,
            rp.secondary_audio_type,
            rp.secondary_audio_language,
            ch.id as ch_id,
            ch.display_channel_id,
            ch.network_id as ch_network_id,
            ch.service_id as ch_service_id,
            ch.transport_stream_id,
            ch.remocon_id,
            ch.channel_number,
            ch.type,
            ch.name as ch_name,
            ch.jikkyo_force,
            ch.is_subchannel,
            s.id as series_id,
            s.title as series_title,
            s.description as series_description
        FROM clip_videos cv
        INNER JOIN recorded_videos rv ON cv.recorded_video_id = rv.id
        INNER JOIN recorded_programs rp ON rv.recorded_program_id = rp.id
        LEFT JOIN channels ch ON rp.channel_id = ch.id
        LEFT JOIN series s ON rp.series_id = s.id
        ORDER BY {order_clause}
        LIMIT {PAGE_SIZE} OFFSET {offset}
    '''

    result = await conn.execute_query(sql)
    rows = result[1]

    # 各行を ClipVideo モデルに変換
    clip_videos: list[schemas.ClipVideo] = []
    for row in rows:
        clip_video = await ConvertRowToClipVideo(row)
        clip_videos.append(clip_video)

    return schemas.ClipVideos(
        clip_videos = clip_videos,
        total = total,
    )


@router.get(
    '/{clip_video_id}',
    summary = 'クリップ動画情報 API',
    response_description = 'クリップ動画の情報。',
    response_model = schemas.ClipVideo,
)
async def ClipVideoAPI(
    clip_video_id: Annotated[int, Path(description='クリップ動画の ID 。')],
) -> schemas.ClipVideo:
    """
    指定された ID のクリップ動画の情報を取得する。
    """

    # データベース接続を取得
    conn = connections.get('default')

    # クリップ動画とそれに紐づく録画番組情報を取得
    sql = '''
        SELECT
            cv.id as cv_id,
            cv.recorded_video_id,
            cv.title as cv_title,
            cv.file_path,
            cv.file_hash,
            cv.file_size,
            cv.start_time as start_time_in_video,
            cv.end_time as end_time_in_video,
            cv.duration as cv_duration,
            cv.segments as segments,
            cv.container_format,
            cv.video_codec,
            cv.video_codec_profile,
            cv.video_scan_type,
            cv.video_frame_rate,
            cv.video_resolution_width,
            cv.video_resolution_height,
            cv.primary_audio_codec,
            cv.primary_audio_channel,
            cv.primary_audio_sampling_rate,
            cv.secondary_audio_codec,
            cv.secondary_audio_channel,
            cv.secondary_audio_sampling_rate,
            cv.created_at,
            cv.updated_at,
            rp.id as rp_id,
            rp.channel_id,
            rp.network_id as rp_network_id,
            rp.service_id as rp_service_id,
            rp.event_id,
            rp.series_id,
            rp.series_broadcast_period_id,
            rp.title as rp_title,
            rp.description,
            rp.detail,
            rp.start_time,
            rp.end_time,
            rp.duration as rp_duration,
            rp.is_free,
            rp.genres,
            rp.primary_audio_type,
            rp.primary_audio_language,
            rp.secondary_audio_type,
            rp.secondary_audio_language,
            ch.id as ch_id,
            ch.display_channel_id,
            ch.network_id as ch_network_id,
            ch.service_id as ch_service_id,
            ch.transport_stream_id,
            ch.remocon_id,
            ch.channel_number,
            ch.type,
            ch.name as ch_name,
            ch.jikkyo_force,
            ch.is_subchannel,
            s.id as series_id,
            s.title as series_title,
            s.description as series_description
        FROM clip_videos cv
        INNER JOIN recorded_videos rv ON cv.recorded_video_id = rv.id
        INNER JOIN recorded_programs rp ON rv.recorded_program_id = rp.id
        LEFT JOIN channels ch ON rp.channel_id = ch.id
        LEFT JOIN series s ON rp.series_id = s.id
        WHERE cv.id = ?
    '''

    result = await conn.execute_query(sql, [clip_video_id])
    rows = result[1]

    if not rows:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video not found',
        )

    return await ConvertRowToClipVideo(rows[0])


@router.delete(
    '/{clip_video_id}',
    summary = 'クリップ動画削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def ClipVideoDeleteAPI(
    clip_video_id: Annotated[int, Path(description='クリップ動画の ID 。')],
    current_user: Annotated[User, Depends(GetCurrentAdminUser)],
) -> None:
    """
    指定された ID のクリップ動画を削除する。
    管理者権限が必要。
    """

    # クリップ動画を取得
    clip_video = await ClipVideo.get_or_none(id=clip_video_id)
    if not clip_video:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video not found',
        )

    # ファイルを削除
    file_path = pathlib.Path(clip_video.file_path)
    if file_path.exists():
        try:
            await anyio.Path(file_path).unlink()
            logging.info(f'[ClipVideoDeleteAPI] Deleted clip video file. [clip_video_id: {clip_video_id}, file_path: {file_path}]')
        except Exception as e:
            logging.error(f'[ClipVideoDeleteAPI] Failed to delete clip video file. [clip_video_id: {clip_video_id}, file_path: {file_path}, error: {e}]')

    # サムネイルを削除
    thumbnail_paths = [
        THUMBNAILS_DIR / f'{clip_video.file_hash}.webp',
        THUMBNAILS_DIR / f'{clip_video.file_hash}_tile.webp',
    ]
    for thumbnail_path in thumbnail_paths:
        if thumbnail_path.exists():
            try:
                await anyio.Path(thumbnail_path).unlink()
                logging.info(
                    f'[ClipVideoDeleteAPI] Deleted clip video thumbnail. '
                    f'[clip_video_id: {clip_video_id}, thumbnail_path: {thumbnail_path}]'
                )
            except Exception as e:
                logging.error(
                    f'[ClipVideoDeleteAPI] Failed to delete clip video thumbnail. '
                    f'[clip_video_id: {clip_video_id}, thumbnail_path: {thumbnail_path}, error: {e}]'
                )

    # データベースから削除
    await clip_video.delete()
    logging.info(f'[ClipVideoDeleteAPI] Deleted clip video from database. [clip_video_id: {clip_video_id}]')


@router.get(
    '/{clip_video_id}/thumbnail',
    summary = 'クリップ動画サムネイル API',
    response_description = 'クリップ動画のサムネイル画像 (WebP または JPEG) 。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'image/webp': {}, 'image/jpeg': {}}},
        304: {'description': 'Not Modified'},
        404: {'description': 'Clip video not found'},
    },
)
async def ClipVideoThumbnailAPI(
    request: Request,
    clip_video_id: Annotated[int, Path(description='クリップ動画の ID 。')],
) -> Response:
    """
    指定された ID のクリップ動画のサムネイル画像を取得する。
    クリップ動画のサムネイルが存在すればそれを返し、なければ元の録画番組のサムネイルを返す。
    """

    # クリップ動画を取得
    # 注意: select_related() を get_or_none() の後にチェーンすると型が期待と異なる場合があるため
    # ここでは一旦モデルを取得し、必要な関連は後で fetch_related() で読み込む。
    clip_video = await ClipVideo.get_or_none(id=clip_video_id)
    if not clip_video:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video not found',
        )

    # クリップ動画専用のサムネイルパスを取得 (file_hash ベース)
    base_thumbnail_path = anyio.Path(str(THUMBNAILS_DIR)) / clip_video.file_hash

    async def select_existing_thumbnail() -> tuple[str | None, str | None]:
        for suffix, media_type in [('.webp', 'image/webp'), ('.jpg', 'image/jpeg')]:
            candidate = base_thumbnail_path.with_suffix(suffix)
            if await candidate.is_file():
                return str(candidate), media_type
        return None, None

    clip_thumbnail_path, media_type = await select_existing_thumbnail()

    # サムネイルが存在しない場合は生成を試みる
    if clip_thumbnail_path is None:
        clip_duration_sec = float(clip_video.duration)
        if clip_duration_sec > 0:
            face_detection_mode: str | None = None
            try:
                await clip_video.fetch_related('recorded_video__recorded_program')
                recorded_video = clip_video.recorded_video
                recorded_program = recorded_video.recorded_program if recorded_video is not None else None
                if recorded_program is not None:
                    genres = recorded_program.genres if isinstance(recorded_program.genres, list) else []

                    def is_anime_genre(genre: dict[str, str]) -> bool:
                        major = genre.get('major')
                        middle = genre.get('middle')
                        if major == 'アニメ・特撮' and middle != '特撮':
                            return True
                        if major == '映画' and middle == 'アニメ':
                            return True
                        return False

                    def is_live_action_genre(genre: dict[str, str]) -> bool:
                        major = genre.get('major')
                        middle = genre.get('middle')
                        if major in {'ニュース・報道', '情報・ワイドショー', 'ドラマ', '劇場・公演'}:
                            return True
                        if major == 'バラエティ' and middle != 'お笑い・コメディ':
                            return True
                        if major == 'アニメ・特撮' and middle == '特撮':
                            return True
                        if major == '映画' and middle != 'アニメ':
                            return True
                        if major == 'ドキュメンタリー・教養' and middle in {'社会・時事', '歴史・紀行', 'インタビュー・討論'}:
                            return True
                        return False

                    has_anime = any(is_anime_genre(genre) for genre in genres)
                    has_live = any(is_live_action_genre(genre) for genre in genres)
                    if has_anime and not has_live:
                        face_detection_mode = 'Anime'
                    elif has_live:
                        face_detection_mode = 'Human'
            except Exception as detect_ex:
                logging.error(
                    f'[ClipVideoThumbnailAPI] Failed to determine face detection mode. '
                    f'[clip_video_id: {clip_video_id}, error: {detect_ex}]'
                )

            try:
                clip_file_path = pathlib.Path(clip_video.file_path)
                if clip_file_path.exists():
                    generator = ThumbnailGenerator(
                        file_path = anyio.Path(str(clip_file_path)),
                        container_format = clip_video.container_format,
                        file_hash = clip_video.file_hash,
                        duration_sec = clip_duration_sec,
                        candidate_time_ranges = [(0.0, clip_duration_sec)],
                        face_detection_mode = face_detection_mode,  # type: ignore[arg-type]
                    )
                    await generator.generateAndSave()
                else:
                    logging.warning(
                        f'[ClipVideoThumbnailAPI] Clip file not found. '
                        f'[clip_video_id: {clip_video_id}, file_path: {clip_file_path}]'
                    )
            except Exception as thumb_ex:
                logging.error(
                    f'[ClipVideoThumbnailAPI] Failed to generate thumbnail. '
                    f'[clip_video_id: {clip_video_id}, error: {thumb_ex}]',
                    exc_info = thumb_ex,
                )

        # 生成後のサムネイルを再取得
    clip_thumbnail_path, media_type = await select_existing_thumbnail()

    # サムネイルが存在する場合はキャッシュ制御付きで返す
    if clip_thumbnail_path is not None and media_type is not None:

        def is_content_not_modified(response_headers: Headers, request_headers: Headers) -> bool:
            """304 レスポンスを返すべきかどうかを判定する"""

            def parse_if_none_match(header_value: str) -> set[str]:
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

            if_none_match = request_headers.get('if-none-match')
            etag = response_headers.get('etag')
            if if_none_match is not None:
                request_tags = parse_if_none_match(if_none_match)
                if '*' in request_tags:
                    return etag is not None
                if etag is not None:
                    normalized_etag = etag.strip('"')
                    if normalized_etag in request_tags or etag in request_tags:
                        return True
                return False

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

        thumbnail_anyio_path = anyio.Path(clip_thumbnail_path)
        stat_result = await thumbnail_anyio_path.stat()
        response = FileResponse(
            clip_thumbnail_path,
            media_type = media_type,
            stat_result = stat_result,
            headers = {
                'Cache-Control': 'public, no-transform, immutable, max-age=2592000',
            }
        )

        if is_content_not_modified(response.headers, request.headers):
            headers_304 = {
                key: value for key, value in response.headers.items()
                if key.lower() != 'content-length'
            }
            return Response(
                status_code = 304,
                headers = headers_304,
            )

        return response

    # クリップ動画のサムネイルが存在しない場合は、元の録画番組のサムネイルを返す
    recorded_video = clip_video.recorded_video
    recorded_program = recorded_video.recorded_program if recorded_video is not None else None  # type: ignore[attr-defined]
    if recorded_program is not None:
        try:
            await recorded_program.fetch_related('recorded_video')
        except Exception as fetch_ex:
            logging.error(
                f'[ClipVideoThumbnailAPI] Failed to fetch related recorded_video for fallback thumbnail. '
                f'[clip_video_id: {clip_video_id}, error: {fetch_ex}]'
            )
        else:
            from app.routers.VideosRouter import GetThumbnailResponse
            return await GetThumbnailResponse(request, recorded_program)

    # 録画番組情報が取得できない場合はデフォルトサムネイルを返す
    default_thumbnail_path = STATIC_DIR / 'thumbnails' / 'default.webp'
    return FileResponse(
        default_thumbnail_path,
        media_type = 'image/webp',
        headers = {
            'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        }
    )


@router.get(
    '/{clip_video_id}/download',
    summary = 'クリップ動画ダウンロード API',
    response_description = 'クリップ動画のファイル。',
    response_class = FileResponse,
    responses = {
        200: {'content': {'video/mp2t': {}, 'video/mp4': {}}},
        404: {'description': 'Specified clip_video_id was not found'},
    },
)
async def ClipVideoDownloadAPI(
    clip_video_id: Annotated[int, Path(description='クリップ動画の ID 。')],
) -> FileResponse:
    """
    指定されたクリップ動画のファイルをダウンロードする。
    """

    # クリップ動画を取得
    clip_video = await ClipVideo.get_or_none(id=clip_video_id)
    if not clip_video:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video not found',
        )

    # ファイルパスとファイル名を取得
    file_path = pathlib.Path(clip_video.file_path)
    filename = file_path.name

    # ファイルが存在しない場合
    if not file_path.exists():
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video file not found',
        )

    # コンテナフォーマットに応じた MIME タイプを設定
    if clip_video.container_format == 'MPEG-TS':
        media_type = 'video/mp2t'
    else:  # MPEG-4
        media_type = 'video/mp4'

    # ファイルをダウンロードさせる
    return FileResponse(
        path = str(file_path),
        filename = filename,
        media_type = media_type,
    )


def _parse_frame_rate(frame_rate: str | None) -> float | None:
    """FFprobe から取得したフレームレート文字列を float に変換する"""

    if frame_rate is None:
        return None
    if '/' in frame_rate:
        num, den = frame_rate.split('/')
        if float(den) == 0.0:
            return None
        return round(float(num) / float(den), 2)
    return round(float(frame_rate), 2)


async def _analyze_clip_video_metadata(file_path: pathlib.Path) -> dict[str, Any] | None:
    """クリップ動画ファイルのメタデータを解析し、ClipVideo モデルへ適用する値を返す"""

    analyzer = MetadataAnalyzer(file_path)
    result = await anyio.to_thread.run_sync(analyzer.analyzeMediaInfo)
    if result is None:
        return None

    full_probe, sample_probe, _ = result
    video_streams = sample_probe.getVideoStreams()
    audio_streams = sample_probe.getAudioStreams()

    if len(video_streams) == 0 or len(audio_streams) == 0:
        return None

    video_stream = video_streams[0]
    audio_stream = audio_streams[0]

    if full_probe.format.format_name == 'mpegts':
        container_format: Literal['MPEG-TS', 'MPEG-4'] = 'MPEG-TS'
    elif 'mp4' in full_probe.format.format_name:
        container_format = 'MPEG-4'
    else:
        return None

    video_codec_map = {
        'mpeg2video': 'MPEG-2',
        'h264': 'H.264',
        'hevc': 'H.265',
    }
    codec_name = video_stream.codec_name
    if codec_name not in video_codec_map:
        return None

    video_scan_type = 'Interlaced'
    if (video_stream.field_order or '').lower() == 'progressive':
        video_scan_type = 'Progressive'
    elif (full_probe.getVideoStreams()[0].field_order or '').lower() == 'progressive':
        video_scan_type = 'Progressive'

    video_frame_rate = _parse_frame_rate(video_stream.avg_frame_rate) or _parse_frame_rate(video_stream.r_frame_rate)
    if video_frame_rate is None:
        return None

    primary_audio_channel_map = {
        1: 'Monaural',
        2: 'Stereo',
        6: '5.1ch',
    }
    primary_audio_channels = primary_audio_channel_map.get(audio_stream.channels)
    if primary_audio_channels is None:
        return None

    duration = None
    if full_probe.format.duration is not None:
        duration = float(full_probe.format.duration)
    elif video_stream.duration is not None:
        duration = float(video_stream.duration)

    return {
        'container_format': container_format,
        'video_codec': video_codec_map[codec_name],
        'video_codec_profile': (video_stream.profile or 'Main').split('@')[0],
        'video_scan_type': video_scan_type,
        'video_frame_rate': video_frame_rate,
        'video_resolution_width': video_stream.width,
        'video_resolution_height': video_stream.height,
        'primary_audio_codec': 'AAC-LC',
        'primary_audio_channel': primary_audio_channels,
        'primary_audio_sampling_rate': int(audio_stream.sample_rate),
        'secondary_audio_codec': None,
        'secondary_audio_channel': None,
        'secondary_audio_sampling_rate': None,
        'duration': duration,
    }


def _fallback_metadata_from_recorded_video(clip_video: ClipVideo) -> dict[str, Any]:
    """解析に失敗した際に RecordedVideo からコピーするメタデータを生成する"""

    recorded_video = clip_video.recorded_video
    if recorded_video is None:
        raise ValueError('Recorded video is not attached to the clip video.')

    return {
        'container_format': recorded_video.container_format,
        'video_codec': recorded_video.video_codec,
        'video_codec_profile': recorded_video.video_codec_profile,
        'video_scan_type': recorded_video.video_scan_type,
        'video_frame_rate': recorded_video.video_frame_rate,
        'video_resolution_width': recorded_video.video_resolution_width,
        'video_resolution_height': recorded_video.video_resolution_height,
        'primary_audio_codec': recorded_video.primary_audio_codec,
        'primary_audio_channel': recorded_video.primary_audio_channel,
        'primary_audio_sampling_rate': recorded_video.primary_audio_sampling_rate,
        'secondary_audio_codec': recorded_video.secondary_audio_codec,
        'secondary_audio_channel': recorded_video.secondary_audio_channel,
        'secondary_audio_sampling_rate': recorded_video.secondary_audio_sampling_rate,
        'duration': clip_video.duration,
    }


async def _calculate_file_hash(file_path: pathlib.Path) -> str:
    """クリップファイルの MD5 ハッシュを計算する"""

    def _inner() -> str:
        hash_md5 = hashlib.md5()
        with file_path.open('rb') as file:
            for chunk in iter(lambda: file.read(8192), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    return await anyio.to_thread.run_sync(_inner)


def _determine_face_detection_mode(clip_video: ClipVideo) -> str | None:
    """代表サムネイル生成時に使用する顔検出モードを判定する"""

    recorded_video = clip_video.recorded_video
    if recorded_video is None or recorded_video.recorded_program is None:
        return None

    genres = recorded_video.recorded_program.genres if isinstance(recorded_video.recorded_program.genres, list) else []

    def is_anime(genre: dict[str, str]) -> bool:
        major = genre.get('major')
        middle = genre.get('middle')
        if major == 'アニメ・特撮' and middle != '特撮':
            return True
        if major == '映画' and middle == 'アニメ':
            return True
        return False

    def is_live_action(genre: dict[str, str]) -> bool:
        major = genre.get('major')
        middle = genre.get('middle')
        if major in {'ニュース・報道', '情報・ワイドショー', 'ドラマ', '劇場・公演'}:
            return True
        if major == 'バラエティ' and middle != 'お笑い・コメディ':
            return True
        if major == 'アニメ・特撮' and middle == '特撮':
            return True
        if major == '映画' and middle != 'アニメ':
            return True
        if major == 'ドキュメンタリー・教養' and middle in {'社会・時事', '歴史・紀行', 'インタビュー・討論'}:
            return True
        return False

    has_anime = any(is_anime(genre) for genre in genres)
    has_live = any(is_live_action(genre) for genre in genres)
    if has_anime and not has_live:
        return 'Anime'
    if has_live:
        return 'Human'
    return None


@router.post(
    '/{clip_video_id}/reanalyze',
    summary = 'クリップ動画メタデータ再解析 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def ClipVideoReanalyzeAPI(
    clip_video_id: Annotated[int, Path(description='クリップ動画の ID 。')],
) -> None:
    """指定されたクリップ動画ファイルのメタデータを再解析し、データベースを更新する"""

    clip_video = await ClipVideo.get_or_none(id=clip_video_id)
    if clip_video is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video not found',
        )

    await clip_video.fetch_related('recorded_video__recorded_program')

    file_path = pathlib.Path(clip_video.file_path)
    clip_anyio_path = anyio.Path(str(file_path))
    if await clip_anyio_path.is_file() is False:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video file not found',
        )

    async with DriveIOLimiter.getSemaphore(clip_anyio_path):
        try:
            file_stat = await clip_anyio_path.stat()
            metadata = await _analyze_clip_video_metadata(file_path)
            if metadata is None:
                metadata = _fallback_metadata_from_recorded_video(clip_video)

            file_hash = await _calculate_file_hash(file_path)

            clip_video.file_size = file_stat.st_size
            clip_video.file_hash = file_hash
            clip_video.container_format = metadata['container_format']
            clip_video.video_codec = metadata['video_codec']
            clip_video.video_codec_profile = metadata['video_codec_profile']
            clip_video.video_scan_type = metadata['video_scan_type']
            clip_video.video_frame_rate = metadata['video_frame_rate']
            clip_video.video_resolution_width = metadata['video_resolution_width']
            clip_video.video_resolution_height = metadata['video_resolution_height']
            clip_video.primary_audio_codec = metadata['primary_audio_codec']
            clip_video.primary_audio_channel = metadata['primary_audio_channel']
            clip_video.primary_audio_sampling_rate = metadata['primary_audio_sampling_rate']
            clip_video.secondary_audio_codec = metadata['secondary_audio_codec']
            clip_video.secondary_audio_channel = metadata['secondary_audio_channel']
            clip_video.secondary_audio_sampling_rate = metadata['secondary_audio_sampling_rate']
            if metadata['duration'] is not None:
                clip_video.duration = float(metadata['duration'])

            await clip_video.save()

            logging.info(
                '[ClipVideoReanalyzeAPI] Updated clip metadata. '
                f'[clip_video_id: {clip_video_id}, file_size: {clip_video.file_size}]'
            )

        except Exception as ex:
            logging.error(
                f'[ClipVideoReanalyzeAPI] Failed to reanalyze clip video. '
                f'[clip_video_id: {clip_video_id}, error: {ex}]',
                exc_info = ex,
            )
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to reanalyze the clip video: {ex!s}',
            )


@router.post(
    '/{clip_video_id}/thumbnail/regenerate',
    summary = 'クリップ動画サムネイル再生成 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def ClipVideoThumbnailRegenerateAPI(
    clip_video_id: Annotated[int, Path(description='クリップ動画の ID 。')],
    skip_tile_if_exists: Annotated[
        bool,
        Query(description='既存のシークバー用タイル画像があれば再利用するかどうか。'),
    ] = False,
) -> None:
    """指定されたクリップ動画のサムネイルを再生成する"""

    clip_video = await ClipVideo.get_or_none(id=clip_video_id)
    if clip_video is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video not found',
        )

    await clip_video.fetch_related('recorded_video__recorded_program')

    clip_file_path = pathlib.Path(clip_video.file_path)
    clip_anyio_path = anyio.Path(str(clip_file_path))
    if await clip_anyio_path.is_file() is False:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Clip video file not found',
        )

    if float(clip_video.duration) <= 0.0:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'Clip video duration is invalid',
        )

    async with DriveIOLimiter.getSemaphore(clip_anyio_path):
        try:
            face_detection_mode = _determine_face_detection_mode(clip_video)

            generator = ThumbnailGenerator(
                file_path = clip_anyio_path,
                container_format = clip_video.container_format,
                file_hash = clip_video.file_hash,
                duration_sec = float(clip_video.duration),
                candidate_time_ranges = [(0.0, float(clip_video.duration))],
                face_detection_mode = face_detection_mode,  # type: ignore[arg-type]
            )
            await generator.generateAndSave(skip_tile_if_exists=skip_tile_if_exists)

            logging.info(
                '[ClipVideoThumbnailRegenerateAPI] Regenerated clip thumbnails. '
                f'[clip_video_id: {clip_video_id}, skip_tile_if_exists: {skip_tile_if_exists}]'
            )

        except Exception as ex:
            logging.error(
                f'[ClipVideoThumbnailRegenerateAPI] Failed to regenerate clip thumbnails. '
                f'[clip_video_id: {clip_video_id}, error: {ex}]',
                exc_info = ex,
            )
            raise HTTPException(
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail = f'Failed to regenerate clip thumbnails: {ex!s}',
            )
