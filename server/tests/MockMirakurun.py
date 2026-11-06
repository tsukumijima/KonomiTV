
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class MockMirakurun:
    """
    テストで放送のバックエンドの代わりに使う、Mirakurun の API の一部だけを返す HTTP サーバー
    サーバーの起動時のチャンネル情報と番組情報の更新が、実際の Mirakurun と同じ経路で動くようにする
    """

    # 返すチャンネル (Mirakurun の /api/services の形式)
    ## テスト用の録画ファイル (tests/fixtures/recorded/) と番組情報 (tests/fixtures/programs/) の放送局に合わせている
    SERVICES: list[dict[str, Any]] = [
        {
            'id': 3273601024,
            'serviceId': 1024,
            'networkId': 32736,
            'name': 'NHK総合1・東京',
            'type': 1,
            'remoteControlKeyId': 1,
            'channel': {'type': 'GR', 'channel': '27'},
        },
        {
            'id': 3273601025,
            'serviceId': 1025,
            'networkId': 32736,
            'name': 'NHK総合2・東京',
            'type': 1,
            'remoteControlKeyId': 1,
            'channel': {'type': 'GR', 'channel': '27'},
        },
        {
            'id': 400101,
            'serviceId': 101,
            'networkId': 4,
            'name': 'NHK BS',
            'type': 1,
            'channel': {'type': 'BS', 'channel': 'BS15_0'},
        },
        {
            'id': 400260,
            'serviceId': 260,
            'networkId': 4,
            'name': 'BS松竹東急',
            'type': 1,
            'channel': {'type': 'BS', 'channel': 'BS13_0'},
        },
    ]


    def __init__(self) -> None:
        """
        空いているポートで HTTP サーバーを作成する (リクエストの受け付けは start() で始める)
        """

        mock = self

        class Handler(BaseHTTPRequestHandler):
            """
            Mirakurun の API のうち、KonomiTV がサーバーの起動時に使うものだけを返すハンドラー
            """

            def do_GET(self) -> None:
                # パスごとに返す内容を決める (チューナーは空にする)
                body: Any
                if self.path == '/api/services':
                    body = mock.SERVICES
                elif self.path == '/api/programs':
                    mock.programs_requested.set()
                    body = mock.programs
                elif self.path == '/api/tuners':
                    body = []
                else:
                    self.send_error(404)
                    return
                data = json.dumps(body, ensure_ascii=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Server', 'Mirakurun/3.9.0-rc.4')
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: Any) -> None:
                # アクセスログの出力を省き、テストの出力を読みやすく保つ
                return

        # HTTP サーバーのインスタンス
        ## ポート 0 を指定して、OS に空いているポートを選ばせる
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)

        # リクエストを受け付けるスレッド (start() で作成し、stop() で終了を待つ)
        self.thread: threading.Thread | None = None

        # /api/programs に返す番組情報 (Mirakurun の /api/programs の形式)
        ## サーバーの起動時は空にしておき、番組情報の更新処理のテスト側で tests/fixtures/programs/ の mirakurun-programs.json の内容を設定する
        self.programs: list[dict[str, Any]] = []

        # /api/programs へのリクエストを受け付けたときにセットするイベント
        ## 別プロセスで実行される番組情報の更新処理が、番組情報の取得まで到達したことをテスト側で検知するために使う
        self.programs_requested = threading.Event()


    @property
    def url(self) -> str:
        """
        config.test.yaml の mirakurun_url に設定する URL
        """
        host, port = self.server.server_address[:2]
        return f'http://{host!s}:{port}/'


    def start(self) -> None:
        """
        別のスレッドでリクエストの受け付けを始める
        """
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()


    def stop(self) -> None:
        """
        リクエストの受け付けを止め、スレッドの終了を待つ
        """
        # shutdown() は serve_forever() の終了を待つので、受け付けを始めていたときだけ呼ぶ
        ## テストの準備の途中で失敗したときは、start() を呼ぶ前にここへ来る
        if self.thread is not None:
            self.server.shutdown()
            self.thread.join()
            self.thread = None
        self.server.server_close()
