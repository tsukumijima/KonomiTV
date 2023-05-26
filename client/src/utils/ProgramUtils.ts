
import dayjs from 'dayjs';
import 'dayjs/locale/ja';
import isBetween from 'dayjs/plugin/isBetween';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore';

import { IProgram } from '@/services/Programs';
import Utils from '@/utils';

dayjs.extend(isBetween);
dayjs.extend(isSameOrAfter);
dayjs.extend(isSameOrBefore);


/**
 * 番組情報周りのユーティリティ
 */
export class ProgramUtils {

    private static format_string_translation_map: {[key: string]: string} | null = null;


    /**
     * ミリ秒単位の Unix タイムスタンプを ISO 8601 形式の文字列に変換する
     * @param timestamp ミリ秒単位の Unix タイムスタンプ
     * @returns ISO 8601 形式の文字列
     */
    public static convertTimestampToISO8601(timestamp: number): string {
        dayjs.locale('ja');
        const date = dayjs(timestamp).toISOString();
        return date;
    }


    /**
     * 番組情報中の[字]や[解]などの記号をいい感じに装飾する
     * @param program 番組情報のオブジェクト
     * @param key 番組情報のオブジェクトから取り出すプロパティのキー
     * @returns 装飾した文字列
     */
    public static decorateProgramInfo(program: IProgram | null, key: string): string {

        // program が空でないかつ、program[key] が存在する
        if (program !== null && program[key] !== null) {

            // 番組情報に含まれる HTML の特殊文字で表示がバグらないように、事前に HTML エスケープしておく
            const text = Utils.escapeHTML(program[key]);

            // 本来 ARIB 外字である記号の一覧
            // ref: https://ja.wikipedia.org/wiki/%E7%95%AA%E7%B5%84%E8%A1%A8
            // ref: https://github.com/xtne6f/EDCB/blob/work-plus-s/EpgDataCap3/EpgDataCap3/ARIB8CharDecode.cpp#L1319
            const mark = '新|終|再|交|映|手|声|多|副|字|文|CC|OP|二|S|B|SS|無|無料' +
                'C|S1|S2|S3|MV|双|デ|D|N|W|P|H|HV|SD|天|解|料|前|後初|生|販|吹|PPV|' +
                '演|移|他|収|・|英|韓|中|字/日|字/日英|3D|2K|4K|8K|5.1|7.1|22.2|60P|120P|d|HC|HDR|SHV|UHD|VOD|配|初';

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
    public static getProgramProgress(program: IProgram | null): number {

        // program が空でない
        if (program !== null) {

            // 番組開始時刻から何秒進んだか
            const progress = dayjs(dayjs()).diff(program.start_time, 'second');

            // %単位の割合を算出して返す
            return progress / program.duration * 100;

        // 放送休止中
        } else {
            return 0;
        }
    }


    /**
     * 番組の放送時刻を取得する
     * @param program 番組情報
     * @param is_short 時刻のみ返すかどうか
     * @returns 番組の放送時刻
     */
    public static getProgramTime(program: IProgram | null, is_short: boolean = false): string {

        // program が空でなく、かつ番組時刻が初期値でない
        if (program !== null && program.start_time !== '2000-01-01T00:00:00+09:00') {

            dayjs.locale('ja');  // ロケールを日本に設定
            const start_time = dayjs(program.start_time);

            // duration が 0 以下の場合は、放送時間未定として扱う
            if (program.duration <= 0) {
                if (is_short === true) {  // 時刻のみ
                    return `${start_time.format('HH:mm')} ～ --:--`;
                } else {
                    return `${start_time.format('YYYY/MM/DD (dd) HH:mm')} ～ --:-- (放送時間未定)`;
                }
            }

            const end_time = dayjs(program.end_time);
            const duration = program.duration / 60;  // 分換算

            if (is_short === true) {  // 時刻のみ
                return `${start_time.format('HH:mm')} ～ ${end_time.format('HH:mm')}`;
            } else {
                return `${start_time.format('YYYY/MM/DD (dd) HH:mm')} ～ ${end_time.format('HH:mm')} (${duration}分)`;
            }

        // 放送休止中
        } else {
            if (is_short === true) {  // 時刻のみ
                return '--:-- ～ --:--';
            } else {
                return '----/--/-- (-) --:-- ～ --:-- (--分)';
            }
        }
    }


    /**
     * 文字列に含まれる英数や記号を半角に置換し、一律な表現に整える
     * server/app/utils/TSInformation.py の TSInformation.formatString() と同等の処理を行う
     * @param string 変換する文字列
     * @returns 置換した文字列
     */
    public static formatString(string: string): string {

        // 変換マップを構築
        if (ProgramUtils.format_string_translation_map === null) {
            ProgramUtils.format_string_translation_map = ProgramUtils.getFormatStringTranslationTable();
        }

        // 変換
        for (const key in ProgramUtils.format_string_translation_map) {
            string = string.replaceAll(key, ProgramUtils.format_string_translation_map[key]);
        }

        // 置換した文字列を返す
        return string;
    }


    /**
     * formatString() で使用する変換テーブルを取得する
     * server/app/utils/TSInformation.py の TSInformation.__getFormatStringTranslationTable() と同等の処理を行う
     * @returns 変換テーブル
     */
    private static getFormatStringTranslationTable(): {[key: string]: string} {

        // 全角英数を半角英数に置換
        const zenkaku_table = '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ';
        const hankaku_table = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
        const merged_table: { [key: string]: string } = {};
        for (let i = 0; i < zenkaku_table.length; i++) {
            merged_table[zenkaku_table[i]] = hankaku_table[i];
        }

        // 全角記号を半角記号に置換
        const synbol_zenkaku_table = '＂＃＄％＆＇（）＋，－．／：；＜＝＞［＼］＾＿｀｛｜｝　';
        const synbol_hankaku_table = '"#$%&\'()+,-./:;<=>[\\]^_`{|} ';
        for (let i = 0; i < synbol_zenkaku_table.length; i++) {
            merged_table[synbol_zenkaku_table[i]] = synbol_hankaku_table[i];
        }
        // 一部の半角記号を全角に置換
        // 主に見栄え的な問題（全角の方が字面が良い）
        merged_table['!'] = '！';
        merged_table['?'] = '？';
        merged_table['*'] = '＊';
        merged_table['~'] = '～';
        merged_table['@'] = '＠';
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
}
