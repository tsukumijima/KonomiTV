<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <div class="offline-videos-container-wrapper">
                <div class="offline-videos-container">
                    <Breadcrumbs :crumbs="[
                        {name: 'ホーム', path: '/'},
                        {name: 'オフライン保存', path: '/offline-videos/', disabled: true},
                    ]" />
                    <RecordedProgramList title="オフライン保存" :programs="displayPrograms"
                        :total="displayTotal" :hideSort="true" :hidePagination="true" :showBackButton="true"
                        :showEmptyMessage="isLoading === false" :isLoading="isLoading" :forOffline="true"
                        :offlineVideos="videos" :offlineJobs="visibleOfflineJobs"
                        emptyIcon="fluent:cloud-off-24-regular" emptyMessage="オフライン保存した番組はありません。"
                        emptySubMessage="録画番組のメニューまたは視聴画面から保存できます。"
                        @cancelOfflineJob="cancelJob" @dismissOfflineJob="dismissJob">
                        <template #after-header>
                            <section class="offline-videos-storage">
                                <div class="offline-videos-storage__item">
                                    <div class="offline-videos-storage__icon">
                                        <Icon icon="fluent:cloud-arrow-down-20-filled" width="24px" height="24px" />
                                    </div>
                                    <div class="offline-videos-storage__content">
                                        <div class="offline-videos-storage__label">オフライン保存済み</div>
                                        <div class="offline-videos-storage__value">{{Utils.formatBytes(savedSizeBytes, 2, true)}}</div>
                                    </div>
                                </div>
                                <div class="offline-videos-storage__item">
                                    <div class="offline-videos-storage__icon">
                                        <Icon icon="material-symbols:storage-rounded" width="24px" height="24px" />
                                    </div>
                                    <div class="offline-videos-storage__content">
                                        <div class="offline-videos-storage__label">ストレージクオータ</div>
                                        <div class="offline-videos-storage__value">
                                            {{Utils.formatBytes(storageUsageBytes, 2, true)}} / {{Utils.formatBytes(storageQuotaBytes, 2, true)}}
                                        </div>
                                    </div>
                                </div>
                            </section>
                        </template>
                    </RecordedProgramList>
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import Message from '@/message';
import OfflineVideos, { type IOfflineDownloadJob, type IOfflineVideo } from '@/services/OfflineVideos';
import { type IRecordedProgram } from '@/services/Videos';
import Utils from '@/utils';

const videos = ref<IOfflineVideo[]>([]);
const jobs = ref<IOfflineDownloadJob[]>([]);
const storageUsageBytes = ref(0);
const storageQuotaBytes = ref(0);
const isLoading = ref(true);
let isRefreshing = false;

const activeJobs = computed(() => jobs.value.filter(job => ['Waiting', 'Downloading', 'Finalizing'].includes(job.state)));
const visibleOfflineJobs = computed(() => jobs.value.filter(job =>
    ['Waiting', 'Downloading', 'Finalizing', 'Failed'].includes(job.state),
));
const savedSizeBytes = computed(() => videos.value.reduce((total, video) => total + video.size_bytes, 0));

/** 保存済み動画と保存ジョブを1つの一覧へ統合する */
const displayPrograms = computed((): IRecordedProgram[] => {
    const programs: IRecordedProgram[] = [];
    const seenVideoIDs = new Set<number>();

    // 実行中・失敗のジョブを先頭へ並べ、同じ番組の二重表示を防ぐ
    for (const job of visibleOfflineJobs.value) {
        if (seenVideoIDs.has(job.video_id) === true) continue;
        seenVideoIDs.add(job.video_id);
        programs.push(job.program);
    }
    for (const video of videos.value) {
        if (seenVideoIDs.has(video.video_id) === true) continue;
        seenVideoIDs.add(video.video_id);
        programs.push(video.program);
    }
    return programs;
});

const displayTotal = computed(() => displayPrograms.value.length);

/** Background Fetch の受信量をジョブ配列へ反映する */
const applyBackgroundFetchProgress = async (targetJobs: IOfflineDownloadJob[]): Promise<void> => {
    if ('serviceWorker' in navigator === false) return;

    const registration = await navigator.serviceWorker.getRegistration();
    const backgroundFetchManager = registration?.backgroundFetch;
    if (backgroundFetchManager === undefined) return;

    await Promise.all(targetJobs.map(async (job) => {
        // 応答展開中の Finalizing はブラウザの受信進捗で Downloading へ戻さない
        if (job.background_fetch_id === null || ['Waiting', 'Downloading'].includes(job.state) === false) return;
        const backgroundFetch = await backgroundFetchManager.get(job.background_fetch_id);
        if (backgroundFetch === undefined) return;

        // IndexedDB 側は Background Fetch 中ほぼ更新されないため、表示中の値より小さく戻さない
        job.downloaded_bytes = Math.max(job.downloaded_bytes, backgroundFetch.downloaded);
        job.state = job.downloaded_bytes > 0 ? 'Downloading' : 'Waiting';
    }));
};

/** 実行中ジョブの進捗を IndexedDB と Background Fetch から既存配列へ反映する */
const refreshActiveJobProgress = async (): Promise<void> => {
    if (activeJobs.value.length === 0) return;
    try {
        const latestJobs = await OfflineVideos.getJobs();
        let needsFullRefresh = false;

        const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : undefined;
        const backgroundFetchManager = registration?.backgroundFetch;

        for (const job of activeJobs.value) {
            const latestJob = latestJobs.find(candidate => candidate.job_id === job.job_id);

            // IndexedDB から消えていれば Service Worker 側で保存処理が終わっている
            if (latestJob === undefined || ['Waiting', 'Downloading', 'Finalizing'].includes(latestJob.state) === false) {
                needsFullRefresh = true;
                continue;
            }

            // 非同期取得の途中で Waiting を画面へ反映せず、受信量と状態を確定してからまとめて更新する
            let nextDownloadedBytes = Math.max(job.downloaded_bytes, latestJob.downloaded_bytes);
            let nextState = latestJob.state;

            // Background Fetch 中はブラウザ側の受信量の方が進んでいることが多い
            if (latestJob.background_fetch_id !== null && backgroundFetchManager !== undefined &&
                ['Waiting', 'Downloading'].includes(latestJob.state) === true) {
                const backgroundFetch = await backgroundFetchManager.get(latestJob.background_fetch_id);
                if (backgroundFetch === undefined) {
                    needsFullRefresh = true;
                    continue;
                }
                nextDownloadedBytes = Math.max(nextDownloadedBytes, backgroundFetch.downloaded);
                nextState = nextDownloadedBytes > 0 ? 'Downloading' : 'Waiting';
            }

            // 関連する表示値を同じ同期処理内で代入し、状態ラベルとプログレスバーの中間表示を防ぐ
            job.downloaded_bytes = nextDownloadedBytes;
            job.state = nextState;
            job.error = latestJob.error;
        }

        if (needsFullRefresh === true) {
            await refresh();
        }
    } catch (error) {
        console.error('[OfflineVideos] Failed to refresh active offline job progress:', error);
    }
};

/** 保存済み動画、保存ジョブ、ブラウザ容量を IndexedDB と Storage API から読み直す */
const refresh = async (): Promise<void> => {
    if (isRefreshing === true) return;
    isRefreshing = true;
    try {
        const nextVideos = await OfflineVideos.getVideos();
        const nextJobs = await OfflineVideos.getJobs();

        // jobs.value 代入前に Background Fetch 進捗を取り込み、0 バイト表示の中間フレームを出さない
        await applyBackgroundFetchProgress(nextJobs);

        videos.value = nextVideos;
        jobs.value = nextJobs;
        const storageEstimate = await navigator.storage.estimate();
        storageUsageBytes.value = storageEstimate.usage ?? 0;
        storageQuotaBytes.value = storageEstimate.quota ?? 0;
    } catch (error) {
        // 保存領域の読み取り失敗はログに残し、Promise の拒否を未処理のまま残さない
        console.error('[OfflineVideos] Failed to refresh offline video data:', error);
    } finally {
        isLoading.value = false;
        isRefreshing = false;
    }
};

/** 実行中の保存をキャンセルする */
const cancelJob = async (jobID: string): Promise<void> => {
    try {
        await OfflineVideos.cancel(jobID);
    } catch (error) {
        Message.error(error instanceof Error ? error.message : 'オフライン保存をキャンセルできませんでした。');
    } finally {
        await refresh();
    }
};

/** 失敗した保存ジョブを一覧から消す */
const dismissJob = async (jobID: string): Promise<void> => {
    try {
        await OfflineVideos.dismissJob(jobID);
    } catch (error) {
        Message.error(error instanceof Error ? error.message : '失敗した保存ジョブを削除できませんでした。');
    } finally {
        await refresh();
    }
};

// 保存処理のイベントに加え、Background Fetch の進捗も画面表示中だけ定期的に読み直す
let refreshTimerID: number | null = null;
watch(() => activeJobs.value.length > 0, (hasActiveJobs) => {
    // Background Fetch 進捗だけを1秒おきに反映し、IndexedDB 全読み直しによる UI の巻き戻りを避ける
    if (hasActiveJobs === true && refreshTimerID === null) {
        refreshTimerID = window.setInterval(refreshActiveJobProgress, 1000);
    } else if (hasActiveJobs === false && refreshTimerID !== null) {
        window.clearInterval(refreshTimerID);
        refreshTimerID = null;
    }
});
onMounted(() => {
    OfflineVideos.eventTarget.addEventListener('change', refresh);
    void refresh();
});
onBeforeUnmount(() => {
    OfflineVideos.eventTarget.removeEventListener('change', refresh);
    if (refreshTimerID !== null) window.clearInterval(refreshTimerID);
});

</script>
<style lang="scss" scoped>

.offline-videos-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;
    @include smartphone-vertical {
        padding-top: 10px !important;
    }
}

.offline-videos-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 1000px;
    padding: 20px;
    margin: 0 auto;
    @include smartphone-vertical {
        padding: 16px 8px !important;
        padding-top: 8px !important;
    }
}

.offline-videos-storage {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 18px;
    padding: 16px 20px;
    border-radius: 8px;
    background: rgb(var(--v-theme-background-lighten-1));
    @include smartphone-vertical {
        grid-template-columns: 1fr;
        margin-bottom: 14px;
        padding: 14px 16px;
    }

    &__item {
        display: flex;
        align-items: center;
        gap: 14px;
        min-width: 0;
    }

    &__icon {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        width: 44px;
        height: 44px;
        border-radius: 10px;
        // ナビゲーションのアクティブ項目 (navigation__link--active) と同系統の primary トーン
        color: rgb(var(--v-theme-primary));
        background: #5b2d3c;
    }

    &__content {
        min-width: 0;
    }

    &__label {
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 12px;
    }

    &__value {
        margin-top: 3px;
        font-size: 18px;
        font-weight: bold;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
}

</style>
