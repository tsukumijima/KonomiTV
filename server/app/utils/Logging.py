
import ctypes
import logging
import os
import sys
import uvicorn.logging

from app.constants import CONFIG, KONOMITV_SERVER_LOG_PATH


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
## ログは標準エラー出力と server/logs/KonomiTV-Server.log の両方に出力する
## 通常用
logger_default = logging.getLogger('KonomiTV')
handler_default = logging.StreamHandler()
handler_default_file = logging.FileHandler(KONOMITV_SERVER_LOG_PATH, mode='a', encoding='utf-8')
## デバッグ向け
logger_debug = logging.getLogger('KonomiTV-Debug')
handler_debug = logging.StreamHandler()
handler_debug_file = logging.FileHandler(KONOMITV_SERVER_LOG_PATH, mode='a', encoding='utf-8')

# Uvicorn の Formatter をフォーマットを変更した上で利用する
# ref: https://github.com/encode/uvicorn/blob/master/uvicorn/logging.py
## 通常用
handler_default.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '[%(asctime)s] %(levelprefix)s %(message)s',
    datefmt = '%Y/%m/%d %H:%M:%S',
    use_colors = sys.stderr.isatty(),
))
handler_default_file.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '[%(asctime)s] %(levelprefix)s %(message)s',
    datefmt = '%Y/%m/%d %H:%M:%S',
    use_colors = False,  # ANSI エスケープシーケンスを出力しない
))
logger_default.addHandler(handler_default)
logger_default.addHandler(handler_default_file)
## デバッグ向け
handler_debug.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '[%(asctime)s] %(levelprefix)s %(pathname)s:%(lineno)s:\n'
          '                                %(message)s',
    datefmt = '%Y/%m/%d %H:%M:%S',
    use_colors = sys.stderr.isatty(),
))
handler_debug_file.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '[%(asctime)s] %(levelprefix)s %(message)s',
    datefmt = '%Y/%m/%d %H:%M:%S',
    use_colors = False,  # ANSI エスケープシーケンスを出力しない
))
logger_debug.addHandler(handler_debug)
logger_debug.addHandler(handler_debug_file)

# デバッグモードであればログ出力のしきい値を DEBUG に設定
if CONFIG['general']['debug'] is True:
    logger_default.setLevel(logging.DEBUG)
    logger_debug.setLevel(logging.DEBUG)
    logger = logger_debug  # 利用する Logger を入れておく
else:
    logger_default.setLevel(logging.INFO)
    logger_debug.setLevel(logging.INFO)
    logger = logger_default  # 利用する Logger を入れておく


def debug(message):
    """ デバッグログを出力する """
    logger_debug.debug(message, stacklevel=2)

def debug_simple(message):
    """ デバッグログを出力する (スクリプトパス・行番号を出力しない) """
    logger_default.debug(message, stacklevel=2)

def info(message):
    """ 情報ログを出力する """
    logger_default.info(message, stacklevel=2)

def warning(message):
    """ 警告ログを出力する """
    logger_default.warning(message, stacklevel=2)

def error(message):
    """ エラーログを出力する """
    logger_default.error(message, stacklevel=2)
