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
                    <ReservationList ref="reservation_list"
                        title="録画予約一覧"
                        :reservations="reservations"
                        :total="total"
                        :page="page"
                        :sort-order="sort_order"
                        :is-loading="is_loading"
                        :show-back-button="true"
                        :show-empty-message="!is_loading"
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

import { ref, onMounted, watch } from 'vue';
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
const sort_order = ref<'desc' | 'asc'>('asc');
// 読み込み中かどうか
const is_loading = ref<boolean>(true);

// 全ての予約データ（一度だけ取得）
const all_reservations = ref<IReservation[]>([]);

// 録画予約リストコンポーネントの参照
const reservation_list = ref<InstanceType<typeof ReservationList>>();

/**
 * 録画予約一覧を取得する（初回のみ）
 */
async function fetchAllReservations() {
    if (all_reservations.value.length > 0) {
        // 既にデータが取得済みの場合はスキップ
        return;
    }

    is_loading.value = true;
    const result = await Reservations.fetchReservations();
    if (result) {
        all_reservations.value = result.reservations;
    }
    is_loading.value = false;
}

/**
 * 表示用データを計算する（クライアント側ソート・ページング）
 */
function updateDisplayData() {
    if (all_reservations.value.length === 0) {
        reservations.value = [];
        total.value = 0;
        return;
    }

    // 並び順に応じてソート
    let sorted_reservations = [...all_reservations.value];
    if (sort_order.value === 'asc') {
        sorted_reservations.sort((a, b) => new Date(a.program.start_time).getTime() - new Date(b.program.start_time).getTime());
    } else {
        sorted_reservations.sort((a, b) => new Date(b.program.start_time).getTime() - new Date(a.program.start_time).getTime());
    }

    // ページネーション用の計算
    const items_per_page = 25;
    const start_index = (page.value - 1) * items_per_page;
    const end_index = start_index + items_per_page;

    reservations.value = sorted_reservations.slice(start_index, end_index);
    total.value = sorted_reservations.length;
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
    sort_order.value = new_sort_order;
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
    all_reservations.value = all_reservations.value.filter(reservation => reservation.id !== reservation_id);
    // 表示データを更新
    updateDisplayData();
}

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
            sort_order.value = order;
        }
    }
    updateDisplayData();
}, { deep: true });

// all_reservations の変更を監視して表示データを更新
watch(() => all_reservations.value, () => {
    updateDisplayData();
}, { deep: true });

// コンポーネントがマウントされた時
onMounted(async () => {
    // クエリパラメータから初期値を設定
    if (route.query.page && typeof route.query.page === 'string') {
        page.value = parseInt(route.query.page, 10);
    }
    if (route.query.order && typeof route.query.order === 'string') {
        sort_order.value = route.query.order as 'desc' | 'asc';
    }

    // 初回の録画予約一覧を取得
    await fetchAllReservations();
    updateDisplayData();
});

</script>
<style lang="scss" scoped>

.reservations-all-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
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