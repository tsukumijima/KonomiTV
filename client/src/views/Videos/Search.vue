<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="videos-search-container">
                <RecordedProgramList
                    :title="`「${query}」の検索結果`"
                    :programs="programs"
                    :total="total_programs"
                    :page="current_page"
                    :sortOrder="sort_order"
                    :isLoading="is_loading"
                    :showBackButton="true"
                    :breadcrumbs="[
                        { name: 'ビデオをみる', path: '/videos/' },
                        { name: '検索結果', path: `/videos/search?query=${encodeURIComponent(query)}` },
                    ]"
                    @update:page="updatePage"
                    @update:sortOrder="updateSortOrder"
                    :emptyMessage="`「${query}」に一致する録画番組は見つかりませんでした。`"
                    :emptySubMessage="'別のキーワードで検索をお試しください。'"
                    v-if="!is_loading || programs.length > 0" />
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import { IRecordedProgram } from '@/services/Videos';
import Videos from '@/services/Videos';

// ルーター
const route = useRoute();
const router = useRouter();

// 検索クエリ
const query = ref('');

// 録画番組のリスト
const programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);
const is_loading = ref(true);

// 現在のページ番号
const current_page = ref(1);

// 並び順
const sort_order = ref<'desc' | 'asc'>('desc');

// 録画番組を検索
const searchPrograms = async () => {
    const result = await Videos.searchVideos(query.value, sort_order.value, current_page.value);
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

.videos-search-container {
    display: flex;
    flex-direction: column;
    width: 100%;
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
    }
}

</style>