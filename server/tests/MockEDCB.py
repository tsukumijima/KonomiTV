
import socketserver
import struct
import threading


class MockEDCB:
    """
    テストで放送バックエンドの代わりに使用する、EDCB (EpgTimerSrv) の CtrlCmd のうち番組情報一覧の取得コマンドのみに応答する TCP サーバー
    番組情報の更新処理を、実際の EDCB を使う場合と同じ通信処理と応答の解析処理を経由して実行できるようにする
    """

    # EpgTimerSrv の CtrlCmd のコマンド番号と応答コード (app/utils/edcb/CtrlCmdUtil.py と同じ値)
    CMD_SUCCESS = 1
    CMD_ERR = 0
    CMD_EPG_SRV_ENUM_PG_INFO_EX = 1029


    def __init__(self) -> None:
        """
        空いているポートで TCP サーバーを作成する (リクエストの受け付けは start() で開始する)
        """

        mock = self

        class Handler(socketserver.StreamRequestHandler):
            """
            CtrlCmd のリクエストを1件読み込み、番組情報一覧の取得コマンドなら programs を、それ以外のコマンドならエラーを返すハンドラー
            """

            def handle(self) -> None:
                # 先頭の8バイト (コマンド番号と本体のサイズ) を読み込み、本体は読み飛ばす
                ## 引数で指定されたチャンネルや期間に関わらず、保存済みの応答をそのまま返す
                cmd, size = struct.unpack('<ii', self.rfile.read(8))
                self.rfile.read(size)

                # 番組情報一覧の取得コマンドには、保存済みの応答の本体をそのまま返す
                if cmd == MockEDCB.CMD_EPG_SRV_ENUM_PG_INFO_EX:
                    mock.programs_requested.set()
                    self.wfile.write(struct.pack('<ii', MockEDCB.CMD_SUCCESS, len(mock.programs)) + mock.programs)
                else:
                    self.wfile.write(struct.pack('<ii', MockEDCB.CMD_ERR, 0))

        # TCP サーバーのインスタンス
        ## ポート 0 を指定して、OS に空いているポートを選ばせる
        self.server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True

        # リクエストを受け付けるスレッド (start() で作成し、stop() で終了を待つ)
        self.thread: threading.Thread | None = None

        # 番組情報一覧の取得コマンドに返す応答の本体 (CtrlCmdUtil が受け取るバイト列)
        ## テスト側で tests/fixtures/programs/ の edcb-programs.bin の内容を設定する
        self.programs: bytes = struct.pack('<ii', 8, 0)

        # 番組情報一覧の取得コマンドを受け付けたときにセットするイベント
        ## 別プロセスで実行される番組情報の更新処理が、番組情報の取得まで到達したことをテスト側で検知するために使う
        self.programs_requested = threading.Event()


    @property
    def url(self) -> str:
        """
        config.test.yaml の edcb_url に設定する URL
        """
        host, port = self.server.server_address[:2]
        return f'tcp://{host!s}:{port}/'


    def start(self) -> None:
        """
        別スレッドでリクエストの受け付けを開始する
        """
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()


    def stop(self) -> None:
        """
        リクエストの受け付けを停止し、スレッドの終了を待機する
        """
        # shutdown() は serve_forever() の終了を待機するため、受け付けを開始済みの場合のみ呼び出す
        ## テストの準備中に失敗した場合は、start() を呼び出す前にここに到達する
        if self.thread is not None:
            self.server.shutdown()
            self.thread.join()
            self.thread = None
        self.server.server_close()
