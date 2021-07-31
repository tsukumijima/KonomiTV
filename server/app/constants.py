
import os
from pathlib import Path


# 環境設定
# 将来的には YAML からのロードになる予定
CONFIG = {
    'preferred_encoder': 'ffmpeg',
    'preferred_quality': '1080p',
    'mirakurun_url': 'http://192.168.1.28:40772',
}

# ベースディレクトリ
BASE_DIR = Path(__file__).resolve().parent.parent

# クライアントの静的ファイルのあるディレクトリ
CLIENT_DIR = BASE_DIR.parent / 'client/dist'

# サードパーティーライブラリのあるディレクトリ
LIBRARY_DIR = BASE_DIR / 'thirdparty'

# サードパーティーライブラリのあるパス
LIBRARY_EXTENSION = '.exe' if os.name == 'nt' else ''
LIBRARY_PATH = {
    'arib-subtitle-timedmetadater': str(LIBRARY_DIR / 'arib-subtitle-timedmetadater/arib-subtitle-timedmetadater') + LIBRARY_EXTENSION,
    'ffmpeg': str(LIBRARY_DIR / 'FFmpeg/ffmpeg') + LIBRARY_EXTENSION,
    'ffprobe': str(LIBRARY_DIR / 'FFmpeg/ffprobe') + LIBRARY_EXTENSION,
}

# データベース (Tortoise ORM) の設定
DATABASE_CONFIG = {
    'connections': {
        'default': f'sqlite://{str(BASE_DIR / "data/database.sqlite")}',
    },
    'apps': {
        'models': {
            'models': ['app.models', 'aerich.models'],
            'default_connection': 'default',
        }
    }
}

# バージョン
VERSION = '0.1.0'
