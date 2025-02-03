<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="recorded-programs-container">
                <RecordedProgramList
                    title="録画番組リスト"
                    :programs="programs"
                    :total="total_programs"
                    :page="current_page"
                    :sortOrder="sort_order"
                    @update:page="updatePage"
                    @update:sortOrder="updateSortOrder" />
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

// 録画番組のリスト
const programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);

// 現在のページ番号
const current_page = ref(1);

// 並び順
const sort_order = ref<'desc' | 'asc'>('desc');

// 録画番組を取得
const fetchPrograms = async () => {
    const result = await Videos.fetchAllVideos(sort_order.value, current_page.value);
    if (result) {
        programs.value = result.recorded_programs;
        total_programs.value = result.total;
    }
};

// ページを更新
const updatePage = async (page: number) => {
    current_page.value = page;
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
    await router.replace({
        query: {
            ...route.query,
            order,
            page: '1',
        },
    });
};

// クエリパラメータが変更されたら録画番組を再取得
watch(() => route.query, async () => {
    await fetchPrograms();
}, { deep: true });

// 開始時に実行
onMounted(async () => {
    // クエリパラメータから初期値を設定
    if (route.query.page) {
        current_page.value = parseInt(route.query.page as string);
    }
    if (route.query.order) {
        sort_order.value = route.query.order as 'desc' | 'asc';
    }

    // 録画番組を取得
    await fetchPrograms();
});

</script>
<style lang="scss" scoped>

.recorded-programs-container {
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