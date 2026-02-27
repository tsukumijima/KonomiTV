
import asyncio
import datetime
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import Any, Literal, TypeVar, cast
from zoneinfo import ZoneInfo

import aiofiles
import emoji
import ifaddr
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
from rich.text import TextType
from typing_extensions import TypedDict
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


def RunKonomiTVServiceWaiter(platform_type: Literal['Windows', 'Linux', 'Linux-Docker'], base_path: Path) -> None:
    """
    KonomiTV が起動するまで監視し、起動が完了するのを待つ

    Args:
        platform_type (Literal['Windows', 'Linux', 'Linux-Docker']): プラットフォームの種類
        base_path (Path): KonomiTV のベースパス
    """

    # サービスが起動したかのフラグ
    is_service_started = False

    # KonomiTV サーバーが起動したかのフラグ
    is_server_started = False

    # 番組情報更新が完了して起動したかのフラグ
    is_programs_update_completed = False

    # 起動中にエラーが発生した場合のフラグ
    is_error_occurred = False

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
            nonlocal is_service_started, is_server_started, is_programs_update_completed, is_error_occurred
            is_service_started = True
            # ファイルのみに限定（フォルダの変更も検知されることがあるが、当然フォルダは開けないのでエラーになる）
            if Path(str(event.src_path)).is_file() is True:
                with open(event.src_path, encoding='utf-8') as log:
                    text = log.read()
                    if 'ERROR:' in text or 'Traceback (most recent call last):' in text:
                        # 何らかのエラーが発生したことが想定されるので、エラーフラグを立てる
                        is_error_occurred = True
                    if 'Waiting for application startup.' in text:
                        # サーバーの起動が完了した事が想定されるので、サーバー起動フラグを立てる
                        is_server_started = True
                    if 'Application startup complete.' in text:
                        # 番組情報の更新が完了した事が想定されるので、番組情報更新完了フラグを立てる
                        is_programs_update_completed = True

    # Watchdog を起動
    ## 通常の OS のファイルシステム変更通知 API を使う Observer だとなかなか検知できないことがあるみたいなので、
    ## 代わりに PollingObserver を使う
    observer = PollingObserver()
    observer.schedule(LogFolderWatchHandler(), str(base_path / 'server/logs/'), recursive=True)
    observer.start()

    # サービスが起動するまで待つ
    print(Padding('サービスの起動を待っています… (時間がかかることがあります)', (1, 2, 0, 2)))
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
                    return  # 処理中断
            time.sleep(0.1)

    # KonomiTV サーバーが起動するまで待つ
    print(Padding('KonomiTV サーバーの起動を待っています… (時間がかかることがあります)', (1, 2, 0, 2)))
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
                    return  # 処理中断
            time.sleep(0.1)

    # 番組情報更新が完了するまで待つ
    print(Padding('すべてのチャンネルの番組情報を取得しています… (数秒～数分かかります)', (1, 2, 0, 2)))
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
                    return  # 処理中断
            time.sleep(0.1)


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

    print(Padding(name, (1, 2, 0, 2)))
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
    print(Rule(style=Style(color='cyan'), align='center'))
    subprocess_result = subprocess.run(args, cwd = cwd, env = env)
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
