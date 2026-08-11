/// <reference lib="webworker" />

import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';

import OfflineVideos from '@/services/OfflineVideos';
import OfflineVideoStorage from '@/services/OfflineVideoStorage';


declare let self: ServiceWorkerGlobalScope;

// generateSW が生成していた更新メッセージを維持し、5秒後の更新処理で待機中の Service Worker を有効化する
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SKIP_WAITING') {
        event.waitUntil(self.skipWaiting());
    }
});

// Vite がビルドごとのアプリ資産一覧を注入し、従来の generateSW と同じ範囲を事前キャッシュする
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// 通常画面は従来の generateSW と同じく index.html へ戻し、API と Cloudflare の内部 URL は対象から外す
registerRoute(new NavigationRoute(createHandlerBoundToURL('index.html'), {
    denylist: [/^\/api/, /^\/cdn-cgi/],
}));

// 保存済み HLS は通常の HTTP キャッシュへ依存せず、オフライン動画専用 CacheStorage から返す
self.addEventListener('fetch', (event) => {
    const requestURL = new URL(event.request.url);
    if (requestURL.origin === self.location.origin && requestURL.pathname.startsWith('/__offline__/videos/')) {
        event.respondWith(OfflineVideoStorage.getResponse(event.request));
    }
});

// Background Fetch が全データを保持し終えた後、ページが閉じていても同じ保存処理を完了させる
self.addEventListener('backgroundfetchsuccess', (event: BackgroundFetchEvent) => {
    event.waitUntil((async () => {
        const jobID = event.registration.id.replace('konomitv-offline-', '');
        try {
            const records = await event.registration.matchAll();
            if (records.length !== 1) {
                throw new Error(`Unexpected background fetch record count: ${records.length}`);
            }
            await OfflineVideos.finalizeResponse(jobID, await records[0].responseReady);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Background fetch response processing failed.';
            await OfflineVideos.markJobFailed(jobID, message);
            throw error;
        }
    })());
});

// ブラウザが報告した失敗理由を保存し、次回 KonomiTV を開いたときにアプリ内で確認できるようにする
self.addEventListener('backgroundfetchfail', (event: BackgroundFetchEvent) => {
    event.waitUntil((async () => {
        const jobID = event.registration.id.replace('konomitv-offline-', '');
        const failureMessages: Record<BackgroundFetchRegistration['failureReason'], string> = {
            '': '原因を特定できませんでした。',
            'aborted': 'ブラウザによって保存が中止されました。',
            'bad-status': 'サーバーがエラーを返しました。',
            'fetch-error': '通信に失敗しました。',
            'quota-exceeded': '端末の空き容量が不足しています。',
            'download-total-exceeded': '受信量がブラウザへ通知した容量を超えました。',
        };
        await OfflineVideos.markJobFailed(jobID, `バックグラウンド保存に失敗しました。${failureMessages[event.registration.failureReason]}`);
    })());
});

// ブラウザ UI または KonomiTV からキャンセルされたジョブの断片を削除する
self.addEventListener('backgroundfetchabort', (event: BackgroundFetchEvent) => {
    event.waitUntil((async () => {
        const jobID = event.registration.id.replace('konomitv-offline-', '');
        await OfflineVideos.markJobCancelled(jobID);
    })());
});
