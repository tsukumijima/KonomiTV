
"""
https://github.com/monyone/biim の一部を変更して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

import re
from typing import Any, Iterator


SPLIT = re.compile('\0\0\0?\1'.encode('ascii'))

class PES:

    HEADER_SIZE = 6

    def __init__(self, payload: bytes = b''):
        self.payload = memoryview(payload)

    def __getitem__(self, item: Any) -> int:
        return self.payload[item]

    def __len__(self) -> int:
        return len(self.payload)

    def packet_start_code_prefix(self) -> int:
        return (self.payload[0] << 16) | (self.payload[1] << 8) | self.payload[2]

    def stream_id(self) -> int:
        return self.payload[3]

    def PES_packet_length(self) -> int:
        return (self.payload[4] << 8) | self.payload[5]

    def has_optional_pes_header(self) -> bool:
        if self.stream_id() in [0b10111100, 0b10111111, 0b11110000, 0b11110001, 0b11110010, 0b11111000, 0b11111111]:
            return False
        elif self.stream_id() in [0b10111110]:
            return False
        else:
            return True

    def has_pts(self) -> bool:
        if self.has_optional_pes_header():
            return (self.payload[PES.HEADER_SIZE + 1] & 0x80) != 0
        else:
            return False

    def has_dts(self) -> bool:
        if self.has_optional_pes_header():
            return (self.payload[PES.HEADER_SIZE + 1] & 0x40) != 0
        else:
            return False

    def pes_header_length(self) -> int | None:
        if self.has_optional_pes_header():
            return (self.payload[PES.HEADER_SIZE + 2])
        else:
            return None

    def pts(self) -> int | None:
        if not self.has_pts(): return None

        pts = 0
        pts <<= 3; pts |= ((self.payload[PES.HEADER_SIZE + 3 + 0] & 0x0E) >> 1)
        pts <<= 8; pts |= ((self.payload[PES.HEADER_SIZE + 3 + 1] & 0xFF) >> 0)
        pts <<= 7; pts |= ((self.payload[PES.HEADER_SIZE + 3 + 2] & 0xFE) >> 1)
        pts <<= 8; pts |= ((self.payload[PES.HEADER_SIZE + 3 + 3] & 0xFF) >> 0)
        pts <<= 7; pts |= ((self.payload[PES.HEADER_SIZE + 3 + 4] & 0xFE) >> 1)
        return pts

    def dts(self) -> int | None:
        if not self.has_dts(): return None

        dts = 0
        if self.has_pts():
            dts <<= 3; dts |= ((self.payload[PES.HEADER_SIZE + 8 + 0] & 0x0E) >> 1)
            dts <<= 8; dts |= ((self.payload[PES.HEADER_SIZE + 8 + 1] & 0xFF) >> 0)
            dts <<= 7; dts |= ((self.payload[PES.HEADER_SIZE + 8 + 2] & 0xFE) >> 1)
            dts <<= 8; dts |= ((self.payload[PES.HEADER_SIZE + 8 + 3] & 0xFF) >> 0)
            dts <<= 7; dts |= ((self.payload[PES.HEADER_SIZE + 8 + 4] & 0xFE) >> 1)
        else:
            dts <<= 3; dts |= ((self.payload[PES.HEADER_SIZE + 3 + 0] & 0x0E) >> 1)
            dts <<= 8; dts |= ((self.payload[PES.HEADER_SIZE + 3 + 1] & 0xFF) >> 0)
            dts <<= 7; dts |= ((self.payload[PES.HEADER_SIZE + 3 + 2] & 0xFE) >> 1)
            dts <<= 8; dts |= ((self.payload[PES.HEADER_SIZE + 3 + 3] & 0xFF) >> 0)
            dts <<= 7; dts |= ((self.payload[PES.HEADER_SIZE + 3 + 4] & 0xFE) >> 1)

        return dts

    def PES_packet_data(self) -> bytes:
        if self.has_optional_pes_header():
            return self.payload[PES.HEADER_SIZE + 3 + self.payload[PES.HEADER_SIZE + 2]:]
        else:
            return self.payload[PES.HEADER_SIZE:]


class H264PES(PES):

    def __init__(self, payload: bytes = b'') -> None:
        super().__init__(payload)
        PES_packet_data = self.PES_packet_data()
        self.ebsps = [x for x in re.split(SPLIT, PES_packet_data) if len(x) > 0]

    def __iter__(self) -> Iterator[bytes]:
        return iter(self.ebsps)


class H265PES(PES):

    def __init__(self, payload: bytes = b'') -> None:
        super().__init__(payload)
        PES_packet_data = self.PES_packet_data()
        self.ebsps = [x for x in re.split(SPLIT, PES_packet_data) if len(x) > 0]

    def __iter__(self) -> Iterator[bytes]:
        return iter(self.ebsps)
