
import queue
import threading
import time
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import StreamingResponse

from app.tasks import LiveEncodingTask
from app.utils import LiveStream
from app.utils import Logging


# ルーター
router = APIRouter(
    tags=['Streams'],
    prefix='/api/streams/live',
)


@router.get('/{channel_id}/{quality}/mpegts', summary='ライブ MPEGTS ストリーム API')
def LiveMPEGTSStreamAPI(channel_id:str, quality:str, background_tasks: BackgroundTasks):

    # ***** バリデーション *****

    # 指定されたチャンネル ID が存在しない
    # 実装中につきダミー
    if False:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified channel_id not found',
        )

    # 指定された映像の品質が存在しない
    if quality not in LiveStream.quality:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified quality not found',
        )


    # ***** エンコードタスクの開始 *****

    # ライブストリームが存在しない場合、バックグラウンドでエンコードタスクを作成・実行する
    if f'{channel_id}-{quality}' not in LiveStream.livestream:

        # エンコードタスクを非同期で実行
        def run():
            instance = LiveEncodingTask()
            instance.run(channel_id, quality)
        thread = threading.Thread(target=run)
        thread.start()

        # ライブストリームが作成されるまで待機
        while f'{channel_id}-{quality}' not in LiveStream.livestream:
            time.sleep(0.01)


    # ***** ライブストリームの読み取り・出力 *****

    # ライブストリームに接続し、クライアント ID を取得する
    livestream = LiveStream(channel_id, quality)
    client_id = livestream.connect()

    Logging.info('LiveStream Connected.')
    Logging.info('Client ID: ' + str(client_id))

    def read():
        """ライブストリームを出力するジェネレーター
        """
        while True:

            # ライブストリームが存在する
            if livestream.livestream_id is not None:

                # 登録した Queue から受信したストリームデータ
                stream_data = livestream.read(client_id)
                #Logging.info('Read Client ID: ' + str(client_id))

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

    # StreamingResponse で名前付きパイプから読み取ったデータをストリーミング
    return StreamingResponse(read(), media_type='video/mp2t')
