
import threading
import time
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Path
from fastapi import status
from fastapi.responses import Response
from fastapi.responses import StreamingResponse

from app.constants import CONFIG
from app.constants import LIVESTREAM_QUALITY
from app.models import Channels
from app.tasks import LiveEncodingTask
from app.utils import LiveStream


# ルーター
router = APIRouter(
    tags=['Streams'],
    prefix='/api/streams',
)


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
    # 実装中につきダミー
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

    # ライブストリームが存在しない場合、バックグラウンドでエンコードタスクを作成・実行する
    if f'{channel_id}-{quality}' not in LiveStream.livestream:

        # エンコードタスクを非同期で実行
        def run():
            instance = LiveEncodingTask()
            instance.run(channel_id, quality, CONFIG['preferred_encoder'])
        thread = threading.Thread(target=run)
        thread.start()

        # ライブストリームが作成されるまで待機
        while f'{channel_id}-{quality}' not in LiveStream.livestream:
            time.sleep(0.01)


    # ***** ライブストリームの読み取り・出力 *****

    # ライブストリームに接続し、クライアント ID を取得する
    livestream = LiveStream(channel_id, quality)
    client_id = livestream.connect()

    def read():
        """ライブストリームを出力するジェネレーター
        """
        while True:

            # ライブストリームが存在する
            if livestream.livestream_id is not None:

                # 登録した Queue から受信したストリームデータ
                stream_data = livestream.read(client_id)

                # ストリームデータが存在する
                if stream_data is not None:

                    # Queue から取得したストリームデータを yield で返す
                    yield stream_data

                # stream_data に None が入った場合はエンコードタスクが終了したものとみなす
                else:
                    break

            # ライブストリームが終了されたのでループを抜ける
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
    return StreamingResponse(read(), media_type='video/mp2t')
