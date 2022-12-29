
"""
https://github.com/monyone/biim の一部を改変して利用しています。

Copyright (c) 2022 もにょ～ん
Released under the MIT license
https://opensource.org/licenses/MIT
"""

from typing import cast

from app.utils.mp4.bitstream import BitStream
from app.utils.mp4.box import trak, tkhd, mdia, mdhd, hdlr, minf, vmhd, dinf, stbl, stsd, hvc1


escapes = set([0x00, 0x01, 0x02, 0x03])

def ebsp2rbsp(data: bytes) -> bytes:
    rbsp = bytearray(data[:2])
    length = len(data)
    for index in range(2, length):
        if index < length - 1 and data[index - 2] == 0x00 and data[index - 1] == 0x00 and data[index + 0] == 0x03 and data[index + 1] in escapes:
            continue
        rbsp.append(data[index])
    return bytes(rbsp)

def hevcTrack(trackId: int, timescale: int, vps: bytes, sps: bytes, pps: bytes) -> bytes:
    general_profile_space = None
    general_tier_flag = None
    general_profile_idc = None
    general_profile_compatibility_flags = None
    general_constraint_indicator_flags = None
    chroma_format_idc = None
    min_spatial_segmentation_idc = None
    bit_depth_luma_minus8 = None
    bit_depth_chroma_minus8 = None
    constant_frame_rate = 0

    sar_width: int = 1
    sar_height: int = 1
    pic_width_in_luma_samples: int | None = None
    pic_height_in_luma_samples: int | None = None

    def parseSPS() -> None:
        nonlocal general_profile_space
        nonlocal general_tier_flag
        nonlocal general_profile_idc
        nonlocal general_profile_compatibility_flags
        nonlocal general_constraint_indicator_flags
        nonlocal chroma_format_idc
        nonlocal min_spatial_segmentation_idc
        nonlocal bit_depth_luma_minus8
        nonlocal bit_depth_chroma_minus8

        nonlocal pic_width_in_luma_samples
        nonlocal pic_height_in_luma_samples

        left_offset = 0
        right_offset = 0
        top_offset = 0
        bottom_offset = 0

        stream = BitStream(ebsp2rbsp(sps))
        stream.readByte(2) # remove header

        video_paramter_set_id = stream.readBits(4)
        max_sub_layers_minus1 = stream.readBits(3)
        temporal_id_nesting_flag = stream.readBool()

        general_profile_space = stream.readBits(2)
        general_tier_flag = stream.readBool()
        general_profile_idc = stream.readBits(5)
        general_profile_compatibility_flags = stream.readByte(4).to_bytes(4, byteorder='big')
        general_constraint_indicator_flags = stream.readByte(6).to_bytes(6, byteorder='big')

        general_level_idc = stream.readByte()
        sub_layer_profile_present_flag = []
        sub_layer_level_present_flag = []
        for _ in range(max_sub_layers_minus1):
            sub_layer_profile_present_flag.append(stream.readBool())
            sub_layer_level_present_flag.append(stream.readBool())
        if max_sub_layers_minus1 > 0:
            for _ in range(max_sub_layers_minus1, 8): stream.readBits(2)
        for i in range(max_sub_layers_minus1):
            if sub_layer_profile_present_flag[i]:
                stream.readByte() # sub_layer_profile_space, sub_layer_tier_flag, sub_layer_profile_idc
                stream.readByte(4) # sub_layer_profile_compatibility_flag
                stream.readByte(6)
            if sub_layer_level_present_flag[i]:
                stream.readByte()

        seq_parameter_set_id = stream.readUEG()
        chroma_format_idc = stream.readUEG()
        if chroma_format_idc == 3: stream.readBits(1)
        pic_width_in_luma_samples = stream.readUEG()
        pic_height_in_luma_samples = stream.readUEG()
        conformance_window_flag = stream.readBool()
        if conformance_window_flag:
            left_offset += stream.readUEG()
            right_offset += stream.readUEG()
            top_offset += stream.readUEG()
            bottom_offset += stream.readUEG()
        bit_depth_luma_minus8 = stream.readUEG()
        bit_depth_chroma_minus8 = stream.readUEG()
        log2_max_pic_order_cnt_lsb_minus4 = stream.readUEG()
        sub_layer_ordering_info_present_flag = stream.readBool()
        for _ in range(0 if sub_layer_ordering_info_present_flag else max_sub_layers_minus1, max_sub_layers_minus1 + 1):
            stream.readUEG() # max_dec_pic_buffering_minus1[i]
            stream.readUEG() # max_num_reorder_pics[i]
            stream.readUEG() # max_latency_increase_plus1[i]
        log2_min_luma_coding_block_size_minus3 = stream.readUEG()
        log2_diff_max_min_luma_coding_block_size = stream.readUEG()
        log2_min_transform_block_size_minus2 = stream.readUEG()
        log2_diff_max_min_transform_block_size = stream.readUEG()
        max_transform_hierarchy_depth_inter = stream.readUEG()
        max_transform_hierarchy_depth_intra = stream.readUEG()
        scaling_list_enabled_flag = stream.readBool()
        if scaling_list_enabled_flag:
            sps_scaling_list_data_present_flag = stream.readBool()
            if sps_scaling_list_data_present_flag:
                for sizeId in range(0, 4):
                    for matrixId in range(0, 2 if sizeId == 3 else 6):
                        scaling_list_pred_mode_flag = stream.readBool()
                        if not scaling_list_pred_mode_flag:
                            stream.readUEG() # scaling_list_pred_matrix_id_delta
                        else:
                            coefNum = min(64, (1 << (4 + (sizeId << 1))))
                            if sizeId > 1: stream.readSEG()
                            for _ in range(coefNum): stream.readSEG()
        amp_enabled_flag = stream.readBool()
        sample_adaptive_offset_enabled_flag = stream.readBool()
        pcm_enabled_flag = stream.readBool()
        if pcm_enabled_flag:
                stream.readByte()
                stream.readUEG()
                stream.readUEG()
                stream.readBool()
        num_short_term_ref_pic_sets = stream.readUEG()
        num_delta_pocs = 0
        for i in range(num_short_term_ref_pic_sets):
            inter_ref_pic_set_prediction_flag = False
            if i != 0: inter_ref_pic_set_prediction_flag = stream.readBool()
            if inter_ref_pic_set_prediction_flag:
                if i == num_short_term_ref_pic_sets: stream.readUEG()
                stream.readBool()
                stream.readUEG()
                next_num_delta_pocs = 0
                for _ in range(0, num_delta_pocs + 1):
                    used_by_curr_pic_flag = stream.readBool()
                    use_delta_flag = False
                    if not used_by_curr_pic_flag: use_delta_flag = stream.readBool()
                    if used_by_curr_pic_flag or use_delta_flag: next_num_delta_pocs += 1
                num_delta_pocs = next_num_delta_pocs
            else:
                num_negative_pics = stream.readUEG()
                num_positive_pics = stream.readUEG()
                num_delta_pocs = num_negative_pics + num_positive_pics
                for _ in range(num_negative_pics):
                    stream.readUEG()
                    stream.readBool()
                for _ in range(num_positive_pics):
                    stream.readUEG()
                    stream.readBool()
        long_term_ref_pics_present_flag = stream.readBool()
        if long_term_ref_pics_present_flag:
            num_long_term_ref_pics_sps = stream.readUEG()
            for i in range(num_long_term_ref_pics_sps):
                for j in range(log2_max_pic_order_cnt_lsb_minus4 + 4): stream.readBits(1)
                stream.readBits(1)

        default_display_window_flag = False
        min_spatial_segmentation_idc = 0
        nonlocal sar_width
        nonlocal sar_height
        fps_fixed = False
        fps_den = 1
        fps_num = 1

        sps_temporal_mvp_enabled_flag = stream.readBool()
        strong_intra_smoothing_enabled_flag = stream.readBool()
        vui_parameters_present_flag = stream.readBool()
        if vui_parameters_present_flag:
            aspect_ratio_info_present_flag = stream.readBool()
            if aspect_ratio_info_present_flag:
                aspect_ratio_idc = stream.readByte()
                sar_w_table = [1, 12, 10, 16, 40, 24, 20, 32, 80, 18, 15, 64, 160, 4, 3, 2]
                sar_h_table = [1, 11, 11, 11, 33, 11, 11, 11, 33, 11, 11, 33,  99, 3, 2, 1]
                if aspect_ratio_idc > 0 and aspect_ratio_idc < 16:
                    sar_width = sar_w_table[aspect_ratio_idc - 1]
                    sar_height = sar_h_table[aspect_ratio_idc - 1]
                elif aspect_ratio_idc == 255:
                    sar_width = stream.readBits(16)
                    sar_height = stream.readBits(16)
            overscan_info_present_flag = stream.readBool()
            if overscan_info_present_flag: stream.readBool()
            video_signal_type_present_flag = stream.readBool()
            if video_signal_type_present_flag:
                stream.readBits(3)
                stream.readBool()
                colour_description_present_flag = stream.readBool()
                if colour_description_present_flag:
                    stream.readByte()
                    stream.readByte()
                    stream.readByte()
            chroma_loc_info_present_flag = stream.readBool()
            if chroma_loc_info_present_flag:
                stream.readUEG()
                stream.readUEG()
            neutral_chroma_indication_flag = stream.readBool()
            field_seq_flag = stream.readBool()
            frame_field_info_present_flag = stream.readBool()
            default_display_window_flag = stream.readBool()
            if default_display_window_flag:
                left_offset += stream.readUEG()
                right_offset += stream.readUEG()
                top_offset += stream.readUEG()
                bottom_offset += stream.readUEG()
            vui_timing_info_present_flag = stream.readBool()
            if vui_timing_info_present_flag:
                fps_den = stream.readByte(4)
                fps_num = stream.readByte(4)
                vui_poc_proportional_to_timing_flag = stream.readBool()
                if vui_poc_proportional_to_timing_flag:
                    stream.readUEG()
                    vui_hrd_parameters_present_flag = stream.readBool()
                    if vui_hrd_parameters_present_flag:
                        commonInfPresentFlag = 1
                        nal_hrd_parameters_present_flag = False
                        vcl_hrd_parameters_present_flag = False
                        sub_pic_hrd_params_present_flag = False
                        if commonInfPresentFlag:
                            nal_hrd_parameters_present_flag = stream.readBool()
                            vcl_hrd_parameters_present_flag = stream.readBool()
                            if nal_hrd_parameters_present_flag or vcl_hrd_parameters_present_flag:
                                sub_pic_hrd_params_present_flag = stream.readBool()
                                if sub_pic_hrd_params_present_flag:
                                    stream.readByte()
                                    stream.readBits(5)
                                    stream.readBool()
                                    stream.readBits(5)
                                bit_rate_scale = stream.readBits(4)
                                cpb_size_scale = stream.readBits(4)
                                if sub_pic_hrd_params_present_flag: stream.readBits(4)
                                stream.readBits(5)
                                stream.readBits(5)
                                stream.readBits(5)
                        for i in range(max_sub_layers_minus1 + 1):
                            fixed_pic_rate_general_flag = stream.readBool()
                            fps_fixed = fixed_pic_rate_general_flag
                            fixed_pic_rate_within_cvs_flag = False
                            cpbCnt = 1
                            if not fixed_pic_rate_general_flag:
                                fixed_pic_rate_within_cvs_flag = stream.readBool()
                            low_delay_hrd_flag = False
                            if fixed_pic_rate_within_cvs_flag: stream.readSEG()
                            else:
                                low_delay_hrd_flag = stream.readBool()
                            if not low_delay_hrd_flag: cpbcnt = stream.readUEG() + 1
                            if nal_hrd_parameters_present_flag:
                                for j in range(0, cpbCnt):
                                    stream.readUEG()
                                    stream.readUEG()
                                    if sub_pic_hrd_params_present_flag:
                                        stream.readUEG()
                                        stream.readUEG()
                            if vcl_hrd_parameters_present_flag:
                                for j in range(0, cpbCnt):
                                    stream.readUEG()
                                    stream.readUEG()
                                    if sub_pic_hrd_params_present_flag:
                                        stream.readUEG()
                                        stream.readUEG()
            bitstream_restriction_flag = stream.readBool()
            if bitstream_restriction_flag:
                tiles_fixed_structure_flag = stream.readBool()
                motion_vectors_over_pic_boundaries_flag = stream.readBool()
                restricted_ref_pic_lists_flag = stream.readBool()
                min_spatial_segmentation_idc = stream.readUEG()
                max_bytes_per_pic_denom = stream.readUEG()
                max_bits_per_min_cu_denom = stream.readUEG()
                log2_max_mv_length_horizontal = stream.readUEG()
                log2_max_mv_length_vertical = stream.readUEG()
    parseSPS()

    temporal_id_nesting_flag = False
    num_temporal_layers = 1
    def parseVPS():
        nonlocal num_temporal_layers
        nonlocal temporal_id_nesting_flag
        stream = BitStream(ebsp2rbsp(vps))
        stream.readByte(2) # remove header

        video_parameter_set_id = stream.readBits(4)
        stream.readBits(2)
        max_layers_minus1 = stream.readBits(6)
        max_sub_layers_minus1 = stream.readBits(3)
        num_temporal_layers = max_sub_layers_minus1 + 1
        temporal_id_nesting_flag = stream.readBool()
    parseVPS()

    parallelismType = 1
    def parsePPS():
        nonlocal parallelismType
        stream = BitStream(ebsp2rbsp(pps))
        stream.readByte(2)

        pic_parameter_set_id = stream.readUEG()
        seq_parameter_set_id = stream.readUEG()
        dependent_slice_segments_enabled_flag = stream.readBool()
        output_flag_present_flag = stream.readBool()
        num_extra_slice_header_bits = stream.readBits(3)
        sign_data_hiding_enabled_flag = stream.readBool()
        cabac_init_present_flag = stream.readBool()
        num_ref_idx_l0_default_active_minus1 = stream.readUEG()
        num_ref_idx_l1_default_active_minus1 = stream.readUEG()
        init_qp_minus26 = stream.readSEG()
        constrained_intra_pred_flag = stream.readBool()
        transform_skip_enabled_flag = stream.readBool()
        cu_qp_delta_enabled_flag = stream.readBool()
        if cu_qp_delta_enabled_flag:
            diff_cu_qp_delta_depth = stream.readUEG()
        cb_qp_offset = stream.readSEG()
        cr_qp_offset = stream.readSEG()
        pps_slice_chroma_qp_offsets_present_flag = stream.readBool()
        weighted_pred_flag = stream.readBool()
        weighted_bipred_flag = stream.readBool()
        transquant_bypass_enabled_flag = stream.readBool()
        tiles_enabled_flag = stream.readBool()
        entropy_coding_sync_enabled_flag = stream.readBool()

        parallelismType = 1 # slice-based parallel decoding
        if entropy_coding_sync_enabled_flag and tiles_enabled_flag:
            parallelismType = 0 # mixed-type parallel decoding
        elif entropy_coding_sync_enabled_flag:
            parallelismType = 3 # wavefront-based parallel decoding
        elif tiles_enabled_flag:
            parallelismType = 2 # tile-based parallel decoding
    parsePPS()

    hvcC = b''.join([
        bytes([
            0x01,
            ((cast(int, general_profile_space) & 0x03) << 6) | ((1 if general_tier_flag else 0) << 5) | ((cast(int, general_profile_idc) & 0x1F)),
        ]),
        cast(bytes, general_profile_compatibility_flags),
        cast(bytes, general_constraint_indicator_flags),
        bytes([
            0x3C,
            0xF0 | ((cast(int, min_spatial_segmentation_idc) & 0x0F00) >> 8),
            ((cast(int, min_spatial_segmentation_idc) & 0x00FF) >> 0),
            0xFC | (parallelismType & 0x03),
            0xFC | (cast(int, chroma_format_idc) & 0x03),
            0xF8 | (cast(int, bit_depth_luma_minus8) & 0x07),
            0xF8 | (cast(int, bit_depth_chroma_minus8) & 0x07),
            0x00,
            0x00,
            ((constant_frame_rate & 0x03) << 6) | ((num_temporal_layers & 0x07) << 3) | ((1 if temporal_id_nesting_flag else 0) << 2) | 3,
            0x03,
        ]),
        bytes([
            0x80 | 32,
            0x00, 0x01,
            ((len(vps) & 0xFF00) >> 8),
            ((len(vps) & 0x00FF) >> 0),
        ]),
        vps,
        bytes([
            0x80 | 33,
            0x00, 0x01,
            ((len(sps) & 0xFF00) >> 8),
            ((len(sps) & 0x00FF) >> 0),
        ]),
        sps,
        bytes([
            0x80 | 34,
            0x00, 0x01,
            ((len(pps) & 0xFF00) >> 8),
            ((len(pps) & 0x00FF) >> 0),
        ]),
        pps,
    ])

    return trak(
        tkhd(trackId, (cast(int, pic_width_in_luma_samples) * sar_width + (sar_height - 1)) // sar_height, cast(int, pic_height_in_luma_samples)),
        mdia(
            mdhd(timescale),
            hdlr('vide', 'VideoHandler'),
            minf(
                vmhd(),
                dinf(),
                stbl(
                    stsd(
                        hvc1(hvcC, cast(int, pic_width_in_luma_samples), cast(int, pic_height_in_luma_samples))
                    )
                )
            )
        )
    )
