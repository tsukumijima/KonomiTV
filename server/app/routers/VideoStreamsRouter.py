
import asyncio
import hashlib
import json
import struct
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Literal

import anyio
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from starlette.types import Receive, Scope, Send

from app import logging
from app.config import Config
from app.constants import QUALITY
from app.models.RecordedProgram import RecordedProgram
from app.schemas import OfflineVideoStreamMetadata
from app.streams.OfflineVideoDownload import OfflineVideoDownload
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

    # 指定された画質が "original" の場合、HLS プレイリストではオリジナル画質で配信できないのでエラーにする
    if stream_quality.quality == 'original':
        logging.error(f'[VideoStreamsRouter][ValidateQuality] Original quality is not available for HLS playlist. [quality: {quality}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Original quality is not available for HLS playlist',
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
    playlist_type: Annotated[
        Literal['master', 'primary-audio', 'secondary-audio'],
        Query(alias='type', description='プレイリストの種類。'),
    ] = 'primary-audio',
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS M3U8 プレイリストを返す。<br>
    この M3U8 プレイリストは仮想的なもので、すべてのセグメントデータがエンコード済みとは限らない。セグメントはリクエストされ次第随時生成される。
    """

    # 品質とオプション指定に対応する録画視聴セッションを作成または取得
    assert stream_quality.quality != 'original'
    video_stream = VideoStream(
        session_id,
        recorded_program,
        stream_quality.quality,
        stream_quality.encoding_options,
        is_new_session_allowed = True,
    )

    # 映像・主音声と副音声は同じエンコード結果を共有し、プレイリストの種類だけをこの API で切り替える
    if playlist_type == 'master':
        # MPEG-TS の多重化オーバーヘッドを10%見込み、最大映像と2本分の音声を収容できる帯域幅を宣言する
        quality = QUALITY[stream_quality.quality]
        video_bitrate = int(quality.video_bitrate_max.removesuffix('K')) * 1000
        audio_bitrate = int(quality.audio_bitrate.removesuffix('K')) * 1000
        bandwidth = round((video_bitrate + audio_bitrate * 2) * 1.1)
        playlist_uri = f'playlist?session_id={session_id}'

        # tsreadex は副音声のない区間も無音 AAC で補完するため、番組情報に関係なく常に2本の音声トラックを公開する
        ## 編成の途中から副音声が始まる場合も、利用者の選択を維持したまま再生できる
        playlist = '#EXTM3U\n#EXT-X-VERSION:6\n'
        playlist += '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="主音声",DEFAULT=YES,AUTOSELECT=YES,LANGUAGE="jpn"\n'
        playlist += f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="副音声",DEFAULT=NO,AUTOSELECT=YES,LANGUAGE="jpn",URI="{playlist_uri}&type=secondary-audio"\n'
        playlist += f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},AUDIO="audio"\n'
        playlist += f'{playlist_uri}&type=primary-audio\n'
    else:
        audio = 'secondary' if playlist_type == 'secondary-audio' else 'primary'
        playlist = video_stream.getVirtualPlaylist(cache_key, audio)
    return Response(
        content = playlist,
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
    audio: Annotated[Literal['primary', 'secondary'], Query(description='音声トラック。')] = 'primary',
):
    """
    指定された画質に対応する、録画番組のストリーミング用 HLS セグメントを返す。<br>
    呼び出された時点でエンコードされていない場合は既存のエンコードタスクが終了され、<br>
    sequence の HLS セグメントが含まれる範囲から新たにエンコードタスクが開始される。
    """

    # 品質とオプション指定に対応する録画視聴セッションを取得
    assert stream_quality.quality != 'original'
    video_stream = VideoStream(session_id, recorded_program, stream_quality.quality, stream_quality.encoding_options)

    # セグメントを取得（キャッシュキーはブラウザキャッシュ避けのための ID なので特に使わない）
    try:
        segment_data = await video_stream.getSegment(sequence, audio)
    except ValueError as ex:
        logging.error(f'{video_stream.log_prefix} Failed to get segment. [sequence: {sequence}, audio: {audio}]', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = f'Failed to get segment. [audio: {audio}]',
        ) from ex
    # エンコードや入力位置の解決に失敗した場合は、再生クライアントへ原因を区別できるレスポンスを返す
    except RuntimeError as ex:
        logging.error(f'{video_stream.log_prefix} Failed to generate segment. [sequence: {sequence}, audio: {audio}]', exc_info=ex)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f'Failed to generate segment. [audio: {audio}]',
        ) from ex
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
    assert stream_quality.quality != 'original'
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
    assert stream_quality.quality != 'original'
    video_stream = VideoStream(session_id, recorded_program, stream_quality.quality, stream_quality.encoding_options)

    # セッションのアクティブ状態を維持する
    video_stream.keepAlive()


@router.get(
    '/{video_id}/{quality}/offline-stream',
    summary = '録画番組オフライン保存ストリーム API',
    response_class = StreamingResponse,
    responses = {
        200: {
            'description': 'オフライン保存用のメタデータと HLS セグメントを格納したバイナリストリーム。',
            'content': {'application/octet-stream': {}},
        },
        409: {'description': '録画中、または再開元の録画・変換条件が一致しない。'},
        410: {'description': '一時保存が期限切れ、削除済み、または変換が中断されたため再開できない。'},
        507: {'description': 'サーバー側の一時保存容量が不足している。'},
    },
)
async def VideoOfflineStreamAPI(
    request: Request,
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    stream_quality: Annotated[StreamQualityWithOptions, Depends(ValidateQuality)],
    quality: Annotated[str, Path(description='映像の品質。ex: 720p-hevc-10bit-24fps')],
    start_sequence: Annotated[int, Query(ge=0, description='保存済みセグメントの次の番号。')] = 0,
    resume_token: Annotated[str | None, Query(max_length=64, description='前回の応答に含まれる再開用識別子。')] = None,
    resumable: Annotated[bool, Query(description='変換結果をサーバーに一時保存して、通信切断後の再開を可能にする。')] = False,
    download_id: Annotated[str | None, Query(pattern=r'^[0-9a-f]{32}$', description='通常保存の一時保存 ID。新規保存では省略時に生成する。')] = None,
) -> StreamingResponse:
    """
    録画番組を指定画質でエンコードし、オフライン保存用の単一ストリームとして返す。<br>
    通常保存の再開では、同じエンコード結果の未保存セグメントだけを送信する。<br>
    応答は KTVODLP ヘッダー、長さ付き JSON、長さ付き MPEG-TS セグメント、終端レコードの順に格納される。

    Args:
        request (Request): 順番待ちや一時保存の作成中に発生した切断を検出するリクエスト
        recorded_program (RecordedProgram): 存在確認済みの録画番組と録画ファイル情報
        stream_quality (StreamQualityWithOptions): 検証済みの画質と変換オプション
        quality (str): 追加オプションを含む API 上の画質
        start_sequence (int): 端末へ保存済みの連続セグメントの次の番号
        resume_token (str | None): 再開元の録画ファイルと変換条件を照合する識別子
        resumable (bool): 通信切断後も変換結果を一時保存し、再開できるようにするか
        download_id (str | None): 一時保存の識別子。新規保存で省略した場合は生成する
    Returns:
        StreamingResponse: 指定位置以降のオフライン保存データを順次返す応答
    """

    # 追いかけ再生中のファイルは終端とハッシュが変化するため、録画完了後だけ保存を許可する
    recorded_video = recorded_program.recorded_video
    if recorded_video.status == 'Recording':
        logging.error(f'[VideoOfflineStreamAPI] Recording video cannot be saved for offline playback. [video_id: {recorded_program.id}]')
        raise HTTPException(409, 'Recording video cannot be saved for offline playback')
    assert stream_quality.quality != 'original'

    # 実ファイルのサイズ・更新時刻も照合し、DB の部分ハッシュが古いままでも別データを継ぎ足さない
    try:
        file_stat = await anyio.Path(recorded_video.file_path).stat()
    except FileNotFoundError as ex:
        raise HTTPException(404, 'Recorded file was not found') from ex
    current_token = hashlib.sha256(json.dumps([
        1, recorded_video.file_hash, file_stat.st_size, file_stat.st_mtime_ns,
        recorded_video.duration, recorded_video.video_frame_rate,
        recorded_video.video_scan_type, recorded_video.video_resolution_width, recorded_video.video_resolution_height,
        recorded_video.video_codec, recorded_video.has_video_stream_changes,
        quality, Config().general.encoder, QUALITY[stream_quality.quality].model_dump(),
        stream_quality.encoding_options.buildSuffix(),
    ], sort_keys=True).encode('utf-8')).hexdigest()
    if resume_token is not None and resume_token != current_token:
        raise HTTPException(409, 'Offline source or encoding settings changed')
    if start_sequence > 0 and (not resumable or resume_token is None or download_id is None):
        raise HTTPException(409, 'Offline resume identity is missing')

    cached_download: OfflineVideoDownload | None = None
    video_stream: VideoStream | None = None
    owns_encoder_slot = False
    try:
        if resumable and resume_token is not None:
            if download_id is None:
                raise HTTPException(422, 'Offline download ID is required')
            # 再送にエンコーダーの空きを待つ必要はない。サーバー再起動後も完成済みの一時保存は読み出せる
            cached_download = await OfflineVideoDownload.open(download_id, current_token, recorded_program.id, quality)
            metadata = cached_download.manifest.metadata.model_copy(deep=True)
            metadata.start_sequence = start_sequence
            if start_sequence > metadata.segment_count:
                raise HTTPException(422, 'Invalid offline start sequence')
        else:
            # 待機中のリクエストは HTTP 応答を開始せず、クライアント側で Waiting と表示できる状態を維持する
            await OFFLINE_VIDEO_STREAM_SEMAPHORE.acquire()
            owns_encoder_slot = True
            # 順番待ち中に取り消された保存を、切断後に新規作成しない
            if await request.is_disconnected():
                raise HTTPException(499, 'Offline download request was disconnected')
            # 通常再生とは独立したセッションを作り、仮想プレイリスト生成によって全セグメント情報を初期化する
            video_stream = VideoStream(
                f'offline-{uuid.uuid4().hex}', recorded_program, stream_quality.quality,
                stream_quality.encoding_options, is_new_session_allowed=True,
            )
            video_stream.getVirtualPlaylist()
            # Pydantic を通して、クライアントへ渡す JSON の型とフィールドを固定する
            metadata = OfflineVideoStreamMetadata(
                video_id=recorded_program.id, file_hash=recorded_video.file_hash, quality=quality,
                duration_seconds=recorded_video.duration, resume_version=1 if resumable else None,
                resume_token=current_token, start_sequence=0, segment_count=len(video_stream.segments),
                download_id=(download_id or uuid.uuid4().hex) if resumable else None,
            )
            if resumable:
                cached_download = await OfflineVideoDownload.create(video_stream, metadata, OFFLINE_VIDEO_STREAM_SEMAPHORE)
                # 以降は生成タスクがセッションと変換枠を所有し、HTTP 切断では破棄しない
                owns_encoder_slot = False
                video_stream = None
                # 作成待ちの間にキャンセルの DELETE が空振りした場合も、応答前の切断なら一時保存を回収する
                if await request.is_disconnected():
                    with anyio.CancelScope(shield=True):
                        await OfflineVideoDownload.delete(cached_download.download_id, recorded_program.id, quality)
                    raise HTTPException(499, 'Offline download request was disconnected')
    except BaseException:
        # StreamingResponse を返す前の失敗ではジェネレーターの finally が動かないため、ここで実行枠を返す
        if cached_download is not None:
            cached_download.release()
        try:
            if video_stream is not None:
                await video_stream.destroy()
        finally:
            if owns_encoder_slot:
                OFFLINE_VIDEO_STREAM_SEMAPHORE.release()
        raise

    async def GenerateOfflineVideoStream() -> AsyncGenerator[bytes]:
        """
        従来と同じフレーミングで、初回は変換結果を順次送り、再開時は同じバイト列を再送する。

        Args:
            None
        Returns:
            AsyncGenerator[bytes]: ヘッダー、メタデータ、セグメント、終端レコードの順に返す非同期ジェネレーター
        """
        # 長い1セグメントのエンコード中も10秒のセッションタイムアウトを迎えないよう、視聴画面と同じ周期で維持する
        async def KeepVideoStreamAlive() -> None:
            """
            ダウンロード中の録画視聴セッションを維持する。

            Args:
                None
            Returns:
                None
            """
            while True:
                if video_stream is not None:
                    video_stream.keepAlive()
                await asyncio.sleep(5)

        keep_alive = asyncio.create_task(KeepVideoStreamAlive()) if video_stream is not None else None
        try:
            encoded_metadata = metadata.model_dump_json().encode('utf-8')
            # 固定マジック値とメタデータ長により、任意のネットワーク分割位置から同じ規則で復元できる
            yield b'KTVODLP\n'
            yield struct.pack('>I', len(encoded_metadata))
            yield encoded_metadata
            # VideoStream が連続生成したセグメントを順番どおり読み、各データを独立して CacheStorage へ格納できる単位にする
            for sequence in range(start_sequence, metadata.segment_count):
                if cached_download is not None:
                    segment, data = await cached_download.getSegment(sequence)
                    duration = segment.duration_milliseconds
                else:
                    assert video_stream is not None
                    data = await video_stream.getSegment(sequence)
                    duration = max(1, round(video_stream.segments[sequence].duration_seconds * 1000))
                if not data:
                    logging.error(f'[VideoOfflineStreamAPI] Offline segment generation failed. [sequence: {sequence}]')
                    raise RuntimeError(f'Offline segment generation failed. [sequence: {sequence}]')
                yield struct.pack('>III', sequence, duration, len(data))
                yield data
            # 終端レコードには件数を格納し、通信切断による末尾欠落をクライアント側で検出できるようにする
            yield struct.pack('>II', 0xffffffff, metadata.segment_count)
        finally:
            if keep_alive is not None:
                keep_alive.cancel()
                await asyncio.gather(keep_alive, return_exceptions=True)

    stream_generator = GenerateOfflineVideoStream()

    class OfflineStreamingResponse(StreamingResponse):
        """送信エラーや応答開始前の切断でも、一時保存の読み取り権と応答ジェネレーターを解放する。"""

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            """
            応答を送信し、送信エラーや切断が発生した場合も所有するリソースを解放する。

            Args:
                scope (Scope): ASGI のリクエスト情報
                receive (Receive): リクエスト受信関数
                send (Send): 応答送信関数
            Returns:
                None
            """
            try:
                await super().__call__(scope, receive, send)
            finally:
                # 送信失敗時には BackgroundTask が呼ばれないため、応答全体の finally で確実に解放する
                with anyio.CancelScope(shield=True):  # ASGI の切断通知によるキャンセル中も、解放処理自体は最後まで実行する
                    try:
                        await stream_generator.aclose()
                    finally:
                        if cached_download is not None:
                            cached_download.release()
                        elif video_stream is not None:
                            try:
                                await video_stream.destroy()
                            finally:
                                OFFLINE_VIDEO_STREAM_SEMAPHORE.release()

    return OfflineStreamingResponse(
        stream_generator, media_type='application/octet-stream',
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
    )


@router.delete('/{video_id}/{quality}/offline-stream', summary='録画番組オフライン一時保存削除 API', status_code=204)
async def VideoOfflineStreamDeleteAPI(
    recorded_program: Annotated[RecordedProgram, Depends(ValidateVideoID)],
    quality: Annotated[str, Path(description='保存時の画質。')],
    download_id: Annotated[str, Query(pattern=r'^[0-9a-f]{32}$', description='キャンセル・完了した通常保存の一時保存 ID。')],
) -> None:
    """
    指定した一時保存の生成を停止し、サーバー側の一時データを削除する。

    Args:
        recorded_program (RecordedProgram): 存在確認済みの録画番組
        quality (str): 一時保存を作成したときの API 上の画質
        download_id (str): キャンセルまたは保存完了により削除する一時保存の識別子
    Returns:
        None
    """
    await OfflineVideoDownload.delete(download_id, recorded_program.id, quality)
