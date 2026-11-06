<template>
    <!-- PC: 右端に年と月の目盛りが並ぶレール。乗せると年月が出て、掴んで引ける -->
    <div v-if="!isTouch" ref="railRef" class="capture-scrubber"
        @pointerdown="onRailPointerDown" @pointermove="onRailPointerMove" @pointerleave="hoverY = null">
        <template v-for="mark in visibleMarks" :key="`${mark.year}-${mark.month}`">
            <!-- 年の文字は上下の端で切れないよう、レールの内側に収める -->
            <div v-if="mark.showYear" class="capture-scrubber__year" :style="{ top: `${Math.min(Math.max(mark.railY, 10), railHeight - 10)}px` }">{{ mark.year }}</div>
            <div v-else class="capture-scrubber__dot" :style="{ top: `${mark.railY}px` }"></div>
        </template>
        <div class="capture-scrubber__position" :style="{ top: `${positionY}px` }"></div>
        <div v-if="hoverY !== null" class="capture-scrubber__hover" :style="{ top: `${hoverY}px` }">
            <div class="capture-scrubber__hover-label">{{ labelAt(railToContent(hoverY)) }}</div>
        </div>
        <!-- スクロールしている間は、Google フォトと同じくレールの上端に今見ている年月を出す (レールに乗せている間は、乗せた位置の年月だけを出す) -->
        <transition name="capture-scrubber-fade">
            <div v-if="isScrolling && hoverY === null" class="capture-scrubber__current">{{ labelAt(scrollOffset) }}</div>
        </transition>
    </div>
    <!-- スマホ: スクロール中だけ右端につまみが出て、引いている間はつまみの横に年月が出る -->
    <div v-else ref="railRef" class="capture-scrubber-touch" :class="{'capture-scrubber-touch--visible': isThumbVisible}">
        <div class="capture-scrubber-touch__thumb" :style="{ top: `${thumbY}px` }"
            @pointerdown="onThumbPointerDown" @pointermove="onThumbPointerMove"
            @pointerup="onThumbPointerUp" @pointercancel="onThumbPointerUp">
            <Icon icon="fluent:arrow-sort-24-filled" width="18px" height="18px" />
            <div v-if="isDragging" class="capture-scrubber-touch__label">{{ labelAt(dragLabelY) }}</div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';


/** スクラバーの目盛り (月の始まりの位置) */
export interface IScrubberMark {
    y: number;
    year: number;
    month: number;
    isYearStart: boolean;
}

const props = defineProps<{
    marks: IScrubberMark[];
    contentHeight: number;
    scrollOffset: number;
    viewportHeight: number;
    labelAt: (contentY: number) => string;
}>();

const emit = defineEmits<{
    (event: 'scroll-to', contentY: number): void;
}>();

// 指で操作する端末か (マウスのある PC ではレール、タッチの端末ではつまみを出す)
const isTouch = ref(window.matchMedia('(pointer: coarse)').matches);
const railRef = ref<HTMLElement | null>(null);
const railHeight = ref(0);

const updateRailHeight = () => {
    railHeight.value = railRef.value?.clientHeight ?? 0;
};
let resizeObserver: ResizeObserver | null = null;
onMounted(() => {
    resizeObserver = new ResizeObserver(updateRailHeight);
    if (railRef.value !== null) {
        resizeObserver.observe(railRef.value);
    }
    updateRailHeight();
});
onBeforeUnmount(() => resizeObserver?.disconnect());

// タイムラインの位置とレールの位置の変換 (全体の高さに比例させる)
const contentToRail = (contentY: number) => props.contentHeight > 0 ? contentY / props.contentHeight * railHeight.value : 0;
const railToContent = (railY: number) => railHeight.value > 0 ? Math.min(Math.max(railY / railHeight.value, 0), 1) * props.contentHeight : 0;

// 目盛りは重ならないように間引く (年の見出しを優先し、月の点は 6px 以上空いたものだけ)
const visibleMarks = computed(() => {
    const result: (IScrubberMark & { railY: number; showYear: boolean })[] = [];
    let lastYearY = -Infinity;
    let lastDotY = -Infinity;
    for (const mark of props.marks) {
        const railY = contentToRail(mark.y);
        if (mark.isYearStart && railY - lastYearY >= 16) {
            result.push({ ...mark, railY, showYear: true });
            lastYearY = railY;
            lastDotY = railY;
        } else if (railY - lastDotY >= 6 && railY - lastYearY >= 12) {
            result.push({ ...mark, railY, showYear: false });
            lastDotY = railY;
        }
    }
    return result;
});
const positionY = computed(() => contentToRail(props.scrollOffset));

// PC: レールに乗せたときの年月と、掴んで引いたときのスクロール
const hoverY = ref<number | null>(null);
let isRailDragging = false;
const railY = (event: PointerEvent) => event.clientY - (railRef.value?.getBoundingClientRect().top ?? 0);
const onRailPointerDown = (event: PointerEvent) => {
    isRailDragging = true;
    railRef.value?.setPointerCapture(event.pointerId);
    emit('scroll-to', railToContent(railY(event)));
    const onUp = () => {
        isRailDragging = false;
        window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointerup', onUp);
};
const onRailPointerMove = (event: PointerEvent) => {
    hoverY.value = Math.min(Math.max(railY(event), 0), railHeight.value);
    if (isRailDragging) {
        emit('scroll-to', railToContent(hoverY.value));
    }
};

// PC: スクロールした直後だけ、レールの上端に今見ている年月を出す
const isScrolling = ref(false);
let scrollingTimer: number | null = null;
watch(() => props.scrollOffset, () => {
    if (isTouch.value) {
        return;
    }
    isScrolling.value = true;
    if (scrollingTimer !== null) {
        window.clearTimeout(scrollingTimer);
    }
    scrollingTimer = window.setTimeout(() => {
        isScrolling.value = false;
    }, 1500);
});
onBeforeUnmount(() => {
    if (scrollingTimer !== null) {
        window.clearTimeout(scrollingTimer);
    }
});

// スマホ: スクロールした直後と引いている間だけ、つまみを出す
const THUMB_HEIGHT = 44;
const isThumbVisible = ref(false);
const isDragging = ref(false);
const dragLabelY = ref(0);
let hideTimer: number | null = null;
onBeforeUnmount(() => {
    if (hideTimer !== null) {
        window.clearTimeout(hideTimer);
    }
});
const scrollableHeight = computed(() => Math.max(props.contentHeight - props.viewportHeight, 1));
const thumbY = computed(() => {
    const ratio = Math.min(Math.max(props.scrollOffset / scrollableHeight.value, 0), 1);
    return ratio * Math.max(railHeight.value - THUMB_HEIGHT, 0);
});
watch(() => props.scrollOffset, () => {
    if (!isTouch.value) {
        return;
    }
    isThumbVisible.value = true;
    if (hideTimer !== null) {
        window.clearTimeout(hideTimer);
    }
    hideTimer = window.setTimeout(() => {
        if (!isDragging.value) {
            isThumbVisible.value = false;
        }
    }, 1500);
});
let dragOffset = 0;
const onThumbPointerDown = (event: PointerEvent) => {
    // 掴み直したときは、前に離したときにつまみを隠すタイマーを止める
    if (hideTimer !== null) {
        window.clearTimeout(hideTimer);
        hideTimer = null;
    }
    isDragging.value = true;
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    dragOffset = event.clientY - ((railRef.value?.getBoundingClientRect().top ?? 0) + thumbY.value);
    dragLabelY.value = props.scrollOffset + props.viewportHeight / 3;
};
const onThumbPointerMove = (event: PointerEvent) => {
    if (!isDragging.value) {
        return;
    }
    const top = event.clientY - (railRef.value?.getBoundingClientRect().top ?? 0) - dragOffset;
    const ratio = Math.min(Math.max(top / Math.max(railHeight.value - THUMB_HEIGHT, 1), 0), 1);
    const contentY = ratio * scrollableHeight.value;
    dragLabelY.value = contentY + props.viewportHeight / 3;
    emit('scroll-to', contentY);
};
const onThumbPointerUp = () => {
    isDragging.value = false;
    if (hideTimer !== null) {
        window.clearTimeout(hideTimer);
    }
    hideTimer = window.setTimeout(() => {
        isThumbVisible.value = false;
    }, 1500);
};

</script>
<style lang="scss" scoped>

// PC のレール
.capture-scrubber {
    position: fixed;
    top: 65px;
    bottom: 0;
    right: 0;
    width: 52px;
    z-index: 5;
    cursor: pointer;
    user-select: none;

    &__year {
        position: absolute;
        right: 8px;
        transform: translateY(-50%);
        font-size: 11px;
        font-weight: 700;
        color: rgb(var(--v-theme-text-darken-1));
        pointer-events: none;
    }
    &__dot {
        position: absolute;
        right: 22px;
        width: 4px;
        height: 4px;
        border-radius: 50%;
        transform: translateY(-50%);
        background: rgb(var(--v-theme-text-darken-2));
        pointer-events: none;
    }
    &__position {
        position: absolute;
        right: 4px;
        width: 30px;
        height: 2px;
        border-radius: 1px;
        background: rgb(var(--v-theme-primary));
        pointer-events: none;
    }
    &__hover {
        position: absolute;
        right: 0;
        width: 100%;
        height: 1px;
        background: rgb(var(--v-theme-primary-lighten-1));
        pointer-events: none;
        &-label {
            position: absolute;
            right: 56px;
            top: -14px;
            padding: 0px 10px;
            border-radius: 6px;
            background: rgb(var(--v-theme-background-lighten-2));
            color: rgb(var(--v-theme-text));
            font-size: 13px;
            font-weight: 700;
            line-height: 28px;
            white-space: nowrap;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }
    }

    // スクロール中にレールの上端に出す今の年月 (Google フォトと同じく、レールの右端にそろえて下線を引く)
    &__current {
        position: absolute;
        top: 4px;
        right: 2px;
        padding: 0px 10px;
        border-bottom: 2px solid rgb(var(--v-theme-primary));
        border-radius: 6px 6px 0 0;
        background: rgb(var(--v-theme-background-lighten-2));
        color: rgb(var(--v-theme-text));
        font-size: 13px;
        font-weight: 700;
        line-height: 28px;
        white-space: nowrap;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        pointer-events: none;
    }

    // レールの目盛りが見にくくならないよう、乗せたときだけ背景を付ける
    &:hover {
        background: linear-gradient(to left, rgba(var(--v-theme-background-lighten-1), 0.85), rgba(var(--v-theme-background-lighten-1), 0));
    }
}

.capture-scrubber-fade-enter-active, .capture-scrubber-fade-leave-active {
    transition: opacity 0.2s ease;
}
.capture-scrubber-fade-enter-from, .capture-scrubber-fade-leave-to {
    opacity: 0;
}

// スマホのつまみ
.capture-scrubber-touch {
    position: fixed;
    top: 64px;
    bottom: calc(env(safe-area-inset-bottom) + 64px);
    right: 0;
    width: 0;
    z-index: 5;
    user-select: none;
    @include smartphone-horizontal {
        top: 12px;
        bottom: 12px;
    }

    &__thumb {
        position: absolute;
        right: 0;
        width: 34px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 22px 0 0 22px;
        background: rgb(var(--v-theme-background-lighten-2));
        color: rgb(var(--v-theme-text));
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
        touch-action: none;
        opacity: 0;
        transform: translateX(34px);
        transition: opacity 0.2s ease, transform 0.2s ease;
        pointer-events: none;
    }
    &--visible &__thumb {
        opacity: 1;
        transform: translateX(0);
        pointer-events: auto;
    }

    &__label {
        position: absolute;
        right: 46px;
        padding: 0px 14px;
        border-radius: 18px;
        background: rgb(var(--v-theme-primary));
        color: rgb(var(--v-theme-text));
        font-size: 15px;
        font-weight: 700;
        line-height: 36px;
        white-space: nowrap;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
    }
}

</style>
