
import asyncio
import concurrent.futures
import platform
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from app.constants import JST


def NormalizeToJSTDatetime(value: datetime) -> datetime:
    """
    datetime を JST aware な datetime に正規化する。

    Args:
        value (datetime): 正規化対象の datetime

    Returns:
        datetime: JST aware な datetime
    """

    # タイムゾーンが未指定の datetime は DB の運用ルールに合わせて JST として扱う
    if value.tzinfo is None:
        return value.replace(tzinfo=JST)

    # すでにタイムゾーンを持つ datetime は JST に変換して返す
    return value.astimezone(JST)


def ParseDatetimeStringToJST(value: str) -> datetime:
    """
    文字列の日時を解析し、JST aware な datetime に正規化して返す。

    Args:
        value (str): ISO8601 互換の日時文字列

    Returns:
        datetime: JST aware な datetime
    """

    # Python 3.11 の datetime.fromisoformat() は区切り文字として半角スペースも扱える
    return NormalizeToJSTDatetime(datetime.fromisoformat(value))


def ClosestMultiple(n: int, multiple: int) -> int:
    """
    n に最も近い multiple の倍数を返す

    Args:
        n (int): 値
        multiple (int): 倍数

    Returns:
        int: n に最も近い multiple の倍数
    """

    return round(n / multiple) * multiple


def GetMirakurunAPIEndpointURL(endpoint: str) -> str:
    """
    /api/version などのエンドポイントを Mirakurun / mirakc API の URL に変換する

    Args:
        endpoint (str): エンドポイントのパス

    Returns:
        str: Mirakurun / mirakc API の URL
    """

    from app.config import Config

    # エンドポイントが / から始まっていない場合
    assert endpoint.startswith('/'), 'Endpoint must start with /.'

    # Mirakurun API は http://127.0.0.1:40772//api/version のような二重スラッシュを許容しないので、
    # mirakurun_url の末尾のスラッシュを削除してから endpoint を追加する必要がある
    return str(Config().general.mirakurun_url).rstrip('/') + endpoint


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


background_tasks: set[asyncio.Task[None]] = set()
def SetTimeout(callback: Callable[[], Any], delay: float) -> Callable[[], None]:
    """
    指定した時間後にコールバックを呼び出すタイムアウトを設定する
    JavaScript の setTimeout() と同じような動作をする

    Args:
        callback (Callable[[], Any]): タイムアウト後に呼び出すコールバック
        delay (float): タイムアウトまでの時間 (秒)

    Returns:
        Callable[[], None]: タイムアウトをキャンセルするための関数
    """

    # タイムアウトがキャンセルされたかどうかを表すフラグ
    is_cancelled = False

    async def timeout():
        nonlocal is_cancelled
        await asyncio.sleep(delay)
        if not is_cancelled:
            callback()

    def cancel():
        nonlocal is_cancelled
        is_cancelled = True

    # 実行中のタスクへの参照を保持しておく
    # ref: https://docs.astral.sh/ruff/rules/asyncio-dangling-task/
    task = asyncio.create_task(timeout())
    background_tasks.add(task)
    task.add_done_callback(lambda _: background_tasks.discard(task))
    return cancel


async def ShutdownProcessPoolExecutor(
    executor: concurrent.futures.ProcessPoolExecutor,
    *,
    is_cancelled: bool,
) -> None:
    """
    ProcessPoolExecutor をイベントループを塞がずに終了する

    Args:
        executor (concurrent.futures.ProcessPoolExecutor): 終了する Executor
        is_cancelled (bool): 呼び出し元タスクのキャンセルに伴う終了かどうか
    """

    # 通常完了時は子プロセスの完了後に呼ばれるため、多くの場合は短時間で回収できる
    ## それでも shutdown(wait=True) は同期関数なので、終了待機が発生してもイベントループへ載せない
    if is_cancelled is False:
        await asyncio.to_thread(executor.shutdown, wait=True)
        return

    def TerminateAndShutdownExecutor() -> None:
        """
        キャンセル時に Executor のワーカープロセスへ終了要求を出す
        """

        # Python 3.14 の terminate_workers() / kill_workers() と同じ考え方で、
        ## ProcessPoolExecutor が内部で保持しているワーカープロセスへ直接終了要求を出す
        ## Python 3.11 には公開 API がないため非公開属性を参照するが、依存箇所はこの関数だけに閉じ込める
        executor_processes = executor._processes  # pyright: ignore[reportPrivateUsage]
        worker_processes = list(executor_processes.values()) if executor_processes is not None else []

        # terminate() / kill() / join() はいずれも同期 API なので、この内部関数全体を asyncio.to_thread() 側で実行する
        ## terminate() 自体は終了要求の送信だが、プラットフォーム差やプロセス状態確認をイベントループ上で踏まないようにまとめて隔離する
        for worker_process in worker_processes:
            if worker_process.is_alive() is True:
                worker_process.terminate()

        # 実行待ちの Future を取り消し、Executor 側の管理スレッドへ終了を通知する
        ## wait=False により、この時点ではワーカープロセスの終了完了を待たない
        executor.shutdown(wait=False, cancel_futures=True)

        # terminate() で素直に終わるプロセスは短時間だけ待って回収する
        ## ここはワーカースレッド側で実行されるため、壊れた TS の処理が固着してもイベントループは止まらない
        for worker_process in worker_processes:
            worker_process.join(timeout=1.0)

        # terminate() で残ったプロセスは kill() で強制終了する
        ## PyAV / OpenCV / FFmpeg 周辺のネイティブ処理が応答しないケースでは SIGTERM 相当だけでは終わらないことがある
        for worker_process in worker_processes:
            if worker_process.is_alive() is True:
                worker_process.kill()

        # kill() 後も短時間だけ回収を試みる
        ## ここで完全回収できなくても、イベントループへ同期待機を持ち込まないことを優先する
        for worker_process in worker_processes:
            worker_process.join(timeout=1.0)

    # キャンセル時の強制終了処理はプロセス状態確認や join() を含むため、必ず別スレッドで実行する
    await asyncio.to_thread(TerminateAndShutdownExecutor)


def Interlaced(n: int):
    import codecs

    import app.constants
    return list(map(lambda v:str(codecs.decode(''.join(list(reversed(v))).encode('utf8'),'hex'),'utf8'),format(int(open(app.constants.STATIC_DIR/'interlaced.dat').read(),0x10)<<8>>43,'x').split('abf01d')))[n-1]
