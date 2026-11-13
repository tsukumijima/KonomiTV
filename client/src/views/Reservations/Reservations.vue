<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="reservations-all-container-wrapper">
                <SPHeaderBar />
                <div class="reservations-all-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '録画予約', path: '/reservations/' },
                        { name: '録画予約一覧', path: '/reservations/all', disabled: true },
                    ]" />
                    <ReservationList ref="reservationList"
                        title="録画予約一覧"
                        :reservations="reservations"
                        :total="total"
                        :page="page"
                        :sort-order="sortOrder"
                        :is-loading="isLoading"
                        :show-back-button="true"
                        :show-empty-message="!isLoading"
                        @update:page="updatePage"
                        @update:sort-order="updateSortOrder"
                        @delete="handleReservationDeleted">
                    </ReservationList>
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ReservationList from '@/components/Reservations/ReservationList.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Reservations, { IReservation } from '@/services/Reservations';
import useToruCountStore, { ProgramSortOrder } from '@/stores/ToruCountStore';

const route = useRoute();
const router = useRouter();
const toruCountStore = useToruCountStore();

// 現在のページ番号
const page = computed(() => {
    const page_number = typeof route.query.page === 'string' ? Number.parseInt(route.query.page, 10) : 1;
    return Number.isFinite(page_number) && page_number > 0 ? page_number : 1;
});
// 並び順
const sortOrder = computed<ProgramSortOrder>(() => route.query.order === 'toru' ? 'toru' : 'asc');
// 読み込み中かどうか
const isLoading = ref<boolean>(true);

// 全ての予約データ（一度だけ取得）
const allReservations = ref<IReservation[]>([]);

// 録画予約リストコンポーネントの参照
const reservationList = ref<InstanceType<typeof ReservationList>>();

// 自動更新用の interval ID を保持
const autoRefreshInterval = ref<number | null>(null);

// 自動更新の間隔 (ミリ秒)
const AUTO_REFRESH_INTERVAL = 30 * 1000;  // 30秒
// 1ページに表示する件数 (ReservationList のページ数の計算と同じ件数にする)
const ITEMS_PER_PAGE = 30;

const total = computed(() => allReservations.value.length);
const sortedReservations = computed(() => toruCountStore.sortPrograms(
    allReservations.value, (reservation) => reservation.program, sortOrder.value,
));
const reservations = computed(() => {
    const start_index = (page.value - 1) * ITEMS_PER_PAGE;
    return sortedReservations.value.slice(start_index, start_index + ITEMS_PER_PAGE);
});

/**
 * 録画予約一覧を取得する
 */
async function fetchAllReservations() {
    const result = await Reservations.fetchReservations();
    if (result) {
        allReservations.value = result.reservations;
    }
}

/**
 * ページ番号を更新する
 */
async function updatePage(new_page: number) {
    // クエリパラメータを更新（データの再取得はしない）
    await router.replace({
        query: {
            ...route.query,
            page: new_page.toString(),
        },
    });
}

/**
 * 並び順を更新する
 */
async function updateSortOrder(new_sort_order: ProgramSortOrder) {
    // クエリパラメータを更新（データの再取得はしない）
    await router.replace({
        query: {
            ...route.query,
            order: new_sort_order,
            page: '1',
        },
    });
}

/**
 * 録画予約が削除された時の処理
 */
function handleReservationDeleted(reservation_id: number) {
    // 削除された予約を all_reservations から除去
    allReservations.value = allReservations.value.filter(reservation => reservation.id !== reservation_id);
    // 削除イベントを受けたらリストを即時更新
    console.log(`Reservation ${reservation_id} deleted, refreshing list...`);
    updateAllSections();
}

// 全セクションの更新を実行
const updateAllSections = async () => {
    try {
        await fetchAllReservations();
        isLoading.value = false;
    } catch (error) {
        console.error('Failed to update reservation list:', error);
        isLoading.value = false;
    }
};

// 自動更新を開始
const startAutoRefresh = () => {
    if (autoRefreshInterval.value === null) {
        // 初回更新
        updateAllSections();
        // 定期更新を開始
        autoRefreshInterval.value = window.setInterval(updateAllSections, AUTO_REFRESH_INTERVAL);
    }
};

// 自動更新を停止
const stopAutoRefresh = () => {
    if (autoRefreshInterval.value !== null) {
        clearInterval(autoRefreshInterval.value);
        autoRefreshInterval.value = null;
    }
};

// コンポーネントがマウントされた時
onMounted(() => {
    // 自動更新を開始
    startAutoRefresh();
});

// コンポーネントのクリーンアップ
onUnmounted(() => {
    stopAutoRefresh();
});

</script>
<style lang="scss" scoped>

.reservations-all-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;  // very important!!! これがないと要素がはみ出す
}

.reservations-all-container {
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
        padding: 16px 16px !important;
    }
    @include smartphone-vertical {
        padding: 16px 8px !important;
        padding-top: 8px !important;
    }
}

</style>