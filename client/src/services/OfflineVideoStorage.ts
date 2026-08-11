import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

import type { IOfflineDownloadJob, IOfflineVideo } from '@/services/OfflineVideos';


/** オフライン保存用 IndexedDB の型付きスキーマ */
interface IOfflineVideoDB extends DBSchema {
    videos: {
        key: number;
        value: IOfflineVideo;
    };
    jobs: {
        key: string;
        value: IOfflineDownloadJob;
    };
}

/**
 * オフライン動画の IndexedDB と CacheStorage を一括して管理する。
 */
export default class OfflineVideoStorage {

    static readonly eventTarget = new EventTarget();

    private static readonly DB_NAME = 'KonomiTV-OfflineVideos';
    private static readonly DB_VERSION = 1;
    private static readonly VIDEO_STORE_NAME = 'videos';
    private static readonly JOB_STORE_NAME = 'jobs';
    private static readonly CACHE_NAME = 'KonomiTV-OfflineVideos';
    private static databasePromise: Promise<IDBPDatabase<IOfflineVideoDB>> | null = null;

    /**
     * 保存日時が新しい順に、欠損のない保存済み動画を取得する。
     * @returns 保存済み動画一覧
     */
    static async getVideos(): Promise<IOfflineVideo[]> {

        const database = await this.openDatabase();
        const videos = await database.getAll(this.VIDEO_STORE_NAME);
        const cache = await this.openCache();
        const cachedRequestURLs = (await cache.keys()).map(request => request.url);
        const validVideos: IOfflineVideo[] = [];

        // IndexedDB だけ残った不完全な世代は一覧へ出さず、同じ世代の保存断片も回収する
        for (const video of videos) {
            if (this.isVideoCacheComplete(video, cachedRequestURLs) === true) {
                validVideos.push(video);
            } else {
                await this.deleteIncompleteVideo(video);
            }
        }

        // オフライン保存ページでは最後に保存した番組を先頭へ表示する
        await this.cleanupOrphanedGenerations();
        return validVideos.sort((first, second) => second.saved_at - first.saved_at);
    }

    /**
     * 録画番組 ID に対応する、欠損のない保存済み動画を取得する。
     * @param videoID 録画番組 ID
     * @returns 保存済み動画（存在しない場合は null）
     */
    static async getVideo(videoID: number): Promise<IOfflineVideo | null> {

        const video = await this.getStoredVideo(videoID);
        if (video === null) return null;

        // 再生直前にも全セグメントを照合し、途中欠損したデータを hls.js へ渡さない
        const cache = await this.openCache();
        const cachedRequestURLs = (await cache.keys()).map(request => request.url);
        if (this.isVideoCacheComplete(video, cachedRequestURLs) === false) {
            const database = await this.openDatabase();
            await database.delete(this.VIDEO_STORE_NAME, video.video_id);
            await this.deleteGeneration(video.video_id, video.generation_id);
            this.eventTarget.dispatchEvent(new Event('change'));
            return null;
        }
        return video;
    }

    /**
     * 保存済み動画を欠損検査せず取得する。
     * @param videoID 録画番組 ID
     * @returns IndexedDB に記録された動画（存在しない場合は null）
     */
    static async getStoredVideo(videoID: number): Promise<IOfflineVideo | null> {

        const database = await this.openDatabase();
        return (await database.get(this.VIDEO_STORE_NAME, videoID)) ?? null;
    }

    /** 保存ジョブを取得する */
    static async getJobs(): Promise<IOfflineDownloadJob[]> {
        const database = await this.openDatabase();
        return await database.getAll(this.JOB_STORE_NAME);
    }

    /** 指定した保存ジョブを取得する */
    static async getJob(jobID: string): Promise<IOfflineDownloadJob | null> {
        const database = await this.openDatabase();
        return (await database.get(this.JOB_STORE_NAME, jobID)) ?? null;
    }

    /** 同じ録画番組の実行中ジョブがなければ、新しいジョブを追加する */
    static async putJobIfVideoIdle(job: IOfflineDownloadJob): Promise<void> {
        const database = await this.openDatabase();
        const transaction = database.transaction(this.JOB_STORE_NAME, 'readwrite');
        const jobs = await transaction.store.getAll();

        // 検査と追加を同じトランザクションへ入れ、別タブ同士の保存開始を直列化する
        if (jobs.some(existingJob => existingJob.video_id === job.video_id &&
            ['Waiting', 'Downloading', 'Finalizing'].includes(existingJob.state))) {
            await transaction.done;
            throw new Error('この録画番組はすでにオフライン保存中です。');
        }
        await transaction.store.put(job);
        await transaction.done;
        this.eventTarget.dispatchEvent(new Event('change'));
    }

    /** 実行中のジョブだけを更新する */
    static async updateActiveJob(job: IOfflineDownloadJob): Promise<boolean> {
        const database = await this.openDatabase();
        const transaction = database.transaction(this.JOB_STORE_NAME, 'readwrite');
        const latestJob = await transaction.store.get(job.job_id);

        // 確定済みの状態を、受信処理が保持する古い状態で上書きしない
        if (latestJob === undefined || ['Completed', 'Failed', 'Cancelled'].includes(latestJob.state)) {
            await transaction.done;
            return false;
        }
        await transaction.store.put(job);
        await transaction.done;
        this.eventTarget.dispatchEvent(new Event('change'));
        return true;
    }

    /** ジョブと有効な保存世代を同じトランザクションで完了させる */
    static async completeJob(job: IOfflineDownloadJob, video: IOfflineVideo): Promise<boolean> {
        const database = await this.openDatabase();
        const transaction = database.transaction([this.JOB_STORE_NAME, this.VIDEO_STORE_NAME], 'readwrite');
        const latestJob = await transaction.objectStore(this.JOB_STORE_NAME).get(job.job_id);

        // キャンセルや失敗が先に確定していれば、動画エントリを作らない
        if (latestJob === undefined || ['Completed', 'Failed', 'Cancelled'].includes(latestJob.state)) {
            await transaction.done;
            return false;
        }
        const completedJob: IOfflineDownloadJob = {
            ...latestJob,
            state: 'Completed',
            downloaded_bytes: video.size_bytes,
        };
        await transaction.objectStore(this.VIDEO_STORE_NAME).put(video);
        await transaction.objectStore(this.JOB_STORE_NAME).put(completedJob);
        await transaction.done;
        this.eventTarget.dispatchEvent(new Event('change'));
        return true;
    }

    /** 実行中の保存ジョブを失敗またはキャンセルへ遷移させる */
    static async transitionActiveJobToTerminalState(
        jobID: string,
        state: 'Failed' | 'Cancelled',
        error: string | null,
    ): Promise<IOfflineDownloadJob | null> {
        const database = await this.openDatabase();
        const transaction = database.transaction(this.JOB_STORE_NAME, 'readwrite');
        const job = await transaction.store.get(jobID);

        // 先に終端状態が確定していれば、後から到着した処理を無視する
        if (job === undefined || ['Completed', 'Failed', 'Cancelled'].includes(job.state)) {
            await transaction.done;
            return null;
        }
        job.state = state;
        job.error = error;
        await transaction.store.put(job);
        await transaction.done;
        this.eventTarget.dispatchEvent(new Event('change'));
        return job;
    }

    /** 動画と、その動画が参照する保存世代を削除する */
    static async deleteVideo(video: IOfflineVideo): Promise<void> {
        await this.deleteGeneration(video.video_id, video.generation_id);
        const database = await this.openDatabase();
        await database.delete(this.VIDEO_STORE_NAME, video.video_id);
        this.eventTarget.dispatchEvent(new Event('change'));
    }

    /** 終端状態の保存ジョブを IndexedDB から削除する */
    static async deleteJob(jobID: string): Promise<void> {
        const database = await this.openDatabase();
        await database.delete(this.JOB_STORE_NAME, jobID);
        this.eventTarget.dispatchEvent(new Event('change'));
    }

    /** 有効な保存世代と実行中ジョブから参照されない CacheStorage の断片を削除する */
    static async cleanupOrphanedGenerations(): Promise<void> {
        const database = await this.openDatabase();
        const [videos, jobs] = await Promise.all([
            database.getAll(this.VIDEO_STORE_NAME),
            database.getAll(this.JOB_STORE_NAME),
        ]);
        const cache = await this.openCache();
        const requests = await cache.keys();
        const generationKeys = new Set<string>();

        // CacheStorage 上の保存世代 URL から video_id / generation_id の組を回収する
        for (const request of requests) {
            const matched = request.url.match(/\/__offline__\/videos\/(\d+)\/([^/]+)\//);
            if (matched !== null) {
                generationKeys.add(`${matched[1]}:${matched[2]}`);
            }
        }

        await Promise.all([...generationKeys].map(async generationKey => {
            const separatorIndex = generationKey.indexOf(':');
            const videoID = Number(generationKey.slice(0, separatorIndex));
            const generationID = generationKey.slice(separatorIndex + 1);
            const savedVideo = videos.find(video => video.video_id === videoID && video.generation_id === generationID);
            const activeJob = jobs.find(job => job.video_id === videoID && job.generation_id === generationID &&
                ['Waiting', 'Downloading', 'Finalizing'].includes(job.state));
            if (savedVideo !== undefined || activeJob !== undefined) return;
            await this.deleteGeneration(videoID, generationID);
        }));
    }

    /** 指定した保存世代に属する CacheStorage のデータを削除する */
    static async deleteGeneration(videoID: number, generationID: string): Promise<void> {
        const cache = await this.openCache();
        const generationPrefix = `${self.location.origin}/__offline__/videos/${videoID}/${generationID}/`;
        const requests = await cache.keys();
        await Promise.all(requests
            .filter(request => request.url.startsWith(generationPrefix))
            .map(request => cache.delete(request)));
    }

    /** オフライン動画専用 CacheStorage を開く */
    static async openCache(): Promise<Cache> {
        return await caches.open(this.CACHE_NAME);
    }

    /** Service Worker から保存済み HLS と付随データを返す */
    static async getResponse(request: Request): Promise<Response> {
        const cache = await this.openCache();

        // hls.js のキャッシュ回避クエリを除き、保存時の URL 本体だけで照合する
        return (await cache.match(request, {ignoreSearch: true})) ??
            new Response('Offline video data was not found.', {status: 404});
    }

    /** 保存済み動画の HLS プレイリスト URL を返す */
    static getPlaylistURL(video: IOfflineVideo): string {
        return `${self.location.origin}/__offline__/videos/${video.video_id}/${video.generation_id}/playlist.m3u8`;
    }

    /** 保存済み動画に付随する画像・JSON の URL を返す */
    static getAssetURL(video: IOfflineVideo, assetName: 'thumbnail.webp' | 'thumbnail-tiled.webp' | 'channel-logo' | 'jikkyo.json'): string {
        return `${self.location.origin}/__offline__/videos/${video.video_id}/${video.generation_id}/assets/${assetName}`;
    }

    private static async openDatabase(): Promise<IDBPDatabase<IOfflineVideoDB>> {

        // 接続を使い回し、進捗更新のたびに IndexedDB 接続を開閉する負荷を避ける
        if (this.databasePromise === null) {
            const databasePromise = openDB<IOfflineVideoDB>(this.DB_NAME, this.DB_VERSION, {
                upgrade: (database) => {
                    if (database.objectStoreNames.contains(this.VIDEO_STORE_NAME) === false) {
                        database.createObjectStore(this.VIDEO_STORE_NAME, {keyPath: 'video_id'});
                    }
                    if (database.objectStoreNames.contains(this.JOB_STORE_NAME) === false) {
                        database.createObjectStore(this.JOB_STORE_NAME, {keyPath: 'job_id'});
                    }
                },
                blocking: () => {
                    // 別タブの新しい DB バージョンを妨げないよう、古い接続を閉じて次回の操作で開き直す
                    void databasePromise.then(database => database.close());
                    if (this.databasePromise === databasePromise) {
                        this.databasePromise = null;
                    }
                },
                terminated: () => {
                    // ブラウザに強制終了された接続を再利用せず、次の操作で新しい接続を取得する
                    if (this.databasePromise === databasePromise) {
                        this.databasePromise = null;
                    }
                },
            });
            this.databasePromise = databasePromise;

            // 一時的なストレージ障害から回復した後は、次の操作で IndexedDB 接続を開き直す
            databasePromise.catch(() => {
                if (this.databasePromise === databasePromise) {
                    this.databasePromise = null;
                }
            });
        }
        return await this.databasePromise;
    }

    private static isVideoCacheComplete(video: IOfflineVideo, cachedRequestURLs: string[]): boolean {
        const generationPrefix = `${self.location.origin}/__offline__/videos/${video.video_id}/${video.generation_id}/`;
        const hasPlaylist = cachedRequestURLs.includes(`${generationPrefix}playlist.m3u8`);
        const segmentCount = cachedRequestURLs.filter(url => url.startsWith(`${generationPrefix}segments/`)).length;
        const isComplete = hasPlaylist === true && segmentCount === video.segment_count;

        // 再生に必要なプレイリストまたは映像セグメントが欠けた世代だけを削除対象として報告する
        // サムネイルなどの付随データは取得失敗を許容しているため、動画本体の完成判定には含めない
        if (isComplete === false) {
            console.warn(
                `[OfflineVideoStorage] Removed incomplete offline video data. [video_id: ${video.video_id}, ` +
                `has_playlist: ${hasPlaylist}, expected_segment_count: ${video.segment_count}, actual_segment_count: ${segmentCount}]`,
            );
        }
        return isComplete;
    }

    private static async deleteIncompleteVideo(video: IOfflineVideo): Promise<void> {
        const database = await this.openDatabase();
        const transaction = database.transaction(this.VIDEO_STORE_NAME, 'readwrite');
        const currentVideo = await transaction.store.get(video.video_id);

        // 欠損検査後に別タブが保存を置き換えていれば、新しい保存世代には触れない
        if (currentVideo?.generation_id !== video.generation_id) {
            await transaction.done;
            return;
        }
        await transaction.store.delete(video.video_id);
        await transaction.done;
        await this.deleteGeneration(video.video_id, video.generation_id);
        this.eventTarget.dispatchEvent(new Event('change'));
    }
}
