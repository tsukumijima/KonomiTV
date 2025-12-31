<template>
    <div class="timetable-program-cell"
        ref="cellRef"
        :class="{
            'timetable-program-cell--selected': isSelected,
            'timetable-program-cell--expanded': isExpanded,
            'timetable-program-cell--past': isPast,
            'timetable-program-cell--subchannel': isSubchannel,
            'timetable-program-cell--reserved': hasReservation,
            'timetable-program-cell--recording': isRecording,
            'timetable-program-cell--partial': isPartialRecording,
            'timetable-program-cell--unavailable': isUnavailableRecording,
            'timetable-program-cell--disabled': isReservationDisabled,
        }"
        :style="cellStyle"
        @click="onClick"
        @mouseenter="onMouseEnter"
        @mouseleave="onMouseLeave">
        <!-- ジャンルハイライト縦線 (REGZA 風) -->
        <div class="timetable-program-cell__highlight" :style="{ background: highlightColor }"></div>
        <!-- メインコンテンツ -->
        <div class="timetable-program-cell__content" :style="contentStickyStyle">
            <!-- 開始分表示 + 予約アイコン -->
            <div class="timetable-program-cell__header">
                <span class="timetable-program-cell__start-minute">{{ startMinute }}</span>
                <div class="timetable-program-cell__reservation-icon" v-if="hasReservation">
                    <Icon :icon="reservationIcon" width="14px" :style="{ color: reservationIconColor }" />
                    <div v-if="isRecording" class="timetable-program-cell__recording-icon"></div>
                    <Icon v-if="isPartialRecording" icon="fluent:warning-16-filled" width="12px" class="timetable-program-cell__warning-icon" />
                    <Icon v-if="isUnavailableRecording" icon="fluent:dismiss-circle-16-filled" width="12px" class="timetable-program-cell__error-icon" />
                </div>
            </div>
            <!-- タイトル -->
            <div class="timetable-program-cell__title" v-html="decoratedTitle"></div>
            <!-- 説明 (常に表示、はみ出た分は隠れる) -->
            <div class="timetable-program-cell__description" v-html="decoratedDescription"></div>
            <!-- アクションボタン (選択時のみ表示) -->
            <div class="timetable-program-cell__actions" v-if="isExpanded">
                <v-btn variant="flat" size="small" class="timetable-program-cell__action-button"
                    @click.stop="$emit('show-detail')">
                    <Icon icon="fluent:info-12-regular" width="16px" />
                    <span>番組詳細</span>
                </v-btn>
                <!-- 録画予約ボタン: 予約なしの場合は追加、予約ありの場合は有効/無効切替 -->
                <v-btn variant="flat" size="small"
                    class="timetable-program-cell__action-button"
                    :class="{
                        'timetable-program-cell__action-button--reserved': hasReservation && !isReservationDisabled,
                        'timetable-program-cell__action-button--disabled-reservation': isReservationDisabled,
                    }"
                    v-if="!isPast"
                    @click.stop="onQuickReserve">
                    <Icon :icon="reservationButtonIcon" width="16px" />
                    <span>{{ reservationButtonLabel }}</span>
                </v-btn>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed, nextTick, ref, watch } from 'vue';

import type { Dayjs } from 'dayjs';

import { ITimeTableChannel, ITimeTableProgram } from '@/services/Programs';
import useSettingsStore from '@/stores/SettingsStore';
import useTimeTableStore from '@/stores/TimeTableStore';
import { dayjs } from '@/utils';
import { ProgramUtils } from '@/utils/ProgramUtils';
import { TimeTableUtils } from '@/utils/TimeTableUtils';

// Props
const props = defineProps<{
    program: ITimeTableProgram;
    channel: ITimeTableChannel['channel'];
    selectedDate: Dayjs;  // 選択された日付 (4:00起点、表示開始時刻とは異なる場合がある)
    hourHeight: number;
    channelWidth: number;
    fullChannelWidth?: number;
    scrollTop: number;  // スクロール位置 (Y方向)
    viewportHeight: number;  // 番組グリッド表示領域の高さ
    channelHeaderHeight: number;
    isScrollAtBottom?: boolean;
    isSubchannel?: boolean;
    isSplit?: boolean;
    isSelected: boolean;
    isPast: boolean;
    is36HourDisplay?: boolean;  // 36時間表示モードかどうか
}>();

// Emits
const emit = defineEmits<{
    (e: 'click'): void;
    (e: 'show-detail'): void;
    (e: 'quick-reserve'): void;
}>();

// ストア
const settingsStore = useSettingsStore();
const timetableStore = useTimeTableStore();

// 状態
const isHovered = ref(false);
const cellRef = ref<HTMLElement | null>(null);
const expandedHeight = ref<number>(0);

// 定数
const RESERVATION_ICON = 'fluent:timer-16-filled';
const RESERVATION_DISABLED_ICON = 'mdi:timer-pause-outline';

/**
 * 展開状態かどうか (選択中またはホバー展開有効時にホバー中)
 */
const isExpanded = computed(() => {
    return props.isSelected || (settingsStore.settings.timetable_hover_expand && isHovered.value);
});

/**
 * 予約がある場合
 */
const hasReservation = computed(() => {
    return props.program.reservation !== null;
});

/**
 * 録画中の場合
 */
const isRecording = computed(() => {
    return props.program.reservation?.status === 'Recording';
});

/**
 * 予約が無効の場合
 */
const isReservationDisabled = computed(() => {
    return props.program.reservation?.status === 'Disabled';
});

/**
 * 一部のみ録画の場合
 */
const isPartialRecording = computed(() => {
    return props.program.reservation?.recording_availability === 'Partial';
});

/**
 * 録画不可の場合
 */
const isUnavailableRecording = computed(() => {
    return props.program.reservation?.recording_availability === 'Unavailable';
});

/**
 * 予約アイコンの色
 */
const reservationIconColor = computed(() => {
    if (isUnavailableRecording.value) {
        return 'rgb(var(--v-theme-error))';
    }
    if (isPartialRecording.value) {
        return 'rgb(var(--v-theme-warning))';
    }
    if (isReservationDisabled.value) {
        return 'rgb(var(--v-theme-text-darken-2))';
    }
    return 'rgb(var(--v-theme-success))';
});

/**
 * 予約アイコン
 */
const reservationIcon = computed(() => {
    if (isReservationDisabled.value) {
        return RESERVATION_DISABLED_ICON;
    }
    return RESERVATION_ICON;
});

/**
 * 録画予約ボタンのアイコン
 * 予約なし: 追加アイコン、予約あり有効: チェックアイコン、予約あり無効: オフアイコン
 */
const reservationButtonIcon = computed(() => {
    if (!hasReservation.value) {
        return 'mdi:timer-plus-outline';  // 追加
    }
    if (isReservationDisabled.value) {
        return 'mdi:timer-play-outline';  // 無効 → 有効に切替
    }
    return 'mdi:timer-pause-outline';  // 有効 → 無効に切替
});

/**
 * 録画予約ボタンのラベル
 * 予約なし: 録画予約、予約あり有効: 予約を無効化、予約あり無効: 予約を有効化
 */
const reservationButtonLabel = computed(() => {
    if (!hasReservation.value) {
        return '録画予約';
    }
    if (isReservationDisabled.value) {
        return '予約を有効化';
    }
    return '予約を無効化';
});

/**
 * 開始分 (00, 30 など)
 */
const startMinute = computed(() => {
    const startTime = dayjs(props.program.start_time);
    return startTime.minute().toString().padStart(2, '0');
});

/**
 * ジャンルのハイライト色
 */
const genreHighlightColor = computed(() => {
    const genreMajor = props.program.genres?.[0]?.major;
    const colors = TimeTableUtils.getGenreColors(genreMajor, settingsStore.settings.timetable_genre_colors);
    return colors.highlight;
});

/**
 * ハイライト色 (過去番組はグレー系に統一)
 */
const highlightColor = computed(() => {
    if (props.isPast) {
        return '#b0b0b0';
    }
    return genreHighlightColor.value;
});

/**
 * セルの背景色
 */
const cellBackgroundColor = computed(() => {
    if (props.isPast) {
        return '#e6e6e6';
    }
    // 録画不可の場合は赤背景
    if (isUnavailableRecording.value) {
        return '#f8d7da';
    }
    // 一部のみ録画の場合は黄色背景
    if (isPartialRecording.value) {
        return '#fff3cd';
    }
    // 通常はジャンル色の淡い版
    const genreMajor = props.program.genres?.[0]?.major;
    const colors = TimeTableUtils.getGenreColors(genreMajor, settingsStore.settings.timetable_genre_colors);
    return colors.background;
});

/**
 * セルの Y 座標 (ヘッダー分を含まない、番組グリッド内の座標)
 * 36時間表示モード時は表示開始時刻 (16:00) を基準に計算する
 */
const cellY = computed(() => {
    const startTime = dayjs(props.program.start_time);
    // 表示開始時刻を取得 (36時間表示時は16:00、通常は4:00)
    const displayStart = timetableStore.getDisplayStartTime();
    return TimeTableUtils.calculateProgramY(
        startTime,
        displayStart,
        props.hourHeight,
        props.channelHeaderHeight,
    ) - props.channelHeaderHeight;
});

/**
 * セルの高さ
 * 番組が番組表の下端を超える場合はクリップする
 * 通常: 28時 (翌4時) でクリップ、36時間表示: 40時 (翌16時) でクリップ
 */
const gridTotalHeight = computed(() => {
    return (props.is36HourDisplay ? 36 : 24) * props.hourHeight;
});

const cellHeight = computed(() => {
    const rawHeight = TimeTableUtils.calculateProgramHeight(props.program.duration, props.hourHeight);

    // セルの下端が番組表の下端を超える場合はクリップ
    const cellBottom = cellY.value + rawHeight;
    if (cellBottom > gridTotalHeight.value) {
        // クリップされた高さを計算 (最小高さは確保)
        const clippedHeight = gridTotalHeight.value - cellY.value;
        return Math.max(clippedHeight, 20);
    }

    return Math.max(rawHeight, 20);  // 最小高さを確保
});

/**
 * セルのスタイル
 * 展開時は高さを auto にしてコンテンツに応じて伸縮可能にする
 */
const cellStyle = computed(() => {
    const fullWidth = props.fullChannelWidth ?? props.channelWidth;
    const isSplitWidth = props.isSplit === true && props.channelWidth < fullWidth;

    // サブチャンネルの場合は右半分に配置
    const left = props.isSubchannel && isSplitWidth ? props.channelWidth : 0;
    const resolvedLeft = isExpanded.value && isSplitWidth ? 0 : left;
    const resolvedWidth = isExpanded.value && isSplitWidth ? fullWidth : props.channelWidth;

    // 展開状態かどうかで height の扱いを変える
    // 展開時は minHeight のみ設定し、height は auto (CSS 側で制御) になる
    const style: Record<string, string> = {
        top: `${cellY.value}px`,
        left: `${resolvedLeft}px`,
        width: `${resolvedWidth}px`,
        minHeight: `${cellHeight.value}px`,
        background: cellBackgroundColor.value,
    };

    // 非展開時のみ高さを固定
    if (!isExpanded.value) {
        style.height = `${cellHeight.value}px`;
    }

    // 展開時に下端がはみ出す場合は、表示領域内に収まるよう上方向にずらす
    if (isExpanded.value && props.viewportHeight > 0 && props.isScrollAtBottom === true) {
        const effectiveHeight = expandedHeight.value > 0 ? expandedHeight.value : cellHeight.value;
        const viewportBottom = props.scrollTop + props.viewportHeight;
        const cellBottom = cellY.value + effectiveHeight;
        const isLastRow = cellY.value + cellHeight.value >= gridTotalHeight.value - 1;
        if (cellBottom > viewportBottom && isLastRow) {
            const overflow = cellBottom - viewportBottom;
            const maxShift = Math.max(0, cellY.value - props.scrollTop);
            const shiftY = Math.min(overflow, maxShift);
            if (shiftY > 0) {
                style.transform = `translateY(-${shiftY}px)`;
            }
        }
    }

    return style;
});

/**
 * コンテンツの sticky オフセット (EMWUI 風スティッキー処理)
 * セルがビューポートの上端を超えている場合、コンテンツを下にオフセットして
 * 常に見えるようにする
 */
const contentStickyStyle = computed(() => {
    // ビューポートがまだ初期化されていない場合はスキップ
    if (props.viewportHeight <= 0) {
        return {};
    }

    const y = cellY.value;
    const height = cellHeight.value;
    const scrollY = props.scrollTop;

    // セルの上端がビューポートより上にある場合 (上にはみ出ている)
    // かつ、セルの下端がビューポート内にある場合
    if (y < scrollY && y + height > scrollY) {
        // オフセット量 = スクロール位置 - セルの上端
        // ただし、セルの下端がビューポート内に収まるようにオフセットを制限
        // (コンテンツが見切れないように最低限の余白を確保)
        const offset = scrollY - y;
        const maxOffset = height - 60;  // 最低60pxはセル内に残す (タイトル分)

        if (offset > 0 && offset < maxOffset) {
            return {
                paddingTop: `${offset}px`,
            };
        } else if (offset >= maxOffset) {
            return {
                paddingTop: `${maxOffset}px`,
            };
        }
    }

    // セルの下端がビューポートより下にある場合 (下にはみ出ている)
    // かつ、セルの上端がビューポート内にある場合
    // → この場合は特別な処理は不要 (通常通り上から表示すればよい)

    return {};
});

/**
 * 装飾されたタイトル (囲み文字ハイライト)
 */
const decoratedTitle = computed(() => {
    return ProgramUtils.decorateProgramInfo(props.program, 'title');
});

/**
 * 装飾された説明 (囲み文字ハイライト)
 */
const decoratedDescription = computed(() => {
    return ProgramUtils.decorateProgramInfo(props.program, 'description');
});

/**
 * クリックイベントハンドラ
 */
function onClick(): void {
    emit('click');
}

/**
 * マウスエンターイベントハンドラ
 */
function onMouseEnter(): void {
    isHovered.value = true;
}

/**
 * マウスリーブイベントハンドラ
 */
function onMouseLeave(): void {
    isHovered.value = false;
}

/**
 * クイック録画予約
 */
function onQuickReserve(): void {
    emit('quick-reserve');
}

// 展開時にセルの実高さを取得する
watch(isExpanded, async (value) => {
    if (value === false) {
        expandedHeight.value = 0;
        return;
    }

    await nextTick();
    if (cellRef.value !== null) {
        expandedHeight.value = Math.max(cellRef.value.getBoundingClientRect().height, cellHeight.value);
    }
});

</script>
<style lang="scss" scoped>

.timetable-program-cell {
    display: flex;
    align-items: stretch;
    position: absolute;
    overflow: hidden;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
    cursor: pointer;
    transition: box-shadow 0.15s ease, z-index 0s;
    user-select: none;
    z-index: 1;  // チャンネル背景 (z-index: 0) より上に表示

    &:hover {
        z-index: 5;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }

    // 選択状態: 現在時刻バー (z-index: 15) より上に表示
    &--selected {
        z-index: 20 !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
    }

    // 展開状態 (選択またはホバー時): コンテンツがはみ出しても表示
    &--expanded {
        z-index: 14;
        overflow: visible;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }

    // 過去番組 (グレーアウト)
    &--past {
        .timetable-program-cell__start-minute {
            color: rgba(0, 0, 0, 0.6);
        }

        .timetable-program-cell__title {
            color: rgba(0, 0, 0, 0.6);
        }

        .timetable-program-cell__description {
            color: rgba(0, 0, 0, 0.55);
        }
    }

    // 予約あり
    &--reserved {
        border: 2.5px dashed rgb(var(--v-theme-secondary));
    }

    // 録画中
    &--recording {
        border: 2.5px dashed rgb(var(--v-theme-secondary));
    }

    // 一部のみ録画
    &--partial {
        border: 2.5px dashed rgb(var(--v-theme-warning));
    }

    // 録画不可
    &--unavailable {
        border: 2.5px dashed rgb(var(--v-theme-error));
    }

    // 予約無効
    &--disabled {
        border: 2.5px dashed rgb(var(--v-theme-text-darken-2));
    }

    // ジャンルハイライト縦線 (REGZA 風)
    &__highlight {
        flex-shrink: 0;
        width: 5px;
        height: auto;
        align-self: stretch;
    }

    // メインコンテンツ
    &__content {
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        padding: 2px 4px;
        min-width: 0;
        overflow: hidden;

        // 展開状態ではオーバーフローを許可
        .timetable-program-cell--expanded & {
            overflow: visible;
        }
    }

    // 開始分 + 予約アイコンの行
    &__header {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    // 開始分
    &__start-minute {
        flex-shrink: 0;
        font-size: 11px;
        font-weight: bold;
        color: rgba(0, 0, 0, 0.7);
        line-height: 1.2;
    }

    // 予約アイコン
    &__reservation-icon {
        display: flex;
        align-items: center;
        gap: 2px;
    }

    &__recording-icon {
        display: block;
        position: relative;
        width: 10px;
        height: 10px;
        border: 3px solid #515151;
        border-radius: 50%;
        background-color: #EF5350;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.25);
        animation: timetable-recording-background-color 2s infinite ease-in-out;
    }

    &__warning-icon {
        color: rgb(var(--v-theme-warning));
    }

    &__error-icon {
        color: rgb(var(--v-theme-error));
    }

    // タイトル
    // EMWUI 風: タイトルは全表示を優先し、縮小しない
    &__title {
        flex-shrink: 0;  // タイトルは縮小させない（全表示優先）
        font-size: 12px;
        font-weight: bold;
        color: rgba(0, 0, 0, 0.9);
        line-height: 1.3;
        word-break: break-all;  // 長いタイトルは強制的に折り返し
    }

    // 説明 (タイトルを全表示した後の残り領域に表示)
    // 領域が足りない場合は overflow: hidden で隠れる
    // 展開時はボタンを概要直下に表示するため flex-grow を無効化
    &__description {
        flex-grow: 1;
        flex-shrink: 1;  // 説明は縮小可能
        margin-top: 2px;
        font-size: 11px;
        color: rgba(0, 0, 0, 0.7);
        line-height: 1.4;
        overflow: hidden;
        min-height: 0;  // flex アイテムがオーバーフローしないように

        // 展開状態ではボタンが概要直下に来るよう flex-grow を無効化
        // これにより余白はボタンの下に表示される (EMWUI と同様)
        .timetable-program-cell--expanded & {
            flex-grow: 0;
        }
    }

    // アクションボタン (縦並びに変更、番組概要の直下に配置)
    &__actions {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 8px;
        padding-top: 8px;
        padding-bottom: 6px;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
    }

    &__action-button {
        width: 100%;
        height: 32px !important;
        font-size: 12px;
        background: rgba(0, 0, 0, 0.1) !important;
        color: rgba(0, 0, 0, 0.8) !important;

        :deep(.v-btn__content) {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }
    }
}

@keyframes timetable-recording-background-color {
    0% {
        background-color: #EF5350;
    }
    50% {
        background-color: #FFCDD2;
    }
    100% {
        background-color: #EF5350;
    }
}

</style>
