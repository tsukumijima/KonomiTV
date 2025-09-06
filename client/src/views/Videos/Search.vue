<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="videos-search-container-wrapper">
                <SPHeaderBar />
                <div class="videos-search-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'ビデオをみる', path: '/videos/' },
                        { name: '検索結果', path: `/videos/search?query=${encodeURIComponent(query)}`, disabled: true },
                    ]" />
                    <RecordedProgramList
                        :title="Utils.isSmartphoneVertical() ? '検索結果' : `「${query}」の検索結果`"
                        :programs="programs"
                        :total="total_programs"
                        :page="current_page"
                        :sortOrder="sort_order"
                        :isLoading="is_loading"
                        :isSearching="is_searching"
                        :showBackButton="true"
                        :breadcrumbs="[
                            { name: 'ビデオをみる', path: '/videos/' },
                            { name: '検索結果', path: `/videos/search?query=${encodeURIComponent(query)}` },
                        ]"
                        @update:page="updatePage"
                        @update:sortOrder="updateSortOrder($event as SortOrder)"
                        :emptyMessage="`「${query}」に一致する録画番組は<br class='d-sm-none'>見つかりませんでした。`"
                        :emptySubMessage="'別のキーワードで検索をお試しください。'"
                        :showEmptyMessage="!is_loading" />
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
import { IRecordedProgram, SortOrder } from '@/services/Videos';
import Videos from '@/services/Videos';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

// ルーター
const route = useRoute();
const router = useRouter();

// 検索クエリ
const query = ref('');

// 録画番組のリスト
const programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);
const is_loading = ref(true);
const is_searching = ref(true);

// 現在のページ番号
const current_page = ref(1);

// 並び順
const sort_order = ref<'desc' | 'asc'>('desc');

// 録画番組を検索
const searchPrograms = async () => {
    is_searching.value = true;  // 検索開始時に検索中フラグを立てる
    const result = await Videos.searchVideos(query.value, sort_order.value, current_page.value);
    if (result) {
        programs.value = result.recorded_programs;
        total_programs.value = result.total;
    }
    is_loading.value = false;
    is_searching.value = false;  // 検索完了時に検索中フラグを下ろす
};

// ページを更新
const updatePage = async (page: number) => {
    current_page.value = page;
    is_loading.value = true;
    is_searching.value = true;  // ページ更新時も検索中フラグを立てる
    await router.replace({
        query: {
            ...route.query,
            page: page.toString(),
        },
    });
};

// 並び順を更新
const updateSortOrder = async (order: 'desc' | 'asc') => {
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

// クエリパラメータが変更されたら録画番組を再検索
watch(() => route.query, async (newQuery) => {
    // 検索クエリが変更された場合はページを1に戻す
    if (newQuery.query !== query.value) {
        current_page.value = 1;
    }
    query.value = newQuery.query as string;
    await searchPrograms();
}, { deep: true });

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();

    // クエリパラメータから初期値を設定
    query.value = route.query.query as string;
    if (route.query.page) {
        current_page.value = parseInt(route.query.page as string);
    }
    if (route.query.order) {
        sort_order.value = route.query.order as 'desc' | 'asc';
    }

    // 録画番組を検索
    await searchPrograms();
});

</script>
<style lang="scss" scoped>

.videos-search-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.videos-search-container {
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