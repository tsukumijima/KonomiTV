
import inspect
import logging
import os
import ruamel.yaml
import sys
from pathlib import Path


# ベースディレクトリ
BASE_DIR = Path(__file__).resolve().parent.parent

# Aerich（マイグレーションツール）からのインポート時に設定ファイルのロードをスキップ
if len(inspect.stack()) > 8 and inspect.stack()[8].function == 'get_tortoise_config':

    # ダミーの CONFIG を用意（インポートエラーの回避のため）
    CONFIG = {'general': {'debug': True}}  # Logging モジュールの初期化に必要

else:

    # 設定ファイルのパス
    CONFIG_YAML = BASE_DIR.parent / 'config.yaml'
    if os.path.exists(CONFIG_YAML) is False:
        logger = logging.getLogger('uvicorn')
        logger.error(
            '設定ファイルが配置されていないため、KonomiTV を起動できません。\n          '
            'config.example.yaml を config.yaml にコピーし、お使いの環境に合わせて編集してください。'
        )
        sys.exit(1)

    # 環境設定を読み込む
    with open(CONFIG_YAML, encoding='utf-8') as stream:
        CONFIG = ruamel.yaml.YAML().load(stream)

# 映像と音声の品質
QUALITY = {
    '1080p': {
        'width': None,  # 縦解像度：1080p のみソースの解像度を使うため指定しない
        'height': None,  # 横解像度：1080p のみソースの解像度を使うため指定しない
        'video_bitrate': '6500K',  # 映像ビットレート
        'video_bitrate_max': '9000K',  # 映像最大ビットレート
        'audio_bitrate': '192K',  # 音声ビットレート
    },
    '810p': {
        'width': 1440,
        'height': 810,
        'video_bitrate': '5500K',
        'video_bitrate_max': '7600K',
        'audio_bitrate': '192K',
    },
    '720p': {
        'width': 1280,
        'height': 720,
        'video_bitrate': '4500K',
        'video_bitrate_max': '6200K',
        'audio_bitrate': '192K',
    },
    '540p': {
        'width': 940,
        'height': 540,
        'video_bitrate': '3000K',
        'video_bitrate_max': '4100K',
        'audio_bitrate': '192K',
    },
    '480p': {
        'width': 720,
        'height': 480,
        'video_bitrate': '2000K',
        'video_bitrate_max': '2800K',
        'audio_bitrate': '192K',
    },
    '360p': {
        'width': 640,
        'height': 360,
        'video_bitrate': '1100K',
        'video_bitrate_max': '1800K',
        'audio_bitrate': '128K',
    },
    '240p': {
        'width': 426,
        'height': 240,
        'video_bitrate': '550K',
        'video_bitrate_max': '650K',
        'audio_bitrate': '128K',
    },
}

# クライアントの静的ファイルのあるディレクトリ
CLIENT_DIR = BASE_DIR.parent / 'client/dist'

# ロゴファイルのあるディレクトリ
LOGO_DIR = BASE_DIR / 'data/logo'

# サードパーティーライブラリのあるディレクトリ
LIBRARY_DIR = BASE_DIR / 'thirdparty'

# サードパーティーライブラリのあるパス
LIBRARY_EXTENSION = ('.exe' if os.name == 'nt' else '.elf')
LIBRARY_PATH = {
    'FFmpeg': str(LIBRARY_DIR / 'FFmpeg/ffmpeg') + LIBRARY_EXTENSION,
    'FFprobe': str(LIBRARY_DIR / 'FFmpeg/ffprobe') + LIBRARY_EXTENSION,
    'QSVEncC': str(LIBRARY_DIR / 'QSVEncC/QSVEncC') + LIBRARY_EXTENSION,
    'NVEncC': str(LIBRARY_DIR / 'NVEncC/NVEncC') + LIBRARY_EXTENSION,
    'tsreadex': str(LIBRARY_DIR / 'tsreadex/tsreadex') + LIBRARY_EXTENSION,
    'VCEEncC': str(LIBRARY_DIR / 'VCEEncC/VCEEncC') + LIBRARY_EXTENSION,
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
VERSION = '0.4.0'
