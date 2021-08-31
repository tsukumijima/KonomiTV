
import Vue from 'vue';
import dayjs from 'dayjs';
import 'dayjs/locale/ja';


// 共通で使う computed や method を定義
export default Vue.extend({
    data() {

        // バックエンドの API のベース URL
        let api_base_url = `${window.location.protocol}//${window.location.host}/api`;
        if (process.env.NODE_ENV === 'development') {
            // デバッグ時はポートを 7000 に強制する
            api_base_url = `${window.location.protocol}//${window.location.hostname}:7000/api`;
        }

        // デフォルトの映像の画質
        // 当面は 1080p で決め打ち
        const default_quality = '1080p';

        // バージョン
        const version = process.env.VUE_APP_VERSION;

        return {
            api_base_url: api_base_url,
            default_quality: default_quality,
            version: version,
        }
    },
    computed: {

        // 連想配列からプロパティを取得し、もしプロパティが存在しなければ代替値を返す
        getAttribute: () => {
            return (items: any, key: string, default_value: any): any => {

                // items が空でないかつ、items[key] が存在する
                if (items !== null && items[key] !== undefined && items[key] !== null) {

                    // items[key] の内容を返す
                    return items[key];

                // 指定された代替値を返す
                } else {
                    return default_value;
                }
            }
        },

        // 番組情報中の[字]や[解]などの記号をいい感じに装飾する
        decorateProgramInfo: () => {
            return (program: any, key: string): string => {

                // program が空でないかつ、program[key] が存在する
                if (program !== null && key in program) {

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
            };
        },

        // 番組の放送時刻を取得する
        getProgramTime: () => {
            return (program: any, is_short: boolean = false): string => {

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
        },

        // 番組の進捗状況を取得する
        getProgramProgress: () => {
            return (program: any): number => {

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
        }
    }
});
