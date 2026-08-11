import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue';

import OfflineVideos from '@/services/OfflineVideos';

/** 処理中のオフライン保存ジョブ件数を監視して返す */
export function useOfflineDownloadJobCount(): { activeJobCount: Ref<number> } {
    const activeJobCount = ref(0);
    let refreshTimerID: number | null = null;
    let isRefreshing = false;

    /** IndexedDB の保存ジョブから表示する処理中件数を取得する */
    const refresh = async (): Promise<void> => {
        // 変更通知と定期更新が重なった場合は、先に始まった読み取りの完了を待つ
        if (isRefreshing === true) return;
        isRefreshing = true;
        try {
            const jobs = await OfflineVideos.getJobs();
            activeJobCount.value = jobs.filter(job => ['Waiting', 'Downloading', 'Finalizing'].includes(job.state)).length;
        } catch (error) {
            // オフライン保存領域の一時的な読み取り失敗で、ナビゲーション全体の描画を止めない
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

    return { activeJobCount };
}
