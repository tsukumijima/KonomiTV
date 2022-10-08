
import asyncio
import emoji
import datetime
import os
import re
import rich
import subprocess
import time
from pathlib import Path
from rich.console import Console
from rich.padding import Padding
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
from rich.text import TextType
from typing import Callable, cast, Dict, List, Optional


class CustomPrompt(Prompt):
    """ カスタムの Rich プロンプトの実装 """

    def __init__(
        self,
        prompt: TextType = "",
        *,
        console: Optional[Console] = None,
        password: bool = False,
        choices: Optional[List[str]] = None,
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


class CtrlCmdConnectionCheckUtil:
    """ server/app/utils/EDCB.py の CtrlCmdUtil クラスのうち、接続確認に必要なロジックだけを抜き出したもの"""

    # EDCB の日付は OS のタイムゾーンに関わらず常に UTC+9
    TZ = datetime.timezone(datetime.timedelta(hours = 9), 'JST')

    def __init__(self, hostname: str, port: int | None) -> None:
        self.__connect_timeout_sec: float = 3  # 3秒でタイムアウト
        self.__pipe_name = 'EpgTimerSrvNoWaitPipe'
        self.__host: str | None = None
        self.__port: int = 0

        if hostname == 'edcb-namedpipe':
            # 特別に名前付きパイプモードにする
            self.__pipe_name = 'EpgTimerSrvNoWaitPipe'
            self.__host = None
        else:
            # TCP/IP モードにする
            self.__host = hostname
            self.__port = cast(int, port)

    async def sendEnumService(self) -> list | None:
        """ サービス一覧を取得する """
        buf = bytearray()
        self.__writeInt(buf, self.__CMD_EPG_SRV_ENUM_SERVICE)
        self.__writeInt(buf, 0)
        ret, buf = await self.__sendAndReceive(buf)
        if ret == self.__CMD_SUCCESS:
            return self.__readVector(self.__readServiceInfo, memoryview(buf), [0], len(buf))  # type: ignore
        return None

    # EDCB/EpgTimer の CtrlCmd.cs より
    __CMD_SUCCESS = 1
    __CMD_EPG_SRV_ENUM_SERVICE = 1021

    async def __sendAndReceive(self, buf: bytearray):
        to = time.monotonic() + self.__connect_timeout_sec
        ret: int | bool | None = 0
        size: int = 0
        if self.__host is None:
            # 名前付きパイプモード
            while True:
                try:
                    with open('\\\\.\\pipe\\' + self.__pipe_name, mode = 'r+b') as f:
                        f.write(buf)
                        f.flush()
                        rbuf = f.read(8)
                        if len(rbuf) == 8:
                            bufview = memoryview(rbuf)
                            pos = [0]
                            ret = self.__readInt(bufview, pos, 8)
                            size = cast(int, self.__readInt(bufview, pos, 8))
                            rbuf = f.read(size)
                            if len(rbuf) == size:
                                    return ret, rbuf
                    break
                except FileNotFoundError:
                    break
                except:
                    pass
                await asyncio.sleep(0.01)
                if time.monotonic() >= to:
                    break
            return None, None

        # TCP/IP モード
        try:
            r, w = await asyncio.wait_for(asyncio.open_connection(self.__host, self.__port), max(to - time.monotonic(), 0.))
        except:
            return None, None
        try:
            w.write(buf)
            await asyncio.wait_for(w.drain(), max(to - time.monotonic(), 0.))
            rbuf = await asyncio.wait_for(r.readexactly(8), max(to - time.monotonic(), 0.))
            if len(rbuf) == 8:
                bufview = memoryview(rbuf)
                pos = [0]
                ret = self.__readInt(bufview, pos, 8)
                size = cast(int, self.__readInt(bufview, pos, 8))
                rbuf = await asyncio.wait_for(r.readexactly(size), max(to - time.monotonic(), 0.))
        except:
            w.close()
            return None, None
        try:
            w.close()
            await asyncio.wait_for(w.wait_closed(), max(to - time.monotonic(), 0.))
        except:
            pass
        if len(rbuf) == size:
            return ret, rbuf
        return None, None

    @staticmethod
    def __writeInt(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(4, 'little', signed = True))

    # 以下、各構造体のライター
    # 各キーの意味は CtrlCmdDef.cs のクラス定義を参照のこと

    @staticmethod
    def __readByte(buf: memoryview, pos: list, size: int, dest: dict | None = None, key: str | None = None):
        if size - pos[0] < 1:
            return None if dest is None else False
        v = int.from_bytes(buf[pos[0]:pos[0] + 1], 'little')
        pos[0] += 1
        if dest is None:
            return v
        dest[key] = v
        return True

    @staticmethod
    def __readUshort(buf: memoryview, pos: list, size: int, dest: dict | None = None, key: str | None = None):
        if size - pos[0] < 2:
            return None if dest is None else False
        v = int.from_bytes(buf[pos[0]:pos[0] + 2], 'little')
        pos[0] += 2
        if dest is None:
            return v
        dest[key] = v
        return True

    @staticmethod
    def __readInt(buf: memoryview, pos: list, size: int, dest: dict | None = None, key: str | None = None):
        if size - pos[0] < 4:
            return None if dest is None else False
        v = int.from_bytes(buf[pos[0]:pos[0] + 4], 'little', signed = True)
        pos[0] += 4
        if dest is None:
            return v
        dest[key] = v
        return True

    @classmethod
    def __readString(cls, buf: memoryview, pos: list, size: int, dest: dict | None = None, key: str | None = None):
        vs = cls.__readInt(buf, pos, size)
        if vs is None or vs < 6 or size - pos[0] < vs - 4:
            return None if dest is None else False
        v = str(buf[pos[0]:pos[0] + vs - 6], 'utf_16_le')
        pos[0] += vs - 4
        if dest is None:
            return v
        dest[key] = v
        return True

    @classmethod
    def __readVector(cls, read_func: Callable, buf: memoryview, pos: list, size: int, dest: dict | None = None, key: str | None = None):
        if ((vs := cls.__readInt(buf, pos, size)) is None or
            (vc := cls.__readInt(buf, pos, size)) is None or
            vs < 8 or vc < 0 or size - pos[0] < vs - 8):
            return None if dest is None else False
        size = pos[0] + vs - 8
        v = []
        for i in range(vc):
            e = read_func(buf, pos, size)
            if e is None:
                return None if dest is None else False
            v.append(e)
        pos[0] = size
        if dest is None:
            return v
        dest[key] = v
        return True

    @classmethod
    def __readStructIntro(cls, buf: memoryview, pos: list, size: int):
        vs = cls.__readInt(buf, pos, size)
        if vs is None or vs < 4 or size - pos[0] < vs - 4:
            return None, 0
        return {}, pos[0] + vs - 4

    # 以下、各構造体のリーダー
    # 各キーの意味は CtrlCmdDef.cs のクラス定義を参照のこと

    @classmethod
    def __readServiceInfo(cls, buf: memoryview, pos: list, size: int) -> dict | None:
        v, size = cls.__readStructIntro(buf, pos, size)
        if (v is None or
            not cls.__readUshort(buf, pos, size, v, 'onid') or
            not cls.__readUshort(buf, pos, size, v, 'tsid') or
            not cls.__readUshort(buf, pos, size, v, 'sid') or
            not cls.__readByte(buf, pos, size, v, 'service_type') or
            not cls.__readByte(buf, pos, size, v, 'partial_reception_flag') or
            not cls.__readString(buf, pos, size, v, 'service_provider_name') or
            not cls.__readString(buf, pos, size, v, 'service_name') or
            not cls.__readString(buf, pos, size, v, 'network_name') or
            not cls.__readString(buf, pos, size, v, 'ts_name') or
            not cls.__readByte(buf, pos, size, v, 'remote_control_key_id')):
            return None
        pos[0] = size
        return v


def GetNetworkDriveList() -> List[Dict[str, str]]:
    """
    レジストリからログオン中のユーザーがマウントしているネットワークドライブのリストを取得する
    KonomiTV-Service.py で利用されているものと基本同じ

    Returns:
        List[Dict[str, str]]: ネットワークドライブのドライブレターとパスのリスト
    """

    # Windows 以外では実行しない
    if os.name != 'nt': return []

    # winreg (レジストリを操作するための標準ライブラリ (Windows 限定) をインポート)
    import winreg

    # ネットワークドライブの情報が入る辞書のリスト
    network_drives: List[Dict[str, str]] = []

    # ネットワークドライブの情報が格納されているレジストリの HKEY_CURRENT_USER\Network を開く
    # ref: https://itasuke.hatenablog.com/entry/2018/01/08/133510
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Network') as root_key:

        # HKEY_CURRENT_USER\Network 以下のキーを列挙
        for key in range(winreg.QueryInfoKey(root_key)[0]):
            drive_letter = winreg.EnumKey(root_key, key)

            # HKEY_CURRENT_USER\Network 以下のキーをそれぞれ開く
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'Network\\{drive_letter}') as key:
                for sub_key in range(winreg.QueryInfoKey(key)[1]):

                    # 値の名前、データ、データ型を取得
                    name, data, regtype = winreg.EnumValue(key, sub_key)

                    # リストに追加
                    if name == 'RemotePath':
                        network_drives.append({
                            'drive_letter': drive_letter,
                            'remote_path': data,
                        })

    return network_drives


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


def IsDockerInstalled() -> bool:
    """
    Linux に Docker + Docker Compose (V1, V2 は不問) がインストールされているかどうか
    Windows では Docker での構築はサポートしていない

    Returns:
        bool: Docker + Docker Compose がインストールされていれば True 、インストールされていなければ False
    """

    # Windows では常に False (サポートしていないため)
    if os.name == 'nt': return False

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
    if docker_compose_v2_result.returncode != 0 and 'Docker Compose version v2' in docker_compose_v2_result.stdout:
        return True  # Docker と Docker Compose V2 がインストールされている

    # Docker Compose V1 の存在確認
    docker_compose_v1_result = subprocess.run(
        args = ['docker-compose', 'version'],
        stdout = subprocess.PIPE,  # 標準出力をキャプチャする
        stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        text = True,  # 出力をテキストとして取得する
    )
    if docker_compose_v1_result.returncode != 0 and 'docker-compose version 1' in docker_compose_v1_result.stdout:
        return True  # Docker と Docker Compose V1 がインストールされている

    return False  # Docker はインストールされているが、Docker Compose がインストールされていない


def IsGitInstalled() -> bool:
    """
    Git コマンドがインストールされているかどうか

    Returns:
        bool: Git コマンドがインストールされていれば True 、インストールされていなければ False
    """
    is_git_installed = False

    ## Windows
    if os.name == 'nt':
        result = subprocess.run(
            args = ['C:/Windows/System32/where.exe', 'git'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )
        if result.returncode == 0:
            is_git_installed = True
    ## Linux
    else:
        result = subprocess.run(
            args = ['/usr/bin/bash', '-c', 'type git'],
            stdout = subprocess.DEVNULL,  # 標準出力を表示しない
            stderr = subprocess.DEVNULL,  # 標準エラー出力を表示しない
        )
        if result.returncode == 0:
            is_git_installed = True

    return is_git_installed


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
    変更された環境設定データを、コメントやフォーマットを保持した形で config.yaml に書き込む
    config.yaml のすべてを上書きするのではなく、具体的な値が記述されている部分のみ正規表現で置換している

    Args:
        config_yaml_path (Path): 保存する config.yaml のパス
        config_data (dict[str, dict[str, int | float | bool | str | None]]): 環境設定データの辞書
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
    current_parent_key: str = ''
    for current_line in current_lines:

        # 'general': { のような記述にマッチする正規表現を実行
        parent_key_match_pattern = r'^ {4}(?P<key>\'.*?\'|\".*?\"): \{$'
        parent_key_match = re.match(parent_key_match_pattern, current_line)

        # マッチした場合、現在の親キー (general, server, tv など) を更新する
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
