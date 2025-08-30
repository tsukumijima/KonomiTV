
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
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

import type { ConfigType, Dayjs } from 'dayjs';

dayjsOriginal.extend(duration);
dayjsOriginal.extend(isBetween);
dayjsOriginal.extend(isSameOrAfter);
dayjsOriginal.extend(isSameOrBefore);
dayjsOriginal.extend(utc);
dayjsOriginal.extend(timezone);
dayjsOriginal.locale(ja);
dayjsOriginal.tz.setDefault('Asia/Tokyo');

export const dayjs = (date?: ConfigType): Dayjs => {
    // return dayjsOriginal(date).tz();  // .tz() では setDefault で設定したタイムゾーンが適用される
    // dayjs.tz() があまりにもクッソ遅いことが判明したので当面使わないことにする
    // dayjs.tz() を使わないようにするだけで低スペ端末でのパフォーマンスが大幅に向上した…
    return dayjsOriginal(date);
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
