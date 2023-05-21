
import DPlayer from 'dplayer';
import { BMLBrowser, BMLBrowserFontFace } from 'web-bml/client/bml_browser';
import { RemoteControl } from 'web-bml/client/remote_controller_client';
import { decodeTS } from 'web-bml/server/decode_ts';

import PlayerManager from '@/services/player/PlayerManager';
import Utils, { PlayerUtils } from '@/utils';


interface IPSIArchivedDataContext {
    pids?: number[];
    dict?: Uint8Array[];
    position?: number;
    trailer_size?: number;
    time_list_count?: number;
    code_list_position?: number;
    code_count?: number;
    init_time?: number;
    curr_time?: number;
}


class LiveDataBroadcastingManager implements PlayerManager {

    private player: DPlayer;
    private display_channel_id: string;
    private container_element: HTMLElement;
    private media_element: HTMLElement;
    private bml_browser: BMLBrowser;

    // PSI/SI アーカイブデータの読み込みに必要な情報
    private psi_archived_data: Uint8Array = new Uint8Array(0);
    private psi_archived_data_api_abort_controller: AbortController = new AbortController();
    private psi_archived_data_context: IPSIArchivedDataContext = {};
    private ts_packet_counters: {[index: number]: number} = {};

    constructor(options: {
        player: DPlayer;
        display_channel_id: string;
    }) {

        this.player = options.player;
        this.display_channel_id = options.display_channel_id;

        // BML文書が入る要素
        // DPlayer 内の dplayer-video-wrap の中に動的に追加する
        const container_element = document.createElement('div');
        container_element.classList.add('dplayer-bml-container');
        this.container_element = this.player.template.videoWrap.insertAdjacentElement('afterbegin', container_element) as HTMLElement;

        // 動画が入っている要素
        // DPlayer 内の dplayer-video-wrap-aspect を使う
        this.media_element = this.player.template.videoWrapAspect;

        // BML 用フォント
        const round_gothic: BMLBrowserFontFace = {
            source: 'url("https://github.com/googlefonts/kosugi-maru/raw/main/fonts/webfonts/KosugiMaru-Regular.woff2"), local("sans-serif")',
        };
        const square_gothic: BMLBrowserFontFace = {
            source: 'url("https://github.com/googlefonts/kosugi/raw/main/fonts/webfonts/Kosugi-Regular.woff2"), local("sans-serif")',
        };

        // リモコンを初期化
        const remote_control = new RemoteControl(document.querySelector('.remote-control')!, document.querySelector('.remote-control-receiving-status')!);

        // BML ブラウザの初期化
        this.bml_browser = new BMLBrowser({
            containerElement: this.container_element,
            mediaElement: this.media_element,
            indicator: remote_control,
            fonts: {
                roundGothic: round_gothic,
                squareGothic: square_gothic,
            },
            epg: {
                tune(originalNetworkId, transportStreamId, serviceId) {
                    // 現状データ放送からのチャンネル切り替えには非対応
                    console.error('tune', originalNetworkId, transportStreamId, serviceId);
                    return false;
                }
            }
        });

        // リモコンに BML ブラウザを設定
        remote_control.content = this.bml_browser.content;
    }


    /**
     * LiveDataBroadcastingManager での処理を開始する
     *
     * EDCB Legacy WebUI での実装を参考にした
     * https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/util.lua#L444-L497
     */
    public async init(): Promise<void> {

        // BML ブラウザのイベントを定義
        this.bml_browser.addEventListener('load', (event) => {
            console.log('BMLBrowser: load', event.detail);
        });
        this.bml_browser.addEventListener('invisible', (event) => {
            if (event.detail === true) {
                console.log('BMLBrowser: invisible');
            } else {
                console.log('BMLBrowser: visible');
            }
        });

        // TS ストリームのデコードを開始
        // PES (字幕) は mpegts.js / LL-HLS 側で既に対応しているため、BML ブラウザ側では対応しない
        const ts_stream = decodeTS({sendCallback: (message) => this.bml_browser.emitMessage(message)});

        // ライブ PSI/SI アーカイブデータストリーミング API にリクエスト
        const api_quality = PlayerUtils.extractAPIQualityFromDPlayer(this.player);
        const api_url = `${Utils.api_base_url}/streams/live/${this.display_channel_id}/${api_quality}/psi-archived-data`;
        const response = await fetch(api_url, {signal: this.psi_archived_data_api_abort_controller.signal});
        const reader = response.body?.getReader();
        if (!reader) return;

        let last_pcr = -1;
        while (true) {

            // API から随時データを取得
            const result = await reader.read();
            if (result.done) {
                break;
            }

            // 今まで受信したデータと結合
            const add_data: Uint8Array = result.value;
            const concat_data = new Uint8Array(this.psi_archived_data.length + add_data.length);
            concat_data.set(this.psi_archived_data);
            concat_data.set(add_data, this.psi_archived_data.length);

            // PSI/SI アーカイブデータから TS パケットを生成し、BML ブラウザに送信
            const psi_archived_data = this.readPSIArchivedData(concat_data.buffer, 0, (second, psi_ts_packets, pid) => {

                // PCR (Packet Clock Reference) を取得して送信
                const pcr = Math.floor(second * 90000);
                if (last_pcr !== pcr) {
                    this.bml_browser.emitMessage({
                        type: 'pcr',
                        pcrBase: pcr,
                        pcrExtension: 0,
                    });
                    last_pcr = pcr;
                }

                // BML ブラウザに TS パケットを送信
                this.setTSPacketHeader(psi_ts_packets, pid);
                ts_stream.parse(Buffer.from(psi_ts_packets.buffer, psi_ts_packets.byteOffset, psi_ts_packets.byteLength));
            });

            // 今回受信したデータを次回に持ち越す
            if (psi_archived_data) {
                this.psi_archived_data = new Uint8Array(psi_archived_data);
            }
        }
    }


    /**
     * LiveDataBroadcastingManager での処理を終了し、破棄する
     */
    public async destroy(): Promise<void> {

        // ライブ PSI/SI アーカイブデータストリーミング API のリクエストを中断
        this.psi_archived_data_api_abort_controller.abort();

        // PSI/SI アーカイブデータを破棄
        this.psi_archived_data = new Uint8Array();

        // BML ブラウザを破棄
        this.bml_browser.destroy();
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
    private readPSIArchivedData(
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
            let pos = this.psi_archived_data_context.position! + this.psi_archived_data_context.trailer_size!;
            const time_list_len = data.getUint16(pos + 10, true);
            const dictionary_len = data.getUint16(pos + 12, true);
            const dictionary_window_len = data.getUint16(pos + 14, true);
            const dictionary_data_size = data.getUint32(pos + 16, true);
            const dictionary_buffer_size = data.getUint32(pos + 20, true);
            const code_list_len = data.getUint32(pos + 24, true);

            if (
                data.getUint32(pos) != 0x50737363 ||
                data.getUint32(pos + 4) != 0x0d0a9a0a ||
                dictionary_window_len < dictionary_len ||
                dictionary_buffer_size < dictionary_data_size ||
                dictionary_window_len > 65536 - 4096
            ) {
                return null;
            }

            const chunkSize = 32 + time_list_len * 4 + dictionary_len * 2 + Math.ceil(dictionary_data_size / 2) * 2 + code_list_len * 2;

            if (data.byteLength - pos < chunkSize) break;

            let timeListPos = pos + 32;
            pos += 32 + time_list_len * 4;

            if (this.psi_archived_data_context.time_list_count < 0) {
                const pids = [];
                const dict = [];
                let sectionListPos = 0;

                for (let i = 0; i < dictionary_len; i++, pos += 2) {
                    const codeOrSize = data.getUint16(pos, true) - 4096;
                    if (codeOrSize >= 0) {
                        if (codeOrSize >= this.psi_archived_data_context.pids.length || this.psi_archived_data_context.pids[codeOrSize] < 0) {
                            return null;
                        }
                        pids[i] = this.psi_archived_data_context.pids[codeOrSize];
                        dict[i] = this.psi_archived_data_context.dict[codeOrSize];
                        this.psi_archived_data_context.pids[codeOrSize] = -1;
                    } else {
                        pids[i] = codeOrSize;
                        dict[i] = null;
                        sectionListPos += 2;
                    }
                }
                sectionListPos += pos;

                for (let i = 0; i < dictionary_len; i++) {
                    if (pids[i] >= 0) {
                        continue;
                    }
                    const psi = new Uint8Array(data.buffer, sectionListPos, pids[i] + 4097);
                    dict[i] = new Uint8Array(Math.ceil((psi.length + 1) / 184) * 188);
                    for (let j = 0, k = 0; k < psi.length; j++, k++) {
                        if (!(j % 188)) {
                            j += 4;
                            if (!k) {
                                dict[i][j++] = 0;
                            }
                        }
                        dict[i][j] = psi[k];
                    }
                    sectionListPos += psi.length;
                    pids[i] = data.getUint16(pos, true) & 0x1fff;
                    pos += 2;
                }

                for (let i = dictionary_len, j = 0; i < dictionary_window_len; j++) {
                    if (j >= this.psi_archived_data_context.pids.length) return null;
                    if (this.psi_archived_data_context.pids[j] < 0) continue;
                    pids[i] = this.psi_archived_data_context.pids[j];
                    dict[i++] = this.psi_archived_data_context.dict[j];
                }
                this.psi_archived_data_context.pids = pids;
                this.psi_archived_data_context.dict = dict;
                this.psi_archived_data_context.time_list_count = 0;
                pos = sectionListPos + dictionary_data_size % 2;
            } else {
                pos += dictionary_len * 2 + Math.ceil(dictionary_data_size / 2) * 2;
            }

            pos += this.psi_archived_data_context.code_list_position;
            timeListPos += this.psi_archived_data_context.time_list_count * 4;
            for (; this.psi_archived_data_context.time_list_count < time_list_len; this.psi_archived_data_context.time_list_count++, timeListPos += 4) {
                let initTime = this.psi_archived_data_context.init_time;
                let currTime = this.psi_archived_data_context.curr_time;
                const absTime = data.getUint32(timeListPos, true);
                if (absTime == 0xffffffff) {
                    currTime = -1;
                } else if (absTime >= 0x80000000) {
                    currTime = absTime & 0x3fffffff;
                    if (initTime < 0) {
                        initTime = currTime;
                    }
                } else {
                    const n = data.getUint16(timeListPos + 2, true) + 1;
                    if (currTime >= 0) {
                        currTime += data.getUint16(timeListPos, true);
                        const sec = ((currTime + 0x40000000 - initTime) & 0x3fffffff) / 11250;
                        if (sec >= (start_second || 0)) {
                            for (; this.psi_archived_data_context.code_count < n; this.psi_archived_data_context.code_count++, pos += 2, this.psi_archived_data_context.code_list_position += 2) {
                                const code = data.getUint16(pos, true) - 4096;
                                callback(sec, this.psi_archived_data_context.dict[code], this.psi_archived_data_context.pids[code]);
                            }
                            this.psi_archived_data_context.code_count = 0;
                        } else {
                            pos += n * 2;
                            this.psi_archived_data_context.code_list_position += n * 2;
                        }
                    } else {
                        pos += n * 2;
                        this.psi_archived_data_context.code_list_position += n * 2;
                    }
                }
                this.psi_archived_data_context.init_time = initTime;
                this.psi_archived_data_context.curr_time = currTime;
            }

            this.psi_archived_data_context.position = pos;
            this.psi_archived_data_context.trailer_size = 2 + (2 + chunkSize) % 4;
            this.psi_archived_data_context.time_list_count = -1;
            this.psi_archived_data_context.code_list_position = 0;
            this.psi_archived_data_context.curr_time = -1;
        }
        const ret = data.buffer.slice(this.psi_archived_data_context.position);
        this.psi_archived_data_context.position = 0;
        return ret;
    }
}

export default LiveDataBroadcastingManager;
