from __future__ import annotations

import bisect
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from biim.mpeg2ts import ts


@dataclass(slots=True)
class _MP4Box:
    """
    MP4 box の位置とサイズを保持するデータクラス

    Args:
        type (bytes): box type
        offset (int): box header の開始位置
        size (int): header を含む box 全体サイズ
        header_size (int): header サイズ (通常 8、largesize 使用時 16)
    """

    type: bytes
    offset: int
    size: int
    header_size: int


@dataclass(slots=True)
class _MP4TrackInfo:
    """
    MP4 の映像トラックから同期サンプル DTS を復元するための情報

    Args:
        handler_type (bytes | None): hdlr の handler_type
        timescale (int | None): mdhd の media timescale
        stts_entries (list[tuple[int, int]]): decode time to sample table
        stss_samples (list[int]): sync sample number 一覧
    """

    handler_type: bytes | None
    timescale: int | None
    stts_entries: list[tuple[int, int]]
    stss_samples: list[int]


class MP4KeyFrameParser:
    """
    MP4 コンテナの moov 内テーブルを読むためのユーティリティ
    """


    @staticmethod
    def readVideoKeyframeDTS(path: Path) -> list[int]:
        """
        MP4 の moov 内テーブルだけを読んで、映像同期サンプルの DTS を 90kHz 単位で返す

        Args:
            path (Path): MPEG-4 コンテナの録画ファイルパス

        Returns:
            list[int]: 先頭同期サンプルを 0 とした 90kHz DTS 一覧
        """

        file_size = path.stat().st_size
        with path.open('rb') as file:
            moov_box: _MP4Box | None = None
            for top_level_box in MP4KeyFrameParser.__iterMP4Boxes(file, 0, file_size):
                if top_level_box.type == b'moov':
                    moov_box = top_level_box
                    break
            if moov_box is None:
                raise RuntimeError(f'moov box was not found: {path}')

            # moov 直下の trak を順に調べ、映像トラックだけを DTS 生成対象にする
            for track_box in MP4KeyFrameParser.__iterMP4Boxes(
                file,
                moov_box.offset + moov_box.header_size,
                moov_box.offset + moov_box.size,
            ):
                if track_box.type != b'trak':
                    continue
                track_info = MP4KeyFrameParser.__parseMP4Track(file, track_box)
                if track_info.handler_type != b'vide':
                    continue
                if track_info.timescale is None:
                    raise RuntimeError(f'video mdhd timescale was not found: {path}')
                if len(track_info.stts_entries) == 0:
                    raise RuntimeError(f'video stts was not found: {path}')

                # stss がない映像トラックは、MP4 仕様上すべてのサンプルを同期サンプルとして扱う
                sync_samples: list[int] | range
                if len(track_info.stss_samples) > 0:
                    sync_samples = track_info.stss_samples
                else:
                    total_sample_count = sum(entry[0] for entry in track_info.stts_entries)
                    sync_samples = range(1, total_sample_count + 1)

                sync_sample_index = 0
                sample_number = 1
                sample_dts = 0
                keyframe_dts_list: list[int] = []
                for sample_count, sample_delta in track_info.stts_entries:
                    # stts は同じ時間差のサンプルをまとめて持つため、現在のまとまりに含まれる最終サンプル番号を計算する
                    entry_last_sample = sample_number + sample_count - 1
                    while sync_sample_index < len(sync_samples) and sync_samples[sync_sample_index] <= entry_last_sample:
                        # stss の同期サンプル番号を stts の累積 DTS に変換する
                        ## サンプル番号は 1 始まりなので、現在のまとまりの先頭との差分だけ sample_delta を足す
                        sync_sample_number = sync_samples[sync_sample_index]
                        sync_sample_dts = sample_dts + (sync_sample_number - sample_number) * sample_delta
                        keyframe_dts_list.append(sync_sample_dts * ts.HZ // track_info.timescale)
                        sync_sample_index += 1
                    # 次の stts のまとまりの先頭サンプル番号と DTS に進める
                    sample_number += sample_count
                    sample_dts += sample_count * sample_delta

                # psisimux の -m はファイル先頭からの相対ミリ秒指定なので、先頭同期サンプルを 0 に正規化する
                if len(keyframe_dts_list) == 0:
                    return []
                base_dts = keyframe_dts_list[0]
                return [dts - base_dts for dts in keyframe_dts_list]

        raise RuntimeError(f'video trak was not found: {path}')


    @staticmethod
    def findKeyframeDTSBefore(keyframe_dts_list: list[int], playlist_start_seconds: float) -> int:
        """
        MP4 の同期サンプル DTS 一覧から、プレイリスト時刻以前の最も近い開始 DTS を選ぶ

        Args:
            keyframe_dts_list (list[int]): 先頭同期サンプルを 0 とした 90kHz DTS 一覧
            playlist_start_seconds (float): 録画内の相対再生時刻

        Returns:
            int: psisimux に渡す開始 DTS (90kHz)
        """

        if len(keyframe_dts_list) == 0:
            raise RuntimeError('MP4 keyframe DTS list is empty.')

        # MP4 はファイル位置へシークせず、psisimux の -m へ渡す時刻だけを決める
        target_dts = round(playlist_start_seconds * ts.HZ)
        keyframe_index = bisect.bisect_right(keyframe_dts_list, target_dts) - 1
        if keyframe_index < 0:
            keyframe_index = 0
        return keyframe_dts_list[keyframe_index]


    @staticmethod
    def __readUInt32(data: bytes, offset: int) -> int:
        """
        MP4 box 内の 32bit big-endian 整数を読む

        Args:
            data (bytes): 読み取り元データ
            offset (int): 読み取り開始位置

        Returns:
            int: 変換後の整数
        """

        return int.from_bytes(data[offset:offset + 4], 'big')


    @staticmethod
    def __readUInt64(data: bytes, offset: int) -> int:
        """
        MP4 box 内の 64bit big-endian 整数を読む

        Args:
            data (bytes): 読み取り元データ
            offset (int): 読み取り開始位置

        Returns:
            int: 変換後の整数
        """

        return int.from_bytes(data[offset:offset + 8], 'big')


    @staticmethod
    def __readMP4BoxHeader(file: BinaryIO, file_end: int) -> _MP4Box | None:
        """
        現在位置の MP4 box header を読み、payload の範囲を計算する

        Args:
            file (BinaryIO): seek/read/tell を持つバイナリファイル
            file_end (int): 親 box の終端位置

        Returns:
            _MP4Box | None: 読み取った box 情報
        """

        box_offset = file.tell()
        if box_offset + 8 > file_end:
            return None

        header = file.read(8)
        if len(header) != 8:
            return None
        size = MP4KeyFrameParser.__readUInt32(header, 0)
        box_type = header[4:8]
        header_size = 8

        if size == 1:
            extended_size = file.read(8)
            if len(extended_size) != 8:
                return None
            size = MP4KeyFrameParser.__readUInt64(extended_size, 0)
            header_size = 16

        # size 0 は親 box の終端まで続く特殊値なので、呼び出し側から渡された境界で長さを決める
        if size == 0:
            size = file_end - box_offset

        if size < header_size or box_offset + size > file_end:
            return None

        return _MP4Box(type = box_type, offset = box_offset, size = size, header_size = header_size)


    @staticmethod
    def __iterMP4Boxes(file: BinaryIO, start_offset: int, end_offset: int) -> list[_MP4Box]:
        """
        指定範囲の直下にある MP4 box 一覧を読む

        Args:
            file (BinaryIO): seek/read/tell を持つバイナリファイル
            start_offset (int): 読み取り開始位置
            end_offset (int): 読み取り終了位置

        Returns:
            list[_MP4Box]: 直下の box 一覧
        """

        boxes: list[_MP4Box] = []
        file.seek(start_offset)
        while file.tell() + 8 <= end_offset:
            box = MP4KeyFrameParser.__readMP4BoxHeader(file, end_offset)
            if box is None:
                break
            boxes.append(box)
            file.seek(box.offset + box.size)
        return boxes


    @staticmethod
    def __findMP4ChildBox(file: BinaryIO, parent_box: _MP4Box, box_type: bytes) -> _MP4Box | None:
        """
        親 box 直下から指定 type の子 box を探す

        Args:
            file (BinaryIO): seek/read/tell を持つバイナリファイル
            parent_box (_MP4Box): 探索対象の親 box
            box_type (bytes): 探す box type

        Returns:
            _MP4Box | None: 見つかった子 box
        """

        for child_box in MP4KeyFrameParser.__iterMP4Boxes(
            file,
            parent_box.offset + parent_box.header_size,
            parent_box.offset + parent_box.size,
        ):
            if child_box.type == box_type:
                return child_box
        return None


    @staticmethod
    def __readMP4Payload(file: BinaryIO, box: _MP4Box) -> bytes:
        """
        MP4 box の payload を読む

        Args:
            file (BinaryIO): seek/read/tell を持つバイナリファイル
            box (_MP4Box): 読み取り対象 box

        Returns:
            bytes: payload データ
        """

        file.seek(box.offset + box.header_size)
        return file.read(box.size - box.header_size)


    @staticmethod
    def __parseMP4Track(file: BinaryIO, track_box: _MP4Box) -> _MP4TrackInfo:
        """
        MP4 の trak box から映像トラック判定とキーフレーム時刻生成に必要な表を読む

        Args:
            file (BinaryIO): seek/read/tell を持つバイナリファイル
            track_box (_MP4Box): trak box

        Returns:
            _MP4TrackInfo: トラック情報
        """

        handler_type: bytes | None = None
        timescale: int | None = None
        stts_entries: list[tuple[int, int]] = []
        stss_samples: list[int] = []

        # trak の中身は mdia 配下にまとまっているため、mdia がないトラックは空情報として扱う
        mdia_box = MP4KeyFrameParser.__findMP4ChildBox(file, track_box, b'mdia')
        if mdia_box is None:
            return _MP4TrackInfo(handler_type, timescale, stts_entries, stss_samples)

        # hdlr の handler_type で映像トラックかどうかを後段で判定する
        hdlr_box = MP4KeyFrameParser.__findMP4ChildBox(file, mdia_box, b'hdlr')
        if hdlr_box is not None:
            hdlr_payload = MP4KeyFrameParser.__readMP4Payload(file, hdlr_box)
            if len(hdlr_payload) >= 12:
                handler_type = hdlr_payload[8:12]

        # mdhd の timescale は stts の時間単位を 90kHz DTS へ換算するときに使う
        mdhd_box = MP4KeyFrameParser.__findMP4ChildBox(file, mdia_box, b'mdhd')
        if mdhd_box is not None:
            mdhd_payload = MP4KeyFrameParser.__readMP4Payload(file, mdhd_box)
            if len(mdhd_payload) >= 24:
                version = mdhd_payload[0]
                timescale_offset = 20 if version == 1 else 12
                if len(mdhd_payload) >= timescale_offset + 4:
                    timescale = MP4KeyFrameParser.__readUInt32(mdhd_payload, timescale_offset)

        minf_box = MP4KeyFrameParser.__findMP4ChildBox(file, mdia_box, b'minf')
        stbl_box = MP4KeyFrameParser.__findMP4ChildBox(file, minf_box, b'stbl') if minf_box is not None else None
        if stbl_box is None:
            return _MP4TrackInfo(handler_type, timescale, stts_entries, stss_samples)

        # stts はサンプル数と時間差のランレングス表で、全サンプルの DTS を復元する元データになる
        stts_box = MP4KeyFrameParser.__findMP4ChildBox(file, stbl_box, b'stts')
        if stts_box is not None:
            stts_payload = MP4KeyFrameParser.__readMP4Payload(file, stts_box)
            if len(stts_payload) >= 8:
                entry_count = MP4KeyFrameParser.__readUInt32(stts_payload, 4)
                for entry_index in range(entry_count):
                    entry_offset = 8 + entry_index * 8
                    if entry_offset + 8 > len(stts_payload):
                        break
                    sample_count = MP4KeyFrameParser.__readUInt32(stts_payload, entry_offset)
                    sample_delta = MP4KeyFrameParser.__readUInt32(stts_payload, entry_offset + 4)
                    stts_entries.append((sample_count, sample_delta))

        # stss は同期サンプル番号の一覧で、存在しない場合は上位側で全サンプルを同期サンプルとして扱う
        stss_box = MP4KeyFrameParser.__findMP4ChildBox(file, stbl_box, b'stss')
        if stss_box is not None:
            stss_payload = MP4KeyFrameParser.__readMP4Payload(file, stss_box)
            if len(stss_payload) >= 8:
                entry_count = MP4KeyFrameParser.__readUInt32(stss_payload, 4)
                for entry_index in range(entry_count):
                    sample_offset = 8 + entry_index * 4
                    if sample_offset + 4 > len(stss_payload):
                        break
                    stss_samples.append(MP4KeyFrameParser.__readUInt32(stss_payload, sample_offset))

        return _MP4TrackInfo(handler_type, timescale, stts_entries, stss_samples)
