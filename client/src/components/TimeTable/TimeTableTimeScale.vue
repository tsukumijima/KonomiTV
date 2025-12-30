<template>
    <div class="timetable-time-scale">
        <!-- 各時刻のスケール -->
        <div class="timetable-time-scale__hour"
            v-for="hour in hours" :key="hour"
            :style="{
                height: `${props.hourHeight}px`,
                background: getTimeScaleColor(hour),
            }">
            <span class="timetable-time-scale__hour-number">{{ formatHour(hour) }}</span>
            <span class="timetable-time-scale__hour-label">時</span>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import type { Dayjs } from 'dayjs';

import useSettingsStore from '@/stores/SettingsStore';
import { TimeTableUtils } from '@/utils/TimeTableUtils';

// Props
const props = defineProps<{
    selectedDate: Dayjs;
    hourHeight: number;
}>();

// ストア
const settingsStore = useSettingsStore();

/**
 * 表示する時刻の配列 (4時〜翌3時)
 */
const hours = computed(() => {
    // 4時から翌3時まで (24時間分)
    const result: number[] = [];
    for (let i = 0; i < 24; i++) {
        result.push((4 + i) % 28);  // 4, 5, 6, ..., 23, 24, 25, 26, 27
    }
    return result;
});

/**
 * 時刻の背景色を取得
 */
function getTimeScaleColor(hour: number): string {
    return TimeTableUtils.getTimeScaleColor(hour);
}

/**
 * 時刻を表示用にフォーマット
 */
function formatHour(hour: number): string {
    // 28時間表記の場合は 24〜27 をそのまま表示、オフの場合は 0〜3 に変換
    if (hour >= 24) {
        if (settingsStore.settings.use_28hour_clock) {
            return hour.toString().padStart(2, '0');
        } else {
            return (hour - 24).toString().padStart(2, '0');
        }
    }
    return hour.toString().padStart(2, '0');
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
        padding-top: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        color: #ffffff;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
    }

    // 時刻の数字
    &__hour-number {
        font-size: 20px;
        font-weight: bold;
        line-height: 1;
    }

    // 「時」ラベル
    &__hour-label {
        font-size: 10px;
        margin-top: 2px;
        opacity: 0.9;
    }
}

</style>
