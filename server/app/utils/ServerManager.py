
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import uvicorn
from typing import ClassVar
from uvicorn.supervisors.watchfilesreload import WatchFilesReload

from app.utils import Logging


class ServerManager:
    """ Uvicorn サーバーを管理するクラス """

    # Uvicorn のサーバーインスタンスを保持するクラス変数
    __server: ClassVar[uvicorn.Server] | None = None

    # Uvicorn サーバーの再起動を要求されているかのフラグ
    __should_restart: ClassVar[bool] = False


    @classmethod
    def run(cls, config: uvicorn.Config) -> None:
        """
        Uvicorn を起動する

        Args:
            config (uvicorn.Config): Uvicorn の設定
        """

        # Uvicorn のサーバーインスタンスを初期化
        cls.__server = uvicorn.Server(config)

        # Uvicorn を起動
        ## 自動リロードモードと通常時で呼び方が異なる
        ## ここで終了までブロッキングされる（非同期 I/O のエントリーポイント）
        ## ref: https://github.com/encode/uvicorn/blob/0.18.2/uvicorn/main.py#L568-L575
        if config.should_reload:
            # 自動リロードモード (Linux 専用)
            ## Windows で自動リロードモードを機能させるには SelectorEventLoop が必要だが、外部プロセス実行に利用している
            ## asyncio.subprocess.create_subprocess_exec() は ProactorEventLoop でないと動作しないため、Windows では事実上利用できない
            ## 外部プロセス実行を伴うストリーミング視聴を行わなければ一応 Windows でも機能する
            sock = config.bind_socket()
            WatchFilesReload(config, target=cls.__server.run, sockets=[sock]).run()
        else:
            # 通常時
            cls.__server.run()

        # ここまで到達したらサーバーが終了したことになる
        # 再起動を要求されている場合、もう一度サーバーを起動する
        if cls.__should_restart is True:
            cls.__server = None
            cls.__should_restart = False
            cls.run(config)


    @classmethod
    def shutdown(cls) -> None:
        """
        Uvicorn をシャットダウンする
        今のところ、技術的な問題でリロードモードでは機能しない
        """

        # サーバーが起動していなければ何もしない
        if cls.__server is None:
            return

        # サーバーのシャットダウンを要求する
        cls.__server.should_exit = True
        Logging.info('[ServerManager] Server shutdown requested')


    @classmethod
    def restart(cls) -> None:
        """
        Uvicorn を再起動する
        今のところ、技術的な問題でリロードモードでは機能しない
        """

        # サーバーが起動していなければ何もしない
        if cls.__server is None:
            return

        # サーバーのシャットダウンを要求する
        cls.__server.should_exit = True
        Logging.info('[ServerManager] Server restart requested')

        # サーバーのシャットダウン後に再起動するようにフラグを立てる
        cls.__should_restart = True
