<template>
    <span v-if="entry !== null" class="toru-count" :class="[`toru-count--${variant}`, `toru-count--${level}`]">
        <Icon v-if="showIcon" icon="fluent:timer-16-filled" class="toru-count__icon" aria-hidden="true" />
        <span class="toru-count__number">{{ entry.count.toLocaleString() }}</span><span class="toru-count__unit">トル</span>
    </span>
</template>
<script setup lang="ts">

import { computed } from 'vue';

import type { IProgram } from '@/services/Programs';

import useToruCountStore from '@/stores/ToruCountStore';

const props = withDefaults(defineProps<{
    program: IProgram | null;
    variant?: 'inline' | 'timetable' | 'reservation';
    showIcon?: boolean;
}>(), {
    variant: 'inline',
    showIcon: true,
});
const store = useToruCountStore();
const entry = computed(() => store.getToruCount(props.program?.id ?? null));
const level = computed(() => store.getToruCountLevel(props.program?.id ?? null));

</script>
<style scoped lang="scss">
.toru-count {
    display: inline-flex;
    align-items: baseline;
    gap: 3px;
    width: max-content;
    font-variant-numeric: tabular-nums;
    font-size: 13px;
    line-height: 1.2;
    white-space: nowrap;

    &__icon {
        align-self: center;
        flex-shrink: 0;
        width: 1em;
        height: 1em;
    }

    &__number {
        font-weight: 700;
    }

    &__unit {
        font-size: 0.8em;
        font-weight: 600;
    }

    // 番組表では、時刻や番組名を読む妨げにならないよう、番組概要より薄い色と細い文字で表示する
    // 予約数が多い番組だけ、下の色分けと太字で目立たせる
    &--timetable {
        color: rgba(0, 0, 0, 0.5);
        font-size: 11px;

        &.toru-count--normal {
            .toru-count__number, .toru-count__unit {
                font-weight: 400;
            }
        }
    }

    &--reservation {
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 12.5px;
        @include tablet-vertical {
            font-size: 12px;
        }
        @include smartphone-horizontal {
            font-size: 12px;
        }
        @include smartphone-vertical {
            font-size: 11px;
        }
    }

    // 予約数が多い番組の色は、どの画面でも同じ色にする
    &--many {
        color: #E7A355;
    }
    &--so-many {
        color: #E76B55;
    }
    &--festival {
        color: #E7556E;
    }
}
</style>
