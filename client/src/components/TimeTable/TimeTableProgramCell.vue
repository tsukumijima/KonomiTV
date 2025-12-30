<template>
    <div class="timetable-program-cell"
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
        <div class="timetable-program-cell__highlight" :style="{ background: genreHighlightColor }"></div>
        <!-- メインコンテンツ -->
        <div class="timetable-program-cell__content" :style="contentStickyStyle">
            <!-- 開始分表示 -->
            <span class="timetable-program-cell__start-minute">{{ startMinute }}</span>
            <!-- 予約アイコン -->
            <div class="timetable-program-cell__reservation-icon" v-if="hasReservation">
                <Icon :icon="reservationIcon" width="14px" :style="{ color: reservationIconColor }" />
                <Icon v-if="isPartialRecording" icon="fluent:warning-16-filled" width="12px" class="timetable-program-cell__warning-icon" />
                <Icon v-if="isUnavailableRecording" icon="fluent:dismiss-circle-16-filled" width="12px" class="timetable-program-cell__error-icon" />
            </div>
            <!-- タイトル -->
            <div class="timetable-program-cell__title" v-html="decoratedTitle"></div>
            <!-- 説明 (常に表示、はみ出た分は隠れる) -->
            <div class="timetable-program-cell__description" v-html="decoratedDescription"></div>
            <!-- アクションボタン (選択時のみ表示) -->
            <div class="timetable-program-cell__actions" v-if="isExpanded">
                <v-btn variant="flat" size="small" class="timetable-program-cell__action-button"
                    @click.stop="$emit('show-detail')">
                    <Icon icon="fluent:info-16-regular" width="16px" />
                    <span>番組詳細</span>
                </v-btn>
                <v-btn variant="flat" size="small" class="timetable-program-cell__action-button"
                    v-if="!isPast"
                    :disabled="!canAddReservation"
                    @click.stop="onQuickReserve">
                    <Icon icon="fluent:timer-16-regular" width="16px" />
                    <span>録画予約</span>
                </v-btn>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed, ref } from 'vue';

import type { Dayjs } from 'dayjs';

import { ITimeTableChannel, ITimeTableProgram } from '@/services/Programs';
import useSettingsStore from '@/stores/SettingsStore';
import { dayjs } from '@/utils';
import { ProgramUtils } from '@/utils/ProgramUtils';
import { TimeTableUtils } from '@/utils/TimeTableUtils';

// Props
const props = defineProps<{
    program: ITimeTableProgram;
    channel: ITimeTableChannel['channel'];
    selectedDate: Dayjs;
    hourHeight: number;
    channelWidth: number;
    scrollTop: number;  // スクロール位置 (Y方向)
    viewportHeight: number;  // 番組グリッド表示領域の高さ
    isSubchannel?: boolean;
    isSelected: boolean;
    isPast: boolean;
}>();

// Emits
const emit = defineEmits<{
    (e: 'click'): void;
    (e: 'show-detail'): void;
    (e: 'quick-reserve'): void;
}>();

// ストア
const settingsStore = useSettingsStore();

// 状態
const isHovered = ref(false);

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
 * 録画予約を追加できるか (EDCB バックエンドのみ & 過去番組でない)
 */
const canAddReservation = computed(() => {
    // TODO: EDCB バックエンドかどうかの判定を追加
    return !props.isPast && !hasReservation.value;
});

/**
 * 予約アイコン
 */
const reservationIcon = computed(() => {
    return 'fluent:timer-16-filled';
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
 * セルの背景色
 */
const cellBackgroundColor = computed(() => {
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
 */
const cellY = computed(() => {
    const startTime = dayjs(props.program.start_time);
    const dayStart = props.selectedDate;
    return TimeTableUtils.calculateProgramY(startTime, dayStart, props.hourHeight)
        - TimeTableUtils.CHANNEL_HEADER_HEIGHT;
});

/**
 * セルの高さ
 */
const cellHeight = computed(() => {
    const height = TimeTableUtils.calculateProgramHeight(props.program.duration, props.hourHeight);
    return Math.max(height, 20);  // 最小高さを確保
});

/**
 * セルのスタイル
 * 展開時は高さを auto にしてコンテンツに応じて伸縮可能にする
 */
const cellStyle = computed(() => {
    // サブチャンネルの場合は右半分に配置
    const left = props.isSubchannel ? props.channelWidth : 0;

    // 展開状態かどうかで height の扱いを変える
    // 展開時は minHeight のみ設定し、height は auto (CSS 側で制御) になる
    const style: Record<string, string> = {
        top: `${cellY.value}px`,
        left: `${left}px`,
        width: `${props.channelWidth}px`,
        minHeight: `${cellHeight.value}px`,
        background: cellBackgroundColor.value,
    };

    // 非展開時のみ高さを固定
    if (!isExpanded.value) {
        style.height = `${cellHeight.value}px`;
    }

    return style;
});

/**
 * コンテンツの sticky オフセット (EMWUI 風スティッキー処理)
 * セルがビューポートの上端を超えている場合、コンテンツを下にオフセットして
 * 常に見えるようにする
 */
const contentStickyStyle = computed(() => {
    // 展開状態 (選択中またはホバー中) の場合はスティッキー処理を無効化
    // 展開時はセル自体が z-index で前面に来て全体が見えるため
    if (isExpanded.value) {
        return {};
    }

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

</script>
<style lang="scss" scoped>

.timetable-program-cell {
    display: flex;
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
        z-index: 10;
        overflow: visible;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }

    // 過去番組 (グレーアウト)
    &--past {
        opacity: 0.5;
        filter: grayscale(50%);
    }

    // 予約あり
    &--reserved {
        border: 2px dashed rgb(var(--v-theme-secondary));
    }

    // 録画中
    &--recording {
        border: 2px dashed rgb(var(--v-theme-secondary));
    }

    // 一部のみ録画
    &--partial {
        border: 2px dashed rgb(var(--v-theme-warning));
    }

    // 録画不可
    &--unavailable {
        border: 2px dashed rgb(var(--v-theme-error));
    }

    // 予約無効
    &--disabled {
        border: 2px dashed rgb(var(--v-theme-text-darken-2));
    }

    // ジャンルハイライト縦線 (REGZA 風)
    &__highlight {
        flex-shrink: 0;
        width: 4px;
        height: 100%;
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
        margin-top: 1px;
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
    &__description {
        flex-grow: 1;
        flex-shrink: 1;  // 説明は縮小可能
        margin-top: 2px;
        font-size: 11px;
        color: rgba(0, 0, 0, 0.7);
        line-height: 1.4;
        overflow: hidden;
        min-height: 0;  // flex アイテムがオーバーフローしないように
    }

    // アクションボタン
    &__actions {
        display: flex;
        gap: 4px;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
    }

    &__action-button {
        flex: 1;
        min-width: 0;
        height: 28px !important;
        font-size: 11px;
        background: rgba(0, 0, 0, 0.1) !important;
        color: rgba(0, 0, 0, 0.8) !important;

        :deep(.v-btn__content) {
            display: flex;
            align-items: center;
            gap: 4px;
        }
    }
}

</style>
