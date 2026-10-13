
// day.js に毎回プラグインやタイムゾーンを設定するのが面倒かつ嵌まりポイントが多いので、ここでエクスポートする day.js を使う
// ややこしすぎるので KonomiTV 内ではブラウザのタイムゾーンに関わらず、常に Asia/Tokyo として扱う
// ref: https://github.com/iamkun/dayjs/issues/1227#issuecomment-917720826
// ref: https://zenn.dev/taigakiyokawa/articles/20221122-dayjs-timezone

import dayjsOriginal from 'dayjs';
import ja from 'dayjs/locale/ja';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore';
import utc from 'dayjs/plugin/utc';

import type { ConfigType, Dayjs, OptionType, PluginFunc } from 'dayjs';

// JST (UTC+9) の UTC からのオフセット
// 日本には夏時間がないため、Asia/Tokyo は常にこの固定オフセットで表せる
const JST_OFFSET_MINUTES = 9 * 60;
const JST_OFFSET_MILLISECONDS = JST_OFFSET_MINUTES * 60 * 1000;

// day.js が内部で保持している値のうち、JST 固定プラグインが参照するもの
// $d は内部の Date オブジェクト、$x はプラグイン向けの拡張領域で、add() や startOf() で生成される新しいインスタンスにも引き継がれる
type DayjsInternal = Dayjs & {
    $d: Date;
    $x: { $jst?: boolean };
};

/**
 * ブラウザのタイムゾーンに関わらず、日時を常に JST の暦で扱うための day.js プラグイン
 * JST のインスタンスは UTC モードで内部の Date を9時間進めて保持し、UTC の getter で JST の年月日・時刻を読む
 * UTC には夏時間がないため、startOf('day') や hour(4) などの暦の計算はブラウザがどのタイムゾーンでも JST どおりになる
 * 絶対時刻 (valueOf() とそれを使う toDate()・比較・diff()) とオフセット表記 (format('Z')) だけを補正して元に戻す
 */
const jstPlugin: PluginFunc = (_option, dayjsClass) => {
    const proto = dayjsClass.prototype;

    // 内部の Date は9時間進めてあるため、絶対時刻を返すときは差し引く
    const oldValueOf = proto.valueOf;
    proto.valueOf = function(this: DayjsInternal) {
        if (this.$x.$jst === true) {
            return this.$d.getTime() - JST_OFFSET_MILLISECONDS;
        }
        return oldValueOf.call(this);
    };

    // day.js 本体の startOf() / endOf() は toDate('s') で得た Date に setUTCHours() などを適用して暦の境界を求める
    // この内部向けの呼び出しにだけ9時間進めた Date を返し、UTC の getter で JST の暦として計算させる
    // 引数なしの toDate() は valueOf() を経由して絶対時刻の Date を返す
    const oldToDate = proto.toDate;
    proto.toDate = function(this: DayjsInternal, ...args: unknown[]) {
        if (this.$x.$jst === true && args[0] === 's') {
            return new Date(this.$d.getTime());
        }
        return (oldToDate as (...args: unknown[]) => Date).apply(this, args);
    };

    // utc プラグインは UTC モードのインスタンスに 0 を返すため、JST のインスタンスでは +09:00 を返す
    // format() の 'Z' / 'ZZ' もこの値からオフセット表記を作る
    const oldUtcOffset = proto.utcOffset;
    proto.utcOffset = function(this: DayjsInternal, ...args: Parameters<Dayjs['utcOffset']>) {
        if (this.$x.$jst === true && args[0] === undefined) {
            return JST_OFFSET_MINUTES;
        }
        return oldUtcOffset.apply(this, args);
    } as Dayjs['utcOffset'];

    // utc プラグインは UTC モードのインスタンスの既定の書式を末尾 Z 固定にするため、JST のインスタンスでは +09:00 付きにする
    const oldFormat = proto.format;
    proto.format = function(this: DayjsInternal, template?: string) {
        if (this.$x.$jst === true && template === undefined) {
            return oldFormat.call(this, 'YYYY-MM-DDTHH:mm:ssZ');
        }
        return oldFormat.call(this, template);
    };
};

dayjsOriginal.extend(duration);
dayjsOriginal.extend(isBetween);
dayjsOriginal.extend(isSameOrAfter);
dayjsOriginal.extend(isSameOrBefore);
dayjsOriginal.extend(utc);
dayjsOriginal.extend(jstPlugin);
dayjsOriginal.locale(ja);

export const dayjs = (date?: ConfigType): Dayjs => {
    // 以前は dayjsOriginal(date).tz() で Asia/Tokyo に変換していたが、dayjs.tz() があまりにもクッソ遅いことが判明したので使わないことにした
    // dayjs.tz() を使わないようにするだけで低スペ端末でのパフォーマンスが大幅に向上した…
    // その後しばらくはブラウザのタイムゾーンのまま扱っていたが、海外から日本のサーバーに接続すると番組の時刻や番組表が現地時刻でずれてしまう
    // そこで、計算の軽い JST 固定プラグインのインスタンスを返すようにしている
    // すでに JST のインスタンスであれば、そのまま複製して返す (二重に9時間進めないため)
    if (dayjsOriginal.isDayjs(date) && (date as DayjsInternal).$x.$jst === true) {
        return date.clone();
    }
    // まず通常どおりパースして絶対時刻を確定させてから、9時間進めた UTC モードのインスタンスを作る
    // サーバーから返される日時はすべて +09:00 付きの ISO 8601 文字列なので、ブラウザのタイムゾーンに関わらず同じ絶対時刻になる
    // 不正な日時は NaN のまま渡り、isValid() が false のインスタンスになる
    const timestamp = dayjsOriginal(date).valueOf();
    return dayjsOriginal(timestamp + JST_OFFSET_MILLISECONDS, {utc: true, x: {$jst: true}} as OptionType);
};
export { dayjsOriginal };


// 共通ユーティリティをデフォルトとしてインポート
import Utils from '@/utils/Utils';
export default Utils;

// Utils フォルダ配下のユーティリティを一括でインポートできるように
export * from '@/utils/ChannelUtils';
export * from '@/utils/CommentUtils';
export * from '@/utils/PlayerUtils';
export * from '@/utils/ProgramUtils';
export * from '@/utils/Semaphore';
export * from '@/utils/TweetUtils';
