from biim.mpeg2ts import ts
from biim.mpeg2ts.packetize import packetize_section
from biim.mpeg2ts.parser import SectionParser
from biim.mpeg2ts.pat import PATSection
from biim.mpeg2ts.pmt import PMTSection
from biim.mpeg2ts.section import Section


class TSSecondaryAudioExtractor:
    """MPEG-TS セグメントから第2 AAC 音声と時刻基準だけを抽出する。"""

    AAC_STREAM_TYPES = {0x0F, 0x11}

    @classmethod
    def extract(cls, segment_data: bytes) -> bytes:
        """
        MPEG-TS セグメントから第2 AAC 音声を抽出する。

        Args:
            segment_data (bytes): 映像と複数音声を含む MPEG-TS セグメント

        Returns:
            bytes: PAT、再構築した PMT、第2 AAC、PCR 搬送パケットだけを含む MPEG-TS セグメント

        Raises:
            ValueError: PAT、PMT、または第2 AAC ストリームを取得できない場合
        """

        if len(segment_data) % ts.PACKET_SIZE != 0:
            raise ValueError('MPEG-TS segment size is not aligned to 188-byte packets.')

        # biim のパケットパーサーが受け取れる188バイト単位へ分割し、壊れた同期バイトを先に検出する
        packets = [
            memoryview(segment_data)[offset:offset + ts.PACKET_SIZE]
            for offset in range(0, len(segment_data), ts.PACKET_SIZE)
        ]
        if any(packet[0] != ts.SYNC_BYTE[0] for packet in packets):
            raise ValueError('Invalid MPEG-TS sync byte was found in the segment.')

        # PAT と PMT は biim の SectionParser へ渡し、複数パケットに分割されたセクションも同じ経路で解析する
        pmt_pid = cls.__getPMTPID(packets)
        pmt_section = cls.__getPMTSection(packets, pmt_pid)
        secondary_audio_pid, filtered_pmt_section = cls.__buildFilteredPMT(pmt_section)
        pcr_pid = pmt_section.PCR_PID
        pmt_packet = next((
            packet for packet in packets
            if ts.pid(packet) == pmt_pid and ts.payload_unit_start_indicator(packet)
        ), None)
        if pmt_packet is None:
            raise ValueError('PMT was not found in the MPEG-TS segment.')
        filtered_pmt_packets = packetize_section(
            Section(filtered_pmt_section),
            ts.transport_error_indicator(pmt_packet),
            ts.transport_priority(pmt_packet),
            pmt_pid,
            ts.transport_scrambling_control(pmt_packet),
            ts.continuity_counter(pmt_packet),
        )

        # PAT と再構築した PMT は元の出現位置を保ち、音声 PES の到着順と PCR の時間順を変えずに返す
        # PCR のない入力はそのまま扱い、音声の再生時刻は元の PES に保持する
        output_packets: list[bytes] = []
        for packet in packets:
            pid = ts.pid(packet)
            if pid == 0:
                output_packets.append(bytes(packet))
            elif pid == pmt_pid:
                if packet is pmt_packet:
                    output_packets.extend(filtered_pmt_packets)
            elif pid == secondary_audio_pid:
                output_packets.append(bytes(packet))
            elif pid == pcr_pid and ts.has_pcr(packet):
                output_packets.append(cls.__buildPCROnlyPacket(packet))
        return b''.join(output_packets)

    @staticmethod
    def __getPMTPID(packets: list[memoryview]) -> int:
        """
        PAT から最初の番組の PMT PID を取得する。

        Args:
            packets (list[memoryview]): MPEG-TS パケットのリスト

        Returns:
            int: PMT PID

        Raises:
            ValueError: 有効な PAT または番組の PMT PID を取得できない場合
        """

        pat_parser = SectionParser(PATSection)
        for packet in packets:
            if ts.pid(packet) != 0:
                continue
            pat_parser.push(packet)
            for pat in pat_parser:
                if pat.table_id() != 0x00 or pat.CRC32() != 0:
                    continue
                for program_number, pmt_pid in pat:
                    if program_number != 0:
                        return pmt_pid
        raise ValueError('PAT does not contain a program map PID.')

    @staticmethod
    def __getPMTSection(packets: list[memoryview], pmt_pid: int) -> PMTSection:
        """
        PMT PID のパケットから有効な PMT セクションを取得する。

        Args:
            packets (list[memoryview]): MPEG-TS パケットのリスト
            pmt_pid (int): PAT から取得した PMT PID

        Returns:
            PMTSection: CRC が正しい PMT セクション

        Raises:
            ValueError: 有効な PMT を取得できない場合
        """

        pmt_parser = SectionParser(PMTSection)
        for packet in packets:
            if ts.pid(packet) != pmt_pid:
                continue
            pmt_parser.push(packet)
            for pmt in pmt_parser:
                if pmt.table_id() == 0x02 and pmt.CRC32() == 0:
                    return pmt
        raise ValueError('PMT was not found in the MPEG-TS segment.')

    @classmethod
    def __buildFilteredPMT(cls, pmt: PMTSection) -> tuple[int, bytes]:
        """
        biim が解析した PMT から第2 AAC だけを持つ PMT を構築する。

        Args:
            pmt (PMTSection): 元の PMT セクション

        Returns:
            tuple[int, bytes]: 第2 AAC PID、再構築した PMT セクション

        Raises:
            ValueError: PMT に第2 AAC ストリームがない場合
        """

        aac_streams = [stream for stream in pmt if stream[0] in cls.AAC_STREAM_TYPES]
        if len(aac_streams) < 2:
            raise ValueError('The second AAC stream was not found in the PMT.')

        # 解析済みの記述子長で元セクションをたどり、副音声の ES エントリーをそのまま保持する
        program_info_length = ((pmt[10] & 0x0F) << 8) | pmt[11]
        entry_offset = 12 + program_info_length
        secondary_audio_pid = aac_streams[1][1]
        section_without_crc = bytearray(pmt[:entry_offset])
        for _, pid, descriptors in pmt:
            entry_length = 5 + sum(2 + len(payload) for _, payload in descriptors)
            if pid == secondary_audio_pid:
                section_without_crc.extend(pmt[entry_offset:entry_offset + entry_length])
                break
            entry_offset += entry_length

        # ES を除去した分だけセクション長と CRC を更新する
        section_length = len(section_without_crc) + 4 - 3
        section_without_crc[1] = (section_without_crc[1] & 0xF0) | ((section_length >> 8) & 0x0F)
        section_without_crc[2] = section_length & 0xFF
        crc = Section(section_without_crc).CRC32()
        return secondary_audio_pid, bytes(section_without_crc) + crc.to_bytes(4, 'big')

    @staticmethod
    def __buildPCROnlyPacket(packet: bytes | bytearray | memoryview) -> bytes:
        """
        入力パケットの PCR だけを保持したアダプテーションフィールド専用パケットを返す。

        Args:
            packet (bytes | bytearray | memoryview): PCR を含む MPEG-TS パケット

        Returns:
            bytes: PCR 以外をスタッフィングした MPEG-TS パケット
        """

        # PCR の6バイトをそのまま保持し、映像ペイロードをスタッフィングへ置き換える
        # adaptation field は PCR と不連続フラグだけを持つ構造にそろえる
        output = bytearray(ts.STUFFING_BYTE * ts.PACKET_SIZE)
        output[:12] = packet[:12]
        output[1] &= 0xBF
        output[3] = 0x20 | (packet[3] & 0x0F)
        output[4] = ts.PACKET_SIZE - ts.HEADER_SIZE - 1
        output[5] = 0x10 | (packet[5] & 0x80)
        return bytes(output)
