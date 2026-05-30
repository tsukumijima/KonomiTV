from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from biim.mpeg2ts import ts
from biim.mpeg2ts.h264 import H264PES
from biim.mpeg2ts.h265 import H265PES
from biim.mpeg2ts.parser import PESParser, SectionParser
from biim.mpeg2ts.pat import PATSection
from biim.mpeg2ts.pes import PES
from biim.mpeg2ts.pmt import PMTSection


@dataclass(slots=True)
class TSKeyFramePosition:
    """
    録画ファイル内でエンコードを開始する位置と時刻を表すデータクラス

    Args:
        source_file_position (int): 入力ファイルのバイト位置
        source_start_dts (int): 入力ソース上の開始 DTS (90kHz)
    """

    source_file_position: int
    source_start_dts: int


@dataclass(slots=True)
class TSStreamInfo:
    """
    TS コンテナ内の映像 PID と PCR PID をまとめて保持するデータクラス

    Args:
        video_pid (int): 映像 PES が流れる PID
        pcr_pid (int): PCR が流れる PID
        codec (Literal['MPEG-2', 'H.264', 'H.265']): 映像コーデック
        packet_size (int): ファイル上の TS パケットサイズ (188 または 192)
    """

    video_pid: int
    pcr_pid: int
    codec: Literal['MPEG-2', 'H.264', 'H.265']
    packet_size: int


@dataclass(slots=True)
class _KeyframeScanResult:
    """
    TS コンテナの前方スキャンで見つかったキーフレーム情報

    Args:
        offset (int): PES 開始位置のファイルオフセット
        dts (int): キーフレームの DTS (90kHz)
        scan_bytes (int): この探索で読み込んだバイト数
        has_confirmed_boundary (bool): 目標時刻を越えたキーフレームまで読めたかどうか
    """

    offset: int
    dts: int
    scan_bytes: int
    has_confirmed_boundary: bool


class TSKeyFrameSeeker:
    """
    TS 録画ファイルの再生開始位置を、プレイリスト上の相対時刻から解決する
    """

    PCR_SEARCH_WINDOW_BYTES = 2 * 1024 * 1024
    KEYFRAME_BACKTRACK_BYTES = 8 * 1024 * 1024
    MAX_KEYFRAME_SCAN_BYTES = 96 * 1024 * 1024


    @staticmethod
    def findStreamInfo(path: Path) -> TSStreamInfo:
        """
        PAT/PMT から映像 PID と PCR PID を取得する

        Args:
            path (Path): TS コンテナの録画ファイルパス

        Returns:
            TSStreamInfo: オンデマンド探索に必要なストリーム情報
        """

        packet_size = TSKeyFrameSeeker.__detectPacketSize(path)
        pat_parser = SectionParser(PATSection)
        pmt_parser = SectionParser(PMTSection)
        pmt_pid: int | None = None

        with path.open('rb') as file:
            for _ in range(300000):
                packet = TSKeyFrameSeeker.__normalizePacket(file.read(packet_size), packet_size)
                if packet is None:
                    break

                pid = ts.pid(packet)
                if pid == 0x00:
                    pat_parser.push(packet)
                    for pat in pat_parser:
                        if pat.CRC32() != 0:
                            continue
                        for program_number, program_map_pid in pat:
                            if program_number != 0:
                                pmt_pid = program_map_pid
                                break
                elif pmt_pid is not None and pid == pmt_pid:
                    pmt_parser.push(packet)
                    for pmt in pmt_parser:
                        if pmt.CRC32() != 0:
                            continue
                        for stream_type, elementary_pid, _ in pmt:
                            if stream_type == 0x02:
                                return TSStreamInfo(elementary_pid, pmt.PCR_PID, 'MPEG-2', packet_size)
                            if stream_type == 0x1B:
                                return TSStreamInfo(elementary_pid, pmt.PCR_PID, 'H.264', packet_size)
                            if stream_type == 0x24:
                                return TSStreamInfo(elementary_pid, pmt.PCR_PID, 'H.265', packet_size)

        raise RuntimeError(f'Video stream information was not found: {path}')


    @staticmethod
    def findBaseDTS(path: Path, stream_info: TSStreamInfo) -> int:
        """
        TS コンテナ内の最初のキーフレーム DTS を取得する

        Args:
            path (Path): TS コンテナの録画ファイルパス
            stream_info (TSStreamInfo): 対象映像 PID などのストリーム情報

        Returns:
            int: 最初のキーフレーム DTS (90kHz)
        """

        parser = TSKeyFrameSeeker.__createPESParser(stream_info.codec)
        pending_pes_start: int | None = None
        scanned_bytes = 0

        with path.open('rb') as file:
            while scanned_bytes < TSKeyFrameSeeker.MAX_KEYFRAME_SCAN_BYTES:
                current_file_offset = file.tell()
                packet = TSKeyFrameSeeker.__normalizePacket(file.read(stream_info.packet_size), stream_info.packet_size)
                scanned_bytes += stream_info.packet_size
                if packet is None:
                    break
                if ts.pid(packet) != stream_info.video_pid:
                    continue

                is_payload_start = (packet[1] & 0x40) != 0
                current_pes_start = current_file_offset if is_payload_start is True else None
                # is_payload_start と current_pes_start は、いま読んだパケットが次の PES の開始位置かどうかを記録する
                ## parser.push(packet) は次の PES 開始を見た時点で前の PES を yield するため、pending_pes_start を for pes in parser 内で進める
                ## yield がなかった場合も次回の TSKeyFrameSeeker.__hasKeyframe() 判定へ開始位置を渡せるよう、後段の補助更新で進める
                parser.push(packet)
                for pes in parser:
                    pes_start = pending_pes_start
                    if current_pes_start is not None:
                        pending_pes_start = current_pes_start
                    if pes_start is None:
                        continue
                    dts_value = pes.dts()
                    raw_dts = dts_value if dts_value is not None else pes.pts()
                    if raw_dts is None:
                        continue
                    if TSKeyFrameSeeker.__hasKeyframe(pes, stream_info.codec) is True:
                        return raw_dts

                if current_pes_start is not None and pending_pes_start != current_pes_start:
                    pending_pes_start = current_pes_start

        raise RuntimeError(f'First keyframe DTS was not found: {path}')


    @staticmethod
    def seek(
        path: Path,
        stream_info: TSStreamInfo,
        playlist_start_seconds: float,
        source_base_dts: int,
    ) -> TSKeyFramePosition:
        """
        TS コンテナで、プレイリスト時刻以前の最も近いキーフレームを探索する

        Args:
            path (Path): TS コンテナの録画ファイルパス
            stream_info (TSStreamInfo): 対象映像 PID などのストリーム情報
            playlist_start_seconds (float): 録画内の相対再生時刻
            source_base_dts (int): 録画先頭キーフレームの DTS (90kHz)

        Returns:
            TSKeyFramePosition: エンコード開始に使うファイル位置と DTS
        """

        file_size = path.stat().st_size
        target_dts = source_base_dts + round(playlist_start_seconds * ts.HZ)
        keyframe = TSKeyFrameSeeker.__resolveKeyframeByPCR(
            path,
            stream_info,
            playlist_start_seconds = playlist_start_seconds,
            target_dts = target_dts,
            file_size = file_size,
        )
        if keyframe is None:
            raise RuntimeError(f'Keyframe was not found near requested time: {path}')

        return TSKeyFramePosition(
            source_file_position = keyframe.offset,
            source_start_dts = keyframe.dts,
        )


    @staticmethod
    def __detectPacketSize(path: Path) -> int:
        """
        TS パケットサイズを 188 バイトまたは 192 バイトから推定する

        Args:
            path (Path): TS コンテナの録画ファイルパス

        Returns:
            int: 検出した TS パケットサイズ
        """

        with path.open('rb') as file:
            head = file.read(8192)
        for packet_size in (ts.PACKET_SIZE, 192):
            for start_offset in range(packet_size):
                if all(
                    start_offset + packet_size * index < len(head) and
                    head[start_offset + packet_size * index] == ts.SYNC_BYTE[0]
                    for index in range(5)
                ) is True:
                    return packet_size
        return ts.PACKET_SIZE


    @staticmethod
    def __normalizePacket(packet: bytes, packet_size: int) -> bytes | None:
        """
        188/192 バイト TS パケットを biim が扱う 188 バイトパケットへ正規化する

        Args:
            packet (bytes): ファイルから読み込んだパケット
            packet_size (int): ファイル上のパケットサイズ

        Returns:
            bytes | None: 188 バイト TS パケット (同期が取れない場合は None)
        """

        if len(packet) != packet_size:
            return None
        if packet_size == 192:
            packet = packet[4:]
        if len(packet) != ts.PACKET_SIZE or packet[0] != ts.SYNC_BYTE[0]:
            return None
        return packet


    @staticmethod
    def __readFirstPCRNear(
        path: Path,
        stream_info: TSStreamInfo,
        start_offset: int,
        max_scan_bytes: int,
    ) -> tuple[int, int] | None:
        """
        指定位置以降で最初に見つかった PCR を返す

        Args:
            path (Path): TS コンテナの録画ファイルパス
            stream_info (TSStreamInfo): PCR PID を含むストリーム情報
            start_offset (int): 探索を開始するファイル位置
            max_scan_bytes (int): 最大スキャンバイト数

        Returns:
            tuple[int, int] | None: ファイル位置と PCR 90kHz 値
        """

        aligned_offset = max(0, (start_offset // stream_info.packet_size) * stream_info.packet_size)
        scanned_bytes = 0
        with path.open('rb') as file:
            file.seek(aligned_offset)
            while scanned_bytes < max_scan_bytes:
                file_offset = file.tell()
                packet = TSKeyFrameSeeker.__normalizePacket(file.read(stream_info.packet_size), stream_info.packet_size)
                scanned_bytes += stream_info.packet_size
                if packet is None:
                    continue
                if ts.pid(packet) == stream_info.pcr_pid and ts.has_pcr(packet) is True:
                    return (file_offset, cast(int, ts.pcr(packet)))
        return None


    @staticmethod
    def __unwrapNear(value_33bit: int, target_dts: int) -> int:
        """
        33bit の時刻を、target_dts に最も近い展開済み時刻へ寄せる

        Args:
            value_33bit (int): PES/PCR から読んだ 33bit 時刻
            target_dts (int): 比較対象の展開済み DTS

        Returns:
            int: target_dts に近い形へ 33bit ラップを展開した値
        """

        wrap_count = round((target_dts - value_33bit) / ts.PCR_CYCLE)
        return value_33bit + wrap_count * ts.PCR_CYCLE


    @staticmethod
    def __hasKeyframe(pes: PES, codec: Literal['MPEG-2', 'H.264', 'H.265']) -> bool:
        """
        PES がセグメント開始に使えるキーフレームかを判定する

        Args:
            pes (PES): 判定対象の PES
            codec (Literal['MPEG-2', 'H.264', 'H.265']): 映像コーデック

        Returns:
            bool: キーフレームとして扱える場合 True
        """

        if codec == 'H.264' and isinstance(pes, H264PES):
            for ebsp in pes.ebsps:
                if len(ebsp) > 0 and (ebsp[0] & 0x1F) == 0x05:
                    return True
            return False

        if codec == 'H.265' and isinstance(pes, H265PES):
            for ebsp in pes.ebsps:
                # H.265 は BLA / IDR / CRA の NAL unit type 16〜21 をランダムアクセスフレームとして扱う
                if len(ebsp) > 0 and ((ebsp[0] >> 1) & 0x3F) in (16, 17, 18, 19, 20, 21):
                    return True
            return False

        # MPEG-2 Video は picture_start_code 直後の picture_coding_type で I ピクチャを判定する
        if codec == 'MPEG-2':
            data = bytes(pes.PES_packet_data())
            marker_index = data.find(b'\x00\x00\x01\x00')
            if marker_index == -1 or marker_index + 5 >= len(data):
                return False
            picture_coding_type = (data[marker_index + 5] >> 3) & 0x07
            return picture_coding_type == 1

        return False


    @staticmethod
    def __createPESParser(codec: Literal['MPEG-2', 'H.264', 'H.265']) -> PESParser[PES]:
        """
        コーデックに応じた PESParser を作成する

        Args:
            codec (Literal['MPEG-2', 'H.264', 'H.265']): 映像コーデック

        Returns:
            PESParser[PES]: PES パーサー
        """

        if codec == 'H.264':
            return PESParser(H264PES)
        if codec == 'H.265':
            return PESParser(H265PES)
        return PESParser(PES)


    @staticmethod
    def __findKeyframeBefore(
        path: Path,
        stream_info: TSStreamInfo,
        *,
        target_dts: int,
        start_offset: int,
        max_scan_bytes: int,
    ) -> _KeyframeScanResult | None:
        """
        target_dts 直前のキーフレームを推定位置付近から探索する

        Args:
            path (Path): TS コンテナの録画ファイルパス
            stream_info (TSStreamInfo): 対象映像 PID などのストリーム情報
            target_dts (int): 探したいプレイリスト時刻に対応するソース側 DTS
            start_offset (int): 前方スキャンを開始するファイル位置
            max_scan_bytes (int): 最大スキャンバイト数

        Returns:
            _KeyframeScanResult | None: 検出したキーフレーム情報
        """

        aligned_start_offset = max(0, (start_offset // stream_info.packet_size) * stream_info.packet_size)
        parser = TSKeyFrameSeeker.__createPESParser(stream_info.codec)
        pending_pes_start: int | None = None
        last_keyframe_before: tuple[int, int] | None = None
        scanned_bytes = 0

        with path.open('rb') as file:
            file.seek(aligned_start_offset)
            while scanned_bytes < max_scan_bytes:
                current_file_offset = file.tell()
                packet = TSKeyFrameSeeker.__normalizePacket(file.read(stream_info.packet_size), stream_info.packet_size)
                scanned_bytes += stream_info.packet_size
                if packet is None:
                    break
                if ts.pid(packet) != stream_info.video_pid:
                    continue

                is_payload_start = (packet[1] & 0x40) != 0
                current_pes_start = current_file_offset if is_payload_start is True else None
                # is_payload_start と current_pes_start は、いま読んだパケットが次の PES の開始位置かどうかを記録する
                ## parser.push(packet) は次の PES 開始を見た時点で前の PES を yield するため、pending_pes_start を for pes in parser 内で進める
                ## yield がなかった場合も次回の TSKeyFrameSeeker.__hasKeyframe() 判定へ開始位置を渡せるよう、後段の補助更新で進める
                parser.push(packet)
                for pes in parser:
                    pes_start = pending_pes_start
                    if current_pes_start is not None:
                        pending_pes_start = current_pes_start
                    if pes_start is None:
                        continue
                    dts_value = pes.dts()
                    raw_dts = dts_value if dts_value is not None else pes.pts()
                    if raw_dts is None:
                        continue
                    source_dts = TSKeyFrameSeeker.__unwrapNear(raw_dts, target_dts)
                    if TSKeyFrameSeeker.__hasKeyframe(pes, stream_info.codec) is False:
                        continue
                    if source_dts <= target_dts:
                        last_keyframe_before = (pes_start, source_dts)
                        continue
                    if last_keyframe_before is not None:
                        return _KeyframeScanResult(last_keyframe_before[0], last_keyframe_before[1], scanned_bytes, True)
                    # 最初に見つかったキーフレームが target_dts より後ろなら、この探索窓は開始位置として使わない
                    ## 後続キーフレームを返すとプレイリスト時刻の冒頭を欠くため、呼び出し側の広い手前探索へ任せる
                    return None

                if current_pes_start is not None and pending_pes_start != current_pes_start:
                    pending_pes_start = current_pes_start

        if last_keyframe_before is not None:
            return _KeyframeScanResult(last_keyframe_before[0], last_keyframe_before[1], scanned_bytes, False)
        return None


    @staticmethod
    def __findOffsetByPCRBinarySearch(
        path: Path,
        stream_info: TSStreamInfo,
        playlist_start_seconds: float,
        file_size: int,
    ) -> int:
        """
        PCR の単調増加を利用してプレイリスト時刻直前のファイル位置を二分探索する

        Args:
            path (Path): TS コンテナの録画ファイルパス
            stream_info (TSStreamInfo): PCR PID を含むストリーム情報
            playlist_start_seconds (float): 録画内相対時刻
            file_size (int): ファイルサイズ

        Returns:
            int: 目標時刻直前と推定できるファイル位置
        """

        first_pcr = TSKeyFrameSeeker.__readFirstPCRNear(
            path,
            stream_info,
            0,
            TSKeyFrameSeeker.PCR_SEARCH_WINDOW_BYTES,
        )
        if first_pcr is None:
            return 0

        first_offset, first_pcr_value = first_pcr
        target_pcr = first_pcr_value + round(playlist_start_seconds * ts.HZ)
        lo = first_offset
        hi = max(first_offset, file_size - stream_info.packet_size)

        while hi - lo > TSKeyFrameSeeker.PCR_SEARCH_WINDOW_BYTES:
            mid = ((lo + hi) // 2 // stream_info.packet_size) * stream_info.packet_size
            mid_pcr = TSKeyFrameSeeker.__readFirstPCRNear(
                path,
                stream_info,
                mid,
                TSKeyFrameSeeker.PCR_SEARCH_WINDOW_BYTES,
            )
            if mid_pcr is None:
                lo = mid
                continue
            _, mid_pcr_value = mid_pcr
            unwrapped_mid_pcr = TSKeyFrameSeeker.__unwrapNear(mid_pcr_value, target_pcr)
            if unwrapped_mid_pcr <= target_pcr:
                lo = mid
            else:
                hi = mid

        return lo


    @staticmethod
    def __resolveKeyframeByPCR(
        path: Path,
        stream_info: TSStreamInfo,
        *,
        playlist_start_seconds: float,
        target_dts: int,
        file_size: int,
    ) -> _KeyframeScanResult | None:
        """
        PCR 二分探索と短い PES 前方スキャンで目標時刻直前のキーフレームを解決する

        Args:
            path (Path): TS コンテナの録画ファイルパス
            stream_info (TSStreamInfo): 対象映像 PID などのストリーム情報
            playlist_start_seconds (float): 録画内相対時刻
            target_dts (int): 探したいプレイリスト時刻に対応するソース側 DTS
            file_size (int): ファイルサイズ

        Returns:
            _KeyframeScanResult | None: 解決したキーフレーム情報
        """

        pcr_offset = TSKeyFrameSeeker.__findOffsetByPCRBinarySearch(
            path,
            stream_info,
            playlist_start_seconds,
            file_size,
        )
        scan_attempts = [
            (TSKeyFrameSeeker.KEYFRAME_BACKTRACK_BYTES, TSKeyFrameSeeker.MAX_KEYFRAME_SCAN_BYTES),
            (TSKeyFrameSeeker.KEYFRAME_BACKTRACK_BYTES * 4, TSKeyFrameSeeker.MAX_KEYFRAME_SCAN_BYTES * 2),
        ]
        total_scan_bytes = 0
        last_result: _KeyframeScanResult | None = None
        for backtrack_bytes, max_scan_bytes in scan_attempts:
            # PCR は映像 PES と別 PID で流れるため、少し手前から映像 PES を読んで直前キーフレームを探す
            scan_start_offset = max(0, pcr_offset - backtrack_bytes)
            result = TSKeyFrameSeeker.__findKeyframeBefore(
                path,
                stream_info,
                target_dts = target_dts,
                start_offset = scan_start_offset,
                max_scan_bytes = max_scan_bytes,
            )
            if result is None:
                continue
            total_scan_bytes += result.scan_bytes
            last_result = result
            if result.has_confirmed_boundary is True:
                return _KeyframeScanResult(
                    offset = result.offset,
                    dts = result.dts,
                    scan_bytes = total_scan_bytes,
                    has_confirmed_boundary = result.has_confirmed_boundary,
                )

        if last_result is not None:
            return _KeyframeScanResult(
                offset = last_result.offset,
                dts = last_result.dts,
                scan_bytes = total_scan_bytes,
                has_confirmed_boundary = last_result.has_confirmed_boundary,
            )
        return None
