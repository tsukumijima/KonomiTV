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

import type { Dayjs } from 'dayjs';

import { dayjs } from '@/utils';
import { TimeTableUtils } from '@/utils/TimeTableUtils';


// Props
const props = defineProps<{
    selectedDate: Dayjs;
    hourHeight: number;
    totalWidth: number;
}>();

// 現在時刻 (毎分更新)
const currentTime = ref(dayjs());
let updateInterval: ReturnType<typeof setInterval> | null = null;


/**
 * 現在時刻バーが表示対象の日付に含まれるか
 */
const isVisible = computed(() => {
    const now = currentTime.value;
    const dayStart = props.selectedDate;
    const dayEnd = props.selectedDate.add(1, 'day');

    return now.isSameOrAfter(dayStart) && now.isBefore(dayEnd);
});

/**
 * 現在時刻バーの Y 位置
 */
const linePosition = computed(() => {
    if (!isVisible.value) return 0;

    const dayStart = props.selectedDate;
    return TimeTableUtils.calculateCurrentTimeY(
        currentTime.value,
        dayStart,
        props.hourHeight,
    ) - TimeTableUtils.CHANNEL_HEADER_HEIGHT;
});


// ライフサイクル
onMounted(() => {
    // 毎分更新
    updateInterval = setInterval(() => {
        currentTime.value = dayjs();
    }, 60 * 1000);
});

onUnmounted(() => {
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
    z-index: 15;
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
