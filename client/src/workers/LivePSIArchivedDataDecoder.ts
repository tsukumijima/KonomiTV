
import * as Comlink from 'comlink';
import { decodeTS } from 'web-bml/server/decode_ts';
import { ResponseMessage } from 'web-bml/server/ws_api';


interface IPSIArchivedDataContext {
    pids?: number[];
    dict?: (Uint8Array | null)[];
    position?: number;
    trailer_size?: number;
    time_list_count?: number;
    code_list_position?: number;
    code_count?: number;
    init_time?: number;
    curr_time?: number;
}

export interface ILivePSIArchivedDataDecoder {
    run(decoded_callback: (message: ResponseMessage) => void): void;
    destroy(): void;
}


/**
 * ライブ PSI/SI アーカイブデータストリーミング API から取得した PSI/SI アーカイブデータをデコードする
 */
class LivePSIArchivedDataDecoder implements ILivePSIArchivedDataDecoder {

    // ライブ PSI/SI アーカイブデータストリーミング API の URL
    private psi_archived_data_api_url: string;

    // PSI/SI アーカイブデータの読み込みに必要な情報
    private psi_archived_data: Uint8Array = new Uint8Array(0);
    private psi_archived_data_api_abort_controller: AbortController | null = null;
    private psi_archived_data_context: IPSIArchivedDataContext = {};
    private ts_packet_counters: {[index: number]: number} = {};

    /**
     * @param psi_archived_data_api_url ライブ PSI/SI アーカイブデータストリーミング API の URL
     */
    constructor(psi_archived_data_api_url: string) {
        this.psi_archived_data_api_url = psi_archived_data_api_url;
    }


    /**
     * PSI/SI アーカイブデータのストリーミングを開始し、TS ストリームをデコードする
     * デコード結果は decoded_callback に送信される
     *
     * EDCB Legacy WebUI での実装を参考にした
     * https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/util.lua#L444-L497
     */
    public run(decoded_callback: (message: ResponseMessage) => void): void {

        // TS ストリームのデコードを開始
        // PES (字幕) は mpegts.js / LL-HLS 側で既に対応しているため、BML ブラウザ側では対応しない
        const ts_stream = decodeTS({
            // TS ストリームをデコードした結果をメインスレッドの BML ブラウザに送信
            sendCallback: (message) => decoded_callback(message),
        });

        // ライブ PSI/SI アーカイブデータストリーミング API にリクエスト
        // 以降の処理はエンドレスなので非同期で実行
        this.psi_archived_data_api_abort_controller = new AbortController();
        fetch(this.psi_archived_data_api_url, {signal: this.psi_archived_data_api_abort_controller.signal}).then(async (response) => {

            // ReadableStreamDefaultReader を取得
            const reader = response.body?.getReader();
            if (reader === undefined) {
                console.error('[PSIArchivedDataDecoder] PSI/SI archived data API response body is not ReadableStream.');
                return;
            }

            let last_pcr = -1;
            while (true) {

                // API から随時データを取得
                const result = await reader.read();

                // サーバー側からのレスポンスが終了した (ライブストリームが Offline になったなど)
                // 基本サーバー側からのレスポンス出力が打ち切られる前にこちらから abort() するので発生しない
                if (result.done) {
                    console.log('[PSIArchivedDataDecoder] PSI/SI archived data finished.');
                    break;
                }
                // console.log(`[PSIArchivedDataDecoder] PSI/SI archived data received. (length: ${result.value.length})`);

                // 今まで受信した PSI/SI アーカイブデータと結合
                // TODO: サーバー側で psisiarc がリセットされた場合はここでも別途処理を挟む必要があるかも？要調査
                const add_data: Uint8Array = result.value;
                const concat_data = new Uint8Array(this.psi_archived_data.length + add_data.length);
                concat_data.set(this.psi_archived_data);
                concat_data.set(add_data, this.psi_archived_data.length);

                // PSI/SI アーカイブデータから TS パケットを生成し、BML ブラウザに送信
                const psi_archived_data = this.readPSIArchivedDataChunk(concat_data.buffer, 0, (second, psi_ts_packets, pid) => {

                    // PCR (Packet Clock Reference) を取得して送信
                    const pcr = Math.floor(second * 90000);
                    if (last_pcr !== pcr) {
                        decoded_callback({
                            type: 'pcr',
                            pcrBase: pcr,
                            pcrExtension: 0,
                        });
                        last_pcr = pcr;
                    }

                    // TS パケットのヘッダを設定してデコード
                    // デコードされた結果は decodeTS() の sendCallback で BML ブラウザに送信される
                    this.setTSPacketHeader(psi_ts_packets, pid);
                    ts_stream.parse(Buffer.from(psi_ts_packets.buffer, psi_ts_packets.byteOffset, psi_ts_packets.byteLength));
                });

                // 今回受信したデータを次回に持ち越す
                if (psi_archived_data) {
                    this.psi_archived_data = new Uint8Array(psi_archived_data);
                }
            }

        }).catch((error) => {
            // 何もしない
        });

        console.log('[PSIArchivedDataDecoder] TS decoder initialized.');
    }


    /**
     * PSI/SI アーカイブデータのストリーミングと TS ストリームのデコードを終了し、破棄する
     */
    public destroy(): void {

        // ライブ PSI/SI アーカイブデータストリーミング API のリクエストを中断
        if (this.psi_archived_data_api_abort_controller !== null) {
            this.psi_archived_data_api_abort_controller.abort();
            this.psi_archived_data_api_abort_controller = null;
        }

        // 既存の PSI/SI アーカイブデータを破棄
        this.psi_archived_data = new Uint8Array();
        this.psi_archived_data_context = {};
        this.ts_packet_counters = {};

        console.log('[PSIArchivedDataDecoder] TS decoder destroyed.');
    }


    /**
     * ヘッダなしの TS パケットにヘッダを設定する
     * EDCB Legacy WebUI の実装をそのまま移植したもの
     * ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/script.js#L125-L134
     *
     * @param psi_ts_packets ヘッダなしの TS パケット
     * @param pid TS パケットの PID
     */
    private setTSPacketHeader(psi_ts_packets: Uint8Array, pid: number): void {
        this.ts_packet_counters[pid] = this.ts_packet_counters[pid] || 0;
        for (let i = 0; i < psi_ts_packets.length; i += 188) {
            psi_ts_packets[i] = 0x47;
            psi_ts_packets[i + 1] = (i > 0 ? 0 : 0x40) | (pid >> 8);
            psi_ts_packets[i + 2] = pid;
            psi_ts_packets[i + 3] = 0x10 | this.ts_packet_counters[pid];
            this.ts_packet_counters[pid] = (this.ts_packet_counters[pid] + 1) & 0xf;
        }
    }


    /**
     * PSI/SI アーカイブデータを読み込み、PSI/SI TS を生成する
     * EDCB Legacy WebUI の実装をそのまま移植したもので、正直どう動いているのか全く理解できていない…
     * ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/script.js#L1-L123
     *
     * @param buffer PSI/SI アーカイブデータ
     * @param start_second 読み込みを開始する秒数
     * @param callback PSI/SI アーカイブデータから生成した PSI/SI TS を返すコールバック関数
     * @returns ロード済みの PSI/SI アーカイブデータ（？）
     */
    private readPSIArchivedDataChunk(
        buffer: ArrayBuffer,
        start_second: number,
        callback: (second: number, psi_ts_packets: Uint8Array, pid: number) => void,
    ): ArrayBuffer | null {
        const data = new DataView(buffer);

        if (!this.psi_archived_data_context.pids) {
            this.psi_archived_data_context.pids = [];
            this.psi_archived_data_context.dict = [];
            this.psi_archived_data_context.position = 0;
            this.psi_archived_data_context.trailer_size = 0;
            this.psi_archived_data_context.time_list_count = -1;
            this.psi_archived_data_context.code_list_position = 0;
            this.psi_archived_data_context.code_count = 0;
            this.psi_archived_data_context.init_time = -1;
            this.psi_archived_data_context.curr_time = -1;
        }

        while (data.byteLength - this.psi_archived_data_context.position! >= this.psi_archived_data_context.trailer_size! + 32) {
            let position = this.psi_archived_data_context.position! + this.psi_archived_data_context.trailer_size!;
            const time_list_len = data.getUint16(position + 10, true);
            const dictionary_len = data.getUint16(position + 12, true);
            const dictionary_window_len = data.getUint16(position + 14, true);
            const dictionary_data_size = data.getUint32(position + 16, true);
            const dictionary_buffer_size = data.getUint32(position + 20, true);
            const code_list_len = data.getUint32(position + 24, true);

            if (
                data.getUint32(position) != 0x50737363 ||
                data.getUint32(position + 4) != 0x0d0a9a0a ||
                dictionary_window_len < dictionary_len ||
                dictionary_buffer_size < dictionary_data_size ||
                dictionary_window_len > 65536 - 4096
            ) {
                return null;
            }

            const chunk_size = 32 + time_list_len * 4 + dictionary_len * 2 + Math.ceil(dictionary_data_size / 2) * 2 + code_list_len * 2;

            if (data.byteLength - position < chunk_size) break;

            let time_list_position = position + 32;
            position += 32 + time_list_len * 4;

            if (this.psi_archived_data_context.time_list_count! < 0) {
                const pids: number[] = [];
                const dict: (Uint8Array | null)[] = [];
                let section_list_position = 0;

                for (let i = 0; i < dictionary_len; i++, position += 2) {
                    const code_or_size = data.getUint16(position, true) - 4096;
                    if (code_or_size >= 0) {
                        if (code_or_size >= this.psi_archived_data_context.pids.length || this.psi_archived_data_context.pids[code_or_size] < 0) {
                            return null;
                        }
                        pids[i] = this.psi_archived_data_context.pids[code_or_size];
                        dict[i] = this.psi_archived_data_context.dict![code_or_size];
                        this.psi_archived_data_context.pids[code_or_size] = -1;
                    } else {
                        pids[i] = code_or_size;
                        dict[i] = null;
                        section_list_position += 2;
                    }
                }
                section_list_position += position;

                for (let i = 0; i < dictionary_len; i++) {
                    if (pids[i] >= 0) {
                        continue;
                    }
                    const psi = new Uint8Array(data.buffer, section_list_position, pids[i] + 4097);
                    dict[i] = new Uint8Array(Math.ceil((psi.length + 1) / 184) * 188);
                    for (let j = 0, k = 0; k < psi.length; j++, k++) {
                        if (!(j % 188)) {
                            j += 4;
                            if (!k) {
                                dict[i]![j++] = 0;
                            }
                        }
                        dict[i]![j] = psi[k];
                    }
                    section_list_position += psi.length;
                    pids[i] = data.getUint16(position, true) & 0x1fff;
                    position += 2;
                }

                for (let i = dictionary_len, j = 0; i < dictionary_window_len; j++) {
                    if (j >= this.psi_archived_data_context.pids.length) return null;
                    if (this.psi_archived_data_context.pids[j] < 0) continue;
                    pids[i] = this.psi_archived_data_context.pids[j];
                    dict[i++] = this.psi_archived_data_context.dict![j];
                }
                this.psi_archived_data_context.pids = pids;
                this.psi_archived_data_context.dict = dict;
                this.psi_archived_data_context.time_list_count = 0;
                position = section_list_position + dictionary_data_size % 2;
            } else {
                position += dictionary_len * 2 + Math.ceil(dictionary_data_size / 2) * 2;
            }

            position += this.psi_archived_data_context.code_list_position!;
            time_list_position += this.psi_archived_data_context.time_list_count! * 4;
            for (; this.psi_archived_data_context.time_list_count! < time_list_len; this.psi_archived_data_context.time_list_count!++, time_list_position += 4) {
                let init_time = this.psi_archived_data_context.init_time!;
                let curr_time = this.psi_archived_data_context.curr_time!;
                const abs_time = data.getUint32(time_list_position, true);
                if (abs_time === 0xffffffff) {
                    curr_time = -1;
                } else if (abs_time >= 0x80000000) {
                    curr_time = abs_time & 0x3fffffff;
                    if (init_time < 0) {
                        init_time = curr_time;
                    }
                } else {
                    const n = data.getUint16(time_list_position + 2, true) + 1;
                    if (curr_time >= 0) {
                        curr_time += data.getUint16(time_list_position, true);
                        const sec = ((curr_time + 0x40000000 - init_time) & 0x3fffffff) / 11250;
                        if (sec >= (start_second || 0)) {
                            for (; this.psi_archived_data_context.code_count! < n; this.psi_archived_data_context.code_count!++, position += 2, this.psi_archived_data_context.code_list_position! += 2) {
                                const code = data.getUint16(position, true) - 4096;
                                callback(sec, this.psi_archived_data_context.dict![code]!, this.psi_archived_data_context.pids[code]);
                            }
                            this.psi_archived_data_context.code_count = 0;
                        } else {
                            position += n * 2;
                            this.psi_archived_data_context.code_list_position! += n * 2;
                        }
                    } else {
                        position += n * 2;
                        this.psi_archived_data_context.code_list_position! += n * 2;
                    }
                }
                this.psi_archived_data_context.init_time = init_time;
                this.psi_archived_data_context.curr_time = curr_time;
            }

            this.psi_archived_data_context.position = position;
            this.psi_archived_data_context.trailer_size = 2 + (2 + chunk_size) % 4;
            this.psi_archived_data_context.time_list_count = -1;
            this.psi_archived_data_context.code_list_position = 0;
            this.psi_archived_data_context.curr_time = -1;
        }
        const ret = data.buffer.slice(this.psi_archived_data_context.position!);
        this.psi_archived_data_context.position = 0;
        return ret;
    }
}

Comlink.expose(LivePSIArchivedDataDecoder);
