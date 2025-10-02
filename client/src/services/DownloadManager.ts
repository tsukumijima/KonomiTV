import { ref } from 'vue';

import Message from '@/message';
import OfflineDownload from '@/services/OfflineDownload';
import Utils from '@/utils';

/** ダウンロードタスクの状態 */
export type DownloadTaskStatus = 'pending' | 'downloading' | 'completed' | 'failed' | 'paused';

/** ダウンロードタスク */
export interface IDownloadTask {
    video_id: number;
    title: string;
    quality: string;
    is_hevc: boolean; // HEVC (H.265) でダウンロードするかどうか
    status: DownloadTaskStatus;
    progress: number; // 0-100
    downloaded_segments: number;
    total_segments: number;
    total_size: number; // 推定サイズ (bytes)
    downloaded_size: number; // ダウンロード済みサイズ (bytes)
    thumbnail_url: string;
    created_at: number;
    updated_at: number;
    error_message?: string;
}

/**
 * 全てのオフラインダウンロードタスクを管理するグローバルマネージャー
 * シングルトンパターンで実装し、アプリケーション全体で1つのインスタンスのみ存在する
 */
class DownloadManager {
    // シングルトンインスタンス
    private static instance: DownloadManager | null = null;

    // リアクティブなダウンロードタスクのマップ (video_id-quality をキーとする)
    // ref を使って手動でトリガーできるようにする
    private tasksMap = new Map<string, IDownloadTask>();
    public tasks = ref(new Map<string, IDownloadTask>());

    // 現在ダウンロード中のタスク (Promise を保持して await できるようにする)
    private activeDownloads = new Map<string, Promise<boolean>>();

    // ダウンロード中止用の AbortController マップ
    private abortControllers = new Map<string, AbortController>();

    // ストレージ更新コールバック（OfflineVideos ページなどで使用）
    public onStorageUpdate: (() => void) | null = null;

    // このページの一意な ID（ダウンロードロック用）
    private readonly pageId: string;

    private constructor() {
        // private constructor でシングルトンを保証
        // ページ固有の ID を生成（ダウンロードロック用）
        this.pageId = crypto.randomUUID();
        console.log(`[DownloadManager] Initialized with page ID: ${this.pageId}`);
    }

    /**
     * シングルトンインスタンスを取得
     */
    static getInstance(): DownloadManager {
        if (!DownloadManager.instance) {
            DownloadManager.instance = new DownloadManager();
        }
        return DownloadManager.instance;
    }

    /**
     * タスクのキーを生成
     */
    private getTaskKey(video_id: number, quality: string): string {
        return `${video_id}-${quality}`;
    }

    /**
     * ダウンロードタスクを開始
     * @param video_id 録画番組 ID
     * @param quality 画質
     * @param title 番組タイトル
     * @param use_hevc HEVC (H.265) でダウンロードするかどうか
     * @returns ダウンロードが成功したかどうか
     */
    async startDownload(
        video_id: number,
        quality: string,
        title: string,
        use_hevc: boolean,
    ): Promise<boolean> {
        const taskKey = this.getTaskKey(video_id, quality);

        // 既にダウンロード中の場合は既存の Promise を返す
        if (this.activeDownloads.has(taskKey)) {
            console.log(`[DownloadManager] Task ${taskKey} is already downloading`);
            return this.activeDownloads.get(taskKey)!;
        }

        // 既に完了している場合はスキップ
        const existingTask = this.tasksMap.get(taskKey);
        if (existingTask && existingTask.status === 'completed') {
            Message.info('この動画は既にダウンロード済みです。');
            return true;
        }

        // 新規タスクまたは失敗/中断したタスクの再開
        const now = Date.now();
        const task: IDownloadTask = existingTask || {
            video_id,
            title,
            quality,
            is_hevc: use_hevc,
            status: 'pending',
            progress: 0,
            downloaded_segments: 0,
            total_segments: 0,
            total_size: 0,
            downloaded_size: 0,
            thumbnail_url: `${Utils.api_base_url}/videos/${video_id}/thumbnail`,
            created_at: now,
            updated_at: now,
        };

        // タスクをマップに追加し、reactive を更新
        this.tasksMap.set(taskKey, task);
        this.tasks.value = new Map(this.tasksMap);

        // AbortController を作成
        const abortController = new AbortController();
        this.abortControllers.set(taskKey, abortController);

        // ダウンロードを開始
        const downloadPromise = this.executeDownload(task, abortController.signal);
        this.activeDownloads.set(taskKey, downloadPromise);

        // ダウンロード完了後にアクティブダウンロードから削除
        downloadPromise.finally(() => {
            this.activeDownloads.delete(taskKey);
            this.abortControllers.delete(taskKey);
        });

        return downloadPromise;
    }

    /**
     * ダウンロードタスクを実行
     */
    private async executeDownload(
        task: IDownloadTask,
        abortSignal: AbortSignal,
    ): Promise<boolean> {
        const taskKey = this.getTaskKey(task.video_id, task.quality);

        try {
            task.status = 'downloading';
            task.updated_at = Date.now();
            this.triggerUpdate();

            // 永続的なストレージの権限をリクエスト
            await OfflineDownload.requestPersistentStorage();

            // ストレージ配額をチェック
            const quota = await OfflineDownload.getStorageQuota();
            if (quota) {
                const MINIMUM_FREE_SPACE = 5 * 1024 * 1024 * 1024; // 5GB
                if (quota.available < MINIMUM_FREE_SPACE) {
                    console.warn(`[DownloadManager] Low storage space: ${Utils.formatBytes(quota.available)}`);
                }
            }

            // ダウンロードを実行（page_id を渡してダウンロードロックを取得）
            const success = await OfflineDownload.downloadVideo(
                task.video_id,
                task.quality,
                task.is_hevc,
                this.pageId, // ページ固有の ID を渡す
                (downloaded: number, total: number) => {
                    // 進捗を更新
                    task.downloaded_segments = downloaded;
                    task.total_segments = total;
                    task.progress = Math.round((downloaded / total) * 100);
                    task.updated_at = Date.now();

                    // Vue の reactive を更新
                    this.triggerUpdate();

                    // ストレージ使用量を更新（頻繁に実行しないよう、10%ごとに更新）
                    if ((task.progress % 10 === 0 || task.progress === 100) && this.onStorageUpdate) {
                        this.onStorageUpdate();
                    }
                },
                abortSignal, // 中止シグナルを渡す
            );

            if (success) {
                // ダウンロード完了
                task.status = 'completed';
                task.progress = 100;
                task.updated_at = Date.now();

                // キャッシュサイズを取得
                const cachedSize = await OfflineDownload.getCachedVideoSize(task.video_id, task.quality);
                task.total_size = cachedSize || 0;
                task.downloaded_size = cachedSize || 0;

                this.triggerUpdate();
                Message.success('オフライン視聴用のダウンロードが完了しました。');

                return true;
            } else {
                // ダウンロード失敗
                task.status = 'failed';
                task.error_message = 'ダウンロードに失敗しました';
                task.updated_at = Date.now();
                this.triggerUpdate();
                Message.error('オフライン視聴用のダウンロードに失敗しました。');

                return false;
            }
        } catch (error) {
            console.error(`[DownloadManager] Failed to download task ${taskKey}:`, error);

            // ロック取得失敗の場合は特別な処理
            if (error instanceof Error && error.name === 'DownloadLockError') {
                task.status = 'paused';
                task.updated_at = Date.now();
                this.triggerUpdate();
                Message.warning(error.message);
                return false;
            }

            // ダウンロード中止の場合は paused として扱う
            if (error instanceof Error && error.message === 'Download aborted by user') {
                task.status = 'paused';
                task.updated_at = Date.now();
                this.triggerUpdate();
                console.log(`[DownloadManager] Task ${taskKey} was paused by user`);
                return false;
            }

            // その他のエラー
            task.status = 'failed';
            task.error_message = error instanceof Error ? error.message : 'Unknown error';
            task.updated_at = Date.now();
            this.triggerUpdate();
            Message.error(`オフライン視聴用のダウンロード中にエラーが発生しました: ${task.error_message}`);

            return false;
        }
    }

    /**
     * ダウンロードタスクを一時停止
     * ダウンロードを中止し、ロックを解放します
     * 次回再開時に断点続伝が行われます
     */
    async pauseDownload(video_id: number, quality: string): Promise<void> {
        const taskKey = this.getTaskKey(video_id, quality);
        const task = this.tasksMap.get(taskKey);

        if (task && task.status === 'downloading') {
            // AbortController を使ってダウンロードを中止
            const abortController = this.abortControllers.get(taskKey);
            if (abortController) {
                console.log(`[DownloadManager] Aborting download task ${taskKey}`);
                abortController.abort();
                Message.info('ダウンロードを一時停止しました（断点続伝をサポート）。');
            }
        }
    }

    /**
     * ダウンロードタスクを再開
     */
    async resumeDownload(video_id: number, quality: string): Promise<boolean> {
        const taskKey = this.getTaskKey(video_id, quality);
        const task = this.tasksMap.get(taskKey);

        if (task && (task.status === 'paused' || task.status === 'failed')) {
            Message.info('ダウンロードを再開します（断点続伝）。');
            return this.startDownload(video_id, quality, task.title, task.is_hevc);
        }

        return false;
    }

    /**
     * ダウンロードタスクを削除
     */
    async deleteDownload(video_id: number, quality: string): Promise<boolean> {
        const taskKey = this.getTaskKey(video_id, quality);

        // キャッシュを削除
        const success = await OfflineDownload.deleteVideo(video_id, quality);

        if (success) {
            // タスクを削除
            this.tasksMap.delete(taskKey);
            this.triggerUpdate();

            Message.success('オフライン視聴用の動画を削除しました。');
            return true;
        }

        Message.error('動画の削除に失敗しました。');
        return false;
    }

    /**
     * すべてのタスクを取得
     */
    getAllTasks(): IDownloadTask[] {
        return Array.from(this.tasks.value.values());
    }

    /**
     * 特定のダウンロードタスクを取得
     */
    getTask(video_id: number, quality: string): IDownloadTask | undefined {
        const taskKey = this.getTaskKey(video_id, quality);
        return this.tasksMap.get(taskKey);
    }

    /**
     * ダウンロード中のタスクを取得
     */
    getActiveDownloads(): IDownloadTask[] {
        return Array.from(this.tasks.value.values()).filter(task => task.status === 'downloading');
    }

    /**
     * Vue の reactive を手動で更新
     */
    private triggerUpdate(): void {
        this.tasks.value = new Map(this.tasksMap);
    }

    /**
     * ダウンロード中のタスクがあるかチェック
     */
    hasActiveDownloads(): boolean {
        return this.getActiveDownloads().length > 0;
    }

    /**
     * すべてのダウンロードロックを解放（ページクローズ時に呼び出す）
     */
    async releaseAllLocks(): Promise<void> {
        const tasks = this.getAllTasks();
        const releasePromises = tasks.map(task =>
            OfflineDownload.releaseDownloadLock(task.video_id, task.quality, this.pageId)
        );
        await Promise.all(releasePromises);
        console.log(`[DownloadManager] Released all locks for page ${this.pageId}`);
    }

    /**
     * 全体の進捗を計算（すべてのダウンロード中タスクの平均）
     */
    getTotalProgress(): number {
        const activeDownloads = this.getActiveDownloads();
        if (activeDownloads.length === 0) {
            return 0;
        }

        const totalProgress = activeDownloads.reduce((sum, task) => sum + task.progress, 0);
        return Math.round(totalProgress / activeDownloads.length);
    }


    /**
     * Cache Storage から完了済みタスクを復元
     */
    async restoreFromCacheStorage(): Promise<void> {
        try {
            const cachedVideos = await OfflineDownload.getCachedVideosInfo();

            for (const videoInfo of cachedVideos) {
                const taskKey = this.getTaskKey(videoInfo.video_id, videoInfo.quality);

                // 既にタスクが存在する場合はスキップ（ダウンロード中のタスクを優先）
                if (this.tasksMap.has(taskKey)) {
                    continue;
                }

                const task: IDownloadTask = {
                    video_id: videoInfo.video_id,
                    title: videoInfo.title,
                    quality: videoInfo.quality,
                    is_hevc: videoInfo.is_hevc,
                    status: videoInfo.status,
                    progress: videoInfo.progress,
                    downloaded_segments: videoInfo.downloaded_segments,
                    total_segments: videoInfo.total_segments,
                    total_size: videoInfo.total_size,
                    downloaded_size: videoInfo.downloaded_size,
                    thumbnail_url: `${Utils.api_base_url}/videos/${videoInfo.video_id}/thumbnail`,
                    created_at: videoInfo.created_at,
                    updated_at: videoInfo.updated_at,
                };

                this.tasksMap.set(taskKey, task);
            }

            this.triggerUpdate();
            console.log(`[DownloadManager] Restored ${this.tasksMap.size} tasks from Cache Storage`);
        } catch (error) {
            console.error('[DownloadManager] Failed to restore from Cache Storage:', error);
        }
    }
}

// シングルトンインスタンスをエクスポート
export default DownloadManager.getInstance();