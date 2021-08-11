
# ユーティリティをモジュールとして登録
from .TSInformation import TSInformation

import asyncio
import functools
import typing


def RunAwait(coro:typing.Coroutine):
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

    # asyncio.run() で非同期関数を実行し、戻り値を返す
    return asyncio.run(run(coro))

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

    # ref:https://github.com/tiangolo/fastapi/issues/1066
    # ref:https://github.com/tiangolo/starlette/blob/master/starlette/concurrency.py

    # 現在のイベントループを取得
    loop = asyncio.get_running_loop()

    # 引数なしの形で呼べるようにする
    sync_function_noargs = functools.partial(sync_function, *args, **kwargs)

    # スレッドプール上で実行する
    return await loop.run_in_executor(None, sync_function_noargs)
