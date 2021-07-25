
import logging


# ハンドラーとロガーを定義
handler = logging.StreamHandler()
logger = logging.getLogger(__name__)

# ロギングフォーマットを設定
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(filename)s:%(lineno)s:\n  %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# ロギングレベル
if False:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.DEBUG)


def debug(message):
    logger.debug(message, stacklevel=2)

def info(message):
    logger.info(message, stacklevel=2)

def error(message):
    logger.error(message, stacklevel=2)
