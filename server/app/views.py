
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


class LiveStreamAPI(APIView):

    def post(self, request:Request, livestream_id:str) -> Response:

        # エンコーダー
        encoder_type = 'ffmpeg'

        # 音声タイプ
        audio_type = 'normal'

        # エンコードタスクを非同期で実行
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

        # エンコードしたライブストリームが存在する
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
