
import queue


# ref: https://qiita.com/ttsubo/items/c4af71ceba15b5b213f8
class LiveStreamSingleton(object):
    def __new__(cls, *args, **kargs):
        # まだインスタンス化されておらず、かつ同じライブストリーム ID が存在しない
        if not hasattr(cls, '_instance') and f'{args[0]}-{args[1]}' not in LiveStream.livestream:
            cls._instance = super(LiveStreamSingleton, cls).__new__(cls)
        return cls._instance


class LiveStream(LiveStreamSingleton):

    # ストリームデータを格納するクラス変数
    # ネスト構造:
    #   livestream = {
    #       # ライブストリームID
    #       'gr011-1080p': [
    #           # 接続しているクライアントごとに
    #           # エンコードタスクはここに登録されている Queue 全てにストリームデータを書き込む必要がある
    #           queue.Queue(),
    #           queue.Queue(),
    #           queue.Queue(),
    #       ]
    #   }
    livestream = {}

    # 映像・音声の品質定義
    quality = {
        '1080p': {
            'width': None,  # 縦解像度：1080p のみソースの解像度を使うため指定しない
            'height': None,  # 横解像度：1080p のみソースの解像度を使うため指定しない
            'video_bitrate': '6500K',  # 映像ビットレート
            'video_bitrate_max': '9000K',  # 映像最大ビットレート
            'audio_bitrate': '192K',  # 音声ビットレート
        },
        '720p': {
            'width': 1280,
            'height': 720,
            'video_bitrate': '4500K',
            'video_bitrate_max': '6200K',
            'audio_bitrate': '192K',  # 音声ビットレート
        },
        '540p': {
            'width': 940,
            'height': 540,
            'video_bitrate': '3000K',
            'video_bitrate_max': '4100K',
            'audio_bitrate': '192K',  # 音声ビットレート
        },
        '360p': {
            'width': 640,
            'height': 360,
            'video_bitrate': '1500K',
            'video_bitrate_max': '2000K',
            'audio_bitrate': '128K',  # 音声ビットレート
        },
    }


    def __init__(self, channel_id:str, quality:int):
        """ライブストリームを作成する

        Args:
            channel_id (str): チャンネルID
            quality (int): 映像の品質 (1080p ~ 360p)
        """

        # ライブストリーム ID  ex:gr011-1080p
        # (チャンネルID)-(映像の品質) で一意な ID になる
        self.livestream_id = f'{channel_id}-{quality}'

        # ライブストリームの作成
        # 接続しているクライアントの Queue が入るリストを定義する
        # なんか別々のインスタンスになってるっぽくてうまくいってない
        #LiveStream.livestream[self.livestream_id] = list()


    def connect(self) -> int:
        """ライブストリームに接続（新しいクライアントを作成）し、クライアント ID を返す

        Returns:
            int: クライアントID
        """

        # ストリームデータが入る Queue を登録する
        LiveStream.livestream[self.livestream_id].append(queue.Queue())

        # 自分の Queue があるインデックス（リストの長さ - 1）を返す
        return len(LiveStream.livestream[self.livestream_id]) - 1


    def read(self, client_id:int) -> bytes:
        """指定されたクライアント ID の Queue からストリームデータを読み取る

        Args:
            client_id (int): LiveStream.connect() で受け取ったクライアントID

        Returns:
            bytes: ストリームデータ
        """

        # 登録した Queue から読み取ったストリームデータを返す
        return LiveStream.livestream[self.livestream_id][client_id].get()


    def write(self, stream_data:bytes) -> None:
        """接続している全てのクライアントの Queue にストリームデータを書き込む

        Args:
            stream_data (bytes): 書き込むストリームデータ
        """

        # ******暫定******
        if self.livestream_id not in LiveStream.livestream:
            LiveStream.livestream[self.livestream_id] = list()

        # 接続している全てのクライアントの Queue にストリームデータを書き込む
        for client in LiveStream.livestream[self.livestream_id]:
            client.put(stream_data)


    def destroy(self) -> None:
        """ライブストリームを終了し、破棄する"""

        # ライブストリームを終了する前に、接続している全てのクライアントの Queue にライブストリームの終了を知らせる None を書き込む
        # クライアントは None を受信した場合、ストリーミングを終了するようになっている
        # これがないとクライアントはライブストリームが終了した事に気づかず、Queue を取り出そうとしてずっとブロッキングされてしまう
        for client in LiveStream.livestream[self.livestream_id]:
            client.put(None)

        # ライブストリームを削除する
        LiveStream.livestream.pop(self.livestream_id)

        # ライブストリーム ID を None にする
        # ライブストリーム ID が None のとき、クライアントはストリームデータが終了されたと判断する
        self.livestream_id = None
