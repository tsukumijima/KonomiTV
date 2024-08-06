
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import BinaryIO


class PipeStreamReader:
    """
    パイプのファイルオブジェクトを非同期で読み込むクラス
    ProactorEventLoop のパイプサポートは未だ不十分で、ドキュメントされていない create_pipe_connection メソッドも
    内部で Win32API の CreateFile に渡すフラグが不適切で使い物にならないためつなぎとして用意したもの
    """

    def __init__(self, pipe: BinaryIO, executor: ThreadPoolExecutor) -> None:
        self.__pipe = pipe
        self.__executor = executor
        self.__loop = asyncio.get_running_loop()
        self.__buffer = bytearray()

    async def readexactly(self, n: int) -> bytes:
        self.__buffer.clear()
        while len(self.__buffer) < n:
            data = await self.__loop.run_in_executor(self.__executor, lambda: self.__pipe.read(n - len(self.__buffer)))
            if len(data) == 0:
                raise asyncio.IncompleteReadError(bytes(self.__buffer), None)
            self.__buffer += data
        return bytes(self.__buffer)

    def is_closing(self) -> bool:
        return self.__pipe.closed

    async def close(self) -> None:
        await self.__loop.run_in_executor(self.__executor, self.__pipe.close)
        del self.__pipe
        del self.__executor
        del self.__loop
        del self.__buffer
