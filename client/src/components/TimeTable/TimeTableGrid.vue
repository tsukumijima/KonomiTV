<template>
    <div class="timetable-grid"
        :style="{
            '--timetable-channel-header-height': `${channelHeaderHeight}px`,
        }">
        <!-- スクロール可能な領域 -->
        <!-- ドラッグスクロール: ポインターイベントをこの要素で直接処理 -->
        <!-- チルトホイール: wheel イベントは onMounted で passive: false で登録 (Vue 3 のデフォルトは passive: true のため) -->
        <div class="timetable-grid__scroll-area" ref="scrollAreaRef"
            :class="{ 'timetable-grid__scroll-area--dragging': isDragging }"
            @scroll="onScroll"
            @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerUp"
            @click.capture="onScrollAreaClickCapture">
            <!-- CSS Grid を使ったレイアウト -->
            <div class="timetable-grid__layout"
                :style="{
                    width: `${timeScaleWidth + totalWidth}px`,
                    height: `${channelHeaderHeight + totalHeight}px`,
                }">
                <!-- ヘッダー行 -->
                <div class="timetable-grid__header-row" :style="{ height: `${channelHeaderHeight}px` }">
                    <!-- 左上の固定コーナー -->
                    <div class="timetable-grid__corner" :style="{ width: `${timeScaleWidth}px` }">
                    </div>
                    <!-- チャンネルヘッダー (上部に固定、横スクロールに追従) -->
                    <div class="timetable-grid__channel-headers">
                    <TimeTableChannelHeader
                        v-for="channelData in channels" :key="channelData.channel.id"
                        :channel="channelData.channel"
                        :width="channelWidth"
                        :height="channelHeaderHeight"
                        :resizeTrigger="windowResizeCounter"
                    />
                    </div>
                </div>
                <!-- 本体行 -->
                <div class="timetable-grid__body-row" :style="{ height: `${totalHeight}px` }">
                    <!-- 時刻スケール (左側に固定、縦スクロールに追従) -->
                    <div class="timetable-grid__time-scale" :style="{ width: `${timeScaleWidth}px` }">
                        <TimeTableTimeScale
                            :hourHeight="hourHeight"
                            :is36HourDisplay="props.is36HourDisplay"
                        />
                    </div>
                    <!-- 番組グリッド本体 -->
                    <div class="timetable-grid__content">
                    <!-- 各チャンネルの番組列 -->
                    <div class="timetable-grid__channel-column"
                        v-for="(channelData, channelIndex) in channels" :key="channelData.channel.id"
                        :style="{
                            left: `${channelIndex * channelWidth}px`,
                            width: `${channelWidth}px`,
                            height: `${totalHeight}px`,
                        }">
                        <!-- チャンネル背景 (番組がない領域は灰色) -->
                        <div class="timetable-grid__channel-background"
                            :style="{ height: `${totalHeight}px` }">
                        </div>
                        <!-- 番組セル -->
                        <!-- サブチャンネルが存在するチャンネルでは、メインチャンネルも半分の幅で左半分に配置 -->
                        <template v-for="program in channelData.programs" :key="program.id">
                            <TimeTableProgramCell
                                v-if="isProgramVisible(program)"
                                :program="program"
                                :channel="channelData.channel"
                                :hourHeight="hourHeight"
                                :channelWidth="getProgramCellWidth(channelData, program, false)"
                                :fullChannelWidth="channelWidth"
                                :isSplit="getSplitState(channelData, program, false)"
                                :viewportHeight="viewportHeight"
                                :channelHeaderHeight="channelHeaderHeight"
                                :isScrollAtBottom="isScrollAtBottom"
                                :isSelected="selectedProgramId === program.id"
                                :isPast="isPastProgram(program)"
                                :is36HourDisplay="props.is36HourDisplay"
                                :isNextReserved="isNextProgramReserved(channelData, program, false)"
                                :resizeTrigger="windowResizeCounter"
                                @click="onProgramClick(program)"
                                @show-detail="$emit('show-program-detail', program.id, channelData.channel, program)"
                                @quick-reserve="$emit('quick-reserve', program.id, channelData.channel, program)"
                            />
                        </template>
                        <!-- サブチャンネル番組 (マルチ編成) -->
                        <!-- サブチャンネルは右半分に配置 -->
                        <template v-if="hasSubchannels(channelData)">
                            <template v-for="subchannel in getSubchannels(channelData)" :key="subchannel.channel.id">
                                <template v-for="program in subchannel.programs" :key="program.id">
                                    <TimeTableProgramCell
                                        v-if="isProgramVisible(program)"
                                        :program="program"
                                        :channel="subchannel.channel"
                                        :hourHeight="hourHeight"
                                        :channelWidth="getProgramCellWidth(channelData, program, true)"
                                        :fullChannelWidth="channelWidth"
                                        :isSplit="getSplitState(channelData, program, true)"
                                        :viewportHeight="viewportHeight"
                                        :channelHeaderHeight="channelHeaderHeight"
                                        :isScrollAtBottom="isScrollAtBottom"
                                        :isSubchannel="true"
                                        :isSelected="selectedProgramId === program.id"
                                        :isPast="isPastProgram(program)"
                                        :is36HourDisplay="props.is36HourDisplay"
                                        :isNextReserved="isNextProgramReserved(channelData, program, true)"
                                        :resizeTrigger="windowResizeCounter"
                                        @click="onProgramClick(program)"
                                        @show-detail="$emit('show-program-detail', program.id, subchannel.channel, program)"
                                        @quick-reserve="$emit('quick-reserve', program.id, subchannel.channel, program)"
                                    />
                                </template>
                            </template>
                        </template>
                    </div>
                    <!-- 現在時刻バー -->
                    <TimeTableCurrentTimeLine
                        :hourHeight="hourHeight"
                        :totalWidth="totalWidth"
                        :channelHeaderHeight="channelHeaderHeight"
                    />
                    </div>
                </div>
            </div>
        </div>
        <!-- 日付遷移フロートボタン (次の日へ) -->
        <Transition name="fade">
            <v-btn class="timetable-grid__next-day-button" variant="elevated" color="background-lighten-1"
                v-if="showNextDayButton"
                @click="$emit('go-to-next-day')">
                <Icon icon="fluent:chevron-down-20-regular" width="20px" />
                <span>次の日を見る</span>
            </v-btn>
        </Transition>
        <!-- 日付遷移フロートボタン (前の日へ) -->
        <Transition name="fade">
            <v-btn class="timetable-grid__prev-day-button" variant="elevated" color="background-lighten-1"
                v-if="showPrevDayButton"
                @click="$emit('go-to-previous-day')">
                <Icon icon="fluent:chevron-up-20-regular" width="20px" />
                <span>前の日を見る</span>
            </v-btn>
        </Transition>
    </div>
</template>
<script lang="ts" setup>

import { computed, nextTick, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue';

import TimeTableChannelHeader from '@/components/TimeTable/TimeTableChannelHeader.vue';
import TimeTableCurrentTimeLine from '@/components/TimeTable/TimeTableCurrentTimeLine.vue';
import TimeTableProgramCell from '@/components/TimeTable/TimeTableProgramCell.vue';
import TimeTableTimeScale from '@/components/TimeTable/TimeTableTimeScale.vue';
import { IChannel } from '@/services/Channels';
import { ITimeTableChannel, ITimeTableProgram, ITimeTableSubchannel } from '@/services/Programs';
import useSettingsStore from '@/stores/SettingsStore';
import useTimeTableStore from '@/stores/TimeTableStore';
import Utils, { dayjs } from '@/utils';
import { TimeTableUtils } from '@/utils/TimeTableUtils';

// Props
const props = defineProps<{
    channels: ITimeTableChannel[];
    is36HourDisplay: boolean;
    canGoPreviousDay: boolean;
    canGoNextDay: boolean;
}>();

// Emits
const emit = defineEmits<{
    (e: 'time-slot-change', hour: number): void;
    (e: 'date-display-offset-change', offset: number): void;  // 日付表示のオフセット変更 (0: 選択日, 1: 翌日)
    (e: 'show-program-detail', program_id: string, channel: IChannel, program: ITimeTableProgram): void;
    (e: 'quick-reserve', program_id: string, channel: IChannel, program: ITimeTableProgram): void;
    (e: 'go-to-next-day'): void;
    (e: 'go-to-previous-day'): void;
}>();

// ストア
const settingsStore = useSettingsStore();
const timetableStore = useTimeTableStore();

// DOM 参照
const scrollAreaRef = ref<HTMLElement | null>(null);

// 状態
const selectedProgramId = ref<string | null>(null);
const showNextDayButton = ref(false);
const showPrevDayButton = ref(false);
let currentScrollTop = 0;  // 現在のスクロール位置 (Y方向)
const viewportHeight = ref(0);  // 番組グリッド表示領域の高さ
const isScrollAtBottom = ref(false);
const visibleRangeTop = ref(0);
const visibleRangeBottom = ref(0);
const VISIBLE_BUFFER_HOURS_DESKTOP = 2;
const VISIBLE_BUFFER_HOURS_SMARTPHONE = 3;
const VISIBLE_RANGE_UPDATE_RATIO = 0.5;
const pendingScrollLeft = ref(0);
const pendingScrollTop = ref(0);
const scrollUpdateAnimationId = ref<number | null>(null);
let lastEmittedTimeSlot: number | null = null;
let lastEmittedDateOffset: number | null = null;
const displayStartMs = ref(0);
const stickyProgramCells = new Set<HTMLElement>();
let stickyObserver: IntersectionObserver | null = null;
let stickyUpdateAnimationId: number | null = null;
let stickyObserveAnimationId: number | null = null;
const STICKY_MIN_VISIBLE_HEIGHT = 60;
const STICKY_BASE_PADDING = 2;

// ウィンドウリサイズ時にリアクティブに再計算をトリガーするためのカウンター
// window.innerWidth や window.matchMedia() の結果は Vue のリアクティブシステムでは追跡されないため、
// リサイズイベント発火時にこのカウンターをインクリメントし、computed がこの値を参照することで再計算をトリガーする
const windowResizeCounter = ref(0);

// 直近のタッチ操作時刻を保持
// タッチとマウスが併用されるデバイスでもマウス操作を恒久的に無効化しないためのガードに使う
const TOUCH_POINTER_GUARD_MS = 500;
const lastTouchTimestamp = ref(0);

// ドラッグスクロール用の状態
const isDragging = ref(false);
const isPointerDown = ref(false);
const isPointerCaptured = ref(false);
const pointerCaptureId = ref<number | null>(null);
const dragStartX = ref(0);
const dragStartY = ref(0);
const scrollStartX = ref(0);
const scrollStartY = ref(0);
const hasMoved = ref(false);  // ドラッグ中に移動したかどうか
const shouldSuppressClick = ref(false);
const lastDragEndTime = ref(0);
const CLICK_SUPPRESS_THRESHOLD = 120;

// モーメンタムスクロール用の状態
const velocityX = ref(0);
const velocityY = ref(0);
const lastMoveTime = ref(0);
const lastMoveX = ref(0);
const lastMoveY = ref(0);
const momentumAnimationId = ref<number | null>(null);
const FRICTION = 0.95;  // 摩擦係数
const STOP_THRESHOLD = 0.5;  // 停止閾値 (px)
const DRAG_THRESHOLD = 5;  // ドラッグと判定する閾値 (px)

/**
 * デバイスタイプ
 * windowResizeCounter を参照することで、リサイズイベント発火時に再計算がトリガーされる
 */
const deviceType = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _trigger = windowResizeCounter.value;
    return TimeTableUtils.getDeviceType();
});

/**
 * チャンネル列の幅
 */
const channelWidth = computed(() => {
    return TimeTableUtils.getChannelWidth(
        settingsStore.settings.timetable_channel_width,
        deviceType.value,
    );
});

/**
 * 1時間あたりの高さ
 */
const hourHeight = computed(() => {
    return TimeTableUtils.getHourHeight(
        settingsStore.settings.timetable_hour_height,
        deviceType.value,
    );
});

/**
 * 表示範囲のバッファ (時間)
 */
const visibleBufferHours = computed(() => {
    return deviceType.value === 'Smartphone' ? VISIBLE_BUFFER_HOURS_SMARTPHONE : VISIBLE_BUFFER_HOURS_DESKTOP;
});

/**
 * チャンネルヘッダーの高さ
 */
const channelHeaderHeight = computed(() => {
    return TimeTableUtils.getChannelHeaderHeight(channelWidth.value);
});

/**
 * 時刻スケールの幅
 * Utils.isSmartphoneVertical() も window.matchMedia() を使用しているため、リサイズ時の再計算が必要
 */
const timeScaleWidth = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _trigger = windowResizeCounter.value;
    return TimeTableUtils.getTimeScaleWidth(
        deviceType.value,
        Utils.isSmartphoneVertical(),
    );
});

/**
 * 番組表の総幅 (全チャンネル分)
 */
const totalWidth = computed(() => {
    return props.channels.length * channelWidth.value;
});

/**
 * 番組表の総高さ (通常24時間分、36時間表示モード時は36時間分、ヘッダーは含まない)
 */
const totalHeight = computed(() => {
    const hours = props.is36HourDisplay ? 36 : 24;
    return hours * hourHeight.value;
});

/**
 * チャンネルにサブチャンネル番組があるかどうかを判定
 * @param channelData チャンネルデータ
 * @returns サブチャンネルが存在する場合は true
 */
function hasSubchannels(channelData: ITimeTableChannel): boolean {
    if (channelData.subchannels === null || channelData.subchannels.length === 0) {
        return false;
    }
    // サブチャンネルが存在し、かつ番組が1つ以上ある場合
    return channelData.subchannels.some(subchannel => subchannel.programs.length > 0);
}

/**
 * 番組の開始/終了時刻を数値で取得する
 */
const programTimeCache = new Map<string, { start: number; end: number }>();
const splitStateCache = new Map<string, boolean>();

function getProgramTimeRange(program: ITimeTableProgram): { start: number; end: number } {
    if (program === undefined || program === null) {
        return { start: 0, end: 0 };
    }
    const cached = programTimeCache.get(program.id);
    if (cached !== undefined) {
        return cached;
    }
    const range = {
        start: dayjs(program.start_time).valueOf(),
        end: dayjs(program.end_time).valueOf(),
    };
    programTimeCache.set(program.id, range);
    return range;
}

/**
 * 対象番組が指定リストと時間帯で重なっているか
 */
function hasOverlappingProgram(target: ITimeTableProgram, other_programs: ITimeTableProgram[]): boolean {
    const target_range = getProgramTimeRange(target);
    return other_programs.some((program) => {
        const other_range = getProgramTimeRange(program);
        return other_range.start < target_range.end && other_range.end > target_range.start;
    });
}

/**
 * 番組セルが分割表示対象かどうか
 */
function getSplitState(
    channelData: ITimeTableChannel,
    program: ITimeTableProgram,
    is_subchannel: boolean,
): boolean {
    const cache_key = `${program.id}:${is_subchannel ? 'sub' : 'main'}`;
    const cached = splitStateCache.get(cache_key);
    if (cached !== undefined) {
        return cached;
    }
    const subchannel_programs = getAllSubchannelPrograms(channelData);
    if (subchannel_programs.length === 0) {
        splitStateCache.set(cache_key, false);
        return false;
    }

    if (is_subchannel) {
        const is_split = hasOverlappingProgram(program, channelData.programs);
        splitStateCache.set(cache_key, is_split);
        return is_split;
    }
    const is_split = hasOverlappingProgram(program, subchannel_programs);
    splitStateCache.set(cache_key, is_split);
    return is_split;
}

/**
 * 番組セルの幅を取得する
 */
function getProgramCellWidth(
    channelData: ITimeTableChannel,
    program: ITimeTableProgram,
    is_subchannel: boolean,
): number {
    if (getSplitState(channelData, program, is_subchannel)) {
        return channelWidth.value / 2;
    }
    return channelWidth.value;
}

/**
 * 表示範囲を更新する
 */
function updateVisibleRange(current_scroll_top: number): void {
    const buffer = hourHeight.value * visibleBufferHours.value;
    visibleRangeTop.value = Math.max(0, current_scroll_top - buffer);
    visibleRangeBottom.value = current_scroll_top + viewportHeight.value + buffer;
}

/**
 * 表示範囲を必要なタイミングだけ更新する
 * バッファ領域の端に近づいた場合のみ再計算することで、更新頻度を抑える
 */
function updateVisibleRangeIfNeeded(current_scroll_top: number): boolean {
    const buffer = hourHeight.value * visibleBufferHours.value;
    const threshold = buffer * VISIBLE_RANGE_UPDATE_RATIO;
    const viewport_bottom = current_scroll_top + viewportHeight.value;

    if (viewportHeight.value <= 0 || visibleRangeBottom.value === 0) {
        updateVisibleRange(current_scroll_top);
        return true;
    }

    if (current_scroll_top < visibleRangeTop.value + threshold) {
        updateVisibleRange(current_scroll_top);
        return true;
    }

    if (viewport_bottom > visibleRangeBottom.value - threshold) {
        updateVisibleRange(current_scroll_top);
        return true;
    }

    return false;
}

/**
 * 番組セルが現在の表示範囲に含まれるかどうか
 */
function isProgramVisible(program: ITimeTableProgram): boolean {
    const program_range = getProgramTimeRange(program);
    const startY = ((program_range.start - displayStartMs.value) / (1000 * 60 * 60)) * hourHeight.value;
    const endY = ((program_range.end - displayStartMs.value) / (1000 * 60 * 60)) * hourHeight.value;
    return endY >= visibleRangeTop.value && startY <= visibleRangeBottom.value;
}

/**
 * サブチャンネルのリストを取得
 * @param channelData チャンネルデータ
 * @returns サブチャンネルのリスト
 */
function getSubchannels(channelData: ITimeTableChannel): ITimeTableSubchannel[] {
    if (channelData.subchannels === null) {
        return [];
    }
    return channelData.subchannels;
}

/**
 * サブチャンネル番組をフラット化して取得 (分割表示判定用)
 * @param channelData チャンネルデータ
 * @returns 全サブチャンネルの番組をフラット化した配列
 */
function getAllSubchannelPrograms(channelData: ITimeTableChannel): ITimeTableProgram[] {
    if (channelData.subchannels === null) {
        return [];
    }
    return channelData.subchannels.flatMap(subchannel => subchannel.programs);
}

/**
 * 番組が過去のものかどうか判定
 */
function isPastProgram(program: ITimeTableProgram): boolean {
    const end_time = dayjs(program.end_time);
    return end_time.isBefore(dayjs());
}

/**
 * 次の番組が予約されているかを判定
 * 隣り合う予約済み番組の border 重複を避けるために使用
 * @param channelData チャンネルデータ
 * @param program 対象の番組
 * @param isSubchannel サブチャンネルかどうか
 * @returns 次の番組が予約されている場合は true
 */
function isNextProgramReserved(
    channelData: ITimeTableChannel,
    program: ITimeTableProgram,
    isSubchannel: boolean,
): boolean {
    // 対象の番組リストを取得
    const programs = isSubchannel ? getAllSubchannelPrograms(channelData) : channelData.programs;
    // 現在の番組の終了時刻と一致する開始時刻を持つ番組を探す
    const programEndTime = dayjs(program.end_time).valueOf();
    const nextProgram = programs.find((p) => {
        return dayjs(p.start_time).valueOf() === programEndTime;
    });
    // 次の番組が存在し、予約されている場合は true
    return nextProgram !== undefined && nextProgram.reservation !== null;
}

/**
 * スクロール位置の更新処理
 * requestAnimationFrame でまとめて処理し、DOM 更新回数を抑える
 */
function applyScrollUpdate(): void {
    if (scrollAreaRef.value === null) return;

    const scrollX = pendingScrollLeft.value;
    const scrollY = pendingScrollTop.value;

    // スクロール位置を更新 (TimeTableProgramCell の sticky 処理用)
    currentScrollTop = scrollY;
    // ビューポート高さを更新 (チャンネルヘッダー分を引いた番組グリッドの表示領域)
    const nextViewportHeight = scrollAreaRef.value.clientHeight - channelHeaderHeight.value;
    if (viewportHeight.value !== nextViewportHeight) {
        viewportHeight.value = nextViewportHeight;
    }

    // スクロール位置が下端に到達しているかを判定
    const maxScrollY = scrollAreaRef.value.scrollHeight - scrollAreaRef.value.clientHeight;
    const isAtBottom = scrollY >= maxScrollY - 1;
    if (isScrollAtBottom.value !== isAtBottom) {
        isScrollAtBottom.value = isAtBottom;
    }
    const isRangeUpdated = updateVisibleRangeIfNeeded(scrollY);
    if (isRangeUpdated) {
        scheduleStickyObserveUpdate();
    }

    // 日付遷移ボタンの表示判定
    // スクロール位置が端に近く、かつ前後の日に遷移可能な場合のみ表示
    const shouldShowNextDay = scrollY > maxScrollY - 100 && props.canGoNextDay;
    const shouldShowPrevDay = scrollY < 100 && props.canGoPreviousDay;
    if (showNextDayButton.value !== shouldShowNextDay) {
        showNextDayButton.value = shouldShowNextDay;
    }
    if (showPrevDayButton.value !== shouldShowPrevDay) {
        showPrevDayButton.value = shouldShowPrevDay;
    }

    // 現在表示中の時刻スロットを計算して親に通知
    // 表示開始時刻を基準にスクロール位置から現在表示されている時刻を算出
    const displayStartTime = timetableStore.getDisplayStartTime();
    const elapsedHours = Math.floor(scrollY / hourHeight.value);
    const currentTime = displayStartTime.add(elapsedHours, 'hour');
    let currentHour = currentTime.hour();
    // 0〜3時は 24〜27時として扱う
    if (currentHour < 4) {
        currentHour += 24;
    }
    // 4時間単位のスロットに丸める
    const slotHour = Math.floor((currentHour - 4) / 4) * 4 + 4;
    // 4〜24 の範囲にクランプ
    const clampedSlot = Math.max(4, Math.min(24, slotHour));
    if (lastEmittedTimeSlot !== clampedSlot) {
        emit('time-slot-change', clampedSlot);
        lastEmittedTimeSlot = clampedSlot;
    }

    // 日付表示の切り替え判定
    // 36時間表示モード時のみ、スクロール位置に応じて日付表示を切り替える
    // 28時間表記オン: 翌日4時 (28時) ラインを超えたら翌日表示
    // 28時間表記オフ: 翌日0時 (24時) ラインを超えたら翌日表示
    if (props.is36HourDisplay) {
        const use28HourClock = settingsStore.settings.use_28hour_clock;
        // 日付切り替えラインの Y 座標を計算
        // 28時間表記: 翌日4時、通常表記: 翌日0時
        const dateBoundaryHour = use28HourClock ? 4 : 0;
        let dateBoundaryTime = displayStartTime.hour(dateBoundaryHour).minute(0).second(0).millisecond(0);
        if (dateBoundaryTime.isSameOrBefore(displayStartTime)) {
            dateBoundaryTime = dateBoundaryTime.add(1, 'day');
        }
        const dateBoundaryElapsedHours = (dateBoundaryTime.valueOf() - displayStartTime.valueOf()) / (1000 * 60 * 60);
        const dateBoundaryY = dateBoundaryElapsedHours * hourHeight.value;
        const dateOffset = scrollY >= dateBoundaryY ? 1 : 0;
        if (lastEmittedDateOffset !== dateOffset) {
            emit('date-display-offset-change', dateOffset);
            lastEmittedDateOffset = dateOffset;
        }
    } else {
        // 通常表示モードではオフセットなし
        if (lastEmittedDateOffset !== 0) {
            emit('date-display-offset-change', 0);
            lastEmittedDateOffset = 0;
        }
    }

    scheduleStickyContentUpdate();
}

/**
 * スクロール更新を requestAnimationFrame にまとめる
 */
function scheduleScrollUpdate(): void {
    if (scrollUpdateAnimationId.value !== null) {
        return;
    }
    scrollUpdateAnimationId.value = requestAnimationFrame(() => {
        scrollUpdateAnimationId.value = null;
        applyScrollUpdate();
    });
}

/**
 * スティッキー対象の更新 (IntersectionObserver)
 */
function scheduleStickyObserveUpdate(): void {
    if (stickyObserveAnimationId !== null) {
        return;
    }
    stickyObserveAnimationId = requestAnimationFrame(() => {
        stickyObserveAnimationId = null;
        setupStickyObserver();
    });
}

/**
 * スティッキー対象のオフセット更新
 */
function scheduleStickyContentUpdate(): void {
    if (stickyUpdateAnimationId !== null) {
        return;
    }
    stickyUpdateAnimationId = requestAnimationFrame(() => {
        stickyUpdateAnimationId = null;
        updateStickyContentOffset();
    });
}

/**
 * IntersectionObserver を初期化する
 */
function setupStickyObserver(): void {
    if (scrollAreaRef.value === null) return;

    if (stickyObserver !== null) {
        stickyObserver.disconnect();
        stickyProgramCells.clear();
    }

    stickyObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            const cell = entry.target as HTMLElement;
            const rootBounds = entry.rootBounds;
            if (rootBounds === null) continue;

            const isIntersectingTop = entry.intersectionRect.top <= rootBounds.top;
            const isPartial = entry.intersectionRect.height < entry.boundingClientRect.height;
            const isRootSmaller = rootBounds.height < entry.boundingClientRect.height;
            const shouldFix = entry.isIntersecting && isIntersectingTop && (isPartial || isRootSmaller);

            if (shouldFix) {
                stickyProgramCells.add(cell);
                cell.classList.add('timetable-program-cell--fixed');
            } else {
                stickyProgramCells.delete(cell);
                cell.classList.remove('timetable-program-cell--fixed');
                const content = cell.querySelector<HTMLElement>('.timetable-program-cell__content');
                if (content !== null) {
                    content.style.paddingTop = '';
                }
            }
        }

        scheduleStickyContentUpdate();
    }, {
        root: scrollAreaRef.value,
        rootMargin: `-${channelHeaderHeight.value}px 0px 0px 0px`,
        threshold: [0, 1],
    });

    scrollAreaRef.value.querySelectorAll<HTMLElement>('.timetable-program-cell').forEach((cell) => {
        stickyObserver?.observe(cell);
    });
}

/**
 * スティッキー中の番組セルの表示位置を調整する
 */
function updateStickyContentOffset(): void {
    if (scrollAreaRef.value === null) return;
    if (stickyProgramCells.size === 0) return;

    const topEdge = scrollAreaRef.value.getBoundingClientRect().top + channelHeaderHeight.value;

    stickyProgramCells.forEach((cell) => {
        const content = cell.querySelector<HTMLElement>('.timetable-program-cell__content');
        if (content === null) return;

        const cellTop = cell.getBoundingClientRect().top;
        const base = topEdge - cellTop;
        if (base <= 0) {
            content.style.paddingTop = '';
            return;
        }

        const rawHeight = cell.style.getPropertyValue('--timetable-cell-height');
        const cellHeight = rawHeight ? Number.parseFloat(rawHeight) : cell.getBoundingClientRect().height;
        const maxOffset = Math.max(0, cellHeight - STICKY_MIN_VISIBLE_HEIGHT);
        const reserveOffset = cell.classList.contains('timetable-program-cell--reserved') ? 3 : 0;
        const resolvedOffset = Math.min(base, maxOffset);
        content.style.paddingTop = `${STICKY_BASE_PADDING + Math.max(resolvedOffset - reserveOffset, 0)}px`;
    });
}

// リサイズイベントハンドラー (デバウンス処理付き)
const RESIZE_DEBOUNCE_MS = 100;
let resizeDebounceTimerId: number | null = null;
function onWindowResize() {
    // デバウンス処理: 連続したリサイズイベントを間引く
    if (resizeDebounceTimerId !== null) {
        clearTimeout(resizeDebounceTimerId);
    }
    resizeDebounceTimerId = window.setTimeout(() => {
        windowResizeCounter.value++;
        resizeDebounceTimerId = null;
    }, RESIZE_DEBOUNCE_MS);
}

/**
 * タッチ操作の検知イベントハンドラ
 * 直近の touchstart 時刻を保存して、タッチ由来の pointerdown を除外するために使う
 */
function onTouchStart(): void {
    lastTouchTimestamp.value = performance.now();
}

/**
 * スクロールイベントハンドラ
 */
function onScroll(): void {
    if (scrollAreaRef.value === null) return;

    pendingScrollLeft.value = scrollAreaRef.value.scrollLeft;
    pendingScrollTop.value = scrollAreaRef.value.scrollTop;
    scheduleScrollUpdate();
}

/**
 * ホイールイベントハンドラ (チルトホイール・Shift+ホイールによる横スクロール対応)
 * touch-action: none を設定しているため、スクロールは全て JavaScript で制御する必要がある
 */
function onWheel(event: WheelEvent): void {
    if (scrollAreaRef.value === null) return;

    // モーメンタムアニメーション中ならキャンセル
    if (momentumAnimationId.value !== null) {
        cancelAnimationFrame(momentumAnimationId.value);
        momentumAnimationId.value = null;
    }

    // チルトホイール (deltaX) がある場合は横スクロール
    if (event.deltaX !== 0) {
        event.preventDefault();
        scrollAreaRef.value.scrollLeft += event.deltaX;
    }

    // Shift + 縦ホイールで横スクロール
    if (event.shiftKey && event.deltaY !== 0) {
        event.preventDefault();
        scrollAreaRef.value.scrollLeft += event.deltaY;
    } else if (event.deltaY !== 0 && event.deltaX === 0) {
        // 通常の縦スクロール (Shift なし、deltaX なし)
        event.preventDefault();
        scrollAreaRef.value.scrollTop += event.deltaY;
    }
}

/**
 * ポインターダウンイベントハンドラ (ドラッグスクロール開始)
 */
function onPointerDown(event: PointerEvent): void {

    // 1. pointerType が明らかにマウスでない場合はスキップ
    // 2. pointerType が mouse と報告されても、タッチ由来ならスキップ
    //    - sourceCapabilities は Safari が対応していないため、一応直近の touchstart をフォールバックに使う
    const isMousePointer = event.pointerType === 'mouse';
    if (isMousePointer === false) {
        return;
    }
    const isTouchPointerByCapabilities = (event as any).sourceCapabilities?.firesTouchEvents === true;
    const elapsedFromLastTouch = performance.now() - lastTouchTimestamp.value;
    const isRecentTouch = elapsedFromLastTouch <= TOUCH_POINTER_GUARD_MS;
    if (isTouchPointerByCapabilities || isRecentTouch) {
        return;
    }

    // scrollAreaRef がない場合は何もしない
    if (scrollAreaRef.value === null) return;

    // 番組セル内のボタン上でのクリックは除外 (ボタン側で処理)
    // 番組セル自体はドラッグ対象とする
    const target = event.target as HTMLElement;
    if (target.closest('.v-btn') || target.closest('a')) {
        return;
    }

    isPointerDown.value = true;
    isDragging.value = false;
    hasMoved.value = false;
    dragStartX.value = event.clientX;
    dragStartY.value = event.clientY;
    scrollStartX.value = scrollAreaRef.value.scrollLeft;
    scrollStartY.value = scrollAreaRef.value.scrollTop;

    // モーメンタムアニメーションをキャンセル
    if (momentumAnimationId.value !== null) {
        cancelAnimationFrame(momentumAnimationId.value);
        momentumAnimationId.value = null;
    }

    velocityX.value = 0;
    velocityY.value = 0;
    lastMoveTime.value = performance.now();
    lastMoveX.value = event.clientX;
    lastMoveY.value = event.clientY;

    // ドラッグ開始前はクリック操作を優先するため、ポインターキャプチャや preventDefault は行わない
}

/**
 * ポインタームーブイベントハンドラ (ドラッグスクロール中)
 */
function onPointerMove(event: PointerEvent): void {
    if (event.pointerType !== 'mouse') return;
    if (isPointerDown.value === false || scrollAreaRef.value === null) return;

    const deltaX = dragStartX.value - event.clientX;
    const deltaY = dragStartY.value - event.clientY;

    // 移動閾値を超えたらドラッグとみなす
    if (Math.abs(deltaX) > DRAG_THRESHOLD || Math.abs(deltaY) > DRAG_THRESHOLD) {
        // ドラッグ開始時のみポインターキャプチャを有効化
        if (isDragging.value === false && scrollAreaRef.value !== null) {
            isDragging.value = true;
            hasMoved.value = true;
            scrollAreaRef.value.setPointerCapture(event.pointerId);
            isPointerCaptured.value = true;
            pointerCaptureId.value = event.pointerId;
        }
    }

    if (isDragging.value === false) {
        return;
    }

    // テキスト選択を防止
    event.preventDefault();

    // ドラッグ中に移動したかどうかを記録
    if (Math.abs(deltaX) > DRAG_THRESHOLD || Math.abs(deltaY) > DRAG_THRESHOLD) {
        hasMoved.value = true;
    }

    scrollAreaRef.value.scrollLeft = scrollStartX.value + deltaX;
    scrollAreaRef.value.scrollTop = scrollStartY.value + deltaY;

    // 速度を計算 (モーメンタムスクロール用)
    const now = performance.now();
    const dt = now - lastMoveTime.value;
    if (dt > 0) {
        const moveX = event.clientX - lastMoveX.value;
        const moveY = event.clientY - lastMoveY.value;
        velocityX.value = -moveX / dt * 16;  // 60fps に正規化
        velocityY.value = -moveY / dt * 16;
    }
    lastMoveTime.value = now;
    lastMoveX.value = event.clientX;
    lastMoveY.value = event.clientY;
}

/**
 * ポインターアップイベントハンドラ (ドラッグスクロール終了)
 */
function onPointerUp(event: PointerEvent): void {
    if (event.pointerType !== 'mouse') return;
    if (isPointerDown.value === false) return;

    isPointerDown.value = false;
    isDragging.value = false;

    // ポインターキャプチャを解除
    if (scrollAreaRef.value !== null && isPointerCaptured.value && pointerCaptureId.value !== null) {
        try {
            scrollAreaRef.value.releasePointerCapture(pointerCaptureId.value);
        } catch {
            // ポインターキャプチャが設定されていない場合は無視
        }
    }
    isPointerCaptured.value = false;
    pointerCaptureId.value = null;

    // ドラッグした場合のみモーメンタムスクロールを開始
    if (hasMoved.value) {
        startMomentumScroll();
        shouldSuppressClick.value = true;
        lastDragEndTime.value = performance.now();
    } else {
        shouldSuppressClick.value = false;
        lastDragEndTime.value = 0;
    }
}

/**
 * クリックイベントのキャプチャハンドラ
 * ドラッグ直後のクリックを抑制して、番組選択を誤発火させない
 */
function onScrollAreaClickCapture(event: MouseEvent): void {
    if (shouldSuppressClick.value === false) {
        return;
    }

    const elapsed = performance.now() - lastDragEndTime.value;
    if (elapsed <= CLICK_SUPPRESS_THRESHOLD) {
        event.preventDefault();
        event.stopPropagation();
    }
    shouldSuppressClick.value = false;
}

/**
 * モーメンタムスクロールを開始
 */
function startMomentumScroll(): void {
    if (scrollAreaRef.value === null) return;

    // 速度が閾値以下なら開始しない
    if (Math.abs(velocityX.value) < STOP_THRESHOLD && Math.abs(velocityY.value) < STOP_THRESHOLD) {
        return;
    }

    const animate = () => {
        if (scrollAreaRef.value === null) return;

        // 摩擦による減速
        velocityX.value *= FRICTION;
        velocityY.value *= FRICTION;

        // スクロール位置を更新
        scrollAreaRef.value.scrollLeft += velocityX.value;
        scrollAreaRef.value.scrollTop += velocityY.value;

        // 速度が閾値以下になったら停止
        if (Math.abs(velocityX.value) < STOP_THRESHOLD && Math.abs(velocityY.value) < STOP_THRESHOLD) {
            momentumAnimationId.value = null;
            return;
        }

        momentumAnimationId.value = requestAnimationFrame(animate);
    };

    momentumAnimationId.value = requestAnimationFrame(animate);
}

/**
 * 番組クリック時のハンドラ
 */
function onProgramClick(program: ITimeTableProgram): void {
    // 同じ番組をクリックした場合は選択解除
    if (selectedProgramId.value === program.id) {
        selectedProgramId.value = null;
    } else {
        selectedProgramId.value = program.id;
    }
}

/**
 * 指定した時刻にスクロール
 */
function scrollToHour(hour: number): void {
    if (scrollAreaRef.value === null) return;

    // 表示開始時刻からの時間を計算
    const displayStart = timetableStore.getDisplayStartTime();
    const displayStartHour = displayStart.hour();
    const normalizedHour = hour === 24 ? 0 : hour;
    let hoursFromStart = normalizedHour - displayStartHour;
    if (hoursFromStart < 0) {
        hoursFromStart += 24;
    }
    const scrollY = hoursFromStart * hourHeight.value;

    scrollAreaRef.value.scrollTo({
        top: scrollY,
        behavior: 'smooth',
    });
}

/**
 * 初期スクロール位置 (Y座標) を計算する
 * 選択日が今日の場合は「現在時刻 - 1時間の正時」の位置を返す
 * 選択日が今日でない場合は 0 (番組表の先頭) を返す
 * @returns 初期スクロール位置の Y 座標 (px)
 */
function getInitialScrollY(): number {
    const limitTime = timetableStore.scroll_top_limit_time;
    if (limitTime === null) {
        return 0;  // 選択日が今日でない場合は先頭
    }

    // 番組表の表示開始時刻を取得
    const displayStart = timetableStore.getDisplayStartTime();

    // 初期スクロール位置の Y 座標を計算
    const elapsedMs = limitTime.valueOf() - displayStart.valueOf();
    const elapsedHours = elapsedMs / (1000 * 60 * 60);
    return Math.max(0, elapsedHours * hourHeight.value);
}

/**
 * 現在時刻にスクロール
 * 選択日が今日の場合:
 *   1. まず「現在時刻 - 1時間の正時」位置に即座に移動
 *   2. そこから「現在時刻 - 30分」位置へスムーズスクロール
 * 選択日が今日でない場合:
 *   - 番組表の先頭 (4:00) を表示
 * @param smooth スムーズスクロールを使用するか (デフォルト: true)
 * @param useSmoothOnly 現在のスクロール位置から直接スムーズスクロールするか
 */
function scrollToCurrentTime(smooth: boolean = true, useSmoothOnly: boolean = false): void {
    if (scrollAreaRef.value === null) return;

    const now = dayjs();
    const displayStart = timetableStore.getDisplayStartTime();

    // 初期スクロール位置を取得 (現在時刻 - 1時間の正時)
    const initialScrollY = getInitialScrollY();

    // 現在時刻 - 30分の位置を計算
    // EMWUI の挙動を踏襲: 現在時刻 - 30分位置が見えるようにスクロール
    const targetTime = now.subtract(30, 'minute');
    const elapsedMs = targetTime.valueOf() - displayStart.valueOf();
    const elapsedHours = elapsedMs / (1000 * 60 * 60);
    const targetY = Math.max(initialScrollY, elapsedHours * hourHeight.value);

    // 現在位置から直接スムーズスクロールする場合
    if (useSmoothOnly) {
        scrollAreaRef.value.scrollTo({
            top: targetY,
            behavior: smooth ? 'smooth' : 'instant',
        });
        return;
    }

    // 選択日が今日でない場合 (初期スクロール位置が 0)
    if (initialScrollY === 0) {
        // 番組表の先頭にスクロール
        scrollAreaRef.value.scrollTo({
            top: 0,
            behavior: 'instant',
        });
        return;
    }

    // まず初期位置に即座にスクロール (これがスクロールの起点)
    scrollAreaRef.value.scrollTo({
        top: initialScrollY,
        behavior: 'instant',
    });

    // スムーズスクロールが不要な場合はここで終了
    if (!smooth) {
        return;
    }

    // 少し遅延を入れてからスムーズスクロール (初期位置への即座のスクロールが完了してから)
    setTimeout(() => {
        if (scrollAreaRef.value === null) return;
        scrollAreaRef.value.scrollTo({
            top: targetY,
            behavior: 'smooth',
        });
    }, 50);
}

/**
 * 番組表の先頭 (4時の位置) へスクロール
 * 「次の日を見る」を押した時に、その日の先頭を表示するために使用
 */
function scrollToStart(): void {
    if (scrollAreaRef.value === null) return;

    scrollAreaRef.value.scrollTo({
        top: 0,
        behavior: 'instant',  // 日付変更時は即座に移動
    });
}

/**
 * 番組表の末尾 (28時/翌4時の位置) へスクロール
 * 「前の日を見る」を押した時に、その日の末尾 (翌0時近辺) を表示するために使用
 */
function scrollToEnd(): void {
    if (scrollAreaRef.value === null) return;

    // 24時間分のスクロール位置 (番組表の末尾) を計算
    const maxScrollY = scrollAreaRef.value.scrollHeight - scrollAreaRef.value.clientHeight;
    scrollAreaRef.value.scrollTo({
        top: maxScrollY,
        behavior: 'instant',  // 日付変更時は即座に移動
    });
}

// 外部から呼び出せるようにメソッドを公開
defineExpose({
    scrollToHour,
    scrollToCurrentTime,
    scrollToStart,
    scrollToEnd,
});

// ライフサイクル
onMounted(async () => {
    // ウィンドウリサイズイベントリスナーを登録
    // 画面回転やウィンドウサイズ変更時に、デバイスタイプ判定などの再計算をトリガーする
    window.addEventListener('resize', onWindowResize);

    // wheel イベントを passive: false で登録
    // Vue 3 のデフォルトでは wheel イベントは passive: true で登録されるため、
    // event.preventDefault() が効かない。手動で { passive: false } を指定して登録することで、
    // チルトホイールや Shift+ホイールでの横スクロールを JavaScript で制御可能にする
    if (scrollAreaRef.value !== null) {
        scrollAreaRef.value.addEventListener('wheel', onWheel, { passive: false });
    }

    // 直近のタッチ操作時刻を更新 (パッシブリスナーで負荷を最小限に)
    window.addEventListener('touchstart', onTouchStart, { passive: true });

    // データロード完了後に初期スクロール位置を設定
    await nextTick();
    if (scrollAreaRef.value !== null) {
        pendingScrollLeft.value = scrollAreaRef.value.scrollLeft;
        pendingScrollTop.value = scrollAreaRef.value.scrollTop;
        applyScrollUpdate();
        setupStickyObserver();
    }
    // 少し遅延を入れて DOM が完全にレンダリングされるのを待つ
    setTimeout(() => {
        scrollToCurrentTime();
        updateVisibleRange(currentScrollTop);
    }, 100);
});

onBeforeUnmount(() => {
    // ウィンドウリサイズイベントリスナーを解除
    window.removeEventListener('resize', onWindowResize);
    // タッチ操作の検知リスナーを解除
    window.removeEventListener('touchstart', onTouchStart);
    // デバウンスタイマーをクリア
    if (resizeDebounceTimerId !== null) {
        clearTimeout(resizeDebounceTimerId);
        resizeDebounceTimerId = null;
    }

    // wheel イベントリスナーを解除
    if (scrollAreaRef.value !== null) {
        scrollAreaRef.value.removeEventListener('wheel', onWheel);
    }

    if (scrollUpdateAnimationId.value !== null) {
        cancelAnimationFrame(scrollUpdateAnimationId.value);
    }
    if (stickyUpdateAnimationId !== null) {
        cancelAnimationFrame(stickyUpdateAnimationId);
    }
    if (stickyObserveAnimationId !== null) {
        cancelAnimationFrame(stickyObserveAnimationId);
    }
    if (stickyObserver !== null) {
        stickyObserver.disconnect();
        stickyObserver = null;
        stickyProgramCells.clear();
    }
    // モーメンタムアニメーションをキャンセル
    if (momentumAnimationId.value !== null) {
        cancelAnimationFrame(momentumAnimationId.value);
    }
});

onUnmounted(() => {
    // モーメンタムアニメーションをキャンセル (念のため)
    if (momentumAnimationId.value !== null) {
        cancelAnimationFrame(momentumAnimationId.value);
    }
});

// チャンネルデータが変更されたら（初回ロード完了時など）、現在時刻にスクロール
watch(() => props.channels, async (newChannels, oldChannels) => {
    programTimeCache.clear();
    splitStateCache.clear();
    updateVisibleRange(currentScrollTop);
    scheduleStickyObserveUpdate();

    // 初回ロード時（空→データあり）のみスクロール
    if (oldChannels.length === 0 && newChannels.length > 0) {
        await nextTick();
        setTimeout(() => {
            scrollToCurrentTime();
            scheduleStickyObserveUpdate();
        }, 100);
    }
}, { deep: false });

watch([hourHeight, viewportHeight], () => {
    updateVisibleRange(currentScrollTop);
    scheduleStickyObserveUpdate();
});

watch(channelHeaderHeight, () => {
    scheduleStickyObserveUpdate();
});

watch(() => timetableStore.display_start_time, (value) => {
    displayStartMs.value = value.valueOf();
}, { immediate: true });

// 日付変更時のスクロール処理は親コンポーネント (TimeTable.vue) で制御する
// 「次の日を見る」→ 先頭 (4:00) へ、「前の日を見る」→ 末尾 (28時) へスクロール
// そのため、ここでは自動的なスクロールリセットは行わない

</script>
<style lang="scss" scoped>
.timetable-grid {
    display: flex;
    flex-direction: column;
    position: relative;
    flex-grow: 1;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background: rgb(var(--v-theme-background));

    // スクロール可能な領域
    &__scroll-area {
        flex-grow: 1;
        overflow: auto;
        min-width: 0;
        // App.vue の html 要素に設定された overscroll-behavior-x: none をオーバーライド
        // これにより、横方向のスクロールが正常に動作する
        overscroll-behavior: auto !important;

        // 「マウスなどの精密なポインタ」があり、かつ「ホバー可能」な場合のみ JS スクロールを適用
        @media (hover: hover) and (pointer: fine) {
            touch-action: none !important;
            cursor: grab;
        }

        // タッチ操作が利用できる環境ではブラウザのネイティブスクロールを優先
        @media (any-pointer: coarse) {
            touch-action: pan-x pan-y !important;
        }

        // タッチデバイス (スマホ・タブレット) ではネイティブスクロールを使用
        // タッチ操作でのスクロールはブラウザネイティブの方がスムーズで自然な動作になる
        @media (hover: none) {
            touch-action: pan-x pan-y !important;
            cursor: default;
        }

        // ドラッグ中状態: カーソルを grabbing に強制
        // 子要素 (番組セルなど) の cursor: pointer をオーバーライドするため !important を使用
        &--dragging {
            cursor: grabbing !important;
            // ドラッグ中は全ての子要素のカーソルも grabbing にする
            * {
                cursor: grabbing !important;
            }
        }
    }

    // レイアウト
    &__layout {
        display: flex;
        flex-direction: column;
    }

    // ヘッダー行
    &__header-row {
        display: flex;
        position: sticky;
        top: -0.1px;  // レンダリングによってはわずかに下が見えてしまう問題の対策
        left: 0;
        z-index: 35;
        background: rgb(var(--v-theme-background-lighten-1));
    }

    // 本体行
    &__body-row {
        display: flex;
        position: relative;
    }

    // 左上の固定コーナー
    &__corner {
        position: sticky;
        top: 0;
        left: 0;
        background: rgb(var(--v-theme-background-lighten-1));
        border-left: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-right: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        z-index: 40;
    }

    // チャンネルヘッダー (上部に固定、横スクロールに追従)
    &__channel-headers {
        display: flex;
        background: rgb(var(--v-theme-background-lighten-1));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        z-index: 35;
    }

    // 時刻スケール (左側に固定、縦スクロールに追従)
    &__time-scale {
        position: sticky;
        left: 0;
        background: rgb(var(--v-theme-background-lighten-1));
        flex-shrink: 0;
        z-index: 30;
    }

    // 番組グリッド本体
    &__content {
        position: relative;
        width: 100%;
        height: 100%;
        min-height: 0;
        overflow: visible;
    }

    // チャンネル列
    // position: relative を設定して、内部の絶対配置要素 (番組セル) の基準位置とする
    &__channel-column {
        position: absolute;
        top: 0;
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }

    // チャンネル背景
    &__channel-background {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        z-index: 0;
        background: var(--timetable-empty-cell-background);
    }

    // 日付遷移ボタン
    // position: fixed を使用して、ビューポートの中央に配置する
    // これにより、横スクロールしてもボタンは常に画面中央に表示される
    &__next-day-button,
    &__prev-day-button {
        position: fixed;
        left: 50%;
        transform: translateX(-50%);
        z-index: 50;
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 8px 16px;
        font-size: 14px;
        color: rgb(var(--v-theme-text)) !important;
        background: rgb(var(--v-theme-background-lighten-1)) !important;
        border: 1px solid rgb(var(--v-theme-background-lighten-2));
    }

    &__next-day-button {
        bottom: 16px;
        @include smartphone-vertical {
            // スマホ縦画面ではボトムナビゲーションバーの上に配置
            bottom: calc(56px + 14px + env(safe-area-inset-bottom));
        }
    }

    &__prev-day-button {
        // ヘッダー (65px) + チャンネルヘッダー + 余白
        top: calc(65px + var(--timetable-channel-header-height) + 8px);
        @include tablet-vertical {
            // タブレット縦画面ではヘッダー + コントロール系ヘッダー + チャンネルヘッダー + 余白
            top: calc(65px + 56px + var(--timetable-channel-header-height) + 8px);
        }
        @include smartphone-horizontal {
            // スマホ横画面ではヘッダーなし
            top: calc(48px + var(--timetable-channel-header-height) + 8px);
        }
        @include smartphone-vertical {
            // スマホ縦画面ではヘッダーなし、モバイルコントロールバーの高さを考慮
            top: calc(48px + 72px + var(--timetable-channel-header-height) + 8px);
        }
    }
}

// フェードトランジション
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

</style>
