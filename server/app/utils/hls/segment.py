
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

import asyncio
from datetime import datetime, timedelta
from typing import Iterator

from app.utils.mpeg2ts import ts


class PartialSegment:

    def __init__(self, beginPTS: int, isIFrame: bool = False) -> None:
        self.beginPTS: int = beginPTS
        self.endPTS: int | None = None
        self.hasIFrame: bool = isIFrame
        self.buffer: bytearray = bytearray()
        self.queues: list[asyncio.Queue[bytes | bytearray | None]] = []
        self.m3u8s: list[asyncio.Future[str]] = []

    def push(self, packet: bytes) -> None:
        self.buffer += packet
        for queue in self.queues: queue.put_nowait(packet)

    async def response(self) -> asyncio.Queue[bytearray | None]:
        queue = asyncio.Queue()
        queue.put_nowait(self.buffer)
        if (self.isCompleted()):
            queue.put_nowait(None)
        else:
            self.queues.append(queue)
        return queue

    def m3u8(self) -> asyncio.Future[str]:
        future: asyncio.Future[str] = asyncio.Future()
        if not self.isCompleted():
            self.m3u8s.append(future)
        return future

    def complete(self, endPTS: int) -> None:
        self.endPTS = endPTS
        for q in self.queues: q.put_nowait(None)
        self.queues = []

    def isCompleted(self) -> bool:
        return self.endPTS is not None

    def extinf(self) -> timedelta | None:
        if not self.endPTS:
            return None
        else:
            return timedelta(seconds = (((self.endPTS - self.beginPTS + ts.PCR_CYCLE) % ts.PCR_CYCLE) / ts.HZ))

    def estimate(self, endPTS: int) -> timedelta:
        return timedelta(seconds = (((endPTS - self.beginPTS + ts.PCR_CYCLE) % ts.PCR_CYCLE) / ts.HZ))


class Segment(PartialSegment):

    def __init__(self, beginPTS: int, isIFrame: bool = False):
        super().__init__(beginPTS, isIFrame = False)
        self.partials = [PartialSegment(beginPTS, isIFrame)]
        self.program_date_time = datetime.now()

    def __iter__(self) -> Iterator[PartialSegment]:
        return iter(self.partials)

    def __len__(self) -> int:
        return len(self.partials)

    def push(self, packet: bytes) -> None:
        super().push(packet)
        if not self.partials: return
        self.partials[-1].push(packet)

    def completePartial(self, endPTS: int) -> None:
        if not self.partials: return
        self.partials[-1].complete(endPTS)

    def newPartial(self, beginPTS: int, isIFrame: bool = False) -> None:
        self.partials.append(PartialSegment(beginPTS, isIFrame))

    def complete(self, endPTS: int) -> None:
        super().complete(endPTS)
        self.completePartial(endPTS)
