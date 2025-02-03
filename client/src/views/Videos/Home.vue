<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="videos-home-container">
                <RecordedProgramList
                    title="新着の録画番組"
                    :programs="recent_programs"
                    :total="total_programs"
                    :hideSort="true"
                    :hidePagination="true"
                    :showMoreButton="true"
                    :showSearch="true"
                    :isLoading="is_loading"
                    @more="$router.push('/videos/programs')" />
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { onMounted, ref } from 'vue';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import { IRecordedProgram } from '@/services/Videos';
import Videos from '@/services/Videos';

// 最近録画された番組のリスト
const recent_programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);
const is_loading = ref(true);

// 最近録画された番組を取得
const fetchRecentPrograms = async () => {
    const result = await Videos.fetchAllVideos('desc', 1);
    if (result) {
        recent_programs.value = result.recorded_programs.slice(0, 10);  // 最新10件のみ表示
        total_programs.value = result.total;
    }
    is_loading.value = false;
};

// 開始時に実行
onMounted(async () => {
    await fetchRecentPrograms();
});

</script>
<style lang="scss" scoped>

.videos-home-container {
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