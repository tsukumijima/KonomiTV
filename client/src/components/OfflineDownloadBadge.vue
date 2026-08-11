<template>
    <router-link v-if="activeJobCount > 0" v-ripple class="offline-download-badge" to="/offline-videos/"
        v-ftooltip="`${activeJobCount}件のオフライン保存を処理中`">
        <Icon icon="fluent:cloud-arrow-down-20-filled" width="23px" />
        <span>{{activeJobCount}}</span>
    </router-link>
</template>
<script lang="ts" setup>

import { onBeforeUnmount, onMounted, ref } from 'vue';

import OfflineVideos from '@/services/OfflineVideos';

const activeJobCount = ref(0);
let refreshTimerID: number | null = null;
let isRefreshing = false;

/** IndexedDB の保存ジョブからヘッダーへ表示する処理中件数を取得する */
const refresh = async (): Promise<void> => {
    // 変更通知と定期更新が重なった場合は、先に始まった読み取りの完了を待つ
    if (isRefreshing === true) return;
    isRefreshing = true;
    try {
        const jobs = await OfflineVideos.getJobs();
        activeJobCount.value = jobs.filter(job => ['Waiting', 'Downloading', 'Finalizing'].includes(job.state)).length;
    } catch (error) {
        // オフライン保存領域の一時的な読み取り失敗で、ヘッダー全体の描画を止めない
        console.warn('[OfflineDownloadBadge] Failed to read offline download jobs:', error);
    } finally {
        isRefreshing = false;
    }
};

onMounted(() => {
    OfflineVideos.eventTarget.addEventListener('change', refresh);
    // Service Worker 側の完了はページ側 EventTarget へ届かないため、表示中だけ低頻度で状態を読み直す
    refreshTimerID = window.setInterval(refresh, 2000);
    void refresh();
});
onBeforeUnmount(() => {
    OfflineVideos.eventTarget.removeEventListener('change', refresh);
    if (refreshTimerID !== null) window.clearInterval(refreshTimerID);
});

</script>
<style lang="scss" scoped>

.offline-download-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    width: 42px;
    height: 42px;
    border-radius: 50%;
    color: rgb(var(--v-theme-text));

    span {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        top: 1px;
        right: 0;
        min-width: 17px;
        height: 17px;
        padding: 0 4px;
        border-radius: 9px;
        color: white;
        background: rgb(var(--v-theme-primary));
        font-size: 10px;
        font-weight: bold;
    }
}

</style>
