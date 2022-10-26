
import dayjs from 'dayjs';
import 'dayjs/locale/ja';
import isBetween from 'dayjs/plugin/isBetween';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore'

import { IProgram } from '@/interface';
import Utils from './Utils';

/**
 * 番組情報周りのユーティリティ
 */
export class ProgramUtils {

    /**
     * 番組情報中の[字]や[解]などの記号をいい感じに装飾する
     * @param program 番組情報のオブジェクト
     * @param key 番組情報のオブジェクトから取り出すプロパティのキー
     * @returns 装飾した文字列
     */
    static decorateProgramInfo(program: IProgram | null, key: string): string {

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
            const pattern1 = new RegExp(`\\((二|字|再)\\)`, 'g');  // 通常の括弧で囲まれている記号
            const pattern2 = new RegExp(`\\[(${mark})\\]`, 'g');

            // 正規表現で置換した結果を返す
            return text.replace(pattern1, '<span class="decorate-symbol">$1</span>')
                       .replace(pattern2, '<span class="decorate-symbol">$1</span>');

        // 番組情報がない時間帯
        } else {

            dayjs.extend(isSameOrAfter);
            dayjs.extend(isSameOrBefore);
            dayjs.extend(isBetween);

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
     * オブジェクトからプロパティを取得し、もしプロパティが存在しなければ代替値を返す
     * @param items 対象のオブジェクト
     * @param key オブジェクトから取り出すプロパティのキー
     * @param default_value 取得できなかった際の代替値
     * @returns オブジェクト取得した値 or 代替値
     */
    static getAttribute(items: {[key: string]: any}, key: string, default_value: any): any {

        // items が空でないかつ、items[key] が存在する
        if (items !== null && items[key] !== undefined && items[key] !== null) {

            // items[key] の内容を返す
            return items[key];

        // 指定された代替値を返す
        } else {
            return default_value;
        }
    }


    /**
     * 番組の進捗状況を取得する
     * @param program 番組情報
     * @returns 番組の進捗状況（%単位）
     */
    static getProgramProgress(program: IProgram): number {

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
    static getProgramTime(program: IProgram, is_short: boolean = false): string {

        // program が空でなく、かつ番組時刻が初期値でない
        if (program !== null && program.start_time !== '2000-01-01T00:00:00+09:00') {

            // dayjs で日付を扱いやすく
            dayjs.locale('ja');  // ロケールを日本に設定
            const start_time = dayjs(program.start_time);
            const end_time = dayjs(program.end_time);
            const duration = program.duration / 60;  // 分換算

            // 時刻のみ返す
            if (is_short === true) {  // 時刻のみ
                return `${start_time.format('HH:mm')} ～ ${end_time.format('HH:mm')}`;
            // 通常
            } else {
                return `${start_time.format('YYYY/MM/DD (dd) HH:mm')} ～ ${end_time.format('HH:mm')} (${duration}分)`;
            }

        // 放送休止中
        } else {

            // 時刻のみ返す
            if (is_short === true) {
                return '--:-- ～ --:--';
            // 通常
            } else {
                return '----/--/-- (-) --:-- ～ --:-- (--分)';
            }
        }
    }
}
