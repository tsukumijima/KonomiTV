<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="reservations-ranking-container-wrapper">
                <SPHeaderBar />
                <div class="reservations-ranking-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '録画予約', path: '/reservations/' },
                        { name: '予約数ランキング', path: '/reservations/ranking', disabled: true },
                    ]" />
                    <ToruRanking
                        :limit="20"
                        :page="page"
                        :filter="filter"
                        :show-pagination="true"
                        :show-back-button="true"
                        :show-filter="true"
                        @update:page="updatePage"
                        @update:filter="updateFilter" />
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import ToruRanking from '@/components/Reservations/ToruRanking.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import { TORU_RANKING_GENRES, ToruRankingFilter } from '@/stores/ToruCountStore';

const route = useRoute();
const router = useRouter();

// 現在のページ番号
// ブラウザの戻る・進むでもページと絞り込みの状態を保てるよう、どちらもクエリパラメータで保持する
const page = computed(() => {
    const page_number = typeof route.query.page === 'string' ? Number.parseInt(route.query.page, 10) : 1;
    return Number.isFinite(page_number) && page_number > 0 ? page_number : 1;
});
// ランキングの絞り込み (チャンネルタイプかジャンルのどちらか一方)
const filter = computed<ToruRankingFilter>(() => {
    const type = route.query.type;
    if (type === 'GR' || type === 'BS' || type === 'CS') {
        return type;
    }
    const genre = TORU_RANKING_GENRES.find((genre) => genre.value === type);
    return genre !== undefined ? genre.value : 'All';
});

/**
 * ページ番号を更新する
 */
async function updatePage(new_page: number) {
    await router.replace({
        query: {
            ...route.query,
            page: new_page.toString(),
        },
    });
}

/**
 * ランキングの絞り込みを更新する
 */
async function updateFilter(new_filter: ToruRankingFilter) {
    // 絞り込みを変更するとランキングの内容が変わるため、1ページ目に戻す
    await router.replace({
        query: {
            ...route.query,
            type: new_filter === 'All' ? undefined : new_filter,
            page: '1',
        },
    });
}

</script>
<style lang="scss" scoped>

.reservations-ranking-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;  // very important!!! これがないと要素がはみ出す
}

.reservations-ranking-container {
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
