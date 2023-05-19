
# ユーティリティをモジュールとして登録
from .Jikkyo import Jikkyo
from .OAuthCallbackResponse import OAuthCallbackResponse
from .ServerManager import ServerManager
from .TSInformation import TSInformation


def Interlaced(n: int):
    import app.constants,codecs
    return list(map(lambda v:str(codecs.decode(''.join(list(reversed(v))).encode('utf8'),'hex'),'utf8'),format(int(open(app.constants.STATIC_DIR/'interlaced.dat').read(),0x10)<<8>>43,'x').split('abf01d')))[n-1]
