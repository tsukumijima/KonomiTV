
import queue
import threading
import time

from app.constants import CONFIG
from app.utils import Logging


# ライブストリーム ID ごとに一つのインスタンスになるようにする
# ref: https://qiita.com/ttsubo/items/c4af71ceba15b5b213f8
class LiveStreamSingleton(object):
    _instances = dict()
    def __new__(cls, *args, **kwargs):
        # まだ同じライブストリーム ID のインスタンスがないときだけインスタンスを生成
        livestream_id = f'{args[0]}-{args[1]}'
        if livestream_id not in cls._instances:
            cls._instances[livestream_id] = super(LiveStreamSingleton, cls).__new__(cls)
        # 登録されたインスタンスを返す
        return cls._instances[livestream_id]


class LiveStream(LiveStreamSingleton):

    """ライブストリームを管理するクラス"""

    # ライブストリームの状態とストリームデータを格納する辞書
    # 起動時に全てのチャンネル&品質のライブストリームが初期定義される
    # interface (?) にしたほうがいい気もするけどとりあえず
    # ネスト構造:
    """
    livestream = {
        # ライブストリームID
        'gr011-1080p': {
            # ステータス ( Offline, Standby, ONAir, Idling のいずれか)
            'status': 'ONAir',
            # ステータスの詳細
            'detail': 'ライブストリームは ONAir です。',
            # 最終更新
            'updated_at': time.time(),
            # ライブストリームクライアント
            'client': [
                # type が mpegts の場合のみ、クライアントが持つ Queue にストリームデータを入れる
                # type が hls の場合は配信方式が異なるため Queue は使われない
                # クライアントの接続が切断された場合、このリストからも削除される（正確にはインデックスを壊さないため None が入る）
                # したがって、クライアントの数は（ None になってるのを除いた）このリストの長さで求められる
                {'type': 'mpegts', 'queue': queue.Queue()},
                {'type': 'mpegts', 'queue': queue.Queue()},
                {'type': 'mpegts', 'queue': queue.Queue()},
                {'type': 'hls', 'queue': None},
            ]
        }
    }
    """
    livestreams = dict()


    def __init__(self, channel_id:str, quality:int):
        """ライブストリームのインスタンスを取得する

        Args:
            channel_id (str): チャンネルID
            quality (int): 映像の品質 (1080p ~ 360p)
        """

        # チャンネルID
        self.channel_id = channel_id

        # 映像の品質
        self.quality = quality

        # ライブストリーム ID  ex:gr011-1080p
        # (チャンネルID)-(映像の品質) で一意な ID になる
        self.livestream_id = f'{self.channel_id}-{self.quality}'

        # ライブストリーム ID に紐づくライブストリーム
        self.livestream = LiveStream.livestreams[self.livestream_id]


    def connect(self, type:str) -> int:
        """ライブストリームに接続（新しいクライアントを登録）し、クライアント ID を返す

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
            # MLT 系チューナーでなければ GR → BS,CS への切り替えでも解放されるのは非効率な気もするけど、一旦考えない事にする
            idling_livestream = self.getIdlingLiveStream()
            if len(idling_livestream) > 0:
                idling_livestream[0].setStatus('Offline', '新しいライブストリームが開始されたため、チューナーリソースを解放しました。')

            # ステータスを Standby に設定
            # タイミングの関係でこっちで明示的に設定しておく必要がある
            self.setStatus('Standby', 'エンコーダーを起動しています…')

            # エンコードタスクを非同期で実行
            def run():
                # 相互に依存し合っている場合、__init__.py でモジュール内の各クラスのインポートを定義している以上うまくいかないため、
                # どちらかをモジュールの初回参照時にインポートされないようにする必要がある
                from app.tasks import LiveEncodingTask
                instance = LiveEncodingTask()
                instance.run(self.channel_id, self.quality, CONFIG['livestream']['preferred_encoder'])
            thread = threading.Thread(target=run)
            thread.start()

        # ライブストリームが Idling 状態な場合、ONAir 状態に戻す（アイドリングから復帰）
        if self.getStatus()['status'] == 'Idling':
            self.setStatus('ONAir', 'ライブストリームは ONAir です。')

        # ***** クライアントの登録 *****

        # クライアントの種別と、クライアントの種別が mpegts の場合に必要な Queue を登録する
        self.livestream['client'].append({
            'type': type,
            'queue': queue.Queue() if type == 'mpegts' else None,
        })

        # 自分の Queue があるインデックス（リストの長さ - 1）をクライアント ID とする
        client_id = len(self.livestream['client']) - 1
        # Client ID は表示上 1 起点とする（その方が直感的なため）
        Logging.info(f'LiveStream:{self.livestream_id} Client Connected. Client ID: {client_id + 1}')

        # 新たに振られたクライアント ID を返す
        return client_id


    def disconnect(self, client_id:int) -> None:
        """指定されたクライアント ID のライブストリームへの接続を切断する

        Args:
            client_id (int): クライアントID
        """

        # 指定されたクライアント ID のクライアントを削除する
        if len(self.livestream['client']) > 0:
            self.livestream['client'][client_id] = None
            # Client ID は表示上 1 起点とする（その方が直感的なため）
            Logging.info(f'LiveStream:{self.livestream_id} Client Disconnected. Client ID: {client_id + 1}')


    def getIdlingLiveStream(self) -> list:
        """現在 Idling なライブストリームを取得する

        Returns:
            list: 現在 Idling なライブストリームのインスタンスの入ったリスト
        """

        result = []

        # 現在 Idling 状態のライブストリームを探す
        # 見つかったら、そのライブストリームのインスタンスをリストに入れる
        for livestream_id, livestream in LiveStream.livestreams.items():
            if livestream['status'] == 'Idling':
                channel_id, quality = livestream_id.split('-')
                result.append(LiveStream(channel_id, quality))

        return result


    def getStatus(self) -> dict:
        """ライブストリームのステータスを取得する

        Returns:
            dict: ライブストリームのステータスが入った辞書
        """

        # ステータス・詳細・最終更新・クライアント数を返す
        return {
            'status': self.livestream['status'],
            'detail': self.livestream['detail'],
            'updated_at': self.livestream['updated_at'],
            'client_count': len(list(filter(None, self.livestream['client']))),
        }


    def setStatus(self, status:str, detail:str) -> None:
        """ライブストリームのステータスを設定する

        Args:
            status (str): ステータス ( Offline, Standby, ONAir, Idling のいずれか)
            detail (str): ステータスの詳細
        """

        # ステータスも詳細も現在と同じなら、更新を行わない
        if self.livestream['status'] == status and self.livestream['detail'] == detail:
            return

        # ステータスと詳細を設定
        Logging.info(f'LiveStream:{self.livestream_id} Status:{status.ljust(7, " ")} Detail:{detail}')
        self.livestream['status'] = status
        self.livestream['detail'] = detail

        # 最終更新のタイムスタンプを更新
        self.livestream['updated_at'] = time.time()


    def read(self, client_id:int) -> bytes:
        """指定されたクライアント ID の Queue からストリームデータを読み取る

        Args:
            client_id (int): LiveStream.connect() で受け取ったクライアントID

        Returns:
            bytes: ストリームデータ
        """

        # 登録したクライアントの Queue から読み取ったストリームデータを返す
        if len(self.livestream['client']) > 0 and self.livestream['client'][client_id] is not None:
            try:
                return self.livestream['client'][client_id]['queue'].get()
            except TypeError:
                return None
        else:
            return None


    def write(self, stream_data:bytes) -> None:
        """接続している全てのクライアントの Queue にストリームデータを書き込む

        Args:
            stream_data (bytes): 書き込むストリームデータ
        """

        # 接続している全てのクライアントの Queue にストリームデータを書き込む
        for client in self.livestream['client']:

            # 削除されたクライアントでなく、かつクライアントの種別が mpegts であれば書き込む
            if client is not None and client['type'] == 'mpegts':
                client['queue'].put(stream_data)
