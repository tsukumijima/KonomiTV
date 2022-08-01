
import dayjs from 'dayjs';
import 'dayjs/locale/ja';

import { IChannel, IProgram } from '@/interface';
import Utils from './Utils';

/**
 * TV 機能のユーティリティ
 */
export class TVUtils {

    /**
     * 番組情報中の[字]や[解]などの記号をいい感じに装飾する
     * @param program 番組情報のオブジェクト
     * @param key 番組情報のオブジェクトから取り出すプロパティのキー
     * @returns 装飾した文字列
     */
    static decorateProgramInfo(program: IProgram, key: string): string {

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

        // 放送休止中
        } else {
            return key == 'title' ? '放送休止': 'この時間は放送を休止しています。';
        }
    }


    /**
     * プレイヤーの背景画像をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景画像の URL
     */
    static generatePlayerBackgroundURL(): string {
        const background_count = 12;  // 12種類から選択
        const random = (Math.floor(Math.random() * background_count) + 1);
        return `/assets/images/player-backgrounds/${random.toString().padStart(2, '0')}.jpg`;
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
     * チャンネル ID からチャンネルタイプを取得する
     * @param channel_id チャンネル ID
     * @param is_chideji GR を「地デジ」と表記するかどうか
     * @returns チャンネルタイプ
     */
    static getChannelType(channel_id: string, is_chideji: boolean = false): string {
        const result = channel_id.match('(?<channel_type>[a-z]+)[0-9]+').groups.channel_type.toUpperCase();
        if (result === 'GR' && is_chideji) {
            return '地デジ';
        } else {
            return result;
        }
    }


    /**
     * チャンネルの実況勢いから「多」「激多」「祭」を取得する
     * ref: https://ja.wikipedia.org/wiki/%E3%83%8B%E3%82%B3%E3%83%8B%E3%82%B3%E5%AE%9F%E6%B3%81
     * @param channel_force チャンネルの実況勢い
     * @returns normal（普通）or many（多）or so-many（激多）or festival（祭）
     */
    static getChannelForceType(channel_force: number | null): 'normal' | 'many' | 'so-many' | 'festival' {

        // 実況勢いが null（=対応する実況チャンネルがない）
        if (channel_force === null) return 'normal';

        // 実況勢いが 1000 コメント以上（祭）
        if (channel_force >= 1000) return 'festival';
        // 実況勢いが 200 コメント以上（激多）
        if (channel_force >= 200) return 'so-many';
        // 実況勢いが 100 コメント以上（多）
        if (channel_force >= 100) return 'many';

        // それ以外
        return 'normal';
    }


    /**
     * チャンネルタイプとリモコン番号からチャンネル情報を取得する
     * @param channels_list チャンネルリスト
     * @param channel_type チャンネルタイプ
     * @param remocon_id リモコン番号
     * @returns チャンネル情報
     */
    static getChannelFromRemoconID(channels_list: Map<string, IChannel[]>, channel_type: string, remocon_id: number): IChannel | null {

        // 指定されたチャンネルタイプのチャンネルを取得
        channel_type = channel_type.replace('GR', '地デジ');  //「GR」は「地デジ」に置換しておく
        const channels = channels_list.get(channel_type);

        // リモコン番号が一致するチャンネルを見つけ、一番最初に見つかったものを返す
        for (let index = 0; index < channels.length; index++) {
            const channel = channels[index];
            if (channel.remocon_id === remocon_id) {
                return channel;
            }
        }

        // リモコン番号が一致するチャンネルを見つけられなかった
        return null;
    }


    /**
     * 前・現在・次のチャンネル情報を取得する
     * @param channels_list チャンネルリスト
     * @param channel_id 起点にする現在のチャンネル ID
     * @returns 前・現在・次のチャンネル情報
     */
    static getPreviousAndCurrentAndNextChannel(channels_list: Map<string, IChannel[]>, channel_id: string): IChannel[] {

        // 前後のチャンネルを取得
        const channels = channels_list.get(this.getChannelType(channel_id, true));
        for (let index = 0; index < channels.length; index++) {
            const element = channels[index];

            // チャンネル ID が一致したときだけ
            if (element.channel_id === channel_id) {

                // インデックスが最初か最後の時はそれぞれ最後と最初にインデックスを一周させる
                let previous_index = index - 1;
                if (previous_index === -1) previous_index = channels.length - 1;
                let next_index = index + 1;
                if (next_index === channels.length) next_index = 0;

                // 前・現在・次のチャンネル情報を返す
                return [channels[previous_index], channels[index], channels[next_index]];
            }
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
