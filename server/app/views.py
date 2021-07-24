
import queue
import threading
import time
from django.conf import settings
from django.http.response import StreamingHttpResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps import AppConfig
from app.tasks import LiveEncodingTask


class LiveStreamAPI(APIView):

    def post(self, request:Request, livestream_id:str) -> Response:

        # エンコーダー
        encoder_type = 'ffmpeg'

        # エンコードタスクを非同期で実行
        def run():
            instance = LiveEncodingTask()
            instance.run(livestream_id, encoder_type=encoder_type)
        thread = threading.Thread(target=run)
        thread.start()

        return Response({
            'meta': {
                'code': 200,
                'message': 'Success',
                'thread': thread.is_alive(),
            }
        })


class LiveMPEGTSStreamAPI(APIView):

    def get(self, request:Request, livestream_id:str) -> StreamingHttpResponse:

        # ライブストリームが存在する
        if livestream_id in AppConfig.livestream:

            # ストリームデータが入れられる Queue を登録する
            AppConfig.livestream[livestream_id].append(queue.Queue())
            queue_index = len(AppConfig.livestream[livestream_id]) - 1  # 自分の Queue があるインデックスを取得

            def read():
                """名前付きパイプから出力を読み取るジェネレーター
                """
                while True:

                    # ライブストリームが存在する
                    if livestream_id in AppConfig.livestream:

                        # 登録した Queue から受信したストリームデータ
                        stream_data = AppConfig.livestream[livestream_id][queue_index].get()

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

            # StreamingHttpResponse で名前付きパイプから読み取ったデータをストリーミング
            return StreamingHttpResponse(read(), content_type='video/mp2t')

        else:

            # 400 Error
            return Response({
                'meta': {
                    'code': 400,
                    'message': 'LiveEncodingTask not launched'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
