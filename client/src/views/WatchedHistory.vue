<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <div class="watched-history-container-wrapper">
                <div class="watched-history-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '視聴履歴', path: '/watched-history/', disabled: true },
                    ]" />
                    <RecordedProgramList
                        title="視聴履歴"
                        :programs="programs"
                        :total="total_programs"
                        :page="current_page"
                        :hideSort="true"
                        :isLoading="is_loading"
                        :showBackButton="true"
                        :showEmptyMessage="!is_loading"
                        :emptyIcon="'fluent:history-20-regular'"
                        :emptyMessage="'まだ視聴履歴がありません。'"
                        :emptySubMessage="'録画番組を30秒以上みると、<br class=\'d-sm-none\'>視聴履歴に追加されます。'"
                        :forWatchedHistory="true"
                        @update:page="updatePage" />
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
import { IRecordedProgram } from '@/services/Videos';
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

// 録画番組を取得
const fetchPrograms = async () => {
    // 視聴履歴に登録されている録画番組の ID を取得
    const history_ids = settingsStore.settings.watched_history
        .sort((a, b) => b.updated_at - a.updated_at)  // 最後に視聴した順
        .map(history => history.video_id);

    // 視聴履歴が空の場合は早期リターン
    if (history_ids.length === 0) {
        programs.value = [];
        total_programs.value = 0;
        is_loading.value = false;
        return;
    }

    // 録画番組を取得
    const result = await Videos.fetchVideos('ids', current_page.value, history_ids);
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

// クエリパラメータが変更されたら録画番組を再取得
watch(() => route.query, async (newQuery) => {
    // ページ番号を同期
    if (newQuery.page) {
        current_page.value = parseInt(newQuery.page as string);
    }
    await fetchPrograms();
}, { deep: true });

// 視聴履歴の変更を監視して即座に再取得
watch(() => settingsStore.settings.watched_history, async () => {
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

    // 録画番組を取得
    await fetchPrograms();
});

</script>
<style lang="scss" scoped>

.watched-history-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    @include smartphone-vertical {
        padding-top: 10px !important;
    }
}

.watched-history-container {
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