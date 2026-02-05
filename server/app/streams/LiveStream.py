
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

import asyncio
import time
from typing import ClassVar, Literal

from hashids import Hashids

from app import logging
from app.config import Config
from app.constants import QUALITY_TYPES
from app.schemas import LiveStreamStatus
from app.streams.LiveEncodingTask import LiveEncodingTask
from app.streams.LivePSIDataArchiver import LivePSIDataArchiver
from app.utils.edcb.EDCBTuner import EDCBTuner


class LiveStreamClient:
    """ ライブストリームのクライアントを表すクラス """

    def __init__(self, live_stream: LiveStream, client_type: Literal['mpegts']) -> None:
        """
        ライブストリーミングクライアントのインスタンスを初期化する
        LiveStreamClient は LiveStream クラス外から初期化してはいけない
        (必ず LiveStream.connect() で取得した LiveStreamClient を利用すること)

        Args:
            live_stream (LiveStream): クライアントが紐づくライブストリームのインスタンス
            client_type (Literal['mpegts']): クライアントの種別 (mpegts, ll-hls クライアントは廃止された)
        """

        # このクライアントが紐づくライブストリームのインスタンス
        self._live_stream: LiveStream = live_stream

        # クライアント ID
        ## ミリ秒単位のタイムスタンプをもとに、Hashids による10文字のユニーク ID が生成される
        self.client_id: str = 'MPEGTS-' + Hashids(min_length=10).encode(int(time.time() * 1000))

        # クライアントの種別 (mpegts)
        self.client_type: Literal['mpegts'] = client_type

        # ストリームデータが入る Queue
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        # ストリームデータの最終読み取り時刻のタイミング
        ## 最終読み取り時刻から 10 秒経過したクライアントは LiveStream.writeStreamData() でタイムアウトと判断され、削除される
        self._stream_data_read_at: float = time.time()


    @property
    def stream_data_read_at(self) -> float:
        """ ストリームデータの最終読み取り時刻のタイミング (読み取り専用) """
        return self._stream_data_read_at


    async def readStreamData(self) -> bytes | None:
        """
        自分自身の Queue からストリームデータを読み取って返す
        Queue 内のストリームデータは writeStreamData() で書き込まれたもの

        Args:
            client (LiveStreamClient): ライブストリームクライアントのインスタンス

        Returns:
            bytes | None: ストリームデータ (エンコードタスクが終了した場合は None が返る)
        """

        # mpegts クライアント以外では実行しない
        if self.client_type != 'mpegts':
            return None

        # ストリームデータの最終読み取り時刻を更新
        self._stream_data_read_at = time.time()

        # Queue から読み取ったストリームデータを返す
        try:
            return await self._queue.get()
        except TypeError:
            return None


    def writeStreamData(self, stream_data: bytes | None) -> None:
        """
        自分自身の Queue にストリームデータを書き込む
        Queue 内のストリームデータは readStreamData() で読み取られる

        Args:
            stream_data (bytes): 書き込むストリームデータ (エンコードタスクが終了した場合は None を渡す)
        """

        # mpegts クライアント以外では実行しない
        if self.client_type != 'mpegts':
            return None

        # Queue にストリームデータを書き込む
        self._queue.put_nowait(stream_data)


class LiveStream:
    """ ライブストリームを管理するクラス """

    # ライブストリームのインスタンスが入る、ライブストリーム ID をキーとした辞書
    # この辞書にライブストリームに関する全てのデータが格納されている
    __instances: ClassVar[dict[str, LiveStream]] = {}


    # 必ずライブストリーム ID ごとに1つのインスタンスになるように (Singleton)
    def __new__(cls, display_channel_id: str, quality: QUALITY_TYPES) -> LiveStream:

        # まだ同じライブストリーム ID のインスタンスがないときだけ、インスタンスを生成する
        # (チャンネルID)-(映像の品質) で一意な ID になる
        live_stream_id = f'{display_channel_id}-{quality}'
        if live_stream_id not in cls.__instances:

            # 新しいライブストリームのインスタンスを生成する
            instance = super().__new__(cls)

            # ライブストリーム ID を設定
            instance.live_stream_id = live_stream_id

            # チャンネル ID と映像の品質を設定
            instance.display_channel_id = display_channel_id
            instance.quality = quality

            # ライブストリームクライアントが入るリスト
            ## クライアントの接続が切断された場合、このリストからも削除される
            ## したがって、クライアントの数はこのリストの長さで求められる
            instance._clients = []

            # ストリームのステータス
            ## Offline, Standby, ONAir, Idling, Restart のいずれか
            instance._status = 'Offline'

            # ストリームのステータス詳細
            instance._detail = 'ライブストリームは Offline です。'

            # ストリームの開始時刻
            instance._started_at = 0

            # ストリームのステータスの最終更新時刻のタイムスタンプ
            instance._updated_at = 0

            # ストリームデータの最終書き込み時刻のタイムスタンプ
            ## 最終書き込み時刻が 5 秒 (ONAir 時) 20 秒 (Standby 時) 以上更新されていない場合は、
            ## エンコーダーがフリーズしたものとみなしてエンコードタスクを再起動する
            instance._stream_data_written_at = 0

            # 実行中の LiveEncodingTask のタスクへの参照
            # ref: https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
            instance._live_encoding_task_ref = None

            # PSI/SI データアーカイバーのインスタンス
            ## LiveStreamsRouter からアクセスする必要があるためここに設置している
            instance.psi_data_archiver = None

            # EDCB バックエンドのチューナーインスタンス
            ## Mirakurun バックエンドを使っている場合は None のまま
            instance.tuner = None

            # チューナー再利用時の排他ロック
            ## チューナー再利用の競合を避けるため、LiveStream ごとにロックを持つ
            instance._tuner_lock = asyncio.Lock()

            # 生成したインスタンスを登録する
            cls.__instances[live_stream_id] = instance

        # 登録されているインスタンスを返す
        return cls.__instances[live_stream_id]


    def __init__(self, display_channel_id: str, quality: QUALITY_TYPES) -> None:
        """
        ライブストリームのインスタンスを取得する

        Args:
            display_channel_id (str): チャンネルID
            quality (QUALITY_TYPES): 映像の品質 (1080p-60fps ~ 240p)
        """

        # インスタンス変数の型ヒントを定義
        # Singleton のためインスタンスの生成は __new__() で行うが、__init__() も定義しておかないと補完がうまく効かない
        self.live_stream_id: str
        self.display_channel_id: str
        self.quality: QUALITY_TYPES
        self._clients: list[LiveStreamClient]
        self._status: Literal['Offline', 'Standby', 'ONAir', 'Idling', 'Restart']
        self._detail: str
        self._started_at: float
        self._updated_at: float
        self._stream_data_written_at: float
        self._live_encoding_task_ref: asyncio.Task[None] | None
        self.psi_data_archiver: LivePSIDataArchiver | None
        self.tuner: EDCBTuner | None
        self._tuner_lock: asyncio.Lock


    @classmethod
    def getAllLiveStreams(cls) -> list[LiveStream]:
        """
        全てのライブストリームのインスタンスを取得する

        Returns:
            list[LiveStream]: ライブストリームのインスタンスの入ったリスト
        """

        # __instances 辞書を values() で値だけのリストにしたものを返す
        return list(cls.__instances.values())


    @classmethod
    def getONAirLiveStreams(cls) -> list[LiveStream]:
        """
        現在 ONAir 状態のライブストリームのインスタンスを取得する

        Returns:
            list[LiveStream]: 現在 ONAir 状態のライブストリームのインスタンスのリスト
        """

        result: list[LiveStream] = []

        # 現在 ONAir 状態のライブストリームに絞り込む
        for live_stream in LiveStream.getAllLiveStreams():
            if live_stream.getStatus().status == 'ONAir':
                result.append(live_stream)

        return result


    @classmethod
    def getIdlingLiveStreams(cls) -> list[LiveStream]:
        """
        現在 Idling 状態のライブストリームのインスタンスを取得する

        Returns:
            list[LiveStream]: 現在 Idling 状態のライブストリームのインスタンスのリスト
        """

        result: list[LiveStream] = []

        # 現在 Idling 状態のライブストリームに絞り込む
        for live_stream in LiveStream.getAllLiveStreams():
            if live_stream.getStatus().status == 'Idling':
                result.append(live_stream)

        return result


    @classmethod
    def getViewerCount(cls, display_channel_id: str) -> int:
        """
        指定されたチャンネルのライブストリームの現在の視聴者数を取得する

        Args:
            display_channel_id (str): チャンネルID

        Returns:
            int: 視聴者数
        """

        # 指定されたチャンネル ID に紐づくライブストリームを探して視聴者数を集計
        viewer_count = 0
        for live_stream in LiveStream.getAllLiveStreams():
            if live_stream.display_channel_id == display_channel_id:
                viewer_count += live_stream.getStatus().client_count

        return viewer_count


    async def connect(self, client_type: Literal['mpegts']) -> LiveStreamClient:
        """
        ライブストリームに接続して、新しくライブストリームに登録されたクライアントを返す
        この時点でライブストリームが Offline ならば、新たにエンコードタスクが起動される

        Args:
            client_type (Literal['mpegts']): クライアントの種別 (mpegts, ll-hls クライアントは廃止された)

        Returns:
            LiveStreamClient: ライブストリームクライアントのインスタンス
        """

        # ***** ステータスの切り替え *****

        current_status = self._status
        should_start_task: bool = False

        # ライブストリームが Offline な場合、新たにエンコードタスクを起動する
        if current_status == 'Offline':

            # ステータスを Standby に設定
            # 現在 Idling 状態のライブストリームを探す前に設定しないと多重に LiveEncodingTask が起動しかねず、重篤な不具合につながる
            async with self._tuner_lock:
                if self._status == 'Offline':
                    self.setStatus('Standby', 'エンコードタスクを起動しています…')
                    should_start_task = True

            # 一般にチューナーリソースは無尽蔵にあるわけではないので、現在 Idling（=つまり誰も見ていない）ライブストリームがあるのなら
            # それを Offline にしてチューナーリソースを解放し、新しいライブストリームがチューナーを使えるようにする
            ## EDCB バックエンドの場合はチューナーインスタンスを直接移譲して再利用できるため、より高度なチューナー再利用ロジックを実行する
            ## Mirakurun バックエンドの場合はチューナー管理が Mirakurun/mirakc 側で行われるため、
            ## Idling ストリームを Offline にしてチューナーを解放するだけでよい (チューナーインスタンスの移譲は不要)
            is_edcb_backend = (
                Config().general.backend == 'EDCB' and
                Config().general.always_receive_tv_from_mirakurun is False
            )

            # EDCB バックエンドの場合は、再利用できるチューナーがあれば取得しておく
            if should_start_task is True and is_edcb_backend is True:

                # チューナー再利用の対象になりうる Standby / ONAir / Idling のストリームを探す
                # (クライアントが 0 のもののみを対象にする)
                ## Idling への移行は非同期で遅れて発生するため、短時間リトライする
                for _ in range(15):
                    found_reusable_tuner = False
                    should_wait_next_retry = False

                    for live_stream in LiveStream.getAllLiveStreams():
                        # 自分自身は対象外
                        if live_stream is self:
                            continue

                        # ステータスを取得
                        async with live_stream._tuner_lock:
                            live_stream_status = live_stream.getStatus()

                        # クライアントが接続されている場合は対象外
                        # ただし Standby 状態のストリームはまだクライアントに有意なデータを配信していないため、
                        # client_count に関係なくチューナー再利用の対象にする (disconnectAll() で安全に切断できる)
                        if live_stream_status.client_count != 0 and live_stream_status.status != 'Standby':
                            # 近いタイミングで Idling に遷移する可能性があるため、リトライ対象とする
                            if (live_stream_status.status == 'ONAir' or
                                live_stream_status.status == 'Idling'):
                                should_wait_next_retry = True
                            continue

                        # Standby / ONAir / Idling 状態でない場合は対象外
                        if live_stream_status.status not in ('Standby', 'ONAir', 'Idling'):
                            continue

                        # チューナーが割り当てられていない場合は対象外
                        if live_stream.tuner is None:
                            continue

                        # チューナーが既にキャンセル中の場合は対象外
                        if live_stream.tuner.getState() == 'Cancelling':
                            continue

                        # チューナー再利用のため、チューナー状態をキャンセル中に切り替える
                        live_stream.tuner.setState('Cancelling')

                        # ステータスを Offline に設定
                        live_stream.setStatus('Offline', '新しいライブストリームが開始されたため、チューナーリソースを再利用します。')

                        # すべての視聴中クライアントのライブストリームへの接続を切断する
                        live_stream.disconnectAll()

                        # PSI/SI データアーカイバーを終了・破棄する
                        if live_stream.psi_data_archiver is not None:
                            live_stream.psi_data_archiver.destroy()
                            live_stream.psi_data_archiver = None

                        # チューナーとのストリーミング接続を明示的に閉じる
                        await live_stream.tuner.disconnect(live_stream.live_stream_id)

                        # チューナーの制御権限を移譲する
                        if live_stream.tuner.handoff(live_stream.live_stream_id, self.live_stream_id) is False:
                            continue

                        # 実行中のタスクがあればキャンセルする
                        if live_stream._live_encoding_task_ref is not None:
                            live_stream._live_encoding_task_ref.cancel()

                            # タスクの完了を最大 10 秒待つ
                            ## エンコーダープロセスの kill とバックグラウンドタスクの完了を含め、通常は 0.5 秒程度で完了する
                            ## EDCB との通信ハングなどで無期限にブロックされることを防ぐためにタイムアウトを設ける
                            ## asyncio.wait() はタスクの状態を変更しないため、タイムアウトしても旧タスクは自然終了を続ける
                            done, _ = await asyncio.wait(
                                {live_stream._live_encoding_task_ref},
                                timeout=10.0,
                            )
                            if not done:
                                logging.warning(f'[Live: {live_stream.live_stream_id}] Encoding task cleanup did not complete within 10 seconds.')

                            live_stream._live_encoding_task_ref = None

                        # チューナーインスタンスを移譲する
                        self.tuner = live_stream.tuner
                        live_stream.tuner = None
                        found_reusable_tuner = True
                        break

                    if found_reusable_tuner is True:
                        break
                    if should_wait_next_retry is False:
                        break

                    await asyncio.sleep(0.1)

            # Mirakurun バックエンドの場合は、現在 Idling 状態のライブストリームを Offline にしてチューナーリソースを解放する
            ## Mirakurun バックエンドではチューナーインスタンスの直接移譲はできないため、
            ## Idling ストリームを Offline にして Controller の自然終了 → Reader 内での HTTP セッション切断を通じて
            ## Mirakurun/mirakc 側でチューナーが解放されるのを待つ形になる
            elif should_start_task is True and is_edcb_backend is False:

                # 画質切り替えなどタイミングの問題で Idling なストリームがない事もあるので、リトライする
                ## ONAir (client_count == 0) のストリームが存在する場合、近いタイミングで Idling に遷移する可能性があるため
                for _ in range(15):

                    # 現在 Idling 状態のライブストリームがあれば
                    idling_live_streams = self.getIdlingLiveStreams()
                    if len(idling_live_streams) > 0:
                        # チューナーリソースを解放する
                        idling_live_streams[0].setStatus('Offline', '新しいライブストリームが開始されたため、チューナーリソースを解放しました。')
                        break

                    # 現在 ONAir 状態のライブストリームがなく、リトライしたところで Idling なライブストリームが取得できる見込みがない
                    if len(self.getONAirLiveStreams()) == 0:
                        break

                    await asyncio.sleep(0.1)

            # エンコードタスクを非同期で実行
            if should_start_task is True:
                instance = LiveEncodingTask(self)
                self._live_encoding_task_ref = asyncio.create_task(instance.run())

        # ***** クライアントの登録 *****

        # ライブストリームクライアントのインスタンスを生成・登録する
        async with self._tuner_lock:
            client = LiveStreamClient(self, client_type)
            self._clients.append(client)
            logging.info(f'[Live: {self.live_stream_id}] Client Connected. Client ID: {client.client_id}')

        # ***** アイドリングからの復帰 *****

        # ライブストリームが Idling 状態な場合、ONAir 状態に戻す（アイドリングから復帰）
        if current_status == 'Idling':
            self.setStatus('ONAir', 'ライブストリームは ONAir です。')

        # ライブストリームクライアントのインスタンスを返す
        return client


    def disconnect(self, client: LiveStreamClient) -> None:
        """
        指定されたクライアントのライブストリームへの接続を切断する
        このメソッドを実行すると LiveStreamClient インスタンスはライブストリームのクライアントリストから削除され、それ以降機能しなくなる
        LiveStreamClient を使い終わったら必ず呼び出すこと (さもなければ誰も見てないのに視聴中扱いでエンコードタスクが実行され続けてしまう)

        Args:
            client (LiveStreamClient): ライブストリームクライアントのインスタンス
        """

        # 指定されたライブストリームクライアントを削除する
        ## すでにタイムアウトなどで削除されていたら何もしない
        try:
            self._clients.remove(client)
            logging.info(f'[Live: {self.live_stream_id}] Client Disconnected. Client ID: {client.client_id}')
        except ValueError:
            pass
        del client


    def disconnectAll(self) -> None:
        """
        すべてのクライアントのライブストリームへの接続を切断する
        disconnect() とは違い、LiveStreamClient の操作元ではなくエンコードタスク側から操作することを想定している
        """

        # すべてのクライアントの接続を切断する
        for client in self._clients:
            # mpegts クライアントのみ、Queue に None を追加して接続切断を通知する
            if client.client_type == 'mpegts':
                client.writeStreamData(None)
            self.disconnect(client)
            del client

        # 念のためクライアントが入るリストを空にする
        self._clients = []


    def getStatus(self) -> LiveStreamStatus:
        """
        ライブストリームのステータスを取得する

        Returns:
            LiveStreamStatus: ライブストリームのステータス
        """

        return LiveStreamStatus(
            status = self._status,  # ライブストリームの現在のステータス
            detail = self._detail,  # ライブストリームの現在のステータスの詳細情報
            started_at = self._started_at,  # ライブストリームが開始された (ステータスが Offline or Restart → Standby に移行した) 時刻
            updated_at = self._updated_at,  # ライブストリームのステータスが最後に更新された時刻
            client_count = len(self._clients),  # ライブストリームに接続中のクライアント数
        )


    def setStatus(self, status: Literal['Offline', 'Standby', 'ONAir', 'Idling', 'Restart'], detail: str, quiet: bool = False) -> bool:
        """
        ライブストリームのステータスを設定する

        Args:
            status (Literal['Offline', 'Standby', 'ONAir', 'Idling', 'Restart']): ライブストリームのステータス
            detail (str): ステータスの詳細
            quiet (bool): ステータス設定のログを出力するかどうか

        Returns:
            bool: ステータスが更新されたかどうか (更新が実際には行われなかった場合は False を返す)
        """

        # ステータスも詳細も現在の状態と重複しているなら、更新を行わない（同じ内容のイベントが複数発生するのを防ぐ）
        if self._status == status and self._detail == detail:
            return False

        # ステータスが Offline or Restart かつ現在の状態と重複している場合は、更新を行わない
        ## Offline や Restart は Standby に移行しない限り同じステータスで詳細が変化することはありえないので、
        ## ステータス詳細が上書きできてしまう状態は不適切
        ## ただ LiveEncodingTask で非同期的にステータスをセットしている関係で上書きしてしまう可能性があるため、ここで上書きを防ぐ
        if (status == 'Offline' or status == 'Restart') and status == self._status:
            return False

        # ステータスは Offline から Restart に移行してはならない
        if self._status == 'Offline' and status == 'Restart':
            return False

        # ストリーム開始 (Offline or Restart → Standby) 時、started_at と stream_data_written_at を更新する
        # ここで更新しておかないと、いつまで経っても初期化時の古いタイムスタンプが使われてしまう
        if ((self._status == 'Offline' or self._status == 'Restart') and status == 'Standby'):
            self._started_at = time.time()
            self._stream_data_written_at = time.time()

        # ステータス変更のログを出力
        if quiet is False:
            logging.info(f'[Live: {self.live_stream_id}] [Status: {status}] {detail}')

        # ストリーム起動完了時 (Standby → ONAir) 時のみ、ストリームの起動にかかった時間も出力
        if self._status == 'Standby' and status == 'ONAir':
            logging.info(f'[Live: {self.live_stream_id}] Startup complete. ({round(time.time() - self._started_at, 2)} sec)')

        # ログ出力を待ってからステータスと詳細をライブストリームにセット
        self._status = status
        self._detail = detail

        # 最終更新のタイムスタンプを更新
        self._updated_at = time.time()

        # チューナーインスタンスが存在する場合 (= EDCB バックエンド利用時) のみ
        if self.tuner is not None:

            # Idling への切り替え時、チューナーをアンロックして再利用できるように
            if self._status == 'Idling':
                self.tuner.unlock(self.live_stream_id)

            # ONAir への切り替え（復帰）時、再びチューナーをロックして制御を横取りされないように
            if self._status == 'ONAir':
                self.tuner.lock(self.live_stream_id)

        return True


    def getStreamDataWrittenAt(self) -> float:
        """
        ストリームデータの最終書き込み時刻を取得する

        Returns:
            float: ストリームデータの最終書き込み時刻
        """

        return self._stream_data_written_at


    async def writeStreamData(self, stream_data: bytes) -> None:
        """
        接続している全ての mpegts クライアントの Queue にストリームデータを書き込む
        同時にストリームデータの最終書き込み時刻を更新し、クライアントがタイムアウトしていたら削除する

        Args:
            stream_data (bytes): 書き込むストリームデータ
        """

        # ストリームデータの書き込み時刻
        now = time.time()

        # 接続している全てのクライアントの Queue にストリームデータを書き込む
        for client in self._clients:

            # タイムアウト秒数は 10 秒
            timeout = 10

            # 最終読み取り時刻を指定秒数過ぎたクライアントはタイムアウトと判断し、クライアントを削除する
            ## 主にネットワークが切断されたなどの理由で発生する
            if now - client.stream_data_read_at > timeout:
                self._clients.remove(client)
                logging.info(f'[Live: {self.live_stream_id}] Client Disconnected (Timeout). Client ID: {client.client_id}')
                del client
                continue

            # ストリームデータを書き込む (クライアント種別が mpegts の場合のみ)
            if client.client_type == 'mpegts':
                client.writeStreamData(stream_data)

        # ストリームデータが空でなければ、最終書き込み時刻を更新
        if stream_data != b'':
            self._stream_data_written_at = now
