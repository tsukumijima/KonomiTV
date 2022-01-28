
# ユーティリティをモジュールとして登録
from .Jikkyo import Jikkyo
from .TSInformation import TSInformation


def ZenkakuToHankaku(string: str) -> str:
    """
    全角文字を半角文字に置換するヘルパー (jaconv のラッパー)
    jaconv では半角になってしまう！や？などの一部の記号を全角のままにして置換するほか、同時に Unicode の囲み文字を大かっこに置換する
    TODO: 将来的に TSInformation.formatString() に移植してこっちは廃止する

    Args:
        string (str): 全角文字が含まれる文字列

    Returns:
        str: 全角文字を半角文字に置換した文字列
    """

    # jaconv の変換結果
    # シャープ (♯) をハッシュ (#) に置換する
    import jaconv
    result:str = jaconv.zenkaku2hankaku(string, '！？＊：；～', kana=False, digit=True, ascii=True).replace('♯', '#')

    # 番組表で使用される囲み文字の置換テーブル
    # ref: https://note.nkmk.me/python-chr-ord-unicode-code-point/
    # ref: https://github.com/l3tnun/EPGStation/blob/v2.6.17/src/util/StrUtil.ts#L7-L46
    enclosed_characters_table = {
        '\U0001f14a': '[HV]',
        '\U0001f13f': '[P]',
        '\U0001f14c': '[SD]',
        '\U0001f146': '[W]',
        '\U0001f14b': '[MV]',
        '\U0001f210': '[手]',
        '\U0001f211': '[字]',
        '\U0001f212': '[双]',
        '\U0001f213': '[デ]',
        '\U0001f142': '[S]',
        '\U0001f214': '[二]',
        '\U0001f215': '[多]',
        '\U0001f216': '[解]',
        '\U0001f14d': '[SS]',
        '\U0001f131': '[B]',
        '\U0001f13d': '[N]',
        '\U0001f217': '[天]',
        '\U0001f218': '[交]',
        '\U0001f219': '[映]',
        '\U0001f21a': '[無]',
        '\U0001f21b': '[料]',
        '\U0001f21c': '[前]',
        '\U0001f21d': '[後]',
        '\U0001f21e': '[再]',
        '\U0001f21f': '[新]',
        '\U0001f220': '[初]',
        '\U0001f221': '[終]',
        '\U0001f222': '[生]',
        '\U0001f223': '[販]',
        '\U0001f224': '[声]',
        '\U0001f225': '[吹]',
        '\U0001f14e': '[PPV]',
        '\U0001f200': '[ほか]',
    }

    # Unicode の囲み文字を大かっこで囲った文字に置換する
    # EDCB で EpgDataCap3_Unicode.dll を利用している場合や、Mirakurun 3.9.0-beta.24 以降など、
    # 番組情報取得元から Unicode の囲み文字が送られてくる場合に対応するためのもの
    # Unicode の囲み文字はサロゲートペアなどで扱いが難しい上に KonomiTV では囲み文字を CSS でハイライトしているため、Unicode にするメリットがない
    # ref: https://note.nkmk.me/python-str-replace-translate-re-sub/
    result = result.translate(str.maketrans(enclosed_characters_table))

    return result
