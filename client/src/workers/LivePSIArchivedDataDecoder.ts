
import assert from 'assert';
import { Buffer } from 'buffer';

import { TsChar, TsDate } from '@tsukumijima/aribts';
import { EIT } from '@tsukumijima/aribts/lib/table/eit';
import * as Comlink from 'comlink';
import { decodeTS, ResponseMessage } from 'web-bml/worker';

import { ILiveChannel } from '@/services/Channels';
import { IProgram, IProgramPF, IProgramDefault } from '@/services/Programs';
import Utils, { dayjs, ProgramUtils } from '@/utils';


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
    run(decoded_callback: (message: ResponseMessage | IProgramPF) => void): void;
    destroy(): void;
}

export interface ILivePSIArchivedDataDecoderConstructor {
    new (channel: ILiveChannel, api_quality: string): ILivePSIArchivedDataDecoder;
}


/**
 * ライブ PSI/SI アーカイブデータストリーミング API から取得した PSI/SI アーカイブデータをデコードする
 * 直接は呼び出さず、LivePSIArchivedDataDecoderProxy (Comlink) 経由で Web Worker 上で実行する
 */
class LivePSIArchivedDataDecoder implements ILivePSIArchivedDataDecoder {

    // 対象のチャンネル情報
    private readonly channel: ILiveChannel;

    // 現在視聴中の API 上の画質 ID (ex: 1080p-60fps)
    private readonly api_quality: string;

    // PSI/SI アーカイブデータの読み込みに必要な情報
    private psi_archived_data: Uint8Array = new Uint8Array(0);
    private psi_archived_data_api_abort_controller: AbortController | null = null;
    private psi_archived_data_context: IPSIArchivedDataContext = {};
    private ts_packet_counters: {[index: number]: number} = {};

    /**
     * コンストラクタ
     * ここで渡すチャンネル情報はメインスレッドから渡された後は当然更新されないが、実際に利用するのは不変のチャンネル ID 系のみなので問題ない
     * @param channel 対象のチャンネル情報
     * @param api_quality 現在視聴中の API 上の画質 ID (ex: 1080p-60fps)
     */
    constructor(channel: ILiveChannel, api_quality: string) {
        this.channel = channel;
        this.api_quality = api_quality;
    }


    /**
     * PSI/SI アーカイブデータのストリーミングを開始し、TS ストリームをデコードする
     * デコード結果は decoded_callback に送信される
     *
     * EDCB Legacy WebUI での実装を参考にした
     * ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/util.lua#L444-L497
     */
    public run(decoded_callback: (message: ResponseMessage | IProgramPF) => void): void {

        // TS ストリームがデコードされた際のハンドラーをセット
        // web-bml には字幕表示機能もあるが、mpegts.js 側で既に対応しているため敢えて無効化している
        const ts_stream = decodeTS({
            // TS ストリームをデコードした結果をメインスレッドの BML ブラウザに送信
            sendCallback: (message) => decoded_callback(message),
            serviceId: this.channel.service_id,
            // ARIB 字幕は PES に含まれるため PES パケットをパースする必要があるが、ここでは無効化
            parsePES: false,
        });

        // EIT[p/f] のみ web-bml の decodeTS でデコードできる情報 (ProgramInfoMessage など) だけでは不十分なため、
        // 独自に EIT[p/f] のデコード処理を行い IProgramPF を生成する
        ts_stream.on('eit', (pid: number, eit: EIT) => {

            // pid: 0x0012 / table_id: 0x4e (EIT[p/f]) に絞り込む
            if (pid !== 0x0012 || eit.table_id !== 0x4e) {
                return;
            }

            // EIT[p/f] のイベント情報をデコード/解析し、IProgram を生成する
            const program = this.generateIProgramFromEPG(eit);
            if (program === null) {
                return;  // 処理対象の EIT[p/f] ではないので無視
            }

            // section_number が 0 なら現在放送中の番組情報、1 なら次の番組情報
            const present_or_following = eit.section_number === 0 ? 'Present' : 'Following';

            // メインスレッドに送信
            decoded_callback({
                type: 'IProgramPF',
                present_or_following: present_or_following,
                program: program,
            });
        });

        // ライブ PSI/SI アーカイブデータストリーミング API の URL を作成
        const psi_archived_data_api_url = `${Utils.api_base_url}/streams/live/${this.channel.display_channel_id}/${this.api_quality}/psi-archived-data`;

        // ライブ PSI/SI アーカイブデータストリーミング API にリクエスト
        // 以降の処理はエンドレスなので非同期で実行
        this.psi_archived_data_api_abort_controller = new AbortController();
        fetch(psi_archived_data_api_url, {signal: this.psi_archived_data_api_abort_controller.signal}).then(async (response) => {

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
     * EIT[p/f] のイベント情報をデコード/解析し、IProgram を生成する
     * 各 EPG データの文字列のフォーマット処理は KonomiTV サーバーでの実装と同等
     * @param eit EIT[p/f]
     */
    private generateIProgramFromEPG(eit: EIT): IProgram | null {

        // 以下は以前書いた EITViewer のコードを参考にした
        // ref: https://github.com/tsukumijima/EITViewer/blob/master/EITViewer.ts

        // 番組開始時刻/番組長未定の場合の生の値
        const UNKNOWN_START_TIME = Buffer.from([0xFF, 0xFF, 0xFF, 0xFF, 0xFF]);
        const UNKNOWN_DURATION = Buffer.from([0xFF, 0xFF, 0xFF]);

        // 有効でない EIT を除外
        // current_next_indicator (カレントネクスト指示): テーブルが現在使用可能である場合は "1" とし、
        // テーブルが現在使用不可であり次に有効となることを示す場合は "0" とする
        if (eit.events === null || eit.events.length !== 1 || eit.current_next_indicator === 0) {
            return null;
        }

        // network_id / service_id が一致しない
        if (eit.original_network_id !== this.channel.network_id || eit.service_id !== this.channel.service_id) {
            return null;
        }

        // 雛形とする IProgram をコピー
        const program = structuredClone(IProgramDefault);

        // ID 系
        const event = eit.events[0];
        program.id = `NID${eit.original_network_id}-SID${eit.service_id}-EID${event.event_id}`;
        program.channel_id = `NID${eit.original_network_id}-SID${eit.service_id}`;
        program.network_id = eit.original_network_id;
        program.service_id = eit.service_id;
        program.event_id = event.event_id;
        program.is_free = event.free_CA_mode === 0;  // 0: 無料番組 / 1: 有料番組

        // 番組開始時刻
        if (UNKNOWN_START_TIME.compare(event.start_time) === 0) {
            // 番組開始時刻が未定の場合は IProgramDefault でも使われている初期値をセット
            program.start_time = '2000-01-01T00:00:00+09:00';
        } else {
            program.start_time = dayjs(new TsDate(event.start_time).decode()).format();
        }

        // 番組長
        if (UNKNOWN_DURATION.compare(event.duration) === 0) {
            // 番組長が未定の場合は Infinity をセット
            // duration が Infinity の場合、ProgramUtils.getProgramTime() は「放送時間未定」と表示する
            program.duration = Infinity;
        } else {
            const duration = new TsDate(event.duration).decodeTime();
            program.duration = duration[0] * 3600 + duration[1] * 60 + duration[2];
        }

        // 番組開始時刻と番組長から番組終了時刻を算出
        // ただし、番組長が未定の場合は便宜上番組終了時刻を番組開始時刻と同一の時刻にする
        if (program.duration === Infinity) {
            program.end_time = program.start_time;
        } else {
            program.end_time = dayjs(program.start_time).add(program.duration, 'second').format();
        }

        // IProgram の生成に必要な記述子を取得
        const descriptors = event.descriptors;
        const short_event_descriptor = descriptors.find(d => d.descriptor_tag === 0x4D) ?? null;  // 短形式イベント記述子
        const extended_event_descriptors = descriptors.filter(d => d.descriptor_tag === 0x4E);  // 拡張形式イベント記述子 (これのみ複数必要)
        const content_descriptor = descriptors.find(d => d.descriptor_tag === 0x54) ?? null;  // コンテント記述子
        const video_component_descriptor = descriptors.find(d => d.descriptor_tag === 0x50) ?? null;  // コンポーネント記述子
        const audio_component_descriptor_primary =
            descriptors.find(d => d.descriptor_tag === 0xC4 && d.main_component_flag === 1) ?? null;  // 音声コンポーネント記述子 (主音声)
        const audio_component_descriptor_secondary =
            descriptors.find(d => d.descriptor_tag === 0xC4 && d.main_component_flag !== 1) ?? null;  // 音声コンポーネント記述子 (副音声)

        // タイトル・番組概要
        if (short_event_descriptor !== null) {
            program.title = ProgramUtils.formatString(new TsChar(short_event_descriptor.event_name_char).decode());
            program.description = ProgramUtils.formatString(new TsChar(short_event_descriptor.text_char).decode());
        } else {
            // 運用上短形式イベント記述子は必ず送出されているはずだが、念のため
            program.title = '番組情報がありません';
            program.description = 'この時間の番組情報を取得できませんでした。';
        }

        // 番組詳細
        // 拡張形式イベント記述子が送出されていない場合はデフォルト値の {} がセットされる
        // ariblib/event.py での実装と server/app/metadata/TSInfoAnalyzer.py での実装をマージしたもの
        const detail_array: {head: string, raw_text: Buffer}[] = [];
        for (const extended_event_descriptor of extended_event_descriptors) {
            // 一応 items 内の item が複数あることを想定してループしているが、運用上は1つしか存在しないはず (?)
            for (const item of extended_event_descriptor.items) {
                // 項目名が空の場合のみ、本文をバイナリレベルで一つ前のものにつなげてからデコードする
                // ref: ARIB TR-B14 第四分冊 第四編 第1部 4.4.3
                if (item.item_description_length === 0) {
                    detail_array[detail_array.length - 1].raw_text = Buffer.concat([detail_array[detail_array.length - 1].raw_text, item.item_char]);
                } else {
                    let head = ProgramUtils.formatString(new TsChar(item.item_description_char).decode());
                    // 項目名が重複する場合はタブ文字を追加して区別する
                    const original_head = head;
                    let tab_suffix = '';
                    while (detail_array.some(detail => detail.head === original_head + tab_suffix)) {
                        tab_suffix += '\t';
                    }
                    head += tab_suffix;
                    detail_array.push({head: head, raw_text: item.item_char});
                }
            }
        }
        for (const detail of detail_array) {
            // 見出し
            // 意図的に重複防止のためのタブ文字付加が行われる場合があるため、
            // trim() ではなく明示的に半角スペースと改行のみを指定した replace() を使っている
            let head_hankaku = ProgramUtils.formatString(detail.head).replaceAll('◇', '').replace(/[ \r\n]+/g, '');  // ◇ を取り除く
            // 見出しが空の場合、固定で「番組内容」としておく
            if (head_hankaku === '') {
                head_hankaku = '番組内容';
            }
            // 本文
            const text_hankaku = ProgramUtils.formatString(new TsChar(detail.raw_text).decode()).trim();
            // この時点で番組概要が空の場合、番組詳細の最初の本文を概要として使う
            // 空でまったく情報がないよりかは良いはず
            if (program.description.trim() === '') {
                program.description = text_hankaku;
            }
            program.detail[head_hankaku] = text_hankaku;
        }

        // ジャンル
        // server/app/models/Program.py 内の処理ロジックを移植したもの
        if (content_descriptor !== null) {
            for (const content of content_descriptor.contents) {
                const genre_tuple = ProgramUtils.CONTENT_TYPE[content.content_nibble_level_1] ?? null;
                if (genre_tuple !== null) {
                    // major: 大分類
                    // middle: 中分類
                    const genre_dict = {
                        'major': genre_tuple[0] as string,
                        'middle': (genre_tuple[1][content.content_nibble_level_2] ?? '未定義') as string,
                    };
                    // BS/地上デジタル放送用番組付属情報がジャンルに含まれている場合、user_nibble から値を取得して書き換える
                    // たとえば「中止の可能性あり」や「延長の可能性あり」といった情報が取れる
                    if (genre_dict['major'] === '拡張') {
                        if (genre_dict['middle'] === 'BS/地上デジタル放送用番組付属情報') {
                            const user_nibble = (content.user_nibble_1 * 0x10) + content.user_nibble_2;
                            genre_dict['middle'] = ProgramUtils.USER_TYPE[user_nibble] ?? '未定義';
                        } else {
                            // 「拡張」はあるがBS/地上デジタル放送用番組付属情報でない場合はなんの値なのかわからないのでパス
                            continue;
                        }
                    }
                    program.genres.push(genre_dict);
                }
            }
        }

        // 映像情報
        // server/app/models/Program.py 内の処理ロジックを移植したもの
        if (video_component_descriptor !== null) {
            // 映像の種類
            const component_types = ProgramUtils.COMPONENT_TYPE[video_component_descriptor.stream_content] ?? null;
            if (component_types !== null) {
                program.video_type = component_types[video_component_descriptor.component_type] ?? null;
            }
            // 映像のコーデック
            program.video_codec = ProgramUtils.STREAM_CONTENT[video_component_descriptor.stream_content] ?? null;
            // 映像の解像度
            program.video_resolution = ProgramUtils.VIDEO_COMPONENT_TYPE[video_component_descriptor.component_type] ?? null;
        } else {
            // ラジオチャンネルなど映像情報がない場合
            program.video_type = null;
            program.video_resolution = null;
            program.video_codec = null;
        }

        // 音声情報 (主音声)
        // server/app/models/Program.py 内の処理ロジックを移植したもの
        if (audio_component_descriptor_primary !== null) {
            // 音声の種類
            program.primary_audio_type = ProgramUtils.COMPONENT_TYPE[0x02][audio_component_descriptor_primary.component_type] ?? '';
            program.primary_audio_language =
                ProgramUtils.getISO639LanguageCodeName(String.fromCharCode(...audio_component_descriptor_primary.ISO_639_language_code));
            program.primary_audio_sampling_rate = ProgramUtils.SAMPLING_RATE[audio_component_descriptor_primary.sampling_rate] ?? '';
            // デュアルモノのみ
            if (program.primary_audio_type == '1/0+1/0モード(デュアルモノ)') {
                if (audio_component_descriptor_primary.ES_multi_lingual_flag === 1) {
                    program.primary_audio_language += '+' +
                        ProgramUtils.getISO639LanguageCodeName(String.fromCharCode(...audio_component_descriptor_primary.ISO_639_language_code_2));
                } else {
                    program.primary_audio_language += '+副音声';  // 副音声で固定
                }
            }
        } else {
            // 運用上音声コンポーネント記述子 (主音声) は必ず送出されているはずだが、念のため
            // 型定義上 null は許容していないのでひとまず空文字列をセット
            program.primary_audio_type = '';
            program.primary_audio_language = '';
            program.primary_audio_sampling_rate = '';
        }

        // 音声情報 (副音声)
        // server/app/models/Program.py 内の処理ロジックを移植したもの
        if (audio_component_descriptor_secondary !== null) {
            // 音声の種類
            program.secondary_audio_type = ProgramUtils.COMPONENT_TYPE[0x02][audio_component_descriptor_secondary.component_type] ?? '';
            program.secondary_audio_language =
                ProgramUtils.getISO639LanguageCodeName(String.fromCharCode(...audio_component_descriptor_secondary.ISO_639_language_code));
            program.secondary_audio_sampling_rate = ProgramUtils.SAMPLING_RATE[audio_component_descriptor_secondary.sampling_rate] ?? '';
            // デュアルモノのみ
            if (program.secondary_audio_type == '1/0+1/0モード(デュアルモノ)') {
                if (audio_component_descriptor_secondary.ES_multi_lingual_flag === 1) {
                    program.secondary_audio_language += '+' +
                        ProgramUtils.getISO639LanguageCodeName(String.fromCharCode(...audio_component_descriptor_secondary.ISO_639_language_code_2));
                } else {
                    program.secondary_audio_language += '+副音声';  // 副音声で固定
                }
            }
        } else {
            // 副音声が存在しない場合
            program.secondary_audio_type = null;
            program.secondary_audio_language = null;
            program.secondary_audio_sampling_rate = null;
        }

        // Safari では console.debug() がデフォルトで出力されてしまい煩いので出力しない
        if (Utils.isSafari() === false) {
            console.debug('[PSIArchivedDataDecoder] EIT[p/f] decoded.', program);
        }
        return program;
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
            assert(this.psi_archived_data_context.time_list_count !== undefined);
            for (; this.psi_archived_data_context.time_list_count! < time_list_len; this.psi_archived_data_context.time_list_count++, time_list_position += 4) {
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
                            assert(this.psi_archived_data_context.code_count !== undefined);
                            for (; this.psi_archived_data_context.code_count! < n; this.psi_archived_data_context.code_count++, position += 2, this.psi_archived_data_context.code_list_position! += 2) {
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

// Comlink にクラスをエクスポート
Comlink.expose(LivePSIArchivedDataDecoder);
