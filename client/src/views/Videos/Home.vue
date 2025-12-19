<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="videos-home-container-wrapper">
                <SPHeaderBar />
                <div class="videos-home-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'ビデオをみる', path: '/videos/', disabled: true },
                    ]" />
                    <RecordedProgramList
                        class="videos-home-container__recent-programs"
                        :class="{'videos-home-container__recent-programs--loading': recent_programs.length === 0 && is_loading}"
                        title="新着の録画番組"
                        :programs="recent_programs"
                        :total="total_programs"
                        :hideSort="true"
                        :hidePagination="true"
                        :showMoreButton="true"
                        :showSearch="true"
                        :isLoading="is_loading"
                        :showEmptyMessage="!is_loading"
                        @more="$router.push('/videos/programs')" />
                    <RecordedProgramList
                        title="マイリスト"
                        :programs="mylist_programs"
                        :total="total_mylist_programs"
                        :hideSort="true"
                        :hidePagination="true"
                        :showMoreButton="true"
                        :showEmptyMessage="!is_loading"
                        :emptyIcon="'ic:round-playlist-play'"
                        :emptyMessage="'あとで観たい番組を<br class=\'d-sm-none\'>マイリストに保存できます。'"
                        :emptySubMessage="'録画番組の右上にある ＋ ボタンから、<br class=\'d-sm-none\'>番組をマイリストに追加できます。'"
                        :isLoading="is_loading"
                        :forMylist="true"
                        @more="$router.push('/mylist/')" />
                    <RecordedProgramList
                        title="視聴履歴"
                        :programs="watched_programs"
                        :total="total_watched_programs"
                        :hideSort="true"
                        :hidePagination="true"
                        :showMoreButton="true"
                        :showEmptyMessage="!is_loading"
                        :emptyIcon="'fluent:history-20-regular'"
                        :emptyMessage="'まだ視聴履歴がありません。'"
                        :emptySubMessage="'録画番組を30秒以上みると、<br class=\'d-sm-none\'>視聴履歴に追加されます。'"
                        :isLoading="is_loading"
                        :forWatchedHistory="true"
                        @more="$router.push('/watched-history/')" />
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { onMounted, ref, onUnmounted, watch } from 'vue';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import { IRecordedProgram } from '@/services/Videos';
import Videos from '@/services/Videos';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';

// 最近録画された番組のリスト
const recent_programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);

// マイリストの録画番組のリスト
const mylist_programs = ref<IRecordedProgram[]>([]);
const total_mylist_programs = ref(0);

// 視聴履歴の録画番組のリスト
const watched_programs = ref<IRecordedProgram[]>([]);
const total_watched_programs = ref(0);

const is_loading = ref(true);

// 自動更新用の interval ID を保持
const autoRefreshInterval = ref<number | null>(null);

// 自動更新の間隔 (ミリ秒)
const AUTO_REFRESH_INTERVAL = 30 * 1000;  // 30秒

// マイリストの変更を監視して即座に再取得
const settingsStore = useSettingsStore();
watch(() => settingsStore.settings.mylist, async () => {
    await fetchMylistPrograms();
}, { deep: true });

// 視聴履歴の変更を監視して即座に再取得
watch(() => settingsStore.settings.watched_history, async () => {
    await fetchWatchedPrograms();
}, { deep: true });

// 最近録画された番組を取得
const fetchRecentPrograms = async () => {
    const result = await Videos.fetchVideos('desc', 1);
    if (result) {
        recent_programs.value = result.recorded_programs.slice(0, 10);  // 最新10件のみ表示
        total_programs.value = result.total;
    }
};

// マイリストの録画番組を取得
const fetchMylistPrograms = async () => {
    // マイリストに登録されている録画番組の ID を取得
    const mylist_ids = settingsStore.settings.mylist
        .filter(item => item.type === 'RecordedProgram')
        .sort((a, b) => b.created_at - a.created_at)  // 新しい順
        .map(item => item.id);

    // マイリストが空の場合は早期リターン
    if (mylist_ids.length === 0) {
        mylist_programs.value = [];
        total_mylist_programs.value = 0;
        return;
    }

    // 録画番組を取得
    const result = await Videos.fetchVideos('ids', 1, mylist_ids);
    if (result) {
        mylist_programs.value = result.recorded_programs.slice(0, 4);  // 最新4件のみ表示
        total_mylist_programs.value = result.total;
    }
};

// 視聴履歴の録画番組を取得
const fetchWatchedPrograms = async () => {
    // 視聴履歴に登録されている録画番組の ID を取得
    const watched_ids = settingsStore.settings.watched_history
        .sort((a, b) => b.updated_at - a.updated_at)  // 最後に視聴した順
        .map(history => history.video_id);

    // 視聴履歴が空の場合は早期リターン
    if (watched_ids.length === 0) {
        watched_programs.value = [];
        total_watched_programs.value = 0;
        return;
    }

    // 録画番組を取得
    const result = await Videos.fetchVideos('ids', 1, watched_ids);
    if (result) {
        watched_programs.value = result.recorded_programs.slice(0, 4);  // 最新4件のみ表示
        total_watched_programs.value = result.total;
    }
};

// 各セクションの更新関数を管理するオブジェクト
const sectionUpdaters = {
    recentPrograms: fetchRecentPrograms,
    mylistPrograms: fetchMylistPrograms,
    watchedPrograms: fetchWatchedPrograms,
} as const;

// 全セクションの更新を実行
const updateAllSections = async () => {
    try {
        // 全セクションの更新関数を実行
        await Promise.all(Object.values(sectionUpdaters).map(updater => updater()));
        is_loading.value = false;
    } catch (error) {
        console.error('Failed to update sections:', error);
        is_loading.value = false;
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

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();
    startAutoRefresh();
});

// コンポーネントのクリーンアップ
onUnmounted(() => {
    stopAutoRefresh();
});

</script>
<style lang="scss" scoped>

.videos-home-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.videos-home-container {
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
        padding-top: 8px !important;
        padding-left: 8px !important;
        padding-right: 8px !important;
        padding-bottom: 20px !important;
    }

    :deep(.recorded-program-list) {
        & + .recorded-program-list {
            margin-top: 28px;
            @include smartphone-vertical {
                margin-top: 16px;
            }
        }
    }

    &__recent-programs.videos-home-container__recent-programs--loading {
        // ローディング中にちらつかないように
        :deep(.recorded-program-list__grid) {
            height: calc(125px * 10);
            @include smartphone-vertical {
                height: calc(100px * 10);
            }
        }
    }
}

</style>