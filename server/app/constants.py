
import os
from pathlib import Path


# 環境設定
# 将来的には YAML からのロードになる予定
CONFIG = {
    'general': {
        'debug': True,
        'mirakurun_url': 'http://192.168.1.28:40772',
    },
    'livestream': {
        'preferred_encoder': 'ffmpeg',
        'preferred_quality': '1080p',
        'max_alive_time': 10,
    }
}

# ライブストリームの映像/音声品質
LIVESTREAM_QUALITY = {
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
    'timezone': 'Asia/Tokyo',
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
