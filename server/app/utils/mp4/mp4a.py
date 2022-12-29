
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from app.utils.mp4.box import trak, tkhd, mdia, mdhd, hdlr, minf, smhd, dinf, stbl, stsd, mp4a


def mp4aTrack(trackId: int, timescale: int, config: bytes, channelCount: int, sampleRate: int) -> bytes:
    return trak(
        tkhd(trackId, 0, 0),
        mdia(
            mdhd(timescale),
            hdlr('soun', 'SoundHandler'),
            minf(
                smhd(),
                dinf(),
                stbl(
                    stsd(
                        mp4a(config, channelCount, sampleRate)
                    )
                )
            )
        )
    )
