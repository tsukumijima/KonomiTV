
import asyncio
import datetime
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import Any, Literal, TypedDict, TypeVar, cast
from zoneinfo import ZoneInfo

import aiofiles
import emoji
import ifaddr
import psutil
import rich
import ruamel.yaml
import ruamel.yaml.scalarstring
from rich import box, print
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text, TextType
from watchdog.events import (
    DirCreatedEvent,
    DirModifiedEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileSystemEventHandler,
)
from watchdog.observers.polling import PollingObserver


class CustomPrompt(Prompt):
    """ カスタムの Rich プロンプトの実装 """

    def __init__(
        self,
        prompt: TextType = "",
        *,
        console: Console | None = None,
        password: bool = False,
        choices: list[str] | None = None,
        case_sensitive: bool = True,
        show_default: bool = True,
        show_choices: bool = True,
    ) -> None:

        if type(prompt) is str:
            prompt = f'  {prompt}'  # 左に半角スペース2つ分余白を空ける

        # 親クラスのコンストラクタを実行
        super().__init__(
            prompt,
            console=console,
            password=password,
            choices=choices,
            case_sensitive=case_sensitive,
            show_default=show_default,
            show_choices=show_choices,
        )

        if self.choices is not None:
            self.illegal_choice_message = Padding(f'[prompt.invalid.choice][{"/".join(self.choices)}] のいずれかを選択してください！', (0, 2, 0, 2))


class CustomConfirm(Confirm):
    """ カスタムの Rich コンファームの実装 """
    validate_error_message = "[prompt.invalid]Y or N のいずれかを入力してください！"

    def __init__(
        self,
        prompt: TextType = "",
        *,
        console: Console | None = None,
        password: bool = False,
        choices: list[str] | None = None,
        case_sensitive: bool = True,
        show_default: bool = True,
        show_choices: bool = True,
    ) -> None:

        if type(prompt) is str:
            prompt = f'  {prompt}'  # 左に半角スペース2つ分余白を空ける

        # 親クラスのコンストラクタを実行
        super().__init__(
            prompt,
            console=console,
            password=password,
            choices=choices,
            case_sensitive=case_sensitive,
            show_default=show_default,
            show_choices=show_choices,
        )


class InstallerAbortError(Exception):
    """ 非対話モードで、回答が指定されていないか不正なため、処理を続行できないことを表すエラー """


class InstallerAnswers:
    """
    インストーラー・アップデーター・アンインストーラーの質問への回答を管理するクラス
    コマンドライン引数で回答が指定されていればその値を使い、指定されていなければ対話的に質問する
    非対話モードでは質問せず、回答がないか不正なときは InstallerAbortError を送出する
    """

    def __init__(self, answers: dict[str, str | list[str] | bool], is_non_interactive: bool) -> None:
        """
        Args:
            answers (dict[str, str | list[str] | bool]): コマンドライン引数で指定された回答 (キーはコマンドライン引数の dest 名)
            is_non_interactive (bool): 非対話モードで実行するかどうか
        """

        # コマンドライン引数で指定された回答
        ## キーはコマンドライン引数の dest 名で、エラーメッセージではキーからオプション名 (--install-path など) を復元する
        ## ask() と confirm() は一度使った回答を取り除くため、入力値が不正で同じ質問をもう一度するときは対話的に質問する
        ## askListItem() はリストの先頭から1つずつ取り出し、すべて取り出した時点でキーごと取り除く
        self.answers: dict[str, str | list[str] | bool] = answers

        # 非対話モードで実行するかどうか
        ## ask()・askListItem()・confirm()・showInvalidInput() から参照される
        self.is_non_interactive: bool = is_non_interactive


    def ask(
        self,
        key: str,
        prompt: str,
        default: str | None = None,
        choices: list[str] | None = None,
        is_secret: bool = False,
    ) -> str:
        """
        質問への回答を取得する
        コマンドライン引数で回答が指定されていればその値を返し、指定されていなければ対話的に質問する
        非対話モードで回答が指定されていないときは、既定値があれば既定値を返し、なければ InstallerAbortError を送出する

        Args:
            key (str): 回答のキー (コマンドライン引数の dest 名)
            prompt (str): 質問文
            default (str | None): 既定値
            choices (list[str] | None): 選択肢 (指定した場合は、回答が選択肢のいずれかであることを検証する)
            is_secret (bool): パスワードなど、コマンドライン引数で受け取った回答を確認のための表示で伏せるかどうか (対話的に入力する場合は、入力できているかを利用者が確認できるよう表示する)

        Returns:
            str: 回答
        """

        option_name = '--' + key.replace('_', '-')

        # コマンドライン引数で回答が指定されている場合は、その値を使う
        ## 一度使った回答は取り除き、入力値が不正で同じ質問をもう一度するときは対話的に質問する
        value = self.answers.pop(key, None)
        if type(value) is str:
            if choices is not None and value not in choices:
                self.showInvalidInput(f'{option_name} には {"・".join(choices)} のいずれかを指定してください。')
            else:
                # 後からログを見返したときに、どの値でインストールされたかが分かるよう、使った回答を表示する
                print(Padding(f'{prompt}: {"********" if is_secret is True else value}', (0, 2, 0, 2)))
                return value

        # 非対話モードでは質問せず、既定値があれば既定値を使う
        if self.is_non_interactive is True:
            if default is not None:
                print(Padding(f'{prompt}: {default} (既定値)', (0, 2, 0, 2)))
                return default
            raise InstallerAbortError(f'{option_name} で「{prompt}」を指定してください。')

        # 対話的に質問する
        if default is not None:
            return CustomPrompt.ask(prompt, default=default, choices=choices)
        return CustomPrompt.ask(prompt, choices=choices)


    def askListItem(self, key: str, prompt: str) -> str:
        """
        複数の値を1つずつ入力する質問 (録画フォルダなど) への回答を1つ取得する
        コマンドライン引数で回答が指定されていれば先頭から1つずつ返し、すべて返したら空文字を返して入力を終了させる
        非対話モードで回答が指定されていないときは、空文字を返す (少なくとも1つ必要かどうかは呼び出し元で判定する)

        Args:
            key (str): 回答のキー (コマンドライン引数の dest 名)
            prompt (str): 質問文

        Returns:
            str: 回答 (入力を終了するときは空文字)
        """

        # コマンドライン引数で回答が指定されている場合は、先頭から1つずつ使う
        values = self.answers.get(key)
        if type(values) is list:
            if len(values) > 0:
                value = values.pop(0)
                print(Padding(f'{prompt}: {value}', (0, 2, 0, 2)))
                return value
            # すべて使い終わったらキーごと取り除き、入力を終了させる
            ## 呼び出し元で入力が足りないと判定されたときは、次の呼び出しで対話的に質問する
            del self.answers[key]
            return ''

        # 非対話モードでは質問せず、入力を終了させる
        if self.is_non_interactive is True:
            return ''

        # 対話的に質問する
        return CustomPrompt.ask(prompt)


    def confirm(self, key: str, prompt: str, default: bool) -> bool:
        """
        Y/N で答える質問への回答を取得する
        非対話モードで回答が指定されていないときは、既定値を返す

        Args:
            key (str): 回答のキー (コマンドライン引数の dest 名)
            prompt (str): 質問文
            default (bool): 既定値

        Returns:
            bool: 回答
        """

        # コマンドライン引数で回答が指定されている場合は、その値を使う
        value = self.answers.pop(key, None)
        if type(value) is bool:
            print(Padding(f'{prompt}: {"Yes" if value is True else "No"}', (0, 2, 0, 2)))
            return value

        # 非対話モードでは質問せず、既定値を使う
        if self.is_non_interactive is True:
            print(Padding(f'{prompt}: {"Yes" if default is True else "No"} (既定値)', (0, 2, 0, 2)))
            return default

        # 対話的に質問する
        return bool(CustomConfirm.ask(prompt, default=default))


    def showInvalidInput(self, message: str) -> None:
        """
        入力値が不正なことを表示する
        非対話モードでは同じ質問をもう一度できないため、InstallerAbortError を送出して処理を中断する
        (メッセージは InstallerAbortError を捕捉した KonomiTV-Installer.py で表示する)

        Args:
            message (str): 表示するメッセージ
        """

        if self.is_non_interactive is True:
            raise InstallerAbortError(message)
        print(Padding(f'[red]{message}', (0, 2, 0, 2)))


class WindowsServiceAccount(TypedDict):
    """ KonomiTV の Windows サービスの実行アカウント """
    service_account: Literal['LocalSystem', 'User']  # 実行アカウントの種類
    user_name: str  # ユーザーの権限で実行する場合のユーザー名 (LocalSystem の場合は空文字)
    password: str  # ユーザーの権限で実行する場合のパスワード (LocalSystem の場合は空文字)


# ジェネリック型
T = TypeVar('T')

class NotifySrvInfo(TypedDict):
    """ 情報通知用パラメーター """
    notify_id: int  # 通知情報の種類
    time: datetime.datetime  # 通知状態の発生した時間
    param1: int  # パラメーター1 (種類によって内容変更)
    param2: int  # パラメーター2 (種類によって内容変更)
    count: int  # 通知の巡回カウンタ
    param4: str  # パラメーター4 (種類によって内容変更)
    param5: str  # パラメーター5 (種類によって内容変更)
    param6: str  # パラメーター6 (種類によって内容変更)

class NotifyUpdate(IntEnum):
    """ 通知情報の種類 """
    EPGDATA = 1  # EPGデータが更新された
    RESERVE_INFO = 2  # 予約情報が更新された
    REC_INFO = 3  # 録画済み情報が更新された
    AUTOADD_EPG = 4  # 自動予約登録情報が更新された
    AUTOADD_MANUAL = 5  # 自動予約 (プログラム) 登録情報が更新された
    PROFILE = 51  # 設定ファイル (ini) が更新された
    SRV_STATUS = 100  # Srv の動作状況が変更 (param1: ステータス 0:通常、1:録画中、2:EPG取得中)
    PRE_REC_START = 101  # 録画準備開始 (param4: ログ用メッセージ)
    REC_START = 102  # 録画開始 (param4: ログ用メッセージ)
    REC_END = 103  # 録画終了 (param4: ログ用メッセージ)
    REC_TUIJYU = 104  # 録画中に追従が発生 (param4: ログ用メッセージ)
    CHG_TUIJYU = 105  # 追従が発生 (param4: ログ用メッセージ)
    PRE_EPGCAP_START = 106  # EPG 取得準備開始
    EPGCAP_START = 107  # EPG 取得開始
    EPGCAP_END = 108  # EPG 取得終了

class CtrlCmdConnectionCheckUtil:
    """ server/app/utils/EDCB.py の CtrlCmdUtil クラスのうち、接続確認に必要なロジックだけを抜き出したもの"""

    # EDCB の日付は OS のタイムゾーンに関わらず常に UTC+9
    TZ = ZoneInfo('Asia/Tokyo')

    # 読み取った日付が不正なときや既定値に使う UNIX エポック
    UNIX_EPOCH = datetime.datetime(1970, 1, 1, 9, tzinfo=TZ)

    __connect_timeout_sec: float
    __pipe_dir: str
    __pipe_name: str
    __host: str | None
    __port: int

    def __init__(self, hostname: str, port: int | None) -> None:
        self.__connect_timeout_sec = 10  # 10秒でタイムアウト

        # 初期値は名前付きパイプモード
        self.__pipe_dir = '\\\\.\\pipe\\' if os.name == 'nt' else '/var/local/edcb/'
        self.__pipe_name = 'EpgTimerSrvNoWaitPipe' if os.name == 'nt' else 'EpgTimerSrvPipe'
        self.__host = None
        self.__port = 0

        if hostname != 'edcb-namedpipe':
            # TCP/IP モードにする
            self.__host = hostname
            self.__port = cast(int, port)

    async def sendGetNotifySrvInfo(self, target_count: int) -> NotifySrvInfo | None:
        """ target_count より大きいカウントの通知を待つ (TCP/IP モードのときロングポーリング) """
        ret, rbuf = await self.__sendCmd2(self.__CMD_EPG_SRV_GET_STATUS_NOTIFY2,
                                          lambda buf: self.__writeUint(buf, target_count))
        if ret == self.__CMD_SUCCESS:
            bufview = memoryview(rbuf)
            pos = [0]
            try:
                if self.__readUshort(bufview, pos, len(rbuf)) >= self.__CMD_VER:
                    return self.__readNotifySrvInfo(bufview, pos, len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendGetNotifySrvStatus(self) -> NotifySrvInfo | None:
        """ 現在の NotifyUpdate.SRV_STATUS を取得する """
        return await self.sendGetNotifySrvInfo(0)

    # EDCB/EpgTimer の CtrlCmd.cs より
    __CMD_SUCCESS = 1
    __CMD_VER = 5
    __CMD_EPG_SRV_GET_STATUS_NOTIFY2 = 2200

    async def __sendAndReceive(self, buf: bytearray) -> tuple[int | None, bytes]:
        to = time.monotonic() + self.__connect_timeout_sec
        if os.name == 'nt' and self.__host is None:
            # 名前付きパイプモード
            while True:
                try:
                    async with aiofiles.open(self.__pipe_dir + self.__pipe_name, mode='r+b') as f:
                        await f.write(buf)
                        await f.flush()
                        rbuf = await f.read(8)
                        if len(rbuf) == 8:
                            bufview = memoryview(rbuf)
                            pos = [0]
                            ret = self.__readInt(bufview, pos, 8)
                            size = self.__readInt(bufview, pos, 8)
                            rbuf = await f.read(size)
                            if len(rbuf) == size:
                                return ret, rbuf
                    break
                except FileNotFoundError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(0.01)
                if time.monotonic() >= to:
                    break
            return None, b''

        # UNIX ドメインソケットまたは TCP/IP モード
        try:
            if self.__host is None:
                connection_future = asyncio.open_unix_connection(self.__pipe_dir + self.__pipe_name)
            else:
                connection_future = asyncio.open_connection(self.__host, self.__port)
            connection = await asyncio.wait_for(connection_future, max(to - time.monotonic(), 0.))
            reader: asyncio.StreamReader = connection[0]
            writer: asyncio.StreamWriter = connection[1]
        except Exception:
            return None, b''
        try:
            writer.write(buf)
            await asyncio.wait_for(writer.drain(), max(to - time.monotonic(), 0.))
            ret = 0
            size = 8
            rbuf = await asyncio.wait_for(reader.readexactly(8), max(to - time.monotonic(), 0.))
            if len(rbuf) == 8:
                bufview = memoryview(rbuf)
                pos = [0]
                ret = self.__readInt(bufview, pos, 8)
                size = self.__readInt(bufview, pos, 8)
                rbuf = await asyncio.wait_for(reader.readexactly(size), max(to - time.monotonic(), 0.))
        except Exception:
            return None, b''
        finally:
            writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), max(to - time.monotonic(), 0.))
        except Exception:
            pass
        if len(rbuf) == size:
            return ret, rbuf
        return None, b''

    async def __sendCmd2(self, cmd2: int, write_func: Callable[[bytearray], None] | None = None) -> tuple[int | None, bytes]:
        buf = bytearray()
        self.__writeInt(buf, cmd2)
        self.__writeInt(buf, 0)
        self.__writeUshort(buf, self.__CMD_VER)
        if write_func:
            write_func(buf)
        self.__writeIntInplace(buf, 4, len(buf) - 8)
        return await self.__sendAndReceive(buf)

    @staticmethod
    def __writeUshort(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(2, 'little'))

    @staticmethod
    def __writeInt(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(4, 'little', signed=True))

    @staticmethod
    def __writeUint(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(4, 'little'))

    @staticmethod
    def __writeIntInplace(buf: bytearray, pos: int, v: int) -> None:
        buf[pos:pos + 4] = v.to_bytes(4, 'little', signed=True)

    class __ReadError(Exception):
        """ バッファをデータ構造として読み取るのに失敗したときの内部エラー """
        pass

    @classmethod
    def __readUshort(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 2:
            raise cls.__ReadError
        v = buf[pos[0]] | buf[pos[0] + 1] << 8
        pos[0] += 2
        return v

    @classmethod
    def __readInt(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 4:
            raise cls.__ReadError
        v = int.from_bytes(buf[pos[0]:pos[0] + 4], 'little', signed=True)
        pos[0] += 4
        return v

    @classmethod
    def __readUint(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 4:
            raise cls.__ReadError
        v = int.from_bytes(buf[pos[0]:pos[0] + 4], 'little')
        pos[0] += 4
        return v

    @classmethod
    def __readSystemTime(cls, buf: memoryview, pos: list[int], size: int) -> datetime.datetime:
        if size - pos[0] < 16:
            raise cls.__ReadError
        try:
            pos0 = pos[0]
            v = datetime.datetime(buf[pos0] | buf[pos0 + 1] << 8,
                                  buf[pos0 + 2] | buf[pos0 + 3] << 8,
                                  buf[pos0 + 6] | buf[pos0 + 7] << 8,
                                  buf[pos0 + 8] | buf[pos0 + 9] << 8,
                                  buf[pos0 + 10] | buf[pos0 + 11] << 8,
                                  buf[pos0 + 12] | buf[pos0 + 13] << 8,
                                  tzinfo=cls.TZ)
        except Exception:
            v = cls.UNIX_EPOCH
        pos[0] += 16
        return v

    @classmethod
    def __readString(cls, buf: memoryview, pos: list[int], size: int) -> str:
        vs = cls.__readInt(buf, pos, size)
        if vs < 6 or size - pos[0] < vs - 4:
            raise cls.__ReadError
        v = str(buf[pos[0]:pos[0] + vs - 6], 'utf_16_le')
        pos[0] += vs - 4
        return v

    @classmethod
    def __readStructIntro(cls, buf: memoryview, pos: list[int], size: int) -> int:
        vs = cls.__readInt(buf, pos, size)
        if vs < 4 or size - pos[0] < vs - 4:
            raise cls.__ReadError
        return pos[0] + vs - 4

    # 以下、各構造体のリーダー

    @classmethod
    def __readNotifySrvInfo(cls, buf: memoryview, pos: list[int], size: int) -> NotifySrvInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: NotifySrvInfo = {
            'notify_id': cls.__readUint(buf, pos, size),
            'time': cls.__readSystemTime(buf, pos, size),
            'param1': cls.__readUint(buf, pos, size),
            'param2': cls.__readUint(buf, pos, size),
            'count': cls.__readUint(buf, pos, size),
            'param4': cls.__readString(buf, pos, size),
            'param5': cls.__readString(buf, pos, size),
            'param6': cls.__readString(buf, pos, size)
        }
        pos[0] = size
        return v


# --json-progress が指定され、標準出力に JSON 形式の進捗を出力するかどうか
## EnableJSONProgress() で有効にし、EmitJSONProgress()・RunSubprocessDirectLogOutput() から参照される
_is_json_progress_enabled = False

def EmitJSONProgress(event: Literal['step', 'warning', 'error', 'access_urls', 'result'], **fields: Any) -> None:
    """
    --json-progress が指定されているときに、進捗を1行の JSON として標準出力に出力する
    インストーラーを外部のアプリケーションから実行するときに、進捗を機械的に読み取れるようにするためのもの

    Args:
        event (Literal['step', 'warning', 'error', 'access_urls', 'result']): イベントの種類
        **fields (Any): イベントに含める値
    """

    if _is_json_progress_enabled is False:
        return

    # Windows の標準出力の文字コードに関わらず読み取れるよう、ASCII 以外の文字はエスケープして出力する
    sys.stdout.write(json.dumps({'event': event, **fields}) + '\n')
    sys.stdout.flush()


def EnableJSONProgress() -> None:
    """
    標準出力に JSON 形式の進捗を出力するようにする
    標準出力を JSON の進捗だけにするため、Rich による人向けの表示はすべて標準エラー出力に出力する
    呼び出し元のアプリケーションが OS の文字コードに関わらず読み取れるよう、標準エラー出力は UTF-8 で出力する
    """

    global _is_json_progress_enabled
    _is_json_progress_enabled = True
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8')
    rich.reconfigure(file=sys.stderr)


def GetNetworkDriveList() -> list[dict[str, str]]:
    """
    レジストリからログオン中のユーザーがマウントしているネットワークドライブのリストを取得する
    KonomiTV-Service.py で利用されているものと基本同じ

    Returns:
        list[dict[str, str]]: ネットワークドライブのドライブレターとパスのリスト
    """

    # Windows 以外では実行しない
    if os.name != 'nt':
        return []

    # winreg (レジストリを操作するための標準ライブラリ (Windows 限定) をインポート)
    import winreg

    # ネットワークドライブの情報が入る辞書のリスト
    network_drives: list[dict[str, str]] = []

    # ネットワークドライブの情報が格納されているレジストリの HKEY_CURRENT_USER\Network を開く
    # ref: https://itasuke.hatenablog.com/entry/2018/01/08/133510
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Network') as root_key:

            # HKEY_CURRENT_USER\Network 以下のキーを列挙
            for key in range(winreg.QueryInfoKey(root_key)[0]):
                drive_letter = winreg.EnumKey(root_key, key)

                # HKEY_CURRENT_USER\Network 以下のキーをそれぞれ開く
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'Network\\{drive_letter}') as key:
                    for sub_key in range(winreg.QueryInfoKey(key)[1]):

                        # 値の名前、データ、データ型を取得
                        name, data, _ = winreg.EnumValue(key, sub_key)

                        # リストに追加
                        if name == 'RemotePath':
                            network_drives.append({
                                'drive_letter': drive_letter,
                                'remote_path': data,
                            })

    # なぜかエラーが出ることがあるが、その際は無視する
    except FileNotFoundError:
        pass

    return network_drives


def GetNetworkInterfaceInformation() -> list[tuple[str, str]]:
    """
    ループバックアドレスまたはリンクローカルアドレスでない IPv4 アドレスとインターフェイス名を取得する

    Returns:
        list[tuple[str, str]]: IPv4 アドレスとインターフェイス名のタプルのリスト
    """

    # ループバックアドレスまたはリンクローカルアドレスでない IPv4 アドレスを取得
    ip_addresses: list[tuple[str, str]] = []
    for nic in ifaddr.get_adapters():
        for ip in nic.ips:
            if ip.is_IPv4:
                # ループバック (127.x.x.x) とリンクローカル (169.254.x.x) を除外
                if cast(str, ip.ip).startswith('127.') is False and cast(str, ip.ip).startswith('169.254.') is False:
                    ip_addresses.append((cast(str, ip.ip), ip.nice_name))  # IP アドレスとインターフェイス名

    # IP アドレス昇順でソート
    ip_addresses.sort(key=lambda key: key[0])

    return ip_addresses


def AskWindowsServiceAccount(
    answers: InstallerAnswers,
    question_number: int,
    network_folders: list[str],
    is_account_selection_supported: bool,
) -> WindowsServiceAccount:
    """
    KonomiTV の Windows サービスを実行するアカウントを質問し、ユーザーの権限で実行する場合はパスワードを検証する
    インストーラーではファイルを配置する前に呼び出し、パスワードの不足や間違いでインストールが途中で止まるのを防ぐ
    入力が不正なときは、対話モードでは質問し直し、非対話モードでは InstallerAbortError を送出する

    Args:
        answers (InstallerAnswers): 質問への回答
        question_number (int): 実行アカウントの質問に付ける番号 (以降の質問には連番を付ける)
        network_folders (list[str]): 録画フォルダとキャプチャ画像の保存先のうち、ネットワーク上にあるフォルダ (既定の実行アカウントの決定に使う)
        is_account_selection_supported (bool): インストールする KonomiTV のサービス管理スクリプトが、LocalSystem での実行に対応しているか

    Returns:
        WindowsServiceAccount: 選ばれた実行アカウント
    """

    def ValidateWindowsUserPassword(account_name: str, password: str) -> int:
        """
        Windows のユーザー名とパスワードの組み合わせでログオンできるかを検証する
        サービスの登録前に検証することで、パスワードの間違いをサービスの起動に失敗する前に伝える

        Args:
            account_name (str): ユーザー名 (ドメイン名またはコンピューター名を付けてもよい)
            password (str): パスワード

        Returns:
            int: ログオンできたときは 0 、できなかったときは Windows のエラーコード
        """

        if sys.platform != 'win32':
            return 0

        import ctypes
        from ctypes import wintypes

        # ユーザー名をドメイン名とユーザー名に分ける
        ## ドメイン名を省略した場合は、"." (ローカルのアカウント) を指定する
        domain_name = '.'
        user_name = account_name
        if '\\' in account_name:
            domain_name, user_name = account_name.split('\\', 1)

        # LogonUserW で対話型ログオンを試す
        ## Microsoft アカウントのユーザーでも、ローカルのユーザー名と Microsoft アカウントのパスワードでログオンできる
        LOGON32_LOGON_INTERACTIVE = 2
        LOGON32_PROVIDER_DEFAULT = 0
        advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        token = wintypes.HANDLE()
        is_succeeded = advapi32.LogonUserW(
            user_name,
            domain_name,
            password,
            LOGON32_LOGON_INTERACTIVE,
            LOGON32_PROVIDER_DEFAULT,
            ctypes.byref(token),
        )
        if is_succeeded == 0:
            return ctypes.get_last_error()
        kernel32.CloseHandle(token)
        return 0

    # 録画フォルダやキャプチャ画像の保存先にネットワーク上のフォルダが含まれる場合は、ユーザーの権限で実行するのを既定にする
    ## LocalSystem で実行すると、ネットワークドライブや NAS 上のフォルダにアクセスできない
    default_service_account = 'User' if len(network_folders) > 0 else 'LocalSystem'

    # LocalSystem での実行に対応しているバージョンでのみ、実行アカウントの二択を表示する
    if is_account_selection_supported is True:
        table_account = CreateTable()
        table_account.add_column(f'{question_number:02d}. KonomiTV の Windows サービスを実行するアカウントを選んでください。')
        table_account.add_row('LocalSystem: この PC のドライブにある録画フォルダだけを使う場合におすすめです。')
        table_account.add_row('Windows のパスワードを入力する必要はありません。')
        table_account.add_row('ただし、ネットワークドライブや NAS 上のフォルダにはアクセスできません。')
        table_account.add_row(CreateRule())
        table_account.add_row('User: ネットワークドライブや NAS 上のフォルダを録画フォルダなどに指定する場合に選びます。')
        table_account.add_row('ログオン中のユーザーの権限で実行するため、Windows のパスワードを入力する必要があります。')
        table_account.add_row('Windows のパスワードを変更したときは、サービスの実行アカウントを設定し直す必要があります。')
        table_account.add_row(CreateRule())
        table_account.add_row('あとからネットワークドライブや NAS を使いたくなった場合は、インストーラーの')
        table_account.add_row('[サービスの実行アカウントを変更] から、いつでも切り替えられます。')
        if len(network_folders) > 0:
            table_account.add_row(CreateRule())
            table_account.add_row('次のフォルダはネットワーク上にあるため、User を既定にしています。')
            for network_folder in network_folders:
                table_account.add_row(f'・{network_folder}')
        print(Padding(table_account, (1, 2, 1, 2)))

    # 現在ログオン中のユーザー名 (ユーザーの権限で実行する場合のユーザー名の既定値)
    ## PowerShell の起動には時間がかかるため、ユーザーの権限で実行することが決まってから1回だけ取得する
    current_user_name_default: str | None = None

    while True:

        # 実行アカウントを取得 (入力が不正な限り何度でも表示される)
        ## LocalSystem での実行に対応していないバージョンでは、ユーザーの権限で実行する
        service_account: Literal['LocalSystem', 'User'] = 'User'
        if is_account_selection_supported is True:
            service_account = cast(
                Literal['LocalSystem', 'User'],
                answers.ask('service_account', 'サービスの実行アカウント', default=default_service_account, choices=['LocalSystem', 'User']),
            )
        elif answers.answers.pop('service_account', None) == 'LocalSystem':
            # 非対話モードでは、指定された実行アカウントを使えないことを伝えて中断し、対話モードではユーザーの権限で実行することを伝えて続行する
            if answers.is_non_interactive is True:
                answers.showInvalidInput('インストールするバージョンの KonomiTV は、LocalSystem での実行に対応していません。--service-account User を指定してください。')
            answers.showInvalidInput('インストールするバージョンの KonomiTV は、LocalSystem での実行に対応していないため、User で実行します。')

        # LocalSystem で実行する場合は、ユーザー名とパスワードの質問を省略する
        if service_account == 'LocalSystem':
            return WindowsServiceAccount(service_account='LocalSystem', user_name='', password='')

        # ユーザーの権限で実行する場合は、ユーザー名とパスワードを質問する
        if current_user_name_default is None:
            ## PowerShell の [Environment]::UserDomainName と [Environment]::UserName を使う
            current_user_name_default = subprocess.run(
                args = ['powershell', '-Command', r'"$([Environment]::UserDomainName)\$([Environment]::UserName)"'],
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                text = True,  # 出力をテキストとして取得する
            ).stdout.strip()

        table_user = CreateTable()
        table_user.add_column(f'{question_number + 1:02d}. KonomiTV の Windows サービスの実行ユーザー名を入力してください。')
        table_user.add_row('KonomiTV の Windows サービスを一般ユーザーの権限で起動するために利用します。')
        table_user.add_row('ほかのユーザー権限で実行したい場合は、そのユーザー名を入力してください。')
        table_user.add_row(f'Enter キーを押すと、現在ログオン中のユーザー ({current_user_name_default}) が利用されます。')
        print(Padding(table_user, (0, 2, 0, 2)))

        # ユーザー名を入力
        current_user_name = answers.ask('service_user', 'KonomiTV の Windows サービスの実行ユーザー名', default=current_user_name_default)

        table_password = CreateTable()
        table_password.add_column(f'{question_number + 2:02d}. ユーザー ({current_user_name}) のパスワードを入力してください。')
        table_password.add_row('KonomiTV の Windows サービスを一般ユーザーの権限で起動するために利用します。')
        table_password.add_row('入力されたパスワードがそれ以外の用途に利用されることはありません。')
        table_password.add_row('Microsoft アカウントでサインインしている場合は、Microsoft アカウントのパスワードを入力してください。')
        table_password.add_row('なお、PIN などのほかの認証方法には対応していません。')
        table_password.add_row(CreateRule())
        table_password.add_row('ログオン中のユーザーにパスワードを設定していない場合は、簡単なものでいいので')
        table_password.add_row('何かパスワードを設定してから、その設定したパスワードを入力してください。')
        table_password.add_row('なお、パスワードの設定後にインストーラーを起動し直す必要はありません。')
        table_password.add_row(CreateRule())
        table_password.add_row('ごく稀に、正しいパスワードを指定したのにログオンできない場合があります。')
        table_password.add_row('その場合は、一度インストーラーを Ctrl+C で中断し、インストーラーの')
        table_password.add_row('実行ファイルを Shift + 右クリック → [別のユーザーとして実行] から、')
        table_password.add_row('ログオン中のユーザーとパスワードを指定して再度実行してみてください。')
        print(Padding(table_password, (1, 2, 1, 2)))

        # ユーザーのパスワードを取得
        ## 対話モードでは、入力できているかを利用者が確認できるよう、入力中のパスワードをそのまま表示する
        current_user_password = answers.ask('service_password', f'ユーザー ({current_user_name}) のパスワード', is_secret=True)
        if current_user_password == '':
            answers.showInvalidInput(f'ユーザー ({current_user_name}) のパスワードが空です。')
            continue

        # サービスを登録する前に、ユーザー名とパスワードでログオンできるかを検証する
        ## 1326: ERROR_LOGON_FAILURE はユーザー名またはパスワードが間違っている場合に発生する
        ## それ以外のエラー (ログオンの種類が許可されていないなど) はパスワードの正否を判定できないため、そのまま登録を試みる
        logon_error_code = ValidateWindowsUserPassword(current_user_name, current_user_password)
        if logon_error_code == 1326:
            answers.showInvalidInput(
                f'ユーザー ({current_user_name}) のユーザー名またはパスワードが間違っています。\n'
                'Microsoft アカウントでサインインしている場合は、PIN ではなく、\n'
                'Microsoft アカウントのパスワードを入力してください。'
            )
            continue

        return WindowsServiceAccount(service_account='User', user_name=current_user_name, password=current_user_password)


def InstallWindowsService(
    install_path: Path,
    answers: InstallerAnswers,
    service_account: WindowsServiceAccount,
    question_number: int,
    network_folders: list[str],
    is_account_selection_supported: bool,
    stop_running_service: bool = False,
) -> bool:
    """
    KonomiTV の Windows サービスを、AskWindowsServiceAccount() で選ばれた実行アカウントでインストールし、起動する
    インストーラーと、サービスの実行アカウントの変更で共通の処理
    すでにサービスがインストールされている場合は、実行アカウントだけを変更する
    ユーザーが見つからない・ログオンに失敗したなど、入力で解決できる失敗は、対話モードでは実行アカウントを質問し直し、非対話モードでは InstallerAbortError を送出する
    それ以外の失敗は、エラーログを表示して False を返す

    Args:
        install_path (Path): KonomiTV のインストールフォルダ
        answers (InstallerAnswers): 質問への回答
        service_account (WindowsServiceAccount): 選ばれた実行アカウント
        question_number (int): 実行アカウントを質問し直すときに付ける番号
        network_folders (list[str]): 録画フォルダとキャプチャ画像の保存先のうち、ネットワーク上にあるフォルダ (質問し直すときに使う)
        is_account_selection_supported (bool): インストールした KonomiTV のサービス管理スクリプトが、LocalSystem での実行に対応しているか (質問し直すときに使う)
        stop_running_service (bool): インストールする前に、起動中のサービスを終了するかどうか

    Returns:
        bool: インストールと起動に成功したかどうか (入力で解決できない失敗の場合は False)
    """

    # Windows サービス管理スクリプトはパッケージマネージャー経由ではなく、仮想環境の Python 実行ファイルを直接実行する
    ## 以前 Poetry 経由で実行していた際、Windows で shell 解釈の影響を受けてパスワード中の記号が崩れる問題があったため
    venv_python_executable_path = install_path / 'server/.venv/Scripts/python.exe'

    while True:

        # 選ばれた実行アカウントに応じて、サービス管理スクリプトに渡す引数を組み立てる
        if service_account['service_account'] == 'LocalSystem':
            service_install_args: list[str | Path] = [
                venv_python_executable_path, 'KonomiTV-Service.py', 'install', '--local-system',
            ]
        else:
            service_install_args = [
                venv_python_executable_path, 'KonomiTV-Service.py', 'install',
                '--username', service_account['user_name'], '--password', service_account['password'],
            ]

        # 実行アカウントの変更は次にサービスを起動したときに反映されるため、起動中のサービスを終了する
        ## アカウントの選択とパスワードの検証が済んでから終了することで、入力を間違えても KonomiTV は起動したままになる
        if stop_running_service is True:
            ShowStep('起動中の Windows サービスを終了しています…')
            service_stop_result = subprocess.run(
                args = [venv_python_executable_path, 'KonomiTV-Service.py', 'stop'],
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )
            # 1060: ERROR_SERVICE_DOES_NOT_EXIST はサービスが登録されていない場合に発生するエラーのため無視する (この後新しく登録する)
            # 1062: ERROR_SERVICE_NOT_ACTIVE はサービスが起動していない場合に発生するエラーのため無視する
            if 'Error stopping service' in service_stop_result.stdout and \
                '(1060)' not in service_stop_result.stdout and '(1062)' not in service_stop_result.stdout:
                ShowSubProcessErrorLog(
                    error_message = '起動中の Windows サービスの終了中に予期しないエラーが発生しました。',
                    error_log = service_stop_result.stdout.strip(),
                )
                return False  # 処理中断

            # サービスの停止要求はサーバー本体やエンコーダーの終了を待たずに完了するため、
            # KonomiTV のフォルダ内のファイルを使うプロセスがすべて終了するまで待つ (残っていれば強制終了する)
            KillProcessesUnderDirectory(install_path)

        # 選ばれた実行アカウントで Windows サービスをインストール
        ## すでに KonomiTV Service がインストールされている場合は、実行アカウントだけが変更される
        ## 失敗の判定には終了コードと出力の両方を使う (古いサービス管理スクリプトは、失敗しても終了コード 0 で終了することがある)
        ShowStep('Windows サービスをインストールしています…')
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            service_install_result = subprocess.run(
                args = service_install_args,
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )
        # 入力されたユーザーが見つからない場合 (サービス管理スクリプトが "Error: " で始まるメッセージを出力する) は、入力の不正として質問し直す
        if service_account['service_account'] == 'User' and 'Error: ' in service_install_result.stdout:
            answers.showInvalidInput(
                'Windows サービスのインストールに失敗しました。\n'
                '入力されたユーザーが存在しないか、コンピューター名または\n'
                'ドメイン名が間違っている可能性があります。\n'
                'ユーザーが存在するにもかかわらず失敗する場合は、コンピューター名\n'
                'またはドメイン名を明示してユーザー名を入力してみてください。\n'
                '例: コンピューター名\\ユーザー名、.\\ユーザー名 (ローカル)\n'
                '　　ドメイン名\\ユーザー名 (ドメイン)\n'
                'エラーログ:\n' + service_install_result.stdout.strip()
            )
            service_account = AskWindowsServiceAccount(answers, question_number, network_folders, is_account_selection_supported)
            continue

        # それ以外の失敗は入力では解決できないため、処理の失敗として中断する
        if service_install_result.returncode != 0 or 'Error installing service' in service_install_result.stdout or \
            'Error changing service configuration' in service_install_result.stdout:
            ShowSubProcessErrorLog(
                error_message = 'Windows サービスのインストール中に予期しないエラーが発生しました。',
                error_log = service_install_result.stdout.strip(),
            )
            return False  # 処理中断

        # Windows サービスを起動
        ShowStep('Windows サービスを起動しています…')
        progress = CreateBasicInfiniteProgress()
        progress.add_task('', total=None)
        with progress:
            service_start_result = subprocess.run(
                args = [venv_python_executable_path, 'KonomiTV-Service.py', 'start'],
                cwd = install_path / 'server/',  # カレントディレクトリを KonomiTV サーバーのベースディレクトリに設定
                stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
                text = True,  # 出力をテキストとして取得する
            )
        # 1069: ERROR_SERVICE_LOGON_FAILED はサービスのログオンに失敗した場合に発生する
        ## パスワードは登録前に検証しているが、検証できないエラーで登録した場合はここで失敗するため、入力の不正として質問し直す
        if service_account['service_account'] == 'User' and service_start_result.returncode == 1069:
            answers.showInvalidInput(
                'Windows サービスの起動に失敗しました。\n'
                '入力されたログオン中ユーザーのパスワードが間違っている可能性があります。\n'
                'エラーログ:\n' + service_start_result.stdout.strip()
            )
            service_account = AskWindowsServiceAccount(answers, question_number, network_folders, is_account_selection_supported)
            continue

        # それ以外の失敗は入力では解決できないため、処理の失敗として中断する
        if service_start_result.returncode != 0 or 'Error starting service' in service_start_result.stdout:
            ShowSubProcessErrorLog(
                error_message = 'Windows サービスの起動中に予期しないエラーが発生しました。',
                error_log = service_start_result.stdout.strip(),
            )
            return False  # 処理中断

        # エラーが出ていなければおそらく正常にサービスがインストールできているはずなので、ループを抜ける
        return True


def IsDockerComposeV2() -> bool:
    """
    インストールされている Docker Compose がサブコマンド形式 (V2 以降) かどうか

    Docker Compose V2 以降は `docker compose` のようにサブコマンド形式で実行するが、
    V1 では `docker-compose` のようにスタンドアロンコマンドとして実行する必要がある。
    この関数は、`docker compose version` コマンドの終了コードで V2 以降かどうかを判定する。

    Returns:
        bool: Docker Compose V2 以降 (サブコマンド形式) なら True、V1 (またはインストールされていない) なら False
    """

    # Windows では常に False (サポートしていないため)
    if os.name == 'nt':
        return False

    # Docker コマンドが PATH に存在するか確認
    if shutil.which('docker') is None:
        return False

    # Docker Compose V2 以降 (サブコマンド形式) の存在確認
    # バージョン文字列のパターンマッチングではなく、コマンドの終了コードで判定する
    result = subprocess.run(
        args = ['docker', 'compose', 'version'],
        stdout = subprocess.DEVNULL,  # 標準出力を表示しない
        stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
    )
    return result.returncode == 0


def IsDockerInstalled() -> bool:
    """
    Linux に Docker + Docker Compose (V1, V2 以降は不問) がインストールされているかどうか
    Windows では Docker での構築はサポートしていない

    Returns:
        bool: Docker + Docker Compose がインストールされていれば True、インストールされていなければ False
    """

    # Windows では常に False (サポートしていないため)
    if os.name == 'nt':
        return False

    # Docker コマンドが PATH に存在するか確認
    if shutil.which('docker') is None:
        return False  # Docker がインストールされていない

    # Docker Compose V2 以降 (サブコマンド形式) の存在確認
    # バージョン文字列のパターンマッチングではなく、コマンドの終了コードで判定する
    docker_compose_v2_result = subprocess.run(
        args = ['docker', 'compose', 'version'],
        stdout = subprocess.DEVNULL,  # 標準出力を表示しない
        stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
    )
    if docker_compose_v2_result.returncode == 0:
        return True  # Docker と Docker Compose V2 以降がインストールされている

    # Docker Compose V1 (スタンドアロン形式) の存在確認
    # shutil.which() で docker-compose コマンドの存在を確認
    if shutil.which('docker-compose') is not None:
        return True  # Docker と Docker Compose V1 がインストールされている

    return False  # Docker はインストールされているが、Docker Compose がインストールされていない


def IsGitInstalled() -> bool:
    """
    Git コマンドがインストールされているかどうか

    Returns:
        bool: Git コマンドがインストールされていれば True 、インストールされていなければ False
    """

    # shutil.which() で git コマンドが PATH に存在するか確認
    # Windows / Linux 両方で動作する
    return shutil.which('git') is not None


def IsNetworkPath(path: str) -> bool:
    """
    Windows で、指定されたパスがネットワーク上のフォルダ (UNC パスまたはネットワークドライブ) かどうか
    LocalSystem で実行する Windows サービスからはアクセスできないため、既定の実行アカウントの決定に使う
    インストーラーの起動時にログオン中ユーザーのネットワークドライブをマウントしているため、ドライブの種類を判定できる

    Args:
        path (str): 判定するパス

    Returns:
        bool: ネットワーク上のフォルダなら True 、それ以外 (Windows 以外を含む) なら False
    """

    if sys.platform != 'win32':
        return False

    import ctypes

    # \\server\share 形式の UNC パス
    if path.startswith('\\\\'):
        return True

    # ドライブレターがネットワークドライブに割り当てられているか
    ## 4: DRIVE_REMOTE はネットワークドライブを表す
    drive = Path(path).drive
    if drive == '':
        return False
    DRIVE_REMOTE = 4
    return ctypes.windll.kernel32.GetDriveTypeW(drive + '\\') == DRIVE_REMOTE


def KillProcessesUnderDirectory(directory: Path, timeout: float = 15.0) -> None:
    """
    指定したフォルダ配下の実行ファイルから起動されたプロセスの終了を待ち、timeout 秒経っても残っているプロセスを強制終了する
    Windows サービスの停止要求は、サーバー本体 (仮想環境の python.exe) や NVEncC などの子プロセスの終了を待たずに完了するため、
    その直後にファイルを上書き・削除すると、実行中のプロセスに開かれている .exe・.dll・.pyd が PermissionError で削除できない
    サービスの停止後にこの関数を呼び、KonomiTV のフォルダ内のファイルを使うプロセスがすべて終了してから更新・削除を行う

    Args:
        directory (Path): KonomiTV のインストールフォルダ
        timeout (float): 自然に終了するのを待つ秒数
    """

    directory_prefix = os.path.normcase(str(directory.resolve())) + os.sep

    # インストーラー自身とその親プロセスは、インストールフォルダ内から実行されていても対象から除外する
    excluded_pids = {os.getpid()}
    for parent in psutil.Process().parents():
        excluded_pids.add(parent.pid)

    def GetProcessesUnderDirectory() -> list[psutil.Process]:
        processes: list[psutil.Process] = []
        for process in psutil.process_iter(['pid', 'exe']):
            # 権限の都合で実行ファイルのパスを取得できないプロセス (システムのプロセスなど) は exe が None になる
            executable_path = process.info['exe']
            if executable_path is None or process.info['pid'] in excluded_pids:
                continue
            if os.path.normcase(executable_path).startswith(directory_prefix):
                processes.append(process)
        return processes

    # 停止処理中のプロセスが自然に終了するのを待つ
    deadline = time.monotonic() + timeout
    while len(GetProcessesUnderDirectory()) > 0 and time.monotonic() < deadline:
        time.sleep(0.5)

    # timeout 秒経っても残っているプロセスを強制終了し、終了を待つ
    remaining_processes = GetProcessesUnderDirectory()
    for process in remaining_processes:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass  # 一覧を取得した後に終了したプロセス
    psutil.wait_procs(remaining_processes, timeout=10)


def RemoveDirectory(directory: Path) -> None:
    """
    フォルダを中のファイルごと削除する
    読み取り専用属性のファイル (.git/ 以下など) は、属性を外してから削除する
    Windows ではウイルス対策ソフトのスキャンなどでファイルが一時的にロックされることがあるため、削除できなければ約10秒間再試行する
    それでも削除できない場合は、ロックされているファイルと対処方法を記載した PermissionError を送出する

    Args:
        directory (Path): 削除するフォルダ (存在しない場合は何もしない)
    """

    if directory.exists() is False:
        return

    # 読み取り専用属性のファイルを削除できるようにする
    # ref: https://stackoverflow.com/a/4829285/17124142
    ## 属性を外しても削除できない場合 (ロックされている場合) は、ここで送出された PermissionError を下で捕捉して再試行する
    def OnRemoveError(function: Callable[[str], Any], path: str, exception: BaseException) -> None:
        os.chmod(path, stat.S_IWRITE)
        function(path)

    retry_count = 20
    for retry in range(retry_count):
        try:
            shutil.rmtree(directory, onexc=OnRemoveError)
            return
        except PermissionError as ex:
            if retry == retry_count - 1:
                raise PermissionError(
                    f'{ex.filename} を削除できませんでした。'
                    'このファイルを使用しているプログラム (KonomiTV のサービスやエンコーダーなど) を終了するか、'
                    'PC を再起動してから、もう一度やり直してください。'
                ) from ex
            time.sleep(0.5)


def RemoveEmojiIfLegacyTerminal(text: str) -> str:
    """
    絵文字が表示できない Windows のレガシーターミナル (conhost.exe) のときのみ絵文字を除去する

    Args:
        text (str): 絵文字の含まれた文字列

    Returns:
        str: レガシーターミナル以外ではそのまま、レガシーターミナルでは絵文字が除去された文字列
    """

    if rich.console.detect_legacy_windows() is True:
        # emoji パッケージを使って絵文字を除去する
        # ref: https://stackoverflow.com/a/51785357/17124142
        # ref: https://carpedm20.github.io/emoji/docs/
        return emoji.replace_emoji(text, '')
    else:
        return text


def SaveConfig(config_yaml_path: Path, config_dict: dict[str, dict[str, Any]]) -> None:
    """
    変更されたサーバー設定データを、コメントやフォーマットを保持した形で config.yaml に書き込む
    server.app.config.SaveConfig の実装を簡略化したもの

    Args:
        config_yaml_path (Path): 保存する config.yaml のパス
        config_dict (dict[str, dict[str, Any]]): 保存するサーバー設定データ
    """

    # config.yaml の内容をロード
    yaml = ruamel.yaml.YAML()
    yaml.default_flow_style = None  # None を使うと、スカラー以外のものはブロックスタイルになる
    yaml.preserve_quotes = True
    yaml.width = 20
    yaml.indent(mapping=4, sequence=4, offset=4)
    try:
        with open(config_yaml_path, encoding='utf-8') as file:
            config_raw = yaml.load(file)
    except Exception as error:
        # 回復不可能
        raise RuntimeError(f'Failed to load config.yaml: {error}')

    # config.yaml の内容を更新して保存
    # コメントやフォーマットを保持して保存するために更新方法を工夫している
    for key in config_dict:
        for sub_key in config_dict[key]:
            # 文字列のリストを更新する場合は clear() と extend() を使う
            if type(config_dict[key][sub_key]) is list:
                if type(config_raw[key][sub_key]) is ruamel.yaml.CommentedSeq:
                    config_raw[key][sub_key].clear()
                    for item in config_dict[key][sub_key]:
                        config_raw[key][sub_key].append(ruamel.yaml.scalarstring.SingleQuotedScalarString(item))
                else:
                    config_raw[key][sub_key] = ruamel.yaml.CommentedSeq(config_dict[key][sub_key])
            # 文字列は明示的に SingleQuotedScalarString に変換する
            elif type(config_dict[key][sub_key]) is str:
                config_raw[key][sub_key] = ruamel.yaml.scalarstring.SingleQuotedScalarString(config_dict[key][sub_key])
            else:
                config_raw[key][sub_key] = config_dict[key][sub_key]

    # None を null として出力するようにする
    yaml.Representer.add_representer(type(None), lambda self, data: self.represent_scalar('tag:yaml.org,2002:null', 'null'))  # type: ignore

    # 配列の末尾の "']" を "',\n    ]" に変換する transform 関数を定義
    # 基本的に recorded_folders 用 (ruamel.yaml がフロースタイルの改行などを保持できないための苦肉の策)
    def transform(value: str) -> str:
        return value.replace("']", "',\n    ]")

    with open(config_yaml_path, mode='w', encoding='utf-8') as file:
        yaml.dump(config_raw, file, transform=transform)


def CreateBasicInfiniteProgress() -> Progress:
    """
    シンプルな完了未定状態向けの Progress インスタンスを新しく生成して返す

    Returns:
        Progress: 進捗表示に使うProgress インスタンス
    """
    return Progress(
        TextColumn(' '),
        BarColumn(bar_width=9999),
        TimeElapsedColumn(),
        TextColumn(' '),
    )


def CreateDownloadProgress() -> Progress:
    """
    ダウンロード時向けの Progress インスタンスを新しく生成して返す

    Returns:
        Progress: 進捗表示に使うProgress インスタンス
    """
    return Progress(
        TextColumn(' '),
        BarColumn(bar_width=9999),
        '[progress.percentage]{task.percentage:>3.1f}%',
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        TextColumn(' '),
    )


def CreateDownloadInfiniteProgress() -> Progress:
    """
    ダウンロード時 (完了未定) 向けの Progress インスタンスを新しく生成して返す

    Returns:
        Progress: 進捗表示に使うProgress インスタンス
    """
    return Progress(
        TextColumn(' '),
        BarColumn(bar_width=9999),
        DownloadColumn(),
        TimeElapsedColumn(),
        TextColumn(' '),
    )


def CreateRule() -> Rule:
    """
    ルールを新しく生成して返す

    Returns:
        Rule: ルール (区切り線)
    """
    return Rule(characters='─', style=Style(color='#E33157'))


def CreateTable() -> Table:
    """
    テーブルを新しく生成して返す

    Returns:
        Table: テーブル
    """
    return Table(expand=True, box=box.SQUARE, border_style=Style(color='#E33157'))


def GetLogFileSizes(base_path: Path) -> dict[str, int]:
    """
    KonomiTV のログフォルダにあるログファイルのサイズを取得する
    サービスを起動する前に取得し、RunKonomiTVServiceWaiter() に渡す

    Args:
        base_path (Path): KonomiTV のベースパス

    Returns:
        dict[str, int]: ログファイルのパスとサイズの辞書 (ログフォルダがまだない場合は空)
    """

    log_file_sizes: dict[str, int] = {}
    for log_path in (base_path / 'server/logs/').glob('*.log'):
        log_file_sizes[str(log_path)] = log_path.stat().st_size
    return log_file_sizes


def RunKonomiTVServiceWaiter(
    platform_type: Literal['Windows', 'Linux', 'Linux-Docker'],
    base_path: Path,
    initial_log_sizes: dict[str, int],
) -> bool:
    """
    KonomiTV が起動するまで監視し、起動が完了するのを待つ

    Args:
        platform_type (Literal['Windows', 'Linux', 'Linux-Docker']): プラットフォームの種類
        base_path (Path): KonomiTV のベースパス
        initial_log_sizes (dict[str, int]): サービスを起動する前に GetLogFileSizes() で取得したログファイルのサイズ

    Returns:
        bool: KonomiTV の起動が完了したかどうか (起動に失敗した場合は False)
    """

    # サービスが起動したかのフラグ
    is_service_started = False

    # KonomiTV サーバーが起動したかのフラグ
    is_server_started = False

    # 番組情報更新が完了して起動したかのフラグ
    is_programs_update_completed = False

    # 起動中にエラーが発生した場合のフラグ
    is_error_occurred = False

    def ScanAppendedLog(log_path: Path) -> None:
        """
        ログファイルのうち、サービスを起動した後に追記された部分を読み、起動の状態を表すフラグを更新する
        ログファイルは起動のたびに追記されるため、前回の起動時のログに含まれる起動完了やエラーの文字列は読まない

        Args:
            log_path (Path): ログファイルのパス
        """

        nonlocal is_server_started, is_programs_update_completed, is_error_occurred
        with open(log_path, mode='rb') as log:
            # サービスを起動した後に追記された部分だけを読む
            ## ファイルがサービスを起動する前より小さくなっている場合は、作り直されたとみなして先頭から読む
            ## サーバーが書き込んでいる途中の行を読むことがあるため、UTF-8 として不正なバイト列は置き換える
            initial_log_size = initial_log_sizes.get(str(log_path), 0)
            if log_path.stat().st_size >= initial_log_size:
                log.seek(initial_log_size)
            text = log.read().decode('utf-8', errors='replace')
        if 'ERROR:' in text or 'Traceback (most recent call last):' in text:
            # 何らかのエラーが発生したことが想定されるので、エラーフラグを立てる
            is_error_occurred = True
        if 'Waiting for application startup.' in text:
            # サーバーの起動が完了した事が想定されるので、サーバー起動フラグを立てる
            is_server_started = True
        if 'Application startup complete.' in text:
            # 番組情報の更新が完了した事が想定されるので、番組情報更新完了フラグを立てる
            is_programs_update_completed = True

    # ログフォルダ以下のファイルに変更があったときのイベントハンドラー
    class LogFolderWatchHandler(FileSystemEventHandler):

        # 何かしらログフォルダに新しいファイルが作成されたら、サービスが起動したものとみなす
        def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
            nonlocal is_service_started
            is_service_started = True

        # ログファイルが更新されたら、ログの中に Application startup complete. という文字列が含まれていないかを探す
        # ログの中に Application startup complete. という文字列が含まれていたら、KonomiTV サーバーの起動が完了したとみなす
        def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
            # もし on_created をハンドリングできなかった場合に備え、on_modified でもサービス起動フラグを立てる
            nonlocal is_service_started
            is_service_started = True
            # ファイルのみに限定（フォルダの変更も検知されることがあるが、当然フォルダは開けないのでエラーになる）
            if Path(str(event.src_path)).is_file() is True:
                ScanAppendedLog(Path(str(event.src_path)))

    # Watchdog を起動
    ## 通常の OS のファイルシステム変更通知 API を使う Observer だとなかなか検知できないことがあるみたいなので、
    ## 代わりに PollingObserver を使う
    observer = PollingObserver()
    observer.schedule(LogFolderWatchHandler(), str(base_path / 'server/logs/'), recursive=True)
    observer.start()

    # 監視を始めるまでの間 (サービスを起動してからこの関数が呼ばれるまで) に追記された部分は変更通知が届かないため、ここで一度読む
    ## 監視の開始後に追記された部分は変更通知でも読むが、どちらもフラグを立てるだけなので同じ結果になる
    for log_path in (base_path / 'server/logs/').glob('*.log'):
        if log_path.stat().st_size != initial_log_sizes.get(str(log_path), 0):
            is_service_started = True
            ScanAppendedLog(log_path)

    # サービスが起動するまで待つ
    ShowStep('サービスの起動を待っています… (時間がかかることがあります)')
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        while is_service_started is False:
            if platform_type == 'Windows':
                # 起動したはずの Windows サービスが停止してしまっている場合はエラーとする
                service_status_result = subprocess.run(
                    args = ['sc', 'query', 'KonomiTV Service'],
                    stdout = subprocess.PIPE,  # 標準出力をキャプチャする
                    stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
                    text = True,  # 出力をテキストとして取得する
                )
                if 'STOPPED' in service_status_result.stdout:
                    ShowPanel([
                        '[red]KonomiTV サーバーの起動に失敗しました。[/red]',
                        'お手数をおかけしますが、イベントビューアーにエラーログが',
                        '出力されている場合は、そのログを開発者に報告してください。',
                    ])
                    return False  # 処理中断
            time.sleep(0.1)

    # KonomiTV サーバーが起動するまで待つ
    ShowStep('KonomiTV サーバーの起動を待っています… (時間がかかることがあります)')
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        while is_server_started is False:
            if is_error_occurred is True:
                with open(base_path / 'server/logs/KonomiTV-Server.log', encoding='utf-8') as log:
                    ShowSubProcessErrorLog(
                        error_message = 'KonomiTV サーバーの起動中に予期しないエラーが発生しました。',
                        error_log_name = 'KonomiTV サーバーのログ',
                        error_log = log.read(),
                    )
                    return False  # 処理中断
            time.sleep(0.1)

    # 番組情報更新が完了するまで待つ
    ShowStep('すべてのチャンネルの番組情報を取得しています… (数秒～数分かかります)')
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        while is_programs_update_completed is False:
            if is_error_occurred is True:
                with open(base_path / 'server/logs/KonomiTV-Server.log', encoding='utf-8') as log:
                    ShowSubProcessErrorLog(
                        error_message = '番組情報の取得中に予期しないエラーが発生しました。',
                        error_log_name = 'KonomiTV サーバーのログ',
                        error_log = log.read(),
                    )
                    return False  # 処理中断
            time.sleep(0.1)

    return True


def RunSubprocess(
    name: str,
    args: list[str | Path],
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    error_message: str = '予期しないエラーが発生しました。',
    error_log_name: str = 'エラーログ',
) -> bool:
    """
    サブプロセスを実行する。

    Args:
        name (str): 表示する実行中タスクの名前
        args (list[str]): 実行するコマンド
        cwd (Path): カレントディレクトリ
        environment (dict[str, str], optional): 追加の環境変数. Defaults to None.
        error_message (str, optional): エラー発生時のエラーメッセージ. Defaults to '予期しないエラーが発生しました。'.
        error_log_name (str, optional): エラー発生時のエラーログ名. Defaults to 'エラーログ'.

    Returns:
        bool: 成功したかどうか
    """

    # OS デフォルトの環境変数をコピーし、その上に追加の環境変数を適用する
    ## OS デフォルトの環境変数がないと、Windows で名前解決に失敗したりなどの予期しない問題が発生する
    env = os.environ.copy()
    if environment is not None:
        env.update(environment)

    ShowStep(name)
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        result = subprocess.run(
            args = args,
            cwd = cwd,
            env = env,
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.STDOUT,  # 標準エラー出力を標準出力にリダイレクト
            text = True,  # 出力をテキストとして取得する
        )

    if result.returncode != 0:
        ShowSubProcessErrorLog(
            error_message = error_message,
            error_log_name = error_log_name,
            error_log = result.stdout,
        )
        return False

    return True


def RunSubprocessDirectLogOutput(
    name: str,
    args: list[str | Path],
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
    error_message: str = '予期しないエラーが発生しました。',
) -> bool:
    """
    サブプロセスを実行する。(ログをそのまま出力する)

    Args:
        name (str): 表示する実行中タスクの名前
        args (list[str]): 実行するコマンド
        cwd (Path): カレントディレクトリ
        environment (dict[str, str], optional): 追加の環境変数. Defaults to None.
        error_message (str, optional): エラー発生時のエラーメッセージ. Defaults to '予期しないエラーが発生しました。'.

    Returns:
        bool: 成功したかどうか
    """

    # OS デフォルトの環境変数をコピーし、その上に追加の環境変数を適用する
    ## OS デフォルトの環境変数がないと、Windows で名前解決に失敗したりなどの予期しない問題が発生する
    env = os.environ.copy()
    if environment is not None:
        env.update(environment)

    print(Padding(name, (1, 2, 1, 2)))
    EmitJSONProgress('step', message=name)
    print(Rule(style=Style(color='cyan'), align='center'))
    # --json-progress が指定されているときは、標準出力を JSON の進捗だけにするため、サブプロセスのログを標準エラー出力に出力する
    subprocess_result = subprocess.run(
        args,
        cwd = cwd,
        env = env,
        stdout = sys.stderr if _is_json_progress_enabled is True else None,
    )
    print(Rule(style=Style(color='cyan'), align='center'))

    if subprocess_result.returncode != 0:
        ShowPanel([
            f'[red]{error_message}[/red]'
            'お手数をおかけしますが、上記のログを開発者に報告してください。',
        ])
        return False

    return True


def ShowPanel(message: list[str], padding: tuple[int, int, int, int] = (1, 2, 0, 2)) -> None:
    """
    パネルを表示する

    Args:
        message (list[str]): パネルに表示するメッセージのリスト
        padding (tuple[int], optional): パネルのパディング. Defaults to (1, 2, 0, 2).
    """
    print(Padding(Panel(
        '\n'.join(message),
        box = box.SQUARE,
        border_style = Style(color='#E33157'),
    ), padding))

    # エラーと警告のパネルは、先頭行を [red] または [yellow] で始める書き方に統一しているため、それを JSON の進捗にも出力する
    ## JSON にはマークアップを取り除いたプレーンテキストを出力する
    if len(message) > 0 and message[0].startswith('[red]'):
        EmitJSONProgress('error', message=Text.from_markup('\n'.join(message)).plain)
    elif len(message) > 0 and message[0].startswith('[yellow]'):
        EmitJSONProgress('warning', message=Text.from_markup('\n'.join(message)).plain)


def ShowStep(message: str) -> None:
    """
    インストールなどの処理の工程を表示する
    --json-progress が指定されているときは、JSON の進捗にも出力する

    Args:
        message (str): 工程の説明 (「〜しています…」の形で書く)
    """

    print(Padding(message, (1, 2, 0, 2)))
    EmitJSONProgress('step', message=message)


def ShowSubProcessErrorLog(
        error_message: str = '予期しないエラーが発生しました。',
        error_log_name: str = 'エラーログ',
        error_log: str = '',
    ) -> None:
    """
    サブプロセスのエラーログを表示する

    Args:
        error_message (str): エラーメッセージ
        error_log (str): エラーログ
        error_log_name (str): エラーログの名前
    """

    ShowPanel([
        f'[red]{error_message}[/red]',
        'お手数をおかけしますが、下記のログを開発者に報告してください。',
    ])
    ShowPanel([
        f'{error_log_name}:\n' + error_log.strip(),
    ], padding=(0, 2, 0, 2))
