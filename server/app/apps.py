
from django.apps import AppConfig

class AppConfig(AppConfig):

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    # ストリームデータを格納する、リクエスト・エンコードタスク間で共有される変数
    """ livestream のネスト構造:
        livestream = {
            # エンコードタスクごとに
            'Live_NID32736-SID1024_1080p': [
                # 接続しているクライアントごとに
                # エンコードタスクはここに登録されている Queue 全てにストリームデータを書き込む必要がある
                queue.Queue(),
                queue.Queue(),
                queue.Queue(),
            ]
        }
    """
    livestream = {}
