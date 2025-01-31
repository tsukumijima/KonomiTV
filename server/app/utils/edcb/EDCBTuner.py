
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import time
from typing import ClassVar

from app.utils.edcb import SetChInfo
from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
from app.utils.edcb.EDCBUtil import EDCBUtil
from app.utils.edcb.PipeStreamReader import PipeStreamReader


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


    def getEDCBNetworkTVID(self) -> int:
        """
        EpgDataCap_Bon の NetworkTV ID を取得する

        Returns:
            int: 取得した EpgDataCap_Bon の NetworkTV ID
        """

        return self._edcb_networktv_id


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
