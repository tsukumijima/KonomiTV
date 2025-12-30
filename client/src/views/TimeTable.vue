<template>
    <div class="route-container">
        <HeaderBar>
            <!-- PC 版では HeaderBar 内に番組表コントロールを配置 -->
            <template #timetable-controls v-if="!Utils.isSmartphoneVertical()">
                <div class="timetable-controls">
                    <!-- チャンネル種別セレクター -->
                    <v-select class="timetable-controls__channel-type" variant="outlined" density="compact" hide-details
                        :items="channelTypeItems" v-model="selectedChannelTypeDisplay"
                        @update:model-value="onChannelTypeChange">
                    </v-select>
                    <!-- 日付セレクター -->
                    <div class="timetable-controls__date">
                        <v-btn variant="flat" icon size="small" :disabled="!canGoPreviousDay" @click="goToPreviousDay">
                            <Icon icon="fluent:chevron-left-20-regular" width="20px" />
                        </v-btn>
                        <v-menu v-model="isDateMenuOpen" :close-on-content-click="false">
                            <template #activator="{ props }">
                                <v-btn variant="flat" class="timetable-controls__date-button" v-bind="props">
                                    {{ formattedSelectedDate }}
                                </v-btn>
                            </template>
                            <v-date-picker v-model="selectedDateForPicker" color="primary" @update:model-value="onDatePickerChange">
                            </v-date-picker>
                        </v-menu>
                        <v-btn variant="flat" icon size="small" :disabled="!canGoNextDay" @click="goToNextDay">
                            <Icon icon="fluent:chevron-right-20-regular" width="20px" />
                        </v-btn>
                    </div>
                    <!-- 時間セレクター -->
                    <v-select class="timetable-controls__time" variant="outlined" density="compact" hide-details
                        :items="timeItems" v-model="selectedTimeDisplay"
                        @update:model-value="onTimeChange">
                    </v-select>
                    <!-- 現在時刻に戻るボタン -->
                    <v-btn variant="flat" class="timetable-controls__now-button" icon
                        @click="goToCurrentTime"
                        v-ftooltip.bottom="'現在時刻に移動'">
                        <Icon icon="fluent:clock-20-regular" width="22px" />
                    </v-btn>
                    <!-- 設定ボタン -->
                    <v-btn variant="flat" class="timetable-controls__settings-button" icon
                        @click="isSettingsDialogOpen = true"
                        v-ftooltip.bottom="'番組表の表示設定'">
                        <Icon icon="fluent:settings-20-regular" width="22px" />
                    </v-btn>
                </div>
            </template>
        </HeaderBar>
        <main>
            <Navigation :icon-only="!Utils.isSmartphoneVertical()" />
            <div class="timetable-container" :class="{'timetable-container--loading': timetableStore.is_loading}">
                <SPHeaderBar />
                <!-- スマホ縦画面用コントロールバー -->
                <div class="timetable-controls-mobile" v-if="Utils.isSmartphoneVertical()">
                    <div class="timetable-controls-mobile__row">
                        <v-select class="timetable-controls-mobile__channel-type" variant="outlined" density="compact" hide-details
                            :items="channelTypeItems" v-model="selectedChannelTypeDisplay"
                            @update:model-value="onChannelTypeChange">
                        </v-select>
                        <v-btn variant="flat" class="timetable-controls-mobile__settings-button" icon size="small"
                            @click="isSettingsDialogOpen = true">
                            <Icon icon="fluent:settings-20-regular" width="20px" />
                        </v-btn>
                    </div>
                    <div class="timetable-controls-mobile__row">
                        <v-btn variant="flat" icon size="x-small" :disabled="!canGoPreviousDay" @click="goToPreviousDay">
                            <Icon icon="fluent:chevron-left-20-regular" width="18px" />
                        </v-btn>
                        <v-menu v-model="isDateMenuOpen" :close-on-content-click="false">
                            <template #activator="{ props }">
                                <v-btn variant="flat" class="timetable-controls-mobile__date-button" size="small" v-bind="props">
                                    {{ formattedSelectedDate }}
                                </v-btn>
                            </template>
                            <v-date-picker v-model="selectedDateForPicker" color="primary" @update:model-value="onDatePickerChange">
                            </v-date-picker>
                        </v-menu>
                        <v-btn variant="flat" icon size="x-small" :disabled="!canGoNextDay" @click="goToNextDay">
                            <Icon icon="fluent:chevron-right-20-regular" width="18px" />
                        </v-btn>
                        <v-select class="timetable-controls-mobile__time" variant="outlined" density="compact" hide-details
                            :items="timeItems" v-model="selectedTimeDisplay"
                            @update:model-value="onTimeChange">
                        </v-select>
                        <v-btn variant="flat" icon size="x-small" @click="goToCurrentTime">
                            <Icon icon="fluent:clock-20-regular" width="18px" />
                        </v-btn>
                    </div>
                </div>
                <!-- 番組表グリッド -->
                <TimeTableGrid
                    ref="timetableGridRef"
                    :channels="timetableStore.channels_data"
                    :selectedDate="timetableStore.selected_date"
                    :isLoading="timetableStore.is_loading"
                    @scroll-position-change="onScrollPositionChange"
                    @program-select="onProgramSelect"
                    @show-program-detail="onShowProgramDetail"
                    @quick-reserve="onQuickReserve"
                    @go-to-next-day="goToNextDay"
                    @go-to-previous-day="goToPreviousDay"
                />
                <!-- ローディングオーバーレイ -->
                <div class="timetable-loading-overlay" v-if="timetableStore.is_loading && !timetableStore.is_initial_load_completed">
                    <v-progress-circular indeterminate color="secondary" :size="48" :width="4"></v-progress-circular>
                    <span class="timetable-loading-overlay__text">番組表を読み込んでいます...</span>
                </div>
            </div>
        </main>
        <!-- 番組表設定ダイアログ -->
        <TimeTableSettingsDialog v-model:isOpen="isSettingsDialogOpen" />
        <!-- 番組詳細ドロワー (予約詳細ドロワーを流用) -->
        <ReservationDetailDrawer
            v-model="isDrawerOpen"
            :reservation="drawerReservation"
            :program="drawerProgram"
            :channel="drawerChannel"
            :isPastProgram="isDrawerProgramPast"
            @added="onReservationAdded"
            @updated="onReservationUpdated"
            @deleted="onReservationDeleted"
        />
    </div>
</template>
<script lang="ts" setup>

import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ReservationDetailDrawer from '@/components/Reservations/ReservationDetailDrawer.vue';
import TimeTableSettingsDialog from '@/components/Settings/TimeTableSettings.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import TimeTableGrid from '@/components/TimeTable/TimeTableGrid.vue';
import { IChannel, ChannelTypePretty } from '@/services/Channels';
import { IProgram, ITimeTableChannel, ITimeTableProgram } from '@/services/Programs';
import Reservations, { IReservation } from '@/services/Reservations';
import useSettingsStore from '@/stores/SettingsStore';
import useTimeTableStore, { CHANNEL_TYPE_DISPLAY_ORDER } from '@/stores/TimeTableStore';
import Utils, { dayjs } from '@/utils';


// ストア
const settingsStore = useSettingsStore();
const timetableStore = useTimeTableStore();

// コンポーネント参照
const timetableGridRef = ref<InstanceType<typeof TimeTableGrid> | null>(null);

// UI 状態
const isSettingsDialogOpen = ref(false);
const isDateMenuOpen = ref(false);

// ドロワー関連の状態
const isDrawerOpen = ref(false);
const drawerReservation = ref<IReservation | null>(null);
const drawerProgram = ref<IProgram | null>(null);
const drawerChannel = ref<IChannel | null>(null);
const isDrawerProgramPast = ref(false);


// チャンネルタイプの選択肢
// ChannelsStore の channels_list_with_pinned に基づいて、実際に存在するチャンネルタイプのみを表示する
// ChannelTypePretty は表示名そのもの ('ピン留め', '地デジ', 'BS' など) なので、title と value は同じ値を使用する
const channelTypeItems = computed(() => {
    const items: { title: ChannelTypePretty; value: ChannelTypePretty }[] = [];
    const availableTypes = timetableStore.available_channel_types;

    // 表示順序に従って、利用可能なチャンネルタイプのみを追加
    for (const channelType of CHANNEL_TYPE_DISPLAY_ORDER) {
        if (availableTypes.has(channelType)) {
            items.push({ title: channelType, value: channelType });
        }
    }

    return items;
});

// 選択中のチャンネルタイプの表示用値
const selectedChannelTypeDisplay = computed({
    get: () => timetableStore.selected_channel_type,
    set: (value: ChannelTypePretty) => {
        timetableStore.changeChannelType(value);
    },
});

// 時間選択の選択肢 (4時間ごと)
const timeItems = computed(() => {
    const use28Hour = settingsStore.settings.use_28hour_clock;
    const items: { title: string; value: number }[] = [];

    // 4時から28時 (翌4時) まで4時間ごと
    for (let hour = 4; hour <= 24; hour += 4) {
        const displayHour = use28Hour && hour >= 24 ? hour : (hour === 24 ? 0 : hour);
        items.push({
            title: `${displayHour.toString().padStart(2, '0')}時`,
            value: hour,
        });
    }

    return items;
});

/**
 * 現在時刻に基づいて初期表示する時間帯を計算する
 * 4時間ごとのスロット (4, 8, 12, 16, 20, 24) のうち、現在時刻を含むスロットの開始時刻を返す
 * @returns 初期表示する時間帯 (4, 8, 12, 16, 20, 24 のいずれか)
 */
function getInitialTimeSlot(): number {
    const now = dayjs();
    // 28時間表記対応: 0〜3時は前日の 24〜27時として扱う
    let hour = now.hour();
    if (hour < 4) {
        hour += 24;  // 0時→24時, 1時→25時, ...
    }
    // 4時間ごとのスロットに丸める (4, 8, 12, 16, 20, 24)
    // 例: 14時 → Math.floor((14-4)/4)*4+4 = 12
    return Math.floor((hour - 4) / 4) * 4 + 4;
}

// 選択中の時間の表示用値 (現在時刻に基づいて初期化)
const selectedTimeDisplay = ref(getInitialTimeSlot());


// 選択中の日付のフォーマット表示
const formattedSelectedDate = computed(() => {
    const date = timetableStore.selected_date;
    const month = date.month() + 1;
    const day = date.date();
    const dayOfWeek = ['日', '月', '火', '水', '木', '金', '土'][date.day()];
    return `${month}/${day} (${dayOfWeek})`;
});

// v-date-picker 用の日付値 (v-date-picker は Date 型を要求するため、境界で変換)
const selectedDateForPicker = computed({
    get: () => timetableStore.selected_date.toDate(),
    set: (value: Date) => {
        // v-date-picker は時刻を 00:00 にするので、4:00 に調整
        const adjusted = dayjs(value).hour(4).minute(0).second(0).millisecond(0);
        timetableStore.changeDate(adjusted);
    },
});

// 前の日に移動できるか
// 日単位で比較するため、'day' を第2引数に指定
const canGoPreviousDay = computed(() => {
    if (timetableStore.date_range === null) return false;
    const previous = timetableStore.selected_date.subtract(1, 'day');
    return previous.isSameOrAfter(timetableStore.date_range.earliest, 'day');
});

// 次の日に移動できるか
// 日単位で比較するため、'day' を第2引数に指定
const canGoNextDay = computed(() => {
    if (timetableStore.date_range === null) return false;
    const next = timetableStore.selected_date.add(1, 'day');
    return next.isSameOrBefore(timetableStore.date_range.latest, 'day');
});

/**
 * チャンネルタイプ変更時のハンドラ
 */
function onChannelTypeChange(value: ChannelTypePretty): void {
    timetableStore.changeChannelType(value);
}

/**
 * 日付ピッカー変更時のハンドラ
 * v-date-picker は Date 型を返すため、境界で Dayjs に変換
 */
function onDatePickerChange(value: Date): void {
    isDateMenuOpen.value = false;
    const adjusted = dayjs(value).hour(4).minute(0).second(0).millisecond(0);
    timetableStore.changeDate(adjusted);
}

/**
 * 時間変更時のハンドラ: 指定した時刻へスクロール
 */
function onTimeChange(hour: number | null): void {
    if (hour === null || timetableGridRef.value === null) return;
    timetableGridRef.value.scrollToHour(hour);
}

/**
 * 前の日へ移動
 */
function goToPreviousDay(): void {
    timetableStore.goToPreviousDay();
}

/**
 * 次の日へ移動
 */
function goToNextDay(): void {
    timetableStore.goToNextDay();
}

/**
 * 現在時刻に戻る
 */
async function goToCurrentTime(): Promise<void> {
    await timetableStore.goToCurrentTime();
    // データロード後に DOM が更新されるのを待ってからスクロール
    await nextTick();
    if (timetableGridRef.value !== null) {
        timetableGridRef.value.scrollToCurrentTime();
    }
}

/**
 * スクロール位置変更時のハンドラ
 */
function onScrollPositionChange(position: { x: number; y: number }): void {
    timetableStore.updateScrollPosition(position.x, position.y);
}

/**
 * 番組選択時のハンドラ
 */
function onProgramSelect(programId: string | null): void {
    timetableStore.selectProgram(programId);
}

/**
 * 番組詳細表示時のハンドラ
 * 番組表から番組詳細ドロワーを開く
 * @param programId 番組 ID
 * @param channelData 番組が属するチャンネルデータ
 * @param program 番組情報
 */
async function onShowProgramDetail(programId: string, channelData: ITimeTableChannel, program: ITimeTableProgram): Promise<void> {
    // 過去番組かどうかを判定
    const endTime = dayjs(program.end_time);
    isDrawerProgramPast.value = endTime.isBefore(dayjs());

    // 予約情報がある場合は、完全な IReservation を API から取得
    if (program.reservation !== null) {
        const reservation = await Reservations.fetchReservation(program.reservation.id);
        if (reservation !== null) {
            drawerReservation.value = reservation;
            drawerProgram.value = null;
            drawerChannel.value = null;
        } else {
            // 取得失敗時は番組情報のみで表示
            drawerReservation.value = null;
            drawerProgram.value = program;
            drawerChannel.value = channelData.channel;
        }
    } else {
        // 予約がない場合は番組情報とチャンネル情報を渡す
        drawerReservation.value = null;
        drawerProgram.value = program;
        drawerChannel.value = channelData.channel;
    }

    isDrawerOpen.value = true;
}

/**
 * 予約追加完了時のハンドラ
 * 番組表データを再取得して最新の予約状態を反映する
 */
async function onReservationAdded(): Promise<void> {
    // 番組表データを再取得して予約状態を更新
    await timetableStore.fetchTimeTableData();
}

/**
 * 予約更新完了時のハンドラ
 */
async function onReservationUpdated(): Promise<void> {
    // 番組表データを再取得して予約状態を更新
    await timetableStore.fetchTimeTableData();
}

/**
 * 予約削除完了時のハンドラ
 */
async function onReservationDeleted(): Promise<void> {
    // 番組表データを再取得して予約状態を更新
    await timetableStore.fetchTimeTableData();
}

/**
 * クイック録画予約時のハンドラ
 * 番組セルの「録画予約」ボタンが押された時に、ドロワーを開いて予約追加できるようにする
 * @param programId 番組 ID
 * @param channelData 番組が属するチャンネルデータ
 * @param program 番組情報
 */
async function onQuickReserve(programId: string, channelData: ITimeTableChannel, program: ITimeTableProgram): Promise<void> {
    // 過去番組の場合は何もしない
    const endTime = dayjs(program.end_time);
    if (endTime.isBefore(dayjs())) {
        return;
    }

    // 予約がない場合のみ処理
    if (program.reservation !== null) {
        // 既に予約がある場合は番組詳細ドロワーを開く
        await onShowProgramDetail(programId, channelData, program);
        return;
    }

    // 予約がない場合は番組情報とチャンネル情報を渡してドロワーを開く
    isDrawerProgramPast.value = false;
    drawerReservation.value = null;
    drawerProgram.value = program;
    drawerChannel.value = channelData.channel;
    isDrawerOpen.value = true;
}

// ライフサイクル
onMounted(async () => {
    // 番組表データの初期ロード
    await timetableStore.initialLoad();
});

onUnmounted(() => {
    // ストアの状態をリセット
    timetableStore.reset();
});

</script>
<style lang="scss" scoped>

.timetable-container {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    position: relative;
    min-height: 0;  // flex アイテムがオーバーフローしないように
    // 番組表はビューポート内でスクロールさせるため、高さを明示的に制限する
    // App.vue の main は min-height: 100% で拡大可能なため、ここで高さを制限しないとスクロールが効かない
    // ヘッダー (65px) と ナビゲーション幅は Navigation コンポーネント側で調整されている
    height: calc(100vh - 65px);
    height: calc(100dvh - 65px);  // iOS Safari 対応
    @include smartphone-horizontal {
        height: 100vh;
        height: 100dvh;
    }
    @include smartphone-vertical {
        // スマホ縦画面ではヘッダーなし + ボトムナビゲーションバー (56px) + safe-area
        height: calc(100vh - 56px - env(safe-area-inset-bottom));
        height: calc(100dvh - 56px - env(safe-area-inset-bottom));
    }
    background: rgb(var(--v-theme-background));

    &--loading {
        pointer-events: none;
    }
}

// PC 版の番組表コントロール
.timetable-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-right: 16px;

    &__settings-button {
        width: 40px;
        height: 40px;
        min-width: 40px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
    }

    &__channel-type {
        width: 120px;
        :deep(.v-field) {
            border-radius: 8px;
            background: rgb(var(--v-theme-background-lighten-1));
        }
        :deep(.v-field__input) {
            padding-top: 6px;
            padding-bottom: 6px;
            min-height: 40px;
        }
    }

    &__date {
        display: flex;
        align-items: center;
        gap: 4px;

        // 無効状態のアイコンボタンの円形背景を非表示にする
        :deep(.v-btn--disabled) {
            background: transparent !important;
            opacity: 0.38;
        }
    }

    &__date-button {
        min-width: 100px;
        height: 40px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
        font-size: 14px;
    }

    &__time {
        width: 90px;
        :deep(.v-field) {
            border-radius: 8px;
            background: rgb(var(--v-theme-background-lighten-1));
        }
        :deep(.v-field__input) {
            padding-top: 6px;
            padding-bottom: 6px;
            min-height: 40px;
        }
    }

    &__now-button {
        width: 40px;
        height: 40px;
        min-width: 40px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
    }
}

// スマホ版の番組表コントロール
.timetable-controls-mobile {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px 12px;
    background: rgb(var(--v-theme-background-lighten-1));
    border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));

    &__row {
        display: flex;
        align-items: center;
        gap: 8px;

        // 無効状態のアイコンボタンの円形背景を非表示にする
        :deep(.v-btn--disabled) {
            background: transparent !important;
            opacity: 0.38;
        }
    }

    &__channel-type {
        flex-grow: 1;
        :deep(.v-field) {
            border-radius: 6px;
        }
        :deep(.v-field__input) {
            padding-top: 4px;
            padding-bottom: 4px;
            min-height: 36px;
            font-size: 14px;
        }
    }

    &__settings-button {
        width: 36px;
        height: 36px;
        min-width: 36px;
    }

    &__date-button {
        min-width: 80px;
        font-size: 13px;
    }

    &__time {
        flex-grow: 1;
        max-width: 100px;
        :deep(.v-field) {
            border-radius: 6px;
        }
        :deep(.v-field__input) {
            padding-top: 4px;
            padding-bottom: 4px;
            min-height: 36px;
            font-size: 14px;
        }
    }
}

// ローディングオーバーレイ
.timetable-loading-overlay {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(var(--v-theme-background), 0.9);
    z-index: 100;

    &__text {
        font-size: 16px;
        color: rgb(var(--v-theme-text-darken-1));
    }
}

</style>
