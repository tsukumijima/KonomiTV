
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from typing import Iterator

from app.utils.mpeg2ts.section import Section


class PMTSection(Section):

    def __init__(self, payload: bytes = b'') -> None:
        super().__init__(payload)
        self.PCR_PID = ((self.payload[Section.EXTENDED_HEADER_SIZE + 0] & 0x1F) << 8) | self.payload[Section.EXTENDED_HEADER_SIZE + 1]
        self.entry: list[tuple[int, int]] = []

        program_info_length = ((self.payload[Section.EXTENDED_HEADER_SIZE + 2] & 0x0F) << 8) | self.payload[Section.EXTENDED_HEADER_SIZE + 3]
        begin = Section.EXTENDED_HEADER_SIZE + 4 + program_info_length
        while begin < 3 + self.section_length() - Section.CRC_SIZE:
            stream_type = self.payload[begin + 0]
            elementary_PID = ((self.payload[begin + 1] & 0x1F) << 8) | self.payload[begin + 2]
            ES_info_length = ((self.payload[begin + 3] & 0x0F) << 8) | self.payload[begin + 4]

            self.entry.append((stream_type, elementary_PID))
            begin += 5 + ES_info_length

    def __iter__(self) -> Iterator[tuple[int, int]]:
        return iter(self.entry)
