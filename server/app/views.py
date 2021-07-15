
import copy
import threading
from django.conf import settings
from django.http.response import StreamingHttpResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps import AppConfig
from app.tasks import LiveEncodingTask
from app.utils import NamedPipeClient


class LiveStreamAPI(APIView):

    def post(self, request:Request, livestream_id:str) -> Response:

        # エンコーダー
        encoder_type = 'ffmpeg'

        # 音声タイプ
        audio_type = 'normal'

        # タスクを非同期で実行
        def run():
            instance = LiveEncodingTask()
            instance.run(livestream_id, encoder_type=encoder_type, audio_type=audio_type)
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

        # パイプに接続
        #pipe_client = NamedPipeClient(livestream_id)
        #result = pipe_client.connect()

        # 接続できたなら
        if livestream_id in AppConfig.livestream:

            def read():
                """名前付きパイプから出力を読み取るジェネレーター
                """
                last_data = bytes()
                while True:

                    if livestream_id in AppConfig.livestream:
                        data = copy.copy(AppConfig.livestream[livestream_id])
                        if last_data != data:
                            last_data = copy.copy(data)
                            yield data
                    else:
                        break

                    # # パイプが開かれている間
                    # if pipe_client.pipe_handle is not None:

                    #     # 名前付きパイプを読み取る
                    #     data = pipe_client.read()

                    #     # 読み取り失敗
                    #     if data is False:
                    #         pipe_client.close()  # 名前付きパイプを閉じる
                    #         break

                    #     # 読み取ったデータを yield で返す
                    #     yield data

                    # # パイプが閉じられているので終了
                    # else:
                    #     break

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
