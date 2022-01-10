<script lang="ts">

import dayjs from 'dayjs';
import 'dayjs/locale/ja';

// グローバルミックスインの型定義を継承する
// こうしないと Vetur が正しく補完してくれない
import mixins from 'vue-typed-mixins';
import mixin from '@/mixins';

import { IChannel, IProgram } from '@/interface';
import Utility from '@/utility';

// TV 内共通で使うユーティリティとプロパティを定義
// ユーティリティメソッドはこの Mixin に定義し、ビューにはメインロジックのみを置く
export default mixins(mixin).extend({
    data() {
        return {

            // チャンネル情報リスト
            channels_list: new Map() as Map<string, IChannel[]>,

            // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
            pinned_channel_ids: [] as string[],
        }
    },
    methods: {

        // 番組情報中の[字]や[解]などの記号をいい感じに装飾する
        decorateProgramInfo(program: IProgram, key: string): string {

            // program が空でないかつ、program[key] が存在する
            if (program !== null && program[key] !== null) {

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
                let replaced = program[key].replace(pattern1, '<span class="decorate-symbol">$1</span>');
                replaced = replaced.replace(pattern2, '<span class="decorate-symbol">$1</span>');
                return replaced;

            // 放送休止中
            } else {
                return key == 'title' ? '放送休止': 'この時間は放送を休止しています。';
            }
        },

        // 連想配列からプロパティを取得し、もしプロパティが存在しなければ代替値を返す
        getAttribute(items: {[key: string]: any}, key: string, default_value: any): any {

            // items が空でないかつ、items[key] が存在する
            if (items !== null && items[key] !== undefined && items[key] !== null) {

                // items[key] の内容を返す
                return items[key];

            // 指定された代替値を返す
            } else {
                return default_value;
            }
        },

        // チャンネル ID からチャンネルタイプを取得する
        getChannelType(channel_id: string, is_chideji: boolean = false): string {
            const result = channel_id.match('(?<channel_type>[a-z]+)[0-9]+').groups.channel_type.toUpperCase();
            if (result === 'GR' && is_chideji) {
                return '地デジ';
            } else {
                return result;
            }
        },

        // チャンネルの実況勢いから「多」「激多」「祭」を取得する
        // ref: https://ja.wikipedia.org/wiki/%E3%83%8B%E3%82%B3%E3%83%8B%E3%82%B3%E5%AE%9F%E6%B3%81
        getChannelForceType(channel_force: number | null): string {

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
        },

        // リモコン番号とチャンネルタイプからチャンネルを取得する
        getChannelFromRemoconID(remocon_id: number, channel_type: string): IChannel | null {

            // 指定されたチャンネルタイプのチャンネルを取得
            channel_type = channel_type.replace('GR', '地デジ');  //「GR」は「地デジ」に置換しておく
            const channels = this.channels_list.get(channel_type);

            // リモコン番号が一致するチャンネルを見つけ、一番最初に見つかったものを返す
            for (let index = 0; index < channels.length; index++) {
                const channel = channels[index];
                if (channel.remocon_id === remocon_id) {
                    return channel;
                }
            }

            // リモコン番号が一致するチャンネルを見つけられなかった
            return null;
        },

        // 前・現在・次のチャンネル情報を取得する
        getPreviousAndCurrentAndNextChannel(channel_id: string): IChannel[] {

            // 前後のチャンネルを取得
            const channels = this.channels_list.get(this.getChannelType(channel_id, true));
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
        },

        // 番組の放送時刻を取得する
        getProgramTime(program: IProgram, is_short: boolean = false): string {

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
        },

        // 番組の進捗状況を取得する
        getProgramProgress(program: IProgram): number {

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
        },

        // ピン留めされているチャンネルのリストを更新する
        updatePinnedChannelList() {

            // 現在ピン留めされているチャンネルを取得
            this.pinned_channel_ids = Utility.getSettingsItem('pinned_channel_ids');

            // 仮で保存する辞書
            const pinned_channels = [] as IChannel[];

            // チャンネルごとに
            for (const pinned_channel_id of this.pinned_channel_ids) {

                // チャンネルタイプを取得
                const pinned_channel_type = this.getChannelType(pinned_channel_id, true);

                // チャンネル ID が一致したチャンネルの情報を入れる
                for (const channel of this.channels_list.get(pinned_channel_type)) {
                    if (pinned_channel_id === channel.channel_id) {
                        pinned_channels.push(channel);
                        break;
                    }
                }
            }

            // pinned_channels に何か入っていたらピン留めタブを表示するし、そうでなければ表示しない
            if (pinned_channels.length > 0) {

                // ピン留めタブが存在しない
                if (!this.channels_list.has('ピン留め')) {

                    // 一番左に表示するためこうしている
                    this.channels_list = new Map([['ピン留め', pinned_channels], ...this.channels_list]);

                // ピン留めタブが存在する
                } else {

                    // 既に存在するピン留めタブに値を設定する
                    this.channels_list.set('ピン留め', pinned_channels);
                }

            } else {
                // ピン留めタブがまだ表示されていれば
                if (this.channels_list.has('ピン留め')) {

                    // ピン留めタブがアクティブな状態なら、タブを削除する前にタブのインデックスを 1（地デジ）に変更
                    // 何もしないと一番最後のタブになってしまう
                    // 本当は VTabsItems 側で制御したかったけど、なぜかインデックスが 2 のタブが選択されてしまうのでやむなくこうしている
                    if ((this as any).tab !== undefined && (this as any).tab === 0) {
                        (this as any).tab = 1;
                    }

                    // ピン留めを削除
                    this.channels_list.delete('ピン留め');
                }
            }
        }
    }
});

</script>