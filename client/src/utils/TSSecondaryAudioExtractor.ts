import { calculateCRC32 } from 'arib-mmt-tlv-ts/crc-32.js';
import { readSection } from 'arib-mmt-tlv-ts/ts/si.js';
import { concatBuffers } from 'arib-mmt-tlv-ts/utils.js';

import type { ProgramMapSection } from 'arib-mmt-tlv-ts/ts/si.js';

/** MPEG-TS セグメントから第2 AAC 音声と時刻基準だけを抽出する。 */
export default class MPEGTSSecondaryAudioExtractor {

    private static readonly PACKET_SIZE = 188;
    private static readonly AAC_STREAM_TYPES = new Set([0x0f, 0x11]);

    /**
     * PAT と PMT を解析し、第2 AAC と必要な PCR 搬送パケットだけを返す。
     * @param segmentData 映像と複数音声を含む MPEG-TS セグメント
     * @returns PAT、再構築した PMT、第2 AAC、PCR 搬送パケットだけを含む MPEG-TS セグメント
     */
    static extract(segmentData: Uint8Array): Uint8Array {
        if (segmentData.byteLength % this.PACKET_SIZE !== 0) {
            throw new Error('MPEG-TS segment size is not aligned to 188-byte packets.');
        }

        // 元セグメントをコピーせず、188バイト単位のビューに分割する
        const packets: Uint8Array[] = [];
        for (let offset = 0; offset < segmentData.byteLength; offset += this.PACKET_SIZE) {
            packets.push(segmentData.subarray(offset, offset + this.PACKET_SIZE));
        }
        if (packets.some(packet => packet[0] !== 0x47)) {
            throw new Error('Invalid MPEG-TS sync byte was found in the segment.');
        }

        // セクションの内容と CRC は arib-mmt-tlv-ts で解析し、記述子の元バイト列も保持する
        const {pmtPID, pmt, rawPMT} = this.parseProgramMap(packets);
        const secondaryStream = pmt.streams.filter(stream => this.AAC_STREAM_TYPES.has(stream.streamType))[1];
        if (secondaryStream === undefined) throw new Error('The second AAC stream was not found in the PMT.');

        const pmtPacketIndex = packets.findIndex(packet => this.getPID(packet) === pmtPID && (packet[1] & 0x40) !== 0);
        if (pmtPacketIndex === -1) throw new Error('PMT was not found in the MPEG-TS segment.');
        const filteredPMTSection = this.buildFilteredPMT(rawPMT, secondaryStream.elementaryPID);
        const filteredPMTPackets = this.packetizePMT(
            filteredPMTSection,
            pmtPID,
            packets[pmtPacketIndex],
        );

        // 元のパケット順を維持し、音声の到着順と PCR の時間順が変わらないストリームを組み立てる
        // PCR のない入力はそのまま扱い、音声の再生時刻は元の PES に保持する
        const outputPackets: Uint8Array[] = [];
        packets.forEach((packet, index) => {
            const pid = this.getPID(packet);
            if (pid === 0) outputPackets.push(packet);
            else if (pid === pmtPID && index === pmtPacketIndex) outputPackets.push(...filteredPMTPackets);
            else if (pid === secondaryStream.elementaryPID) {
                outputPackets.push(packet);
            }
            else if (pid === pmt.pcrPID && (packet[3] & 0x20) !== 0 && packet[4] >= 7 && (packet[5] & 0x10) !== 0) {
                outputPackets.push(this.buildPCROnlyPacket(packet));
            }
        });
        return concatBuffers(outputPackets);
    }

    /**
     * TS ヘッダーから PID を取得する。
     * @param packet MPEG-TS パケット
     * @returns PID
     */
    private static getPID(packet: Uint8Array): number {
        return ((packet[1] & 0x1f) << 8) | packet[2];
    }

    /**
     * 指定 PID のセクションを元バイト列のまま取り出す。
     * @param packets MPEG-TS パケット
     * @param pid 対象 PID
     * @returns 結合済み PSI セクション
     */
    private static *readSections(packets: Uint8Array[], pid: number): Generator<Uint8Array> {
        // TSReader の公開イベントには元セクションが含まれないため、書き出しに必要なバイト列だけをここで結合する
        // 内容の解析と CRC 検証は呼び出し側の readSection() に任せる
        let pending: Uint8Array = new Uint8Array();
        let lastCounter: number | null = null;
        for (const packet of packets) {
            if (this.getPID(packet) !== pid) continue;
            // 壊れたパケットや暗号化されたパケットをまたぐセクションは破棄する
            if ((packet[1] & 0x80) !== 0 || (packet[3] & 0xc0) !== 0) {
                pending = new Uint8Array();
                lastCounter = null;
                continue;
            }
            if ((packet[3] & 0x10) === 0) continue;
            const counter = packet[3] & 0x0f;
            if (counter === lastCounter) continue;
            if (lastCounter !== null && counter !== ((lastCounter + 1) & 0x0f)) pending = new Uint8Array();
            lastCounter = counter;
            let offset = 4 + ((packet[3] & 0x20) !== 0 ? 1 + packet[4] : 0);
            if (offset >= packet.length) continue;

            // PUSI パケットではポインター手前が前セクションの末尾、後ろが新セクションの先頭となる
            if ((packet[1] & 0x40) !== 0) {
                const pointer = packet[offset++];
                if (offset + pointer > packet.length) {
                    pending = new Uint8Array();
                    continue;
                }
                if (pending.length > 0) yield concatBuffers([pending, packet.subarray(offset, offset + pointer)]);
                pending = packet.subarray(offset + pointer);
            } else {
                if (pending.length === 0) continue;
                pending = concatBuffers([pending, packet.subarray(offset)]);
            }
            // セクション長までを切り出し、同じパケット内の後続セクションも順に返す
            while (pending.length >= 3 && pending[0] !== 0xff) {
                const length = 3 + (((pending[1] & 0x0f) << 8) | pending[2]);
                if (pending.length < length) break;
                yield pending.subarray(0, length);
                pending = pending.subarray(length);
            }
            if (pending[0] === 0xff) pending = new Uint8Array();
        }
    }

    /**
     * arib-mmt-tlv-ts で PAT と PMT を CRC 検証付きで解析する。
     * @param packets MPEG-TS パケット
     * @returns PAT が参照する PMT PID、解析済み PMT、元セクション
     */
    private static parseProgramMap(packets: Uint8Array[]): {pmtPID: number; pmt: ProgramMapSection; rawPMT: Uint8Array} {
        let pmtPID: number | null = null;
        for (const raw of this.readSections(packets, 0)) {
            const pat = readSection(raw);
            if (pat?.tableId !== 'PAT') continue;
            const program = pat.programs.find(entry => entry.type === 'program');
            if (program?.type === 'program') {
                pmtPID = program.programMapPID;
                break;
            }
        }
        if (pmtPID === null) throw new Error('PAT does not contain a program map PID.');
        for (const rawPMT of this.readSections(packets, pmtPID)) {
            const pmt = readSection(rawPMT);
            if (pmt?.tableId === 'PMT') return {pmtPID, pmt, rawPMT};
        }
        throw new Error('PMT was not found in the MPEG-TS segment.');
    }

    /**
     * 解析済み PMT の元バイト列から第2 AAC のエントリーを残し、CRC32 を更新する。
     * @param rawPMT 元の PMT セクション
     * @param secondaryPID 第2 AAC の PID
     * @returns CRC を含む PMT セクション
     */
    private static buildFilteredPMT(rawPMT: Uint8Array, secondaryPID: number): Uint8Array {
        // ヘッダーと番組記述子、および副音声の ES エントリーを元のままコピーする
        const headerLength = 12 + (((rawPMT[10] & 0x0f) << 8) | rawPMT[11]);
        let entryOffset = headerLength;
        while ((((rawPMT[entryOffset + 1] & 0x1f) << 8) | rawPMT[entryOffset + 2]) !== secondaryPID) {
            entryOffset += 5 + (((rawPMT[entryOffset + 3] & 0x0f) << 8) | rawPMT[entryOffset + 4]);
        }
        const entryLength = 5 + (((rawPMT[entryOffset + 3] & 0x0f) << 8) | rawPMT[entryOffset + 4]);
        const section = concatBuffers([rawPMT.subarray(0, headerLength), rawPMT.subarray(entryOffset, entryOffset + entryLength)]);

        // ES を除去した分だけセクション長と CRC を更新する
        const sectionLength = section.byteLength - 3 + 4;
        section[1] = (section[1] & 0xf0) | ((sectionLength >> 8) & 0x0f);
        section[2] = sectionLength & 0xff;
        const crc = new Uint8Array(4);
        new DataView(crc.buffer).setUint32(0, calculateCRC32(section, -1));
        return concatBuffers([section, crc]);
    }

    /**
     * PMT セクションを必要な数の TS パケットへ格納する。
     * @param section CRC を含む PMT セクション
     * @param pmtPID PMT PID
     * @param sourcePacket 元の PMT パケットヘッダー
     * @returns 再構築した PMT パケットの配列
     */
    private static packetizePMT(
        section: Uint8Array,
        pmtPID: number,
        sourcePacket: Uint8Array,
    ): Uint8Array[] {
        const packets: Uint8Array[] = [];
        let sectionOffset = 0;
        let continuityCounter = sourcePacket[3] & 0x0f;

        // 最初のパケットだけポインターフィールドを置き、後続パケットは184バイトすべてをセクションへ使う
        while (sectionOffset < section.byteLength) {
            const isFirstPacket = sectionOffset === 0;
            const payloadCapacity = this.PACKET_SIZE - 4 - (isFirstPacket ? 1 : 0);
            const sectionChunk = section.subarray(sectionOffset, sectionOffset + payloadCapacity);
            // ライブラリは読み取り専用なので、4バイトの TS ヘッダーとペイロードを直接書き出す
            const packet = new Uint8Array(this.PACKET_SIZE).fill(0xff);
            packet[0] = 0x47;
            packet[1] = (isFirstPacket ? 0x40 : 0) | (sourcePacket[1] & 0x20) | (pmtPID >> 8);
            packet[2] = pmtPID & 0xff;
            packet[3] = (sourcePacket[3] & 0xc0) | 0x10 | continuityCounter;
            if (isFirstPacket) packet[4] = 0;
            packet.set(sectionChunk, isFirstPacket ? 5 : 4);
            packets.push(packet);
            sectionOffset += sectionChunk.byteLength;
            continuityCounter = (continuityCounter + 1) & 0x0f;
        }
        return packets;
    }

    /**
     * 入力パケットの PCR を保持し、映像ペイロードをスタッフィングへ置き換える。
     * @param packet PCR を含む MPEG-TS パケット
     * @returns PCR と不連続フラグを保持した adaptation-field-only パケット
     */
    private static buildPCROnlyPacket(packet: Uint8Array): Uint8Array {
        // PCR の6バイトをそのままコピーし、数値への変換を挟まず元の時刻を保持する
        const output = new Uint8Array(this.PACKET_SIZE).fill(0xff);
        output.set(packet.subarray(0, 12));
        output[1] &= 0xbf;
        output[3] = 0x20 | (packet[3] & 0x0f);
        output[4] = this.PACKET_SIZE - 5;
        output[5] = 0x10 | (packet[5] & 0x80);
        return output;
    }
}
