
import pkgutil
import secrets
import sys
from pathlib import Path
from typing import Any, Literal

import httpx
from passlib.context import CryptContext
from pydantic import BaseModel, PositiveInt


# バージョン
VERSION = '0.13.0-dev'

# ベースディレクトリ
BASE_DIR = Path(__file__).resolve().parent.parent

# クライアントの静的ファイルがあるディレクトリ
CLIENT_DIR = BASE_DIR.parent / 'client/dist'

# データディレクトリ
DATA_DIR = BASE_DIR / 'data'
## アカウントのアイコン画像があるディレクトリ
ACCOUNT_ICON_DIR = DATA_DIR / 'account-icons'
## サムネイル画像があるディレクトリ
THUMBNAILS_DIR = DATA_DIR / 'thumbnails'
## サーバー終了時に再起動が必要なことを伝えるロックファイルのパス
RESTART_REQUIRED_LOCK_PATH = DATA_DIR / 'restart_required.lock'

# スタティックディレクトリ
STATIC_DIR = BASE_DIR / 'static'
## ロゴファイルがあるディレクトリ
LOGO_DIR = STATIC_DIR / 'logos'
## デフォルトのアイコン画像があるディレクトリ
ACCOUNT_ICON_DEFAULT_DIR = STATIC_DIR / 'account-icons'
## jikkyo_channels.json があるパス
JIKKYO_CHANNELS_PATH = STATIC_DIR / 'jikkyo_channels.json'

# ログディレクトリ
LOGS_DIR = BASE_DIR / 'logs'
## KonomiTV のサーバーログのパス
KONOMITV_SERVER_LOG_PATH = LOGS_DIR / 'KonomiTV-Server.log'
## KonomiTV のアクセスログのパス
KONOMITV_ACCESS_LOG_PATH = LOGS_DIR / 'KonomiTV-Access.log'
## Akebi (HTTPS リバースプロキシ) のログファイルのパス
AKEBI_LOG_PATH = LOGS_DIR / 'Akebi-HTTPS-Server.log'

# サードパーティーライブラリのあるディレクトリ
LIBRARY_DIR = BASE_DIR / 'thirdparty'

# サードパーティーライブラリのあるパス
LIBRARY_EXTENSION = ('.exe' if sys.platform == 'win32' else '.elf')
LIBRARY_PATH = {
    'Akebi': str(LIBRARY_DIR / 'Akebi/akebi-https-server') + LIBRARY_EXTENSION,
    'FFmpeg': str(LIBRARY_DIR / 'FFmpeg/ffmpeg') + LIBRARY_EXTENSION,
    'FFprobe': str(LIBRARY_DIR / 'FFmpeg/ffprobe') + LIBRARY_EXTENSION,
    'QSVEncC': str(LIBRARY_DIR / 'QSVEncC/QSVEncC') + LIBRARY_EXTENSION,
    'NVEncC': str(LIBRARY_DIR / 'NVEncC/NVEncC') + LIBRARY_EXTENSION,
    'VCEEncC': str(LIBRARY_DIR / 'VCEEncC/VCEEncC') + LIBRARY_EXTENSION,
    'rkmppenc': str(LIBRARY_DIR / 'rkmppenc/rkmppenc') + LIBRARY_EXTENSION,
    'tsreadex': str(LIBRARY_DIR / 'tsreadex/tsreadex') + LIBRARY_EXTENSION,
    'psisiarc': str(LIBRARY_DIR / 'psisiarc/psisiarc') + LIBRARY_EXTENSION,
    'psisimux': str(LIBRARY_DIR / 'psisimux/psisimux') + LIBRARY_EXTENSION,
}

# データベース (Tortoise ORM) の設定
__model_list = [name for _, name, _ in pkgutil.iter_modules(path=['app/models'])]
DATABASE_CONFIG = {
    'timezone': 'Asia/Tokyo',
    'connections': {
        'default': f'sqlite://{DATA_DIR / "database.sqlite"!s}',
    },
    'apps': {
        'models': {
            'models': [f'app.models.{name}' for name in __model_list] + ['aerich.models'],
            'default_connection': 'default',
        }
    }
}

# Uvicorn のロギング設定
## この dictConfig を Uvicorn に渡す (KonomiTV 本体のロギング設定は app.logging に別で存在する)
## Uvicorn のもとの dictConfig を参考にして作成した
## ref: https://github.com/encode/uvicorn/blob/0.18.2/uvicorn/config.py#L95-L126
LOGGING_CONFIG: dict[str, Any] = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        # サーバーログ用のログフォーマッター
        'default': {
            '()': 'uvicorn.logging.DefaultFormatter',
            'datefmt': '%Y/%m/%d %H:%M:%S',
            'format': '[%(asctime)s] %(levelprefix)s %(message)s',
        },
        'default_file': {
            '()': 'uvicorn.logging.DefaultFormatter',
            'datefmt': '%Y/%m/%d %H:%M:%S',
            'format': '[%(asctime)s] %(levelprefix)s %(message)s',
            'use_colors': False,  # ANSI エスケープシーケンスを出力しない
        },
        # サーバーログ (デバッグ) 用のログフォーマッター
        'debug': {
            '()': 'uvicorn.logging.DefaultFormatter',
            'datefmt': '%Y/%m/%d %H:%M:%S',
            'format': '[%(asctime)s] %(levelprefix)s %(pathname)s:%(lineno)s:\n'
                '                                %(message)s',
        },
        'debug_file': {
            '()': 'uvicorn.logging.DefaultFormatter',
            'datefmt': '%Y/%m/%d %H:%M:%S',
            'format': '[%(asctime)s] %(levelprefix)s %(pathname)s:%(lineno)s:\n'
                '                                %(message)s',
            'use_colors': False,  # ANSI エスケープシーケンスを出力しない
        },
        # アクセスログ用のログフォーマッター
        'access': {
            '()': 'uvicorn.logging.AccessFormatter',
            'datefmt': '%Y/%m/%d %H:%M:%S',
            'format': '[%(asctime)s] %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
        'access_file': {
            '()': 'uvicorn.logging.AccessFormatter',
            'datefmt': '%Y/%m/%d %H:%M:%S',
            'format': '[%(asctime)s] %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            'use_colors': False,  # ANSI エスケープシーケンスを出力しない
        },
    },
    'handlers': {
        ## サーバーログは標準エラー出力と server/logs/KonomiTV-Server.log の両方に出力する
        'default': {
            'formatter': 'default',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr',
        },
        'default_file': {
            'formatter': 'default_file',
            'class': 'logging.FileHandler',
            'filename': KONOMITV_SERVER_LOG_PATH,
            'mode': 'a',
            'encoding': 'utf-8',
        },
        ## サーバーログ (デバッグ) は標準エラー出力と server/logs/KonomiTV-Server.log の両方に出力する
        'debug': {
            'formatter': 'debug',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr',
        },
        'debug_file': {
            'formatter': 'debug_file',
            'class': 'logging.FileHandler',
            'filename': KONOMITV_SERVER_LOG_PATH,
            'mode': 'a',
            'encoding': 'utf-8',
        },
        ## アクセスログは標準出力と server/logs/KonomiTV-Access.log の両方に出力する
        'access': {
            'formatter': 'access',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
        'access_file': {
            'formatter': 'access_file',
            'class': 'logging.FileHandler',
            'filename': KONOMITV_ACCESS_LOG_PATH,
            'mode': 'a',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'uvicorn': {'level': 'INFO', 'handlers': ['default', 'default_file']},
        'uvicorn.debug': {'level': 'DEBUG', 'handlers': ['debug', 'debug_file'], 'propagate': False},
        'uvicorn.access': {'level': 'INFO', 'handlers': ['access', 'access_file'], 'propagate': False},
        'uvicorn.error': {'level': 'INFO'},
    },
}

# 品質を表す Pydantic モデル
class Quality(BaseModel):
    is_hevc: bool  # 映像コーデックが HEVC かどうか
    is_60fps: bool  # フレームレートが 60fps かどうか
    width: PositiveInt  # 縦解像度
    height: PositiveInt  # 横解像度
    video_bitrate: str  # 映像のビットレート
    video_bitrate_max: str  # 映像の最大ビットレート
    audio_bitrate: str  # 音声のビットレート

# 品質の種類 (型定義)
QUALITY_TYPES = Literal[
    '1080p-60fps',
    '1080p-60fps-hevc',
    '1080p',
    '1080p-hevc',
    '810p',
    '810p-hevc',
    '720p',
    '720p-hevc',
    '540p',
    '540p-hevc',
    '480p',
    '480p-hevc',
    '360p',
    '360p-hevc',
    '240p',
    '240p-hevc',
]

# 映像と音声の品質
QUALITY: dict[QUALITY_TYPES, Quality] = {
    '1080p-60fps': Quality(
        is_hevc = False,
        is_60fps = True,
        width = 1440,
        height = 1080,
        video_bitrate = '9500K',
        video_bitrate_max = '13000K',
        audio_bitrate = '256K',
    ),
    '1080p-60fps-hevc': Quality(
        is_hevc = True,
        is_60fps = True,
        width = 1440,
        height = 1080,
        video_bitrate = '3500K',
        video_bitrate_max = '5200K',
        audio_bitrate = '192K',
    ),
    '1080p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 1440,
        height = 1080,
        video_bitrate = '9500K',
        video_bitrate_max = '13000K',
        audio_bitrate = '256K',
    ),
    '1080p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 1440,
        height = 1080,
        video_bitrate = '3000K',
        video_bitrate_max = '4500K',
        audio_bitrate = '192K',
    ),
    '810p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 1440,
        height = 810,
        video_bitrate = '5500K',
        video_bitrate_max = '7600K',
        audio_bitrate = '192K',
    ),
    '810p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 1440,
        height = 810,
        video_bitrate = '2500K',
        video_bitrate_max = '3700K',
        audio_bitrate = '192K',
    ),
    '720p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 1280,
        height = 720,
        video_bitrate = '4500K',
        video_bitrate_max = '6200K',
        audio_bitrate = '192K',
    ),
    '720p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 1280,
        height = 720,
        video_bitrate = '2000K',
        video_bitrate_max = '3000K',
        audio_bitrate = '192K',
    ),
    '540p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 960,
        height = 540,
        video_bitrate = '3000K',
        video_bitrate_max = '4100K',
        audio_bitrate = '192K',
    ),
    '540p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 960,
        height = 540,
        video_bitrate = '1400K',
        video_bitrate_max = '2100K',
        audio_bitrate = '192K',
    ),
    '480p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 854,
        height = 480,
        video_bitrate = '2000K',
        video_bitrate_max = '2800K',
        audio_bitrate = '192K',
    ),
    '480p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 854,
        height = 480,
        video_bitrate = '1050K',
        video_bitrate_max = '1750K',
        audio_bitrate = '192K',
    ),
    '360p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 640,
        height = 360,
        video_bitrate = '1100K',
        video_bitrate_max = '1800K',
        audio_bitrate = '128K',
    ),
    '360p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 640,
        height = 360,
        video_bitrate = '750K',
        video_bitrate_max = '1250K',
        audio_bitrate = '128K',
    ),
    '240p': Quality(
        is_hevc = False,
        is_60fps = False,
        width = 426,
        height = 240,
        video_bitrate = '550K',
        video_bitrate_max = '650K',
        audio_bitrate = '128K',
    ),
    '240p-hevc': Quality(
        is_hevc = True,
        is_60fps = False,
        width = 426,
        height = 240,
        video_bitrate = '450K',
        video_bitrate_max = '650K',
        audio_bitrate = '128K',
    ),
}

# ニコニコ OAuth の Client ID
NICONICO_OAUTH_CLIENT_ID = '4JTJdyBZLwMJwaI7'

# JWT のエンコード/デコードに使うシークレットキー
## jwt_secret.dat がない場合は自動生成する
JWT_SECRET_KEY_PATH = DATA_DIR / 'jwt_secret.dat'
if Path.exists(JWT_SECRET_KEY_PATH) is False:
    with open(JWT_SECRET_KEY_PATH, mode='w', encoding='utf-8') as file:
        file.write(secrets.token_hex(32))  # 32ビット (256文字) の乱数を書き込む
## jwt_secret.dat からシークレットキーをロードする
with open(JWT_SECRET_KEY_PATH, encoding='utf-8') as file:
    JWT_SECRET_KEY = file.read().strip()

# パスワードハッシュ化のための設定
PASSWORD_CONTEXT = CryptContext(
    schemes = ['bcrypt'],
    deprecated = 'auto',
)

# 外部 API に送信するリクエストヘッダー
## KonomiTV の User-Agent を指定
API_REQUEST_HEADERS: dict[str, str] = {
    'User-Agent': f'KonomiTV/{VERSION}',
}

# KonomiTV で利用する httpx.AsyncClient の設定
## httpx.AsyncClient 自体は一度使ったら再利用できないので、httpx.AsyncClient を返す関数にしている
HTTPX_CLIENT = lambda: httpx.AsyncClient(
    # KonomiTV の User-Agent を指定
    headers = API_REQUEST_HEADERS,
    # リダイレクトを追跡する
    follow_redirects = True,
    # 3 秒応答がない場合はタイムアウトする
    timeout = 3.0,
)
