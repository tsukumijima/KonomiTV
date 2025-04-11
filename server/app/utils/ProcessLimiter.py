
import asyncio
from typing import ClassVar

import psutil


class ProcessLimiter:
    """
    外部プロセスの同時実行数を CPU コア数の 50% に制限するためのユーティリティクラス
    """

    # クラス変数として Semaphore の辞書を保持
    # key: プロセスを識別するキー
    # value: そのプロセス用の Semaphore
    _semaphores: ClassVar[dict[str, asyncio.Semaphore]] = {}


    @classmethod
    def getSemaphore(cls, process_key: str) -> asyncio.Semaphore:
        """
        指定されたプロセス用の Semaphore を取得する
        初回呼び出し時に CPU 論理コア数の 50% の Semaphore を作成する

        Args:
            process_key (str): プロセスを識別するキー

        Returns:
            asyncio.Semaphore: 指定されたプロセス用の Semaphore
        """

        if process_key not in cls._semaphores:
            # CPU 論理コア数を取得
            cpu_count = psutil.cpu_count(logical=True)
            if cpu_count is None:
                cpu_count = 4  # 取得できない場合は4コアと仮定
            # 同時実行数を CPU コア数の 50% に制限
            cls._semaphores[process_key] = asyncio.Semaphore(cpu_count // 2)
        return cls._semaphores[process_key]
