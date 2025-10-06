import APIClient from '@/services/APIClient';
import Utils from '@/utils';

/** オフラインダウンロードの状態 */
export type OfflineDownloadStatus = 'pending' | 'downloading' | 'completed' | 'failed' | 'paused';

/** オフライン視聴用ビデオ情報 */
export interface IOfflineVideo {
    video_id: number;
    title: string;
    quality: string;
    is_hevc: boolean; // HEVC (H.265) でダウンロードされたかどうか
    status: OfflineDownloadStatus;
    progress: number; // 0-100
    downloaded_segments: number; // ダウンロード済みセグメント数
    total_segments: number; // 総セグメント数
    total_size: number; // 総サイズ (bytes)
    downloaded_size: number; // ダウンロード済みサイズ (bytes)
    created_at: number; // タイムスタンプ
    updated_at: number; // タイムスタンプ
    cache_name: string; // Cache Storage 内のキャッシュ名
}

/** ダウンロード状態メタデータ（Cache Storage に保存） */
interface DownloadStatusMetadata {
    total_segments: number; // 総セグメント数
    downloaded_segments: number[]; // ダウンロード済みセグメントのインデックス配列
    status: OfflineDownloadStatus; // ダウンロード状態
    last_updated: number; // 最終更新タイムスタンプ
    is_hevc: boolean; // HEVC (H.265) でダウンロードしているかどうか
    lock: {
        locked: boolean; // ロック状態
        page_id: string; // ロックを保持しているページID
        timestamp: number; // ロックのタイムスタンプ（2分間更新されなければ期限切れ）
    };
}

/** オフラインダウンロード管理クラス */
class OfflineDownload {

    // オフライン視聴用ビデオ専用のキャッシュ名プレフィックス
    private static readonly CACHE_PREFIX = 'konomitv-offline-video-';

    /**
     * 永続的なストレージ権限をリクエストする
     * @returns 永続的なストレージ権限が付与された場合は true
     */
    static async requestPersistentStorage(): Promise<boolean> {
        if (navigator.storage && navigator.storage.persist) {
            const isPersisted = await navigator.storage.persist();
            console.log(`[OfflineDownload] Persistent storage granted: ${isPersisted}`);
            return isPersisted;
        }
        return false;
    }

    /**
     * ストレージ使用量情報を取得する
     * @returns 使用量情報オブジェクト { usage: 使用済みバイト数, quota: 総容量バイト数, available: 利用可能バイト数 }
     */
    static async getStorageQuota(): Promise<{ usage: number; quota: number; available: number } | null> {
        if (navigator.storage && navigator.storage.estimate) {
            const estimate = await navigator.storage.estimate();
            const usage = estimate.usage || 0;
            const quota = estimate.quota || 0;
            const available = quota - usage;

            console.log(`[OfflineDownload] Storage: ${Utils.formatBytes(usage)} / ${Utils.formatBytes(quota)} (available: ${Utils.formatBytes(available)})`);

            return { usage, quota, available };
        }
        return null;
    }

    /**
     * 十分なストレージ容量があるかチェックする
     * @param requiredBytes 必要なバイト数
     * @returns 十分な容量がある場合は true
     */
    static async hasEnoughSpace(requiredBytes: number): Promise<boolean> {
        const quota = await this.getStorageQuota();
        if (!quota) {
            // 使用量情報を取得できない場合、保守的に false を返す
            return false;
        }
        return quota.available >= requiredBytes;
    }

    /**
     * ビデオのキャッシュ名を取得する
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @returns キャッシュ名
     */
    static getCacheName(video_id: number, quality: string): string {
        return `${this.CACHE_PREFIX}${video_id}-${quality}`;
    }

    /**
     * 画質とコーデックを組み合わせた文字列を取得
     * @param quality 画質 (例: "1080p")
     * @param is_hevc HEVC (H.265) を使用するかどうか
     * @returns コーデック付き画質文字列 (例: "1080p-hevc" または "1080p")
     */
    private static getQualityWithCodec(quality: string, is_hevc: boolean): string {
        return is_hevc ? `${quality}-hevc` : quality;
    }

    /**
     * ストリーミング API の playlist URL を構築
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param is_hevc HEVC (H.265) を使用するかどうか
     * @param session_id セッション ID (オプション)
     * @param cache_key キャッシュキー（ダウンロード用、オプション）
     * @returns playlist の完全な URL
     */
    private static buildPlaylistUrl(video_id: number, quality: string, is_hevc: boolean, session_id?: string, cache_key?: string): string {
        const qualityWithCodec = this.getQualityWithCodec(quality, is_hevc);
        const baseUrl = `${Utils.api_base_url}/streams/video/${video_id}/${qualityWithCodec}/playlist`;
        const params = new URLSearchParams();
        if (session_id) params.set('session_id', session_id);
        if (cache_key) params.set('cache_key', cache_key);
        return params.toString() ? `${baseUrl}?${params.toString()}` : baseUrl;
    }

    /**
     * ストリーミング API の playlist の相対パスを構築
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param is_hevc HEVC (H.265) を使用するかどうか
     * @returns playlist の相対パス
     */
    private static buildPlaylistRelativePath(video_id: number, quality: string, is_hevc: boolean): string {
        const qualityWithCodec = this.getQualityWithCodec(quality, is_hevc);
        return `/api/streams/video/${video_id}/${qualityWithCodec}/playlist`;
    }

    /**
     * ダウンロード状態メタデータの URL を取得
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @returns メタデータの URL
     */
    private static getDownloadStatusUrl(video_id: number, quality: string): string {
        return `/api/videos/${video_id}/${quality}/download-status`;
    }

    /**
     * ダウンロード状態メタデータを取得
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @returns メタデータ、存在しない場合は null
     */
    private static async getDownloadStatus(video_id: number, quality: string): Promise<DownloadStatusMetadata | null> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            const cache = await caches.open(cacheName);
            const statusUrl = this.getDownloadStatusUrl(video_id, quality);
            const response = await cache.match(statusUrl);

            if (!response) {
                return null;
            }

            const metadata: DownloadStatusMetadata = await response.json();
            return metadata;
        } catch (error) {
            console.error('[OfflineDownload] Failed to get download status:', error);
            return null;
        }
    }

    /**
     * ダウンロード状態メタデータを更新
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param updates 更新する項目
     */
    private static async updateDownloadStatus(
        video_id: number,
        quality: string,
        updates: Partial<DownloadStatusMetadata>,
    ): Promise<void> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            const cache = await caches.open(cacheName);
            const statusUrl = this.getDownloadStatusUrl(video_id, quality);

            // 既存のメタデータを取得
            let metadata = await this.getDownloadStatus(video_id, quality);

            if (!metadata) {
                // 初回作成
                metadata = {
                    total_segments: 0,
                    downloaded_segments: [],
                    status: 'pending',
                    last_updated: Date.now(),
                    is_hevc: false, // デフォルトは H.264
                    lock: {
                        locked: false,
                        page_id: '',
                        timestamp: 0,
                    },
                };
            }

            // 更新をマージ
            metadata = {
                ...metadata,
                ...updates,
                last_updated: Date.now(),
            };

            // キャッシュに保存
            const response = new Response(JSON.stringify(metadata), {
                status: 200,
                statusText: 'OK',
                headers: {
                    'Content-Type': 'application/json',
                },
            });

            await cache.put(statusUrl, response);
            console.log(`[OfflineDownload] Updated download status for video ${video_id} (${quality})`);
        } catch (error) {
            console.error('[OfflineDownload] Failed to update download status:', error);
        }
    }

    /**
     * ダウンロードロックを取得
     * ロックが期限切れ（2分間更新なし）の場合は強制的に取得可能
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param page_id ページ ID
     * @returns ロック取得に成功した場合は true
     */
    private static async acquireDownloadLock(
        video_id: number,
        quality: string,
        page_id: string,
    ): Promise<boolean> {
        try {
            const metadata = await this.getDownloadStatus(video_id, quality);
            const now = Date.now();
            const LOCK_TIMEOUT = 10 * 1000; // 10秒

            if (!metadata) {
                // メタデータが存在しない場合は新規作成してロック取得
                await this.updateDownloadStatus(video_id, quality, {
                    lock: {
                        locked: true,
                        page_id,
                        timestamp: now,
                    },
                });
                console.log(`[OfflineDownload] Acquired new lock for video ${video_id} (${quality}) by page ${page_id}`);
                return true;
            }

            // デバッグ情報を出力
            const lockAge = now - metadata.lock.timestamp;
            console.log(`[OfflineDownload] Lock status for video ${video_id} (${quality}):`, {
                locked: metadata.lock.locked,
                page_id: metadata.lock.page_id,
                timestamp: metadata.lock.timestamp,
                age_ms: lockAge,
                timeout_ms: LOCK_TIMEOUT,
                expired: lockAge > LOCK_TIMEOUT,
            });

            // ロックがない場合、またはロックが期限切れの場合はロックを取得
            if (!metadata.lock.locked || lockAge > LOCK_TIMEOUT) {
                if (metadata.lock.locked) {
                    console.log(`[OfflineDownload] Lock expired (${Math.floor(lockAge / 1000)}s > ${LOCK_TIMEOUT / 1000}s) for video ${video_id} (${quality}), acquiring new lock`);
                }
                await this.updateDownloadStatus(video_id, quality, {
                    lock: {
                        locked: true,
                        page_id,
                        timestamp: now,
                    },
                });
                console.log(`[OfflineDownload] Acquired lock for video ${video_id} (${quality}) by page ${page_id}`);
                return true;
            }

            // 同じ page_id が既にロックを保持している場合はロックを更新
            if (metadata.lock.page_id === page_id) {
                await this.updateDownloadStatus(video_id, quality, {
                    lock: {
                        locked: true,
                        page_id,
                        timestamp: now,
                    },
                });
                console.log(`[OfflineDownload] Refreshed existing lock for video ${video_id} (${quality}) by page ${page_id}`);
                return true;
            }

            // 別の page_id がロックを保持している場合は取得失敗
            console.warn(`[OfflineDownload] Lock held by another page (${metadata.lock.page_id}) for video ${video_id} (${quality}), age: ${Math.floor(lockAge / 1000)}s`);
            return false;
        } catch (error) {
            console.error('[OfflineDownload] Failed to acquire lock:', error);
            return false;
        }
    }

    /**
     * ダウンロードロックを解放
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param page_id ページ ID
     */
    static async releaseDownloadLock(
        video_id: number,
        quality: string,
        page_id: string,
    ): Promise<void> {
        try {
            const metadata = await this.getDownloadStatus(video_id, quality);

            // 自分がロックを保持している場合のみ解放
            if (metadata && metadata.lock.page_id === page_id) {
                await this.updateDownloadStatus(video_id, quality, {
                    lock: {
                        locked: false,
                        page_id: '',
                        timestamp: 0,
                    },
                });
                console.log(`[OfflineDownload] Released lock for video ${video_id} (${quality}) by page ${page_id}`);
            } else {
                console.warn(`[OfflineDownload] Cannot release lock: not held by page ${page_id}`);
            }
        } catch (error) {
            console.error('[OfflineDownload] Failed to release lock:', error);
        }
    }

    /**
     * ダウンロードロックのハートビートを更新（30秒ごとに呼び出し）
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param page_id ページ ID
     */
    private static async refreshDownloadLock(
        video_id: number,
        quality: string,
        page_id: string,
    ): Promise<void> {
        try {
            const metadata = await this.getDownloadStatus(video_id, quality);

            // 自分がロックを保持している場合のみ更新
            if (metadata && metadata.lock.locked && metadata.lock.page_id === page_id) {
                await this.updateDownloadStatus(video_id, quality, {
                    lock: {
                        locked: true,
                        page_id,
                        timestamp: Date.now(),
                    },
                });
                console.log(`[OfflineDownload] Refreshed lock heartbeat for video ${video_id} (${quality}) by page ${page_id}`);
            }
        } catch (error) {
            console.error('[OfflineDownload] Failed to refresh lock:', error);
        }
    }

    /**
     * HLS playlist (.m3u8) を解析して全 .ts セグメントの URL を取得する
     * @param playlistUrl HLS playlist の URL
     * @returns .ts セグメントの URL 一覧
     */
    static async parseHLSPlaylist(playlistUrl: string): Promise<string[]> {
        try {
            const response = await APIClient.get<string>(playlistUrl, {
                responseType: 'text',
            });
            if (response.type === 'error') {
                throw new Error(`Failed to fetch playlist: ${response.status}`);
            }

            const playlistText = response.data;
            return this.parseHLSPlaylistFromText(playlistText, playlistUrl);
        } catch (error) {
            console.error('[OfflineDownload] Failed to parse HLS playlist:', error);
            throw error;
        }
    }

    /**
     * HLS playlist のテキストを解析して全 .ts セグメントの URL を取得する
     * @param playlistText HLS playlist のテキスト内容
     * @param baseUrl ベース URL（相対パスの解決に使用）
     * @returns .ts セグメントの URL 一覧
     */
    static parseHLSPlaylistFromText(playlistText: string, baseUrl: string): string[] {
        const lines = playlistText.split('\n');
        const segmentUrls: string[] = [];

        // HLS playlist を解析して .ts ファイルの URL を抽出
        for (const line of lines) {
            const trimmedLine = line.trim();
            // コメント行と空行をスキップ
            if (trimmedLine.startsWith('#') || trimmedLine === '') {
                continue;
            }
            // .ts セグメントは通常相対パスなので、絶対 URL に解決する
            const segmentUrl = new URL(trimmedLine, baseUrl).href;
            segmentUrls.push(segmentUrl);
        }

        console.log(`[OfflineDownload] Parsed ${segmentUrls.length} segments from playlist text`);
        return segmentUrls;
    }

    /**
     * キャッシュされたセグメント数を取得する（断点続伝用）
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param segmentUrls 全セグメント URL のリスト
     * @returns キャッシュ済みのセグメント数
     */
    static async getCachedSegmentsCount(video_id: number, quality: string, segmentUrls: string[]): Promise<number> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            const cache = await caches.open(cacheName);
            let cachedCount = 0;

            for (const segmentUrl of segmentUrls) {
                // セグメント URL を正規化
                let normalizedSegmentUrl = segmentUrl;
                try {
                    const url = new URL(segmentUrl);
                    const params = new URLSearchParams(url.search);
                    const sequence = params.get('sequence');
                    if (sequence !== null) {
                        url.search = `?sequence=${sequence}`;
                        normalizedSegmentUrl = url.toString();
                    }
                } catch (e) {
                    // URL 解析失敗時はそのまま使用
                }

                const cachedResponse = await cache.match(normalizedSegmentUrl);
                if (cachedResponse) {
                    cachedCount++;
                }
            }

            return cachedCount;
        } catch (error) {
            console.error('[OfflineDownload] Failed to get cached segments count:', error);
            return 0;
        }
    }

    /**
     * ビデオの全セグメント、メタデータ、サムネイルをダウンロードしてキャッシュする
     * 断点続伝に対応：既にダウンロード済みのセグメントはスキップする
     * @param video_id 録画番組 ID
     * @param quality 画質 (例: '1080p', '720p' など)
     * @param use_hevc HEVC (H.265) でダウンロードするかどうか (デフォルト: false)
     * @param page_id ページ ID (ダウンロードロック用、デフォルトは自動生成)
     * @param onProgress 進捗コールバック関数、引数は (ダウンロード済みセグメント数, 総セグメント数)
     * @param abortSignal ダウンロードを中止するための AbortSignal (オプション)
     * @returns ダウンロードが成功したかどうか
     */
    static async downloadVideo(
        video_id: number,
        quality: string,
        use_hevc: boolean = false,
        page_id: string = crypto.randomUUID(),
        onProgress?: (downloaded: number, total: number) => void,
        abortSignal?: AbortSignal,
    ): Promise<boolean> {
        let heartbeatTimer: number | null = null;

        try {
            console.log(`[OfflineDownload] Starting download for video ${video_id} at ${quality} (HEVC: ${use_hevc}) by page ${page_id}`);

            // 1. ダウンロードロックを取得
            const lockAcquired = await this.acquireDownloadLock(video_id, quality, page_id);
            if (!lockAcquired) {
                const error = new Error('この動画は別のタブ/ウィンドウでダウンロード中です');
                error.name = 'DownloadLockError';
                console.error('[OfflineDownload] Failed to acquire download lock, another page is downloading this video');
                throw error;
            }

            // Service Worker に通知して tracker を作成（セグメントの自動キャッシュを有効化）
            if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                navigator.serviceWorker.controller.postMessage({
                    type: 'START_DOWNLOAD',
                    videoId: video_id,
                    quality: quality,
                });
                console.log(`[OfflineDownload] Notified Service Worker to start tracking download for video ${video_id} (${quality})`);
            }

            // is_hevc フラグをメタデータに保存
            await this.updateDownloadStatus(video_id, quality, {
                is_hevc: use_hevc,
            });

            // 2. ハートビートタイマーを開始（5秒ごとにロックを更新）
            heartbeatTimer = window.setInterval(async () => {
                await this.refreshDownloadLock(video_id, quality, page_id);
            }, 5000);

            // 3. Cache Storage を開く
            const cacheName = this.getCacheName(video_id, quality);
            const cache = await caches.open(cacheName);

            // 1. 録画番組のメタデータを取得してキャッシュ
            console.log('[OfflineDownload] Caching video metadata...');
            const metadataUrl = `${Utils.api_base_url}/videos/${video_id}`;
            let targetDownloadPercentage = 100; // デフォルトは 100%
            try {
                const metadataResponse = await APIClient.get(`/videos/${video_id}`);
                if (metadataResponse.type === 'success') {
                    // service_id を確認（333 の場合は 80% で十分）
                    const metadata = metadataResponse.data as any;
                    if (metadata?.channel?.service_id === '333') {
                        targetDownloadPercentage = 80;
                        console.log('[OfflineDownload] service_id is 333, target download percentage set to 80%');
                    }

                    // JSON レスポンスを Response オブジェクトに変換
                    const metadataResponseForCache = new Response(JSON.stringify(metadataResponse.data), {
                        status: 200,
                        statusText: 'OK',
                        headers: { 'Content-Type': 'application/json' },
                    });
                    // 完整 URL でキャッシュ
                    await cache.put(metadataUrl, metadataResponseForCache.clone());
                    // 相対パスでもキャッシュ（Service Worker と同じ形式）
                    await cache.put(`/api/videos/${video_id}`, metadataResponseForCache.clone());
                } else {
                    console.warn('[OfflineDownload] Failed to cache video metadata:', metadataResponse.status);
                }
            } catch (error) {
                console.warn('[OfflineDownload] Failed to fetch video metadata:', error);
            }

            // 2. サムネイルをキャッシュ（失敗しても続行）
            console.log('[OfflineDownload] Caching thumbnail...');
            const thumbnailUrl = `${Utils.api_base_url}/videos/${video_id}/thumbnail`;
            try {
                const thumbnailResponse = await APIClient.get<Blob>(`/videos/${video_id}/thumbnail`, {
                    responseType: 'blob',
                    signal: abortSignal,
                });
                if (thumbnailResponse.type === 'success') {
                    // Blob レスポンスを Response オブジェクトに変換
                    const thumbnailResponseForCache = new Response(thumbnailResponse.data, {
                        status: 200,
                        statusText: 'OK',
                        headers: { 'Content-Type': 'image/jpeg' },
                    });
                    // 完整 URL でキャッシュ
                    await cache.put(thumbnailUrl, thumbnailResponseForCache.clone());
                    // 相対パスでもキャッシュ
                    await cache.put(`/api/videos/${video_id}/thumbnail`, thumbnailResponseForCache.clone());
                } else {
                    console.warn('[OfflineDownload] Failed to cache thumbnail:', thumbnailResponse.status);
                }
            } catch (error) {
                console.warn('[OfflineDownload] Failed to fetch thumbnail (continuing anyway):', error);
            }

            // 3. タイル状サムネイル（シークバー用）をキャッシュ（失敗しても続行）
            console.log('[OfflineDownload] Caching tiled thumbnail...');
            const tiledThumbnailUrl = `${Utils.api_base_url}/videos/${video_id}/thumbnail/tiled`;
            try {
                const tiledThumbnailResponse = await APIClient.get<Blob>(`/videos/${video_id}/thumbnail/tiled`, {
                    responseType: 'blob',
                    signal: abortSignal,
                });
                if (tiledThumbnailResponse.type === 'success') {
                    // Blob レスポンスを Response オブジェクトに変換
                    const tiledThumbnailResponseForCache = new Response(tiledThumbnailResponse.data, {
                        status: 200,
                        statusText: 'OK',
                        headers: { 'Content-Type': 'image/jpeg' },
                    });
                    // 完整 URL でキャッシュ
                    await cache.put(tiledThumbnailUrl, tiledThumbnailResponseForCache.clone());
                    // 相対パスでもキャッシュ
                    await cache.put(`/api/videos/${video_id}/thumbnail/tiled`, tiledThumbnailResponseForCache.clone());
                } else {
                    console.warn('[OfflineDownload] Failed to cache tiled thumbnail:', tiledThumbnailResponse.status);
                }
            } catch (error) {
                console.warn('[OfflineDownload] Failed to fetch tiled thumbnail (continuing anyway):', error);
            }

            // 4. HLS playlist URL を構築
            // 新しい session_id と cache_key を使用してダウンロード
            const session_id = crypto.randomUUID().split('-')[0];
            const cache_key = crypto.randomUUID().split('-')[0];
            const playlistUrl = this.buildPlaylistUrl(video_id, quality, use_hevc, session_id, cache_key);

            // 5. playlist を取得
            const playlistResponse = await APIClient.get<string>(playlistUrl.replace(Utils.api_base_url, ''), {
                responseType: 'text',
            });
            if (playlistResponse.type === 'error') {
                console.error('[OfflineDownload] Failed to fetch playlist:', playlistResponse.status);
                return false;
            }

            // 6. playlist のテキストを取得してパース
            const playlistText = playlistResponse.data;

            // 7. playlist を解析して全セグメント URL を取得
            const segmentUrls = this.parseHLSPlaylistFromText(playlistText, playlistUrl);

            if (segmentUrls.length === 0) {
                console.error('[OfflineDownload] No segments found in playlist');
                return false;
            }

            // 8. playlist 自体をキャッシュ
            // IMPORTANT: session_id を含まない正規化された URL をキャッシュキーとして使用
            // これにより、再生時に異なる session_id でアクセスしてもキャッシュから読み込める
            const normalizedPlaylistUrl = this.buildPlaylistUrl(video_id, quality, use_hevc);
            const relativePlaylistUrl = this.buildPlaylistRelativePath(video_id, quality, use_hevc);
            // Response を再構築してキャッシュ
            const playlistResponseForCache = new Response(playlistText, {
                status: 200,
                statusText: 'OK',
                headers: {
                    'Content-Type': 'application/vnd.apple.mpegurl',
                },
            });
            // 完整 URL でキャッシュ
            await cache.put(normalizedPlaylistUrl, playlistResponseForCache.clone());
            // 相対パスでもキャッシュ
            await cache.put(relativePlaylistUrl, playlistResponseForCache.clone());
            console.log(`[OfflineDownload] Cached playlist at normalized URL: ${normalizedPlaylistUrl}`);

            // 9. 既にキャッシュされているセグメント数を取得（断点続伝）
            const initialCachedCount = await this.getCachedSegmentsCount(video_id, quality, segmentUrls);
            console.log(`[OfflineDownload] ${initialCachedCount}/${segmentUrls.length} segments already cached`);

            // 9.1. total_segments を即座に更新（UI で 0/0 が表示されるのを防ぐ）
            await this.updateDownloadStatus(video_id, quality, {
                total_segments: segmentUrls.length,
                downloaded_segments: initialCachedCount > 0
                    ? [...Array(segmentUrls.length).keys()].filter(i => i < initialCachedCount)
                    : [],
            });

            // 10. 全セグメントを並発ダウンロード
            const downloadedCounts = { value: initialCachedCount };  // オブジェクトで包んで参照渡し

            // 初期進捗を報告
            if (onProgress) {
                onProgress(downloadedCounts.value, segmentUrls.length);
            }

            // ダウンロードキューを作成（未キャッシュのセグメントのみ）
            const downloadQueue: Array<{ index: number; url: string }> = [];
            for (let i = 0; i < segmentUrls.length; i++) {
                const segmentUrl = segmentUrls[i];

                // セグメント URL を正規化 (sequence のみ保持)
                let normalizedSegmentUrl = segmentUrl;
                try {
                    const url = new URL(segmentUrl);
                    const params = new URLSearchParams(url.search);
                    const sequence = params.get('sequence');
                    if (sequence !== null) {
                        url.search = `?sequence=${sequence}`;
                        normalizedSegmentUrl = url.toString();
                    }
                } catch (e) {
                    console.warn(`[OfflineDownload] Failed to normalize segment URL: ${segmentUrl}`, e);
                }

                // 既にキャッシュされているか確認（正規化 URL で）
                const cachedResponse = await cache.match(normalizedSegmentUrl);
                if (!cachedResponse) {
                    // キャッシュがない場合はダウンロードキューに追加
                    downloadQueue.push({ index: i, url: segmentUrl });
                } else {
                    // キャッシュが存在する場合、サイズをチェック（0 バイトの場合は再ダウンロード）
                    try {
                        const blob = await cachedResponse.blob();
                        if (blob.size === 0) {
                            console.warn(`[OfflineDownload] Segment ${i} is cached but empty (0 bytes), will re-download`);
                            downloadQueue.push({ index: i, url: segmentUrl });
                        }
                    } catch (e) {
                        console.warn(`[OfflineDownload] Failed to check cached segment ${i} size:`, e);
                        downloadQueue.push({ index: i, url: segmentUrl });
                    }
                }
            }

            console.log(`[OfflineDownload] ${downloadQueue.length} segments to download`);

            // 単一セッションでダウンロード
            const downloadSegment = async (queueItem: { index: number; url: string }) => {
                const { index, url: originalSegmentUrl } = queueItem;
                let currentSegmentUrl = originalSegmentUrl;

                // 中止シグナルをチェック
                if (abortSignal?.aborted) {
                    throw new Error('Download aborted by user');
                }

                // Playlist をリフレッシュする内部関数
                const refreshPlaylist = async (): Promise<boolean> => {
                    try {
                        console.log('[OfflineDownload] Refreshing session and playlist...');
                        // キャッシュから古い playlist を削除（SW が Cache First を使うため）
                        const cacheName = `konomitv-offline-video-${video_id}-${quality}`;
                        const cache = await caches.open(cacheName);
                        const oldPlaylistUrl = this.buildPlaylistUrl(video_id, quality, use_hevc);
                        await cache.delete(oldPlaylistUrl);

                        // 新しい session_id と cache_key を生成
                        const new_session_id = crypto.randomUUID().split('-')[0];
                        const new_cache_key = crypto.randomUUID().split('-')[0];
                        const newPlaylistUrl = this.buildPlaylistUrl(video_id, quality, use_hevc, new_session_id, new_cache_key);

                        // 新しい playlist を取得
                        const newPlaylistResponse = await APIClient.get<string>(
                            newPlaylistUrl.replace(Utils.api_base_url, ''),
                            {
                                responseType: 'text',
                                signal: abortSignal,
                            }
                        );

                        if (newPlaylistResponse.type === 'success') {
                            // Service Worker が自動的に新しい playlist をキャッシュする
                            const newSegmentUrls = this.parseHLSPlaylistFromText(newPlaylistResponse.data, newPlaylistUrl);
                            if (newSegmentUrls[index]) {
                                currentSegmentUrl = newSegmentUrls[index];
                                console.log(`[OfflineDownload] Updated segment ${index + 1} URL with new session`);
                                return true;
                            } else {
                                console.warn(`[OfflineDownload] New playlist does not contain segment ${index + 1}`);
                            }
                        } else {
                            console.warn(`[OfflineDownload] Failed to refresh playlist: ${newPlaylistResponse.status}`);
                        }
                        return false;
                    } catch (error) {
                        console.warn('[OfflineDownload] Error refreshing session:', error);
                        return false;
                    }
                };

                // セグメントをダウンロード
                // 最大9回リトライ、失敗時は5秒待機
                // 第3回と第6回のリトライ後に新しい session を取得
                console.log(`[OfflineDownload] Downloading segment ${index + 1}/${segmentUrls.length}`);
                let segmentBlob: Blob | null = null;
                let lastError: Error | null = null;

                for (let retry = 0; retry < 9; retry++) {
                    // 中止シグナルをチェック
                    if (abortSignal?.aborted) {
                        throw new Error('Download aborted by user');
                    }

                    try {
                        if (retry > 0) {
                            console.log(`[OfflineDownload] Retrying segment ${index + 1} (attempt ${retry + 1}/9)...`);
                            // 5秒待機
                            await new Promise(resolve => setTimeout(resolve, 5000));

                            // 待機後も中止シグナルをチェック
                            if (abortSignal?.aborted) {
                                throw new Error('Download aborted by user');
                            }
                        }

                        // 第3回と第6回のリトライ時に定期的に playlist をリフレッシュ
                        if (retry === 3 || retry === 6) {
                            console.log(`[OfflineDownload] Attempt ${retry + 1}: Periodic playlist refresh`);
                            await refreshPlaylist();
                        }

                        // Segment をダウンロード（タイムアウト 20 秒）
                        const segmentResponse = await APIClient.get<Blob>(currentSegmentUrl, {
                            responseType: 'blob',
                            timeout: 20 * 1000, // 20秒タイムアウト（セグメントサイズ 10-15MB を考慮）
                            signal: abortSignal,
                        });

                        if (segmentResponse.type === 'success') {
                            const responseBlob = segmentResponse.data;

                            // Blob が null または size が 0 の場合はリトライ
                            if (!responseBlob || responseBlob.size === 0) {
                                lastError = new Error('Received empty or null blob');
                                console.warn(`[OfflineDownload] ⚠️ Segment ${index + 1} has empty or null blob (size: ${responseBlob?.size || 'null'}), will retry. URL: ${currentSegmentUrl}`);
                                continue; // リトライ
                            }

                            // 有効な blob を取得した場合のみ成功とする
                            segmentBlob = responseBlob;
                            console.log(`[OfflineDownload] Segment ${index + 1} response: status=${segmentResponse.status}, size=${segmentBlob.size} bytes`);
                            break; // 成功したらループを抜ける
                        } else {
                            lastError = new Error(`HTTP ${segmentResponse.status}`);
                            console.warn(`[OfflineDownload] Segment ${index + 1} download failed with status ${segmentResponse.status}`);

                            // 404エラーの場合は即座に playlist をリフレッシュして再試行
                            if (segmentResponse.status === 404) {
                                console.log('[OfflineDownload] 404 detected (session revoked), refreshing playlist immediately');
                                const refreshed = await refreshPlaylist();
                                if (refreshed) {
                                    // リフレッシュ成功、新しい URL で即座に再試行
                                    console.log('[OfflineDownload] Retrying immediately with new session');
                                    try {
                                        const retryResponse = await APIClient.get<Blob>(currentSegmentUrl, {
                                            responseType: 'blob',
                                            timeout: 20 * 1000,
                                            signal: abortSignal,
                                        });
                                        if (retryResponse.type === 'success' && retryResponse.data && retryResponse.data.size > 0) {
                                            segmentBlob = retryResponse.data;
                                            console.log(`[OfflineDownload] Immediate retry after 404 successful, size: ${segmentBlob.size} bytes`);
                                            break; // 成功、ループを抜ける
                                        } else {
                                            console.warn('[OfflineDownload] Immediate retry failed, continuing normal retry flow');
                                        }
                                    } catch (error) {
                                        console.warn('[OfflineDownload] Immediate retry after 404 failed:', error);
                                    }
                                }
                                // リフレッシュ失敗または即座の再試行が失敗した場合、通常のリトライフローを続行
                            }
                        }
                    } catch (error) {
                        lastError = error as Error;
                        console.warn(`[OfflineDownload] Segment ${index + 1} download failed:`, error);
                    }
                }

                if (!segmentBlob) {
                    console.error(`[OfflineDownload] Failed to download segment ${index + 1} after 9 attempts:`, lastError);
                    throw new Error(`Failed to download segment ${index + 1}: ${lastError?.message || 'Unknown error'}`);
                }

                // セグメントのダウンロード完了（Service Worker が自動的にキャッシュします）
                console.log(`[OfflineDownload] Segment ${index + 1}/${segmentUrls.length} downloaded, size: ${segmentBlob.size} bytes`);
                downloadedCounts.value++;

                // メタデータを更新（ダウンロード済みセグメントを記録、状態は書き込まない）
                await this.updateDownloadStatus(video_id, quality, {
                    total_segments: segmentUrls.length,
                    downloaded_segments: [...Array(segmentUrls.length).keys()].filter(i => {
                        // 既にダウンロードされているセグメントのインデックスを記録
                        return i < downloadedCounts.value || downloadQueue.findIndex(q => q.index === i) === -1;
                    }),
                });

                // 進捗コールバックを呼び出し
                if (onProgress) {
                    onProgress(downloadedCounts.value, segmentUrls.length);
                }
            };

            // 順次ダウンロード
            for (const queueItem of downloadQueue) {
                await downloadSegment(queueItem);

                // 進捗をチェックし、目標パーセンテージに達したら停止
                const currentProgress = Math.round((downloadedCounts.value / segmentUrls.length) * 100);
                if (currentProgress >= targetDownloadPercentage) {
                    console.log(`[OfflineDownload] Reached target download percentage ${targetDownloadPercentage}%, stopping download`);
                    break;
                }
            }

            // ダウンロード完了：メタデータを更新（完了状態のみ書き込む）
            // 既にダウンロードされたセグメントのインデックスを記録
            const downloadedIndices: number[] = [];
            for (let i = 0; i < segmentUrls.length; i++) {
                const segmentUrl = segmentUrls[i];
                let normalizedSegmentUrl = segmentUrl;
                try {
                    const url = new URL(segmentUrl);
                    const params = new URLSearchParams(url.search);
                    const sequence = params.get('sequence');
                    if (sequence !== null) {
                        url.search = `?sequence=${sequence}`;
                        normalizedSegmentUrl = url.toString();
                    }
                } catch (e) {
                    // ignore
                }
                const cachedResponse = await cache.match(normalizedSegmentUrl);
                if (cachedResponse) {
                    downloadedIndices.push(i);
                }
            }

            await this.updateDownloadStatus(video_id, quality, {
                total_segments: segmentUrls.length,
                downloaded_segments: downloadedIndices,
                status: 'completed',
            });

            console.log(`[OfflineDownload] Successfully downloaded video ${video_id} (${downloadedCounts.value}/${segmentUrls.length} segments = ${Math.round((downloadedCounts.value / segmentUrls.length) * 100)}%)`);
            return true;

        } catch (error) {
            console.error('[OfflineDownload] Failed to download video:', error);

            // ユーザーによる中止またはロック取得失敗の場合は、状態を書き込まずにエラーを再スロー
            if (error instanceof Error &&
                (error.message === 'Download aborted by user' || error.name === 'DownloadLockError')) {
                throw error;
            }

            // 実際のエラーの場合のみ失敗状態を書き込む
            await this.updateDownloadStatus(video_id, quality, {
                status: 'failed',
            });

            return false;
        } finally {
            // ハートビートタイマーを停止
            if (heartbeatTimer !== null) {
                clearInterval(heartbeatTimer);
            }

            // ダウンロードロックを解放
            await this.releaseDownloadLock(video_id, quality, page_id);

            // Service Worker に通知して tracker を削除
            if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                navigator.serviceWorker.controller.postMessage({
                    type: 'STOP_DOWNLOAD',
                    videoId: video_id,
                    quality: quality,
                });
                console.log(`[OfflineDownload] Notified Service Worker to stop tracking download for video ${video_id} (${quality})`);
            }
        }
    }

    /**
     * ビデオがダウンロード済みでキャッシュされているかチェックする
     * Cache 名が存在するだけでなく、中身（playlist）があることも確認する
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @returns キャッシュされている場合は true
     */
    static async isVideoCached(video_id: number, quality: string): Promise<boolean> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            const cacheNames = await caches.keys();

            // Cache 名が存在しない場合は false
            if (!cacheNames.includes(cacheName)) {
                return false;
            }

            // Cache が存在する場合、中身を確認
            const cache = await caches.open(cacheName);
            const keys = await cache.keys();

            // Cache が空の場合は false
            if (keys.length === 0) {
                console.warn(`[OfflineDownload] Cache ${cacheName} exists but is empty, cleaning up...`);
                // 空の cache を削除
                await caches.delete(cacheName);
                return false;
            }

            // playlist が存在するか確認
            const hevcPlaylistUrl = this.buildPlaylistRelativePath(video_id, quality, true);
            const h264PlaylistUrl = this.buildPlaylistRelativePath(video_id, quality, false);

            const hevcPlaylist = await cache.match(hevcPlaylistUrl);
            const h264Playlist = await cache.match(h264PlaylistUrl);

            // いずれかの playlist が存在すれば true
            return !!(hevcPlaylist || h264Playlist);
        } catch (error) {
            console.error('[OfflineDownload] Failed to check if video is cached:', error);
            return false;
        }
    }

    /**
     * キャッシュから指定 URL のリソースを取得する
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param url リクエスト URL
     * @returns キャッシュされたレスポンス、存在しない場合は null
     */
    static async getCachedResponse(video_id: number, quality: string, url: string): Promise<Response | null> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            console.log(`[OfflineDownload] Looking for ${url} in cache: ${cacheName}`);
            const cache = await caches.open(cacheName);
            let cachedResponse = await cache.match(url);

            // 専用キャッシュで見つからない場合、全キャッシュから検索
            if (!cachedResponse) {
                console.log('[OfflineDownload] Not found in dedicated cache, searching all caches...');
                cachedResponse = await caches.match(url);
            }

            console.log('[OfflineDownload] Cache match result:', cachedResponse ? 'Found' : 'Not found');
            return cachedResponse || null;
        } catch (error) {
            console.error(`[OfflineDownload] Failed to get cached response for ${url}:`, error);
            return null;
        }
    }


    /**
     * キャッシュされたビデオを削除する（全エントリ/index を含む）
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @returns 削除に成功した場合は true
     */
    static async deleteVideo(video_id: number, quality: string): Promise<boolean> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            const cacheNames = await caches.keys();

            // Cache が存在しない場合は既に削除済み
            if (!cacheNames.includes(cacheName)) {
                console.log(`[OfflineDownload] Cache ${cacheName} does not exist, nothing to delete`);
                return true; // 既に削除済みの場合は成功とみなす
            }

            // Cache 全体を削除（全エントリ/index、メタデータを含む）
            const result = await caches.delete(cacheName);

            if (result) {
                console.log(`[OfflineDownload] Successfully deleted cache ${cacheName} with all its contents (including metadata)`);
            } else {
                console.warn(`[OfflineDownload] Failed to delete cache ${cacheName}`);
            }

            return result;
        } catch (error) {
            console.error('[OfflineDownload] Failed to delete cached video:', error);
            return false;
        }
    }

    /**
     * キャッシュされた全ビデオの一覧を取得する
     * @returns キャッシュされたビデオのキャッシュ名一覧
     */
    static async getCachedVideos(): Promise<string[]> {
        const cacheNames = await caches.keys();
        return cacheNames.filter(name => name.startsWith(this.CACHE_PREFIX));
    }

    /**
     * キャッシュされた全ビデオの詳細情報を取得する
     * Cache Storage から直接データを読み取り、IOfflineVideo 形式で返す
     * @returns キャッシュされたビデオの詳細情報一覧
     */
    static async getCachedVideosInfo(): Promise<IOfflineVideo[]> {
        const cacheNames = await this.getCachedVideos();
        const videos: IOfflineVideo[] = [];

        for (const cacheName of cacheNames) {
            // キャッシュ名から video_id, quality を抽出
            // 例: "konomitv-offline-video-123-1080p" -> video_id=123, quality=1080p
            const match = cacheName.match(new RegExp(`^${this.CACHE_PREFIX}(\\d+)-(.+)$`));
            if (!match) {
                console.warn(`[OfflineDownload] Invalid cache name format: ${cacheName}`);
                continue;
            }

            const video_id = parseInt(match[1], 10);
            const quality = match[2];

            try {
                const cache = await caches.open(cacheName);

                // メタデータを取得
                let title = `Video ${video_id}`;
                const metadataUrl = `/api/videos/${video_id}`;
                const metadataResponse = await cache.match(metadataUrl);
                if (metadataResponse) {
                    try {
                        const metadata = await metadataResponse.json();
                        title = metadata.title || title;
                    } catch (e) {
                        console.warn(`[OfflineDownload] Failed to parse metadata for video ${video_id}:`, e);
                    }
                }

                // ダウンロードステータスメタデータから情報を取得
                let total_segments = 0;
                let downloaded_segments = 0;
                let status: OfflineDownloadStatus = 'completed';
                let progress = 100;
                let is_hevc = false;
                let playlistText: string | null = null;

                const downloadStatus = await this.getDownloadStatus(video_id, quality);
                if (downloadStatus) {
                    // メタデータから is_hevc を読み取る（undefined の場合は fallback detection）
                    if (downloadStatus.is_hevc !== undefined) {
                        is_hevc = downloadStatus.is_hevc;
                        console.log(`[OfflineDownload] HEVC flag from metadata for video ${video_id}: ${is_hevc}`);
                    } else {
                        // 古いメタデータの場合は playlist から判定
                        console.log(`[OfflineDownload] HEVC flag undefined in metadata for video ${video_id}, using fallback detection`);
                        const hevcPlaylistUrl = this.buildPlaylistRelativePath(video_id, quality, true);
                        const hevcPlaylistResponse = await cache.match(hevcPlaylistUrl);
                        if (hevcPlaylistResponse) {
                            is_hevc = true;
                            console.log(`[OfflineDownload] Detected HEVC playlist for video ${video_id}`);
                        } else {
                            is_hevc = false;
                            console.log(`[OfflineDownload] Detected H.264 playlist for video ${video_id}`);
                        }
                        // メタデータを更新して次回のため保存
                        await this.updateDownloadStatus(video_id, quality, {
                            is_hevc: is_hevc,
                        });
                    }
                    // メタデータが存在する場合はそこから読み取る
                    total_segments = downloadStatus.total_segments;
                    downloaded_segments = downloadStatus.downloaded_segments.length;
                    progress = total_segments > 0 ? Math.floor((downloaded_segments / total_segments) * 100) : 0;

                    // 状態判定：
                    // - completed/failed はメタデータから読み取る
                    // - それ以外は進捗から判定（downloading は存在しないはず、常に paused として扱う）
                    if (downloadStatus.status === 'completed' || downloadStatus.status === 'failed') {
                        status = downloadStatus.status;
                    } else {
                        // メタデータに completed/failed 以外の状態がある場合は paused として扱う
                        status = progress === 100 ? 'completed' : 'paused';
                    }

                    // ロックのクリーンアップ
                    const now = Date.now();
                    const LOCK_TIMEOUT = 10 * 1000; // 10秒
                    if (downloadStatus.lock.locked && (now - downloadStatus.lock.timestamp > LOCK_TIMEOUT)) {
                        console.log(`[OfflineDownload] Video ${video_id}: Lock expired, releasing lock`);
                        await this.updateDownloadStatus(video_id, quality, {
                            lock: {
                                locked: false,
                                page_id: '',
                                timestamp: 0,
                            },
                        });
                    }

                    console.log(`[OfflineDownload] Video ${video_id}: ${downloaded_segments}/${total_segments} segments, status: ${status} (from metadata)`);
                } else {
                    // メタデータが存在しない場合は後方互換性のため playlist から HEVC を判定
                    console.log(`[OfflineDownload] No metadata found for video ${video_id}, using fallback detection`);
                    const hevcPlaylistUrl = this.buildPlaylistRelativePath(video_id, quality, true);
                    const h264PlaylistUrl = this.buildPlaylistRelativePath(video_id, quality, false);

                    const hevcPlaylistResponse = await cache.match(hevcPlaylistUrl);
                    if (hevcPlaylistResponse) {
                        is_hevc = true;
                        playlistText = await hevcPlaylistResponse.text();
                        console.log(`[OfflineDownload] Found HEVC playlist for video ${video_id}`);
                    } else {
                        const h264PlaylistResponse = await cache.match(h264PlaylistUrl);
                        if (h264PlaylistResponse) {
                            is_hevc = false;
                            playlistText = await h264PlaylistResponse.text();
                            console.log(`[OfflineDownload] Found H.264 playlist for video ${video_id}`);
                        }
                    }

                    if (playlistText) {
                        // 従来の方法でカウント
                        const baseUrl = `${Utils.api_base_url}/streams/video/${video_id}/${this.getQualityWithCodec(quality, is_hevc)}/`;
                        const segmentUrls = this.parseHLSPlaylistFromText(playlistText, baseUrl);
                        total_segments = segmentUrls.length;

                        // Cache 内のセグメント URL をカウント
                        const requests = await cache.keys();
                        for (const request of requests) {
                            const url = request.url;
                            if (url.includes('/segment')) {
                                downloaded_segments++;
                            }
                        }
                        console.log(`[OfflineDownload] Video ${video_id}: ${downloaded_segments}/${total_segments} segments (counted from cache)`);
                    }
                }

                // キャッシュサイズを計算
                const total_size = await this.getCachedVideoSize(video_id, quality) || 0;

                // キャッシュの作成日時を取得（最初のエントリーの Date ヘッダーから推定）
                const requests = await cache.keys();
                let created_at = Date.now();
                if (requests.length > 0) {
                    const firstResponse = await cache.match(requests[0]);
                    if (firstResponse) {
                        const dateHeader = firstResponse.headers.get('Date');
                        if (dateHeader) {
                            created_at = new Date(dateHeader).getTime();
                        }
                    }
                }

                videos.push({
                    video_id,
                    title,
                    quality,
                    is_hevc,
                    status,
                    progress,
                    downloaded_segments,
                    total_segments,
                    total_size,
                    downloaded_size: total_size,
                    created_at,
                    updated_at: created_at,
                    cache_name: cacheName,
                });
            } catch (error) {
                console.error(`[OfflineDownload] Failed to get info for ${cacheName}:`, error);
            }
        }

        return videos;
    }

    /**
     * キャッシュされたビデオが占有するストレージ容量を計算する (概算値)
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @returns 占有バイト数、計算できない場合は null
     */
    static async getCachedVideoSize(video_id: number, quality: string): Promise<number | null> {
        try {
            const cacheName = this.getCacheName(video_id, quality);
            const cache = await caches.open(cacheName);
            const requests = await cache.keys();

            let totalSize = 0;
            for (const request of requests) {
                const response = await cache.match(request);
                if (response && response.body) {
                    // 尝试从 Content-Length header 获取大小
                    const contentLength = response.headers.get('Content-Length');
                    if (contentLength) {
                        totalSize += parseInt(contentLength, 10);
                    }
                }
            }

            return totalSize > 0 ? totalSize : null;
        } catch (error) {
            console.error('[OfflineDownload] Failed to calculate cached video size:', error);
            return null;
        }
    }
}

export default OfflineDownload;