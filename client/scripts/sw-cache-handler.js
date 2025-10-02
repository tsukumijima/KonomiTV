// ===== OFFLINE_CACHE_HANDLER_INJECTED =====
// オフライン視聴用のカスタムキャッシュハンドラー

// cache miss/hit 追跡用のグローバル変数
const cacheMissTracker = new Map(); // video_id-quality -> { misses: number, consecutiveHits: number, downloadPaused: boolean }

// メッセージハンドラー：ダウンロード開始/停止の通知を受け取る
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'START_DOWNLOAD') {
        const { videoId, quality } = event.data;
        const trackerKey = `${videoId}-${quality}`;

        // tracker を作成（ダウンロード中であることを記録）
        cacheMissTracker.set(trackerKey, {
            misses: 0,
            consecutiveHits: 0,
            downloadPaused: false,
        });
        console.log(`[SW] Download tracker created for video ${videoId} (${quality})`);
    } else if (event.data && event.data.type === 'STOP_DOWNLOAD') {
        const { videoId, quality } = event.data;
        const trackerKey = `${videoId}-${quality}`;

        // tracker を削除
        cacheMissTracker.delete(trackerKey);
        console.log(`[SW] Download tracker removed for video ${videoId} (${quality})`);
    }
});

// 注意: fetch イベントリスナー自体は async にしない（event.respondWith を同期的に呼ぶ必要があるため）
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    const params = new URLSearchParams(url.search);

    // オフライン視聴用リソースのパターンマッチング
    const segmentMatch = url.pathname.match(/\/api\/streams\/video\/(\d+)\/(\d+p(?:-hevc)?)\/segment/);
    const playlistMatch = url.pathname.match(/\/api\/streams\/video\/(\d+)\/(\d+p(?:-hevc)?)\/playlist/);
    const metadataMatch = url.pathname.match(/\/api\/videos\/(\d+)$/);
    const thumbnailMatch = url.pathname.match(/\/api\/videos\/(\d+)\/thumbnail(\/tiled)?$/);

    // いずれかのパターンにマッチしない場合は処理しない
    if (!segmentMatch && !playlistMatch && !metadataMatch && !thumbnailMatch) {
        return;
    }

    event.respondWith(
        (async () => {
            try {
                // リクエスト情報を解析
                let videoId, quality, cacheName, normalizedUrl;

                if (segmentMatch) {
                    videoId = segmentMatch[1];
                    quality = segmentMatch[2].replace('-hevc', '');
                    cacheName = `konomitv-offline-video-${videoId}-${quality}`;
                    const sequence = params.get('sequence');
                    normalizedUrl = sequence !== null ? `${url.origin}${url.pathname}?sequence=${sequence}` : url.href;
                } else if (playlistMatch) {
                    videoId = playlistMatch[1];
                    quality = playlistMatch[2].replace('-hevc', '');
                    cacheName = `konomitv-offline-video-${videoId}-${quality}`;
                    normalizedUrl = `${url.origin}${url.pathname}`;
                } else if (metadataMatch) {
                    videoId = metadataMatch[1];
                    normalizedUrl = `${url.origin}${url.pathname}`;
                } else if (thumbnailMatch) {
                    videoId = thumbnailMatch[1];
                    normalizedUrl = `${url.origin}${url.pathname}`;
                }

                // ============ 早期チェック：キャッシュの存在確認 ============
                // segment/playlist の場合、キャッシュが存在しなければ直接ネットワークから取得
                if (cacheName) {
                    const cacheExists = await caches.has(cacheName);
                    if (!cacheExists) {
                        // console.log(`[SW] Cache not found, fetching from network: ${event.request.url}`);
                        return fetch(event.request);
                    }
                }
                
                const cacheKey = params.get('cache_key');
                // ============ 具体的なキャッシュ戦略 ============

                // Playlist の処理
                if (playlistMatch) {
                    // 下載器請求（帶 cache_key）→ Network First + 寫入緩存
                    if (cacheKey) {
                        const networkResponse = await fetch(event.request);
                        if (networkResponse.ok) {
                            const cache = await caches.open(cacheName);
                            // 寫入緩存，供播放器複用 session_id
                            await cache.put(normalizedUrl, networkResponse.clone());
                            console.log(`[SW] Playlist cached for download session: ${normalizedUrl}`);
                        }
                        return networkResponse;
                    }

                    // 播放器請求（不帶 cache_key）
                    const trackerKey = `${videoId}-${quality}`;
                    const tracker = cacheMissTracker.get(trackerKey);

                    // 有下載任務 → 使用緩存的 playlist（複用下載器的 session_id）
                    if (tracker) {
                        const cache = await caches.open(cacheName);
                        const cachedResponse = await cache.match(normalizedUrl);
                        if (cachedResponse) {
                            console.log(`[SW] ✓ Cache hit (playlist, download active): ${normalizedUrl}`);
                            return cachedResponse;
                        }
                    }

                    // 無下載任務 → 從網路獲取新 session（但斷網時使用緩存）
                    try {
                        console.log(`[SW] No active download, fetching playlist from network: ${event.request.url}`);
                        return await fetch(event.request);
                    } catch (error) {
                        // 斷網時嘗試使用緩存
                        console.log(`[SW] Network failed for playlist, trying cache: ${error}`);
                        const cache = await caches.open(cacheName);
                        const cachedResponse = await cache.match(normalizedUrl);
                        if (cachedResponse) {
                            console.log(`[SW] ✓ Offline cache hit (playlist): ${normalizedUrl}`);
                            return cachedResponse;
                        }
                        throw error;
                    }
                }

                // Segment の処理
                if (segmentMatch) {
                    const cache = await caches.open(cacheName);
                    const cachedResponse = await cache.match(normalizedUrl);

                    if (cachedResponse) {
                        console.log(`[SW] ✓ Cache hit (segment): ${normalizedUrl}`);

                        // 播放器のリクエスト時：連続ヒット数を追跡
                        if (!cacheKey) {
                            const trackerKey = `${videoId}-${quality}`;
                            let tracker = cacheMissTracker.get(trackerKey);
                            if (!tracker) {
                                tracker = { misses: 0, consecutiveHits: 0, downloadPaused: false };
                                cacheMissTracker.set(trackerKey, tracker);
                            }

                            tracker.consecutiveHits++;

                            // 連続 10 回ヒット → ダウンロード再開
                            if (tracker.consecutiveHits >= 10 && tracker.downloadPaused) {
                                console.log(`[SW] 10 consecutive hits, resuming download for video ${videoId} (${quality})`);
                                tracker.downloadPaused = false;
                                tracker.consecutiveHits = 0;

                                const clients = await self.clients.matchAll({ type: 'window' });
                                for (const client of clients) {
                                    client.postMessage({
                                        type: 'RESUME_DOWNLOAD',
                                        videoId: parseInt(videoId),
                                        quality: quality,
                                    });
                                }
                            }
                        }

                        return cachedResponse;
                    }

                    // Cache miss → 從網路獲取
                    console.log(`[SW] Segment cache miss, fetching from network: ${event.request.url}`);
                    const networkResponse = await fetch(event.request);

                    // 如果有下載任務，自動保存到緩存（實現邊看邊存）
                    const trackerKey = `${videoId}-${quality}`;
                    const tracker = cacheMissTracker.get(trackerKey);
                    if (tracker && networkResponse.ok) {
                        await cache.put(normalizedUrl, networkResponse.clone());
                        console.log(`[SW] Segment cached (auto-save): ${normalizedUrl}`);
                    }

                    return networkResponse;
                }

                // Metadata の処理：Network First
                if (metadataMatch) {
                    try {
                        console.log(`[SW] Fetching metadata from network: ${event.request.url}`);
                        const networkResponse = await fetch(event.request);
                        if (networkResponse.ok) {
                            return networkResponse;
                        }
                        throw new Error(`HTTP ${networkResponse.status}`);
                    } catch (error) {
                        // ネットワーク失敗→全ての関連キャッシュから検索
                        console.log(`[SW] Network failed, trying cache: ${error}`);
                        const allCaches = await caches.keys();
                        const offlineCaches = allCaches.filter(name =>
                            name.startsWith('konomitv-offline-video-') && name.includes(`-${videoId}-`)
                        );

                        for (const cacheName of offlineCaches) {
                            const cache = await caches.open(cacheName);
                            const cachedResponse = await cache.match(normalizedUrl);
                            if (cachedResponse) {
                                console.log(`[SW] ✓ Offline cache hit (metadata): ${normalizedUrl}`);
                                return cachedResponse;
                            }
                        }
                        console.log(`[SW] Cache miss (metadata): ${normalizedUrl}`);
                        throw error;
                    }
                }

                // Thumbnail の処理：Cache First（複数の画質で共有）
                if (thumbnailMatch) {
                    const isTiled = thumbnailMatch[2] === '/tiled';
                    const allCaches = await caches.keys();
                    const offlineCaches = allCaches.filter(name =>
                        name.startsWith('konomitv-offline-video-') && name.includes(`-${videoId}-`)
                    );

                    for (const cacheName of offlineCaches) {
                        const cache = await caches.open(cacheName);
                        const cachedResponse = await cache.match(normalizedUrl);
                        if (cachedResponse) {
                            console.log(`[SW] ✓ Cache hit (thumbnail${isTiled ? ' tiled' : ''}): ${normalizedUrl}`);
                            return cachedResponse;
                        }
                    }

                    // キャッシュミス→ネットワークから取得
                    console.log(`[SW] Thumbnail cache miss, fetching from network: ${event.request.url}`);
                    return fetch(event.request);
                }

                // フォールバック：ネットワークから取得
                return fetch(event.request);

            } catch (error) {
                console.error('[SW] Error in offline cache handler:', error);
                return fetch(event.request);
            }
        })()
    );
});
// ===== END OFFLINE_CACHE_HANDLER_INJECTED =====
