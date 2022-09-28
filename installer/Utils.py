
import asyncio
import datetime
import os
import time
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
        BarColumn(bar_width=None),
        '[progress.percentage]{task.percentage:>3.1f}%',
        '•',
        DownloadColumn(),
        '•',
        TransferSpeedColumn(),
        '•',
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
        '•',
        TimeElapsedColumn(),
        TextColumn(' '),
    )
