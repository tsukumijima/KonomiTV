import asyncio
import datetime
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic_core import Url

from app.config import Config
from app.utils.edcb import ChSet5Item
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.PipeStreamReader import PipeStreamReader


class EDCBUtil:
    """
    EDCB に関連する雑多なユーティリティ
    EDCB 自体や CtrlCmd インターフェイス絡みの独自フォーマットのパースなど
    ref: https://github.com/xtne6f/edcb.py/blob/master/edcb.py
    """

    @staticmethod
    def getEDCBHost(edcb_url: Url | None = None) -> str | None:
        """
        バックエンドとして指定された EDCB の接続先ホスト名を取得する

        Args:
            edcb_url (Url): EDCB の接続先 URL (指定されなかった場合は Config().general.edcb_url から取得する)

        Returns:
            str: バックエンドとして指定された EDCB の接続先ホスト名 (取得できなかった場合は None を返す)
        """
        if edcb_url is None:
            edcb_url = Config().general.edcb_url
        return edcb_url.host

    @staticmethod
    def getEDCBPort(edcb_url: Url | None = None) -> int | None:
        """
        バックエンドとして指定された EDCB の接続先ポートを取得する

        Args:
            edcb_url (Url): EDCB の接続先 URL (指定されなかった場合は Config().general.edcb_url から取得する)

        Returns:
            int: バックエンドとして指定された EDCB の接続先ポート (取得できなかった場合は None を返す)
        """
        if edcb_url is None:
            edcb_url = Config().general.edcb_url
        return edcb_url.port

    @staticmethod
    async def getEDCBStatus(edcb_url: Url | None = None) -> Literal['Normal', 'Recording', 'EPGGathering', 'Unknown']:
        """
        現在の EDCB (EpgTimerSrv) の動作ステータスを取得する
        Unknown が返る場合はおそらく EpgTimerSrv が起動していない

        Returns:
            Literal['Normal', 'Recording', 'EPGGathering', 'Unknown']: EDCB (EpgTimerSrv) の動作ステータス
        """

        # 現在の EpgTimerSrv の動作ステータスを取得できるか試してみる
        edcb = CtrlCmdUtil(edcb_url)
        edcb.setConnectTimeOutSec(5)  # 5秒後にタイムアウト
        result = await edcb.sendGetNotifySrvStatus()
        if result is None:
            return 'Unknown'

        # result['param1'] に EpgTimerSrv の動作ステータスが入っている (0: 通常 / 1: 録画中 / 2: EPG 取得中)
        if result['param1'] == 0:
            return 'Normal'
        elif result['param1'] == 1:
            return 'Recording'
        elif result['param1'] == 2:
            return 'EPGGathering'

        return 'Unknown'

    @staticmethod
    def convertBytesToString(buffer: bytes | bytearray | memoryview, default_encoding: str = 'cp932') -> str:
        """ BOM に基づいて Bytes データを文字列に変換する """
        if len(buffer) == 0:
            return ''
        elif len(buffer) >= 2 and buffer[0] == 0xff and buffer[1] == 0xfe:
            return str(memoryview(buffer)[2:], 'utf_16_le', 'replace')
        elif len(buffer) >= 3 and buffer[0] == 0xef and buffer[1] == 0xbb and buffer[2] == 0xbf:
            return str(memoryview(buffer)[3:], 'utf_8', 'replace')
        else:
            return str(buffer, default_encoding, 'replace')

    @staticmethod
    def parseChSet5(chset5_txt: str) -> list[ChSet5Item]:
        """ ChSet5.txt を解析する """
        result: list[ChSet5Item] = []
        for line in chset5_txt.splitlines():
            field = line.split('\t')
            if len(field) >= 9:
                try:
                    result.append({
                        'service_name': field[0],
                        'network_name': field[1],
                        'onid': int(field[2]),
                        'tsid': int(field[3]),
                        'sid': int(field[4]),
                        'service_type': int(field[5]),
                        'partial_flag': int(field[6]) != 0,
                        'epg_cap_flag': int(field[7]) != 0,
                        'search_flag': int(field[8]) != 0,
                        # リモコン ID は EDCB-240213 以降にのみ存在する
                        ## ref: https://github.com/xtne6f/EDCB/commit/aefe0eec87e495f92165ae67b50115353fb28599
                        ## ref: https://github.com/xtne6f/EDCB/commit/f19dd4031bff9cc41134d5e3dc6fd8b17373020c
                        'remocon_id': int(field[9]) if len(field) >= 10 else 0,
                    })
                except Exception:
                    pass
        return result

    @staticmethod
    def getLogoIDFromLogoDataIni(logo_data_ini: str, network_id: int, service_id: int) -> int:
        """ LogoData.ini をもとにロゴ識別を取得する。失敗のとき負値を返す """
        target = f'{network_id:04X}{service_id:04X}'
        for line in logo_data_ini.splitlines():
            key_value = line.split('=', 1)
            if len(key_value) == 2 and key_value[0].strip().upper() == target:
                try:
                    return int(key_value[1].strip())
                except Exception:
                    break
        return -1

    @staticmethod
    def getLogoFileNameFromDirectoryIndex(logo_dir_index: str, network_id: int, logo_id: int, logo_type: int) -> str | None:
        """ ファイルリストをもとにロゴファイル名を取得する """
        target = f'{network_id:04X}_{logo_id:03X}_'
        target_type = f'_{logo_type:02d}.'
        for line in logo_dir_index.splitlines():
            split = line.split(' ', 3)
            if len(split) == 4:
                name = split[3]
                if len(name) >= 16 and name[0:9].upper() == target and name[12:16] == target_type:
                    return name
        return None

    @staticmethod
    def parseProgramExtendedText(extended_text: str) -> dict[str, str]:
        """ 詳細情報テキストを解析して項目ごとの辞書を返す """
        extended_text = extended_text.replace('\r', '')
        result: dict[str, str] = {}
        head = ''
        i = 0
        while True:
            if i == 0 and extended_text.startswith('- '):
                j = 2
            elif (j := extended_text.find('\n- ', i)) >= 0:
                # 重複する項目名にはタブ文字を付加する
                while head in result:
                    head += '\t'
                result[head] = extended_text[(0 if i == 0 else i + 1):j + 1]
                j += 3
            else:
                if len(extended_text) != 0:
                    while head in result:
                        head += '\t'
                    result[head] = extended_text[(0 if i == 0 else i + 1):]
                break
            i = extended_text.find('\n', j)
            if i < 0:
                head = extended_text[j:]
                while head in result:
                    head += '\t'
                result[head] = ''
                break
            head = extended_text[j:i]
        return result

    @staticmethod
    def datetimeToFileTime(dt: datetime.datetime, tz: datetime.timezone = datetime.UTC) -> int:
        """ FILETIME 時間 (1601 年からの 100 ナノ秒時刻) に変換する """
        # 注意: tz には datetime.timezone (固定オフセット) のみ指定可能
        ## ZoneInfo は utcoffset(None) が None を返すため、ここで AttributeError になる
        ## ZoneInfo を使いたい場合は utcoffset() に datetime インスタンスを渡す実装への変更が必要
        return int((dt.timestamp() + tz.utcoffset(None).total_seconds()) * 10000000) + 116444736000000000

    @staticmethod
    async def openViewStream(process_id: int, timeout_sec: float = 10.0) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        """ View アプリの SrvPipe ストリームの転送を開始する """
        edcb = CtrlCmdUtil()
        edcb.setConnectTimeOutSec(timeout_sec)
        to = time.monotonic() + timeout_sec
        wait = 0.1
        while time.monotonic() < to:
            reader_and_writer = await edcb.openViewStream(process_id)
            if reader_and_writer is not None:
                return reader_and_writer
            await asyncio.sleep(wait)
            # 初期に成功しなければ見込みは薄いので問い合わせを疎にしていく
            wait = min(wait + 0.1, 1.0)
        return None

    @staticmethod
    async def openPipeStream(process_id: int, buffering: int = -1, timeout_sec: float = 10.0, dir: str | None = None) -> PipeStreamReader | None:
        """ システムに存在する SrvPipe ストリームを開き、PipeStreamReader を返す """
        to = time.monotonic() + timeout_sec
        wait = 0.1
        while time.monotonic() < to:
            # ポートは必ず 0 から 29 まで
            for port in range(30):
                pipe = None
                for index in range(2):
                    try:
                        if sys.platform == 'win32':
                            # 同時利用でも名前は同じ
                            path = ('\\\\.\\pipe\\' if dir is None else dir) + 'SendTSTCP_' + str(port) + '_' + str(process_id)
                            pipe = await asyncio.to_thread(open, path, mode='rb', buffering=buffering)
                            return PipeStreamReader(pipe, ThreadPoolExecutor())
                        else:
                            # 同時利用のための index がつく
                            path = ('/var/local/edcb/' if dir is None else dir) + 'SendTSTCP_' + str(port) + '_' + str(process_id) + '_' + str(index) + '.fifo'
                            pipe = await asyncio.to_thread(open, path, mode='rb', buffering=buffering)
                    except Exception:
                        break
                    # アドバイザリロックを使って index を自動選択する
                    assert sys.platform != 'win32'
                    import fcntl
                    try:
                        fcntl.flock(pipe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return PipeStreamReader(pipe, ThreadPoolExecutor())
                    except Exception:
                        pipe.close()
                # オープンが成功していれば他のポートは調べない
                if pipe is not None:
                    break
            await asyncio.sleep(wait)
            # 初期に成功しなければ見込みは薄いので問い合わせを疎にしていく
            wait = min(wait + 0.1, 1.0)
        return None
