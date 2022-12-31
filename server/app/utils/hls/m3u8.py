
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

import asyncio
from collections import deque
from datetime import timedelta
from typing import cast

from app.utils.hls.segment import Segment


class M3U8:

    def __init__(self, target_duration: int, part_target: float, list_size: int | None, hasInit: bool = False, prefix: str = '') -> None:
        self.media_sequence: int = 0
        self.target_duration: int = target_duration
        self.part_target: float = part_target
        self.list_size: int | None = list_size
        self.hasInit: bool = hasInit
        self.prefix: str = prefix
        self.segments: deque[Segment] = deque()
        self.published: bool = False
        self.futures: list[asyncio.Future[str]] = []

    def in_range(self, msn: int) -> bool:
        return self.media_sequence <= msn and msn < self.media_sequence + len(self.segments)

    def plain(self) -> asyncio.Future[str]:
        future: asyncio.Future[str] = asyncio.Future()
        if self.published:
            future.set_result(self.manifest())
        else:
            self.futures.append(future)
        return future

    def blocking(self, msn: int, part: int) -> asyncio.Future[str] | None:
        if not self.in_range(msn): return None

        future: asyncio.Future[str] = asyncio.Future()
        index = msn - self.media_sequence

        if part is None:
            if self.segments[index].isCompleted():
                future.set_result(self.manifest())
            else:
                self.segments[index].m3u8s.append(future)
        else:
            if part > len(self.segments[index].partials): return None

            if self.segments[index].partials[part].isCompleted():
                future.set_result(self.manifest())
            else:
                self.segments[index].partials[part].m3u8s.append(future)
        return future

    def push(self, packet: bytes) -> None:
        if not self.segments: return
        self.segments[-1].push(packet)

    def newSegment(self, beginPTS: int, isIFrame: bool = False) -> None:
        self.segments.append(Segment(beginPTS, isIFrame))
        while self.list_size is not None and self.list_size < len(self.segments):
            self.segments.popleft()
            self.media_sequence += 1

    def newPartial(self, beginPTS: int, isIFrame: bool = False) -> None:
        if not self.segments: return
        self.segments[-1].newPartial(beginPTS, isIFrame)

    def completeSegment(self, endPTS: int) -> None:
        self.published = True

        if not self.segments: return
        self.segments[-1].complete(endPTS)
        for m in self.segments[-1].partials[-1].m3u8s:
            if not m.done(): m.set_result(self.manifest())
        self.segments[-1].partials[-1].m3u8s = []
        for m in self.segments[-1].m3u8s:
            if not m.done(): m.set_result(self.manifest())
        self.segments[-1].m3u8s = []
        for f in self.futures: f.set_result(self.manifest())
        self.futures = []

    def completePartial(self, endPTS: int) -> None:
        if not self.segments: return
        self.segments[-1].completePartial(endPTS)
        for m in self.segments[-1].partials[-1].m3u8s:
            if not m.done(): m.set_result(self.manifest())
        self.segments[-1].partials[-1].m3u8s

    def continuousSegment(self, endPTS: int, isIFrame: bool = False) -> None:
        lastSegment = self.segments[-1] if self.segments else None
        self.newSegment(endPTS, isIFrame)

        self.published = True
        if lastSegment:
            lastSegment.complete(endPTS)
            for m in lastSegment.partials[-1].m3u8s:
                if not m.done(): m.set_result(self.manifest())
            lastSegment.partials[-1].m3u8s = []
            for m in lastSegment.m3u8s:
                if not m.done(): m.set_result(self.manifest())
            lastSegment.m3u8s = []
        for f in self.futures: f.set_result(self.manifest())
        self.futures = []

    def continuousPartial(self, endPTS: int, isIFrame: bool = False) -> None:
        lastSegment = self.segments[-1] if self.segments else None
        lastPartial = lastSegment.partials[-1] if lastSegment else None
        self.newPartial(endPTS, isIFrame)

        if not lastPartial: return
        lastPartial.complete(endPTS)
        for m in lastPartial.m3u8s:
            if not m.done(): m.set_result(self.manifest())
        lastPartial.m3u8s = []

    async def segment(self, msn: int) -> asyncio.Queue[bytearray | None] | None:
        if not self.in_range(msn): return None
        index = msn - self.media_sequence
        return await self.segments[index].response()

    async def partial(self, msn: int, part: int) -> asyncio.Queue[bytearray | None] | None:
        if not self.in_range(msn): return None
        index = msn - self.media_sequence
        if part > len(self.segments[index].partials): return None
        return await self.segments[index].partials[part].response()

    def manifest(self) -> str:
        m3u8 = ''
        m3u8 += f'#EXTM3U\n'
        m3u8 += f'#EXT-X-VERSION:6\n'
        m3u8 += f'#EXT-X-TARGETDURATION:{self.target_duration}\n'
        m3u8 += f'#EXT-X-PART-INF:PART-TARGET={self.part_target:.06f}\n'
        m3u8 += f'#EXT-X-SERVER-CONTROL:CAN-BLOCK-RELOAD=YES,PART-HOLD-BACK={(self.part_target * 3):.06f}\n'
        m3u8 += f'#EXT-X-MEDIA-SEQUENCE:{self.media_sequence}\n'

        if self.hasInit:
            m3u8 += f'#EXT-X-MAP:URI="{self.prefix}init"\n'

        for seg_index, segment in enumerate(self.segments):
            msn = self.media_sequence + seg_index
            m3u8 += f'\n'
            m3u8 += f'#EXT-X-PROGRAM-DATE-TIME:{segment.program_date_time.isoformat()}\n'
            for part_index, partial in enumerate(segment):
                hasIFrame = ',INDEPENDENT=YES' if partial.hasIFrame else ''
                if not partial.isCompleted():
                    m3u8 += f'#EXT-X-PRELOAD-HINT:TYPE=PART,URI="{self.prefix}part?msn={msn}&part={part_index}"{hasIFrame}\n'
                else:
                    m3u8 += f'#EXT-X-PART:DURATION={cast(timedelta, partial.extinf()).total_seconds():.06f},URI="{self.prefix}part?msn={msn}&part={part_index}"{hasIFrame}\n'

            if segment.isCompleted():
                m3u8 += f'#EXTINF:{cast(timedelta, segment.extinf()).total_seconds():.06f}\n'
                m3u8 += f'{self.prefix}segment?msn={msn}\n'

        return m3u8
