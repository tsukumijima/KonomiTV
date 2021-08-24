
# ユーティリティをモジュールとして登録
from .TSInformation import TSInformation

import asyncio
import functools
import jaconv
import time
import typing


def ZenkakuToHankaku(string: str) -> str:
    """
    全角文字を半角文字に変換するヘルパー (jaconv のラッパー)
    jaconv では半角になってしまう！や？などの一部の記号を全角のままにして変換する

    Args:
        string (str): 全角文字が含まれる文字列

    Returns:
        str: 全角文字を半角文字に変換した文字列
    """

    # 変換結果を返す
    return jaconv.zenkaku2hankaku(string, '！？＊：；', kana=False, digit=True, ascii=True)


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
    async def run(coro:typing.Coroutine):
        return await coro

    # 非同期関数を実行し、戻り値を返す
    # イベントループ周りは壊れやすいようで、asyncio.run() だとまれにエラーになることがある
    # ref: https://stackoverflow.com/questions/53724665/using-queues-results-in-asyncio-exception-got-future-future-pending-attached
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        result = loop.run_until_complete(run(coro))
    finally:
        try:
            asyncio.runners._cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()

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
