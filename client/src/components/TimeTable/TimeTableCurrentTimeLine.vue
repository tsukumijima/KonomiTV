<template>
    <div class="timetable-current-time-line"
        v-if="isVisible"
        :style="{
            top: `${linePosition}px`,
            width: `${totalWidth}px`,
        }">
        <div class="timetable-current-time-line__indicator"></div>
        <div class="timetable-current-time-line__line"></div>
    </div>
</template>
<script lang="ts" setup>

import { computed, onMounted, onUnmounted, ref } from 'vue';

import useTimeTableStore from '@/stores/TimeTableStore';
import { dayjs } from '@/utils';
import { TimeTableUtils } from '@/utils/TimeTableUtils';


// Props
const props = defineProps<{
    hourHeight: number;
    totalWidth: number;
    channelHeaderHeight: number;
}>();

// ストア
const timetableStore = useTimeTableStore();

// 現在時刻 (毎分更新)
const currentTime = ref(dayjs());
let updateInterval: ReturnType<typeof setInterval> | null = null;
let updateTimeout: ReturnType<typeof setTimeout> | null = null;


/**
 * 現在時刻バーが表示対象の日付に含まれるか
 * 36時間表示モード時は表示開始時刻 (16:00) から表示終了時刻 (翌々日4:00) の範囲
 */
const isVisible = computed(() => {
    const now = currentTime.value;
    // 表示開始時刻を取得 (36時間表示時は16:00、通常は4:00)
    const displayStart = timetableStore.getDisplayStartTime();
    // 表示終了時刻を取得 (36時間表示時は翌々日4:00、通常は翌日4:00)
    const displayEnd = timetableStore.getDayEndTime(displayStart, timetableStore.is_36hour_display);

    return now.isSameOrAfter(displayStart) && now.isBefore(displayEnd);
});

/**
 * 現在時刻バーの Y 位置
 * 36時間表示モード時は表示開始時刻 (16:00) を基準に計算する
 */
const linePosition = computed(() => {
    if (!isVisible.value) return 0;

    // 表示開始時刻を取得 (36時間表示時は16:00、通常は4:00)
    const displayStart = timetableStore.getDisplayStartTime();
    return TimeTableUtils.calculateCurrentTimeY(
        currentTime.value,
        displayStart,
        props.hourHeight,
        props.channelHeaderHeight,
    ) - props.channelHeaderHeight;
});


// ライフサイクル
onMounted(() => {
    // 次の分境界に合わせて更新し、その後は毎分更新
    const now = dayjs();
    const nextMinute = now.add(1, 'minute').startOf('minute');
    const delayMs = Math.max(0, nextMinute.valueOf() - now.valueOf());

    updateTimeout = setTimeout(() => {
        currentTime.value = dayjs();
        updateInterval = setInterval(() => {
            currentTime.value = dayjs();
        }, 60 * 1000);
    }, delayMs);
});

onUnmounted(() => {
    if (updateTimeout !== null) {
        clearTimeout(updateTimeout);
    }
    if (updateInterval !== null) {
        clearInterval(updateInterval);
    }
});

</script>
<style lang="scss" scoped>

.timetable-current-time-line {
    display: flex;
    align-items: center;
    position: absolute;
    left: 0;
    height: 2px;
    z-index: 32;
    pointer-events: none;

    // 左端のインジケーター
    &__indicator {
        flex-shrink: 0;
        width: 12px;
        height: 12px;
        margin-left: -6px;
        background: rgb(var(--v-theme-secondary));
        border-radius: 50%;
        box-shadow: 0 0 4px rgba(var(--v-theme-secondary), 0.5);
    }

    // ライン
    &__line {
        flex-grow: 1;
        height: 2px;
        background: rgb(var(--v-theme-secondary));
        box-shadow: 0 0 4px rgba(var(--v-theme-secondary), 0.5);
    }
}

</style>
