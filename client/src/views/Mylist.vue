<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <div class="mylist-container-wrapper">
                <div class="mylist-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'マイリスト', path: '/mylist/', disabled: true },
                    ]" />
                    <RecordedProgramList
                        title="マイリスト"
                        :programs="programs"
                        :total="total_programs"
                        :page="current_page"
                        :sortOrder="sort_order"
                        :isLoading="is_loading"
                        :showBackButton="true"
                        :showEmptyMessage="!is_loading"
                        :emptyIcon="'ic:round-playlist-play'"
                        :emptyMessage="'あとで観たい番組を<br class=\'d-sm-none\'>マイリストに保存できます。'"
                        :emptySubMessage="'録画番組の右上にある ＋ ボタンから、<br class=\'d-sm-none\'>番組をマイリストに追加できます。'"
                        :forMylist="true"
                        @update:page="updatePage"
                        @update:sortOrder="updateSortOrder($event as MylistSortOrder)" />
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import { IRecordedProgram, MylistSortOrder } from '@/services/Videos';
import Videos from '@/services/Videos';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';

// ルーター
const route = useRoute();
const router = useRouter();
const settingsStore = useSettingsStore();

// 録画番組のリスト
const programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);
const is_loading = ref(true);

// 現在のページ番号
const current_page = ref(1);

// 並び順
const sort_order = ref<MylistSortOrder>('mylist_added_desc');

// 録画番組を取得
const fetchPrograms = async () => {
    // マイリストに登録されている録画番組の ID を取得
    const mylist_ids = settingsStore.settings.mylist
        .filter(item => item.type === 'RecordedProgram')
        .sort((a, b) => {
            // ソート順に応じて並び替え
            switch (sort_order.value) {
                case 'mylist_added_desc':
                    return b.created_at - a.created_at;
                case 'mylist_added_asc':
                    return a.created_at - b.created_at;
                case 'recorded_desc':
                case 'recorded_asc':
                    // 録画番組の情報を取得する前なので、ここでは created_at でソート
                    // 録画番組の情報を取得後に再度ソートする
                    return b.created_at - a.created_at;
                default:
                    return 0;
            }
        })
        .map(item => item.id);

    // マイリストが空の場合は早期リターン
    if (mylist_ids.length === 0) {
        programs.value = [];
        total_programs.value = 0;
        is_loading.value = false;
        return;
    }

    // 録画番組を取得
    let order: 'desc' | 'asc' | 'ids' = 'ids';
    if (sort_order.value === 'recorded_desc') {
        order = 'desc';
    } else if (sort_order.value === 'recorded_asc') {
        order = 'asc';
    }
    const result = await Videos.fetchVideos(order, current_page.value, mylist_ids);
    if (result) {
        programs.value = result.recorded_programs;
        total_programs.value = result.total;
    }
    is_loading.value = false;
};

// ページを更新
const updatePage = async (page: number) => {
    current_page.value = page;
    is_loading.value = true;
    await router.replace({
        query: {
            ...route.query,
            page: page.toString(),
        },
    });
};

// 並び順を更新
const updateSortOrder = async (order: MylistSortOrder) => {
    sort_order.value = order;
    current_page.value = 1;  // ページを1に戻す
    is_loading.value = true;
    await router.replace({
        query: {
            ...route.query,
            order,
            page: '1',
        },
    });
};

// クエリパラメータが変更されたら録画番組を再取得
watch(() => route.query, async (newQuery) => {
    // ページ番号を同期
    if (newQuery.page) {
        current_page.value = parseInt(newQuery.page as string);
    }
    // ソート順を同期
    if (newQuery.order) {
        sort_order.value = newQuery.order as MylistSortOrder;
    }
    await fetchPrograms();
}, { deep: true });

// マイリストの変更を監視して即座に再取得
watch(() => settingsStore.settings.mylist, async () => {
    await fetchPrograms();
}, { deep: true });

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();

    // クエリパラメータから初期値を設定
    if (route.query.page) {
        current_page.value = parseInt(route.query.page as string);
    }
    if (route.query.order) {
        sort_order.value = route.query.order as MylistSortOrder;
    }

    // 録画番組を取得
    await fetchPrograms();
});

</script>
<style lang="scss" scoped>

.mylist-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    @include smartphone-vertical {
        padding-top: 10px !important;
    }
}

.mylist-container {
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