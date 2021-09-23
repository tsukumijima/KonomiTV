
import queue
import threading
import time
from typing import Dict, List, Optional

from app.constants import CONFIG
from app.utils import Logging
from app.utils.EDCB import EDCBTuner


class LiveStreamClient():
    """ライブストリームクライアントの構造定義"""

    # type が mpegts の場合のみ、クライアントが持つ Queue にストリームデータを入れる
    # type が hls の場合は配信方式が異なるため Queue は使われない
    type:str  # クライアントの種別 (mpegts or hls)
    queue:Optional[queue.Queue]  # ストリームデータが入る Queue または None

    def __init__(self, type:str, queue:Optional[queue.Queue]):
        self.type = type
        self.queue = queue


class LiveStream():
    """ ライブストリームを管理するクラス """

    # ライブストリームのインスタンスが入る、ライブストリーム ID をキーとした辞書
    # この辞書にライブストリームに関する全てのデータが格納されており、ライブストリーム機能の根幹をなす
    __instances:Dict = dict()

    # ライブストリーム ID  ex:gr011-1080p
    livestream_id:str

    # ステータス
    status:str = 'Offline'

    # ステータス詳細
    detail:str = 'ライブストリームは Offline です。'

    # ステータスの最終更新時刻のタイムスタンプ
    updated_at:float = time.time()

    # ストリームデータの最終書き込み時刻のタイムスタンプ
    # ONAir 状態にも関わらず最終書き込み時刻が 3 秒以上更新されていない場合は、
    # エンコーダーがフリーズしたものとみなしてエンコードタスクを再起動する
    stream_data_writed_at:float = 0

    # ライブストリームクライアント
    # クライアントの接続が切断された場合、このリストからも削除される（正確にはインデックスを壊さないため None が入る）
    # したがって、クライアントの数は（ None になってるのを除いた）このリストの長さで求められる
    clients:List[Optional[LiveStreamClient]]

    # 必ずライブストリーム ID ごとに1つのインスタンスになるように (Singleton)
    # ref: https://qiita.com/ttsubo/items/c4af71ceba15b5b213f8
    def __new__(cls, channel_id:str, quality:int):

        # 型アノテーションを追加（IDE用）
        ## クラス直下で自クラスを型として指定することはできないため、ここで明示的に指定する
        cls.__instances:Dict[str, LiveStream]

        # まだ同じライブストリーム ID のインスタンスがないときだけ、インスタンスを生成する
        livestream_id = f'{channel_id}-{quality}'
        if livestream_id not in cls.__instances:

            # 新しいライブストリームのインスタンスを生成する
            instance = super(LiveStream, cls).__new__(cls)

            # ライブストリームクライアントを初期化する
            # クラス直下で定義すると全てのインスタンスのライブストリームクライアントが同じ参照（同じオブジェクトID）になってしまうため、
            # 同じ参照にならないようにインスタンス生成時に実行するようにする
            instance.clients = list()

            # 生成したインスタンスを登録する
            # インスタンスの参照が渡されるので、オブジェクトとしては同一
            cls.__instances[livestream_id] = instance

        # 登録されたインスタンスを返す
        return cls.__instances[livestream_id]


    def __init__(self, channel_id:str, quality:int):
        """
        ライブストリームのインスタンスを取得する

        Args:
            channel_id (str): チャンネルID
            quality (int): 映像の品質 (1080p ~ 240p)
        """

        # チャンネル ID 、映像の品質を設定
        self.channel_id:str = channel_id
        self.quality:str = quality

        # ライブストリーム ID を設定
        # (チャンネルID)-(映像の品質) で一意な ID になる
        self.livestream_id:str = f'{self.channel_id}-{self.quality}'

        # EDCB バックエンドのチューナーインスタンス
        # Mirakurun バックエンドを使っている場合は None のまま
        self.tuner:Optional[EDCBTuner] = None


    @classmethod
    def getAllLiveStreams(cls) -> list:
        """
        全てのライブストリームのインスタンスを取得する

        Returns:
            list: ライブストリームのインスタンスの入ったリスト
        """

        # __instances 辞書を values() で値だけのリストにしたものを返す
        return list(cls.__instances.values())


    @classmethod
    def getIdlingLiveStreams(cls) -> list:
        """
        現在 Idling なライブストリームのインスタンスを取得する

        Returns:
            list: 現在 Idling なライブストリームのインスタンスの入ったリスト
        """

        result = []

        # 現在 Idling 状態のライブストリームを探す
        # 見つかったら、そのライブストリームのインスタンスをリストに入れる
        for livestream in LiveStream.getAllLiveStreams():
            if livestream.status == 'Idling':
                result.append(livestream)

        return result


    @classmethod
    def getViewers(cls, channel_id:str) -> int:
        """
        指定されたチャンネルのライブストリームの現在の視聴者数を取得する

        Args:
            channel_id (str): チャンネルID

        Returns:
            int: 視聴者数
        """

        # 指定されたチャンネル ID が含まれるライブストリームを探す
        viewers = 0
        for livestream in LiveStream.getAllLiveStreams():
            if livestream.channel_id == channel_id:
                # 足していく
                viewers += livestream.getStatus()['clients_count']

        # カウントした視聴者数を返す
        return viewers


    def connect(self, type:str) -> int:
        """
        ライブストリームに接続（新しいクライアントを登録）し、クライアント ID を返す

        Args:
            type (str): クライアントの種別 (mpegts or hls)

        Returns:
            int: クライアントID
        """

        # ***** ステータスの切り替え *****

        # ライブストリームが Offline な場合、新たにエンコードタスクを起動する
        if self.getStatus()['status'] == 'Offline':

            # 現在 Idling 状態のライブストリームがあれば、うち最初のライブストリームを Offline にする
            # 一般にチューナーリソースは無尽蔵にあるわけではないので、現在 Idling（=つまり誰も見ていない）ライブストリームがあるのなら
            # それを Offline にしてチューナーリソースを解放し、新しいライブストリームがチューナーを使えるようにする
            # 通常のチューナー（マルチチューナーでない）で GR → BS,CS への切り替えでも解放されるのは非効率な気もするけど、
            # ただチューナーはともかく複数のエンコードが同時に走る状態ってのもそんなによくない気がするし、一旦仕様として保留
            idling_livestreams = self.getIdlingLiveStreams()
            if len(idling_livestreams) > 0:

                idling_livestream:LiveStream = idling_livestreams[0]

                # EDCB バックエンドの場合はチューナーをアンロックし、これから開始するエンコードタスクで再利用できるようにする
                if idling_livestream.tuner is not None:
                    idling_livestream.tuner.unlock()

                # チューナーリソースを解放する
                idling_livestream.setStatus('Offline', '新しいライブストリームが開始されたため、チューナーリソースを解放しました。')

            # ステータスを Standby に設定
            # タイミングの関係でこっちで明示的に設定しておく必要がある
            if CONFIG['general']['backend'] == 'Mirakurun':
                self.setStatus('Standby', 'エンコーダーを起動しています…')
            elif CONFIG['general']['backend'] == 'EDCB':
                self.setStatus('Standby', 'チューナーを起動しています…')

            # エンコードタスクを非同期で実行
            def run():
                # 相互に依存し合っている場合、__init__.py でモジュール内の各クラスのインポートを定義している以上うまくいかないため、
                # どちらかをモジュールの初回参照時にインポートされないようにする必要がある
                from app.tasks import LiveEncodingTask
                instance = LiveEncodingTask()
                instance.run(self.channel_id, self.quality)
            thread = threading.Thread(target=run, name='LiveEncodingTask')
            thread.start()

        # ***** クライアントの登録 *****

        # クライアントの種別と、クライアントの種別が mpegts の場合に必要な Queue を登録する
        self.clients.append(LiveStreamClient(
            type = type,
            queue = queue.Queue() if type == 'mpegts' else None,
        ))

        # 自分の Queue があるインデックス（リストの長さ - 1）をクライアント ID とする
        client_id = len(self.clients) - 1

        # Client ID は表示上 1 起点とする（その方が直感的なため）
        Logging.info(f'LiveStream:{self.livestream_id} Client Connected. Client ID: {client_id + 1}')

        # ***** アイドリングからの復帰 *****

        # ライブストリームが Idling 状態な場合、ONAir 状態に戻す（アイドリングから復帰）
        if self.getStatus()['status'] == 'Idling':
            self.setStatus('ONAir', 'ライブストリームは ONAir です。')

        # 新たに振られたクライアント ID を返す
        return client_id


    def disconnect(self, client_id:int) -> None:
        """
        指定されたクライアント ID のライブストリームへの接続を切断する

        Args:
            client_id (int): クライアントID
        """

        # 指定されたクライアント ID のクライアントを削除する
        if len(self.clients) > 0:
            self.clients[client_id] = None
            # Client ID は表示上 1 起点とする（その方が直感的なため）
            Logging.info(f'LiveStream:{self.livestream_id} Client Disconnected. Client ID: {client_id + 1}')


    def getStatus(self) -> dict:
        """
        ライブストリームのステータスを取得する

        Returns:
            dict: ライブストリームのステータスが入った辞書
        """

        # ステータス・詳細・最終更新・クライアント数を返す
        return {
            'status': self.status,
            'detail': self.detail,
            'updated_at': self.updated_at,
            'clients_count': len(list(filter(None, self.clients))),
        }


    def setStatus(self, status:str, detail:str, quiet:bool=False) -> None:
        """
        ライブストリームのステータスを設定する

        Args:
            status (str): ステータス ( Offline, Standby, ONAir, Idling, Restart のいずれか)
            detail (str): ステータスの詳細
        """

        # ステータスも詳細も現在の状態と重複しているなら、更新を行わない（同じ内容のイベントが複数発生するのを防ぐ）
        if self.status == status and self.detail == detail:
            return

        # ステータスと詳細を設定
        if quiet is False:
            Logging.info(f'LiveStream:{self.livestream_id} Status:{status.ljust(7, " ")} Detail:{detail}')
        self.status = status
        self.detail = detail

        # 最終更新のタイムスタンプを更新
        self.updated_at = time.time()

        # チューナーインスタンスが存在する場合のみ
        if self.tuner is not None:

            # Idling への切り替え時、チューナーをアンロックして再利用できるように
            if self.status == 'Idling':
                self.tuner.unlock()

            # ONAir への切り替え（復帰）時、再びチューナーをロックして制御を横取りされないように
            if self.status == 'ONAir':
                self.tuner.lock()


    def setTunerInstance(self, tuner:EDCBTuner) -> None:
        """
        EDCB バックエンドのチューナーインスタンスを設定する
        設定されたチューナーインスタンスはステータス変更時のチューナーのアンロック/ロックに利用する

        Args:
            tuner (EDCBTuner): EDCB バックエンドのチューナーインスタンス
        """
        self.tuner = tuner


    def read(self, client_id:int) -> bytes:
        """
        指定されたクライアント ID の Queue からストリームデータを読み取る

        Args:
            client_id (int): connect() で受け取ったクライアントID

        Returns:
            bytes: ストリームデータ
        """

        # 登録したクライアントの Queue から読み取ったストリームデータを返す
        if len(self.clients) > 0 and self.clients[client_id] is not None:
            try:
                return self.clients[client_id].queue.get_nowait()
            except queue.Empty:
                return b''  # None にはせず、処理を継続させる
            except TypeError:
                return None
        else:
            return None


    def write(self, stream_data:bytes) -> None:
        """
        接続している全てのクライアントの Queue にストリームデータを書き込む

        Args:
            stream_data (bytes): 書き込むストリームデータ
        """

        # 接続している全てのクライアントの Queue にストリームデータを書き込む
        for client in self.clients:

            # 削除されたクライアントでなく、かつクライアントの種別が mpegts であれば書き込む
            if client is not None and client.type == 'mpegts':
                client.queue.put(stream_data)

        # ストリームデータが空でなければ、最終書き込み時刻を更新
        if stream_data != b'':
            self.stream_data_writed_at = time.time()
