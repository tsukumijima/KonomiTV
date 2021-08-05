
import queue
import time

from app.utils import Logging


# ライブストリーム ID ごとに一つのインスタンスになるようにする
# ref: https://qiita.com/ttsubo/items/c4af71ceba15b5b213f8
class LiveStreamSingleton(object):
    _instances = dict()
    def __new__(cls, *args, **kwargs):
        livestream_id = f'{args[0]}-{args[1]}'
        # まだインスタンス化されておらず、かつ同じライブストリーム ID が存在しないときだけインスタンスを生成
        if livestream_id not in cls._instances:
            cls._instances[livestream_id] = super(LiveStreamSingleton, cls).__new__(cls)
        # 登録されたインスタンスを返す
        return cls._instances[livestream_id]


class LiveStream(LiveStreamSingleton):

    # ストリームデータを格納するクラス変数
    # ネスト構造:
    #   livestream = {
    #       # ライブストリームID
    #       'gr011-1080p': [
    #           # クライアントは [(ストリームデータが入る Queue), (最終読み取り時刻)] のリストになっている
    #           # ここに登録されているクライアントの Queue 全てにストリームデータを書き込む必要がある
    #           # 最終読み取り時刻から 5 秒以上経過したクライアントは削除され、None が設定される
    #           [queue.Queue(), time.time()],
    #           [queue.Queue(), time.time()],
    #           [queue.Queue(), time.time()],
    #       ]
    #   }
    livestream = dict()


    def __init__(self, channel_id:str, quality:int):
        """ライブストリームを作成する

        Args:
            channel_id (str): チャンネルID
            quality (int): 映像の品質 (1080p ~ 360p)
        """

        # ライブストリーム ID  ex:gr011-1080p
        # (チャンネルID)-(映像の品質) で一意な ID になる
        self.livestream_id = f'{channel_id}-{quality}'

        # ライブストリームの作成（まだ存在しない場合のみ）
        # 接続しているクライアントの Queue が入るリストを定義する
        if self.livestream_id not in LiveStream.livestream:
            LiveStream.livestream[self.livestream_id] = list()


    def connect(self) -> int:
        """ライブストリームに接続（新しいクライアントを登録）し、クライアント ID を返す

        Returns:
            int: クライアントID
        """

        # ストリームデータが入る Queue と、最終読み取り時刻のリストを登録する
        # 最終読み取り時刻から 5 秒以上経っていたら、ここで登録したクライアントを削除する
        # 接続時は最終読み取り時刻を登録しない（エンコーダーの起動で待たされるため）
        LiveStream.livestream[self.livestream_id].append(queue.Queue())

        # 自分の Queue があるインデックス（リストの長さ - 1）をクライアント ID とする
        client_id = len(LiveStream.livestream[self.livestream_id]) - 1
        Logging.info(f'***** LiveStream Connected. Client ID: {client_id} *****')

        # 新たに振られたクライアント ID を返す
        return client_id


    def disconnect(self, client_id:int) -> None:
        """指定されたクライアント ID のライブストリームへの接続を切断する

        Args:
            client_id (int): クライアントID
        """

        # 指定されたクライアント ID の Queue を削除する
        LiveStream.livestream[self.livestream_id][client_id] = None
        Logging.info(f'***** LiveStream Disconnected. Client ID: {client_id} *****')


    def read(self, client_id:int) -> bytes:
        """指定されたクライアント ID の Queue からストリームデータを読み取る

        Args:
            client_id (int): LiveStream.connect() で受け取ったクライアントID

        Returns:
            bytes: ストリームデータ
        """

        # 登録したクライアントの Queue から読み取ったストリームデータを返す
        return LiveStream.livestream[self.livestream_id][client_id].get()


    def write(self, stream_data:bytes) -> None:
        """接続している全てのクライアントの Queue にストリームデータを書き込む

        Args:
            stream_data (bytes): 書き込むストリームデータ
        """

        # 接続している全てのクライアントの Queue にストリームデータを書き込む
        for index, client in enumerate(LiveStream.livestream[self.livestream_id]):

            # 削除されたクライアントでなければ書き込む
            if client is not None:
                client.put(stream_data)


    def destroy(self) -> None:
        """ライブストリームを終了し、破棄する"""

        # ライブストリームを終了する前に、接続している全てのクライアントの Queue にライブストリームの終了を知らせる None を書き込む
        # クライアントは None を受信した場合、ストリーミングを終了するようになっている
        # これがないとクライアントはライブストリームが終了した事に気づかず、Queue を取り出そうとしてずっとブロッキングされてしまう
        for client in LiveStream.livestream[self.livestream_id]:
            if client is not None:
                client.put(None)

        # ライブストリームを削除する
        LiveStream.livestream.pop(self.livestream_id)

        # ライブストリーム ID を None にする
        # ライブストリーム ID が None のとき、クライアントはストリームデータが終了されたと判断する
        self.livestream_id = None
