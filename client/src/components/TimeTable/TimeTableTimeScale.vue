<template>
    <div class="timetable-time-scale">
        <!-- 各時刻のスケール -->
        <div class="timetable-time-scale__hour"
            v-for="hourTime in hourTimes" :key="hourTime.valueOf()"
            :style="{
                height: `${props.hourHeight}px`,
                background: getTimeScaleColor(hourTime),
            }">
            <div class="timetable-time-scale__label">
                <!-- 日付表示 (特定の時刻に表示) -->
                <span class="timetable-time-scale__date" v-if="shouldShowDate(hourTime)">
                    {{ getDateLabel(hourTime) }}
                </span>
                <span class="timetable-time-scale__hour-number">{{ formatHour(hourTime) }}</span>
                <span class="timetable-time-scale__hour-label">時</span>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import type { Dayjs } from 'dayjs';

import useSettingsStore from '@/stores/SettingsStore';
import useTimeTableStore from '@/stores/TimeTableStore';
import { TimeTableUtils } from '@/utils/TimeTableUtils';

// Props
const props = defineProps<{
    selectedDate: Dayjs;
    hourHeight: number;
    is36HourDisplay?: boolean;  // 36時間表示モードかどうか
}>();

// ストア
const settingsStore = useSettingsStore();
const timetableStore = useTimeTableStore();

/**
 * 表示する時刻の Dayjs オブジェクト配列
 * 表示開始時刻から1時間ごとに Dayjs オブジェクトを生成
 * - 通常表示: 4:00 ~ 翌日3:00 (24時間分)
 * - 36時間表示: 16:00 ~ 翌々日3:00 (36時間分)
 */
const hourTimes = computed<Dayjs[]>(() => {
    const totalHours = props.is36HourDisplay ? 36 : 24;
    // computed の display_start_time を使用
    const displayStart = timetableStore.display_start_time;
    const result: Dayjs[] = [];
    for (let i = 0; i < totalHours; i++) {
        // 開始時刻から1時間ずつ加算した Dayjs オブジェクトを生成
        result.push(displayStart.add(i, 'hour'));
    }
    return result;
});

/**
 * 時刻の背景色を取得
 * @param hourTime 時刻を表す Dayjs オブジェクト
 */
function getTimeScaleColor(hourTime: Dayjs): string {
    // TimeTableUtils は時刻数値 (0-23) を期待するので、hour() で取得
    // 28時間表記用の仮想時刻ではなく、実際の時刻を渡す
    return TimeTableUtils.getTimeScaleColor(hourTime.hour());
}

/**
 * 時刻を表示用にフォーマット
 * 28時間表記設定に応じて、0:00-3:59 の表示を切り替える
 * - 28時間表記ON: 0:00-3:59 → 24:00-27:59 として表示
 * - 28時間表記OFF: 常に通常表記 (0:00-23:59)
 * @param hourTime 時刻を表す Dayjs オブジェクト
 */
function formatHour(hourTime: Dayjs): string {
    const hour = hourTime.hour();

    // 28時間表記の場合
    if (settingsStore.settings.use_28hour_clock) {
        // 0〜3時は 24〜27時として表示
        if (hour >= 0 && hour <= 3) {
            return (hour + 24).toString().padStart(2, '0');
        }
    }
    // 28時間表記オフ、または 4時以降は通常表記
    return hour.toString().padStart(2, '0');
}

/**
 * 日付表示が必要な時刻かどうかを判定
 * - 通常表示: 4/8/12/16/20/24(0) のタイミングで表示
 * - 36時間表示: 4/8/12/16/20/24(0) のタイミングで表示
 * @param hourTime 時刻を表す Dayjs オブジェクト
 */
function shouldShowDate(hourTime: Dayjs): boolean {
    const hour = hourTime.hour();
    const displayStart = timetableStore.display_start_time;

    // 4時間単位で日付を表示する
    if ([0, 4, 8, 12, 16, 20].includes(hour) === false) {
        return false;
    }

    // 36時間表示の際、表示開始が4時の場合は日付境界の4時表示を抑制する
    if (props.is36HourDisplay && hour === 4 && displayStart.hour() === 4) {
        return false;
    }

    return true;
}

/**
 * 日付ラベルを取得
 * @param hourTime 時刻を表す Dayjs オブジェクト
 * @returns 日付ラベル (例: "12/30")
 */
function getDateLabel(hourTime: Dayjs): string {
    // Dayjs オブジェクトから直接日付を取得
    return `${hourTime.month() + 1}/${hourTime.date()}`;
}

</script>
<style lang="scss" scoped>

.timetable-time-scale {
    display: flex;
    flex-direction: column;
    background: rgb(var(--v-theme-background-lighten-1));

    // 各時刻
    &__hour {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        color: #ffffff;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
        z-index: 1;
    }

    &__label {
        display: flex;
        flex-direction: column;
        align-items: center;
        position: sticky;
        top: var(--timetable-channel-header-height);
        padding-top: 6px;
        padding-bottom: 4px;
        background: inherit;
    }

    // 日付ラベル (4/8/12/16/20/24(0) に表示)
    &__date {
        font-size: 10px;
        font-weight: bold;
        line-height: 1;
        opacity: 0.9;
        margin-bottom: 4px;
        padding: 2px 4px;
        background: rgba(255, 255, 255, 0.15);
        border-radius: 2px;
    }

    // 時刻の数字
    &__hour-number {
        font-size: 20px;
        font-weight: bold;
        line-height: 1;
        @include smartphone-vertical {
            font-size: 17px;
        }
    }

    // 「時」ラベル
    &__hour-label {
        font-size: 10px;
        margin-top: 2px;
        opacity: 0.9;
    }
}

</style>
