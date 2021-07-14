
from django.http.request import HttpRequest
from django.http.response import HttpResponseBadRequest
from django.http.response import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.utils import NamedPipeUtil


class LiveMPEGTSStreamAPI(APIView):

    def get(self, request:HttpRequest, livestream_id:str) -> StreamingHttpResponse:

        # パイプに接続
        namedpipe = NamedPipeUtil(livestream_id)
        result = namedpipe.connectNamedPipe()

        # 接続できたなら
        if result is True:

            def read():
                """名前付きパイプから出力を読み取るジェネレーター
                """
                while True:
                    data = namedpipe.readNamedPipe()
                    if data is None:  # 読み取り失敗
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
