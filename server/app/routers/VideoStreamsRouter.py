
import asyncio
import hashlib
import json
import shutil
import uuid
from pathlib import Path as PathLib
from typing import Annotated
from urllib.parse import quote

import anyio
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse

from app import logging
from app.constants import DATA_DIR, LIBRARY_PATH, QUALITY, QUALITY_TYPES
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.models.ClipVideo import ClipVideo
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.schemas import (
    VideoClipExportRequest,
    VideoClipExportResult,
    VideoClipExportStatus,
)
from app.streams.VideoStream import VideoStream


# ルーター
router = APIRouter(
    tags = ['Streams'],
    prefix = '/api/streams/video',
)


async def ValidateVideoID(video_id: Annotated[int, Path(description='録画番組の ID 。')]) -> RecordedProgram:
    """ 録画番組 ID のバリデーション """

    # 指定された video_id が存在するか確認
    recorded_program = await RecordedProgram.filter(id=video_id).get_or_none() \
        .select_related('recorded_video') \
        .select_related('channel')
    if recorded_program is None:
        logging.error(f'[VideoStreamsRouter][ValidateVideoID] Specified video_id was not found. [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    return recorded_program


async def ValidateQuality(quality: Annotated[str, Path(description='映像の品質。ex: 1080p')]) -> QUALITY_TYPES:
    """ 映像の品質のバリデーション """

    # 指定された品質が存在するか確認
    if quality not in QUALITY:
        logging.error(f'[VideoStreamsRouter][ValidateQuality] Specified quality was not found. [quality: {quality}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified quality was not found',
        )

    return quality


@router.get(
    '/{video_id}/{quality}/playlist',
    summary = '録画番組 HLS M3U8 プレイリスト API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': '録画番組の HLS M3U8 プレイリスト。',
            'content': {'application/vnd.apple.mpegurl': {}},
        }
    }
)
async def VideoHLSPlaylistAPI(
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
    cache_key: Annotated[str | None, Query(description='キャッシュ制御用のキー。')] = None,
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS M3U8 プレイリストを返す。<br>
    この M3U8 プレイリストは仮想的なもので、すべてのセグメントデータがエンコード済みとは限らない。セグメントはリクエストされ次第随時生成される。
    """

    # 録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, quality)

    # 仮想 HLS M3U8 プレイリストを取得
    virtual_playlist = await video_stream.getVirtualPlaylist(cache_key)
    return Response(
        content = virtual_playlist,
        media_type = 'application/vnd.apple.mpegurl',
        headers = {
            'Cache-Control': 'max-age=0',
        },
    )


@router.get(
    '/{video_id}/{quality}/segment',
    summary = '録画番組 HLS セグメント API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'HLS セグメントとして分割された MPEG-TS データ。',
            'content': {'video/mp2t': {}},
        }
    }
)
async def VideoHLSSegmentAPI(
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
    sequence: Annotated[int, Query(description='HLS セグメントの 0 スタートのシーケンス番号。')],
    cache_key: Annotated[str | None, Query(description='キャッシュ制御用のキー。')],
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS セグメントを返す。<br>
    呼び出された時点でエンコードされていない場合は既存のエンコードタスクが終了され、<br>
    sequence の HLS セグメントが含まれる範囲から新たにエンコードタスクが開始される。
    """

    # 録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, quality)

    # セグメントを取得（キャッシュキーはブラウザキャッシュ避けのための ID なので特に使わない）
    segment_data = await video_stream.getSegment(sequence)
    if segment_data is None:
        logging.error(f'[VideoHLSSegmentAPI] Specified sequence segment was not found. [video_id: {recorded_program.id}, quality: {quality}, sequence: {sequence}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified sequence segment was not found',
        )

    # 取得した MPEG-TS データを返す
    return Response(
        content = segment_data,
        media_type = 'video/mp2t',
        headers = {
            # キャッシュ有効期間を3時間に設定
            'Cache-Control': 'max-age=10800',
        },
    )


@router.get(
    '/{video_id}/{quality}/buffer',
    summary = '録画番組 HLS バッファ範囲 API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': '録画番組の HLS バッファ範囲が随時配信されるイベントストリーム。',
            'content': {'text/event-stream': {}},
        }
    }
)
async def VideoHLSBufferAPI(
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
):
    """
    録画番組の HLS バッファ範囲を Server-Sent Events で随時配信する。

    イベントには、
    - バッファ範囲の更新を示す **buffer_range_update**
    の1種類がある。

    どのイベントでも配信される JSON 構造は同じ。<br>
    エンコードタスクが終了した場合は、接続を終了する。
    """

    # 録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, quality)

    # バッファ範囲の変更を監視し、変更があればバッファ範囲をイベントストリームとして出力する
    async def generator():
        """イベントストリームを出力するジェネレーター"""

        # 初期値
        previous_buffer_range = video_stream.getBufferRange()

        # 初回接続時に必ず現在のバッファ範囲を返す
        yield {
            'event': 'buffer_range_update',  # buffer_range_update イベントを設定
            'data': json.dumps({
                'begin': previous_buffer_range[0],
                'end': previous_buffer_range[1],
            }),
        }

        while True:

            # 現在のバッファ範囲を取得
            buffer_range = video_stream.getBufferRange()

            # 以前の結果と異なっている場合のみレスポンスを返す
            if previous_buffer_range != buffer_range:
                logging.info(f'[VideoHLSBufferAPI] Buffer range updated. [begin: {buffer_range[0]}, end: {buffer_range[1]}]')
                yield {
                    'event': 'buffer_range_update',  # buffer_range_update イベントを設定
                    'data': json.dumps({
                        'begin': buffer_range[0],
                        'end': buffer_range[1],
                    }),
                }

                # 取得結果を保存
                previous_buffer_range = buffer_range

            # ビジーにならないように、0.1秒ごとにチェックする
            await asyncio.sleep(0.1)

    # EventSourceResponse でイベントストリームを配信する
    return EventSourceResponse(generator())


@router.put(
    '/{video_id}/{quality}/keep-alive',
    summary = '録画番組 HLS Keep-Alive API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def VideoHLSKeepAliveAPI(
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    quality: Annotated[QUALITY_TYPES, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
):
    """
    録画番組のストリーミング用 HLS セグメントの生成を継続するための API 。<br>
    ストリーミングセッションを維持するために、この API は録画番組の視聴を続けている間、定期的に呼び出さなければならない。<br>
    この API が定期的に呼び出されなくなった場合、一定時間後にストリーミング用 HLS セグメントの生成が停止され、メモリ上のデータが破棄される。
    """

    # 録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, quality)

    # セッションのアクティブ状態を維持する
    video_stream.keepAlive()


# クリップ書き出しタスクの状態を保持するグローバル辞書
_clip_export_tasks: dict[str, VideoClipExportStatus] = {}


@router.post(
    '/{video_id}/clip-export',
    summary = '録画番組クリップ書き出し API',
    response_model = VideoClipExportResult,
)
async def VideoClipExportAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
    request: VideoClipExportRequest,
    background_tasks: BackgroundTasks,
) -> VideoClipExportResult:
    """
    録画番組の指定された時間範囲をクリップして MP4 ファイルとして書き出す。<br>
    書き出しはバックグラウンドで実行され、タスク ID が返される。<br>
    書き出しの進捗状況は /api/streams/video/{video_id}/clip-export/{task_id} で確認できる。
    """

    # 指定された video_id が存在するか確認
    recorded_program = await RecordedProgram.filter(id=video_id).get_or_none() \
        .select_related('recorded_video') \
        .select_related('channel')
    if recorded_program is None:
        logging.error(f'[VideoClipExportAPI] Specified video_id was not found. [video_id: {video_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified video_id was not found',
        )

    # 録画ファイルの存在確認
    recorded_video = recorded_program.recorded_video
    if recorded_video is None or not PathLib(recorded_video.file_path).exists():
        logging.error(f'[VideoClipExportAPI] Recorded video file not found. [video_id: {video_id}]')
        return VideoClipExportResult(
            is_success = False,
            detail = 'Recorded video file not found',
            task_id = None,
        )

    # 時間範囲のバリデーション
    if request.end_time > recorded_video.duration:
        logging.error(f'[VideoClipExportAPI] End time exceeds video duration. [video_id: {video_id}, end_time: {request.end_time}, duration: {recorded_video.duration}]')
        return VideoClipExportResult(
            is_success = False,
            detail = f'End time ({request.end_time}s) exceeds video duration ({recorded_video.duration}s)',
            task_id = None,
        )

    # タスク ID を生成
    task_id = str(uuid.uuid4())

    # 出力ディレクトリの作成
    output_dir = DATA_DIR / 'clip_exports'
    output_dir.mkdir(exist_ok=True)

    # 出力ファイル名を生成 (番組タイトル + 日時 + タスクID)
    # ファイル名に使えない文字を除去
    safe_title = ''.join(c for c in recorded_program.title if c.isalnum() or c in (' ', '-', '_')).strip()
    output_filename = f'{safe_title}_{request.start_time:.0f}-{request.end_time:.0f}_{task_id[:8]}.mp4'
    output_path = output_dir / output_filename

    # タスクの初期状態を登録
    _clip_export_tasks[task_id] = VideoClipExportStatus(
        task_id = task_id,
        status = 'Processing',
        progress = 0.0,
        detail = 'Clip export started',
        output_file_path = None,
        output_file_size = None,
    )

    # バックグラウンドでクリップ書き出しを実行
    background_tasks.add_task(
        ExecuteClipExport,
        task_id,
        recorded_video.file_path,
        str(output_path),
        request.start_time,
        request.end_time,
        recorded_video.duration,
        recorded_video.id,
        recorded_program.title,
    )

    logging.info(f'[VideoClipExportAPI] Clip export task started. [video_id: {video_id}, task_id: {task_id}, start_time: {request.start_time}, end_time: {request.end_time}]')

    return VideoClipExportResult(
        is_success = True,
        detail = 'Clip export task started',
        task_id = task_id,
    )


@router.get(
    '/{video_id}/clip-export/{task_id}',
    summary = '録画番組クリップ書き出しステータス API',
    response_model = VideoClipExportStatus,
)
async def VideoClipExportStatusAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
    task_id: Annotated[str, Path(description='クリップ書き出しタスクの ID 。')],
) -> VideoClipExportStatus:
    """
    指定されたタスク ID のクリップ書き出しの進捗状況を返す。
    """

    # タスクの存在確認
    if task_id not in _clip_export_tasks:
        logging.error(f'[VideoClipExportStatusAPI] Task not found. [video_id: {video_id}, task_id: {task_id}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Task not found',
        )

    return _clip_export_tasks[task_id]


@router.get(
    '/{video_id}/clip-export/{task_id}/download',
    summary = '録画番組クリップダウンロード API',
    response_class = FileResponse,
)
async def VideoClipDownloadAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
    task_id: Annotated[str, Path(description='クリップ書き出しタスクの ID 。')],
) -> FileResponse:
    """
    指定されたタスク ID で書き出されたクリップファイルをダウンロードする。<br>
    タスクが完了している場合のみダウンロード可能。
    """

    # タスクの存在確認
    if task_id not in _clip_export_tasks:
        logging.error(f'[VideoClipDownloadAPI] Task not found. [video_id: {video_id}, task_id: {task_id}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Task not found',
        )

    task = _clip_export_tasks[task_id]

    # タスクが完了しているか確認
    if task.status != 'Completed' or task.output_file_path is None:
        logging.error(f'[VideoClipDownloadAPI] Task not completed. [video_id: {video_id}, task_id: {task_id}, status: {task.status}]')
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'Task not completed or file not available',
        )

    # ファイルの存在確認
    output_path = PathLib(task.output_file_path)
    if not output_path.exists():
        logging.error(f'[VideoClipDownloadAPI] Output file not found. [video_id: {video_id}, task_id: {task_id}, path: {task.output_file_path}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Output file not found',
        )

    logging.info(f'[VideoClipDownloadAPI] Clip download started. [video_id: {video_id}, task_id: {task_id}, path: {task.output_file_path}]')

    # ファイル名を URL エンコード (日本語対応)
    encoded_filename = quote(output_path.name)
    
    return FileResponse(
        path = str(output_path),
        media_type = 'video/mp4',
        headers = {
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.get(
    '/{video_id}/clip-export/{task_id}/preview',
    summary = '録画番組クリッププレビュー API',
    response_class = FileResponse,
)
async def VideoClipPreviewAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
    task_id: Annotated[str, Path(description='クリップ書き出しタスクの ID 。')],
) -> FileResponse:
    """
    指定されたタスク ID で書き出されたクリップファイルをブラウザでプレビューする。<br>
    タスクが完了している場合のみプレビュー可能。ダウンロードではなくブラウザ内で再生される。
    """

    # タスクの存在確認
    if task_id not in _clip_export_tasks:
        logging.error(f'[VideoClipPreviewAPI] Task not found. [video_id: {video_id}, task_id: {task_id}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Task not found',
        )

    task = _clip_export_tasks[task_id]

    # タスクが完了しているか確認
    if task.status != 'Completed' or task.output_file_path is None:
        logging.error(f'[VideoClipPreviewAPI] Task not completed. [video_id: {video_id}, task_id: {task_id}, status: {task.status}]')
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'Task not completed or file not available',
        )

    # ファイルの存在確認
    output_path = PathLib(task.output_file_path)
    if not output_path.exists():
        logging.error(f'[VideoClipPreviewAPI] Output file not found. [video_id: {video_id}, task_id: {task_id}, path: {task.output_file_path}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Output file not found',
        )

    logging.info(f'[VideoClipPreviewAPI] Clip preview started. [video_id: {video_id}, task_id: {task_id}, path: {task.output_file_path}]')

    # ファイル名を URL エンコード (日本語対応)
    encoded_filename = quote(output_path.name)
    
    # Content-Disposition を inline に設定してブラウザ内で表示
    return FileResponse(
        path = str(output_path),
        media_type = 'video/mp4',
        headers = {
            'Content-Disposition': f"inline; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.post(
    '/{video_id}/clip-export/{task_id}/save',
    summary = '録画番組クリップDB保存 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def VideoClipSaveAPI(
    video_id: Annotated[int, Path(description='録画番組の ID 。')],
    task_id: Annotated[str, Path(description='クリップ書き出しタスクの ID 。')],
) -> None:
    """
    指定されたタスク ID で書き出されたクリップファイルをデータベースに保存する。<br>
    プレビュー後、ユーザーが保存を決定した際に呼び出される。
    """

    # タスクの存在確認
    if task_id not in _clip_export_tasks:
        logging.error(f'[VideoClipSaveAPI] Task not found. [video_id: {video_id}, task_id: {task_id}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Task not found',
        )

    task = _clip_export_tasks[task_id]

    # タスクが完了しているか確認
    if task.status != 'Completed' or task.output_file_path is None:
        logging.error(f'[VideoClipSaveAPI] Task not completed. [video_id: {video_id}, task_id: {task_id}, status: {task.status}]')
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'Task not completed',
        )

    # ファイルの存在確認
    output_path = PathLib(task.output_file_path)
    if not output_path.exists():
        logging.error(f'[VideoClipSaveAPI] Output file not found. [video_id: {video_id}, task_id: {task_id}, path: {task.output_file_path}]')
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = 'Output file not found',
        )

    # 必要な情報が全て揃っているか確認
    if (task.recorded_video_id is None or task.recorded_program_title is None or 
        task.start_time is None or task.end_time is None or task.duration is None or
        task.file_hash is None or task.output_file_size is None):
        logging.error(f'[VideoClipSaveAPI] Task metadata incomplete. [video_id: {video_id}, task_id: {task_id}]')
        logging.error(f'  recorded_video_id: {task.recorded_video_id}')
        logging.error(f'  recorded_program_title: {task.recorded_program_title}')
        logging.error(f'  start_time: {task.start_time}')
        logging.error(f'  end_time: {task.end_time}')
        logging.error(f'  duration: {task.duration}')
        logging.error(f'  file_hash: {task.file_hash}')
        logging.error(f'  output_file_size: {task.output_file_size}')
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'Task metadata incomplete',
        )

    # クリップ動画のタイトルを生成
    clip_title = f'{task.recorded_program_title} ({int(task.start_time)}秒〜{int(task.end_time)}秒)'

    logging.info(f'[VideoClipSaveAPI] Attempting to save clip to database. [clip_title: {clip_title}]')

    try:
        # 録画ビデオ情報を取得
        logging.info(f'[VideoClipSaveAPI] Fetching RecordedVideo. [id: {task.recorded_video_id}]')
        recorded_video = await RecordedVideo.get(id=task.recorded_video_id)
        await recorded_video.fetch_related('recorded_program')
        logging.info(f'[VideoClipSaveAPI] RecordedVideo fetched successfully.')

        # 代表サムネイルで顔検出を行うかどうかを決定
        face_detection_mode: str | None = None
        try:
            recorded_program = recorded_video.recorded_program
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
            logging.error(f'[VideoClipSaveAPI] Failed to determine face detection mode. [video_id: {video_id}, task_id: {task_id}, error: {detect_ex}]')

        # クリップファイルを永続的な保存先に移動
        temp_file_path = PathLib(task.output_file_path)
        clip_videos_dir = DATA_DIR / 'clip_videos'
        clip_videos_dir.mkdir(parents=True, exist_ok=True)
        
        # 新しいファイル名を生成（ファイル名はそのまま使用）
        permanent_file_path = clip_videos_dir / temp_file_path.name
        
        # ファイルを移動
        logging.info(f'[VideoClipSaveAPI] Moving clip file. [from: {temp_file_path}, to: {permanent_file_path}]')
        shutil.move(str(temp_file_path), str(permanent_file_path))
        logging.info(f'[VideoClipSaveAPI] Clip file moved successfully.')

        # クリップ動画をデータベースに保存
        logging.info(f'[VideoClipSaveAPI] Creating ClipVideo record...')
        clip_video = await ClipVideo.create(
            recorded_video_id = task.recorded_video_id,
            title = clip_title,
            file_path = str(permanent_file_path),  # 永続的なパスを保存
            file_hash = task.file_hash,
            file_size = task.output_file_size,
            start_time = task.start_time,
            end_time = task.end_time,
            duration = task.duration,
            container_format = recorded_video.container_format,
            video_codec = recorded_video.video_codec,
            video_codec_profile = recorded_video.video_codec_profile,
            video_scan_type = recorded_video.video_scan_type,
            video_frame_rate = recorded_video.video_frame_rate,
            video_resolution_width = recorded_video.video_resolution_width,
            video_resolution_height = recorded_video.video_resolution_height,
            primary_audio_codec = recorded_video.primary_audio_codec,
            primary_audio_channel = recorded_video.primary_audio_channel,
            primary_audio_sampling_rate = recorded_video.primary_audio_sampling_rate,
            secondary_audio_codec = recorded_video.secondary_audio_codec,
            secondary_audio_channel = recorded_video.secondary_audio_channel,
            secondary_audio_sampling_rate = recorded_video.secondary_audio_sampling_rate,
        )
        logging.info(f'[VideoClipSaveAPI] Clip video saved to database. [video_id: {video_id}, task_id: {task_id}, clip_video_id: {clip_video.id}, permanent_path: {permanent_file_path}]')

        # クリップ動画の代表サムネイルとシークバー用サムネイルを生成
        clip_duration_sec = float(clip_video.duration)
        if clip_duration_sec <= 0:
            logging.warning(f'[VideoClipSaveAPI] Clip duration is invalid. Skip thumbnail generation. [video_id: {video_id}, task_id: {task_id}, duration: {clip_video.duration}]')
        else:
            candidate_ranges = [(0.0, clip_duration_sec)]
            try:
                generator = ThumbnailGenerator(
                    file_path = anyio.Path(str(permanent_file_path)),
                    container_format = clip_video.container_format,
                    file_hash = clip_video.file_hash,
                    duration_sec = clip_duration_sec,
                    candidate_time_ranges = candidate_ranges,
                    face_detection_mode = face_detection_mode,  # type: ignore[arg-type]
                )
                await generator.generateAndSave()
                logging.info(f'[VideoClipSaveAPI] Generated clip thumbnails. [video_id: {video_id}, task_id: {task_id}, clip_video_id: {clip_video.id}]')
            except Exception as thumb_ex:
                logging.error(
                    f'[VideoClipSaveAPI] Failed to generate clip thumbnails. '
                    f'[video_id: {video_id}, task_id: {task_id}, clip_video_id: {clip_video.id}, error: {thumb_ex}]',
                    exc_info = thumb_ex,
                )
    except Exception as ex:
        logging.error(f'[VideoClipSaveAPI] Failed to save clip video to database. [video_id: {video_id}, task_id: {task_id}, exception: {ex}]')
        # エラーが発生した場合、移動したファイルがあれば元に戻す
        if 'permanent_file_path' in locals() and permanent_file_path.exists():
            logging.info(f'[VideoClipSaveAPI] Rolling back file move. [from: {permanent_file_path}, to: {temp_file_path}]')
            shutil.move(str(permanent_file_path), str(temp_file_path))
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f'Failed to save clip video: {ex!s}',
        )


async def ExecuteClipExport(
    task_id: str,
    input_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    duration: float,
    recorded_video_id: int,
    recorded_program_title: str,
) -> None:
    """
    FFmpeg を使ってクリップを書き出す実際の処理
    バックグラウンドタスクとして実行される

    Args:
        task_id (str): タスク ID
        input_path (str): 入力ファイルパス
        output_path (str): 出力ファイルパス
        start_time (float): 開始時刻（秒）
        end_time (float): 終了時刻（秒）
        duration (float): 動画の総再生時間（秒）
        recorded_video_id (int): 録画ビデオの ID
        recorded_program_title (str): 録画番組のタイトル
    """

    try:
        # FFmpeg のパスを取得
        ffmpeg_path = LIBRARY_PATH['FFmpeg']

        # クリップの長さを計算
        clip_duration = end_time - start_time

        # FFmpeg コマンドを構築
        # -ss を -i の前に置くことで高速シークが可能になる
        # -c copy でストリームをそのままコピー（再エンコードなし）
        cmd = [
            ffmpeg_path,
            '-y',  # 既存ファイルを上書き
            '-ss', str(start_time),  # 開始位置（入力前に指定することで高速シーク）
            '-i', input_path,  # 入力ファイル
            '-t', str(clip_duration),  # クリップの長さ
            '-c', 'copy',  # コーデックをコピー（再エンコードしない）
            '-avoid_negative_ts', 'make_zero',  # タイムスタンプを調整
            '-movflags', '+faststart',  # Web 最適化（メタデータを先頭に配置）
            output_path,  # 出力ファイル
        ]

        logging.info(f'[ExecuteClipExport] Starting FFmpeg clip export. [task_id: {task_id}, command: {" ".join(cmd)}]')

        # FFmpeg を実行（進捗監視付き）
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.PIPE,
        )

        # 進捗を監視しながら実行
        stderr_output = []
        while True:
            line = await process.stderr.readline()  # type: ignore
            if not line:
                break

            line_str = line.decode('utf-8', errors='ignore')
            stderr_output.append(line_str)

            # FFmpeg の進捗情報を解析（time=の部分を抽出）
            if 'time=' in line_str:
                try:
                    # time=00:01:23.45 のような形式から秒数を抽出
                    time_str = line_str.split('time=')[1].split()[0]
                    time_parts = time_str.split(':')
                    if len(time_parts) == 3:
                        hours, minutes, seconds = time_parts
                        current_time = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
                        # 進捗率を計算（クリップの長さに対する割合）
                        progress = min((current_time / clip_duration) * 100, 100.0)
                        _clip_export_tasks[task_id].progress = progress
                        _clip_export_tasks[task_id].detail = f'Processing: {progress:.1f}%'
                except Exception:
                    pass  # 進捗解析に失敗しても続行

        # プロセスの完了を待つ
        await process.wait()

        # 終了コードを確認
        if process.returncode == 0:
            # 成功
            output_file_path = PathLib(output_path)
            output_file_size = output_file_path.stat().st_size

            # ファイルハッシュを計算
            file_hash_md5 = hashlib.md5()
            with open(output_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    file_hash_md5.update(chunk)
            file_hash = file_hash_md5.hexdigest()

            _clip_export_tasks[task_id].status = 'Completed'
            _clip_export_tasks[task_id].progress = 100.0
            _clip_export_tasks[task_id].detail = 'Clip export completed successfully'
            _clip_export_tasks[task_id].output_file_path = output_path
            _clip_export_tasks[task_id].output_file_size = output_file_size
            _clip_export_tasks[task_id].file_hash = file_hash
            # recorded_video_id と start_time, end_time もタスク情報に保存（DB保存時に使用）
            _clip_export_tasks[task_id].recorded_video_id = recorded_video_id
            _clip_export_tasks[task_id].recorded_program_title = recorded_program_title
            _clip_export_tasks[task_id].start_time = start_time
            _clip_export_tasks[task_id].end_time = end_time
            _clip_export_tasks[task_id].duration = clip_duration
            logging.info(f'[ExecuteClipExport] Clip export completed successfully. [task_id: {task_id}, output_path: {output_path}, size: {output_file_size}]')
        else:
            # 失敗
            stderr_full = ''.join(stderr_output)
            _clip_export_tasks[task_id].status = 'Failed'
            _clip_export_tasks[task_id].detail = f'FFmpeg failed with return code {process.returncode}'
            logging.error(f'[ExecuteClipExport] Clip export failed. [task_id: {task_id}, return_code: {process.returncode}, stderr: {stderr_full}]')

    except Exception as ex:
        # 例外が発生した場合
        _clip_export_tasks[task_id].status = 'Failed'
        _clip_export_tasks[task_id].detail = f'Exception occurred: {ex!s}'
        logging.error(f'[ExecuteClipExport] Clip export failed with exception. [task_id: {task_id}, exception: {ex}]')

