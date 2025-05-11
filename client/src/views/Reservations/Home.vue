<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="reservations-home-container-wrapper">
                <SPHeaderBar />
                <div class="reservations-home-container">
                    <div class="reservations-home-container__header">
                        <Breadcrumbs :crumbs="[
                            { name: 'ホーム', path: '/' },
                            { name: '予約', path: '/reservations/', disabled: true },
                        ]" />
                        <v-btn icon variant="flat" class="ml-auto" @click="onClickRefresh" :loading="is_loading">
                            <v-icon>mdi-refresh</v-icon>
                        </v-btn>
                    </div>
                    <!-- 近日中の予約・録画中セクション -->
                    <ReservationList
                        class="reservations-home-container__upcoming-reservations"
                        :class="{'reservations-home-container__upcoming-reservations--loading': upcoming_or_recording_reservations.length === 0 && is_loading}"
                        title="近日中の予約・録画中"
                        :reservations="upcoming_or_recording_reservations"
                        :total="total_upcoming_or_recording_reservations"
                        :hideSort="true"
                        :hidePagination="true"
                        :showMoreButton="true"
                        :isLoading="is_loading"
                        :showEmptyMessage="!is_loading"
                        :emptyIcon="'mdi-motion-play-outline'"
                        :emptyMessage="'近日中の予約や録画中の番組はありません。'"
                        :emptySubMessage="''"
                        @more="$router.push('/reservations/all')"
                        @delete="handleReservationDeleted" />

                    <!-- 24時間以内に終了した予約セクション -->
                    <ReservationList
                        class="reservations-home-container__recently-finished-reservations"
                        :class="{'reservations-home-container__recently-finished-reservations--loading': recently_finished_reservations.length === 0 && is_loading}"
                        title="24時間以内に終了した予約"
                        :reservations="recently_finished_reservations"
                        :total="total_recently_finished_reservations"
                        :hideSort="true"
                        :hidePagination="true"
                        :showMoreButton="true"
                        :isLoading="is_loading"
                        :showEmptyMessage="!is_loading"
                        :emptyIcon="'mdi-history'"
                        :emptyMessage="'24時間以内に終了した予約はありません。'"
                        :emptySubMessage="''"
                        @more="$router.push('/reservations/all')"
                        @delete="handleReservationDeleted" />

                    <!-- すべての予約セクション -->
                    <ReservationList
                        class="reservations-home-container__all-reservations"
                        title="すべての予約"
                        :reservations="recent_reservations_subset"
                        :total="total_all_reservations"
                        :hideSort="true"
                        :hidePagination="true"
                        :showMoreButton="true"
                        :isLoading="is_loading"
                        :showEmptyMessage="!is_loading"
                        emptyIcon="mdi-calendar-check-outline"
                        emptyMessage="録画予約はまだありません。"
                        emptySubMessage="番組表などから録画予約を行ってください。"
                        @more="$router.push('/reservations/all')"
                        @delete="handleReservationDeleted" />
                </div>
            </div>
        </main>
    </div>
</template>

<script lang="ts" setup>
import dayjs from 'dayjs';
import { onMounted, ref, onUnmounted, computed } from 'vue';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ReservationList from '@/components/Reservations/ReservationList.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Reservations, { IReservation } from '@/services/Reservations';

// 定数定義
const AUTO_REFRESH_INTERVAL = 30 * 1000;  // 自動更新の間隔: 30秒
const UPCOMING_OR_RECORDING_DISPLAY_LIMIT = 5; // 「近日中の予約・録画中」セクションの表示上限
const RECENTLY_FINISHED_DISPLAY_LIMIT = 5;    // 「24時間以内に終了した予約」セクションの表示上限
const ALL_RECENT_DISPLAY_LIMIT = 10;         // 「すべての予約」セクションの表示上限

// 状態管理
const is_loading = ref(true);
const autoRefreshInterval = ref<number | null>(null);

// 近日中の予約・録画中
const upcoming_or_recording_reservations = ref<IReservation[]>([]);
const total_upcoming_or_recording_reservations = ref(0);

// 24時間以内に終了した予約
const recently_finished_reservations = ref<IReservation[]>([]);
const total_recently_finished_reservations = ref(0);

// すべての予約
const all_reservations_for_display = ref<IReservation[]>([]);
const total_all_reservations = ref(0);

const recent_reservations_subset = computed(() => {
    if (is_loading.value) {
        return [];
    }
    return [...all_reservations_for_display.value]
        .sort((a, b) => dayjs(b.program.start_time).valueOf() - dayjs(a.program.start_time).valueOf())
        .slice(0, ALL_RECENT_DISPLAY_LIMIT);
});

const fetchAndCategorizeReservations = async () => {
    is_loading.value = true;
    const result = await Reservations.fetchReservations();

    if (result) {
        const now = dayjs();
        const allFetchedReservations = result.reservations;

        total_all_reservations.value = result.total;
        all_reservations_for_display.value = allFetchedReservations;

        const finishedWithin24Hours = allFetchedReservations
            .filter(res => {
                const endTime = dayjs(res.program.end_time);
                // 終了時刻が過去、かつ24時間以内 (is_recording_in_progress の状態は問わない)
                return endTime.isBefore(now) && endTime.isAfter(now.subtract(24, 'hours'));
            })
            .sort((a, b) => dayjs(b.program.end_time).valueOf() - dayjs(a.program.end_time).valueOf());
        total_recently_finished_reservations.value = finishedWithin24Hours.length;
        recently_finished_reservations.value = finishedWithin24Hours.slice(0, RECENTLY_FINISHED_DISPLAY_LIMIT);
        const finishedWithin24HoursIds = new Set(finishedWithin24Hours.map(r => r.id));

        const upcomingOrRecording = allFetchedReservations
            .filter(res => {
                if (finishedWithin24HoursIds.has(res.id)) {
                    return false;
                }
                const startTime = dayjs(res.program.start_time);
                const isUpcoming = startTime.isAfter(now) && startTime.isBefore(now.add(24, 'hours'));
                const isRecording = res.is_recording_in_progress;
                return isUpcoming || isRecording;
            })
            .sort((a, b) => {
                if (a.is_recording_in_progress && !b.is_recording_in_progress) return -1;
                if (!a.is_recording_in_progress && b.is_recording_in_progress) return 1;
                return dayjs(a.program.start_time).valueOf() - dayjs(b.program.start_time).valueOf();
            });
        total_upcoming_or_recording_reservations.value = upcomingOrRecording.length;
        upcoming_or_recording_reservations.value = upcomingOrRecording.slice(0, UPCOMING_OR_RECORDING_DISPLAY_LIMIT);

    } else {
        resetReservations();
    }
    is_loading.value = false;
};

const resetReservations = () => {
    upcoming_or_recording_reservations.value = [];
    total_upcoming_or_recording_reservations.value = 0;
    recently_finished_reservations.value = [];
    total_recently_finished_reservations.value = 0;
    all_reservations_for_display.value = [];
    total_all_reservations.value = 0;
};

const updateAllSections = async () => {
    // 既にローディング中は何もしない
    if (is_loading.value) return;
    try {
        await fetchAndCategorizeReservations();
    } catch (error) {
        console.error('Failed to update reservation sections:', error);
        resetReservations();
    }
};

const onClickRefresh = () => {
    // 自動更新を一旦止めて、手動更新後に再開する（多重実行を防ぐため）
    stopAutoRefresh();
    updateAllSections().finally(() => {
        startAutoRefresh();
    });
};

const handleReservationDeleted = (deleted_reservation_id: number) => {
    // 削除イベントを受けたらリストを即時更新
    console.log(`Reservation ${deleted_reservation_id} deleted, refreshing list...`);
    onClickRefresh(); // 更新ボタンの処理を再利用
};

const startAutoRefresh = () => {
    if (autoRefreshInterval.value === null) {
        // 初回更新は is_loading の状態を見て実行
        if (!is_loading.value) {
            updateAllSections();
        } else {
            // 初回ロードがまだなら fetchAndCategorizeReservations が実行されるのを待つ
            // (通常 onMounted で is_loading=true の状態で fetchAndCategorizeReservations が呼ばれる)
        }
        autoRefreshInterval.value = window.setInterval(updateAllSections, AUTO_REFRESH_INTERVAL);
    }
};

const stopAutoRefresh = () => {
    if (autoRefreshInterval.value !== null) {
        clearInterval(autoRefreshInterval.value);
        autoRefreshInterval.value = null;
    }
};

onMounted(() => {
    fetchAndCategorizeReservations(); // 初回データ取得
    startAutoRefresh();
});

onUnmounted(() => {
    stopAutoRefresh();
});
</script>

<style lang="scss" scoped>
.reservations-home-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.reservations-home-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    padding: 20px;
    margin: 0 auto;
    min-width: 0;
    max-width: 1000px;

    @include smartphone-horizontal {
        padding: 16px 20px !important;
    }

    @include smartphone-horizontal-short {
        padding: 16px !important;
    }

    @include smartphone-vertical {
        padding: 8px 8px 20px !important;
    }

    &__header {
        display: flex;
        align-items: center;
        width: 100%;

    }

    :deep(.reservation-list) {
        & + .reservation-list {
            margin-top: 40px;
            @include smartphone-vertical {
                margin-top: 32px;
            }
        }
    }

    .reservations-home-container__header + :deep(.reservation-list) {
        margin-top: 16px;
         @include smartphone-vertical {
            margin-top: 12px;
        }
    }


    &__upcoming-reservations--loading,
    &__recently-finished-reservations--loading,
    &__all-reservations--loading {
        :deep(.reservation-list__table-container),
        :deep(.reservation-list__empty) {
            min-height: 180px;
        }
    }
}
</style>
