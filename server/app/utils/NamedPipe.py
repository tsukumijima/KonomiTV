
import logging
import os
import pywintypes
import threading
import win32file
import win32pipe
from typing import Union


class NamedPipe:

    def __init__(self, pipe_name:str):
        """名前付きパイプのユーティリティクラス

        Args:
            pipe_name (str): 名前付きパイプの名称 (ex: Live_NID32736-SID1024_1080p)
        """

        # 名前付きパイプのパス
        if os.name == 'nt':
            self.pipe_path = '\\\.\pipe\Konomi_' + pipe_name

        # 名前付きパイプのハンドル
        self.pipe_handle = None

        # ロガー
        self.logger = logging.getLogger('app')


    def read(self, size:int=48128) -> Union[bytes, bool]:
        """名前付きパイプから出力を読み取る

        Args:
            size (int, optional): 名前付きパイプから読み取るバイト数. Defaults to 48128.

        Returns:
            Union[bytes, bool]: 名前付きパイプから読み取ったデータ 読み取りに失敗した場合は False を返す
        """

        # Windows のみ
        if os.name == 'nt':

            # 名前付きパイプから size 分読み取る
            try:
                # 実行結果と読み取ったデータのタプルなので注意
                _, data = win32file.ReadFile(self.pipe_handle, size)
                return data
            except pywintypes.error as ex:
                # 読み取りに失敗した（主にパイプが閉じられているなどの理由）なら False を返す
                self.logger.error(f'ReadFile() failed. Code:{ex.args[0]} Message:{ex.args[2]}')
                return False


    def write(self, data:bytes) -> bool:
        """名前付きパイプに入力を書き込む

        Args:
            data (bytes): 名前付きパイプに書き込むデータ

        Returns:
            bool: 書き込みが成功したら True, 失敗したら False を返す
        """

        # Windows のみ
        if os.name == 'nt':

            # 名前付きパイプに書き込む
            try:
                # 書き込みが成功したら True・失敗したら False が返る
                return win32file.WriteFile(self.pipe_handle, data)
            except pywintypes.error as ex:
                # 読み取りに失敗した（主にパイプが閉じられているなどの理由）なら False を返す
                self.logger.error(f'WriteFile() failed. Code:{ex.args[0]} Message:{ex.args[2]}')
                return False


    def close(self) -> None:
        """開いた名前付きパイプを閉じる
        """

        # Windows のみ
        if os.name == 'nt':

            # 名前付きパイプを閉じる
            if self.pipe_handle is not None:
                win32pipe.DisconnectNamedPipe(self.pipe_handle)
                win32file.CloseHandle(self.pipe_handle)

        # ハンドルを空にする
        self.pipe_handle = None


class NamedPipeServer(NamedPipe):

    def create(self) -> bool:
        """名前付きパイプを作成する
        Windows では create(), Linux では mkfifo を使う

        Returns:
            bool: 作成できたら True, 作成に失敗したら False を返す
        """

        # まだハンドルが閉じられていなければ閉じる
        if self.pipe_handle is not None:
            self.close()

        # Windows のみ
        if os.name == 'nt':

            # Win32Pipe を使って名前付きパイプを作成
            # 参考: https://github.com/xtne6f/EDCB/blob/work-plus-s/SendTSTCP/SendTSTCP/SendTSTCPMain.cpp#L267
            try:
                self.pipe_handle = win32pipe.CreateNamedPipe(
                    # Name: 名前付きパイプのパス
                    self.pipe_path,
                    # OpenMode: 双方向パイプ・オーバーラップモード
                    win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED,
                    # PipeMode: バイトストリーム・ブロッキング
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                    # MaxInstance: 無制限のパイプインスタンス
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    # OutBufferSize: 0B の出力バッファ
                    0,
                    # InBufferSize: 48128B の入力バッファ
                    48128,
                    # DefaultTimeOut: デフォルトのタイムアウト秒を使用
                    0,
                    # SecurityAttributes: なし
                    None,
                )
            except pywintypes.error as ex:
                # 接続に失敗したら念のため接続を閉じて False を返す
                self.logger.error(f'CreateNamedPipe() failed. Code:{ex.args[0]} Message:{ex.args[2]}')
                self.close()
                return False

            # 非同期でクライアントの接続を待ち受ける（非同期でないと次の処理へ進めない）
            # Linux の名前付きパイプはクライアントサーバモデルではないので不要
            def listen():
                win32pipe.ConnectNamedPipe(self.pipe_handle, None)
            thread = threading.Thread(target=listen)
            thread.start()

        return True


class NamedPipeClient(NamedPipe):

    def connect(self) -> bool:
        """名前付きパイプに接続する

        Returns:
            bool: 接続できたら True, 接続に失敗したら False を返す
        """

        # まだハンドルが閉じられていなければ閉じる
        if self.pipe_handle is not None:
            self.close()

        # Windows のみ
        if os.name == 'nt':

            # 名前付きパイプに接続
            try:
                self.pipe_handle = win32file.CreateFile(
                    # FileName: 名前付きパイプのパス
                    self.pipe_path,
                    # DesiredAccess: 読み取り
                    win32file.GENERIC_READ,
                    # ShareMode: 読み取りの共有を許可
                    win32file.FILE_SHARE_READ,
                    # SecurityAttributes: なし
                    None,
                    # CreationDisposition: ファイルまたはデバイスが存在する場合にのみ開く
                    win32file.OPEN_EXISTING,
                    # FlagsAndAttributes: オーバーラップモード
                    win32file.FILE_FLAG_OVERLAPPED,
                    # TemplateFile: なし
                    None,
                )
            except pywintypes.error as ex:
                # 接続に失敗したら念のため接続を閉じて False を返す
                self.logger.error(f'CreateFile() failed. Code:{ex.args[0]} Message:{ex.args[2]}')
                self.close()
                return False

        return True
