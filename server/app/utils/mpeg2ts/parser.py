
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from collections import deque
from typing import cast

from app.utils.mpeg2ts import ts
from app.utils.mpeg2ts.pes import PES
from app.utils.mpeg2ts.pes import H264PES
from app.utils.mpeg2ts.pes import H265PES
from app.utils.mpeg2ts.section import Section
from app.utils.mpeg2ts.pat import PATSection
from app.utils.mpeg2ts.pmt import PMTSection


class SectionParser:

    def __init__(self, _class = Section) -> None:
        self.section = None
        self.queue = deque()
        self._class = _class

    def __iter__(self):
        return self

    def __next__(self) -> Section | PATSection | PMTSection:
        if not self.queue:
            raise StopIteration()
        return self.queue.popleft()

    def push(self, packet: bytes) -> None:
        begin = ts.HEADER_SIZE + (1 + ts.adaptation_field_length(packet) if ts.has_adaptation_field(packet) else 0)
        if ts.payload_unit_start_indicator(packet): begin += 1

        if not self.section:
            if ts.payload_unit_start_indicator(packet):
                begin += ts.pointer_field(packet)
            else:
                return

        if ts.payload_unit_start_indicator(packet):
            while begin < ts.PACKET_SIZE:
                if packet[begin] == ts.STUFFING_BYTE[0]: break
                if self.section:
                    # TODO: self.section.count() で正しく動くのか不明
                    next = min(begin + self.section.count(packet), ts.PACKET_SIZE)
                else:
                    section_length = ((packet[begin + 1] & 0x0F) << 8) | packet[begin + 2]
                    next = min(begin + (3 + section_length), ts.PACKET_SIZE)
                    self.section = bytearray()
                self.section += packet[begin:next]

                section_length = ((self.section[1] & 0x0F) << 8) | self.section[2]
                if len(self.section) == section_length + 3:
                    self.queue.append(self._class(self.section))
                    self.section = None
                elif len(self.section) > section_length + 3:
                    self.section = None

                begin = next
        else:
            self.section = cast(bytearray, self.section)
            section_length = ((self.section[1] & 0x0F) << 8) | self.section[2]
            remains = max(0, section_length + 3 - len(self.section))

            next = min(begin + remains, ts.PACKET_SIZE)
            self.section += packet[begin:next]

            if len(self.section) == section_length + 3:
                self.queue.append(self._class(self.section))
                self.section = None
            elif len(self.section) > section_length + 3:
                self.section = None


class PESParser:

    def __init__(self, _class = PES) -> None:
        self.pes = None
        self.queue = deque()
        self._class = _class

    def __iter__(self):
        return self

    def __next__(self) -> PES | H264PES | H265PES:
        if not self.queue:
            raise StopIteration()
        return self.queue.popleft()

    def push(self, packet: bytes) -> None:
        begin = ts.HEADER_SIZE + (1 + ts.adaptation_field_length(packet) if ts.has_adaptation_field(packet) else 0)
        if not ts.payload_unit_start_indicator(packet) and not self.pes: return

        if ts.payload_unit_start_indicator(packet):
            if self.pes and ((self.pes[4] << 8) | self.pes[5]) == 0:
                self.queue.append(self._class(self.pes))

            pes_length = (packet[begin + 4] << 8) | packet[begin + 5]
            if pes_length == 0:
                next = ts.PACKET_SIZE
            else:
                next = min(begin + (PES.HEADER_SIZE + pes_length), ts.PACKET_SIZE)
            self.pes = bytearray(packet[begin:next])
        elif self.pes:
            pes_length = (self.pes[4] << 8) | self.pes[5]
            if pes_length == 0:
                next = ts.PACKET_SIZE
            else:
                next = min(begin + (PES.HEADER_SIZE + pes_length) - len(self.pes), ts.PACKET_SIZE)
            self.pes += packet[begin:next]

        self.pes = cast(bytearray, self.pes)
        if ((self.pes[4] << 8) | self.pes[5]) > 0:
            if len(self.pes) == PES.HEADER_SIZE + (self.pes[4] << 8 | self.pes[5]):
                self.queue.append(self._class(self.pes))
                self.pes = None
            elif len(self.pes) > PES.HEADER_SIZE + (self.pes[4] << 8 | self.pes[5]):
                self.pes = None
