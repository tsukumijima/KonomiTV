
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import aiofiles
import asyncio
import datetime
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from io import BufferedReader
from typing import Callable, cast, ClassVar, Literal, TypedDict, TypeVar

from app.constants import CONFIG

# ジェネリック型
T = TypeVar('T')


class PipeStreamReader:
    """
    パイプのファイルオブジェクトを非同期で読み込むクラス
    ProactorEventLoop のパイプサポートは未だ不十分で、ドキュメントされていない create_pipe_connection メソッドも
    内部で Win32API の CreateFile に渡すフラグが不適切で使い物にならないためつなぎとして用意したもの
    """

    def __init__(self, pipe: BufferedReader, executor: ThreadPoolExecutor) -> None:
        self.__pipe = pipe
        self.__executor = executor
        self.__loop = asyncio.get_running_loop()
        self.__buffer = bytearray()

    async def readexactly(self, n: int) -> bytes:
        self.__buffer.clear()
        while len(self.__buffer) < n:
            data = await self.__loop.run_in_executor(self.__executor, lambda: self.__pipe.read(n - len(self.__buffer)))
            if len(data) == 0:
                raise asyncio.IncompleteReadError(bytes(self.__buffer), None)
            self.__buffer += data
        return bytes(self.__buffer)

    def is_closing(self) -> bool:
        return self.__pipe.closed

    async def close(self) -> None:
        await self.__loop.run_in_executor(self.__executor, self.__pipe.close)


class EDCBTuner:
    """ EDCB バックエンドのチューナーを制御するクラス """

    # 全てのチューナーインスタンスが格納されるリスト
    # チューナーを閉じずに再利用するため、全てのチューナーインスタンスにアクセスできるようにする
    __instances: ClassVar[list[EDCBTuner | None]] = []


    def __new__(cls, network_id: int, service_id: int, transport_stream_id: int) -> EDCBTuner:

        # 新しいチューナーインスタンスを生成する
        instance = super(EDCBTuner, cls).__new__(cls)

        # 生成したチューナーインスタンスを登録する
        cls.__instances.append(instance)

        # 登録されたチューナーインスタンスを返す
        return instance


    def __init__(self, network_id: int, service_id: int, transport_stream_id: int) -> None:
        """
        チューナーインスタンスを初期化する

        Args:
            network_id (int): ネットワーク ID
            service_id (int): サービス ID
            transport_stream_id (int): トランスポートストリーム ID
        """

        # NID・SID・TSID を設定
        self.network_id: int = network_id
        self.service_id: int = service_id
        self.transport_stream_id: int = transport_stream_id

        # チューナーがロックされているかどうか
        ## 一般に ONAir 時はロックされ、Idling 時はアンロックされる
        self._locked: bool = False

        # チューナーの制御権限を委譲している（＝チューナーが再利用されている）かどうか
        ## このフラグが True になっているチューナーは、チューナー制御の取り合いにならないように以後何を実行してもチューナーの状態を変更できなくなる
        self._delegated: bool = False

        # このチューナーインスタンス固有の NetworkTV ID を取得
        ## NetworkTV ID は NetworkTV モードの EpgDataCap_Bon を識別するために割り当てられる ID
        ## アンロック状態のチューナーがあれば、その NetworkTV ID を使い起動中の EpgDataCap_Bon を再利用する
        self._edcb_networktv_id: int = self.__getNetworkTVID()

        # EpgDataCap_Bon のプロセス ID
        ## プロセス ID が None のときはチューナーが起動されていないものとして扱う
        self._edcb_process_id: int | None = None

        # チューナーとのストリーミング接続を閉じるための StreamWriter (TCP/IP モード時)
        ## まだ接続していないとき、接続が閉じられた後は None になる
        self._edcb_stream_writer: asyncio.StreamWriter | None = None

        # チューナーとのストリーミング接続を閉じるためのパイプ (名前付きパイプモード時)
        ## まだ接続していないとき、接続が閉じられた後は None になる
        self._edcb_pipe_stream_reader: PipeStreamReader | None = None


    def __getNetworkTVID(self) -> int:
        """
        EpgDataCap_Bon の NetworkTV ID を取得する
        アンロック状態のチューナーインスタンスがあれば、それを削除した上でそのチューナーインスタンスの NetworkTV ID を返す

        Returns:
            int: 取得した EpgDataCap_Bon の NetworkTV ID
        """

        # 二重制御の防止
        if self._delegated is True:
            return 0

        # NetworkTV モードのチューナーを識別する任意の整数
        ## ほかのロケフリ系アプリと重複しないように 500 を増分してある
        ## さらに登録されているチューナーインスタンスの数を足す（とりあえず被らなければいいのでこれで）
        edcb_networktv_id = 500 + len(EDCBTuner.__instances)

        # インスタンスごとに
        for instance in EDCBTuner.__instances:

            # ロックされていなければ
            if instance is not None and instance._locked is False:

                # edcb_networktv_id が存在しない（初期化途中、おそらく自分自身のインスタンス）場合はスキップ
                if not hasattr(instance, '_edcb_networktv_id'):
                    continue

                # そのインスタンスの NetworkTV ID を取得
                edcb_networktv_id = instance._edcb_networktv_id

                # そのインスタンスから今後チューナーを制御できないようにする（制御権限の委譲）
                # NetworkTV ID が同じチューナーインスタンスが複数ある場合でも、制御できるインスタンスは1つに限定する
                instance._delegated = True

                # 二重にチューナーを再利用することがないよう、インスタンスの登録を削除する
                # インデックスがずれるのを避けるため、None を入れて要素自体は削除しない
                EDCBTuner.__instances[EDCBTuner.__instances.index(instance)] = None
                break

        # NetworkTV ID を返す
        return edcb_networktv_id


    async def open(self) -> bool:
        """
        チューナーを起動する
        すでに EpgDataCap_Bon が起動している（チューナーを再利用した）場合は、その EpgDataCap_Bon に対してチャンネル切り替えを行う

        Returns:
            bool: チューナーを起動できたかどうか
        """

        # 二重制御の防止
        if self._delegated is True:
            return False

        # edcb.sendNwTVIDSetCh() に渡す辞書
        set_ch_info: SetChInfo = {

            # NID・SID・TSID を設定
            'onid': self.network_id,
            'sid': self.service_id,
            'tsid': self.transport_stream_id,

            # NetworkTV ID をセット
            'space_or_id': self._edcb_networktv_id,

            # TCP 送信を有効にする (EpgDataCap_Bon の起動モード)
            # 1:UDP 2:TCP 3:UDP+TCP
            'ch_or_mode': 2,

            # onid・tsid・sid の値が使用できるかどうか
            # これを False にすれば起動確認とプロセス ID の取得ができる
            'use_sid': True,

            # space_or_id・ch_or_mode の値が使用できるかどうか
            'use_bon_ch': True,
        }

        # チューナーを起動する
        ## ほかのタスクがチューナーを閉じている (Idling -> Offline) などで空きがない場合があるのでいくらかリトライする
        set_ch_timeout = time.monotonic() + 5  # 現在時刻から5秒後
        while True:

            # チューナーの起動（あるいはチャンネル変更）を試す
            edcb = CtrlCmdUtil()
            self._edcb_process_id = await edcb.sendNwTVIDSetCh(set_ch_info)

            # チューナーが起動できた、もしくはリトライ時間をタイムアウトした
            if self._edcb_process_id is not None or time.monotonic() >= set_ch_timeout:
                break

            await asyncio.sleep(0.5)

        # チューナーの起動に失敗した
        if self._edcb_process_id is None:
            await self.close()  # チューナーを閉じる
            return False

        return True


    async def connect(self) -> asyncio.StreamReader | PipeStreamReader | None:
        """
        チューナーに接続し、放送波を受け取るための TCP ソケットまたは名前付きパイプを返す

        Returns:
            asyncio.StreamReader | PipeStreamReader | None: TCP ソケットまたは名前付きパイプの StreamReader (取得できなかった場合は None を返す)
        """

        # プロセス ID が取得できている（チューナーが起動している）ことが前提
        if self._edcb_process_id is None:
            return None

        stream_reader: asyncio.StreamReader | PipeStreamReader | None = None

        # チューナーに接続する
        if EDCBUtil.getEDCBHost() != 'edcb-namedpipe':
            ## EpgDataCap_Bon で受信した放送波を受け取るための名前付きパイプの出力を、
            ## EpgTimerSrv の CtrlCmd インターフェイス (TCP API) 経由で受信するための TCP ソケット (StreamReader / StreamWriter)
            result = await EDCBUtil.openViewStream(self._edcb_process_id)
            stream_reader, stream_writer = (None, None) if result is None else result
        else:
            ## EpgDataCap_Bon で受信した放送波を受け取るための名前付きパイプ (PipeStreamReader)
            stream_reader = await EDCBUtil.openPipeStream(self._edcb_process_id)
            stream_writer = None
            self._edcb_pipe_stream_reader = stream_reader

        # チューナーへの接続に失敗した
        ## チューナーを閉じてからエラーを返す
        if stream_reader is None:
            await self.close()  # チューナーを閉じる
            return None

        if stream_writer is not None:
            self._edcb_stream_writer = stream_writer

        return stream_reader


    async def disconnect(self) -> None:
        """
        チューナーとのストリーミング接続を閉じる
        ストリーミングが終了した際に必ず呼び出す必要がある
        """

        # TCP/IP モード
        if self._edcb_stream_writer is not None:
            self._edcb_stream_writer.close()
            await self._edcb_stream_writer.wait_closed()
            self._edcb_stream_writer = None

        # 名前付きパイプモード
        elif self._edcb_pipe_stream_reader is not None:
            await self._edcb_pipe_stream_reader.close()
            self._edcb_pipe_stream_reader = None


    def isDisconnected(self) -> bool:
        """
        チューナーとのストリーミング接続が閉じられているかどうかを返す

        Returns:
            bool: チューナーとのストリーミング接続が閉じられているかどうか
        """

        if self._edcb_stream_writer is not None:
            return self._edcb_stream_writer.is_closing()
        elif self._edcb_pipe_stream_reader is not None:
            return self._edcb_pipe_stream_reader.is_closing()

        return True


    def lock(self) -> None:
        """
        チューナーをロックする
        ロックしておかないとチューナーの制御を横取りされてしまうので、基本はロック状態にする
        """
        self._locked = True


    def unlock(self) -> None:
        """
        チューナーをアンロックする
        チューナーがアンロックされている場合、起動中の EpgDataCap_Bon は次のチューナーインスタンスの初期化時に再利用される
        """
        self._locked = False


    async def close(self) -> bool:
        """
        チューナーを終了する

        Returns:
            bool: チューナーを終了できたかどうか
        """

        # 二重制御の防止
        if self._delegated is True:
            return False

        # チューナーを閉じ、実行結果を取得する
        edcb = CtrlCmdUtil()
        result = await edcb.sendNwTVIDClose(self._edcb_networktv_id)

        # チューナーが閉じられたので、プロセス ID を None に戻す
        self._edcb_process_id = None

        # インスタンスの登録を削除する
        if self in EDCBTuner.__instances:
            EDCBTuner.__instances[EDCBTuner.__instances.index(self)] = None

        return result


    @classmethod
    async def closeAll(cls) -> None:
        """
        現在起動中の全てのチューナーを終了する
        明示的に終了しないといつまでも起動してしまうため、アプリケーション終了時に実行する
        """
        for instance in EDCBTuner.__instances:
            if instance is not None:
                await instance.close()


class ChSet5Item(TypedDict):
    """ ChSet5.txt の一行の情報 """
    service_name: str
    network_name: str
    onid: int
    tsid: int
    sid: int
    service_type: int
    partial_flag: bool
    epg_cap_flag: bool
    search_flag: bool


class EDCBUtil:
    """
    EDCB に関連する雑多なユーティリティ
    EDCB 自体や CtrlCmd インターフェイス絡みの独自フォーマットのパースなど
    """

    @staticmethod
    def getEDCBHost() -> str | None:
        """
        バックエンドとして指定された EDCB の接続先ホスト名を取得する

        Returns:
            str: バックエンドとして指定された EDCB の接続先ホスト名 (取得できなかった場合は None を返す)
        """
        edcb_url_parse = urllib.parse.urlparse(CONFIG['general']['edcb_url'])
        return edcb_url_parse.hostname

    @staticmethod
    def getEDCBPort() -> int | None:
        """
        バックエンドとして指定された EDCB の接続先ポートを取得する

        Returns:
            str: バックエンドとして指定された EDCB の接続先ポート (取得できなかった場合は None を返す)
        """
        edcb_url_parse = urllib.parse.urlparse(CONFIG['general']['edcb_url'])
        return edcb_url_parse.port

    @staticmethod
    def convertBytesToString(buffer: bytes) -> str:
        """ BOM に基づいて Bytes データを文字列に変換する """
        if len(buffer) == 0:
            return ''
        elif len(buffer) >= 2 and buffer[0] == 0xff and buffer[1] == 0xfe:
            return str(memoryview(buffer)[2:], 'utf_16_le', 'replace')
        elif len(buffer) >= 3 and buffer[0] == 0xef and buffer[1] == 0xbb and buffer[2] == 0xbf:
            return str(memoryview(buffer)[3:], 'utf_8', 'replace')
        else:
            return str(buffer, 'cp932', 'replace')

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
                        'search_flag': int(field[8]) != 0
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
                result[head] = extended_text[(0 if i == 0 else i + 1):j + 1]
                j += 3
            else:
                if len(extended_text) != 0:
                    result[head] = extended_text[(0 if i == 0 else i + 1):]
                break
            i = extended_text.find('\n', j)
            if i < 0:
                result[extended_text[j:]] = ''
                break
            head = extended_text[j:i]
        return result

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
    async def openPipeStream(process_id: int, timeout_sec: float = 10.0) -> PipeStreamReader | None:
        """ システムに存在する SrvPipe ストリームを開く """
        if sys.platform != 'win32':
            raise NotImplementedError('Windows Only')

        to = time.monotonic() + timeout_sec
        wait = 0.1
        while time.monotonic() < to:
            # ポートは必ず 0 から 29 まで
            for port in range(30):
                try:
                    path = '\\\\.\\pipe\\SendTSTCP_' + str(port) + '_' + str(process_id)
                    pipe = await asyncio.to_thread(open, path, mode='rb')
                    return PipeStreamReader(pipe, ThreadPoolExecutor())
                except Exception:
                    pass
            await asyncio.sleep(wait)
            # 初期に成功しなければ見込みは薄いので問い合わせを疎にしていく
            wait = min(wait + 0.1, 1.0)
        return None


# 以下、 CtrlCmdUtil で受け渡しする辞書の型ヒント
# ・キーの意味は https://github.com/xtne6f/EDCB の Readme_Mod.txt のテーブル定義の対応する説明を参照
#   のこと。キーについてのコメントはこの説明と異なるものだけ行う
# ・辞書やキーの命名は EpgTimer の CtrlCmdDef.cs を基準とする
# ・注記がなければ受け取り方向ではすべてのキーが存在し、引き渡し方向は存在しないキーを 0 や False や
#   空文字列などとして解釈する


class SetChInfo(TypedDict, total=False):
    """ チャンネル・ NetworkTV モード変更情報 """
    use_sid: int
    onid: int
    tsid: int
    sid: int
    use_bon_ch: int
    space_or_id: int
    ch_or_mode: int


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


class FileData(TypedDict):
    """ 転送ファイルデータ """
    name: str
    data: bytes


class RecFileSetInfo(TypedDict, total=False):
    """ 録画フォルダ情報 """
    rec_folder: str
    write_plug_in: str
    rec_name_plug_in: str


class RecSettingData(TypedDict, total=False):
    """ 録画設定 """
    rec_mode: int  # 0-4: 全サービス～視聴, 5-8: 無効の指定サービス～視聴, 9: 無効の全サービス
    priority: int
    tuijyuu_flag: bool
    service_mode: int
    pittari_flag: bool
    bat_file_path: str
    rec_folder_list: list[RecFileSetInfo]
    suspend_mode: int
    reboot_flag: bool
    start_margin: int  # デフォルトのとき存在しない
    end_margin: int  # デフォルトのとき存在しない
    continue_rec_flag: bool
    partial_rec_flag: int
    tuner_id: int
    partial_rec_folder: list[RecFileSetInfo]


class ReserveData(TypedDict, total=False):
    """ 予約情報 """
    title: str
    start_time: datetime.datetime
    duration_second: int
    station_name: str
    onid: int
    tsid: int
    sid: int
    eid: int
    comment: str
    reserve_id: int
    overlap_mode: int
    start_time_epg: datetime.datetime
    rec_setting: RecSettingData
    rec_file_name_list: list[str]  # 録画予定ファイル名


class RecFileInfo(TypedDict, total=False):
    """ 録画済み情報 """
    id: int
    rec_file_path: str
    title: str
    start_time: datetime.datetime
    duration_sec: int
    service_name: str
    onid: int
    tsid: int
    sid: int
    eid: int
    drops: int
    scrambles: int
    rec_status: int
    start_time_epg: datetime.datetime
    comment: str
    program_info: str
    err_info: str
    protect_flag: bool


class TunerReserveInfo(TypedDict):
    """ チューナー予約情報 """
    tuner_id: int
    tuner_name: str
    reserve_list: list[int]


class ShortEventInfo(TypedDict):
    """ イベントの基本情報 """
    event_name: str
    text_char: str


class ExtendedEventInfo(TypedDict):
    """ イベントの拡張情報 """
    text_char: str


class ContentData(TypedDict):
    """ ジャンルの個別データ """
    content_nibble: int
    user_nibble: int


class ContentInfo(TypedDict):
    """ ジャンル情報 """
    nibble_list: list[ContentData]


class ComponentInfo(TypedDict):
    """ 映像情報 """
    stream_content: int
    component_type: int
    component_tag: int
    text_char: str


class AudioComponentInfoData(TypedDict):
    """ 音声情報の個別データ """
    stream_content: int
    component_type: int
    component_tag: int
    stream_type: int
    simulcast_group_tag: int
    es_multi_lingual_flag: int
    main_component_flag: int
    quality_indicator: int
    sampling_rate: int
    text_char: str


class AudioComponentInfo(TypedDict):
    """ 音声情報 """
    component_list: list[AudioComponentInfoData]


class EventData(TypedDict):
    """ イベントグループの個別データ """
    onid: int
    tsid: int
    sid: int
    eid: int


class EventGroupInfo(TypedDict):
    """ イベントグループ情報 """
    group_type: int
    event_data_list: list[EventData]


class EventInfoRequired(TypedDict):
    """ イベント情報の必須項目 """
    onid: int
    tsid: int
    sid: int
    eid: int
    free_ca_flag: int


class EventInfo(EventInfoRequired, total=False):
    """ イベント情報 """
    start_time: datetime.datetime  # 不明のとき存在しない
    duration_sec: int  # 不明のとき存在しない
    short_info: ShortEventInfo  # 情報がないとき存在しない、以下同様
    ext_info: ExtendedEventInfo
    content_info: ContentInfo
    component_info: ComponentInfo
    audio_info: AudioComponentInfo
    event_group_info: EventGroupInfo
    event_relay_info: EventGroupInfo


class ServiceEventInfo(TypedDict):
    """ サービスとそのイベント一覧 """
    service_info: ServiceInfo
    event_list: list[EventInfo]


# 以上、 CtrlCmdUtil で受け渡しする辞書の型ヒント


class CtrlCmdUtil:
    """
    EpgTimerSrv の CtrlCmd インタフェースと通信する (EDCB/EpgTimer の CtrlCmd(Def).cs を移植したもの)
    ・利用可能なコマンドはもっとあるが使いそうなものだけ
    ・sendView* 系コマンドは EpgDataCap_Bon 等との通信用。接続先パイプは "View_Ctrl_BonNoWaitPipe_{プロセス ID}"
    """

    # EDCB の日付は OS のタイムゾーンに関わらず常に UTC+9
    TZ = datetime.timezone(datetime.timedelta(hours=9), 'JST')

    # 読み取った日付が不正なときや既定値に使う UNIX エポック
    UNIX_EPOCH = datetime.datetime(1970, 1, 1, 9, tzinfo=TZ)

    __connect_timeout_sec: float
    __pipe_name: str
    __host: str | None
    __port: int

    def __init__(self) -> None:
        self.__connect_timeout_sec = 15.
        self.__pipe_name = 'EpgTimerSrvNoWaitPipe'
        self.__host = None
        self.__port = 0

        if EDCBUtil.getEDCBHost() == 'edcb-namedpipe':
            # 特別に名前付きパイプモードにする
            self.setPipeSetting('EpgTimerSrvNoWaitPipe')
        else:
            # TCP/IP モードにする
            self.setNWSetting(cast(str, EDCBUtil.getEDCBHost()), cast(int, EDCBUtil.getEDCBPort()))

    def setNWSetting(self, host: str, port: int) -> None:
        """ TCP/IP モードにする """
        self.__host = host
        self.__port = port

    def setPipeSetting(self, name: str) -> None:
        """ 名前付きパイプモードにする """
        self.__pipe_name = name
        self.__host = None

    def setConnectTimeOutSec(self, timeout: float) -> None:
        """ 接続処理時のタイムアウト設定 """
        self.__connect_timeout_sec = timeout

    async def sendViewSetBonDriver(self, name: str) -> bool:
        """ BonDriver の切り替え """
        ret, _ = await self.__sendCmd(self.__CMD_VIEW_APP_SET_BONDRIVER,
                                      lambda buf: self.__writeString(buf, name))
        return ret == self.__CMD_SUCCESS

    async def sendViewGetBonDriver(self) -> str | None:
        """ 使用中の BonDriver のファイル名を取得 """
        ret, rbuf = await self.__sendCmd(self.__CMD_VIEW_APP_GET_BONDRIVER)
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readString(memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendViewSetCh(self, set_ch_info: SetChInfo) -> bool:
        """ チャンネル切り替え """
        ret, _ = await self.__sendCmd(self.__CMD_VIEW_APP_SET_CH,
                                      lambda buf: self.__writeSetChInfo(buf, set_ch_info))
        return ret == self.__CMD_SUCCESS

    async def sendViewAppClose(self) -> bool:
        """ アプリケーションの終了 """
        ret, _ = await self.__sendCmd(self.__CMD_VIEW_APP_CLOSE)
        return ret == self.__CMD_SUCCESS

    async def sendEnumService(self) -> list[ServiceInfo] | None:
        """ サービス一覧を取得する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_ENUM_SERVICE)
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readVector(self.__readServiceInfo, memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendEnumPgInfoEx(self, service_time_list: list[int]) -> list[ServiceEventInfo] | None:
        """ サービス指定と時間指定で番組情報一覧を取得する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_ENUM_PG_INFO_EX,
                                         lambda buf: self.__writeVector(self.__writeLong, buf, service_time_list))
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readVector(self.__readServiceEventInfo, memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendEnumPgArc(self, service_time_list: list[int]) -> list[ServiceEventInfo] | None:
        """ サービス指定と時間指定で過去番組情報一覧を取得する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_ENUM_PG_ARC,
                                         lambda buf: self.__writeVector(self.__writeLong, buf, service_time_list))
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readVector(self.__readServiceEventInfo, memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendFileCopy(self, name: str) -> bytes | None:
        """ 指定ファイルを転送する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_FILE_COPY,
                                         lambda buf: self.__writeString(buf, name))
        if ret == self.__CMD_SUCCESS:
            return rbuf
        return None

    async def sendFileCopy2(self, name_list: list[str]) -> list[FileData] | None:
        """ 指定ファイルをまとめて転送する """
        ret, rbuf = await self.__sendCmd2(self.__CMD_EPG_SRV_FILE_COPY2,
                                          lambda buf: self.__writeVector(self.__writeString, buf, name_list))
        if ret == self.__CMD_SUCCESS:
            bufview = memoryview(rbuf)
            pos = [0]
            try:
                if self.__readUshort(bufview, pos, len(rbuf)) >= self.__CMD_VER:
                    return self.__readVector(self.__readFileData, bufview, pos, len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendNwTVIDSetCh(self, set_ch_info: SetChInfo) -> int | None:
        """ NetworkTV モードの View アプリのチャンネルを切り替え、または起動の確認 (ID 指定) """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_NWTV_ID_SET_CH,
                                         lambda buf: self.__writeSetChInfo(buf, set_ch_info))
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readInt(memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendNwTVIDClose(self, nwtv_id: int) -> bool:
        """ NetworkTV モードで起動中の View アプリを終了 (ID 指定) """
        ret, _ = await self.__sendCmd(self.__CMD_EPG_SRV_NWTV_ID_CLOSE,
                                      lambda buf: self.__writeInt(buf, nwtv_id))
        return ret == self.__CMD_SUCCESS

    async def sendEnumReserve(self) -> list[ReserveData] | None:
        """ 予約一覧を取得する """
        ret, rbuf = await self.__sendCmd2(self.__CMD_EPG_SRV_ENUM_RESERVE2)
        if ret == self.__CMD_SUCCESS:
            bufview = memoryview(rbuf)
            pos = [0]
            try:
                if self.__readUshort(bufview, pos, len(rbuf)) >= self.__CMD_VER:
                    return self.__readVector(self.__readReserveData, bufview, pos, len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendAddReserve(self, reserve_list: list[ReserveData]) -> bool:
        """ 予約を追加する """
        ret, _ = await self.__sendCmd2(self.__CMD_EPG_SRV_ADD_RESERVE2,
                                       lambda buf: self.__writeVector(self.__writeReserveData, buf, reserve_list))
        return ret == self.__CMD_SUCCESS

    async def sendChgReserve(self, reserve_list: list[ReserveData]) -> bool:
        """ 予約を変更する """
        ret, _ = await self.__sendCmd2(self.__CMD_EPG_SRV_CHG_RESERVE2,
                                       lambda buf: self.__writeVector(self.__writeReserveData, buf, reserve_list))
        return ret == self.__CMD_SUCCESS

    async def sendDelReserve(self, reserve_id_list: list[int]) -> bool:
        """ 予約を削除する """
        ret, _ = await self.__sendCmd(self.__CMD_EPG_SRV_DEL_RESERVE,
                                      lambda buf: self.__writeVector(self.__writeInt, buf, reserve_id_list))
        return ret == self.__CMD_SUCCESS

    async def sendEnumRecInfoBasic(self) -> list[RecFileInfo] | None:
        """ 録画済み情報一覧取得 (programInfo と errInfo を除く) """
        ret, rbuf = await self.__sendCmd2(self.__CMD_EPG_SRV_ENUM_RECINFO_BASIC2)
        if ret == self.__CMD_SUCCESS:
            bufview = memoryview(rbuf)
            pos = [0]
            try:
                if self.__readUshort(bufview, pos, len(rbuf)) >= self.__CMD_VER:
                    return self.__readVector(self.__readRecFileInfo, bufview, pos, len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendGetRecInfo(self, info_id: int) -> RecFileInfo | None:
        """ 録画済み情報取得 """
        ret, rbuf = await self.__sendCmd2(self.__CMD_EPG_SRV_GET_RECINFO2,
                                          lambda buf: self.__writeInt(buf, info_id))
        if ret == self.__CMD_SUCCESS:
            bufview = memoryview(rbuf)
            pos = [0]
            try:
                if self.__readUshort(bufview, pos, len(rbuf)) >= self.__CMD_VER:
                    return self.__readRecFileInfo(bufview, pos, len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendEnumTunerReserve(self) -> list[TunerReserveInfo] | None:
        """ チューナーごとの予約一覧を取得する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_ENUM_TUNER_RESERVE)
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readVector(self.__readTunerReserveInfo, memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def sendEnumPlugIn(self, index: Literal[1, 2]) -> list[str] | None:
        """ PlugIn ファイルの一覧を取得する """
        ret, rbuf = await self.__sendCmd(self.__CMD_EPG_SRV_ENUM_PLUGIN,
                                         lambda buf: self.__writeUshort(buf, index))
        if ret == self.__CMD_SUCCESS:
            try:
                return self.__readVector(self.__readString, memoryview(rbuf), [0], len(rbuf))
            except self.__ReadError:
                pass
        return None

    async def openViewStream(self, process_id: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        """ View アプリの SrvPipe ストリームの転送を開始する """
        to = time.monotonic() + self.__connect_timeout_sec
        buf = bytearray()
        self.__writeInt(buf, self.__CMD_EPG_SRV_RELAY_VIEW_STREAM)
        self.__writeInt(buf, 4)
        self.__writeInt(buf, process_id)

        # TCP/IP モードであること
        if self.__host is None:
            return None

        try:
            connection = await asyncio.wait_for(asyncio.open_connection(self.__host, self.__port),  max(to - time.monotonic(), 0.))
            reader: asyncio.StreamReader = connection[0]
            writer: asyncio.StreamWriter = connection[1]
        except Exception:
            return None
        try:
            writer.write(buf)
            await asyncio.wait_for(writer.drain(), max(to - time.monotonic(), 0.))
            rbuf = bytearray()
            while len(rbuf) < 8:
                r = await asyncio.wait_for(reader.readexactly(8 - len(rbuf)), max(to - time.monotonic(), 0.))
                if not r:
                    break
                rbuf.extend(r)
        except Exception:
            writer.close()
            return None

        if len(rbuf) == 8:
            ret = self.__readInt(memoryview(rbuf), [0], 8)
            if ret == self.__CMD_SUCCESS:
                return (reader, writer)
        try:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), max(to - time.monotonic(), 0.))
        except Exception:
            pass
        return None

    # EDCB/EpgTimer の CtrlCmd.cs より
    __CMD_SUCCESS = 1
    __CMD_VER = 5
    __CMD_VIEW_APP_SET_BONDRIVER = 201
    __CMD_VIEW_APP_GET_BONDRIVER = 202
    __CMD_VIEW_APP_SET_CH = 205
    __CMD_VIEW_APP_CLOSE = 208
    __CMD_EPG_SRV_RELAY_VIEW_STREAM = 301
    __CMD_EPG_SRV_DEL_RESERVE = 1014
    __CMD_EPG_SRV_ENUM_TUNER_RESERVE = 1016
    __CMD_EPG_SRV_ENUM_SERVICE = 1021
    __CMD_EPG_SRV_ENUM_PG_INFO_EX = 1029
    __CMD_EPG_SRV_ENUM_PG_ARC = 1030
    __CMD_EPG_SRV_FILE_COPY = 1060
    __CMD_EPG_SRV_ENUM_PLUGIN = 1061
    __CMD_EPG_SRV_NWTV_ID_SET_CH = 1073
    __CMD_EPG_SRV_NWTV_ID_CLOSE = 1074
    __CMD_EPG_SRV_ENUM_RESERVE2 = 2011
    __CMD_EPG_SRV_GET_RESERVE2 = 2012
    __CMD_EPG_SRV_ADD_RESERVE2 = 2013
    __CMD_EPG_SRV_CHG_RESERVE2 = 2015
    __CMD_EPG_SRV_ENUM_RECINFO_BASIC2 = 2020
    __CMD_EPG_SRV_GET_RECINFO2 = 2024
    __CMD_EPG_SRV_FILE_COPY2 = 2060

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
            writer.close()
            return None, b''
        try:
            writer.close()
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
    def __writeByte(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(1, 'little'))

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
    def __writeLong(buf: bytearray, v: int) -> None:
        buf.extend(v.to_bytes(8, 'little', signed=True))

    @staticmethod
    def __writeIntInplace(buf: bytearray, pos: int, v: int) -> None:
        buf[pos:pos + 4] = v.to_bytes(4, 'little', signed=True)

    @classmethod
    def __writeSystemTime(cls, buf: bytearray, v: datetime.datetime) -> None:
        cls.__writeUshort(buf, v.year)
        cls.__writeUshort(buf, v.month)
        cls.__writeUshort(buf, v.isoweekday() % 7)
        cls.__writeUshort(buf, v.day)
        cls.__writeUshort(buf, v.hour)
        cls.__writeUshort(buf, v.minute)
        cls.__writeUshort(buf, v.second)
        cls.__writeUshort(buf, 0)

    @classmethod
    def __writeString(cls, buf: bytearray, v: str) -> None:
        vv = v.encode('utf_16_le')
        cls.__writeInt(buf, 6 + len(vv))
        buf.extend(vv)
        cls.__writeUshort(buf, 0)

    @classmethod
    def __writeVector(cls, write_func: Callable[[bytearray, T], None], buf: bytearray, v: list[T]) -> None:
        pos = len(buf)
        cls.__writeInt(buf, 0)
        cls.__writeInt(buf, len(v))
        for e in v:
            write_func(buf, e)
        cls.__writeIntInplace(buf, pos, len(buf) - pos)

    # 以下、各構造体のライター

    @classmethod
    def __writeSetChInfo(cls, buf: bytearray, v: SetChInfo) -> None:
        pos = len(buf)
        cls.__writeInt(buf, 0)
        cls.__writeInt(buf, 1 if v.get('use_sid') else 0)
        cls.__writeUshort(buf, v.get('onid', 0))
        cls.__writeUshort(buf, v.get('tsid', 0))
        cls.__writeUshort(buf, v.get('sid', 0))
        cls.__writeInt(buf, 1 if v.get('use_bon_ch') else 0)
        cls.__writeInt(buf, v.get('space_or_id', 0))
        cls.__writeInt(buf, v.get('ch_or_mode', 0))
        cls.__writeIntInplace(buf, pos, len(buf) - pos)

    @classmethod
    def __writeRecFileSetInfo(cls, buf: bytearray, v: RecFileSetInfo) -> None:
        pos = len(buf)
        cls.__writeInt(buf, 0)
        cls.__writeString(buf, v.get('rec_folder', ''))
        cls.__writeString(buf, v.get('write_plug_in', ''))
        cls.__writeString(buf, v.get('rec_name_plug_in', ''))
        cls.__writeString(buf, '')
        cls.__writeIntInplace(buf, pos, len(buf) - pos)

    @classmethod
    def __writeRecSettingData(cls, buf: bytearray, v: RecSettingData) -> None:
        pos = len(buf)
        cls.__writeInt(buf, 0)
        cls.__writeByte(buf, v.get('rec_mode', 0))
        cls.__writeByte(buf, v.get('priority', 0))
        cls.__writeByte(buf, v.get('tuijyuu_flag', False))
        cls.__writeUint(buf, v.get('service_mode', 0))
        cls.__writeByte(buf, v.get('pittari_flag', False))
        cls.__writeString(buf, v.get('bat_file_path', ''))
        cls.__writeVector(cls.__writeRecFileSetInfo, buf, v.get('rec_folder_list', []))
        cls.__writeByte(buf, v.get('suspend_mode', 0))
        cls.__writeByte(buf, v.get('reboot_flag', False))
        cls.__writeByte(buf, v.get('start_margin') is not None and v.get('end_margin') is not None)
        cls.__writeInt(buf, v.get('start_margin', 0))
        cls.__writeInt(buf, v.get('end_margin', 0))
        cls.__writeByte(buf, v.get('continue_rec_flag', False))
        cls.__writeByte(buf, v.get('partial_rec_flag', 0))
        cls.__writeUint(buf, v.get('tuner_id', 0))
        cls.__writeVector(cls.__writeRecFileSetInfo, buf, v.get('partial_rec_folder', []))
        cls.__writeIntInplace(buf, pos, len(buf) - pos)

    @classmethod
    def __writeReserveData(cls, buf: bytearray, v: ReserveData) -> None:
        pos = len(buf)
        cls.__writeInt(buf, 0)
        cls.__writeString(buf, v.get('title', ''))
        cls.__writeSystemTime(buf, v.get('start_time', cls.UNIX_EPOCH))
        cls.__writeUint(buf, v.get('duration_second', 0))
        cls.__writeString(buf, v.get('station_name', ''))
        cls.__writeUshort(buf, v.get('onid', 0))
        cls.__writeUshort(buf, v.get('tsid', 0))
        cls.__writeUshort(buf, v.get('sid', 0))
        cls.__writeUshort(buf, v.get('eid', 0))
        cls.__writeString(buf, v.get('comment', ''))
        cls.__writeInt(buf, v.get('reserve_id', 0))
        cls.__writeByte(buf, 0)
        cls.__writeByte(buf, v.get('overlap_mode', 0))
        cls.__writeString(buf, '')
        cls.__writeSystemTime(buf, v.get('start_time_epg', cls.UNIX_EPOCH))
        cls.__writeRecSettingData(buf, v.get('rec_setting', {}))
        cls.__writeInt(buf, 0)
        cls.__writeVector(cls.__writeString, buf, v.get('rec_file_name_list', []))
        cls.__writeInt(buf, 0)
        cls.__writeIntInplace(buf, pos, len(buf) - pos)

    class __ReadError(Exception):
        """ バッファをデータ構造として読み取るのに失敗したときの内部エラー """
        pass

    @classmethod
    def __readByte(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 1:
            raise cls.__ReadError
        v = int.from_bytes(buf[pos[0]:pos[0] + 1], 'little')
        pos[0] += 1
        return v

    @classmethod
    def __readUshort(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 2:
            raise cls.__ReadError
        v = int.from_bytes(buf[pos[0]:pos[0] + 2], 'little')
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
    def __readLong(cls, buf: memoryview, pos: list[int], size: int) -> int:
        if size - pos[0] < 8:
            raise cls.__ReadError
        v = int.from_bytes(buf[pos[0]:pos[0] + 8], 'little', signed=True)
        pos[0] += 8
        return v

    @classmethod
    def __readSystemTime(cls, buf: memoryview, pos: list[int], size: int) -> datetime.datetime:
        if size - pos[0] < 16:
            raise cls.__ReadError
        try:
            v = datetime.datetime(int.from_bytes(buf[pos[0]:pos[0] + 2], 'little'),
                                  int.from_bytes(buf[pos[0] + 2:pos[0] + 4], 'little'),
                                  int.from_bytes(buf[pos[0] + 6:pos[0] + 8], 'little'),
                                  int.from_bytes(buf[pos[0] + 8:pos[0] + 10], 'little'),
                                  int.from_bytes(buf[pos[0] + 10:pos[0] + 12], 'little'),
                                  int.from_bytes(buf[pos[0] + 12:pos[0] + 14], 'little'),
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
    def __readFileData(cls, buf: memoryview, pos: list[int], size: int) -> FileData:
        size = cls.__readStructIntro(buf, pos, size)
        name = cls.__readString(buf, pos, size)
        data_size = cls.__readInt(buf, pos, size)
        cls.__readInt(buf, pos, size)
        if data_size < 0 or size - pos[0] < data_size:
            raise cls.__ReadError
        v: FileData = {
            'name': name,
            'data': bytes(buf[pos[0]:pos[0] + data_size])
        }
        pos[0] = size
        return v

    @classmethod
    def __readRecFileSetInfo(cls, buf: memoryview, pos: list[int], size: int) -> RecFileSetInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: RecFileSetInfo = {
            'rec_folder': cls.__readString(buf, pos, size),
            'write_plug_in': cls.__readString(buf, pos, size),
            'rec_name_plug_in': cls.__readString(buf, pos, size)
        }
        cls.__readString(buf, pos, size)
        pos[0] = size
        return v

    @classmethod
    def __readRecSettingData(cls, buf: memoryview, pos: list[int], size: int) -> RecSettingData:
        size = cls.__readStructIntro(buf, pos, size)
        v: RecSettingData = {
            'rec_mode': cls.__readByte(buf, pos, size),
            'priority': cls.__readByte(buf, pos, size),
            'tuijyuu_flag': cls.__readByte(buf, pos, size) != 0,
            'service_mode': cls.__readUint(buf, pos, size),
            'pittari_flag': cls.__readByte(buf, pos, size) != 0,
            'bat_file_path': cls.__readString(buf, pos, size),
            'rec_folder_list': cls.__readVector(cls.__readRecFileSetInfo, buf, pos, size),
            'suspend_mode': cls.__readByte(buf, pos, size),
            'reboot_flag': cls.__readByte(buf, pos, size) != 0
        }
        use_margin_flag = cls.__readByte(buf, pos, size) != 0
        start_margin = cls.__readInt(buf, pos, size)
        end_margin = cls.__readInt(buf, pos, size)
        if use_margin_flag:
            v['start_margin'] = start_margin
            v['end_margin'] = end_margin
        v['continue_rec_flag'] = cls.__readByte(buf, pos, size) != 0
        v['partial_rec_flag'] = cls.__readByte(buf, pos, size)
        v['tuner_id'] = cls.__readUint(buf, pos, size)
        v['partial_rec_folder'] = cls.__readVector(cls.__readRecFileSetInfo, buf, pos, size)
        pos[0] = size
        return v

    @classmethod
    def __readReserveData(cls, buf: memoryview, pos: list[int], size: int) -> ReserveData:
        size = cls.__readStructIntro(buf, pos, size)
        v: ReserveData = {
            'title': cls.__readString(buf, pos, size),
            'start_time': cls.__readSystemTime(buf, pos, size),
            'duration_second': cls.__readUint(buf, pos, size),
            'station_name': cls.__readString(buf, pos, size),
            'onid': cls.__readUshort(buf, pos, size),
            'tsid': cls.__readUshort(buf, pos, size),
            'sid': cls.__readUshort(buf, pos, size),
            'eid': cls.__readUshort(buf, pos, size),
            'comment': cls.__readString(buf, pos, size),
            'reserve_id': cls.__readInt(buf, pos, size)
        }
        cls.__readByte(buf, pos, size)
        v['overlap_mode'] = cls.__readByte(buf, pos, size)
        cls.__readString(buf, pos, size)
        v['start_time_epg'] = cls.__readSystemTime(buf, pos, size)
        v['rec_setting'] = cls.__readRecSettingData(buf, pos, size)
        cls.__readInt(buf, pos, size)
        v['rec_file_name_list'] = cls.__readVector(cls.__readString, buf, pos, size)
        cls.__readInt(buf, pos, size)
        pos[0] = size
        return v

    @classmethod
    def __readRecFileInfo(cls, buf: memoryview, pos: list[int], size: int) -> RecFileInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: RecFileInfo = {
            'id': cls.__readInt(buf, pos, size),
            'rec_file_path': cls.__readString(buf, pos, size),
            'title': cls.__readString(buf, pos, size),
            'start_time': cls.__readSystemTime(buf, pos, size),
            'duration_sec': cls.__readInt(buf, pos, size),
            'service_name': cls.__readString(buf, pos, size),
            'onid': cls.__readUshort(buf, pos, size),
            'tsid': cls.__readUshort(buf, pos, size),
            'sid': cls.__readUshort(buf, pos, size),
            'eid': cls.__readUshort(buf, pos, size),
            'drops': cls.__readLong(buf, pos, size),
            'scrambles': cls.__readLong(buf, pos, size),
            'rec_status': cls.__readInt(buf, pos, size),
            'start_time_epg': cls.__readSystemTime(buf, pos, size),
            'comment': cls.__readString(buf, pos, size),
            'program_info': cls.__readString(buf, pos, size),
            'err_info': cls.__readString(buf, pos, size),
            'protect_flag': cls.__readByte(buf, pos, size) != 0
        }
        pos[0] = size
        return v

    @classmethod
    def __readTunerReserveInfo(cls, buf: memoryview, pos: list[int], size: int) -> TunerReserveInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: TunerReserveInfo = {
            'tuner_id': cls.__readUint(buf, pos, size),
            'tuner_name': cls.__readString(buf, pos, size),
            'reserve_list': cls.__readVector(cls.__readInt, buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readServiceEventInfo(cls, buf: memoryview, pos: list[int], size: int) -> ServiceEventInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: ServiceEventInfo = {
            'service_info': cls.__readServiceInfo(buf, pos, size),
            'event_list': cls.__readVector(cls.__readEventInfo, buf, pos, size)
        }
        pos[0] = size
        return v

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

    @classmethod
    def __readEventInfo(cls, buf: memoryview, pos: list[int], size: int) -> EventInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: EventInfo = {
            'onid': cls.__readUshort(buf, pos, size),
            'tsid': cls.__readUshort(buf, pos, size),
            'sid': cls.__readUshort(buf, pos, size),
            'eid': cls.__readUshort(buf, pos, size),
            'free_ca_flag': 0
        }

        start_time_flag = cls.__readByte(buf, pos, size)
        start_time = cls.__readSystemTime(buf, pos, size)
        if start_time_flag != 0:
            v['start_time'] = start_time

        duration_flag = cls.__readByte(buf, pos, size)
        duration_sec = cls.__readInt(buf, pos, size)
        if duration_flag != 0:
            v['duration_sec'] = duration_sec

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['short_info'] = cls.__readShortEventInfo(buf, pos, size)

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['ext_info'] = cls.__readExtendedEventInfo(buf, pos, size)

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['content_info'] = cls.__readContentInfo(buf, pos, size)

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['component_info'] = cls.__readComponentInfo(buf, pos, size)

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['audio_info'] = cls.__readAudioComponentInfo(buf, pos, size)

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['event_group_info'] = cls.__readEventGroupInfo(buf, pos, size)

        if cls.__readInt(buf, pos, size) != 4:
            pos[0] -= 4
            v['event_relay_info'] = cls.__readEventGroupInfo(buf, pos, size)

        v['free_ca_flag'] = cls.__readByte(buf, pos, size)
        pos[0] = size
        return v

    @classmethod
    def __readShortEventInfo(cls, buf: memoryview, pos: list[int], size: int) -> ShortEventInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: ShortEventInfo = {
            'event_name': cls.__readString(buf, pos, size),
            'text_char': cls.__readString(buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readExtendedEventInfo(cls, buf: memoryview, pos: list[int], size: int) -> ExtendedEventInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: ExtendedEventInfo = {
            'text_char': cls.__readString(buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readContentInfo(cls, buf: memoryview, pos: list[int], size: int) -> ContentInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: ContentInfo = {
            'nibble_list': cls.__readVector(cls.__readContentData, buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readContentData(cls, buf: memoryview, pos: list[int], size: int) -> ContentData:
        size = cls.__readStructIntro(buf, pos, size)
        cn = cls.__readUshort(buf, pos, size)
        un = cls.__readUshort(buf, pos, size)
        v: ContentData = {
            'content_nibble': (cn >> 8 | cn << 8) & 0xffff,
            'user_nibble': (un >> 8 | un << 8) & 0xffff
        }
        pos[0] = size
        return v

    @classmethod
    def __readComponentInfo(cls, buf: memoryview, pos: list[int], size: int) -> ComponentInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: ComponentInfo = {
            'stream_content': cls.__readByte(buf, pos, size),
            'component_type': cls.__readByte(buf, pos, size),
            'component_tag': cls.__readByte(buf, pos, size),
            'text_char': cls.__readString(buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readAudioComponentInfo(cls, buf: memoryview, pos: list[int], size: int) -> AudioComponentInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: AudioComponentInfo = {
            'component_list': cls.__readVector(cls.__readAudioComponentInfoData, buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readAudioComponentInfoData(cls, buf: memoryview, pos: list[int], size: int) -> AudioComponentInfoData:
        size = cls.__readStructIntro(buf, pos, size)
        v: AudioComponentInfoData = {
            'stream_content': cls.__readByte(buf, pos, size),
            'component_type': cls.__readByte(buf, pos, size),
            'component_tag': cls.__readByte(buf, pos, size),
            'stream_type': cls.__readByte(buf, pos, size),
            'simulcast_group_tag': cls.__readByte(buf, pos, size),
            'es_multi_lingual_flag': cls.__readByte(buf, pos, size),
            'main_component_flag': cls.__readByte(buf, pos, size),
            'quality_indicator': cls.__readByte(buf, pos, size),
            'sampling_rate': cls.__readByte(buf, pos, size),
            'text_char': cls.__readString(buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readEventGroupInfo(cls, buf: memoryview, pos: list[int], size: int) -> EventGroupInfo:
        size = cls.__readStructIntro(buf, pos, size)
        v: EventGroupInfo = {
            'group_type': cls.__readByte(buf, pos, size),
            'event_data_list': cls.__readVector(cls.__readEventData, buf, pos, size)
        }
        pos[0] = size
        return v

    @classmethod
    def __readEventData(cls, buf: memoryview, pos: list[int], size: int) -> EventData:
        size = cls.__readStructIntro(buf, pos, size)
        v: EventData = {
            'onid': cls.__readUshort(buf, pos, size),
            'tsid': cls.__readUshort(buf, pos, size),
            'sid': cls.__readUshort(buf, pos, size),
            'eid': cls.__readUshort(buf, pos, size)
        }
        pos[0] = size
        return v
