
import { isEqual } from 'ohash';
import { defineStore } from 'pinia';
import { computed, ref, shallowRef, watch } from 'vue';

import type { Dayjs } from 'dayjs';

import { ChannelType, ChannelTypePretty } from '@/services/Channels';
import Programs, { ITimeTableChannel } from '@/services/Programs';
import useChannelsStore from '@/stores/ChannelsStore';
import useSettingsStore from '@/stores/SettingsStore';
import { dayjs } from '@/utils';


/**
 * チャンネルタイプの表示順序
 */
export const CHANNEL_TYPE_DISPLAY_ORDER: ChannelTypePretty[] = ['ピン留め', '地デジ', 'BS', 'CS', 'CATV', 'SKY', 'BS4K'];

/**
 * 表示名から API 用チャンネルタイプへのマッピング (ChannelTypePretty -> ChannelType)
 * 'ピン留め' は API では channel_ids パラメータで指定するため、このマッピングには含まれない
 */
const CHANNEL_TYPE_PRETTY_TO_API: Map<ChannelTypePretty, ChannelType> = new Map([
    ['地デジ', 'GR'],
    ['BS', 'BS'],
    ['CS', 'CS'],
    ['CATV', 'CATV'],
    ['SKY', 'SKY'],
    ['BS4K', 'BS4K'],
]);


/**
 * 番組表のデータと表示状態を管理するストア
 * TV 番組表ページで使用される
 */
const useTimeTableStore = defineStore('timetable', () => {

    // 設定ストアを取得
    const settings_store = useSettingsStore();
    // チャンネルストアを取得 (storeToRefs は使わず、直接プロパティにアクセスしてリアクティビティを確保)
    const channels_store = useChannelsStore();

    // 選択中のチャンネルタイプ (表示名で管理)
    // 初期値は null とし、initialLoad() で ChannelsStore の状態に基づいて決定する
    const selected_channel_type = ref<ChannelTypePretty | null>(null);

    // 選択中の日付 (4:00 起点の1日の開始日時を表す)
    // デフォルトは現在日時から算出した今日の 4:00
    const selected_date = ref<Dayjs>(getTodayStartTime());

    // 番組表データ
    const channels_data = shallowRef<ITimeTableChannel[]>([]);

    // 番組表の日付範囲 (API から取得した earliest/latest)
    const date_range = ref<{ earliest: Dayjs; latest: Dayjs } | null>(null);

    // ローディング状態
    const is_loading = ref<boolean>(false);

    // 初回の番組表データ取得が完了したかどうか
    const is_initial_load_completed = ref<boolean>(false);

    // 36時間表示モードかどうか (現在時刻から翌日4時までが11時間未満の場合)
    const is_36hour_display = ref<boolean>(false);

    // 日付表示のオフセット (36時間表示モード時のスクロール位置に応じて変化)
    // 0: selected_date の日付を表示中, 1: selected_date + 1日 (翌日) を表示中
    // 通常モード (非36時間表示) では常に 0
    // 「次の日を見る」「前の日を見る」で移動する日付の計算に使用される
    const date_display_offset = ref<number>(0);

    // スクロール上端の制限時刻 (選択日が今日の場合のみ有効、それ以外は null)
    // 「現在時刻 - 1時間の00分」を表す
    const scroll_top_limit_time = ref<Dayjs | null>(null);


    /**
     * 36時間表示が必要かどうかを判定する
     * 選択日が今日で、現在時刻から翌日の4時まで11時間未満の場合に true
     * @returns 36時間表示が必要な場合は true
     */
    function should36HourDisplay(): boolean {
        const now = dayjs();
        const today_start = getTodayStartTime();

        // 選択日が今日でない場合は36時間表示しない
        // isSame('day') で日付部分のみを比較（ミリ秒のずれを回避）
        if (selected_date.value.isSame(today_start, 'day') === false) {
            return false;
        }

        // 28時間表記対応: 0〜3時は前日の24〜27時として扱う
        let current_hour = now.hour();
        if (current_hour < 4) {
            current_hour += 24;
        }

        // 17時以降 (翌日4時まで11時間未満) なら36時間表示
        // 4時起点なので、17時は開始から13時間後
        return current_hour >= 17;
    }


    /**
     * スクロール上端の制限時刻を計算する
     * 選択日が今日の場合: 現在時刻 - 1時間を正時に切り捨てた時刻
     * 選択日が今日でない場合: null (制限なし)
     * @returns スクロール上端の制限時刻、または null
     */
    function calculateScrollTopLimitTime(): Dayjs | null {
        const now = dayjs();
        const today_start = getTodayStartTime();

        // 選択日が今日でない場合は制限なし
        // isSame('day') で日付部分のみを比較（ミリ秒のずれを回避）
        if (selected_date.value.isSame(today_start, 'day') === false) {
            return null;
        }

        // 現在時刻 - 1時間を正時に切り捨て
        // 例: 23:05 → 22:00, 10:30 → 09:00
        const limit_time = now.startOf('hour').subtract(1, 'hour');

        // 番組表の開始時刻 (選択日の開始時刻) より前にはならないようにする
        const display_start = getDisplayStartTime();
        if (limit_time.isBefore(display_start)) {
            return display_start;
        }

        return limit_time;
    }


    /**
     * 番組表の表示開始時刻を取得する
     * 36時間表示モードの場合は16:00、通常は4:00を返す
     * @returns 表示開始時刻
     */
    function getDisplayStartTime(): Dayjs {
        if (is_36hour_display.value) {
            // 36時間表示: 16:00から開始 (selected_date は4:00を指すため +12時間)
            return selected_date.value.add(12, 'hour');
        }
        // 通常: 4:00から開始 (selected_date は4:00を指している)
        return selected_date.value;
    }


    /**
     * 日時から「放送日」を計算する
     * 番組表は04:00を境界として日付が切り替わるため、04:00より前の時刻は前日の放送日として扱う
     * @param datetime 日時
     * @returns 放送日の開始時刻 (その日の04:00)
     */
    function getBroadcastDate(datetime: Dayjs): Dayjs {
        // 04:00ちょうどの場合を前日扱いにするため、1ミリ秒引いてから計算
        // 例: 2026-01-14T04:00:00 → 2026-01-14T03:59:59.999 → 4時間引いて 2026-01-13T23:59:59.999 → 1/13
        const adjusted = datetime.subtract(1, 'millisecond');
        const shiftedBack = adjusted.subtract(4, 'hour');
        // 放送日の開始時刻 (04:00) を返す
        return shiftedBack.startOf('day').add(4, 'hour');
    }


    /**
     * 今日の番組表の開始時刻 (4:00) を取得する
     * 0:00〜3:59 の場合は前日の 4:00 を返す (28時間表記対応)
     * @returns 今日の開始時刻
     */
    function getTodayStartTime(): Dayjs {
        const now = dayjs();
        let start = now.hour(4).minute(0).second(0).millisecond(0);

        // 現在時刻が 4:00 より前の場合は前日の 4:00 を返す
        if (now.hour() < 4) {
            start = start.subtract(1, 'day');
        }

        return start;
    }


    /**
     * 指定した日付の番組表終了時刻を取得する
     * 36時間表示モードの場合は開始から36時間後、
     * 通常は開始から24時間後を返す
     * @param start_date 開始日時
     * @param is_extended 36時間表示モードかどうか
     * @returns 終了時刻
     */
    function getDayEndTime(start_date: Dayjs, is_extended: boolean = false): Dayjs {
        if (is_extended) {
            // 36時間表示: 開始時刻から 36時間後
            return start_date.add(36, 'hour');
        }
        // 通常: 開始時刻から 24時間後
        return start_date.add(1, 'day');
    }


    /**
     * 番組表の表示開始時刻 (computed)
     * 36時間表示モードの場合は selected_date (4:00) の12時間後 (= 16:00)
     * 通常モードの場合は selected_date (4:00)
     */
    const display_start_time = computed<Dayjs>(() => {
        if (is_36hour_display.value) {
            // 36時間表示: selected_date の12時間後 = 16:00
            return selected_date.value.add(12, 'hour');
        }
        // 通常: selected_date (4:00)
        return selected_date.value;
    });


    /**
     * ChannelsStore の channels_list_with_pinned から利用可能なチャンネルタイプを取得する computed
     * これにより、チャンネルタイプを切り替えても available_channel_types は変化しない
     */
    const available_channel_types = computed<Set<ChannelTypePretty>>(() => {
        const types = new Set<ChannelTypePretty>();

        // ChannelsStore の初期化が完了していない場合は空のセットを返す
        if (channels_store.is_channels_list_initial_updated === false) {
            return types;
        }

        // channels_list_with_pinned の各キーを追加
        // ChannelsStore 側で既にチャンネルが0のタイプは削除されているので、そのまま使える
        for (const channel_type_pretty of channels_store.channels_list_with_pinned.keys()) {
            // ピン留めチャンネルが空の場合は追加しない
            if (channel_type_pretty === 'ピン留め') {
                const pinned_channels = channels_store.channels_list_with_pinned.get('ピン留め');
                if (pinned_channels === undefined || pinned_channels.length === 0) {
                    continue;
                }
            }
            types.add(channel_type_pretty);
        }

        return types;
    });


    /**
     * 選択中のチャンネルタイプが有効かどうかを確認し、無効なら有効なタイプに切り替える
     * @returns 切り替えが発生した場合は新しいチャンネルタイプ、そうでない場合は null
     */
    function validateAndFixChannelType(): ChannelTypePretty | null {
        // selected_channel_type がまだ設定されていない場合
        if (selected_channel_type.value === null) {
            return getDefaultChannelType();
        }

        // 選択中のチャンネルタイプが available_channel_types に存在するか確認
        if (available_channel_types.value.has(selected_channel_type.value)) {
            return null;  // 切り替え不要
        }

        // 存在しない場合はデフォルトのチャンネルタイプに切り替え
        return getDefaultChannelType();
    }


    /**
     * デフォルトのチャンネルタイプを取得する
     * ピン留めがあればピン留め、なければ地デジ、それもなければ最初に存在するタイプ
     */
    function getDefaultChannelType(): ChannelTypePretty {
        // ピン留めチャンネルが存在する場合はピン留め
        if (available_channel_types.value.has('ピン留め')) {
            return 'ピン留め';
        }

        // 地デジが存在する場合は地デジ
        if (available_channel_types.value.has('地デジ')) {
            return '地デジ';
        }

        // それ以外の場合は表示順序に従って最初に存在するタイプを返す
        for (const channel_type of CHANNEL_TYPE_DISPLAY_ORDER) {
            if (available_channel_types.value.has(channel_type)) {
                return channel_type;
            }
        }

        // どれも存在しない場合は地デジを返す（API が空を返すことになる）
        return '地デジ';
    }


    /**
     * 番組表データを API から取得する
     * @param start_time 開始日時 (省略時は selected_date、36時間表示時は16:00)
     * @param end_time 終了日時 (省略時は start_time の翌日 4:00、36時間表示時は start_time + 36時間)
     * @param channel_type チャンネルタイプ (省略時は selected_channel_type)
     * @param pinned_channel_ids チャンネル ID リスト (ピン留め用、省略可)
     * @returns 取得成功時は true、失敗時は false
     */
    async function fetchTimeTableData(
        start_time?: Dayjs,
        end_time?: Dayjs,
        channel_type?: ChannelTypePretty,
        pinned_channel_ids?: string[],
    ): Promise<boolean> {

        // 36時間表示が必要かどうかを判定して更新
        is_36hour_display.value = should36HourDisplay();

        // スクロール上端の制限時刻を更新
        scroll_top_limit_time.value = calculateScrollTopLimitTime();

        // デフォルト値の設定
        // 36時間表示モードの場合は16:00から開始
        const actual_start_time = start_time ?? getDisplayStartTime();
        // 36時間表示モードの場合は翌々日4時まで取得 (16:00 + 36時間)
        const actual_end_time = end_time ?? getDayEndTime(actual_start_time, is_36hour_display.value);
        const actual_channel_type = channel_type ?? selected_channel_type.value ?? '地デジ';

        // ピン留めの場合はチャンネル ID リストを使用
        const actual_pinned_channel_ids = actual_channel_type === 'ピン留め'
            ? (pinned_channel_ids ?? settings_store.settings.pinned_channel_ids)
            : undefined;

        // ChannelTypePretty から API 用の ChannelType に変換
        const api_channel_type = CHANNEL_TYPE_PRETTY_TO_API.get(actual_channel_type);

        // API リクエストを実行 (Programs サービスを使用)
        const response = await Programs.fetchTimeTable(
            actual_start_time,
            actual_end_time,
            // ピン留め以外の場合のみ channel_type を指定
            api_channel_type,
            // ピン留めの場合は pinned_channel_ids を指定
            actual_pinned_channel_ids,
        );

        if (response === null) {
            return false;
        }

        // 番組表データを更新
        // shallowRef でリアクティブ化の負荷を抑えつつ差し替えのみ検知する
        channels_data.value = response.channels;

        // 日付範囲を更新 (API から返される文字列を Dayjs に変換)
        date_range.value = {
            earliest: dayjs(response.date_range.earliest),
            latest: dayjs(response.date_range.latest),
        };

        return true;
    }


    /**
     * 番組表データを初期ロードする
     * ChannelsStore の初期化完了を待ってから、1日分の全データを取得する
     */
    async function initialLoad(): Promise<void> {
        is_loading.value = true;
        is_initial_load_completed.value = false;

        try {
            // ChannelsStore の初期化が完了するまで待機
            // チャンネル情報を使って available_channel_types を計算するため
            await channels_store.update();

            // 今日の開始時刻を設定
            selected_date.value = getTodayStartTime();

            // デフォルトのチャンネルタイプを設定
            // ピン留めがあればピン留め、なければ地デジ、それもなければ最初に存在するタイプ
            selected_channel_type.value = getDefaultChannelType();

            // 1日分の番組表データを取得
            const success = await fetchTimeTableData();

            if (success === false) {
                is_loading.value = false;
                return;
            }

            // 初期ロード完了フラグを立てる (ここで UI 表示を開始)
            is_initial_load_completed.value = true;

        } finally {
            is_loading.value = false;
        }
    }


    /**
     * 日付を変更して番組表データを再取得する
     * @param new_date 新しい日付
     */
    async function changeDate(new_date: Dayjs): Promise<void> {
        is_loading.value = true;

        try {
            selected_date.value = new_date;
            await fetchTimeTableData();
        } finally {
            is_loading.value = false;
        }
    }


    /**
     * チャンネルタイプを変更して番組表データを再取得する
     * @param new_channel_type 新しいチャンネルタイプ
     */
    async function changeChannelType(new_channel_type: ChannelTypePretty): Promise<void> {
        is_loading.value = true;

        try {
            selected_channel_type.value = new_channel_type;
            await fetchTimeTableData();
        } finally {
            is_loading.value = false;
        }
    }


    /**
     * 現在時刻が36時間表示の時間帯（17時以降）かどうかを判定する
     * この判定は selected_date に依存しない純粋な時刻判定
     * @returns 17時以降なら true
     */
    function is36HourTimeRange(): boolean {
        const now = dayjs();
        // 28時間表記対応: 0〜3時は前日の24〜27時として扱う
        let current_hour = now.hour();
        if (current_hour < 4) {
            current_hour += 24;
        }
        return current_hour >= 17;
    }


    /**
     * 前の日の番組表データを取得する
     *
     * 36時間モードのページング設計:
     * - 17時以降は「今日」と「今日+1」が36時間モードの1ページとして統合される
     * - そのため、「今日+1」は単独ページとして存在しない
     * - ページ構成: ... → 今日-1 (24h) → 今日 (36h) → 今日+2 (24h) → ...
     *
     * 例 (1/6 22:00 の場合):
     * - 1/8 から「前の日」→ 1/6 (36時間モード) ※1/7をスキップ
     * - 36時間モードから「前の日」→ 1/5
     */
    async function goToPreviousDay(): Promise<void> {
        if (date_range.value === null) {
            return;
        }

        const today_start = getTodayStartTime();
        const is_36hour_time = is36HourTimeRange();

        let previous_date: Dayjs;

        if (is_36hour_display.value) {
            // 現在36時間モードを表示中の場合
            // 36時間モードからの「前の日」は、36時間モードの開始日 (today) の前日に移動
            // date_display_offset に関わらず、36時間モードページの「前」は常に today - 1
            previous_date = selected_date.value.subtract(1, 'day');
        } else if (is_36hour_time) {
            // 36時間表示の時間帯 (17時以降) だが、現在36時間モードではない場合
            // 移動先が「今日+1」になる場合は、代わりに「今日」(36時間モード) に移動
            // これにより、1/8 → 1/7 ではなく 1/8 → 1/6 (36h) となる
            const naive_previous = selected_date.value.subtract(1, 'day');
            if (naive_previous.isSame(today_start.add(1, 'day'), 'day')) {
                // 移動先が「今日+1」(例: 1/7) の場合、「今日」(例: 1/6) に移動
                previous_date = today_start;
            } else {
                previous_date = naive_previous;
            }
        } else {
            // 通常モード (17時より前): 単純に1日前
            previous_date = selected_date.value.subtract(1, 'day');
        }

        // 日付範囲の最小値を超えないようにする (放送日ベースで比較)
        const earliestBroadcastDate = getBroadcastDate(date_range.value.earliest);
        if (previous_date.isBefore(earliestBroadcastDate, 'day')) {
            return;
        }

        await changeDate(previous_date);
    }


    /**
     * 次の日の番組表データを取得する
     *
     * 36時間モードのページング設計:
     * - 17時以降は「今日」と「今日+1」が36時間モードの1ページとして統合される
     * - 36時間モードからの「次の日」は「今日+2」に移動する
     * - ページ構成: ... → 今日-1 (24h) → 今日 (36h) → 今日+2 (24h) → ...
     *
     * 例 (1/6 22:00 の場合):
     * - 36時間モードから「次の日」→ 1/8 ※1/7をスキップ
     * - 1/8 から「次の日」→ 1/9
     */
    async function goToNextDay(): Promise<void> {
        if (date_range.value === null) {
            return;
        }

        let next_date: Dayjs;

        if (is_36hour_display.value) {
            // 現在36時間モードを表示中の場合
            // 36時間モードは今日 (selected_date) から翌々日4時まで表示するため、
            // 「次の日」は selected_date + 2 (翌々日) に移動
            // これにより、1/6 (36h) → 1/8 となる
            next_date = selected_date.value.add(2, 'day');
        } else {
            // 通常モード: 単純に1日後
            next_date = selected_date.value.add(1, 'day');
        }

        // 日付範囲の最大値を超えないようにする (放送日ベースで比較)
        const latestBroadcastDate = getBroadcastDate(date_range.value.latest);
        if (next_date.isAfter(latestBroadcastDate, 'day')) {
            return;
        }

        await changeDate(next_date);
    }


    /**
     * 現在時刻に戻る
     * 自動追従を再開し、現在時刻が含まれる日付の番組表を表示する
     */
    async function goToCurrentTime(): Promise<void> {
        const today_start = getTodayStartTime();

        // 現在の日付と異なる場合のみ再取得
        // isSame('day') で日付部分のみを比較（ミリ秒のずれを回避）
        if (selected_date.value.isSame(today_start, 'day') === false) {
            await changeDate(today_start);
        }
    }


    /**
     * 日付表示オフセットを設定する
     * TimeTableGrid からスクロール位置に応じて呼び出される
     * @param offset オフセット値 (0: 選択日, 1: 選択日 + 1日)
     */
    function setDateDisplayOffset(offset: number): void {
        date_display_offset.value = offset;
    }


    /**
     * 前の日に移動できるかどうか
     * goToPreviousDay() と同じロジックで判定
     */
    const can_go_previous_day = computed<boolean>(() => {
        if (date_range.value === null) {
            return false;
        }

        const today_start = getTodayStartTime();
        const is_36hour_time = is36HourTimeRange();

        let previous_date: Dayjs;

        if (is_36hour_display.value) {
            // 36時間モードからの「前の日」: today - 1
            previous_date = selected_date.value.subtract(1, 'day');
        } else if (is_36hour_time) {
            // 17時以降で、移動先が「今日+1」なら「今日」に移動
            const naive_previous = selected_date.value.subtract(1, 'day');
            if (naive_previous.isSame(today_start.add(1, 'day'), 'day')) {
                previous_date = today_start;
            } else {
                previous_date = naive_previous;
            }
        } else {
            previous_date = selected_date.value.subtract(1, 'day');
        }

        // date_range.earliest を放送日ベースに変換してから比較する
        // earliest は番組の開始時刻なので、04:00境界を考慮して放送日を計算
        const earliestBroadcastDate = getBroadcastDate(date_range.value.earliest);
        return previous_date.isSameOrAfter(earliestBroadcastDate, 'day');
    });


    /**
     * 次の日に移動できるかどうか
     * goToNextDay() と同じロジックで判定
     */
    const can_go_next_day = computed<boolean>(() => {
        if (date_range.value === null) {
            return false;
        }

        let next_date: Dayjs;

        if (is_36hour_display.value) {
            // 36時間モードからの「次の日」: today + 2
            next_date = selected_date.value.add(2, 'day');
        } else {
            next_date = selected_date.value.add(1, 'day');
        }

        // date_range.latest を放送日ベースに変換してから比較する
        // 例: latest が 2026-01-14T04:00:00 の場合、04:00境界を考慮すると選択可能な最終放送日は 1/13
        const latestBroadcastDate = getBroadcastDate(date_range.value.latest);
        return next_date.isSameOrBefore(latestBroadcastDate, 'day');
    });


    /**
     * ストアの状態をリセットする
     * 番組表ページから離れる際に呼び出される
     */
    function reset(): void {
        channels_data.value = [];
        date_range.value = null;
        is_loading.value = false;
        is_initial_load_completed.value = false;
        is_36hour_display.value = false;
        date_display_offset.value = 0;
        scroll_top_limit_time.value = null;
        // selected_channel_type は次回アクセス時に initialLoad() で再設定されるため、
        // あえて null にリセットして、次回は最新の available_channel_types に基づいて決定されるようにする
        selected_channel_type.value = null;
    }


    // ピン留めチャンネルの変更を監視し、ピン留め表示中なら再取得する
    watch(
        () => settings_store.settings.pinned_channel_ids,
        async (new_ids, old_ids) => {
            // ピン留め表示中でない場合は何もしない
            if (selected_channel_type.value !== 'ピン留め') {
                return;
            }
            // 初期ロード完了前は何もしない
            if (is_initial_load_completed.value === false) {
                return;
            }
            // ピン留めチャンネルが変更された場合は再取得
            if (isEqual(new_ids, old_ids) === false) {
                await fetchTimeTableData();
            }
        },
        { deep: true },
    );


    // ChannelsStore の channels_list_with_pinned が更新されたときに、
    // 選択中のチャンネルタイプが有効かどうかを確認し、無効なら有効なタイプに切り替える
    watch(
        () => channels_store.channels_list_with_pinned,
        async () => {
            // 初期ロード完了前は何もしない
            if (is_initial_load_completed.value === false) {
                return;
            }

            const new_channel_type = validateAndFixChannelType();
            if (new_channel_type !== null) {
                await changeChannelType(new_channel_type);
            }
        },
        { deep: true },
    );


    return {
        // State
        selected_channel_type,
        selected_date,
        channels_data,
        date_range,
        is_loading,
        is_initial_load_completed,
        is_36hour_display,
        date_display_offset,
        scroll_top_limit_time,

        // Getters
        available_channel_types,
        display_start_time,
        can_go_previous_day,
        can_go_next_day,

        // Actions
        getBroadcastDate,
        getTodayStartTime,
        getDayEndTime,
        getDisplayStartTime,
        setDateDisplayOffset,
        fetchTimeTableData,
        initialLoad,
        changeDate,
        changeChannelType,
        goToPreviousDay,
        goToNextDay,
        goToCurrentTime,
        reset,
    };
});

export default useTimeTableStore;
