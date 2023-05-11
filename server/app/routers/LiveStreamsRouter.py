
import asyncio
import copy
import json
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import status
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from typing import cast

from app import schemas
from app.constants import QUALITY, QUALITY_TYPES
from app.models import Channel
from app.models import LiveStream
from app.models import LiveStreamClient
from app.utils import Logging


# ルーター
router = APIRouter(
    tags = ['Streams'],
    prefix = '/api/streams/live',
)


# チャンネル ID のバリデーション
async def ValidateChannelID(channel_id: str = Path(..., description='チャンネル ID 。ex:gr011')) -> str:
    if await Channel.filter(channel_id=channel_id).get_or_none() is None:
        Logging.error(f'[LiveStreamsRouter][ValidateChannelID] Specified channel_id was not found [channel_id: {channel_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified channel_id was not found',
        )
    return channel_id

# 品質のバリデーション
async def ValidateQuality(quality: str = Path(..., description='映像の品質。ex:1080p')) -> QUALITY_TYPES:
    if quality not in QUALITY:
        Logging.error(f'[LiveStreamsRouter][ValidateQuality] Specified quality was not found [quality: {quality}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified quality was not found',
        )
    return quality

# クライアント ID からライブストリームクライアントのインスタンスを取得する
async def GetLiveStreamClient(
    channel_id: str = Depends(ValidateChannelID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
    client_id: str = Path(..., description='ライブストリームのクライアント ID 。'),
) -> LiveStreamClient:

    # 既に接続済みのクライアントのインスタンスを取得
    livestream = LiveStream(channel_id, quality)
    livestream_client = livestream.connectToExistingClient(client_id)

    # 指定されたクライアント ID が存在しない
    if livestream_client is None:
        Logging.error(f'[LiveStreamsRouter][GetLiveStreamClient] Specified client_id was not found [client_id: {client_id}]')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified client_id was not found',
        )

    return livestream_client


@router.get(
    '',
    summary = 'ライブストリーム一覧 API',
    response_description = 'ステータスごとに分類された、すべてのライブストリームの状態。',
    response_model = schemas.LiveStreams,
)
async def LiveStreamsAPI():
    """
    すべてのライブストリームの状態を Offline・Standby・ONAir・Idling・Restart の各ステータスごとに取得する。
    """

    # 返却するデータ
    # 逆順になっているのは、デバッグ時に全体の大半を占める Offline なストリームが邪魔なため
    result = {
        'Restart': {},
        'Idling' : {},
        'ONAir'  : {},
        'Standby': {},
        'Offline': {},
    }

    # すべてのストリームごとに
    for livestream in LiveStream.getAllLiveStreams():
        livestream_status = livestream.getStatus()
        result[livestream_status['status']][livestream.livestream_id] = livestream_status

    # すべてのライブストリームの状態を返す
    return result


@router.get(
    '/{channel_id}/{quality}',
    summary = 'ライブストリーム API',
    response_description = 'ライブストリームの状態。',
    response_model = schemas.LiveStream,
)
async def LiveStreamAPI(
    channel_id: str = Depends(ValidateChannelID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    """
    ライブストリームの状態を取得する。<br>
    ライブストリーム イベント API にて配信されるイベントと同一のデータだが、一回限りの取得である点が異なる。
    """

    # ライブストリームを取得
    # ステータスを取得したいだけなので、接続はしない
    livestream = LiveStream(channel_id, quality)

    # 取得してきた値をそのまま返す
    return livestream.getStatus()


@router.get(
    '/{channel_id}/{quality}/events',
    summary = 'ライブストリーム イベント API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブストリームのイベントが随時配信されるイベントストリーム。',
            'content': {'text/event-stream': {}},
        }
    }
)
async def LiveStreamEventAPI(
    channel_id: str = Depends(ValidateChannelID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    """
    ライブストリームのイベントを Server-Sent Events で随時配信する。

    イベントには、

    - 初回接続時に現在のステータスを示す **initial_update**
    - ステータスの更新を示す **status_update**
    - ステータス詳細の更新を示す **detail_update**
    - クライアント数の更新を示す **clients_update**

    の4種類がある。

    どのイベントでも配信される JSON 構造は同じ。<br>
    ステータスが Offline になった、あるいは既にそうなっている時は、status_update イベントが配信された後に接続を終了する。
    """

    # ライブストリームを取得
    # ステータスを取得したいだけなので、接続はしない
    livestream = LiveStream(channel_id, quality)

    # ステータスの変更を監視し、変更があればステータスをイベントストリームとして出力する
    async def generator():
        """イベントストリームを出力するジェネレーター"""

        # 初期値
        previous_status = livestream.getStatus()

        # 取得できたクライアント数はあくまで同じチャンネル+同じ画質で視聴中のクライアントをカウントしたものなので、
        # 同じチャンネル+すべての画質で視聴中のクライアント数を別途取得して上書きする
        previous_status['clients_count'] = LiveStream.getViewerCount(channel_id)

        # 初回接続時に必ず現在のステータスを返す
        yield {
            'event': 'initial_update',  # initial_update イベントを設定
            'data': json.dumps(previous_status, ensure_ascii=False),
        }

        while True:

            # 現在のライブストリームのステータスを取得
            status = livestream.getStatus()

            # 取得できたクライアント数はあくまで同じチャンネル+同じ画質で視聴中のクライアントをカウントしたものなので、
            # 同じチャンネル+すべての画質で視聴中のクライアント数を別途取得して上書きする
            status['clients_count'] = LiveStream.getViewerCount(channel_id)

            # 以前の結果と異なっている場合のみレスポンスを返す
            if previous_status != status:

                # ステータスが以前と異なる
                if previous_status['status'] != status['status']:
                    yield {
                        'event': 'status_update',  # status_update イベントを設定
                        'data': json.dumps(status, ensure_ascii=False),
                    }
                # 詳細が以前と異なる
                elif previous_status['detail'] != status['detail']:
                    yield {
                        'event': 'detail_update',  # detail_update イベントを設定
                        'data': json.dumps(status, ensure_ascii=False),
                    }
                # クライアント数が以前と異なる
                elif previous_status['clients_count'] != status['clients_count']:
                    yield {
                        'event': 'clients_update',  # clients_update イベントを設定
                        'data': json.dumps(status, ensure_ascii=False),
                    }

                # 取得結果を保存
                previous_status = copy.copy(status)

            # 一応スリープを入れておく
            await asyncio.sleep(0.05)

    # EventSourceResponse でイベントストリームを配信する
    return EventSourceResponse(generator())


# ***** MPEG-TS ストリーミング API *****


@router.get(
    '/{channel_id}/{quality}/mpegts',
    summary = 'ライブ MPEGTS ストリーム API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブ MPEGTS ストリーム。',
            'content': {'video/mp2t': {}},
        }
    }
)
async def LiveMPEGTSStreamAPI(
    request: Request,
    channel_id: str = Depends(ValidateChannelID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    """
    ライブ MPEGTS ストリームを配信する。

    同じチャンネル ID 、同じ画質のライブストリームが Offline 状態のときは、新たにエンコードタスクを立ち上げて、
    ONAir 状態になるのを待機してからストリームデータを配信する。<br>
    同じチャンネル ID 、同じ画質のライブストリームが ONAir や Idling 状態のときは、新たにエンコードタスクを立ち上げることなく、他のクライアントとストリームデータを共有して配信する。

    何らかの理由でライブストリームが終了しない限り、継続的にレスポンスが出力される（ストリーミング）。
    """

    # ライブストリームに接続し、ライブストリームクライアントを取得する
    ## 接続時に Offline だった場合は自動的にエンコードタスクが起動される
    livestream = LiveStream(channel_id, quality)
    livestream_client = await livestream.connect('mpegts')

    # ライブストリームを出力するジェネレーター
    async def generator():
        while True:

            # リクエストがキャンセル（切断）されている場合
            ## エンコードに失敗とかしない限り基本エンドレスで配信されるので、
            ## チャンネル変えたりやタブの再読み込みで必然的にリクエストがキャンセルされる
            if await request.is_disconnected():

                # ライブストリームへの接続を切断し、ループを終了する
                Logging.debug_simple('[LiveStreamsRouter][LiveMPEGTSStreamAPI] Request is disconnected')
                livestream.disconnect(livestream_client)
                break

            if livestream.getStatus()['status'] != 'Offline':

                # クライアントが持つ Queue から読み取ったストリームデータ
                stream_data: bytes | None = await livestream_client.readStreamData()

                # 読み取ったストリームデータを yield で随時出力する
                if stream_data is not None:
                    yield stream_data

                # stream_data に None が入った場合はエンコードタスクが終了し、接続が切断されたものとみなす
                else:

                    # ライブストリームへの接続を切断し、ループを終了する
                    Logging.debug_simple('[LiveStreamsRouter][LiveMPEGTSStreamAPI] Encode task is finished')
                    livestream.disconnect(livestream_client)  # 必要ないとは思うけど念のため
                    break

            # ライブストリームが Offline になった場合もエンコードタスクが終了し、接続が切断されたものとみなす
            else:

                # ライブストリームへの接続を切断し、ループを終了する
                Logging.debug_simple('[LiveStreamsRouter][LiveMPEGTSStreamAPI] LiveStream is currently Offline')
                livestream.disconnect(livestream_client)  # 必要ないとは思うけど念のため
                break

    # StreamingResponse で読み取ったストリームデータをストリーミングする
    response = StreamingResponse(generator(), media_type='video/mp2t')

    # HTTP リクエストがキャンセルされたときに自前でライブストリームの接続を切断できるよう、StreamingResponse のインスタンスにモンキーパッチを当てる
    ## StreamingResponse はリクエストがキャンセルされるとレスポンスを生成するジェネレーターの実行自体を勝手に強制終了してしまう
    ## そうするとリクエストがキャンセルされたか判定できず、クライアントがタイムアウトするまで接続切断がライブストリームに反映されない
    ## これを避けるため StreamingResponse.listen_for_disconnect() を書き換えて、自前でライブストリームの接続を切断できるようにする
    # ref: https://github.com/encode/starlette/pull/839
    from starlette.types import Receive
    async def listen_for_disconnect_monkeypatch(receive: Receive) -> None:
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                # 上のループでライブストリームへの接続を切断できるようにしばらく待つ
                await asyncio.sleep(5)
                break
    response.listen_for_disconnect = listen_for_disconnect_monkeypatch

    return response


# ***** LL-HLS ストリーミング開始/終了 API *****


@router.post(
    '/{channel_id}/{quality}/ll-hls',
    summary = 'ライブ LL-HLS クライアント接続 API',
    response_description = 'ライブストリームのクライアント ID。',
    response_model = schemas.LiveStreamLLHLSClientID,
)
async def LiveLLHLSClientConnectAPI(
    channel_id: str = Depends(ValidateChannelID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    # ライブストリームに接続し、クライアントのインスタンスを取得
    livestream = LiveStream(channel_id, quality)
    livestream_client = await livestream.connect('ll-hls')

    # クライアント ID を返す
    return {'client_id': livestream_client.client_id}


@router.delete(
    '/{channel_id}/{quality}/ll-hls/{client_id}',
    summary = 'ライブ LL-HLS クライアント接続切断 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def LiveLLHLSClientDisconnectAPI(
    channel_id: str = Depends(ValidateChannelID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
):
    # ライブストリームへの接続を切断する
    livestream = LiveStream(channel_id, quality)
    livestream.disconnect(livestream_client)


# ***** LL-HLS ストリーミング API (主音声) *****


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/primary-audio/playlist.m3u8',
    summary = 'ライブ LL-HLS M3U8 プレイリスト API (主音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS の M3U8 プレイリスト。',
            'content': {'application/vnd.apple.mpegurl': {}},
        }
    }
)
async def LiveLLHLSPrimaryAudioPlaylistAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
    _HLS_msn: int | None = Query(None, description='LL-HLS プレイリストの msn (Media Sequence Number) インデックス。'),
    _HLS_part: int | None = Query(None, description='LL-HLS プレイリストの part (部分セグメント) インデックス。'),
):
    # クライアントから LL-HLS プレイリストのレスポンスを取得してそのまま返す
    return await livestream_client.getPlaylist(_HLS_msn, _HLS_part, secondary_audio=False)


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/primary-audio/segment',
    summary = 'ライブ LL-HLS セグメントデータ API (主音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS のセグメントデータ (m4s) 。',
            'content': {'video/mp4': {}},
        }
    }
)
async def LiveLLHLSPrimaryAudioSegmentAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
    msn: int | None = Query(None, description='LL-HLS セグメントの msn (Media Sequence Number) インデックス。'),
):
    # クライアントから LL-HLS セグメントデータのレスポンスを取得してそのまま返す
    return await livestream_client.getSegment(msn, secondary_audio=False)


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/primary-audio/part',
    summary = 'ライブ LL-HLS 部分セグメントデータ API (主音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS の部分セグメントデータ (m4s) 。',
            'content': {'video/mp4': {}},
        }
    }
)
async def LiveLLHLSPrimaryAudioPartialSegmentAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
    msn: int | None = Query(None, description='LL-HLS セグメントの msn (Media Sequence Number) インデックス。'),
    part: int | str | None = Query(None, description='LL-HLS セグメントの part (部分セグメント) インデックス。'),
):
    # part が空文字列の場合は 0 に変換する
    if part == '':
        part = 0
    part = cast(int | None, part)

    # クライアントから LL-HLS 部分セグメントデータのレスポンスを取得してそのまま返す
    return await livestream_client.getPartialSegment(msn, part, secondary_audio=False)


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/primary-audio/init',
    summary = 'ライブ LL-HLS 初期セグメントデータ API (主音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS の初期セグメントデータ (m4s) 。',
            'content': {'video/mp4': {}},
        }
    }
)
async def LiveLLHLSPrimaryAudioInitializationSegmentAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
):
    # クライアントから LL-HLS 初期セグメントデータのレスポンスを取得してそのまま返す
    return await livestream_client.getInitializationSegment(secondary_audio=False)


# ***** LL-HLS ストリーミング API (副音声) *****


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/secondary-audio/playlist.m3u8',
    summary = 'ライブ LL-HLS M3U8 プレイリスト API (副音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS の M3U8 プレイリスト。',
            'content': {'application/vnd.apple.mpegurl': {}},
        }
    }
)
async def LiveLLHLSSecondaryAudioPlaylistAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
    _HLS_msn: int | None = Query(None, description='LL-HLS プレイリストの msn (Media Sequence Number) インデックス。'),
    _HLS_part: int | None = Query(None, description='LL-HLS プレイリストの part (部分セグメント) インデックス。'),
):
    # クライアントから LL-HLS プレイリストのレスポンスを取得してそのまま返す
    return await livestream_client.getPlaylist(_HLS_msn, _HLS_part, secondary_audio=True)


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/secondary-audio/segment',
    summary = 'ライブ LL-HLS セグメントデータ API (副音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS のセグメントデータ (m4s) 。',
            'content': {'video/mp4': {}},
        }
    }
)
async def LiveLLHLSSecondaryAudioSegmentAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
    msn: int | None = Query(None, description='LL-HLS セグメントの msn (Media Sequence Number) インデックス。'),
):
    # クライアントから LL-HLS セグメントデータのレスポンスを取得してそのまま返す
    return await livestream_client.getSegment(msn, secondary_audio=True)


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/secondary-audio/part',
    summary = 'ライブ LL-HLS 部分セグメントデータ API (副音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS の部分セグメントデータ (m4s) 。',
            'content': {'video/mp4': {}},
        }
    }
)
async def LiveLLHLSSecondaryAudioPartialSegmentAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
    msn: int | None = Query(None, description='LL-HLS セグメントの msn (Media Sequence Number) インデックス。'),
    part: int | str | None = Query(None, description='LL-HLS セグメントの part (部分セグメント) インデックス。'),
):
    # part が空文字列の場合は 0 に変換する
    if part == '':
        part = 0
    part = cast(int | None, part)

    # クライアントから LL-HLS 部分セグメントデータのレスポンスを取得してそのまま返す
    return await livestream_client.getPartialSegment(msn, part, secondary_audio=True)


@router.get(
    '/{channel_id}/{quality}/ll-hls/{client_id}/secondary-audio/init',
    summary = 'ライブ LL-HLS 初期セグメントデータ API (副音声)',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'LL-HLS の初期セグメントデータ (m4s) 。',
            'content': {'video/mp4': {}},
        }
    }
)
async def LiveLLHLSSecondaryAudioInitializationSegmentAPI(
    livestream_client: LiveStreamClient = Depends(GetLiveStreamClient),
):
    # クライアントから LL-HLS 初期セグメントデータのレスポンスを取得してそのまま返す
    return await livestream_client.getInitializationSegment(secondary_audio=True)
