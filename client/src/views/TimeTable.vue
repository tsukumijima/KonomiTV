<template>
    <div class="route-container">
        <HeaderBar>
            <!-- PC 版では HeaderBar 内に番組表コントロールを配置 -->
            <template #timetable-controls v-if="!isCompactControls">
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
                            <v-date-picker v-model="selectedDateForPicker" color="primary"
                                :min="datePickerMinDate" :max="datePickerMaxDate"
                                :allowed-dates="isDateSelectable"
                                @update:model-value="onDatePickerChange">
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
            <Navigation :icon-only="isNavigationIconOnly" />
            <div class="timetable-container" :class="{'timetable-container--loading': timetableStore.is_loading}">
                <SPHeaderBar />
                <!-- スマホ/タブレット用コントロールバー -->
                <div class="timetable-controls-mobile" v-if="isCompactControls">
                    <div class="timetable-controls-mobile__inner">
                        <v-select class="timetable-controls-mobile__channel-type" variant="outlined" density="compact" hide-details
                            :items="channelTypeItems" v-model="selectedChannelTypeDisplay"
                            @update:model-value="onChannelTypeChange">
                        </v-select>
                        <div class="timetable-controls-mobile__date">
                            <v-menu v-model="isDateMenuOpen" :close-on-content-click="false">
                                <template #activator="{ props }">
                                    <v-btn variant="flat" class="timetable-controls-mobile__date-button" size="small" v-bind="props">
                                        {{ formattedSelectedDate }}
                                    </v-btn>
                                </template>
                                <v-date-picker v-model="selectedDateForPicker" color="primary"
                                    :min="datePickerMinDate" :max="datePickerMaxDate"
                                    :allowed-dates="isDateSelectable"
                                    @update:model-value="onDatePickerChange">
                                </v-date-picker>
                            </v-menu>
                        </div>
                        <v-select class="timetable-controls-mobile__time" variant="outlined" density="compact" hide-details
                            :items="timeItems" v-model="selectedTimeDisplay"
                            @update:model-value="onTimeChange">
                        </v-select>
                        <v-btn variant="flat" class="timetable-controls-mobile__now-button" icon size="small" @click="goToCurrentTime">
                            <Icon icon="fluent:clock-20-regular" width="18px" />
                        </v-btn>
                        <v-btn variant="flat" class="timetable-controls-mobile__settings-button" icon size="small"
                            @click="isSettingsDialogOpen = true">
                            <Icon icon="fluent:settings-20-regular" width="18px" />
                        </v-btn>
                    </div>
                </div>
                <!-- 番組表グリッド -->
                <TimeTableGrid
                    ref="timetableGridRef"
                    :channels="timetableStore.channels_data"
                    :is36HourDisplay="timetableStore.is_36hour_display"
                    :canGoPreviousDay="canGoPreviousDay"
                    :canGoNextDay="canGoNextDay"
                    @time-slot-change="onTimeSlotChange"
                    @date-display-offset-change="onDateDisplayOffsetChange"
                    @show-program-detail="onShowProgramDetail"
                    @quick-reserve="onQuickReserve"
                    @go-to-next-day="goToNextDay"
                    @go-to-previous-day="goToPreviousDay"
                />
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

import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ReservationDetailDrawer from '@/components/Reservations/ReservationDetailDrawer.vue';
import TimeTableSettingsDialog from '@/components/Settings/TimeTableSettings.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import TimeTableGrid from '@/components/TimeTable/TimeTableGrid.vue';
import Message from '@/message';
import { IChannel, ChannelTypePretty } from '@/services/Channels';
import { IProgram, ITimeTableProgram } from '@/services/Programs';
import Reservations, { IReservation, IRecordSettingsDefault } from '@/services/Reservations';
import useServerSettingsStore from '@/stores/ServerSettingsStore';
import useSettingsStore from '@/stores/SettingsStore';
import useTimeTableStore, { CHANNEL_TYPE_DISPLAY_ORDER } from '@/stores/TimeTableStore';
import Utils, { dayjs } from '@/utils';


// ストア
const settingsStore = useSettingsStore();
const timetableStore = useTimeTableStore();

// コンポーネント参照
const timetableGridRef = ref<InstanceType<typeof TimeTableGrid> | null>(null);

// サーバー設定（バックエンド種別の判定用）
const serverSettingsStore = useServerSettingsStore();
const serverSettings = computed(() => serverSettingsStore.server_settings);

// EDCB バックエンドかどうか
const isEDCBBackend = computed(() => serverSettings.value.general.backend === 'EDCB');

// UI 状態
const isSettingsDialogOpen = ref(false);
const isDateMenuOpen = ref(false);

// ウィンドウリサイズ時にリアクティブに再計算をトリガーするためのカウンター
// window.innerWidth や window.matchMedia() の結果は Vue のリアクティブシステムでは追跡されないため、
// リサイズイベント発火時にこのカウンターをインクリメントし、computed がこの値を参照することで再計算をトリガーする
const windowResizeCounter = ref(0);

// リサイズイベントハンドラー (デバウンス処理付き)
let resizeDebounceTimerId: number | null = null;
const RESIZE_DEBOUNCE_MS = 100;
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

// タブレット横画面は幅的に PC 版ヘッダーコントロールが収まるので、PC 版を使用する
const isCompactControls = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _trigger = windowResizeCounter.value;
    return Utils.isSmartphoneVertical() ||
        Utils.isSmartphoneHorizontal() ||
        Utils.isTabletVertical();
});

// Navigation の icon-only 判定 (リサイズ対応)
const isNavigationIconOnly = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _trigger = windowResizeCounter.value;
    return !Utils.isSmartphoneVertical();
});

// ストアの date_display_offset への参照を作成 (テンプレートでのアクセスを簡潔にするため)
// 36時間表示モード時にスクロール位置に応じて日付表示を切り替えるために使用
// 0: 選択日をそのまま表示, 1: 選択日 + 1日 (翌日) を表示
const dateDisplayOffset = computed(() => timetableStore.date_display_offset);

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
    const items: { title: string; value: number; props?: { disabled: boolean } }[] = [];
    const shouldDisableEarlyHours = timetableStore.is_36hour_display && dateDisplayOffset.value === 0;

    // 4時から28時 (翌4時) まで4時間ごと
    for (let hour = 4; hour <= 24; hour += 4) {
        const displayHour = hour;
        const isEarlyHour = hour <= 12;
        items.push({
            title: `${displayHour.toString().padStart(2, '0')}時`,
            value: hour,
            ...(shouldDisableEarlyHours && isEarlyHour ? { props: { disabled: true } } : {}),
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
// 36時間表示モード時は、スクロール位置に応じてオフセットを加算して表示する
// これにより、28時間表記オン時は4時ライン、オフ時は0時ラインを超えたら翌日の日付が表示される
const formattedSelectedDate = computed(() => {
    const date = timetableStore.selected_date.add(dateDisplayOffset.value, 'day');
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
// ストアの computed を使用 (36時間表示モード時の date_display_offset を考慮した判定)
const canGoPreviousDay = computed(() => timetableStore.can_go_previous_day);

// 次の日に移動できるか
// ストアの computed を使用 (36時間表示モード時の date_display_offset を考慮した判定)
const canGoNextDay = computed(() => timetableStore.can_go_next_day);

// v-date-picker 用の日付範囲制限
// 番組情報が存在する日付範囲のみ選択可能にする
// 番組表は04:00を境界として日付が切り替わるため、放送日ベースに変換してから比較する
const datePickerMinDate = computed(() => {
    if (timetableStore.date_range === null) return undefined;
    // v-date-picker は Date 型を受け付ける
    // earliest を放送日ベースに変換してから startOf('day') を適用
    const earliestBroadcastDate = timetableStore.getBroadcastDate(timetableStore.date_range.earliest);
    return earliestBroadcastDate.startOf('day').toDate();
});
const datePickerMaxDate = computed(() => {
    if (timetableStore.date_range === null) return undefined;
    // latest を放送日ベースに変換してから endOf('day') を適用
    // 例: latest が 2026-01-14T04:00:00 の場合、放送日は 1/13 なので 1/13 23:59:59 が最大日時
    const latestBroadcastDate = timetableStore.getBroadcastDate(timetableStore.date_range.latest);
    return latestBroadcastDate.endOf('day').toDate();
});

/**
 * 日付ピッカーで選択可能かどうかを判定する
 * Vuetify の allowed-dates は (date: unknown) => boolean を期待するため、引数は unknown 型で受け取る
 * 番組表は04:00を境界として日付が切り替わるため、放送日ベースに変換してから比較する
 * @param date 日付 (Vuetify からは Date 型で渡される)
 * @returns 選択可能なら true
 */
function isDateSelectable(date: unknown): boolean {
    if (timetableStore.date_range === null) return false;
    // Vuetify の v-date-picker は Date オブジェクトを渡してくるが、dayjs() はそれを受け付ける
    const targetDate = dayjs(date as Date);
    // date_range を放送日ベースに変換してから比較
    const earliestBroadcastDate = timetableStore.getBroadcastDate(timetableStore.date_range.earliest);
    const latestBroadcastDate = timetableStore.getBroadcastDate(timetableStore.date_range.latest);
    return targetDate.isSameOrAfter(earliestBroadcastDate, 'day') &&
        targetDate.isSameOrBefore(latestBroadcastDate, 'day');
}

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
 * 日付変更後、番組表の末尾 (翌0時近辺) にスクロールして、時間的に連続した体験を提供
 */
async function goToPreviousDay(): Promise<void> {
    await timetableStore.goToPreviousDay();
    // データ更新後に DOM が更新されるのを待ってからスクロール
    await nextTick();
    if (timetableGridRef.value !== null) {
        timetableGridRef.value.scrollToEnd();
    }
}

/**
 * 次の日へ移動
 * 日付変更後、番組表の先頭 (4時) にスクロールして、時間的に連続した体験を提供
 */
async function goToNextDay(): Promise<void> {
    await timetableStore.goToNextDay();
    // データ更新後に DOM が更新されるのを待ってからスクロール
    await nextTick();
    if (timetableGridRef.value !== null) {
        timetableGridRef.value.scrollToStart();
    }
}

/**
 * 現在時刻に戻る
 */
async function goToCurrentTime(): Promise<void> {
    await timetableStore.goToCurrentTime();
    // データロード後に DOM が更新されるのを待ってからスクロール
    await nextTick();
    if (timetableGridRef.value !== null) {
        timetableGridRef.value.scrollToCurrentTime(true, true);
    }
}

/**
 * 表示中の時間帯変更時のハンドラ
 * スクロール位置から計算された現在表示中の時間帯を受け取り、時刻セレクターを更新
 * @param hour 現在表示中の時間帯 (4, 8, 12, 16, 20, 24 のいずれか)
 */
function onTimeSlotChange(hour: number): void {
    // 時刻セレクターの値を更新 (4時間ごとのスロットに丸める)
    const slotHour = Math.floor((hour - 4) / 4) * 4 + 4;
    // 4〜24 の範囲に収める
    const clampedSlot = Math.max(4, Math.min(24, slotHour));
    selectedTimeDisplay.value = clampedSlot;
}

/**
 * 日付表示オフセット変更時のハンドラ
 * 36時間表示モード時に、スクロール位置が日付境界を超えたかどうかに応じて
 * 日付表示を切り替えるために使用
 * また、ストアに保存することで「次の日」「前の日」の移動先日付の計算にも使用される
 * @param offset オフセット (0: 選択日, 1: 選択日 + 1日)
 */
function onDateDisplayOffsetChange(offset: number): void {
    timetableStore.setDateDisplayOffset(offset);
}

/**
 * 番組詳細表示時のハンドラ
 * 番組表から番組詳細ドロワーを開く
 * 予約がある場合は API から取得し、予約がない場合は mock の IReservation を作成して渡す
 * @param programId 番組 ID
 * @param channel 番組が属するチャンネル情報
 * @param program 番組情報
 */
async function onShowProgramDetail(programId: string, channel: IChannel, program: ITimeTableProgram): Promise<void> {

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
            // 取得失敗時は mock の IReservation を作成して渡す
            drawerReservation.value = createMockReservation(program, channel);
            drawerProgram.value = null;
            drawerChannel.value = null;
        }
    } else {
        // 予約がない場合は mock の IReservation を作成して渡す
        // id が -1 の場合は mock と判定され、予約追加ボタンが表示される
        drawerReservation.value = createMockReservation(program, channel);
        drawerProgram.value = null;
        drawerChannel.value = null;
    }

    isDrawerOpen.value = true;
}

/**
 * 予約がない番組用に mock の IReservation を作成する
 * ReservationDetailDrawer で録画設定タブを表示し、設定をカスタマイズしてから予約追加できるようにするため
 * id が -1 の場合は mock と判定され、予約追加ボタンが表示される
 * @param program 番組情報
 * @param channel チャンネル情報
 * @returns mock の IReservation
 */
function createMockReservation(program: ITimeTableProgram, channel: IChannel): IReservation {
    return {
        id: -1,  // mock を示す特別な値 (ReservationDetailDrawer で判定に使用)
        channel: channel,
        program: program as IProgram,  // ITimeTableProgram は IProgram を継承している
        is_recording_in_progress: false,
        recording_availability: 'Full',
        comment: '',
        scheduled_recording_file_name: '',
        estimated_recording_file_size: 0,
        record_settings: structuredClone(IRecordSettingsDefault),
    };
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
 * 番組セルの「録画予約」ボタンが押された時:
 * - 予約がない場合: デフォルト設定でワンクリック予約追加
 * - 既存予約がある場合: 予約の有効/無効を切り替え
 * @param programId 番組 ID
 * @param channel 番組が属するチャンネル情報
 * @param program 番組情報
 */
async function onQuickReserve(programId: string, channel: IChannel, program: ITimeTableProgram): Promise<void> {
    // 過去番組の場合は何もしない
    const endTime = dayjs(program.end_time);
    if (endTime.isBefore(dayjs())) {
        return;
    }

    // EDCB バックエンドでない場合はエラー
    if (isEDCBBackend.value === false) {
        Message.warning('録画予約機能は EDCB バックエンド選択時のみ利用できます。');
        return;
    }

    // 予約がある場合は有効/無効を切り替え
    if (program.reservation !== null) {
        // 完全な予約情報を取得
        const reservation = await Reservations.fetchReservation(program.reservation.id);
        if (reservation === null) {
            return;
        }

        // 有効/無効を切り替え
        const newSettings = structuredClone(reservation.record_settings);
        newSettings.is_enabled = !newSettings.is_enabled;

        const result = await Reservations.updateReservation(reservation.id, newSettings);
        if (result !== null) {
            const message = newSettings.is_enabled
                ? '録画予約を有効にしました。\n番組開始時刻になると自動的に録画が開始されます。'
                : '録画予約を無効にしました。\n番組開始時刻までに再度予約を有効にしない限り、この番組は録画されません。';
            Message.success(message);
            // 番組表データを再取得して予約状態を更新
            await timetableStore.fetchTimeTableData();
        }
        return;
    }

    // 予約がない場合はデフォルト設定でワンクリック予約追加
    const success = await Reservations.addReservation(programId, structuredClone(IRecordSettingsDefault));
    if (success) {
        Message.success('録画予約を追加しました。');
        // 番組表データを再取得して予約状態を更新
        await timetableStore.fetchTimeTableData();
    }
}

// ライフサイクル
onMounted(async () => {
    // ウィンドウリサイズイベントリスナーを登録
    // 画面回転やウィンドウサイズ変更時に、レイアウト判定の再計算をトリガーする
    window.addEventListener('resize', onWindowResize);

    // サーバー設定を取得（バックエンド種別の判定用）
    await serverSettingsStore.fetchServerSettingsOnce();

    // 番組表データの初期ロード
    await timetableStore.initialLoad();
});

onUnmounted(() => {
    // ウィンドウリサイズイベントリスナーを解除
    window.removeEventListener('resize', onWindowResize);
    // デバウンスタイマーをクリア
    if (resizeDebounceTimerId !== null) {
        clearTimeout(resizeDebounceTimerId);
        resizeDebounceTimerId = null;
    }

    // ストアの状態をリセット
    timetableStore.reset();
});

// 日付が変更されたら、日付表示オフセットをリセット
// これにより、日付変更後はボタンに選択された日付が表示される
watch(() => timetableStore.selected_date, () => {
    timetableStore.setDateDisplayOffset(0);
});

</script>
<style lang="scss">

:root {
    // REGZA 風の時刻スケール背景色
    // 彩度を抑えた淡い色味で、時刻の流れを表現
    // 深夜 (0-3時): 紫成分が抜けた群青から徐々に明るい青へ
    --timetable-time-scale-color-00: #2a4068;
    --timetable-time-scale-color-01: #325080;
    --timetable-time-scale-color-02: #3a5c90;
    --timetable-time-scale-color-03: #4268a0;
    // 朝 (4-7時): 青から青緑、緑へ
    --timetable-time-scale-color-04: #4a7aa0;
    --timetable-time-scale-color-05: #4d8898;
    --timetable-time-scale-color-06: #509690;
    --timetable-time-scale-color-07: #55a080;
    // 午前 (8-11時): 緑から黄緑へ (彩度・明度を抑えめに)
    --timetable-time-scale-color-08: #4c8860;
    --timetable-time-scale-color-09: #5c8a58;
    --timetable-time-scale-color-10: #6c8c52;
    --timetable-time-scale-color-11: #7a8c4c;
    // 昼 (12-15時): 落ち着いた黄緑からオリーブへ
    --timetable-time-scale-color-12: #7c8a48;
    --timetable-time-scale-color-13: #888848;
    --timetable-time-scale-color-14: #908248;
    --timetable-time-scale-color-15: #987a48;
    // 夕方 (16-19時): 黄土色からくすんだ茶色へ
    --timetable-time-scale-color-16: #987048;
    --timetable-time-scale-color-17: #906248;
    --timetable-time-scale-color-18: #80564c;
    --timetable-time-scale-color-19: #6c4a50;
    // 夜 (20-23時): 赤紫から紫へ
    --timetable-time-scale-color-20: #5c4058;
    --timetable-time-scale-color-21: #4c3a54;
    --timetable-time-scale-color-22: #3c3850;
    --timetable-time-scale-color-23: #30384c;

    // 番組がない領域の背景色
    --timetable-empty-cell-background: #616161;
}

</style>
<style lang="scss" scoped>

.timetable-container {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    position: relative;
    min-width: 0;
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
        margin-left: -4px;
        margin-right: -4px;

        .v-btn {
            width: calc(var(--v-btn-height) + 8px) !important;
            height: calc(var(--v-btn-height) + 8px) !important;
        }

        // 無効状態のアイコンボタンのスタイル
        // 背景やホバー効果を完全に無効化し、アイコンのみを薄く表示
        :deep(.v-btn--disabled) {
            .v-btn__overlay {
                opacity: 0 !important;
            }
        }
    }

    &__date-button {
        position: relative;
        min-width: 90px;
        height: 40px;
        min-height: 40px;
        padding-top: 6px;
        padding-bottom: 6px;
        padding-left: 6px;
        padding-right: 6px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
        font-size: 14px;
        line-height: 21px;
        --timetable-date-border-opacity: 0.26;
        --timetable-date-border-width: 1px;
        box-shadow: inset 0 0 0 var(--timetable-date-border-width) rgba(var(--v-theme-on-surface), var(--timetable-date-border-opacity));
        transition: box-shadow 250ms cubic-bezier(0.4, 0, 0.2, 1);

        @media (hover: hover) {
            &:hover {
                --timetable-date-border-opacity: 0.55;
            }
        }

        &:focus-visible,
        &[aria-expanded='true'] {
            --timetable-date-border-opacity: 1;
            --timetable-date-border-width: 2px;
        }

        :deep(.v-btn__overlay) {
            background: transparent !important;
            opacity: 0 !important;
        }
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

// コンパクト表示向けの番組表コントロール
.timetable-controls-mobile {
    background: rgb(var(--v-theme-background-lighten-1));
    border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
    @include tablet-vertical {
        border-left: 1px solid rgb(var(--v-theme-background-lighten-2));
    }
    @include smartphone-vertical {
        margin-top: 14px;
    }

    // 内側のコンテナ: 実際のコントロール要素を配置
    // タブレット縦画面・スマホ横画面では max-width を制限して右寄せ
    &__inner {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        padding: 10px 10px 12px;
        @include tablet-vertical {
            gap: 10px;
            padding-left: 16px;
            padding-right: 16px;
            padding-bottom: 10px;
        }
        @include smartphone-horizontal {
            gap: 10px;
            max-width: calc(100% - (210px - 60px));
            margin-left: auto;
            padding: 6px 10px 6px;
        }
        @include smartphone-horizontal-short {
            max-width: calc(100% - (190px - 56px));
        }
    }

    // 無効状態のアイコンボタンのスタイル
    // 背景やホバー効果を完全に無効化し、アイコンのみを薄く表示
    :deep(.v-btn--disabled) {
        background: transparent !important;
        opacity: 0.38;

        // ホバー時の背景も非表示
        &::before {
            display: none !important;
        }
        &:hover {
            background: transparent !important;
        }
    }

    &__channel-type {
        width: 88px;
        :deep(.v-field) {
            border-radius: 6px;
            background: rgb(var(--v-theme-background-lighten-1));
        }
        :deep(.v-field) {
            padding-right: 5px;
        }
        :deep(.v-field__input) {
            padding-top: 4px;
            padding-left: 12px;
            padding-bottom: 4px;
            min-height: 36px;
            font-size: 14px;
        }

        @include tablet-horizontal {
            width: 110px;
        }
        @include tablet-vertical {
            width: 110px;
        }
        @include smartphone-horizontal {
            width: 80px;
        }
    }

    &__settings-button {
        width: 34px;
        height: 34px;
        min-width: 34px;
        background: rgb(var(--v-theme-background-lighten-2));
        border-radius: 6px;

        @include tablet-horizontal {
            width: 36px;
            height: 36px;
            min-width: 36px;
        }
        @include tablet-vertical {
            width: 36px;
            height: 36px;
            min-width: 36px;
        }
    }

    &__now-button {
        width: 34px;
        height: 34px;
        min-width: 34px;
        background: rgb(var(--v-theme-background-lighten-2));
        border-radius: 6px;

        @include tablet-horizontal {
            width: 36px;
            height: 36px;
            min-width: 36px;
        }
        @include tablet-vertical {
            width: 36px;
            height: 36px;
            min-width: 36px;
        }
    }

    &__date {
        display: flex;
        align-items: center;
        gap: 2px;
    }

    &__date-button {
        position: relative;
        min-height: 36px;
        height: 36px;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
        font-size: 14px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 6px;
        line-height: 20px;
        --timetable-date-border-opacity: 0.26;
        --timetable-date-border-width: 1px;
        box-shadow: inset 0 0 0 var(--timetable-date-border-width) rgba(var(--v-theme-on-surface), var(--timetable-date-border-opacity));
        transition: box-shadow 250ms cubic-bezier(0.4, 0, 0.2, 1);

        @media (hover: hover) {
            &:hover {
                --timetable-date-border-opacity: 0.55;
            }
        }

        &:focus-visible,
        &[aria-expanded='true'] {
            --timetable-date-border-opacity: 1;
            --timetable-date-border-width: 2px;
        }

        :deep(.v-btn__overlay) {
            background: transparent !important;
            opacity: 0 !important;
        }

        @include tablet-vertical {
            width: 140px;
            justify-content: flex-start;
            flex-shrink: 0;
        }
        @include smartphone-horizontal {
            width: 140px;
            justify-content: flex-start;
            flex-shrink: 0;
        }
        @include smartphone-horizontal-short {
            width: 110px;
            justify-content: flex-start;
            flex-shrink: 0;
        }
    }

    &__time {
        width: 64px;
        :deep(.v-field) {
            border-radius: 6px;
            background: rgb(var(--v-theme-background-lighten-1));
        }
        :deep(.v-field) {
            padding-right: 5px;
        }
        :deep(.v-field__input) {
            padding-top: 4px;
            padding-left: 12px;
            padding-bottom: 4px;
            min-height: 36px;
            font-size: 14px;
        }

        @include tablet-vertical {
            max-width: 140px;
            flex-shrink: 0;
        }
        @include smartphone-horizontal {
            max-width: 140px;
            flex-shrink: 0;
        }
        @include smartphone-horizontal-short {
            max-width: 110px;
            flex-shrink: 0;
        }
    }
}

</style>
