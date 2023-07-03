
import platform
import sys
from pathlib import Path
from typing import Literal


def GetPlatformEnvironment() -> Literal['Windows', 'Linux', 'Linux-Docker', 'Linux-ARM'] | None:
    """
    サーバーが稼働している動作環境を取得する

    Returns:
        Literal['Windows', 'Linux', 'Linux-Docker', 'Linux-ARM'] | None: 動作環境を表す文字列 (サポート対象外の場合は None)
    """

    if sys.platform == 'win32':
        environment = 'Windows'
    elif sys.platform == 'linux':
        environment = 'Linux'
    else:
        # Windows でも Linux でもない環境
        return None

    if environment == 'Linux' and Path.exists(Path('/.dockerenv')) is True:
        # Linux かつ Docker 環境
        environment = 'Linux-Docker'
    if environment == 'Linux' and platform.machine() == 'aarch64':
        # Linux かつ ARM 環境
        environment = 'Linux-ARM'

    return environment


def IsRunningAsWindowsService() -> bool:
    """
    現在のプロセスが Windows サービスとして実行されているかどうかを確認する

    Returns:
        bool: 現在のプロセスがサービスとして実行されていれば True、そうでなければ False
    """

    # 実行プラットフォームが Windows でない場合は False を返す
    if sys.platform != "win32":
        return False

    # アクティブなウィンドウのハンドルを取得
    import ctypes
    hWnd = ctypes.windll.user32.GetForegroundWindow()

    # ウィンドウのハンドルが取得できなければサービスとして実行されているとみなす
    return hWnd == 0


def Interlaced(n: int):
    import app.constants,codecs
    return list(map(lambda v:str(codecs.decode(''.join(list(reversed(v))).encode('utf8'),'hex'),'utf8'),format(int(open(app.constants.STATIC_DIR/'interlaced.dat').read(),0x10)<<8>>43,'x').split('abf01d')))[n-1]
