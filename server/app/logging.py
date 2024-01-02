
import ctypes
import logging
import logging.config
import sys
from typing import Any

from app.config import Config
from app.constants import LOGGING_CONFIG


# ログの色付き表示に必要な ANSI エスケープシーケンスを Windows でも有効化
# conhost.exe では明示的に SetConsoleMode() で有効にしないとエスケープシーケンスがそのまま表示されてしまう
# Windows Terminal なら何もしなくても色付きで表示される
# Windows 7, 8.1 はエスケープシーケンス非対応だけど、クリティカルな不具合ではないのでご愛嬌…
# ref: https://github.com/tiangolo/fastapi/pull/3753
if sys.platform == 'win32':
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

# Uvicorn を起動する前に Uvicorn のロガーを使えるようにする
logging.config.dictConfig(LOGGING_CONFIG)

# ロガーを取得
logger = logging.getLogger('uvicorn')
logger_debug = logging.getLogger('uvicorn.debug')


def debug(message: Any) -> None:
    """
    デバッグログを出力する

    Args:
        message (Any): ログメッセージ
    """
    if Config().general.debug is True:
        logger_debug.debug(message, stacklevel=2)


def debug_simple(message: Any) -> None:
    """
    デバッグログを出力する (スクリプトパス・行番号を出力しない)

    Args:
        message (Any): ログメッセージ
    """
    if Config().general.debug is True:
        logger.setLevel(logging.DEBUG)
        logger.debug(message, stacklevel=2)
        logger.setLevel(logging.INFO)


def info(message: Any) -> None:
    """
    情報ログを出力する

    Args:
        message (Any): ログメッセージ
    """
    logger.info(message, stacklevel=2)


def warning(message: Any) -> None:
    """
    警告ログを出力する

    Args:
        message (Any): ログメッセージ
    """
    logger.warning(message, stacklevel=2)


def error(message: Any) -> None:
    """
    エラーログを出力する

    Args:
        message (Any): ログメッセージ
    """
    logger.error(message, stacklevel=2)
