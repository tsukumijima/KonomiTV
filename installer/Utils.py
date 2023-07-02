
import aiofiles
import asyncio
import emoji
import datetime
import ifaddr
import os
import re
import rich
import subprocess
import time
from pathlib import Path
from rich import box
from rich import print
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress
from rich.progress import (
    BarColumn,
    DownloadColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm
from rich.prompt import Prompt
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import TextType
from typing import Callable, cast, Literal, Optional, TypedDict, TypeVar
from watchdog.events import FileCreatedEvent
from watchdog.events import FileModifiedEvent
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver


class CustomPrompt(Prompt):
    """ カスタムの Rich プロンプトの実装 """

    def __init__(
        self,
        prompt: TextType = "",
        *,
        console: Optional[Console] = None,
        password: bool = False,
        choices: Optional[list[str]] = None,
        show_default: bool = True,
        show_choices: bool = True,
    ) -> None:

        if type(prompt) is str:
            prompt = f'  {prompt}'  # 左に半角スペース2つ分余白を空ける

        # 親クラスのコンストラクタを実行
        super().__init__(prompt, console=console, password=password, choices=choices, show_default=show_default, show_choices=show_choices)

        if self.choices is not None:
            self.illegal_choice_message = Padding(f'[prompt.invalid.choice][{"/".join(self.choices)}] のいずれかを選択してください！', (0, 2, 0, 2))


class CustomConfirm(Confirm):
    """ カスタムの Rich コンファームの実装 """
    validate_error_message = "[prompt.invalid]Y or N のいずれかを入力してください！"

    def __init__(
        self,
        prompt: TextType = "",
        *,
        console: Optional[Console] = None,
        password: bool = False,
        choices: Optional[list[str]] = None,
        show_default: bool = True,
        show_choices: bool = True,
    ) -> None:

        if type(prompt) is str:
            prompt = f'  {prompt}'  # 左に半角スペース2つ分余白を空ける

        # 親クラスのコンストラクタを実行
        super().__init__(prompt, console=console, password=password, choices=choices, show_default=show_default, show_choices=show_choices)


# ジェネリック型
T = TypeVar('T')

class ServiceInfo(TypedDict):
    """ サービス情報 """
    onid: int
    tsid: int
    sid: int
    service_type: int
    partial_reception_flag: int
    service_provider_name: str
    service_name: str
    network_name: str
    ts_name: str
    remote_control_key_id: int

class CtrlCmdConnectionCheckUtil:
    """ server/app/utils/EDCB.py の CtrlCmdUtil クラスのうち、接続確認に必要なロジックだけを抜き出したもの"""

    # EDCB の日付は OS のタイムゾーンに関わらず常に UTC+9
    TZ = datetime.timezone(datetime.timedelta(hours=9), 'JST')

    # 読み取った日付が不正なときや既定値に使う UNIX エポック
    UNIX_EPOCH = datetime.datetime(1970, 1, 1, 9, tzinfo=TZ)

    __connect_timeout_sec: float
    __pipe_name: str
    __host: str | None
    __port: int

    def __init__(self, hostname: str, port: int | None) -> None:
        self.__connect_timeout_sec = 10  # 10秒でタイムアウト
        self.__pipe_name = 'EpgTimerSrvNoWaitPipe'
        self.__host = None
        self.__port = 0

        if hostname == 'edcb-namedpipe':
            # 特別に名前付きパイプモードにする
            self.__pipe_name = 'EpgTimerSrvNoWaitPipe'
            self.__host = None
        else:
            # TCP/IP モードにする
            self.__host = hostname
            self.__port = cast(int, port)

    async def sendEnumService(self) -> list[ServiceInfo] | None:
        """ サービス一覧を取得する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_ENUM_SERVICE)
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readVector(self.__readServiceInfo, memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    # EDCB/EpgTimer の CtrlCmd.cs より
    __CMD_SUCCESS = 1
    __CMD_EPG_SRV_ENUM_SERVICE = 1021

    async def __sendAndReceive(self, buf: bytearray) -> tuple[int | None, bytes]:
        to = time.monotonic() + self.__connect_timeout_sec
        if self.__host is None:
            # 名前付きパイプモード
            while True:
                try:
                    async with aiofiles.open('\\\\.\\pipe\\' + self.__pipe_name, mode='r+b') as f:
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

        # TCP/IP モード
        try:
            connection = await asyncio.wait_for(asyncio.open_connection(self.__host, self.__port), max(to - time.monotonic(), 0.))
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

    async def __sendCmd(self, cmd: int, write_func: Callable[[bytearray], None] | None = None) -> tuple[int | None, bytes]:
        buf = bytearray()
        self.__writeInt(buf, cmd)
        self.__writeInt(buf, 0)
        if write_func:
            write_func(buf)
        self.__writeIntInplace(buf, 4, len(buf) - 8)
        return await self.__sendAndReceive(buf)

    @staticmethod
    def __writeInt(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(4, 'little', signed=True))

    @staticmethod
    def __writeIntInplace(buf: bytearray, pos: int, v: int) -> None:
        buf[pos:pos + 4] = v.to_bytes(4, 'little', signed=True)

    class __ReadError(Exception):
        """ バッファをデータ構造として読み取るのに失敗したときの内部エラー """
        pass

    @classmethod
    def __readByte(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 1:
            raise cls.__ReadError
        v = buf[pos[0]]
        pos[0] += 1
        return v

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
    def __readString(cls, buf: memoryview, pos: list[int], size: int) -> str:
        vs = cls.__readInt(buf, pos, size)
        if vs < 6 or size - pos[0] < vs - 4:
            raise cls.__ReadError
        v = str(buf[pos[0]:pos[0] + vs - 6], 'utf_16_le')
        pos[0] += vs - 4
        return v

    @classmethod
    def __readVector(cls, read_func: Callable[[memoryview, list[int], int], T], buf: memoryview, pos: list[int], size: int) -> list[T]:
        vs = cls.__readInt(buf, pos, size)
        vc = cls.__readInt(buf, pos, size)
        if vs < 8 or vc < 0 or size - pos[0] < vs - 8:
            raise cls.__ReadError
        size = pos[0] + vs - 8
        v: list[T] = []
        for _ in range(vc):
            v.append(read_func(buf, pos, size))
        pos[0] = size
        return v

    @classmethod
    def __readStructIntro(cls, buf: memoryview, pos: list[int], size: int) -> int:
        vs = cls.__readInt(buf, pos, size)
        if vs < 4 or size - pos[0] < vs - 4:
            raise cls.__ReadError
        return pos[0] + vs - 4

    # 以下、各構造体のリーダー

    @classmethod
    def __readServiceInfo(cls, buf: memoryview, pos: list[int], size: int) -> ServiceInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: ServiceInfo = {
            'onid': cls.__readUshort(buf, pos, size),
            'tsid': cls.__readUshort(buf, pos, size),
            'sid': cls.__readUshort(buf, pos, size),
            'service_type': cls.__readByte(buf, pos, size),
            'partial_reception_flag': cls.__readByte(buf, pos, size),
            'service_provider_name': cls.__readString(buf, pos, size),
            'service_name': cls.__readString(buf, pos, size),
            'network_name': cls.__readString(buf, pos, size),
            'ts_name': cls.__readString(buf, pos, size),
            'remote_control_key_id': cls.__readByte(buf, pos, size)
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
    if os.name != 'nt': return []

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
    インストールされている Docker Compose が V2 かどうか

    Returns:
        bool: Docker Compose V2 なら True 、V1 (またはインストールされていない) なら False
    """

    # Windows では常に False (サポートしていないため)
    if os.name == 'nt': return False

    try:
        # Docker Compose V2 の存在確認
        docker_compose_v2_result = subprocess.run(
            args = ['docker', 'compose', 'version'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        )
        if docker_compose_v2_result.returncode == 0 and any(x in docker_compose_v2_result.stdout for x in
                                                            ('Docker Compose version v2', 'Docker Compose version 2')):
            return True  #  Docker Compose V2 がインストールされている
    except FileNotFoundError:
        pass

    # Docker Compose V2 がインストールされていないので消去法で V1 だと確定する
    return False


def IsDockerInstalled() -> bool:
    """
    Linux に Docker + Docker Compose (V1, V2 は不問) がインストールされているかどうか
    Windows では Docker での構築はサポートしていない

    Returns:
        bool: Docker + Docker Compose がインストールされていれば True 、インストールされていなければ False
    """

    # Windows では常に False (サポートしていないため)
    if os.name == 'nt': return False

    try:

        # Docker コマンドの存在確認
        docker_result = subprocess.run(
            args = ['/usr/bin/bash', '-c', 'type docker'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )
        if docker_result.returncode != 0:
            return False  # Docker がインストールされていない

        # Docker Compose V2 の存在確認
        docker_compose_v2_result = subprocess.run(
            args = ['docker', 'compose', 'version'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        )
        if docker_compose_v2_result.returncode == 0 and any(x in docker_compose_v2_result.stdout for x in
                                                            ('Docker Compose version v2', 'Docker Compose version 2')):
            return True  # Docker と Docker Compose V2 がインストールされている

        # Docker Compose V1 の存在確認
        docker_compose_v1_result = subprocess.run(
            args = ['docker-compose', 'version'],
            stdout = subprocess.PIPE,  # 標準出力をキャプチャする
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
            text = True,  # 出力をテキストとして取得する
        )
        if docker_compose_v1_result.returncode == 0 and 'docker-compose version 1' in docker_compose_v1_result.stdout:
            return True  # Docker と Docker Compose V1 がインストールされている

        return False  # Docker はインストールされているが、Docker Compose がインストールされていない

    # subprocess.run() で万が一 FileNotFoundError が送出された場合、
    # コマンドが存在しないことによる例外のため、インストールされていないものと判断する
    except FileNotFoundError:
        return False


def IsGitInstalled() -> bool:
    """
    Git コマンドがインストールされているかどうか

    Returns:
        bool: Git コマンドがインストールされていれば True 、インストールされていなければ False
    """

    ## Windows
    if os.name == 'nt':
        result = subprocess.run(
            args = ['C:/Windows/System32/where.exe', 'git'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )
        if result.returncode == 0:
            return True
    ## Linux
    else:
        result = subprocess.run(
            args = ['/usr/bin/bash', '-c', 'type git'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )
        if result.returncode == 0:
            return True

    return False


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


def SaveConfigYaml(config_yaml_path: Path, config_data: dict[str, dict[str, int |float | bool | str | None]]) -> None:
    """
    変更されたサーバー設定データを、コメントやフォーマットを保持した形で config.yaml に書き込む
    config.yaml のすべてを上書きするのではなく、具体的な値が記述されている部分のみ正規表現で置換している

    Args:
        config_yaml_path (Path): 保存する config.yaml のパス
        config_data (dict[str, dict[str, int | float | bool | str | None]]): サーバー設定データの辞書
    """

    # 現在の config.yaml の内容を行ごとに取得
    current_lines: list[str]
    with open(config_yaml_path, mode='r', encoding='utf-8') as file:
        current_lines = file.readlines()

    # 新しく作成する config.yaml の内容が入るリスト
    ## このリストに格納された値を、最後に文字列として繋げて書き込む
    new_lines: list[str] = []

    # config.yaml の行ごとに実行
    ## 以下の実装は、キーが必ずシングルクオートかダブルクオートで囲われている事、1階層目に直接バリューが入らない事、
    ## 親キーが半角スペース4つ、その配下にあるキーが半角スペース8つでインデントされている事などを前提としたもの
    ## KonomiTV の config.yaml のフォーマットにのみ適合するもので、汎用性はない
    current_parent_key: str = ''  # 現在処理中の親キー
    for current_line in current_lines:

        # 'general': { のような記述にマッチする正規表現を実行
        parent_key_match_pattern = r'^ {4}(?P<key>\'.*?\'|\".*?\"): \{$'
        parent_key_match = re.match(parent_key_match_pattern, current_line)

        # マッチした場合、現在処理中の親キー (general, server, tv など) を更新する
        if parent_key_match is not None:

            # 親キーの値を取得し、更新する
            ## 生の値にはシングルクオート or ダブルクオートが含まれているので、除去してから代入
            parent_key_match_data = parent_key_match.groupdict()
            current_parent_key = parent_key_match_data['key'].replace('"', '').replace('\'', '')

            # 新しく作成する config.yaml には現在の行データをそのまま追加（変更する必要がないため）
            new_lines.append(current_line)
            continue

        # 'backend': 'EDCB', のような記述にマッチし、キーとバリューの値をそれぞれ取り出せる正規表現を実行
        key_value_match_pattern = r'^ {8}(?P<key>\'.*?\'|\".*?\"): (?P<value>[0-9\.]+|true|false|null|\'.*?\'|\".*?\"),$'
        key_value_match = re.match(key_value_match_pattern, current_line)

        # 何かしらマッチした場合のみ
        # コメント行では何も行われない
        if key_value_match is not None:

            # キーの値を取得する
            ## 生の値にはシングルクオート or ダブルクオートが含まれているので、除去してから代入
            key_value_match_data = key_value_match.groupdict()
            key = key_value_match_data['key'].replace('"', '').replace('\'', '')

            # 取得したキーが config_data[current_parent_key] の中に存在するときのみ
            ## current_parent_key は現在処理中の親キー (general, server, tv など)
            if key in config_data[current_parent_key]:

                # config_data から新しいバリューとなる値を取得
                value = config_data[current_parent_key][key]

                # バリューを YAML に書き込めるフォーマットに整形する
                if type(value) is str:
                    value_real = f"'{value}'"  # 文字列: シングルクオートで囲う
                elif value is True:
                    value_real = 'true'  # True → true に置換
                elif value is False:
                    value_real = 'false'  # False → false に置換
                elif value is None:
                    value_real = 'null'  # None → null に置換
                else:
                    value_real = str(value)  # それ以外 (数値など): そのまま文字列化
                ## 正規表現パターンに組み込んでも良いように、値の中のバックスラッシュをエスケープ
                value_real = value_real.replace('\\', '\\\\')

                # キー/バリュー行を新しい値で置換
                ## キーは以前と同じ値が使われる (バリューのみ新しい値置換される)
                new_line = re.sub(key_value_match_pattern, r'        \g<key>: ' + value_real + ',', current_line)

                # 新しく作成する config.yaml に置換した行データを追加
                new_lines.append(new_line)
                continue

        # 何もマッチしなかった場合 (コメント行など)
        ## 新しく作成する config.yaml には現在の行データをそのまま追加（変更する必要がないため）
        new_lines.append(current_line)

    # 置換が終わったので、config.yaml に書き込む
    ## リスト内の各要素にはすでに改行コードが含まれているので、空文字で join() するだけで OK
    with open(config_yaml_path, mode='w', encoding='utf-8') as file:
        file.write(''.join(new_lines))


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
        def on_created(self, event: FileCreatedEvent) -> None:
            nonlocal is_service_started
            is_service_started = True

        # ログファイルが更新されたら、ログの中に Application startup complete. という文字列が含まれていないかを探す
        # ログの中に Application startup complete. という文字列が含まれていたら、KonomiTV サーバーの起動が完了したとみなす
        def on_modified(self, event: FileModifiedEvent) -> None:
            # もし on_created をハンドリングできなかった場合に備え、on_modified でもサービス起動フラグを立てる
            nonlocal is_service_started, is_server_started, is_programs_update_completed, is_error_occurred
            is_service_started = True
            # ファイルのみに限定（フォルダの変更も検知されることがあるが、当然フォルダは開けないのでエラーになる）
            if Path(event.src_path).is_file() is True:
                with open(event.src_path, mode='r', encoding='utf-8') as log:
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
                with open(base_path / 'server/logs/KonomiTV-Server.log', mode='r', encoding='utf-8') as log:
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
                with open(base_path / 'server/logs/KonomiTV-Server.log', mode='r', encoding='utf-8') as log:
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
        name (str): プロセス名
        args (list[str]): 実行するコマンド
        cwd (Path): カレントディレクトリ
        error_message (str, optional): エラー発生時のエラーメッセージ. Defaults to '予期しないエラーが発生しました。'.
        error_log_name (str, optional): エラー発生時のエラーログ名. Defaults to 'エラーログ'.

    Returns:
        bool: 成功したかどうか
    """

    print(Padding(name, (1, 2, 0, 2)))
    progress = CreateBasicInfiniteProgress()
    progress.add_task('', total=None)
    with progress:
        result = subprocess.run(
            args = args,
            cwd = cwd,
            env = environment,
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
        name (str): プロセス名
        args (list[str]): 実行するコマンド
        cwd (Path): カレントディレクトリ
        error_message (str, optional): エラー発生時のエラーメッセージ. Defaults to '予期しないエラーが発生しました。'.

    Returns:
        bool: 成功したかどうか
    """

    print(Padding(name, (1, 2, 1, 2)))
    print(Rule(style=Style(color='cyan'), align='center'))
    pipenv_sync_result = subprocess.run(args, cwd = cwd, env = environment)
    print(Rule(style=Style(color='cyan'), align='center'))

    if pipenv_sync_result.returncode != 0:
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
