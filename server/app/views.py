
from django.conf import settings
from django.http.request import HttpRequest
from django.http.response import HttpResponseBadRequest
from django.http.response import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from config import fifo
from app.utils import NamedPipeClient


class TestAPI(APIView):

    def get(self, request:HttpRequest):

        import datetime
        data = fifo.get()
        fifo.put(datetime.datetime.now().isoformat())

        return Response({
            'meta': {
                'code': 200,
                'message': data,
            }
        })


class LiveMPEGTSStreamAPI(APIView):

    def get(self, request:HttpRequest, livestream_id:str) -> StreamingHttpResponse:

        # パイプに接続
        pipe_client = NamedPipeClient(livestream_id)
        result = pipe_client.connect()

        # 接続できたなら
        if result is True:

            def read():
                """名前付きパイプから出力を読み取るジェネレーター
                """
                while True:

                    # パイプが開かれている間
                    if pipe_client.pipe_handle is not None:

                        # 名前付きパイプを読み取る
                        data = pipe_client.read()

                        # 読み取り失敗
                        if data is False:
                            pipe_client.close()  # 名前付きパイプを閉じる
                            break

                        # 読み取ったデータを yield で返す
                        yield data

                    # パイプが閉じられているので終了
                    else:
                        break

            # StreamingHttpResponse で名前付きパイプから読み取ったデータをストリーミング
            return StreamingHttpResponse(read(), content_type='video/mp2t')

        else:

            # 400 Error
            return Response({
                'meta': {
                    'code': 400,
                    'message': 'PIPE_CONNECT_FAILED'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
