
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import time
from threading import Lock
from typing import ClassVar, Literal, cast

from app.utils.edcb import SetChInfo
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.edcb.PipeStreamReader import PipeStreamReader


EDCBTunerState = Literal['Idle', 'Starting', 'Active', 'Cancelling']


class EDCBTuner:
    """ EDCB バックエンドのチューナーを制御するクラス """

    # 全てのチューナーインスタンスが格納されるリスト
    # チューナーを閉じずに再利用するため、全てのチューナーインスタンスにアクセスできるようにする
    __instances: ClassVar[list[EDCBTuner]] = []

    # NetworkTV モードのチューナーを識別する任意の整数
    # ほかのロケフリ系アプリと重複しないように 500 から増分する
    __next_networktv_id: ClassVar[int] = 500
    __lock: ClassVar[Lock] = Lock()


    @classmethod
    def getOrCreate(cls, owner_live_stream_id: str) -> EDCBTuner:
        """
        再利用可能なチューナーインスタンスを取得する
        再利用できるチューナーがない場合は新規に生成する

        Args:
            owner_live_stream_id (str): 制御権限を持つライブストリーム ID

        Returns:
            EDCBTuner: 取得したチューナーインスタンス
        """

        # インスタンスの再利用/生成は排他制御する
        ## 競合した場合に同じチューナーを二重取得しないようにする
        with cls.__lock:

            # 再利用可能なチューナーインスタンスがあれば、それを返す
            for instance in cls.__instances:
                # 未使用かつ未割り当てであれば再利用する
                if instance._state == 'Idle' and instance._owner_live_stream_id is None and instance._locked is False:
                    # 制御権限を割り当てる
                    instance._owner_live_stream_id = owner_live_stream_id
                    return instance

            # NetworkTV ID を払い出す
            edcb_networktv_id = cls.__next_networktv_id
            cls.__next_networktv_id += 1

            # 新しいチューナーインスタンスを生成する
            ## __init__ は直接呼び出さず、このメソッドからのみ生成する
            instance = cls(edcb_networktv_id, owner_live_stream_id)

            # 生成したチューナーインスタンスを登録する
            cls.__instances.append(instance)

            return instance


    def __init__(self, edcb_networktv_id: int, owner_live_stream_id: str) -> None:
        """
        チューナーインスタンスを初期化する
        直接呼び出してはいけない (必ず getOrCreate() を経由すること)

        Args:
            edcb_networktv_id (int): NetworkTV ID
            owner_live_stream_id (str): 制御権限を持つライブストリーム ID
        """

        # NID・SID・TSID を設定
        ## setChannel() で設定するため、初期値は 0 にする
        self.network_id: int = 0
        self.service_id: int = 0
        self.transport_stream_id: int = 0

        # チューナーがロックされているかどうか
        ## 一般に ONAir 時はロックされ、Idling 時はアンロックされる
        self._locked: bool = False

        # EpgDataCap_Bon の NetworkTV ID
        ## NetworkTV ID は NetworkTV モードの EpgDataCap_Bon を識別するために割り当てられる ID
        self._edcb_networktv_id: int = edcb_networktv_id

        # EpgDataCap_Bon のプロセス ID
        ## プロセス ID が None のときはチューナーが起動されていないものとして扱う
        self._edcb_process_id: int | None = None

        # チューナーとのストリーミング接続を閉じるための StreamWriter (TCP/IP モード時)
        ## まだ接続していないとき、接続が閉じられた後は None になる
        self._edcb_stream_writer: asyncio.StreamWriter | None = None

        # チューナーとのストリーミング接続の StreamReader (TCP/IP モード時)
        ## まだ接続していないとき、接続が閉じられた後は None になる
        self._edcb_stream_reader: asyncio.StreamReader | None = None

        # チューナーとのストリーミング接続を閉じるためのパイプ (名前付きパイプモード時)
        ## まだ接続していないとき、接続が閉じられた後は None になる
        self._edcb_pipe_stream_reader: PipeStreamReader | None = None

        # このチューナーの利用状態
        ## Idle: 未使用 / Starting: 起動・チャンネル切り替え中 / Active: 受信中 / Cancelling: キャンセル中
        self._state: EDCBTunerState = 'Idle'

        # このチューナーの制御権限を持つライブストリーム ID
        ## None の場合は未割り当て
        self._owner_live_stream_id: str | None = owner_live_stream_id


    def getEDCBNetworkTVID(self) -> int:
        """
        EpgDataCap_Bon の NetworkTV ID を取得する

        Returns:
            int: 取得した EpgDataCap_Bon の NetworkTV ID
        """

        # NetworkTV ID を返す
        return self._edcb_networktv_id


    def getState(self) -> EDCBTunerState:
        """
        チューナーの現在の状態を取得する

        Returns:
            EDCBTunerState: 現在の状態
        """

        # 現在の状態を返す
        return self._state


    def setState(self, state: EDCBTunerState) -> None:
        """
        チューナーの状態を設定する

        Args:
            state (EDCBTunerState): 設定する状態
        """

        # 状態を更新する
        self._state = state


    def _isOwner(self, live_stream_id: str) -> bool:
        """
        指定されたライブストリームがこのチューナーの制御権限を持っているかどうかを返す

        Args:
            live_stream_id (str): ライブストリーム ID

        Returns:
            bool: 制御権限を持っているかどうか
        """

        # 制御権限の一致を返す
        return self._owner_live_stream_id == live_stream_id


    async def setChannel(
        self,
        network_id: int,
        service_id: int,
        transport_stream_id: int,
        owner_live_stream_id: str,
    ) -> bool:
        """
        チューナーのチャンネルを設定する
        チューナーが起動していない場合は起動する

        Args:
            network_id (int): ネットワーク ID
            service_id (int): サービス ID
            transport_stream_id (int): トランスポートストリーム ID
            owner_live_stream_id (str): 制御権限を持つライブストリーム ID

        Returns:
            bool: チャンネル設定に成功したかどうか
        """

        # 制御権限が一致していない場合は処理しない
        if self._isOwner(owner_live_stream_id) is False:
            return False

        # キャンセル中は処理しない
        if self._state == 'Cancelling':
            return False

        # NID・SID・TSID を更新
        self.network_id = network_id
        self.service_id = service_id
        self.transport_stream_id = transport_stream_id

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
        self._state = 'Starting'
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
            self._state = 'Idle'
            return False

        # 起動済みとして状態を更新する
        self._state = 'Active'

        return True


    async def connect(self, owner_live_stream_id: str) -> asyncio.StreamReader | PipeStreamReader | None:
        """
        チューナーに接続し、放送波を受け取るための TCP ソケットまたは名前付きパイプを返す

        Args:
            owner_live_stream_id (str): 制御権限を持つライブストリーム ID

        Returns:
            asyncio.StreamReader | PipeStreamReader | None: TCP ソケットまたは名前付きパイプの StreamReader (取得できなかった場合は None を返す)
        """

        # 制御権限が一致していない場合は処理しない
        if self._isOwner(owner_live_stream_id) is False:
            return None

        # キャンセル中は処理しない
        if self._state == 'Cancelling':
            return None

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
        if stream_reader is None:
            self._state = 'Idle'
            return None

        # Reader / Writer を保持する
        if stream_writer is not None:
            self._edcb_stream_writer = stream_writer
            self._edcb_stream_reader = cast(asyncio.StreamReader, stream_reader)

        # 接続済みとして状態を更新する
        self._state = 'Active'

        return stream_reader


    async def disconnect(self, owner_live_stream_id: str) -> None:
        """
        チューナーとのストリーミング接続を閉じる
        ストリーミングが終了した際に必ず呼び出す必要がある

        Args:
            owner_live_stream_id (str): 制御権限を持つライブストリーム ID
        """

        # 制御権限が一致していない場合は処理しない
        if self._isOwner(owner_live_stream_id) is False:
            return

        # TCP/IP モード
        if self._edcb_stream_writer is not None:
            self._edcb_stream_writer.close()
            await self._edcb_stream_writer.wait_closed()
            self._edcb_stream_writer = None
            self._edcb_stream_reader = None

        # 名前付きパイプモード
        elif self._edcb_pipe_stream_reader is not None:
            await self._edcb_pipe_stream_reader.close()
            self._edcb_pipe_stream_reader = None

        # 切断済みとして状態を更新する
        # Cancelling 状態の場合は handoff シーケンスの途中であるため、状態を維持する
        ## handoff 後の旧タスク終了時に getState() == 'Cancelling' でチューナー close をスキップする判定に使われる
        if self._state != 'Cancelling':
            self._state = 'Idle'


    def isDisconnected(self) -> bool:
        """
        チューナーとのストリーミング接続が閉じられているかどうかを返す

        Returns:
            bool: チューナーとのストリーミング接続が閉じられているかどうか
        """

        # TCP/IP モード
        if self._edcb_stream_writer is not None:
            return self._edcb_stream_writer.is_closing()

        # 名前付きパイプモード
        if self._edcb_pipe_stream_reader is not None:
            return self._edcb_pipe_stream_reader.is_closing()

        return True


    def lock(self, owner_live_stream_id: str | None) -> bool:
        """
        チューナーをロックする
        ロックしておかないとチューナーの制御を横取りされてしまうので、基本はロック状態にする

        Args:
            owner_live_stream_id (str | None): 制御権限を持つライブストリーム ID

        Returns:
            bool: ロックできたかどうか
        """

        # 制御権限が一致していない場合は処理しない
        if owner_live_stream_id is None or self._isOwner(owner_live_stream_id) is False:
            return False

        # ロック状態にする
        self._locked = True
        return True


    def unlock(self, owner_live_stream_id: str | None) -> bool:
        """
        チューナーをアンロックする
        チューナーがアンロックされている場合、起動中の EpgDataCap_Bon は次のチューナーインスタンスの初期化時に再利用される

        Args:
            owner_live_stream_id (str | None): 制御権限を持つライブストリーム ID

        Returns:
            bool: アンロックできたかどうか
        """

        # 制御権限が一致していない場合は処理しない
        if owner_live_stream_id is None or self._isOwner(owner_live_stream_id) is False:
            return False

        # アンロック状態にする
        self._locked = False
        return True


    def handoff(self, current_owner_live_stream_id: str, next_owner_live_stream_id: str) -> bool:
        """
        チューナーの制御権限を別のライブストリームに移譲する
        ストリーミング接続のクリーンアップは呼び出し元で行う

        Args:
            current_owner_live_stream_id (str): 現在の制御権限を持つライブストリーム ID
            next_owner_live_stream_id (str): 移譲先のライブストリーム ID

        Returns:
            bool: 移譲に成功したかどうか
        """

        # 制御権限が一致していない場合は処理しない
        if self._isOwner(current_owner_live_stream_id) is False:
            return False

        # 再利用可能な状態に戻す
        self._state = 'Idle'
        self._locked = False

        # 制御権限を移譲する
        self._owner_live_stream_id = next_owner_live_stream_id

        return True


    async def close(self, owner_live_stream_id: str | None, force: bool = False) -> bool:
        """
        チューナーを終了する

        Args:
            owner_live_stream_id (str | None): 制御権限を持つライブストリーム ID
            force (bool): 制御権限の一致を無視して終了するかどうか

        Returns:
            bool: チューナーを終了できたかどうか
        """

        # 制御権限が一致していない場合は処理しない
        if force is False and (owner_live_stream_id is None or self._isOwner(owner_live_stream_id) is False):
            return False

        # チューナーを閉じ、実行結果を取得する
        edcb = CtrlCmdUtil()
        result = await edcb.sendNwTVIDClose(self._edcb_networktv_id)

        # チューナーが閉じられたので、プロセス ID を None に戻す
        self._edcb_process_id = None

        # ストリーミング接続の状態を破棄する
        self._edcb_stream_writer = None
        self._edcb_stream_reader = None
        self._edcb_pipe_stream_reader = None

        # 状態を初期化する
        self._state = 'Idle'
        self._owner_live_stream_id = None
        self._locked = False

        # インスタンスの登録を削除する
        if self in EDCBTuner.__instances:
            EDCBTuner.__instances.remove(self)

        return result


    @classmethod
    async def closeAll(cls) -> None:
        """
        現在起動中の全てのチューナーを終了する
        明示的に終了しないといつまでも起動してしまうため、アプリケーション終了時に実行する
        """

        # 登録されているチューナーを順に終了する
        for instance in list(cls.__instances):
            await instance.close(instance._owner_live_stream_id, force=True)
