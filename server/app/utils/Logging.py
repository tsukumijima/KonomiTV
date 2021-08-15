
import logging
import uvicorn.logging

from app.constants import CONFIG


# Logger と Handler を定義
## 通常とデバッグ向けで 2 つ用意する
logger = logging.getLogger('Konomi')
logger_debug = logging.getLogger('Konomi_debug')
handler = logging.StreamHandler()  # 通常
handler_debug = logging.StreamHandler()  # デバッグ向け

# Uvicorn の Formatter をフォーマットを変更した上で利用する
# ref: https://github.com/encode/uvicorn/blob/master/uvicorn/logging.py
handler.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '%(levelprefix)s %(message)s',
    use_colors = True,
))
logger.addHandler(handler)
handler_debug.setFormatter(uvicorn.logging.DefaultFormatter(
    fmt = '%(levelprefix)s [%(asctime)s] %(filename)s:%(lineno)s:\n          %(message)s',
    use_colors = True,
))
logger_debug.addHandler(handler_debug)

# デバッグモードであればロギングのしきい値を DEBUG に設定
if CONFIG['general']['debug'] is True:
    logger.setLevel(logging.DEBUG)
    logger_debug.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
    logger_debug.setLevel(logging.INFO)


def debug(message):
    logger_debug.debug(message, stacklevel=2)

def debug_simple(message):
    logger.debug(message, stacklevel=2)

def info(message):
    logger.info(message, stacklevel=2)

def warning(message):
    logger.warning(message, stacklevel=2)

def error(message):
    logger.error(message, stacklevel=2)
