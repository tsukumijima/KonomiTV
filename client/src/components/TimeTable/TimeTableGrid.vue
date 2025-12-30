<template>
    <div class="timetable-grid" ref="gridContainerRef"
        @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerUp">
        <!-- スクロール可能な領域 -->
        <div class="timetable-grid__scroll-area" ref="scrollAreaRef" @scroll="onScroll">
            <!-- CSS Grid を使ったレイアウト -->
            <div class="timetable-grid__layout"
                :style="{
                    gridTemplateColumns: `${TIME_SCALE_WIDTH}px ${totalWidth}px`,
                    gridTemplateRows: `${CHANNEL_HEADER_HEIGHT}px ${totalHeight}px`,
                }">
                <!-- 左上の固定コーナー -->
                <div class="timetable-grid__corner">
                </div>
                <!-- チャンネルヘッダー (上部に固定、横スクロールに追従) -->
                <div class="timetable-grid__channel-headers">
                    <TimeTableChannelHeader
                        v-for="channelData in channels" :key="channelData.channel.id"
                        :channel="channelData.channel"
                        :width="channelWidth"
                    />
                </div>
                <!-- 時刻スケール (左側に固定、縦スクロールに追従) -->
                <div class="timetable-grid__time-scale">
                    <TimeTableTimeScale
                        :selectedDate="props.selectedDate"
                        :hourHeight="hourHeight"
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
                            :style="{ height: `${totalHeight}px`, background: EMPTY_CELL_BACKGROUND_COLOR }">
                        </div>
                        <!-- 番組セル -->
                        <TimeTableProgramCell
                            v-for="program in channelData.programs" :key="program.id"
                            :program="program"
                            :channel="channelData.channel"
                            :selectedDate="props.selectedDate"
                            :hourHeight="hourHeight"
                            :channelWidth="channelWidth"
                            :scrollTop="scrollTop"
                            :viewportHeight="viewportHeight"
                            :isSelected="selectedProgramId === program.id"
                            :isPast="isPastProgram(program)"
                            @click="onProgramClick(program)"
                            @show-detail="$emit('show-program-detail', program.id, channelData, program)"
                            @quick-reserve="$emit('quick-reserve', program.id, channelData, program)"
                        />
                        <!-- サブチャンネル番組 (マルチ編成) -->
                        <template v-if="channelData.subchannel_programs">
                            <TimeTableProgramCell
                                v-for="program in getSubchannelPrograms(channelData)" :key="program.id"
                                :program="program"
                                :channel="channelData.channel"
                                :selectedDate="props.selectedDate"
                                :hourHeight="hourHeight"
                                :channelWidth="channelWidth / 2"
                                :scrollTop="scrollTop"
                                :viewportHeight="viewportHeight"
                                :isSubchannel="true"
                                :isSelected="selectedProgramId === program.id"
                                :isPast="isPastProgram(program)"
                                @click="onProgramClick(program)"
                                @show-detail="$emit('show-program-detail', program.id, channelData, program)"
                                @quick-reserve="$emit('quick-reserve', program.id, channelData, program)"
                            />
                        </template>
                    </div>
                    <!-- 現在時刻バー -->
                    <TimeTableCurrentTimeLine
                        :selectedDate="props.selectedDate"
                        :hourHeight="hourHeight"
                        :totalWidth="totalWidth"
                    />
                </div>
            </div>
        </div>
        <!-- 日付遷移フロートボタン (次の日へ) -->
        <Transition name="fade">
            <v-btn class="timetable-grid__next-day-button" variant="elevated" color="secondary"
                v-if="showNextDayButton"
                @click="$emit('go-to-next-day')">
                <Icon icon="fluent:chevron-down-20-regular" width="20px" />
                <span>次の日を見る</span>
            </v-btn>
        </Transition>
        <!-- 日付遷移フロートボタン (前の日へ) -->
        <Transition name="fade">
            <v-btn class="timetable-grid__prev-day-button" variant="elevated" color="secondary"
                v-if="showPrevDayButton"
                @click="$emit('go-to-previous-day')">
                <Icon icon="fluent:chevron-up-20-regular" width="20px" />
                <span>前の日を見る</span>
            </v-btn>
        </Transition>
    </div>
</template>
<script lang="ts" setup>

import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import type { Dayjs } from 'dayjs';

import TimeTableChannelHeader from '@/components/TimeTable/TimeTableChannelHeader.vue';
import TimeTableCurrentTimeLine from '@/components/TimeTable/TimeTableCurrentTimeLine.vue';
import TimeTableProgramCell from '@/components/TimeTable/TimeTableProgramCell.vue';
import TimeTableTimeScale from '@/components/TimeTable/TimeTableTimeScale.vue';
import { ITimeTableChannel, ITimeTableProgram } from '@/services/Programs';
import useSettingsStore from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import { TimeTableUtils } from '@/utils/TimeTableUtils';


// 定数
const TIME_SCALE_WIDTH = TimeTableUtils.TIME_SCALE_WIDTH;
const CHANNEL_HEADER_HEIGHT = TimeTableUtils.CHANNEL_HEADER_HEIGHT;
const EMPTY_CELL_BACKGROUND_COLOR = TimeTableUtils.EMPTY_CELL_BACKGROUND_COLOR;

// Props
const props = defineProps<{
    channels: ITimeTableChannel[];
    selectedDate: Dayjs;
    isLoading: boolean;
}>();

// Emits
const emit = defineEmits<{
    (e: 'scroll-position-change', position: { x: number; y: number }): void;
    (e: 'program-select', program_id: string | null): void;
    (e: 'show-program-detail', program_id: string, channel_data: ITimeTableChannel, program: ITimeTableProgram): void;
    (e: 'quick-reserve', program_id: string, channel_data: ITimeTableChannel, program: ITimeTableProgram): void;
    (e: 'go-to-next-day'): void;
    (e: 'go-to-previous-day'): void;
}>();

// ストア
const settingsStore = useSettingsStore();

// DOM 参照
const gridContainerRef = ref<HTMLElement | null>(null);
const scrollAreaRef = ref<HTMLElement | null>(null);

// 状態
const selectedProgramId = ref<string | null>(null);
const showNextDayButton = ref(false);
const showPrevDayButton = ref(false);
const isInitialLoadDone = ref(false);  // 初回ロードが完了したかどうか (日付変更時のスクロール制御用)
const scrollTop = ref(0);  // 現在のスクロール位置 (Y方向)
const viewportHeight = ref(0);  // 番組グリッド表示領域の高さ

// ドラッグスクロール用の状態
const isDragging = ref(false);
const dragStartX = ref(0);
const dragStartY = ref(0);
const scrollStartX = ref(0);
const scrollStartY = ref(0);
const hasMoved = ref(false);  // ドラッグ中に移動したかどうか

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
 */
const deviceType = computed(() => TimeTableUtils.getDeviceType());

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
 * 番組表の総幅 (全チャンネル分)
 */
const totalWidth = computed(() => {
    return props.channels.length * channelWidth.value;
});

/**
 * 番組表の総高さ (24時間分、ヘッダーは含まない)
 */
const totalHeight = computed(() => {
    return 24 * hourHeight.value;
});

/**
 * サブチャンネル番組を取得
 */
function getSubchannelPrograms(channelData: ITimeTableChannel): ITimeTableProgram[] {
    if (channelData.subchannel_programs === null) {
        return [];
    }
    // 全サブチャンネルの番組をフラット化して返す
    return Object.values(channelData.subchannel_programs).flat();
}

/**
 * 番組が過去のものかどうか判定
 */
function isPastProgram(program: ITimeTableProgram): boolean {
    const end_time = dayjs(program.end_time);
    return end_time.isBefore(dayjs());
}

/**
 * スクロールイベントハンドラ
 */
const onScroll = TimeTableUtils.throttle(() => {
    if (scrollAreaRef.value === null) return;

    const scrollX = scrollAreaRef.value.scrollLeft;
    const scrollY = scrollAreaRef.value.scrollTop;

    // スクロール位置を更新 (TimeTableProgramCell の sticky 処理用)
    scrollTop.value = scrollY;
    // ビューポート高さを更新 (チャンネルヘッダー分を引いた番組グリッドの表示領域)
    viewportHeight.value = scrollAreaRef.value.clientHeight - CHANNEL_HEADER_HEIGHT;

    // スクロール位置を親に通知
    emit('scroll-position-change', { x: scrollX, y: scrollY });

    // 日付遷移ボタンの表示判定
    const maxScrollY = scrollAreaRef.value.scrollHeight - scrollAreaRef.value.clientHeight;
    showNextDayButton.value = scrollY > maxScrollY - 100;
    showPrevDayButton.value = scrollY < 100;
}, 16);

/**
 * ポインターダウンイベントハンドラ (ドラッグスクロール開始)
 */
function onPointerDown(event: PointerEvent): void {
    // 番組セル上でのクリックは除外 (番組セル側で処理)
    const target = event.target as HTMLElement;
    if (target.closest('.timetable-program-cell') || target.closest('.v-btn')) {
        return;
    }

    isDragging.value = true;
    hasMoved.value = false;
    dragStartX.value = event.clientX;
    dragStartY.value = event.clientY;

    if (scrollAreaRef.value !== null) {
        scrollStartX.value = scrollAreaRef.value.scrollLeft;
        scrollStartY.value = scrollAreaRef.value.scrollTop;
    }

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

    // ポインターキャプチャを設定
    (event.target as HTMLElement).setPointerCapture(event.pointerId);

    // テキスト選択を防止
    event.preventDefault();
}

/**
 * ポインタームーブイベントハンドラ (ドラッグスクロール中)
 */
function onPointerMove(event: PointerEvent): void {
    if (isDragging.value === false || scrollAreaRef.value === null) return;

    const deltaX = dragStartX.value - event.clientX;
    const deltaY = dragStartY.value - event.clientY;

    // 移動閾値を超えたらドラッグとみなす
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
    if (isDragging.value === false) return;

    isDragging.value = false;

    // ポインターキャプチャを解除
    try {
        (event.target as HTMLElement).releasePointerCapture(event.pointerId);
    } catch {
        // ポインターキャプチャが設定されていない場合は無視
    }

    // ドラッグした場合のみモーメンタムスクロールを開始
    if (hasMoved.value) {
        startMomentumScroll();
    }
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
        emit('program-select', null);
    } else {
        selectedProgramId.value = program.id;
        emit('program-select', program.id);
    }
}

/**
 * 指定した時刻にスクロール
 */
function scrollToHour(hour: number): void {
    if (scrollAreaRef.value === null) return;

    // 4時起点からの時間を計算
    const hoursFromStart = hour >= 4 ? hour - 4 : hour + 20;
    const scrollY = hoursFromStart * hourHeight.value;

    scrollAreaRef.value.scrollTo({
        top: scrollY,
        behavior: 'smooth',
    });
}

/**
 * 現在時刻にスクロール
 */
function scrollToCurrentTime(): void {
    if (scrollAreaRef.value === null) return;

    const now = dayjs();
    const dayStart = props.selectedDate;

    // 現在時刻が選択日の範囲外の場合は何もしない
    const dayEnd = dayStart.add(1, 'day');
    if (now.isBefore(dayStart) || now.isAfter(dayEnd)) {
        return;
    }

    // 現在時刻の Y 座標を計算 (ヘッダー分は含まない)
    const elapsedMs = now.valueOf() - dayStart.valueOf();
    const elapsedHours = elapsedMs / (1000 * 60 * 60);
    const currentTimeY = elapsedHours * hourHeight.value;

    // ビューポートの上から 15〜20% の位置に現在時刻バーが来るようにスクロール
    const viewportOffset = scrollAreaRef.value.clientHeight * 0.17;

    scrollAreaRef.value.scrollTo({
        top: Math.max(0, currentTimeY - viewportOffset),
        behavior: 'smooth',
    });
}

// 外部から呼び出せるようにメソッドを公開
defineExpose({
    scrollToHour,
    scrollToCurrentTime,
});

// ライフサイクル
onMounted(async () => {
    // データロード完了後に初期スクロール位置を設定
    await nextTick();
    // 少し遅延を入れて DOM が完全にレンダリングされるのを待つ
    setTimeout(() => {
        scrollToCurrentTime();
    }, 100);
});

onUnmounted(() => {
    // モーメンタムアニメーションをキャンセル
    if (momentumAnimationId.value !== null) {
        cancelAnimationFrame(momentumAnimationId.value);
    }
});

// チャンネルデータが変更されたら（初回ロード完了時など）、現在時刻にスクロール
watch(() => props.channels, async (newChannels, oldChannels) => {
    // 初回ロード時（空→データあり）のみスクロール
    if (oldChannels.length === 0 && newChannels.length > 0) {
        await nextTick();
        setTimeout(() => {
            scrollToCurrentTime();
            // 初回ロード完了フラグを立てる (日付変更時のスクロールリセットを有効化)
            isInitialLoadDone.value = true;
        }, 100);
    }
}, { deep: false });

// 日付変更時にスクロール位置をリセット
// ただし、初回ロード時は現在時刻にスクロールするため、リセットしない
watch(() => props.selectedDate, () => {
    // 初回ロード完了前は何もしない (現在時刻へのスクロールを妨げないため)
    if (!isInitialLoadDone.value) {
        return;
    }
    if (scrollAreaRef.value !== null) {
        // 4:00 の位置 (=0) にスクロール
        scrollAreaRef.value.scrollTo({ top: 0, left: 0 });
    }
});

</script>
<style lang="scss" scoped>
.timetable-grid {
    display: flex;
    flex-direction: column;
    position: relative;
    flex-grow: 1;
    min-height: 0;
    overflow: hidden;
    background: rgb(var(--v-theme-background));

    // スクロール可能な領域
    &__scroll-area {
        flex-grow: 1;
        overflow: auto;
        // スクロールバーのスタイル
        &::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        &::-webkit-scrollbar-track {
            background: rgb(var(--v-theme-background-lighten-1));
        }
        &::-webkit-scrollbar-thumb {
            background: rgb(var(--v-theme-background-lighten-2));
            border-radius: 5px;
        }
        &::-webkit-scrollbar-corner {
            background: rgb(var(--v-theme-background-lighten-1));
        }
    }

    // CSS Grid を使ったレイアウト
    &__layout {
        display: grid;
    }

    // 左上の固定コーナー (グリッド: 1行目1列目)
    &__corner {
        grid-row: 1;
        grid-column: 1;
        position: sticky;
        top: 0;
        left: 0;
        background: rgb(var(--v-theme-background-lighten-1));
        border-right: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        z-index: 30;
    }

    // チャンネルヘッダー (グリッド: 1行目2列目、上部に固定)
    &__channel-headers {
        grid-row: 1;
        grid-column: 2;
        display: flex;
        position: sticky;
        top: 0;
        background: rgb(var(--v-theme-background-lighten-1));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        z-index: 20;
    }

    // 時刻スケール (グリッド: 2行目1列目、左側に固定)
    &__time-scale {
        grid-row: 2;
        grid-column: 1;
        position: sticky;
        left: 0;
        background: rgb(var(--v-theme-background-lighten-1));
        z-index: 15;
    }

    // 番組グリッド本体 (グリッド: 2行目2列目)
    &__content {
        grid-row: 2;
        grid-column: 2;
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
    }

    &__next-day-button {
        bottom: 20px;
        @include smartphone-vertical {
            // スマホ縦画面ではボトムナビゲーションバーの上に配置
            bottom: calc(56px + 20px + env(safe-area-inset-bottom));
        }
    }

    &__prev-day-button {
        // ヘッダー (65px) + チャンネルヘッダー (CHANNEL_HEADER_HEIGHT) + 余白
        top: calc(65px + 48px + 20px);
        @include smartphone-horizontal {
            // スマホ横画面ではヘッダーなし
            top: calc(48px + 20px);
        }
        @include smartphone-vertical {
            // スマホ縦画面ではヘッダーなし、モバイルコントロールバーの高さを考慮
            top: calc(48px + 100px + 20px);
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
