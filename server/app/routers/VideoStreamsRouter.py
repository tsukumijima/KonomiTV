
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
from app.config import Config
from app.constants import DATA_DIR, LIBRARY_PATH, QUALITY, QUALITY_TYPES
from app.metadata.ThumbnailGenerator import ThumbnailGenerator
from app.models.ClipVideo import ClipVideo
from app.models.RecordedProgram import RecordedProgram
from app.models.RecordedVideo import RecordedVideo
from app.schemas import (
    ClipSegment,
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

    # セグメントの正規化とバリデーション
    # フレームレートを取得
    frame_rate = recorded_video.video_frame_rate if recorded_video.video_frame_rate > 0 else 29.97

    def frame_to_time(frame: int) -> float:
        """フレーム番号を秒に変換"""
        return frame / frame_rate

    def time_to_frame(time_sec: float) -> int:
        """秒をフレーム番号に変換"""
        return int(time_sec * frame_rate)

    # セグメントをフレーム単位で管理
    raw_segments: list[dict[str, int | float]]
    if request.segments:
        raw_segments = []
        for segment in request.segments:
            # フレーム指定の場合はそのまま使用
            if segment.start_frame is not None and segment.end_frame is not None:
                raw_segments.append({
                    'start_frame': segment.start_frame,
                    'end_frame': segment.end_frame,
                    'start_time': frame_to_time(segment.start_frame),
                    'end_time': frame_to_time(segment.end_frame),
                })
            else:
                # 秒指定の場合はフレームに変換
                raw_segments.append({
                    'start_frame': time_to_frame(float(segment.start_time)),  # type: ignore
                    'end_frame': time_to_frame(float(segment.end_time)),  # type: ignore
                    'start_time': float(segment.start_time),  # type: ignore
                    'end_time': float(segment.end_time),  # type: ignore
                })
    else:
        # 単一セグメントの場合
        if request.start_frame is not None and request.end_frame is not None:
            raw_segments = [{
                'start_frame': request.start_frame,
                'end_frame': request.end_frame,
                'start_time': frame_to_time(request.start_frame),
                'end_time': frame_to_time(request.end_frame),
            }]
        else:
            assert request.start_time is not None and request.end_time is not None
            raw_segments = [{
                'start_frame': time_to_frame(float(request.start_time)),
                'end_frame': time_to_frame(float(request.end_time)),
                'start_time': float(request.start_time),
                'end_time': float(request.end_time),
            }]

    normalized_segments: list[dict[str, int | float]] = []
    total_frames = int(recorded_video.duration * frame_rate)
    for segment in raw_segments:
        end_time = segment['end_time']
        end_frame = segment['end_frame']
        if end_time > recorded_video.duration or end_frame > total_frames:
            logging.error(
                f'[VideoClipExportAPI] Segment end exceeds video duration. '
                f'[video_id: {video_id}, end_frame: {end_frame}, total_frames: {total_frames}]'
            )
            return VideoClipExportResult(
                is_success = False,
                detail = f'End frame ({end_frame}) exceeds video total frames ({total_frames})',
                task_id = None,
            )
        normalized_segments.append(segment)

    normalized_segments.sort(key=lambda s: s['start_frame'])

    total_clip_duration = 0.0
    for segment in normalized_segments:
        duration = segment['end_time'] - segment['start_time']
        if duration <= 0:
            logging.error(
                '[VideoClipExportAPI] Invalid segment duration detected. '
                f"[video_id: {video_id}, start_time: {segment['start_time']}, end_time: {segment['end_time']}]"
            )
            return VideoClipExportResult(
                is_success = False,
                detail = 'Each segment must have a positive duration',
                task_id = None,
            )
        total_clip_duration += duration

    if total_clip_duration <= 0:
        logging.error(f'[VideoClipExportAPI] Total clip duration is zero. [video_id: {video_id}]')
        return VideoClipExportResult(
            is_success = False,
            detail = 'Total clip duration must be greater than zero',
            task_id = None,
        )

    overall_start = normalized_segments[0]['start_time']
    overall_end = normalized_segments[-1]['end_time']

    # タスク ID を生成
    task_id = str(uuid.uuid4())

    # 出力ディレクトリの作成
    output_dir = DATA_DIR / 'clip_exports'
    output_dir.mkdir(exist_ok=True)

    # 出力ファイル名を生成 (番組タイトル + 範囲 + タスクID)
    safe_title = ''.join(c for c in recorded_program.title if c.isalnum() or c in (' ', '-', '_')).strip()
    range_suffix = '_'.join(f"{int(segment['start_time']):d}-{int(segment['end_time']):d}" for segment in normalized_segments)
    output_filename = f'{safe_title}_{range_suffix}_{task_id[:8]}.mp4'
    output_path = output_dir / output_filename

    # タスクの初期状態を登録
    # normalized_segments を ClipSegment のリストに変換
    clip_segments = [
        ClipSegment(
            start_frame=int(seg['start_frame']),
            end_frame=int(seg['end_frame']),
            start_time=float(seg['start_time']),
            end_time=float(seg['end_time']),
        )
        for seg in normalized_segments
    ]
    _clip_export_tasks[task_id] = VideoClipExportStatus(
        task_id = task_id,
        status = 'Processing',
        progress = 0.0,
        detail = 'Clip export started',
        output_file_path = None,
        output_file_size = None,
        recorded_video_id = recorded_video.id,
        recorded_program_title = recorded_program.title,
        start_time = overall_start,
        end_time = overall_end,
        duration = total_clip_duration,
        segments = clip_segments,
    )

    # バックグラウンドでクリップ書き出しを実行
    background_tasks.add_task(
        ExecuteClipExport,
        task_id,
        recorded_video.file_path,
        str(output_path),
        normalized_segments,
        recorded_video.id,
        recorded_program.title,
        frame_rate,
        recorded_video.video_resolution_width,
        recorded_video.video_resolution_height,
    )

    logging.info(
        '[VideoClipExportAPI] Clip export task started. '
        f'[video_id: {video_id}, task_id: {task_id}, segments: {normalized_segments}]'
    )

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
    if (
        task.recorded_video_id is None
        or task.recorded_program_title is None
        or task.start_time is None
        or task.end_time is None
        or task.duration is None
        or task.file_hash is None
        or task.output_file_size is None
        or task.segments is None
        or len(task.segments) == 0
    ):
        logging.error(f'[VideoClipSaveAPI] Task metadata incomplete. [video_id: {video_id}, task_id: {task_id}]')
        logging.error(f'  recorded_video_id: {task.recorded_video_id}')
        logging.error(f'  recorded_program_title: {task.recorded_program_title}')
        logging.error(f'  start_time: {task.start_time}')
        logging.error(f'  end_time: {task.end_time}')
        logging.error(f'  duration: {task.duration}')
        logging.error(f'  file_hash: {task.file_hash}')
        logging.error(f'  output_file_size: {task.output_file_size}')
        logging.error(f'  segments: {task.segments}')
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'Task metadata incomplete',
        )

    # クリップ動画のタイトルを生成
    if task.segments:
        ranges_str = ', '.join(
            f'{int(segment.start_time)}秒〜{int(segment.end_time)}秒' for segment in task.segments
        )
    else:
        ranges_str = f'{int(task.start_time)}秒〜{int(task.end_time)}秒'
    clip_title = f'{task.recorded_program_title} ({ranges_str})'

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
        server_settings = Config()
        configured_clip_dir = server_settings.video.clip_videos_folder
        if configured_clip_dir is not None:
            clip_videos_dir = PathLib(configured_clip_dir)
        else:
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
            segments = [segment.model_dump() for segment in task.segments],
            container_format = 'MPEG-4',  # クリップは常に MP4 形式
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
    segments: list[dict[str, int | float]],
    recorded_video_id: int,
    recorded_program_title: str,
    frame_rate: float,
    video_width: int,
    video_height: int,
) -> None:
    """FFmpeg を用いて複数セグメントのクリップをフレーム単位で書き出すバックグラウンド処理。"""

    temp_dir: PathLib | None = None

    try:
        ffmpeg_path = LIBRARY_PATH['FFmpeg']

        if len(segments) == 0:
            raise ValueError('No segments specified for clip export')

        # アスペクト比を計算
        # 日本の放送波は通常 1440x1080 (SAR 4:3) → DAR 16:9
        # または 1920x1080 (SAR 1:1) → DAR 16:9
        if video_width == 1440 and video_height == 1080:
            aspect_ratio = '16:9'
        elif video_width == 1920 and video_height == 1080:
            aspect_ratio = '16:9'
        elif video_width == 720 and video_height == 480:
            aspect_ratio = '16:9'  # SD放送
        elif video_width == 720 and video_height == 576:
            aspect_ratio = '16:9'  # PAL SD
        elif video_width > 0 and video_height > 0:
            # その他の解像度はピクセルアスペクト比を使用
            aspect_ratio = f'{video_width}:{video_height}'
        else:
            aspect_ratio = '16:9'  # デフォルト

        # 総フレーム数を計算
        total_clip_frames = sum(int(segment['end_frame']) - int(segment['start_frame']) for segment in segments)
        total_clip_duration = total_clip_frames / frame_rate
        if total_clip_frames <= 0:
            raise ValueError('Calculated clip frames must be positive')

        if len(segments) == 1:
            start_frame = int(segments[0]['start_frame'])
            end_frame = int(segments[0]['end_frame'])
            clip_frames = end_frame - start_frame
            clip_duration = clip_frames / frame_rate

            # フレーム単位で正確に切り出すため、再エンコードを行う
            # -c copy だとキーフレーム単位でしか切り出せないため、指定したフレームから始まらない場合がある
            # また、スマホ等でアスペクト比が正しく表示されない問題を解消するため、アスペクト比情報を焼き込む
            start_time = start_frame / frame_rate

            cmd = [
                ffmpeg_path,
                '-y',
                '-i', input_path,
                '-ss', str(start_time),  # -i の後に置くことで正確なシーク
                '-frames:v', str(clip_frames),
                '-c:v', 'libx264',  # 正確なカットとアスペクト比反映のため再エンコード
                '-preset', 'superfast',  # 高速化
                '-crf', '23',
                '-c:a', 'aac',  # 音声もAACで再エンコード（MP4互換性を確保）
                '-b:a', '128k',
                '-map_metadata', '0',  # 元のメタデータを保持
                '-aspect', aspect_ratio,  # アスペクト比を明示的に設定
                '-avoid_negative_ts', 'make_zero',
                '-movflags', '+faststart',
                '-f', 'mp4',  # MP4形式を明示的に指定
                '-progress', 'pipe:1',  # 進捗をstdoutに出力
                output_path,
            ]

            logging.info(f'[ExecuteClipExport] Starting FFmpeg clip export. [task_id: {task_id}, start_frame: {start_frame}, end_frame: {end_frame}, clip_frames: {clip_frames}, command: {" ".join(cmd)}]')

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE,
            )

            # 進捗を読み取る（-progress pipe:1 の出力をstdoutから読む）
            stderr_output: list[str] = []

            async def read_progress() -> None:
                while True:
                    line = await process.stdout.readline()  # type: ignore
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    if line_str.startswith('frame='):
                        try:
                            current_frames = int(line_str.split('=')[1])
                            progress = min((current_frames / clip_frames) * 100, 99.0)
                            _clip_export_tasks[task_id].progress = progress
                            _clip_export_tasks[task_id].detail = f'Processing: {current_frames}/{clip_frames} frames ({progress:.1f}%)'
                        except Exception:
                            pass

            async def read_stderr() -> None:
                while True:
                    line = await process.stderr.readline()  # type: ignore
                    if not line:
                        break
                    stderr_output.append(line.decode('utf-8', errors='ignore'))

            # 両方を並行して読み取る
            await asyncio.gather(read_progress(), read_stderr())

            await process.wait()

            if process.returncode != 0:
                stderr_full = ''.join(stderr_output)
                _clip_export_tasks[task_id].status = 'Failed'
                _clip_export_tasks[task_id].detail = f'FFmpeg failed with return code {process.returncode}'
                logging.error(
                    f'[ExecuteClipExport] Clip export failed. '
                    f'[task_id: {task_id}, return_code: {process.returncode}, stderr: {stderr_full}]'
                )
                return

        else:
            temp_dir = PathLib(output_path).parent / f'.clip_export_{task_id}'
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)

            segment_files: list[PathLib] = []
            processed_frames = 0

            for index, segment in enumerate(segments, start=1):
                start_frame = int(segment['start_frame'])
                end_frame = int(segment['end_frame'])
                segment_frames = end_frame - start_frame
                start_time = start_frame / frame_rate
                segment_file = temp_dir / f'segment_{index:02d}.ts'
                segment_files.append(segment_file)

                cmd = [
                    ffmpeg_path,
                    '-y',
                    '-i', input_path,
                    '-ss', str(start_time),  # -i の後に置くことで正確なシーク
                    '-frames:v', str(segment_frames),
                    '-c:v', 'libx264',  # 正確なカットとアスペクト比反映のため再エンコード
                    '-preset', 'superfast',
                    '-crf', '23',
                    '-c:a', 'aac',  # 音声もAACで再エンコード
                    '-b:a', '128k',
                    '-aspect', aspect_ratio,
                    '-avoid_negative_ts', 'make_zero',
                    '-f', 'mpegts',  # TS形式で出力（後で結合）
                    '-progress', 'pipe:1',  # 進捗をstdoutに出力
                    segment_file.as_posix(),
                ]

                logging.info(
                    f'[ExecuteClipExport] Starting segment extraction. '
                    f'[task_id: {task_id}, segment_index: {index}, start_frame: {start_frame}, end_frame: {end_frame}, command: {" ".join(cmd)}]'
                )

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout = asyncio.subprocess.PIPE,
                    stderr = asyncio.subprocess.PIPE,
                )

                stderr_output: list[str] = []

                async def read_segment_progress() -> None:
                    while True:
                        line = await process.stdout.readline()  # type: ignore
                        if not line:
                            break
                        line_str = line.decode('utf-8', errors='ignore').strip()
                        if line_str.startswith('frame='):
                            try:
                                current_frames = int(line_str.split('=')[1])
                                progress = ((processed_frames + min(current_frames, segment_frames)) / total_clip_frames) * 100
                                progress = min(progress, 97.0)
                                _clip_export_tasks[task_id].progress = progress
                                _clip_export_tasks[task_id].detail = f'Processing segment {index}/{len(segments)}: {progress:.1f}%'
                            except Exception:
                                pass

                async def read_segment_stderr() -> None:
                    while True:
                        line = await process.stderr.readline()  # type: ignore
                        if not line:
                            break
                        stderr_output.append(line.decode('utf-8', errors='ignore'))

                await asyncio.gather(read_segment_progress(), read_segment_stderr())

                await process.wait()

                if process.returncode != 0:
                    stderr_full = ''.join(stderr_output)
                    _clip_export_tasks[task_id].status = 'Failed'
                    _clip_export_tasks[task_id].detail = f'FFmpeg segment export failed with return code {process.returncode}'
                    logging.error(
                        f'[ExecuteClipExport] Segment export failed. '
                        f'[task_id: {task_id}, segment_index: {index}, return_code: {process.returncode}, stderr: {stderr_full}]'
                    )
                    return

                processed_frames += segment_frames

            concat_list_path = temp_dir / 'segments.txt'
            with concat_list_path.open('w', encoding='utf-8') as concat_file:
                for segment_file in segment_files:
                    concat_file.write(f"file '{segment_file.as_posix()}'\n")

            _clip_export_tasks[task_id].progress = min(_clip_export_tasks[task_id].progress + 1.0, 98.0)
            _clip_export_tasks[task_id].detail = 'Combining segments...'

            cmd = [
                ffmpeg_path,
                '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path.as_posix(),
                '-c:v', 'copy',  # 映像はコピー
                '-c:a', 'aac',  # 音声はAACに再エンコード
                '-b:a', '128k',
                '-map_metadata', '0',  # 元のメタデータを保持
                '-aspect', aspect_ratio,  # アスペクト比を明示的に設定
                '-movflags', '+faststart',
                '-f', 'mp4',  # MP4形式を明示的に指定
                output_path,
            ]

            logging.info(f'[ExecuteClipExport] Combining segments. [task_id: {task_id}, command: {" ".join(cmd)}]')

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE,
            )

            stderr_output = []
            while True:
                line = await process.stderr.readline()  # type: ignore[arg-type]
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore')
                stderr_output.append(line_str)

            await process.wait()

            if process.returncode != 0:
                stderr_full = ''.join(stderr_output)
                _clip_export_tasks[task_id].status = 'Failed'
                _clip_export_tasks[task_id].detail = f'FFmpeg concat failed with return code {process.returncode}'
                logging.error(
                    f'[ExecuteClipExport] Segment combine failed. '
                    f'[task_id: {task_id}, return_code: {process.returncode}, stderr: {stderr_full}]'
                )
                return

        output_file_path = PathLib(output_path)
        output_file_size = output_file_path.stat().st_size

        file_hash_md5 = hashlib.md5()
        with open(output_path, 'rb') as file_handle:
            for chunk in iter(lambda: file_handle.read(8192), b''):
                file_hash_md5.update(chunk)
        file_hash = file_hash_md5.hexdigest()

        _clip_export_tasks[task_id].status = 'Completed'
        _clip_export_tasks[task_id].progress = 100.0
        _clip_export_tasks[task_id].detail = 'Clip export completed successfully'
        _clip_export_tasks[task_id].output_file_path = output_path
        _clip_export_tasks[task_id].output_file_size = output_file_size
        _clip_export_tasks[task_id].file_hash = file_hash
        _clip_export_tasks[task_id].recorded_video_id = recorded_video_id
        _clip_export_tasks[task_id].recorded_program_title = recorded_program_title
        _clip_export_tasks[task_id].duration = total_clip_duration
        logging.info(f'[ExecuteClipExport] Clip export completed successfully. [task_id: {task_id}, output_path: {output_path}, size: {output_file_size}]')

    except Exception as ex:
        _clip_export_tasks[task_id].status = 'Failed'
        _clip_export_tasks[task_id].detail = f'Exception occurred: {ex!s}'
        logging.error(f'[ExecuteClipExport] Clip export failed with exception. [task_id: {task_id}, exception: {ex}]')

    finally:
        if temp_dir is not None and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

