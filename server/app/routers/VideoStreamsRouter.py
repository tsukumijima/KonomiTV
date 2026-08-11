
import asyncio
import json
import struct
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import Response, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from app import logging
from app.models.RecordedProgram import RecordedProgram
from app.schemas import OfflineVideoStreamMetadata
from app.streams.StreamEncodingOptions import (
    SplitQualityAndEncodingOptions,
    StreamQualityWithOptions,
)
from app.streams.VideoStream import VideoStream


# ルーター
router = APIRouter(
    tags = ['Streams'],
    prefix = '/api/streams/video',
)

# オフライン保存はエンコーダーを長時間占有するため、通常視聴分の余裕を残して同時実行数を制限する
OFFLINE_VIDEO_STREAM_SEMAPHORE = asyncio.Semaphore(3)


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


async def ValidateQuality(quality: Annotated[str, Path(description='映像の品質。ex: 1080p')]) -> StreamQualityWithOptions:
    """ 映像の品質のバリデーション """

    # 指定された品質が存在するか確認
    ## 品質の指定に -10bit や -24fps が付いていれば分解する
    stream_quality = SplitQualityAndEncodingOptions(quality)
    if stream_quality is None:
        logging.error(f'[VideoStreamsRouter][ValidateQuality] Specified quality was not found. [quality: {quality}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified quality was not found',
        )

    return stream_quality


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
    stream_quality: Annotated[StreamQualityWithOptions, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
    cache_key: Annotated[str | None, Query(description='キャッシュ制御用のキー。')] = None,
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS M3U8 プレイリストを返す。<br>
    この M3U8 プレイリストは仮想的なもので、すべてのセグメントデータがエンコード済みとは限らない。セグメントはリクエストされ次第随時生成される。
    """

    # 品質とオプション指定に対応する録画視聴セッションを作成または取得
    video_stream = VideoStream(
        session_id,
        recorded_program,
        stream_quality.quality,
        stream_quality.encoding_options,
        is_new_session_allowed = True,
    )

    # 仮想 HLS M3U8 プレイリストを取得
    virtual_playlist = video_stream.getVirtualPlaylist(cache_key)
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
    stream_quality: Annotated[StreamQualityWithOptions, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
    sequence: Annotated[int, Query(description='HLS セグメントの 0 スタートのシーケンス番号。')],
    cache_key: Annotated[str | None, Query(description='キャッシュ制御用のキー。')],
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS セグメントを返す。<br>
    呼び出された時点でエンコードされていない場合は既存のエンコードタスクが終了され、<br>
    sequence の HLS セグメントが含まれる範囲から新たにエンコードタスクが開始される。
    """

    # 品質とオプション指定に対応する録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, stream_quality.quality, stream_quality.encoding_options)

    # セグメントを取得（キャッシュキーはブラウザキャッシュ避けのための ID なので特に使わない）
    segment_data = await video_stream.getSegment(sequence)
    if segment_data is None:
        logging.error(
            f'{video_stream.log_prefix} Specified sequence segment was not found. '
            f'[sequence: {sequence}]'
        )
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
    stream_quality: Annotated[StreamQualityWithOptions, Depends(ValidateQuality)],
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

    # 品質とオプション指定に対応する録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, stream_quality.quality, stream_quality.encoding_options)

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
                logging.info(f'{video_stream.log_prefix} Buffer range updated. [begin: {buffer_range[0]}, end: {buffer_range[1]}]')
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
    stream_quality: Annotated[StreamQualityWithOptions, Depends(ValidateQuality)],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
):
    """
    録画番組のストリーミング用 HLS セグメントの生成を継続するための API 。<br>
    ストリーミングセッションを維持するために、この API は録画番組の視聴を続けている間、定期的に呼び出さなければならない。<br>
    この API が定期的に呼び出されなくなった場合、一定時間後にストリーミング用 HLS セグメントの生成が停止され、メモリ上のデータが破棄される。
    """

    # 品質とオプション指定に対応する録画視聴セッションを取得
    video_stream = VideoStream(session_id, recorded_program, stream_quality.quality, stream_quality.encoding_options)

    # セッションのアクティブ状態を維持する
    video_stream.keepAlive()


@router.get(
    '/{video_id}/{quality}/offline-stream',
    summary = '録画番組オフライン保存ストリーム API',
    response_class = StreamingResponse,
    responses = {
        status.HTTP_200_OK: {
            'description': 'オフライン保存用のメタデータと HLS セグメントを格納したバイナリストリーム。',
            'content': {'application/octet-stream': {}},
        },
        status.HTTP_409_CONFLICT: {
            'description': '録画中のためオフライン保存を開始できない。',
        },
    },
)
async def VideoOfflineStreamAPI(
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    stream_quality: Annotated[StreamQualityWithOptions, Depends(ValidateQuality)],
    quality: Annotated[str, Path(description='映像の品質。ex: 720p-hevc-10bit-24fps')],
) -> StreamingResponse:
    """
    録画番組を指定画質で先頭から順にエンコードし、オフライン保存用の単一ストリームとして返す。<br>
    応答は `KTVODLP` のヘッダーから始まる独自バイナリ形式で、長さ付き JSON メタデータ、長さ付き MPEG-TS セグメント、終端レコードの順に格納される。
    """

    # 追いかけ再生中のファイルは終端とハッシュが変化するため、録画完了後だけ保存を許可する
    if recorded_program.recorded_video.status == 'Recording':
        logging.error(f'[VideoOfflineStreamAPI] Recording video cannot be saved for offline playback. [video_id: {recorded_program.id}]')
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail = 'Recording video cannot be saved for offline playback',
        )

    # 待機中のリクエストは HTTP 応答を開始せず、クライアント側で Waiting と表示できる状態を維持する
    await OFFLINE_VIDEO_STREAM_SEMAPHORE.acquire()
    video_stream: VideoStream | None = None
    try:
        # 通常再生とは独立したセッションを作り、仮想プレイリスト生成によって全セグメント情報を初期化する
        session_id = f'offline-{uuid.uuid4().hex}'
        video_stream = VideoStream(
            session_id,
            recorded_program,
            stream_quality.quality,
            stream_quality.encoding_options,
            is_new_session_allowed = True,
        )
        video_stream.getVirtualPlaylist()

        # Pydantic を通して、クライアントへ渡す JSON の型とフィールドを固定する
        metadata = OfflineVideoStreamMetadata(
            video_id = recorded_program.id,
            file_hash = recorded_program.recorded_video.file_hash,
            quality = quality,
            duration_seconds = recorded_program.recorded_video.duration,
        ).model_dump_json().encode('utf-8')
    except Exception:
        # StreamingResponse を返す前の失敗ではジェネレーターの finally が動かないため、ここで実行枠を返す
        if video_stream is not None:
            await video_stream.destroy()
        OFFLINE_VIDEO_STREAM_SEMAPHORE.release()
        raise

    is_stream_cleaned_up = False

    async def CleanupOfflineVideoStream() -> None:
        """オフライン保存用ストリームと同時実行枠を解放する。"""
        nonlocal is_stream_cleaned_up
        # 応答本文の finally と StreamingResponse の終了処理から重複して呼ばれるため、最初の1回だけ解放する
        if is_stream_cleaned_up is True:
            return
        is_stream_cleaned_up = True
        await video_stream.destroy()
        OFFLINE_VIDEO_STREAM_SEMAPHORE.release()

    async def GenerateOfflineVideoStream():
        """オフライン保存用のバイナリストリームを生成する。"""

        # 長い1セグメントのエンコード中も10秒のセッションタイムアウトを迎えないよう、視聴画面と同じ周期で維持する
        async def KeepVideoStreamAlive() -> None:
            """ダウンロード中の録画視聴セッションを維持する。"""
            while True:
                await asyncio.sleep(5)
                video_stream.keepAlive()

        keep_alive_task = asyncio.create_task(KeepVideoStreamAlive())
        try:
            # 固定マジック値とメタデータ長により、任意のネットワーク分割位置から同じ規則で復元できる
            yield b'KTVODLP\n'
            yield struct.pack('>I', len(metadata))
            yield metadata

            # VideoStream が連続生成したセグメントを順番どおり読み、各データを独立して CacheStorage へ格納できる単位にする
            for segment in video_stream.segments:
                segment_data = await video_stream.getSegment(segment.sequence_index)
                if segment_data is None or len(segment_data) == 0:
                    logging.error(f'[VideoOfflineStreamAPI] Offline segment generation failed. [sequence: {segment.sequence_index}]')
                    raise RuntimeError(f'Offline segment generation failed. [sequence: {segment.sequence_index}]')
                duration_milliseconds = max(1, round(segment.duration_seconds * 1000))
                yield struct.pack('>III', segment.sequence_index, duration_milliseconds, len(segment_data))
                yield segment_data

            # 終端レコードには件数を格納し、通信切断による末尾欠落をクライアント側で検出できるようにする
            yield struct.pack('>II', 0xffffffff, len(video_stream.segments))
        finally:
            # 応答完了・切断・例外のすべてで維持タスクとエンコーダーを終了し、次の保存へ実行枠を返す
            keep_alive_task.cancel()
            await asyncio.gather(keep_alive_task, return_exceptions=True)
            await CleanupOfflineVideoStream()

    return StreamingResponse(
        GenerateOfflineVideoStream(),
        media_type = 'application/octet-stream',
        headers = {
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
        },
        # クライアントが応答開始直後に切断し、ジェネレーター本体が一度も実行されない場合も必ず解放する
        background = BackgroundTask(CleanupOfflineVideoStream),
    )
