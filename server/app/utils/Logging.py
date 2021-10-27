
import ctypes
import logging
import os
import sys
import uvicorn.logging

from app.constants import CONFIG


# ログの色付き表示に必要な ANSI エスケープシーケンスを Windows でも有効化
# conhost.exe では明示的に SetConsoleMode() で有効にしないとエスケープシーケンスがそのまま表示されてしまう
# Windows Terminal なら何もしなくても色付きで表示される
# Windows 7, 8.1 はエスケープシーケンス非対応だけど、クリティカルな不具合ではないのでご愛嬌…
# ref: https://github.com/tiangolo/fastapi/pull/3753
if os.name == 'nt':
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

# Logger と Handler を定義
## 通常とデバッグ向けで 2 つ用意する
logger_default = logging.getLogger('KonomiTV')
logger_debug = logging.getLogger('KonomiTV_debug')
handler_default = logging.StreamHandler()  # 通常
handler_debug = logging.StreamHandler()  # デバッグ向け

# Uvicorn の Formatter をフォーマットを変更した上で利用する
# ref: https://github.com/encode/uvicorn/blob/master/uvicorn/logging.py
handler_default.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '%(levelprefix)s %(message)s',
    use_colors = sys.stderr.isatty(),
))
logger_default.addHandler(handler_default)
handler_debug.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '%(levelprefix)s [%(asctime)s] %(filename)s:%(lineno)s:\n          %(message)s',
    use_colors = sys.stderr.isatty(),
))
logger_debug.addHandler(handler_debug)

# デバッグモードであればロギングのしきい値を DEBUG に設定
if CONFIG['general']['debug'] is True:
    logger_default.setLevel(logging.DEBUG)
    logger_debug.setLevel(logging.DEBUG)
    logger = logger_debug  # 利用する Logger を入れておく
else:
    logger_default.setLevel(logging.INFO)
    logger_debug.setLevel(logging.INFO)
    logger = logger_default  # 利用する Logger を入れておく


def debug(message):
    logger_debug.debug(message, stacklevel=2)

def debug_simple(message):
    logger_default.debug(message, stacklevel=2)

def info(message):
    logger_default.info(message, stacklevel=2)

def warning(message):
    logger_default.warning(message, stacklevel=2)

def error(message):
    logger_default.error(message, stacklevel=2)
