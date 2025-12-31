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

import { ref, onMounted, watch, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ReservationList from '@/components/Reservations/ReservationList.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Reservations, { IReservation } from '@/services/Reservations';

const route = useRoute();
const router = useRouter();

// 録画予約リスト
const reservations = ref<IReservation[]>([]);
// 全体の録画予約数
const total = ref<number>(0);
// 現在のページ番号
const page = ref<number>(1);
// 並び順
const sortOrder = ref<'desc' | 'asc'>('asc');
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
const ITEMS_PER_PAGE = 25;

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
 * 表示用データを計算する（クライアント側ソート・ページング）
 */
function updateDisplayData() {
    if (allReservations.value.length === 0) {
        reservations.value = [];
        total.value = 0;
        return;
    }

    // 並び順に応じてソート
    let sortedReservations = [...allReservations.value];
    if (sortOrder.value === 'asc') {
        sortedReservations.sort((a, b) => new Date(a.program.start_time).getTime() - new Date(b.program.start_time).getTime());
    } else {
        sortedReservations.sort((a, b) => new Date(b.program.start_time).getTime() - new Date(a.program.start_time).getTime());
    }

    // ページネーション用の計算
    const startIndex = (page.value - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;

    reservations.value = sortedReservations.slice(startIndex, endIndex);
    total.value = sortedReservations.length;
}

/**
 * ページ番号を更新する
 */
async function updatePage(new_page: number) {
    page.value = new_page;
    // クエリパラメータを更新（データの再取得はしない）
    await router.replace({
        query: {
            ...route.query,
            page: new_page.toString(),
        },
    });
    // updateDisplayData は watch によって自動的に呼び出されるため、ここでは呼び出さない
}

/**
 * 並び順を更新する
 */
async function updateSortOrder(new_sort_order: 'desc' | 'asc') {
    sortOrder.value = new_sort_order;
    page.value = 1; // ページを1に戻す
    // クエリパラメータを更新（データの再取得はしない）
    await router.replace({
        query: {
            ...route.query,
            order: new_sort_order,
            page: '1',
        },
    });
    // updateDisplayData は watch によって自動的に呼び出されるため、ここでは呼び出さない
}

/**
 * 録画予約が削除された時の処理
 */
function handleReservationDeleted(reservation_id: number) {
    // 削除された予約を all_reservations から除去
    allReservations.value = allReservations.value.filter(reservation => reservation.id !== reservation_id);
    // 表示データを更新
    updateDisplayData();
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

// クエリパラメータが変更されたら表示データを更新（再取得はしない）
watch(() => route.query, async (newQuery) => {
    // ページ番号を同期
    if (newQuery.page) {
        const page_number = parseInt(String(newQuery.page), 10);
        if (Number.isFinite(page_number) && page_number > 0) {
            page.value = page_number;
        }
    }
    // ソート順を同期
    if (newQuery.order) {
        const order = String(newQuery.order);
        if (order === 'asc' || order === 'desc') {
            sortOrder.value = order;
        }
    }
    updateDisplayData();
}, { deep: true });

// allReservations の変更を監視して表示データを更新
watch(() => allReservations.value, () => {
    updateDisplayData();
}, { deep: true });

// コンポーネントがマウントされた時
onMounted(async () => {
    // クエリパラメータから初期値を設定
    if (route.query.page && typeof route.query.page === 'string') {
        page.value = parseInt(route.query.page, 10);
    }
    if (route.query.order && typeof route.query.order === 'string') {
        sortOrder.value = route.query.order as 'desc' | 'asc';
    }

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