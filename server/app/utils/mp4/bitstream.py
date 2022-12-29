
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from collections import deque


class BitStream:

    def __init__(self, data: bytes) -> None:
        self.bits: deque[int] = deque()
        self.data: deque[int] = deque(data)

    def __bool__(self) -> bool:
        return bool(self.bits or self.data)

    def __len__(self) -> int:
        return len(self.data) * 8 + len(self.bits)

    def __fill_bits(self) -> None:
        if not self.data:
            return
        byte = self.data.popleft()
        for index in range(8):
            bit_index = (8 - 1) - index
            self.bits.append(1 if (byte & (1 << bit_index)) != 0 else 0)

    def __peekBit(self) -> int:
        if not self.bits:
            self.__fill_bits()
        return self.bits[0]

    def __count_trailing_zeros(self) -> int:
        result = 0
        while self.__peekBit() == 0:
            self.readBits(1)
            result += 1
        return result

    def readBits(self, size: int) -> int:
        result = 0
        remain_bits_len = min(len(self.bits), size)
        for _ in range(remain_bits_len):
            result *= 2
            result += self.bits.popleft()
            size -= 1

        while size >= 8 and self.data:
            byte = self.data.popleft()
            result *= 256
            result += byte
            size -= 8
        if size == 0:
            return result

        self.__fill_bits()
        remain_bits_len = min(len(self.bits), size)
        for _ in range(remain_bits_len):
            result *= 2
            result += self.bits.popleft()
            size -= 1
        return result

    def readBool(self) -> bool:
        return self.readBits(1) == 1

    def readByte(self, size: int = 1) -> int:
        return self.readBits(size * 8)

    def readBitStreamFromBytes(self, size: int) -> 'BitStream':
        return BitStream(bytes([
            self.readByte(1) for _ in range(size)
        ]))

    def readUEG(self) -> int:
        count = self.__count_trailing_zeros()
        return self.readBits(count + 1) - 1

    def readSEG(self) -> int:
        ueg = self.readUEG()
        if ueg % 2 == 1:
            return ueg
        else:
            return -1 * (ueg >> 1)

    def retainByte(self, byte: int):
        for i in range(8):
            self.bits.appendleft(1 if byte & (1 << i) != 0 else 0)
