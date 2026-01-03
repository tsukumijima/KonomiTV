
import { IProgram } from '@/services/Programs';
import { IRecordedProgram } from '@/services/Videos';
import Utils, { dayjs } from '@/utils';


/**
 * 番組情報周りのユーティリティ
 */
export class ProgramUtils {

    // 映像のコーデック
    // ref: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/EPG.ts#L23-L27
    static readonly STREAM_CONTENT = {
        0x01: 'MPEG-2',
        0x05: 'H.264',
        0x09: 'H.265',
    };

    // 映像の解像度
    // ref: https://github.com/Chinachu/Mirakurun/blob/master/src/Mirakurun/EPG.ts#L29-L63
    static readonly VIDEO_COMPONENT_TYPE = {
        0x01: '480i',
        0x02: '480i',
        0x03: '480i',
        0x04: '480i',
        0x83: '4320p',
        0x91: '2160p',
        0x92: '2160p',
        0x93: '2160p',
        0x94: '2160p',
        0xA1: '480p',
        0xA2: '480p',
        0xA3: '480p',
        0xA4: '480p',
        0xB1: '1080i',
        0xB2: '1080i',
        0xB3: '1080i',
        0xB4: '1080i',
        0xC1: '720p',
        0xC2: '720p',
        0xC3: '720p',
        0xC4: '720p',
        0xD1: '240p',
        0xD2: '240p',
        0xD3: '240p',
        0xD4: '240p',
        0xE1: '1080p',
        0xE2: '1080p',
        0xE3: '1080p',
        0xE4: '1080p',
        0xF1: '180p',
        0xF2: '180p',
        0xF3: '180p',
        0xF4: '180p',
    };

    // 以下は ariblib から LivePSIArchivedDataDecoder で必要なもののみ移植
    // node-aribts にも同等の定義があるが微妙に文字列の表記揺れがあるため、互換性を鑑みて敢えて移植している
    // ref: https://github.com/tsukumijima/ariblib/blob/master/ariblib/constants.py

    // ARIB-STD-B10-2-H コンテント記述子におけるジャンル指定
    // KonomiTV では見栄え的な都合で中分類の "／" を "・" に置き換えている (サーバー側も同様)
    static readonly CONTENT_TYPE = {
        0x0: ['ニュース・報道', {
            0x0: '定時・総合',
            0x1: '天気',
            0x2: '特集・ドキュメント',
            0x3: '政治・国会',
            0x4: '経済・市況',
            0x5: '海外・国際',
            0x6: '解説',
            0x7: '討論・会談',
            0x8: '報道特番',
            0x9: 'ローカル・地域',
            0xA: '交通',
            0xF: 'その他',
        }],
        0x1: ['スポーツ', {
            0x0: 'スポーツニュース',
            0x1: '野球',
            0x2: 'サッカー',
            0x3: 'ゴルフ',
            0x4: 'その他の球技',
            0x5: '相撲・格闘技',
            0x6: 'オリンピック・国際大会',
            0x7: 'マラソン・陸上・水泳',
            0x8: 'モータースポーツ',
            0x9: 'マリン・ウィンタースポーツ',
            0xA: '競馬・公営競技',
            0xF: 'その他',
        }],
        0x2: ['情報・ワイドショー', {
            0x0: '芸能・ワイドショー',
            0x1: 'ファッション',
            0x2: '暮らし・住まい',
            0x3: '健康・医療',
            0x4: 'ショッピング・通販',
            0x5: 'グルメ・料理',
            0x6: 'イベント',
            0x7: '番組紹介・お知らせ',
            0xF: 'その他',
        }],
        0x3: ['ドラマ', {
            0x0: '国内ドラマ',
            0x1: '海外ドラマ',
            0x2: '時代劇',
            0xF: 'その他',
        }],
        0x4: ['音楽', {
            0x0: '国内ロック・ポップス',
            0x1: '海外ロック・ポップス',
            0x2: 'クラシック・オペラ',
            0x3: 'ジャズ・フュージョン',
            0x4: '歌謡曲・演歌',
            0x5: 'ライブ・コンサート',
            0x6: 'ランキング・リクエスト',
            0x7: 'カラオケ・のど自慢',
            0x8: '民謡・邦楽',
            0x9: '童謡・キッズ',
            0xA: '民族音楽・ワールドミュージック',
            0xF: 'その他',
        }],
        0x5: ['バラエティ', {
            0x0: 'クイズ',
            0x1: 'ゲーム',
            0x2: 'トークバラエティ',
            0x3: 'お笑い・コメディ',
            0x4: '音楽バラエティ',
            0x5: '旅バラエティ',
            0x6: '料理バラエティ',
            0xF: 'その他',
        }],
        0x6: ['映画', {
            0x0: '洋画',
            0x1: '邦画',
            0x2: 'アニメ',
            0xF: 'その他',
        }],
        0x7: ['アニメ・特撮', {
            0x0: '国内アニメ',
            0x1: '海外アニメ',
            0x2: '特撮',
            0xF: 'その他',
        }],
        0x8: ['ドキュメンタリー・教養', {
            0x0: '社会・時事',
            0x1: '歴史・紀行',
            0x2: '自然・動物・環境',
            0x3: '宇宙・科学・医学',
            0x4: 'カルチャー・伝統文化',
            0x5: '文学・文芸',
            0x6: 'スポーツ',
            0x7: 'ドキュメンタリー全般',
            0x8: 'インタビュー・討論',
            0xF: 'その他',
        }],
        0x9: ['劇場・公演', {
            0x0: '現代劇・新劇',
            0x1: 'ミュージカル',
            0x2: 'ダンス・バレエ',
            0x3: '落語・演芸',
            0x4: '歌舞伎・古典',
            0xF: 'その他',
        }],
        0xA: ['趣味・教育', {
            0x0: '旅・釣り・アウトドア',
            0x1: '園芸・ペット・手芸',
            0x2: '音楽・美術・工芸',
            0x3: '囲碁・将棋',
            0x4: '麻雀・パチンコ',
            0x5: '車・オートバイ',
            0x6: 'コンピュータ・ＴＶゲーム',
            0x7: '会話・語学',
            0x8: '幼児・小学生',
            0x9: '中学生・高校生',
            0xA: '大学生・受験',
            0xB: '生涯教育・資格',
            0xC: '教育問題',
            0xF: 'その他',
        }],
        0xB: ['福祉', {
            0x0: '高齢者',
            0x1: '障害者',
            0x2: '社会福祉',
            0x3: 'ボランティア',
            0x4: '手話',
            0x5: '文字（字幕）',
            0x6: '音声解説',
            0xF: 'その他',
        }],
        0xE: ['拡張', {
            0x0: 'BS/地上デジタル放送用番組付属情報',
            0x1: '広帯域CSデジタル放送用拡張',
            0x2: '衛星デジタル音声放送用拡張',
            0x3: 'サーバー型番組付属情報',
            0x4: 'IP放送用番組付属情報',
        }],
        0xF: ['その他', {
            0xF: 'その他',
        }],
    };

    // ARIB-TR-B24-4.B 表B-1 地上デジタルテレビジョン放送用番組付属情報
    // ARIB-TR-B25-4.B 表B-1 BSデジタル放送用番組付属情報
    static readonly USER_TYPE = {
        0x00: '中止の可能性あり',
        0x01: '延長の可能性あり',
        0x02: '中断の可能性あり',
        0x03: '同一シリーズの別話数放送の可能性あり',
        0x04: '編成未定枠',
        0x05: '繰り上げの可能性あり',
        0x10: '中断ニュースあり',
        0x11: '当該イベントに関連する臨時サービスあり',
        0x20: '当該イベント中に3D映像あり',
    };

    // ARIB-STD-B10-2-6.2.3 表6-5 コンポーネント内容とコンポーネント種別
    static readonly COMPONENT_TYPE = {
        0x01: {
            0x00: '将来使用のためリザーブ',
            0x01: '映像480i(525i)、アスペクト比4:3',
            0x02: '映像480i(525i)、アスペクト比16:9 パンベクトルあり',
            0x03: '映像480i(525i)、アスペクト比16:9 パンベクトルなし',
            0x04: '映像480i(525i)、アスペクト比16:9',
            0x91: '映像2160p、アスペクト比4:3',
            0x92: '映像2160p、アスペクト比16:9 パンベクトルあり',
            0x93: '映像2160p、アスペクト比16:9 パンベクトルなし',
            0x94: '映像2160p、アスペクト比16:9',
            0xA1: '映像480p(525p)、アスペクト比4:3',
            0xA2: '映像480p(525p)、アスペクト比16:9 パンベクトルあり',
            0xA3: '映像480p(525p)、アスペクト比16:9 パンベクトルなし',
            0xA4: '映像480p(525p)、アスペクト比16:9',
            0xB1: '映像1080i(1125i)、アスペクト比4:3',
            0xB2: '映像1080i(1125i)、アスペクト比16:9 パンベクトルあり',
            0xB3: '映像1080i(1125i)、アスペクト比16:9 パンベクトルなし',
            0xB4: '映像1080i(1125i)、アスペクト比16:9',
            0xC1: '映像720p(750p)、アスペクト比4:3',
            0xC2: '映像720p(750p)、アスペクト比16:9 パンベクトルあり',
            0xC3: '映像720p(750p)、アスペクト比16:9 パンベクトルなし',
            0xC4: '映像720p(750p)、アスペクト比16:9',
            0xD1: '映像240p アスペクト比4:3',
            0xD2: '映像240p アスペクト比16:9 パンベクトルあり',
            0xD3: '映像240p アスペクト比16:9 パンベクトルなし',
            0xD4: '映像240p アスペクト比16:9',
            0xE1: '映像1080p(1125p)、アスペクト比4:3',
            0xE2: '映像1080p(1125p)、アスペクト比16:9 パンベクトルあり',
            0xE3: '映像1080p(1125p)、アスペクト比16:9 パンベクトルなし',
            0xE4: '映像1080p(1125p)、アスペクト比16:9',
            0xF1: '映像180p アスペクト比4:3',
            0xF2: '映像180p アスペクト比16:9 パンベクトルあり',
            0xF3: '映像180p アスペクト比16:9 パンベクトルなし',
            0xF4: '映像180p アスペクト比16:9',
        },
        0x02: {
            0x00: '将来使用のためリザーブ',
            0x01: '1/0モード(シングルモノ)',
            0x02: '1/0+1/0モード(デュアルモノ)',
            0x03: '2/0モード(ステレオ)',
            0x04: '2/1モード',
            0x05: '3/0モード',
            0x06: '2/2モード',
            0x07: '3/1モード',
            0x08: '3/2モード',
            0x09: '3/2+LFEモード(3/2.1モード)',
            0x0A: '3/3.1モード',
            0x0B: '2/0/0-2/0/2-0.1モード',
            0x0C: '5/2.1モード',
            0x0D: '3/2/2.1モード',
            0x0E: '2/0/0-3/0/2-0.1モード',
            0x0F: '0/2/0-3/0/2-0.2モード',
            0x10: '2/0/0-3/2/3-0.2モード',
            0x11: '3/3/3-5/2/3-3/0/0.2モード',
            0x40: '視覚障害者用音声解説',
            0x41: '聴覚障害者用音声',
        },
        0x05: {
            0x01: 'H.264|MPEG-4 AVC、映像480i(525i)、アスペクト比4:3',
            0x02: 'H.264|MPEG-4 AVC、映像480i(525i)、アスペクト比16:9 パンベクトルあり',
            0x03: 'H.264|MPEG-4 AVC、映像480i(525i)、アスペクト比16:9 パンベクトルなし ',
            0x04: 'H.264|MPEG-4 AVC、映像480i(525i)、アスペクト比 > 16:9',
            0x91: 'H.264|MPEG-4 AVC、映像2160p、アスペクト比4:3',
            0x92: 'H.264|MPEG-4 AVC、映像2160p、アスペクト比16:9 パンベクトルあり',
            0x93: 'H.264|MPEG-4 AVC、映像2160p、アスペクト比16:9 パンベクトルなし',
            0x94: 'H.264|MPEG-4 AVC、映像2160p、アスペクト比 > 16:9',
            0xA1: 'H.264|MPEG-4 AVC、映像480p(525p)、アスペクト比4:3',
            0xA2: 'H.264|MPEG-4 AVC、映像480p(525p)、アスペクト比16:9 パンベクトルあり',
            0xA3: 'H.264|MPEG-4 AVC、映像480p(525p)、アスペクト比16:9 パンベクトルなし',
            0xA4: 'H.264|MPEG-4 AVC、映像480p(525p)、アスペクト比 > 16:9',
            0xB1: 'H.264|MPEG-4 AVC、映像1080i(1125i)、アスペクト比4:3',
            0xB2: 'H.264|MPEG-4 AVC、映像1080i(1125i)、アスペクト比16:9 パンベクトルあり',
            0xB3: 'H.264|MPEG-4 AVC、映像1080i(1125i)、アスペクト比16:9 パンベクトルなし',
            0xB4: 'H.264|MPEG-4 AVC、映像1080i(1125i)、アスペクト比 > 16:9',
            0xC1: 'H.264|MPEG-4 AVC、映像720p(750p)、アスペクト比4:3',
            0xC2: 'H.264|MPEG-4 AVC、映像720p(750p)、アスペクト比16:9 パンベクトルあり',
            0xC3: 'H.264|MPEG-4 AVC、映像720p(750p)、アスペクト比16:9 パンベクトルなし',
            0xC4: 'H.264|MPEG-4 AVC、映像720p(750p)、アスペクト比 > 16:9',
            0xD1: 'H.264|MPEG-4 AVC、映像240p アスペクト比4:3',
            0xD2: 'H.264|MPEG-4 AVC、映像240p アスペクト比16:9 パンベクトルあり',
            0xD3: 'H.264|MPEG-4 AVC、映像240p アスペクト比16:9 パンベクトルなし',
            0xD4: 'H.264|MPEG-4 AVC、映像240p アスペクト比 > 16:9',
            0xE1: 'H.264|MPEG-4 AVC、映像1080p(1125p)、アスペクト比4:3',
            0xE2: 'H.264|MPEG-4 AVC、映像1080p(1125p)、アスペクト比16:9 パンベクトルあり',
            0xE3: 'H.264|MPEG-4 AVC、映像1080p(1125p)、アスペクト比16:9 パンベクトルなし',
            0xE4: 'H.264|MPEG-4 AVC、映像1080p(1125p)、アスペクト比 > 16:9',
            0xF1: 'H.264|MPEG-4 AVC、映像180p アスペクト比4:3',
            0xF2: 'H.264|MPEG-4 AVC、映像180p アスペクト比16:9 パンベクトルあり',
            0xF3: 'H.264|MPEG-4 AVC、映像180p アスペクト比16:9 パンベクトルなし',
            0xF4: 'H.264|MPEG-4 AVC、映像180p アスペクト比 > 16:9',
        },
    };

    // ARIB-STD-B10-2-6.2.26 表6-45 サンプリング周波数
    static readonly SAMPLING_RATE = {
        0b000: '将来使用のためリザーブ',
        0b001: '16kHz',
        0b010: '22.05kHz',
        0b011: '24kHz',
        0b100: 'リザーブ',
        0b101: '32kHz',
        0b110: '44.1kHz',
        0b111: '48kHz',
    };

    // 事前に文字列の変換テーブルを構築しておく
    private static readonly format_string_translation_map = ProgramUtils.buildFormatStringTranslationMap();


    /**
     * 番組がショッピング・通販枠かどうかを判定する
     * @param program 番組情報
     * @returns ショッピング・通販枠なら true
     */
    static isShoppingProgram(program: IProgram): boolean {
        return program.genres?.some((genre) => genre.middle === 'ショッピング・通販') ?? false;
    }


    /**
     * 番組情報中の[字]や[解]などの記号をいい感じに装飾する
     * @param program 番組情報のオブジェクト
     * @param key 番組情報のオブジェクトから取り出すプロパティのキー
     * @returns 装飾した文字列
     */
    static decorateProgramInfo(program: IProgram | IRecordedProgram | null, key: string): string {

        // program が空でないかつ、program[key] が存在する
        if (program !== null && program[key] !== null) {

            // 番組情報に含まれる HTML の特殊文字で表示がバグらないように、事前に HTML エスケープしておく
            const text = Utils.escapeHTML(program[key]);

            // 本来 ARIB 外字である記号の一覧
            // ref: https://ja.wikipedia.org/wiki/%E7%95%AA%E7%B5%84%E8%A1%A8
            // ref: https://github.com/xtne6f/EDCB/blob/work-plus-s/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1319
            const mark = '新|終|再|交|映|手|声|多|副|字|文|CC|OP|二|S|B|SS|無|無料|' +
                'C|S1|S2|S3|MV|双|デ|D|N|W|P|H|HV|SD|天|解|料|前|後初|生|販|吹|PPV|' +
                '演|移|他|収|・|英|韓|中|字/日|字/日英|3D|2ndScr|2K|4K|8K|5.1|7.1|22.2|60P|120P|d|HC|HDR|Hi-Res|Lossless|SHV|UHD|VOD|配|初';

            // 正規表現を作成
            const pattern1 = new RegExp('\\((二|字|再)\\)', 'g');  // 通常の括弧で囲まれている記号
            const pattern2 = new RegExp(`\\[(${mark})\\]`, 'g');

            // 正規表現で置換した結果を返す
            return text.replace(pattern1, '<span class="decorate-symbol">$1</span>')
                .replace(pattern2, '<span class="decorate-symbol">$1</span>');

        // 番組情報がない時間帯
        } else {

            // 23時～翌7時 (0:00 ~ 06:59 or 23:00 ~ 23:59) の間なら放送を休止している可能性が高いので、放送休止と表示する
            const now = dayjs();
            const pause_time_start = dayjs().hour(0).minute(0).second(0);
            const pause_time_end = dayjs().hour(6).minute(59).second(59);
            const pause_time_start_23 = dayjs().hour(23).minute(0).second(0);
            const pause_time_end_23 = dayjs().hour(23).minute(59).second(59);
            if ((now.isSameOrAfter(pause_time_start) && now.isSameOrBefore(pause_time_end)) ||
                (now.isSameOrAfter(pause_time_start_23) && now.isSameOrBefore(pause_time_end_23))) {
                if (key === 'title') {
                    return '放送休止';  // タイトル
                } else {
                    return 'この時間は放送を休止しています。';  // 番組概要
                }

            // それ以外の時間帯では、「番組情報がありません」と表示する
            // 急な番組変更の影響で、一時的にその時間帯に対応する番組情報が消えることがある
            // 特に Mirakurun バックエンドでは高頻度で収集した EIT[p/f] が比較的すぐ反映されるため、この現象が起こりやすい
            // 日中に放送休止（停波）になることはまずあり得ないので、番組情報が取得できてないだけで視聴できるかも？というニュアンスを与える
            } else {
                if (key === 'title') {
                    return '番組情報がありません';  // タイトル
                } else {
                    return 'この時間の番組情報を取得できませんでした。';  // 番組概要
                }
            }
        }
    }


    /**
     * 番組の進捗状況を取得する
     * @param program 番組情報
     * @returns 番組の進捗状況（%単位）
     */
    static getProgramProgress(program: IProgram | IRecordedProgram | null): number {

        // program が空でない
        if (program !== null) {

            // 番組開始時刻から何秒進んだか
            const progress = dayjs(dayjs()).diff(program.start_time, 'second');

            // %単位の割合を算出して返す
            // duration が Infinity の場合は、放送時間未定として扱う
            if (program.duration !== Infinity) {
                return progress / program.duration * 100;
            } else {
                return 100;  // 放送時間未定
            }

        // 放送休止中
        } else {
            return 0;
        }
    }


    /**
     * 番組放送時刻の文字列表現を取得する
     * @param program 番組情報
     * @param is_short 時刻のみ返すかどうか
     * @returns 番組の放送時刻
     */
    static getProgramTime(program: IProgram | IRecordedProgram | null, is_short: boolean = false): string {

        // program が空でなく、かつ番組時刻が初期値でない
        if (program !== null && program.start_time !== '2000-01-01T00:00:00+09:00') {

            const start_time = dayjs(program.start_time);
            const end_time = dayjs(program.end_time);

            // duration が Infinity の場合は、end_time を無視して放送時間未定として扱う
            // この時 end_time には便宜上 start_time と同一の時刻が設定されるため、参照してはいけない
            // IRecordedProgram (録画番組) では発生しない
            if (program.duration === Infinity) {
                if (is_short === true) {  // 時刻のみ
                    return Utils.apply28HourClock(`${start_time.format('HH:mm')} ～ --:--`);
                } else {
                    return Utils.apply28HourClock(`${start_time.format('YYYY/MM/DD (dd) HH:mm')} ～ --:-- (放送時間未定)`);
                }
            }

            // 分単位の番組長 (割り切れない場合は小数第2位で四捨五入)
            const duration = Math.round(program.duration / 60 * 100) / 100;

            if (is_short === true) {  // 時刻のみ
                if ('recorded_video' in program) {
                    return Utils.apply28HourClock(`${start_time.format('YYYY/MM/DD HH:mm')} ～ ${end_time.format('HH:mm')}`);  // 録画番組
                } else {
                    return Utils.apply28HourClock(`${start_time.format('HH:mm')} ～ ${end_time.format('HH:mm')}`);  // 放送中/次の番組
                }
            } else {
                return Utils.apply28HourClock(`${start_time.format('YYYY/MM/DD (dd) HH:mm')} ～ ${end_time.format('HH:mm')} (${duration}分)`);
            }

        // 放送休止中
        } else {
            if (is_short === true) {  // 時刻のみ
                if (program !== null && 'recorded_video' in program) {
                    return '----/--/-- --:-- ～ --:--';  // 録画番組
                } else {
                    return '--:-- ～ --:--';  // 放送中/次の番組
                }
            } else {
                return '----/--/-- (-) --:-- ～ --:-- (--分)';
            }
        }
    }


    /**
     * 録画期間の文字列表現を取得する
     * @param recorded_program 録画番組情報
     * @returns 録画番組の録画開始時刻〜録画終了時刻
     */
    static getRecordingTime(recorded_program: IRecordedProgram): string {

        // 録画期間が不明な場合は代替文字列を返す
        if (recorded_program.recorded_video.recording_start_time === null || recorded_program.recorded_video.recording_end_time === null) {
            return '----/--/-- (-) --:--:-- ～ --:--:-- (--分)';
        }

        const start_time = dayjs(recorded_program.recorded_video.recording_start_time);
        const end_time = dayjs(recorded_program.recorded_video.recording_end_time);

        // 分単位の番組長 (割り切れない場合は小数第2位で四捨五入)
        const duration = Math.round(recorded_program.recorded_video.duration / 60 * 100) / 100;

        return Utils.apply28HourClock(`${start_time.format('YYYY/MM/DD (dd) HH:mm:ss')} ～ ${end_time.format('HH:mm:ss')} (${duration}分)`);
    }


    /**
     * 文字列に含まれる英数や記号を半角に置換し、一律な表現に整える
     * server/app/utils/TSInformation.py の TSInformation.formatString() と同等の処理を行う
     * @param string 変換する文字列
     * @returns 置換した文字列
     */
    static formatString(string: string): string {

        // 変換
        for (const key in ProgramUtils.format_string_translation_map) {
            string = string.replaceAll(key, ProgramUtils.format_string_translation_map[key]);
        }

        // 置換した文字列を返す
        return string;
    }


    /**
     * formatString() で使用する変換マップを取得する
     * server/app/utils/TSInformation.py の TSInfoAnalyzer.__buildFormatStringTranslationMap() と同等の処理を行う
     * @returns 変換マップ
     */
    private static buildFormatStringTranslationMap(): {[key: string]: string} {

        // 全角英数を半角英数に置換
        const zenkaku_table = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ';
        const hankaku_table = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
        const merged_table: { [key: string]: string } = {};
        for (let i = 0; i < zenkaku_table.length; i++) {
            merged_table[zenkaku_table[i]] = hankaku_table[i];
        }

        // 全角記号を半角記号に置換
        const symbol_zenkaku_table = '＂＃＄％＆＇（）＋，－．／：；＜＝＞［＼］＾＿｀｛｜｝　';
        const symbol_hankaku_table = '"#$%&\'()+,-./:;<=>[\\]^_`{|} ';
        for (let i = 0; i < symbol_zenkaku_table.length; i++) {
            merged_table[symbol_zenkaku_table[i]] = symbol_hankaku_table[i];
        }
        // 一部の半角記号を全角に置換
        // 主に見栄え的な問題（全角の方が字面が良い）
        merged_table['!'] = '！';
        merged_table['?'] = '？';
        merged_table['*'] = '＊';
        merged_table['~'] = '～';
        // シャープ → ハッシュ
        merged_table['♯'] = '#';
        // 波ダッシュ → 全角チルダ
        // EDCB は ～ を全角チルダとして扱っているため、KonomiTV でもそのように統一する
        merged_table['〜'] = '～';

        // 番組表で使用される囲み文字の置換テーブル
        // ref: https://note.nkmk.me/python-chr-ord-unicode-code-point/
        // ref: https://github.com/l3tnun/EPGStation/blob/v2.6.17/src/util/StrUtil.ts#L7-L46
        const enclosed_characters_table: {[key: string]: string} = {
            '\u{1F14A}': '[HV]',
            '\u{1F13F}': '[P]',
            '\u{1F14C}': '[SD]',
            '\u{1F146}': '[W]',
            '\u{1F14B}': '[MV]',
            '\u{1F210}': '[手]',
            '\u{1F211}': '[字]',
            '\u{1F212}': '[双]',
            '\u{1F213}': '[デ]',
            '\u{1F142}': '[S]',
            '\u{1F214}': '[二]',
            '\u{1F215}': '[多]',
            '\u{1F216}': '[解]',
            '\u{1F14D}': '[SS]',
            '\u{1F131}': '[B]',
            '\u{1F13D}': '[N]',
            '\u{1F217}': '[天]',
            '\u{1F218}': '[交]',
            '\u{1F219}': '[映]',
            '\u{1F21A}': '[無]',
            '\u{1F21B}': '[料]',
            '\u{1F21C}': '[前]',
            '\u{1F21D}': '[後]',
            '\u{1F21E}': '[再]',
            '\u{1F21F}': '[新]',
            '\u{1F220}': '[初]',
            '\u{1F221}': '[終]',
            '\u{1F222}': '[生]',
            '\u{1F223}': '[販]',
            '\u{1F224}': '[声]',
            '\u{1F225}': '[吹]',
            '\u{1F14E}': '[PPV]',
            '\u{1F200}': '[ほか]',
            '\u{1f19b}': '[3D]',
            '\u{1f19c}': '[2ndScr]',
            '\u{1f19d}': '[2K]',
            '\u{1f19e}': '[4K]',
            '\u{1f19f}': '[8K]',
            '\u{1f1a0}': '[5.1]',
            '\u{1f1a1}': '[7.1]',
            '\u{1f1a2}': '[22.2]',
            '\u{1f1a3}': '[60P]',
            '\u{1f1a4}': '[120P]',
            '\u{1f1a5}': '[d]',
            '\u{1f1a6}': '[HC]',
            '\u{1f1a7}': '[HDR]',
            '\u{1f1a8}': '[Hi-Res]',
            '\u{1f1a9}': '[Lossless]',
            '\u{1f1aa}': '[SHV]',
            '\u{1f1ab}': '[UHD]',
            '\u{1f1ac}': '[VOD]',
            '\u{1f23b}': '[配]',
        };

        // Unicode の囲み文字を大かっこで囲った文字に置換する
        // EDCB で EpgDataCap3_Unicode.dll を利用している場合や、Mirakurun 3.9.0-beta.24 以降など、
        // 番組情報取得元から Unicode の囲み文字が送られてくる場合に対応するためのもの
        // Unicode の囲み文字はサロゲートペアなどで扱いが難しい上に KonomiTV では囲み文字を CSS でハイライトしているため、Unicode にするメリットがない
        // ref: https://note.nkmk.me/python-str-replace-translate-re-sub/
        for (const key in enclosed_characters_table) {
            merged_table[key] = enclosed_characters_table[key];
        }

        return merged_table;
    }


    /**
     * ISO639 形式の言語コードが示す言語の名称を取得する
     * server/app/utils/TSInformation.py の TSInformation.getISO639LanguageCodeName() と同等の処理を行う
     * @param iso639_language_code ISO639 形式の言語コード
     * @returns ISO639 形式の言語コードが示す言語の名称
     */
    static getISO639LanguageCodeName(iso639_language_code: string): string {
        if (iso639_language_code === 'jpn') {
            return '日本語';
        } else if (iso639_language_code === 'eng') {
            return '英語';
        } else if (iso639_language_code === 'deu') {
            return 'ドイツ語';
        } else if (iso639_language_code === 'fra') {
            return 'フランス語';
        } else if (iso639_language_code === 'ita') {
            return 'イタリア語';
        } else if (iso639_language_code === 'rus') {
            return 'ロシア語';
        } else if (iso639_language_code === 'zho') {
            return '中国語';
        } else if (iso639_language_code === 'kor') {
            return '韓国語';
        } else if (iso639_language_code === 'spa') {
            return 'スペイン語';
        } else {
            return 'その他の言語';
        }
    }


    /**
     * 番組の長さを「1:30:00」のような形式でフォーマットする
     * @param program 番組情報
     * @param use_kanji 1:30:00 ではなく「1時間30分00秒」のような形式で返すかどうか
     * @returns フォーマットされた番組の長さ
     */
    static getProgramDuration(program: IProgram | IRecordedProgram, use_kanji: boolean = false): string {
        // 録画番組の場合は recorded_video.duration を使用
        if ('recorded_video' in program) {
            const duration = program.recorded_video.duration;
            const hours = Math.floor(duration / 3600);
            const minutes = Math.floor((duration % 3600) / 60);
            const seconds = Math.floor(duration % 60);
            if (use_kanji) {
                if (hours > 0) {
                    return `${hours}時間${minutes}分${seconds}秒`;
                } else {
                    return `${minutes}分${seconds}秒`;
                }
            } else {
                if (hours > 0) {
                    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
                }
            }
        }

        // 通常の番組の場合は duration を使用
        const duration = program.duration;
        const hours = Math.floor(duration / 3600);
        const minutes = Math.floor((duration % 3600) / 60);
        const seconds = Math.floor(duration % 60);
        if (use_kanji) {
            if (hours > 0) {
                return `${hours}時間${minutes}分${seconds}秒`;
            } else {
                return `${minutes}分${seconds}秒`;
            }
        } else {
            if (hours > 0) {
                return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            } else {
                return `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
        }
    }
}
