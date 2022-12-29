
"""
https://github.com/monyone/biim の一部を変更して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from typing import Iterator

from mpeg2ts.section import Section


class PATSection(Section):

    def __init__(self, payload: bytes = b'') -> None:
        super().__init__(payload)
        self.entry = [
            ((payload[offset + 0] << 8) | payload[offset + 1], ((payload[offset + 2] & 0x1F) << 8) | payload[offset + 3])
            for offset in range(Section.EXTENDED_HEADER_SIZE, 3 + self.section_length() - Section.CRC_SIZE, 4)
        ]

    def __iter__(self) -> Iterator[tuple[int, int]]:
        return iter(self.entry)
