
# ユーティリティをモジュールとして登録
from .Jikkyo import Jikkyo
from .TSInformation import TSInformation

import asyncio
import functools
import jaconv
import typing
import warnings


def ZenkakuToHankaku(string: str) -> str:
    """
    全角文字を半角文字に置換するヘルパー (jaconv のラッパー)
    jaconv では半角になってしまう！や？などの一部の記号を全角のままにして置換するほか、同時に Unicode の囲み文字を大かっこに置換する

    Args:
        string (str): 全角文字が含まれる文字列

    Returns:
        str: 全角文字を半角文字に置換した文字列
    """

    # jaconv の変換結果
    # シャープ (♯) をハッシュ (#) に置換する
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


def RunAwait(coro:typing.Coroutine) -> typing.Any:
    """
    非同期関数を同期的に実行するためのヘルパー
    非同期関数を実行し、結果が返ってくるのを待つ

    Args:
        coro (Coroutine): 非同期関数のコルーチン

    Returns:
        [Any]: 非同期関数の戻り値
    """

    # await で実行完了を待つ
    # これを挟む事で、直接的にはコルーチンでない非同期関数もコルーチンにできる
    async def run(coro:typing.Coroutine):
        return await coro

    # メインスレッドのイベントループを取ってくる
    from app import app
    loop = app.loop

    ## なぜか警告が出ることがあるが、実行できるので黙殺する
    ## ref: https://note.nkmk.me/python-warnings-ignore-warning/
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        try:

            # メインスレッドのイベントループ上でコルーチンを実行し、結果が返ってくるのを待つ
            # メインスレッドのイベントループ上でないと変なエラーが出る事がある（スレッドセーフでないため）
            future = asyncio.run_coroutine_threadsafe(run(coro), loop)
            result = future.result()

        # メインスレッドのイベントループが使用できない状態の場合
        except RuntimeError:

            # 新しいイベントループを作成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # イベントループ上でコルーチンを実行し、結果が返ってくるのを待つ
            result = loop.run_until_complete(run(coro))

    # 実行結果を返す
    return result


async def RunAsync(sync_function:typing.Callable, *args:typing.Any, **kwargs:typing.Any) -> typing.Coroutine:
    """
    同期関数をスレッド上で非同期的に実行するためのヘルパー
    同期関数を実行し、Awaitable なコルーチンオブジェクトを返す

    Args:
        function (typing.Callable): 同期関数
        *args (Any): 同期関数の引数（可変長引数）
        *kwargs (Any): 同期関数のキーワード引数（可変長引数）

    Returns:
        typing.Coroutine: 同期関数のコルーチン
    """

    # ref: https://github.com/tiangolo/fastapi/issues/1066
    # ref: https://github.com/tiangolo/starlette/blob/master/starlette/concurrency.py

    # 現在のイベントループを取得
    loop = asyncio.get_running_loop()

    # 引数なしの形で呼べるようにする
    sync_function_noargs = functools.partial(sync_function, *args, **kwargs)

    # スレッドプール上で実行する
    return await loop.run_in_executor(None, sync_function_noargs)
