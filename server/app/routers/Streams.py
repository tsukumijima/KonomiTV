
import asyncio
import copy
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Path
from fastapi import status
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.constants import CONFIG
from app.constants import LIVESTREAM_QUALITY
from app.models import Channels
from app.utils import LiveStream


# ルーター
router = APIRouter(
    tags=['Streams'],
    prefix='/api/streams',
)


@router.get(
    '/live/{channel_id}/{quality}/events',
    summary = 'ライブストリーム イベント API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブストリームのイベントが随時配信されるイベントストリーム。',
            'content': {'text/event-stream': {}}
        }
    }
)
async def LiveStreamEventAPI(
    channel_id:str = Path(..., description='チャンネル ID 。ex:gr011'),
    quality:str = Path(..., description='映像の品質。ex:1080p'),
):
    """
    ライブストリームのイベントを Server-Sent Events で随時配信する。

    イベントには、

    - ステータスの更新を示す **status_update**
    - ステータス詳細の更新を示す **detail_update**
    - クライアント数の更新を示す **client_update**

    の3種類がある。

    どのイベントでも配信される JSON 構造は同じ。<br>
    ステータスが Offline になった、あるいは既にそうなっている時は、status_update イベントが配信された後に接続を終了する。
    """

    # ***** バリデーション *****

    # 指定されたチャンネル ID が存在しない
    if await Channels.filter(channel_id=channel_id).get_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified channel_id was not found',
        )

    # 指定された映像の品質が存在しない
    if quality not in LIVESTREAM_QUALITY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified quality was not found',
        )

    # ***** イベントの配信 *****

    # ライブストリームを取得
    # イベントを取得したいだけなので、接続はしない
    livestream = LiveStream(channel_id, quality)

    # ステータスの変更を監視し、変更があればステータスをイベントストリームとして出力する
    async def generator():
        """イベントストリームを出力するジェネレーター"""
        previous_status = livestream.getStatus()  # 初期値
        while True:

            # 現在のライブストリームのステータスを取得
            status = livestream.getStatus()

            # 取得したステータスが Offline であれば配信を停止する
            # 実際には JavaScript 側での対応が必要（自動で再接続してしまうため）
            if status['status'] == 'Offline':
                yield {
                    'event': 'status_update',  # status_update イベントを設定
                    'data': status,
                }
                break

            # 以前の結果と異なっている場合のみレスポンスを返す
            if previous_status != status:

                # ステータスが以前と異なる
                if previous_status['status'] != status['status']:
                    yield {
                        'event': 'status_update',  # status_update イベントを設定
                        'data': status,
                    }
                # 詳細が以前と異なる
                elif previous_status['detail'] != status['detail']:
                    yield {
                        'event': 'detail_update',  # detail_update イベントを設定
                        'data': status,
                    }
                # クライアント数が以前と異なる
                elif previous_status['client_count'] != status['client_count']:
                    yield {
                        'event': 'client_update',  # client_update イベントを設定
                        'data': status,
                    }

                # 取得結果を保存
                previous_status = copy.copy(status)

            # 一応スリープを入れておく
            await asyncio.sleep(0.05)

    # EventSourceResponse でイベントストリームを配信する
    return EventSourceResponse(generator())


@router.get(
    '/live/{channel_id}/{quality}/mpegts',
    summary = 'ライブ MPEGTS ストリーム API',
    response_class = Response,
    responses = {
        status.HTTP_200_OK: {
            'description': 'ライブ MPEGTS ストリーム。',
            'content': {'video/mp2t': {}}
        }
    }
)
async def LiveMPEGTSStreamAPI(
    channel_id:str = Path(..., description='チャンネル ID 。ex:gr011'),
    quality:str = Path(..., description='映像の品質。ex:1080p'),
):
    """
    ライブ MPEGTS ストリームを配信する。

    同じチャンネル ID 、同じ画質のライブストリームが Offline 状態のときは、新たにエンコードタスクを立ち上げて、
    ONAir 状態になるのを待機してからストリームデータを配信する。<br>
    同じチャンネル ID 、同じ画質のライブストリームが ONAir 状態のときは、新たにエンコードタスクを立ち上げることなく、他のクライアントとストリームデータを共有して配信する。

    何らかの理由でライブストリームが終了しない限り、継続的にレスポンスが出力される（ストリーミング）。
    """

    # ***** バリデーション *****

    # 指定されたチャンネル ID が存在しない
    if await Channels.filter(channel_id=channel_id).get_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified channel_id was not found',
        )

    # 指定された映像の品質が存在しない
    if quality not in LIVESTREAM_QUALITY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified quality was not found',
        )

    # ***** エンコードタスクの開始 *****

    # ライブストリームに接続し、クライアント ID を取得する
    # 接続時に Offline だった場合は自動的にエンコードタスクが起動される
    livestream = LiveStream(channel_id, quality)
    client_id = livestream.connect('mpegts')

    # ***** ライブストリームの読み取り・出力 *****

    def generator():
        """ライブストリームを出力するジェネレーター"""
        while True:

            # ライブストリームが Offline ではない
            if livestream.getStatus()['status'] != 'Offline':

                # 登録した Queue から受信したストリームデータ
                stream_data = livestream.read(client_id)

                # ストリームデータが存在する
                if stream_data is not None:

                    # Queue から取得したストリームデータを yield で返す
                    yield stream_data

                # stream_data に None が入った場合はエンコードタスクが終了したものとみなす
                else:
                    break

            # ライブストリームが Offline になったのでループを抜ける
            else:
                break

    # リクエストがキャンセルされたときにライブストリームへの接続を切断できるよう、モンキーパッチを当てる
    # StreamingResponse はリクエストがキャンセルされるとレスポンスを強制終了してしまう
    # そうするとリクエストがキャンセルされたか判定できないため、StreamingResponse.listen_for_disconnect() を書き換える
    # ref: https://github.com/encode/starlette/pull/839
    from starlette.types import Receive
    async def listen_for_disconnect_monkeypatch(self, receive: Receive) -> None:
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    # ライブストリームへの接続を切断する（クライアントを削除する）
                    livestream.disconnect(client_id)
                    break
    StreamingResponse.listen_for_disconnect = listen_for_disconnect_monkeypatch

    # StreamingResponse で読み取ったストリームデータをストリーミングする
    return StreamingResponse(generator(), media_type='video/mp2t')
