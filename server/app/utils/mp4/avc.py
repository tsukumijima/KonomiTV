
"""
https://github.com/monyone/biim の一部を変更して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from typing import cast

from mp4.bitstream import BitStream
from mp4.box import trak, tkhd, mdia, mdhd, hdlr, minf, vmhd, dinf, stbl, stsd, avc1


escapes = set([0x00, 0x01, 0x02, 0x03])

def ebsp2rbsp(data: bytes) -> bytes:
    rbsp = bytearray(data[:2])
    length = len(data)
    for index in range(2, length):
        if index < length - 1 and data[index - 2] == 0x00 and data[index - 1] == 0x00 and data[index + 0] == 0x03 and data[index + 1] in escapes:
            continue
        rbsp.append(data[index])
    return bytes(rbsp)

def avcTrack(trackId: int, timescale: int, sps: bytes, pps: bytes) -> bytes:
    need_extra_fields = sps[3] not in [66, 77, 88]
    chroma_format_idc: int | None = None
    bit_depth_luma_minus8: int | None = None
    bit_depth_chroma_minus8: int | None = None

    codec_width: int | None = None
    codec_height: int | None = None
    presentation_width: int | None = None
    presentation_height: int | None = None

    def parseSPS() -> None:
        nonlocal chroma_format_idc
        nonlocal bit_depth_luma_minus8
        nonlocal bit_depth_chroma_minus8

        nonlocal codec_width
        nonlocal codec_height
        nonlocal presentation_width
        nonlocal presentation_height

        stream = BitStream(ebsp2rbsp(sps))
        stream.readByte() # remove header

        profile_idc = stream.readByte()
        stream.readByte()
        level_idc = stream.readByte()
        stream.readUEG()

        chroma_format_idc = 1
        chroma_format = 420
        chroma_format_table = [0, 420, 422, 444]
        bit_depth_luma_minus8 = 0
        bit_depth_chroma_minus8 = 0
        if profile_idc in [100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 144]:
            chroma_format_idc = stream.readUEG()
            if chroma_format_idc == 3:
                stream.readBits(1)

            bit_depth_luma_minus8 = stream.readUEG()
            bit_depth_chroma_minus8 = stream.readUEG()
            stream.readBits(1)
            if stream.readBool():
                scaling_list_count = 8 if chroma_format_idc != 3 else 12
                for i in range(scaling_list_count):
                    if stream.readBool():
                        count = 16 if i < 6 else 64
                        last_scale, next_scale = 8, 8
                        delta_scale = 0
                        for _ in range(count):
                            if next_scale != 0:
                                delta_scale = stream.readSEG()
                                next_scale = (last_scale + delta_scale + 256) % 256
                            last_scale = last_scale if next_scale == 0 else next_scale

        stream.readUEG()
        pic_order_cnt_type = stream.readUEG()
        if pic_order_cnt_type == 0:
            stream.readUEG()
        elif pic_order_cnt_type == 1:
            stream.readBits(1)
            stream.readSEG()
            stream.readSEG()
            num_ref_frames_in_pic_order_cnt_cycle = stream.readUEG()
            for _ in range(num_ref_frames_in_pic_order_cnt_cycle): stream.readSEG()
        ref_frames = stream.readUEG()
        stream.readBits(1)

        pic_width_in_mbs_minus1 = stream.readUEG()
        pic_height_in_map_units_minus1 = stream.readUEG()

        frame_mbs_only_flag = stream.readBool()
        if frame_mbs_only_flag == 0: stream.readBits(1)
        stream.readBool()

        frame_crop_left_offset = 0
        frame_crop_right_offset = 0
        frame_crop_top_offset = 0
        frame_crop_bottom_offset = 0
        frame_cropping_flag = stream.readBool()
        if frame_cropping_flag:
            frame_crop_left_offset = stream.readUEG()
            frame_crop_right_offset = stream.readUEG()
            frame_crop_top_offset = stream.readUEG()
            frame_crop_bottom_offset = stream.readUEG()

        sar_width, sar_height = 1, 1
        fps, fps_fixed, fps_num, fps_den = 0, True, 0, 0

        vui_parameters_present_flag = stream.readBool()
        if vui_parameters_present_flag:
            if stream.readBool():
                aspect_ratio_idc = stream.readByte()
                sar_w_table = [1, 12, 10, 16, 40, 24, 20, 32, 80, 18, 15, 64, 160, 4, 3, 2]
                sar_h_table = [1, 11, 11, 11, 33, 11, 11, 11, 33, 11, 11, 33,  99, 3, 2, 1]

                if aspect_ratio_idc > 0 and aspect_ratio_idc < 16:
                    sar_width = sar_w_table[aspect_ratio_idc - 1]
                    sar_height = sar_h_table[aspect_ratio_idc - 1]
                elif aspect_ratio_idc == 255:
                    sar_width = stream.readByte() << 8 | stream.readByte()
                    sar_height = stream.readByte() << 8 | stream.readByte()

            if stream.readBool():
                stream.readBool()

            if stream.readBool():
                stream.readBits(4)
                if stream.readBool():
                    stream.readBits(24)

            if stream.readBool():
                stream.readUEG()
                stream.readUEG()

            if stream.readBool():
                num_units_in_tick = stream.readBits(32)
                time_scale = stream.readBits(32)
                fps_fixed = stream.readBool()

                fps_num = time_scale
                fps_den = num_units_in_tick * 2
                fps = fps_num / fps_den

        crop_unit_x, crop_unit_y = 0, 0
        if chroma_format_idc == 0:
            crop_unit_x = 1
            crop_unit_y = 2 - frame_mbs_only_flag
        else:
            sub_wc = 1 if chroma_format_idc == 3 else 2
            sub_hc = 2 if chroma_format_idc == 1 else 1
            crop_unit_x = sub_wc
            crop_unit_y = sub_hc * (2 - frame_mbs_only_flag)

        codec_width = (pic_width_in_mbs_minus1 + 1) * 16
        codec_height = (2 - frame_mbs_only_flag) * ((pic_height_in_map_units_minus1 + 1) * 16)
        codec_width -= (frame_crop_left_offset + frame_crop_right_offset) * crop_unit_x
        codec_height -= (frame_crop_top_offset + frame_crop_bottom_offset) * crop_unit_y

        presentation_width = (codec_width * sar_width + (sar_height - 1)) // sar_height
        presentation_height = codec_height
    parseSPS()

    avcC = b''.join([
        bytes([
            0x01, # configurationVersion
            sps[1], # AVCProfileIndication
            sps[2], # profile_compatibility
            sps[3], # AVCLevelIndication
            0xFF, # 111111 + lengthSizeMinusOne(3)
        ]),
        bytes([
            0xE0 | 0x01, # 111 + numOfSequenceParameterSets
        ]),
        (len(sps)).to_bytes(2, byteorder='big'),
        sps,
        bytes([
            0x01, # numOfPictureParameterSets
        ]),
        (len(pps)).to_bytes(2, byteorder='big'),
        pps,
        bytes([]) if not need_extra_fields else bytes([
            0xFC | cast(int, chroma_format_idc),
            0xF8 | cast(int, bit_depth_luma_minus8),
            0xF8 | cast(int, bit_depth_chroma_minus8),
            0x00
        ]),
    ])

    return trak(
        tkhd(trackId, cast(int, presentation_width), cast(int, presentation_height)),
        mdia(
            mdhd(timescale),
            hdlr('vide', 'VideoHandler'),
            minf(
                vmhd(),
                dinf(),
                stbl(
                    stsd(
                        avc1(avcC, cast(int, codec_width), cast(int, codec_height))
                    )
                )
            )
        )
    )
