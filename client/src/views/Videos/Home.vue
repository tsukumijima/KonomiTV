<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="videos-home-container">
                <RecordedProgramList
                    title="最近録画された番組"
                    :programs="recent_programs"
                    :total="total_programs"
                    :hideSort="true"
                    :hidePagination="true"
                    :showMoreButton="true"
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

// 最近録画された番組を取得
const fetchRecentPrograms = async () => {
    const result = await Videos.fetchAllVideos('desc', 1);
    if (result) {
        recent_programs.value = result.recorded_programs.slice(0, 12);  // 最新12件のみ表示
        total_programs.value = result.total;
    }
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
    min-width: 0;  // magic!
    margin-left: 21px;
    margin-right: 21px;
    margin-bottom: 24px;
    @include smartphone-vertical {
        margin-left: 12px;
        margin-right: 12px;
        margin-bottom: 20px;
    }
}

</style>