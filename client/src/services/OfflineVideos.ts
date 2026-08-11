import type { IRecordedProgram } from '@/services/Videos';

import OfflineVideoStorage from '@/services/OfflineVideoStorage';
import Utils from '@/utils';


/** オフライン保存ジョブの状態 */
export type OfflineDownloadState = 'Waiting' | 'Downloading' | 'Finalizing' | 'Completed' | 'Failed' | 'Cancelled';

/** オフライン保存済み動画 */
export interface IOfflineVideo {
    video_id: number;
    generation_id: string;
    file_hash: string;
    program: IRecordedProgram;
    quality: string;
    size_bytes: number;
    segment_count: number;
    saved_at: number;
}

/** オフライン保存ジョブ */
export interface IOfflineDownloadJob {
    job_id: string;
    video_id: number;
    generation_id: string;
    program: IRecordedProgram;
    quality: string;
    state: OfflineDownloadState;
    estimated_size_bytes: number;
    downloaded_bytes: number;
    background_fetch_id: string | null;
    error: string | null;
}

interface IOfflineVideoStreamMetadata {
    video_id: number;
    file_hash: string;
    quality: string;
    duration_seconds: number;
}

/**
 * 録画番組のオフライン保存ジョブとダウンロード応答の展開を管理する。
 */
export default class OfflineVideos {

    static readonly eventTarget = OfflineVideoStorage.eventTarget;

    /** 保存画質セレクタと同じ利用者向けラベル */
    private static readonly QUALITY_LABELS: Record<string, string> = {
        '1080p-60fps': '1080p (60fps)',
        '1080p': '1080p',
        '810p': '810p',
        '720p': '720p',
        '540p': '540p',
        '480p': '480p',
        '360p': '360p',
        '240p': '240p',
    };

    /** 保存画質セレクタの基底値 (HEVC / 24fps 等の接尾辞は含まない) */
    static readonly BASE_QUALITY_VALUES = [
        '1080p-60fps',
        '1080p',
        '810p',
        '720p',
        '540p',
        '480p',
        '360p',
        '240p',
    ] as const;

    /** server/app/constants.py QUALITY と同じエンコード設定 (表示用の平均ビットレートと上限ビットレート) */
    private static readonly STREAM_QUALITY_BITRATES: Record<string, {video_bitrate_kbps: number; video_bitrate_max_kbps: number; audio_bitrate_kbps: number}> = {
        '1080p-60fps': {video_bitrate_kbps: 9500, video_bitrate_max_kbps: 13000, audio_bitrate_kbps: 256},
        '1080p-60fps-hevc': {video_bitrate_kbps: 3500, video_bitrate_max_kbps: 5200, audio_bitrate_kbps: 192},
        '1080p': {video_bitrate_kbps: 9500, video_bitrate_max_kbps: 13000, audio_bitrate_kbps: 256},
        '1080p-hevc': {video_bitrate_kbps: 3000, video_bitrate_max_kbps: 4500, audio_bitrate_kbps: 192},
        '810p': {video_bitrate_kbps: 5500, video_bitrate_max_kbps: 7600, audio_bitrate_kbps: 192},
        '810p-hevc': {video_bitrate_kbps: 2500, video_bitrate_max_kbps: 3700, audio_bitrate_kbps: 192},
        '720p': {video_bitrate_kbps: 4500, video_bitrate_max_kbps: 6200, audio_bitrate_kbps: 192},
        '720p-hevc': {video_bitrate_kbps: 2000, video_bitrate_max_kbps: 3000, audio_bitrate_kbps: 192},
        '540p': {video_bitrate_kbps: 3000, video_bitrate_max_kbps: 4100, audio_bitrate_kbps: 192},
        '540p-hevc': {video_bitrate_kbps: 1400, video_bitrate_max_kbps: 2100, audio_bitrate_kbps: 192},
        '480p': {video_bitrate_kbps: 2000, video_bitrate_max_kbps: 2800, audio_bitrate_kbps: 192},
        '480p-hevc': {video_bitrate_kbps: 1050, video_bitrate_max_kbps: 1750, audio_bitrate_kbps: 192},
        '360p': {video_bitrate_kbps: 1100, video_bitrate_max_kbps: 1800, audio_bitrate_kbps: 128},
        '360p-hevc': {video_bitrate_kbps: 750, video_bitrate_max_kbps: 1250, audio_bitrate_kbps: 128},
        '240p': {video_bitrate_kbps: 550, video_bitrate_max_kbps: 650, audio_bitrate_kbps: 128},
        '240p-hevc': {video_bitrate_kbps: 450, video_bitrate_max_kbps: 650, audio_bitrate_kbps: 128},
    };

    /** 空き容量判定向けの上限ビットレート余裕係数 */
    private static readonly REQUIRED_STORAGE_SIZE_MARGIN = 1.1;

    /**
     * VBR / QVBR エンコード (-vb, --vbr, --qvbr) では constants.py の video_bitrate は目標値であり、
     * 実際の映像平均は番組内容次第で目標より低く収まる
     * 720p-hevc・30分で 470MB 見積もり→370MB 実測のような乖離を抑える係数
     */
    private static readonly VBR_EFFECTIVE_VIDEO_BITRATE_RATIO = {
        hevc: 0.75,
        avc: 0.85,
    } as const;

    /** 進捗バー見積もり向けの余裕係数 (実効平均を基準にするため、表示見積もりより小さく保つ) */
    private static readonly JOB_PROGRESS_SIZE_MARGIN = 1.05;

    private static readonly STREAM_MAGIC = new TextEncoder().encode('KTVODLP\n');
    private static foregroundAbortControllers = new Map<string, AbortController>();
    private static foregroundLockReleases = new Map<string, () => void>();
    /** Web Locks 非対応環境で、同一タブ内の start() 呼び出しを録画番組 ID ごとに直列化する */
    private static startMutexTailByVideoID = new Map<number, Promise<void>>();

    /** 前景保存中にタブを閉じようとしたときの警告 */
    private static readonly onBeforeUnload = (event: BeforeUnloadEvent): void => {
        event.preventDefault();
        event.returnValue = '';
    };

    /**
     * Background Fetch を利用できるかを返す。
     * @returns 利用できる場合は true
     */
    static async isBackgroundFetchSupported(): Promise<boolean> {

        // Service Worker の登録がなければ Background Fetch の管理オブジェクトも取得できない
        if ('serviceWorker' in navigator === false) {
            return false;
        }
        const registration = await navigator.serviceWorker.getRegistration();
        return registration?.backgroundFetch !== undefined;
    }

    /**
     * 保存済み動画を取得する。
     * @returns 保存日時が新しい順の動画一覧
     */
    static async getVideos(): Promise<IOfflineVideo[]> {
        return await OfflineVideoStorage.getVideos();
    }

    /**
     * 録画番組 ID に対応する保存済み動画を取得する。
     * @param videoID 録画番組 ID
     * @returns 保存済み動画（存在しない場合は null）
     */
    static async getVideo(videoID: number): Promise<IOfflineVideo | null> {
        return await OfflineVideoStorage.getVideo(videoID);
    }

    /**
     * 実行中または完了した保存ジョブを取得する。
     * @returns 保存ジョブ一覧
     */
    static async getJobs(): Promise<IOfflineDownloadJob[]> {

        return await OfflineVideoStorage.getJobs();
    }

    /**
     * 指定した録画番組の実行中保存ジョブを取得する。
     * @param videoID 録画番組 ID
     * @returns 実行中ジョブ (存在しない場合は null)
     */
    static async getActiveJobForVideo(videoID: number): Promise<IOfflineDownloadJob | null> {

        const jobs = await this.getJobs();
        return jobs.find(job =>
            job.video_id === videoID && ['Waiting', 'Downloading', 'Finalizing'].includes(job.state),
        ) ?? null;
    }

    /**
     * ページ内 Fetch で保存中のジョブがあるかを返す。
     * @returns 前景保存中なら true
     */
    static async hasActiveForegroundDownload(): Promise<boolean> {

        // IndexedDB は別タブとも共有されるため、このページが所有するロックだけを更新延期の判定に使う
        return this.foregroundLockReleases.size > 0;
    }

    /**
     * 前回のページ終了で中断された前景保存ジョブを回収する。
     */
    static async recoverInterruptedForegroundDownloads(): Promise<void> {

        const jobs = await this.getJobs();
        if ('locks' in navigator) {
            for (const job of jobs) {
                if (job.background_fetch_id !== null || ['Waiting', 'Downloading', 'Finalizing'].includes(job.state) === false) continue;

                // Web Locks を取得できなければ別タブが保存中なので、共有 IndexedDB の状態へ触れない
                await navigator.locks.request(this.getForegroundLockName(job.job_id), {ifAvailable: true}, async (lock) => {
                    if (lock === null) return;
                    const latestJob = await OfflineVideoStorage.getJob(job.job_id);
                    if (latestJob === null || ['Waiting', 'Downloading', 'Finalizing'].includes(latestJob.state) === false) return;
                    await this.markJobFailed(latestJob.job_id, 'ページが閉じられたため、オフライン保存が中断されました。');
                });
            }
        } else {
            // Web Locks 非対応環境では所有タブを識別できないため、前景保存の実行中ジョブは起動時に失敗へ倒して断片を回収する
            for (const job of jobs) {
                if (job.background_fetch_id !== null || ['Waiting', 'Downloading', 'Finalizing'].includes(job.state) === false) continue;
                await this.markJobFailed(job.job_id, 'ページが閉じられたため、オフライン保存が中断されました。');
            }
        }

        await OfflineVideoStorage.cleanupOrphanedGenerations();
    }

    /**
     * 録画番組のオフライン保存を開始する。
     * @param program 保存する録画番組
     * @param quality 追加オプションを含む API 画質
     * @returns 作成した保存ジョブ
     */
    static async start(program: IRecordedProgram, quality: string): Promise<IOfflineDownloadJob> {

        // Vue コンポーネントから渡される番組情報はリアクティブ Proxy のため、そのままでは IndexedDB の構造化複製に失敗する
        // API 由来の JSON データだけを保存時点のスナップショットへ変換し、Service Worker からも安全に読み出せる値へ固定する
        const programSnapshot = JSON.parse(JSON.stringify(program)) as IRecordedProgram;

        // 同一録画番組への並行 start() を直列化し、IndexedDB へジョブが載る前の重複開始を防ぐ
        return await this.withVideoStartLock(programSnapshot.id, async () => {
            const activeJob = await this.getActiveJobForVideo(programSnapshot.id);
            if (activeJob !== null) {
                throw new Error('この録画番組はすでにオフライン保存中です。');
            }

            // 進捗バーは目標ビットレート基準、空き容量判定は上限ビットレート基準で見積もる
            const estimatedSizeBytes = OfflineVideos.estimateJobSizeBytes(programSnapshot.recorded_video.duration, quality);
            if (estimatedSizeBytes === null) {
                throw new Error(`オフライン保存に対応していない画質です。(${quality})`);
            }
            const requiredStorageBytes = OfflineVideos.estimateRequiredStorageBytes(programSnapshot.recorded_video.duration, quality);
            if (requiredStorageBytes === null) {
                throw new Error(`オフライン保存に対応していない画質です。(${quality})`);
            }

            // Background Fetch は一時応答と展開後キャッシュが併存するため、前景保存の2倍を空き容量判定へ使う
            const isBackgroundFetchSupported = await this.isBackgroundFetchSupported();
            const storageEstimate = await navigator.storage?.estimate() ?? {};
            const availableBytes = (storageEstimate.quota ?? 0) - (storageEstimate.usage ?? 0);
            const requiredBytes = requiredStorageBytes * (isBackgroundFetchSupported === true ? 2 : 1);
            if (storageEstimate.quota !== undefined && availableBytes < requiredBytes) {
                throw new Error(`オフライン保存に必要な空き容量が不足しています。必要: ${Utils.formatBytes(requiredBytes)} / 空き: ${Utils.formatBytes(Math.max(0, availableBytes))}`);
            }

            // 同じ録画番組を保存し直す場合も、旧世代を消さず新しい世代へ書き込む
            const generationID = crypto.randomUUID();
            const jobID = crypto.randomUUID();
            const job: IOfflineDownloadJob = {
                job_id: jobID,
                video_id: programSnapshot.id,
                generation_id: generationID,
                program: programSnapshot,
                quality,
                state: 'Waiting',
                estimated_size_bytes: estimatedSizeBytes,
                downloaded_bytes: 0,
                background_fetch_id: isBackgroundFetchSupported === true ? `konomitv-offline-${jobID}` : null,
                error: null,
            };
            const releaseForegroundLock = isBackgroundFetchSupported === false ? await this.acquireForegroundLock(job.job_id) : null;
            try {
                await OfflineVideoStorage.putJobIfVideoIdle(job);
            } catch (error) {
                releaseForegroundLock?.();
                throw error;
            }

            let request: Request;
            try {
            // API と同じオリジンの Request へ認証情報を固定し、ページ終了後もブラウザが単独で取得できるようにする
                const accessToken = Utils.getAccessToken();
                if (accessToken === null) {
                    throw new Error('ログイン情報がありません。');
                }
                request = new Request(`${Utils.api_base_url}/streams/video/${programSnapshot.id}/${quality}/offline-stream`, {
                    headers: {'Authorization': `Bearer ${accessToken}`},
                });

                // 番組一覧とシークバーが通信なしでも描画できるよう、小さな付随データは動画本体より先に同じ世代へ保存する
                const cache = await OfflineVideoStorage.openCache();
                const generationBaseURL = OfflineVideoStorage.getGenerationBaseURL(programSnapshot.id, generationID);
                const assetRequests = [
                    {source: `${Utils.api_base_url}/videos/${programSnapshot.id}/thumbnail`, destination: `${generationBaseURL}/assets/thumbnail.webp`},
                    {source: `${Utils.api_base_url}/videos/${programSnapshot.id}/thumbnail/tiled`, destination: `${generationBaseURL}/assets/thumbnail-tiled.webp`},
                ];
                if (programSnapshot.channel !== null) {
                    assetRequests.push({
                        source: `${Utils.api_base_url}/channels/${programSnapshot.channel.id}/logo`,
                        destination: `${generationBaseURL}/assets/channel-logo`,
                    });
                }
                await Promise.all(assetRequests.map(async assetRequest => {
                    try {
                        const assetResponse = await fetch(assetRequest.source, {
                            headers: {'Authorization': `Bearer ${accessToken}`},
                        });
                        if (assetResponse.ok === true) {
                            await cache.put(assetRequest.destination, assetResponse);
                        }
                    } catch (error) {
                    // 付随データの取得失敗は動画保存を止めず、映像本体を優先する
                        console.warn('[OfflineVideos] Failed to cache an optional offline asset:', error);
                    }
                }));

                // 実況 API は応答が遅くなりがちで、保存開始自体はコメントがなくても問題ないため、動画転送の登録を待たせない
                void (async () => {
                    const jikkyoSource = `${Utils.api_base_url}/videos/${programSnapshot.id}/jikkyo`;
                    const jikkyoDestination = `${generationBaseURL}/assets/jikkyo.json`;
                    try {
                        const assetResponse = await fetch(jikkyoSource, {
                            headers: {'Authorization': `Bearer ${accessToken}`},
                        });
                        if (assetResponse.ok !== true) return;

                        // キャンセルや失敗で世代が破棄された後の到着分を CacheStorage へ書き込まない
                        const latestJob = await OfflineVideoStorage.getJob(job.job_id);
                        if (latestJob === null || latestJob.generation_id !== generationID ||
                        ['Failed', 'Cancelled'].includes(latestJob.state)) {
                            return;
                        }
                        await cache.put(jikkyoDestination, assetResponse);
                    } catch (error) {
                        console.warn('[OfflineVideos] Failed to cache an optional offline asset:', error);
                    }
                })();

                // 付随データの取得中にも別画面からキャンセルできるため、実際の動画転送を登録する直前に最新状態を確認する
                if (await OfflineVideoStorage.updateActiveJob(job) === false) {
                    throw new Error('オフライン保存はキャンセルされました。');
                }
            } catch (error) {
            // 動画転送へ所有権を渡す前の失敗では、作成済みの断片と前景ロックをこの呼び出し内で回収する
                releaseForegroundLock?.();
                await this.markJobFailed(job.job_id, error instanceof Error ? error.message : 'オフライン保存を開始できませんでした。');
                throw error;
            }

            if (isBackgroundFetchSupported === true && job.background_fetch_id !== null) {
                try {
                    const registration = await navigator.serviceWorker.getRegistration();
                    if (registration === undefined) {
                        throw new Error('Service Worker の登録が見つかりません。');
                    }
                    const backgroundFetchManager = registration.backgroundFetch;
                    if (backgroundFetchManager === undefined) {
                        throw new Error('Background Fetch API を利用できません。');
                    }
                    await backgroundFetchManager.fetch(job.background_fetch_id, [request], {
                        title: `${programSnapshot.title}をオフライン保存`,
                        icons: [{src: '/assets/images/icons/icon-192px.png', sizes: '192x192', type: 'image/png'}],
                    });

                    // 登録処理中にキャンセルされた場合は、ブラウザへ渡した直後の Background Fetch も確実に停止する
                    if (await OfflineVideoStorage.updateActiveJob(job) === false) {
                        const backgroundFetch = await backgroundFetchManager.get(job.background_fetch_id);
                        await backgroundFetch?.abort();
                        await OfflineVideoStorage.deleteGeneration(job.video_id, job.generation_id);
                        throw new Error('オフライン保存はキャンセルされました。');
                    }
                } catch (error) {
                // 登録失敗時は先に保存した付随データを残さず、一覧へ失敗理由を引き継ぐ
                    await this.markJobFailed(job.job_id, error instanceof Error ? error.message : 'バックグラウンド保存を登録できませんでした。');
                    throw error;
                }
                this.notifyChange();
                return job;
            }

            // Safari などではページが存続している間だけ通常の Fetch で同じ応答を保存する
            try {
                job.state = 'Downloading';
                if (await OfflineVideoStorage.updateActiveJob(job) === false) {
                    throw new Error('オフライン保存はキャンセルされました。');
                }
            } catch (error) {
            // 転送処理へ引き渡す前の失敗は、この呼び出しで前景ロックを解放する
                releaseForegroundLock?.();
                await this.markJobFailed(job.job_id, error instanceof Error ? error.message : 'オフライン保存を開始できませんでした。');
                throw error;
            }
            const abortController = new AbortController();
            this.foregroundAbortControllers.set(job.job_id, abortController);
            void (async () => {
                let wakeLock: WakeLockSentinel | null = null;
                let releaseForegroundActivityProtection: (() => void) | null = null;
                try {
                // 前景保存中だけ画面の自動消灯を抑え、Safari などで JavaScript 実行が止まる可能性を下げる
                    if ('wakeLock' in navigator) {
                        try {
                            wakeLock = await navigator.wakeLock.request('screen');
                        } catch (error) {
                            console.warn('[OfflineVideos] Failed to acquire a screen wake lock:', error);
                        }
                    }

                    // 無音音声は Chrome のバックグラウンド保護対象にならないため、ローカル WebRTC 接続でページ凍結を抑える
                    // マイク権限や外部サーバーを使わない RTCDataChannel を、動画転送が終わるまで開いたまま保持する
                    try {
                        releaseForegroundActivityProtection = await this.acquireForegroundActivityProtection();
                    } catch (error) {
                        console.warn('[OfflineVideos] Failed to acquire foreground activity protection:', error);
                    }
                    const response = await fetch(request, {signal: abortController.signal});
                    if (response.ok === false) {
                        throw new Error(`オフライン保存 API が HTTP ${response.status} を返しました。`);
                    }
                    await this.finalizeResponse(job.job_id, response);
                } catch (error) {
                    console.error('[OfflineVideos] Foreground offline download failed:', error);
                    const latestJob = await OfflineVideoStorage.getJob(job.job_id);
                    if (latestJob !== null && ['Waiting', 'Downloading', 'Finalizing'].includes(latestJob.state)) {
                    // 利用者による中止とページ終了による fetch 中断の双方で、未完の断片を残さない
                        if (abortController.signal.aborted === true) {
                            await this.markJobCancelled(job.job_id);
                        } else {
                            await this.markJobFailed(job.job_id, error instanceof Error ? error.message : 'オフライン保存に失敗しました。');
                        }
                    }
                } finally {
                    // ページ凍結防止用の WebRTC 接続を先に閉じ、前景保存中だけの資源利用に限定する
                    releaseForegroundActivityProtection?.();

                    // Wake Lock の解放失敗でも、前景保存の所有情報と Web Lock は必ず回収する
                    this.foregroundAbortControllers.delete(job.job_id);
                    releaseForegroundLock?.();
                    try {
                        await wakeLock?.release();
                    } catch (error) {
                        console.warn('[OfflineVideos] Failed to release the screen wake lock:', error);
                    }
                }
            })();
            return job;
        });
    }

    /**
     * Background Fetch または前景 Fetch の応答を CacheStorage へ展開する。
     * @param jobID 保存ジョブ ID
     * @param response オフライン保存 API の応答
     */
    static async finalizeResponse(jobID: string, response: Response): Promise<void> {

        const job = await OfflineVideoStorage.getJob(jobID);
        if (job === null || response.body === null) {
            throw new Error('保存ジョブまたはレスポンス本体が見つかりません。');
        }
        job.state = 'Downloading';
        if (await OfflineVideoStorage.updateActiveJob(job) === false) {
            throw new Error('オフライン保存ジョブはすでに終了しています。');
        }

        const reader = response.body.getReader();
        const pendingChunks: Uint8Array[] = [];
        let pendingChunkIndex = 0;
        let pendingChunkOffset = 0;
        let pendingLength = 0;
        let isStreamFinished = false;
        let sizeBytes = 0;
        let segmentCount = 0;
        let lastPersistedProgressBytes = job.downloaded_bytes;
        let lastPersistedProgressAt = Date.now();
        const segmentDurations: number[] = [];
        const cache = await OfflineVideoStorage.openCache();
        const generationBaseURL = OfflineVideoStorage.getGenerationBaseURL(job.video_id, job.generation_id);

        /** 指定バイト数をネットワークチャンク列から読み取る */
        const readBytes = async (length: number): Promise<Uint8Array> => {
            while (pendingLength < length && isStreamFinished === false) {
                const result = await reader.read();
                if (result.done === true) {
                    isStreamFinished = true;
                    break;
                }
                pendingChunks.push(result.value);
                pendingLength += result.value.byteLength;
                job.downloaded_bytes += result.value.byteLength;

                // ネットワークチャンクごとの書き込みを避け、進捗表示に十分な間隔だけ IndexedDB を更新する
                const currentTime = Date.now();
                if (job.downloaded_bytes - lastPersistedProgressBytes >= 1024 * 1024 || currentTime - lastPersistedProgressAt >= 250) {
                    if (await OfflineVideoStorage.updateActiveJob(job) === false) {
                        throw new Error('オフライン保存がキャンセルされました。');
                    }
                    lastPersistedProgressBytes = job.downloaded_bytes;
                    lastPersistedProgressAt = currentTime;
                }
            }
            if (pendingLength < length) {
                throw new Error('オフライン保存データが途中で終了しました。');
            }

            // 受信済みデータの全連結を避け、呼び出し元が必要とする長さの領域だけを割り当てる
            const output = new Uint8Array(length);
            let outputOffset = 0;
            while (outputOffset < length) {
                const chunk = pendingChunks[pendingChunkIndex];
                const availableChunkLength = chunk.byteLength - pendingChunkOffset;
                const copyLength = Math.min(availableChunkLength, length - outputOffset);
                output.set(chunk.subarray(pendingChunkOffset, pendingChunkOffset + copyLength), outputOffset);
                outputOffset += copyLength;
                pendingChunkOffset += copyLength;

                // チャンク全体を読み終えたら次のチャンクへ進む
                if (pendingChunkOffset === chunk.byteLength) {
                    pendingChunkIndex++;
                    pendingChunkOffset = 0;
                }
            }
            pendingLength -= length;

            // 長時間の保存で読み終えたチャンクへの参照を保持し続けないよう、一定数ごとに配列先頭を回収する
            if (pendingChunkIndex >= 32) {
                pendingChunks.splice(0, pendingChunkIndex);
                pendingChunkIndex = 0;
            }
            return output;
        };

        try {
            // 固定マジック値が一致しない応答は、サーバーのエラーページや未知の将来形式なので保存しない
            const magic = await readBytes(this.STREAM_MAGIC.byteLength);
            if (magic.some((value, index) => value !== this.STREAM_MAGIC[index])) {
                throw new Error('オフライン保存データの形式を認識できません。');
            }

            // 先頭 JSON から録画ファイルと画質を検証し、別リクエストの応答を混在させない
            const metadataLength = new DataView((await readBytes(4)).buffer).getUint32(0);
            if (metadataLength === 0 || metadataLength > 1024 * 1024) {
                throw new Error('オフライン保存データのメタデータ長が不正です。');
            }
            const metadata = JSON.parse(new TextDecoder().decode(await readBytes(metadataLength))) as IOfflineVideoStreamMetadata;
            if (metadata.video_id !== job.video_id || metadata.file_hash !== job.program.recorded_video.file_hash ||
                metadata.quality !== job.quality) {
                throw new Error('オフライン保存データのメタデータが保存ジョブと一致しません。');
            }

            while (true) {
                // 終端レコードは sequence と件数の8バイト、それ以外は長さを含む12バイトで判別する
                const sequence = new DataView((await readBytes(4)).buffer).getUint32(0);
                if (sequence === 0xffffffff) {
                    const expectedSegmentCount = new DataView((await readBytes(4)).buffer).getUint32(0);
                    if (expectedSegmentCount !== segmentCount) {
                        throw new Error('オフライン保存データのセグメント数が一致しません。');
                    }
                    break;
                }
                const recordHeader = new DataView((await readBytes(8)).buffer);
                const durationMilliseconds = recordHeader.getUint32(0);
                const segmentLength = recordHeader.getUint32(4);
                if (sequence !== segmentCount || durationMilliseconds === 0 || segmentLength === 0 || segmentLength > 128 * 1024 * 1024) {
                    throw new Error('オフライン保存データのセグメントヘッダーが不正です。');
                }
                const segmentData = await readBytes(segmentLength);
                await cache.put(`${generationBaseURL}/segments/${sequence}.ts`, new Response(segmentData, {
                    headers: {'Content-Type': 'video/mp2t'},
                }));
                segmentDurations.push(durationMilliseconds / 1000);
                segmentCount++;
                sizeBytes += segmentLength;
            }

            // 保存した実データだけを指す VOD プレイリストを生成し、通常再生のセッション API から完全に切り離す
            job.state = 'Finalizing';
            if (await OfflineVideoStorage.updateActiveJob(job) === false) {
                throw new Error('オフライン保存がキャンセルされました。');
            }
            if (segmentDurations.length === 0) {
                throw new Error('オフライン保存データに映像セグメントがありません。');
            }
            const targetDuration = Math.ceil(segmentDurations.reduce((maximum, duration) => Math.max(maximum, duration), 0));
            let playlist = '#EXTM3U\n#EXT-X-VERSION:6\n#EXT-X-PLAYLIST-TYPE:VOD\n';
            playlist += `#EXT-X-TARGETDURATION:${targetDuration}\n`;
            segmentDurations.forEach((duration, sequence) => {
                playlist += `#EXTINF:${duration.toFixed(3)},\nsegments/${sequence}.ts\n`;
            });
            playlist += '#EXT-X-ENDLIST\n';
            await cache.put(`${generationBaseURL}/playlist.m3u8`, new Response(playlist, {
                headers: {'Content-Type': 'application/vnd.apple.mpegurl'},
            }));

            // 新世代の全データを書き終えてから動画レコードを差し替え、再生側が途中データを参照する時間を作らない
            const previousVideo = await this.getVideo(job.video_id);
            const video: IOfflineVideo = {
                video_id: job.video_id,
                generation_id: job.generation_id,
                file_hash: metadata.file_hash,
                program: job.program,
                quality: job.quality,
                size_bytes: sizeBytes,
                segment_count: segmentCount,
                saved_at: Date.now(),
            };
            const isCompleted = await OfflineVideoStorage.completeJob(job, video);
            if (isCompleted === false) {
                // 展開中にキャンセルされた場合は動画一覧へ追加せず、キャンセル後に書き込まれた断片も回収する
                await OfflineVideoStorage.deleteGeneration(job.video_id, job.generation_id);
                return;
            }

            // 有効世代を切り替えた後なら、削除中も必ず新しい保存データから再生できる
            if (previousVideo !== null && previousVideo.generation_id !== video.generation_id) {
                await OfflineVideoStorage.deleteGeneration(previousVideo.video_id, previousVideo.generation_id);
            }
            this.notifyChange();
        } catch (error) {
            // 破損応答や保存キャンセルでは未読部分の受信を打ち切り、ネットワーク接続とストリームロックを解放する
            try {
                await reader.cancel();
            } catch (cancelError) {
                console.warn('[OfflineVideos] Failed to cancel the offline download response reader:', cancelError);
            }
            await this.markJobFailed(job.job_id, error instanceof Error ? error.message : 'オフライン保存データを処理できませんでした。');

            // キャンセル処理の削除後に受信処理が書いた断片も回収し、完了済みの有効世代だけは保持する
            const savedVideo = await OfflineVideoStorage.getStoredVideo(job.video_id);
            if (savedVideo?.generation_id !== job.generation_id) {
                await OfflineVideoStorage.deleteGeneration(job.video_id, job.generation_id);
            }
            throw error;
        }
    }

    /**
     * Service Worker で完了できなかった保存ジョブを失敗状態へ更新する。
     * @param jobID 保存ジョブ ID
     * @param error 利用者へ表示する失敗理由
     */
    static async markJobFailed(jobID: string, error: string): Promise<void> {

        // 状態遷移に勝った失敗処理だけが断片を削除し、確定済みの保存世代には触れない
        const job = await OfflineVideoStorage.transitionActiveJobToTerminalState(jobID, 'Failed', error);
        if (job === null) return;
        await OfflineVideoStorage.deleteGeneration(job.video_id, job.generation_id);
        this.notifyChange();
    }

    /**
     * Service Worker で中止された保存ジョブをキャンセル状態へ更新する。
     * @param jobID 保存ジョブ ID
     */
    static async markJobCancelled(jobID: string): Promise<void> {

        // Background Fetch の完了と中止が競合しても、先に確定した終端状態を保持する
        const job = await OfflineVideoStorage.transitionActiveJobToTerminalState(jobID, 'Cancelled', null);
        if (job === null) return;
        await OfflineVideoStorage.deleteGeneration(job.video_id, job.generation_id);
        this.notifyChange();
    }

    /**
     * 保存開始時に指定する API 画質文字列を組み立てる。
     * @param baseQuality 1080p や 720p などの基底画質
     * @param options 通信節約モードなどの付加オプション
     * @returns API 画質
     */
    static buildAPIQuality(baseQuality: string, options: {
        isDataSaverMode: boolean;
        isHEVCSupported: boolean;
        isHEVC10bitSupported: boolean;
        is24fpsMode: boolean;
    }): string {

        let apiQuality = baseQuality;
        if (options.isDataSaverMode === true && options.isHEVCSupported === true) {
            apiQuality += '-hevc';
            if (options.isHEVC10bitSupported === true) {
                apiQuality += '-10bit';
            }
        }
        if (options.is24fpsMode === true && baseQuality !== '1080p-60fps') {
            apiQuality += '-24fps';
        }
        return apiQuality;
    }

    /**
     * 保存ジョブの進捗計算向けに、VBR の実効平均ビットレートから保存容量を見積もる。
     * @param durationSeconds 番組尺 (秒)
     * @param apiQuality API 画質
     * @returns 見積もりバイト数。未対応画質なら null
     */
    static estimateJobSizeBytes(durationSeconds: number, apiQuality: string): number | null {

        const effectiveBitrates = OfflineVideos.getEffectiveStreamBitrates(apiQuality);
        if (effectiveBitrates.total_bitrate_kbps === 0) return null;

        const effectiveBitrateBps = effectiveBitrates.total_bitrate_kbps * 1000;
        return Math.ceil((effectiveBitrateBps * durationSeconds / 8) * OfflineVideos.JOB_PROGRESS_SIZE_MARGIN);
    }

    /**
     * 空き容量判定向けに、server/app/constants.py の video_bitrate_max + audio_bitrate から保存容量を見積もる。
     * @param durationSeconds 番組尺 (秒)
     * @param apiQuality API 画質
     * @returns 見積もりバイト数。未対応画質なら null
     */
    static estimateRequiredStorageBytes(durationSeconds: number, apiQuality: string): number | null {

        const bitrates = OfflineVideos.getStreamQualityBitrates(apiQuality);
        if (bitrates.video_bitrate_max_kbps === 0) return null;

        const maxBitrateBps = (bitrates.video_bitrate_max_kbps + bitrates.audio_bitrate_kbps) * 1000;
        return Math.ceil((maxBitrateBps * durationSeconds / 8) * OfflineVideos.REQUIRED_STORAGE_SIZE_MARGIN);
    }

    /**
     * 表示向けに、VBR の実効平均ビットレートから保存容量を見積もる。
     * @param durationSeconds 番組尺 (秒)
     * @param apiQuality API 画質
     * @returns 見積もりバイト数
     */
    static estimateDisplaySizeBytes(durationSeconds: number, apiQuality: string): number {

        const effectiveBitrates = OfflineVideos.getEffectiveStreamBitrates(apiQuality);
        return Math.ceil(effectiveBitrates.total_bitrate_kbps * 1000 * durationSeconds / 8);
    }

    /**
     * オフライン保存容量を利用者向けに整形する。
     * @param bytes バイト数
     * @param approximate 見積もり表示なら true
     * @returns 約 2.2GB や 340MB などの文字列
     */
    static formatOfflineSize(bytes: number, approximate: boolean): string {

        const formatted = OfflineVideos.formatOfflineSizeValue(bytes, approximate);
        return approximate === true ? `約${formatted}` : formatted;
    }

    /**
     * オフライン保存容量の単位付き文字列を返す。
     * 見積もり表示では GB 以上は小数1桁、MB は10MB刻みに丸める。
     * 実測表示では GB 以上は小数2桁、MB は1MB単位の整数、それ未満は通常の自動単位切り替え。
     * @param bytes バイト数
     * @param approximate 見積もり表示なら true
     * @returns 2.2GB や 340MB などの文字列
     */
    private static formatOfflineSizeValue(bytes: number, approximate: boolean): string {

        const oneMB = 1024 * 1024;
        const oneGB = oneMB * 1024;

        // GB 以上は見積もりなら粗く、実測なら小数2桁まで表示する
        if (bytes >= oneGB) {
            return Utils.formatBytes(bytes, approximate === true ? 1 : 2);
        }

        if (bytes >= oneMB) {
            const megabytes = bytes / oneMB;
            // 見積もりだけ 344MB のような細かい値を避け、340MB のように10MB刻みへ丸める
            if (approximate === true) {
                const roundedMegabytes = Math.round(megabytes / 10) * 10;
                return `${roundedMegabytes}MB`;
            }
            // 実測値は1MB単位でそのまま表示する
            return `${Math.round(megabytes)}MB`;
        }

        return Utils.formatBytes(bytes, approximate === true ? 1 : 0);
    }

    /**
     * 画質設定画面と同じ形式で平均ビットレートを返す。
     * @param apiQuality API 画質
     * @returns 4.9Mbps などの文字列
     */
    static formatAverageBitrateLabel(apiQuality: string): string {

        const effectiveBitrates = OfflineVideos.getEffectiveStreamBitrates(apiQuality);
        const averageMbps = effectiveBitrates.total_bitrate_kbps / 1000;
        return `${averageMbps.toFixed(1)}Mbps`;
    }

    /**
     * 保存画質セレクタ向けの表示ラベルを返す。
     * @param baseQuality 1080p や 720p などの基底画質
     * @param durationSeconds 番組尺 (秒)
     * @param isHEVC 通信節約モード (HEVC) が有効か
     * @returns 720p (約 2.2GB / 平均4.9Mbps) などの文字列
     */
    static formatQualitySelectLabel(baseQuality: string, durationSeconds: number, isHEVC: boolean): string {

        const apiQuality = isHEVC === true ? `${baseQuality}-hevc` : baseQuality;
        const qualityLabel = OfflineVideos.QUALITY_LABELS[baseQuality] ?? baseQuality;
        const sizeLabel = OfflineVideos.formatOfflineSize(
            OfflineVideos.estimateDisplaySizeBytes(durationSeconds, apiQuality),
            true,
        );
        const bitrateLabel = OfflineVideos.formatAverageBitrateLabel(apiQuality);
        return `${qualityLabel} (${sizeLabel} / 平均${bitrateLabel})`;
    }

    /**
     * 録画一覧メニュー向けに、既定画質 (720p) の見積もり容量を返す。
     * @param program 録画番組
     * @param isHEVC 通信節約モード (HEVC) を既定で使うか
     * @returns 約 2.2GB などの文字列
     */
    static formatDefaultMenuSizeLabel(program: IRecordedProgram, isHEVC: boolean): string {

        const apiQuality = isHEVC === true ? '720p-hevc' : '720p';
        return OfflineVideos.formatOfflineSize(
            OfflineVideos.estimateDisplaySizeBytes(program.recorded_video.duration, apiQuality),
            true,
        );
    }

    /**
     * API 画質文字列から server/app/constants.py 相当の平均ビットレートを取得する。
     * @param apiQuality API 画質
     * @returns 映像・音声ビットレート (kbps)
     */
    private static getStreamQualityBitrates(apiQuality: string): {
        video_bitrate_kbps: number;
        video_bitrate_max_kbps: number;
        audio_bitrate_kbps: number;
    } {

        // 10bit / 24fps は平均ビットレートへ影響しないため、ルックアップキーから除外する
        const lookupQuality = apiQuality.replace(/-10bit/g, '').replace(/-24fps/g, '');
        const bitrates = OfflineVideos.STREAM_QUALITY_BITRATES[lookupQuality];
        if (bitrates !== undefined) return bitrates;

        const baseQuality = lookupQuality.replace(/-hevc/g, '');
        return OfflineVideos.STREAM_QUALITY_BITRATES[baseQuality] ?? {
            video_bitrate_kbps: 0,
            video_bitrate_max_kbps: 0,
            audio_bitrate_kbps: 0,
        };
    }

    /**
     * VBR エンコードの実効平均ビットレートを返す。
     * VideoEncodingTask が -vb / --vbr / --qvbr で指定する video_bitrate は目標値のため、映像側だけ係数を掛けて実測に近づける。
     * @param apiQuality API 画質
     * @returns 実効映像・音声・合算ビットレート (kbps)
     */
    private static getEffectiveStreamBitrates(apiQuality: string): {
        video_bitrate_kbps: number;
        audio_bitrate_kbps: number;
        total_bitrate_kbps: number;
    } {

        const bitrates = OfflineVideos.getStreamQualityBitrates(apiQuality);
        const isHEVC = apiQuality.includes('-hevc') === true;
        const effectiveVideoRatio = isHEVC === true
            ? OfflineVideos.VBR_EFFECTIVE_VIDEO_BITRATE_RATIO.hevc
            : OfflineVideos.VBR_EFFECTIVE_VIDEO_BITRATE_RATIO.avc;
        const effectiveVideoBitrateKbps = bitrates.video_bitrate_kbps * effectiveVideoRatio;
        const totalBitrateKbps = effectiveVideoBitrateKbps + bitrates.audio_bitrate_kbps;
        return {
            video_bitrate_kbps: effectiveVideoBitrateKbps,
            audio_bitrate_kbps: bitrates.audio_bitrate_kbps,
            total_bitrate_kbps: totalBitrateKbps,
        };
    }

    /**
     * API 画質文字列から利用者向けの画質ラベルを返す。
     * HEVC / 10bit / 24fps などの内部接尾辞は一覧表示では省略する。
     * @param quality API 画質
     * @returns 720p や 1080p (60fps) などの表示ラベル
     */
    static formatQualityLabel(quality: string): string {

        // 保存開始時と同じ順序で付与される接尾辞だけを外し、解像度ベースのラベルへ戻す
        const baseQuality = quality.replace(/-hevc/g, '').replace(/-10bit/g, '').replace(/-24fps/g, '');
        return OfflineVideos.QUALITY_LABELS[baseQuality] ?? baseQuality;
    }

    /**
     * 終端状態の保存ジョブを一覧から消す。
     * @param jobID 保存ジョブ ID
     */
    static async dismissJob(jobID: string): Promise<void> {
        await OfflineVideoStorage.deleteJob(jobID);
    }

    /**
     * 保存ジョブをキャンセルする。
     * @param jobID 保存ジョブ ID
     */
    static async cancel(jobID: string): Promise<void> {

        // 完了確定と同じ IndexedDB 上でキャンセルを確定し、勝った処理だけが保存世代を削除する
        const job = await OfflineVideoStorage.transitionActiveJobToTerminalState(jobID, 'Cancelled', null);
        if (job === null) return;

        // Background Fetch の停止はブラウザへ任せ、前景 Fetch は世代削除と状態変更で後続処理を無効化する
        if (job.background_fetch_id !== null && 'serviceWorker' in navigator) {
            const registration = await navigator.serviceWorker.getRegistration();
            const backgroundFetch = await registration?.backgroundFetch?.get(job.background_fetch_id);
            await backgroundFetch?.abort();
        } else {
            this.foregroundAbortControllers.get(job.job_id)?.abort();
        }
        await OfflineVideoStorage.deleteGeneration(job.video_id, job.generation_id);
    }

    /**
     * 保存済み動画を端末から削除する。
     * @param videoID 録画番組 ID
     */
    static async deleteVideo(videoID: number): Promise<void> {

        const video = await this.getVideo(videoID);
        if (video === null) return;
        await OfflineVideoStorage.deleteVideo(video);
    }

    /**
     * 保存済み動画の HLS プレイリスト URLを返す。
     * @param video 保存済み動画
     * @returns Service Worker が配信するプレイリスト URL
     */
    static getPlaylistURL(video: IOfflineVideo): string {
        return OfflineVideoStorage.getPlaylistURL(video);
    }

    /**
     * 保存済み動画に付随する画像・JSON の URLを返す。
     * @param video 保存済み動画
     * @param assetName 付随データ名
     * @returns Service Worker が配信する付随データ URL
     */
    static getAssetURL(video: IOfflineVideo, assetName: 'thumbnail.webp' | 'thumbnail-tiled.webp' | 'channel-logo' | 'jikkyo.json'): string {
        return OfflineVideoStorage.getAssetURL(video, assetName);
    }

    private static getForegroundLockName(jobID: string): string {
        return `konomitv-offline-foreground-${jobID}`;
    }

    private static getVideoStartLockName(videoID: number): string {
        return `konomitv-offline-start-${videoID}`;
    }

    /**
     * 前景保存中のページ凍結を抑えるローカル WebRTC 接続を開始する。
     * @returns WebRTC 接続を閉じる関数（利用できない環境では null）
     */
    private static async acquireForegroundActivityProtection(): Promise<(() => void) | null> {

        if ('RTCPeerConnection' in window === false) return null;

        const offerPeerConnection = new RTCPeerConnection({iceServers: []});
        const answerPeerConnection = new RTCPeerConnection({iceServers: []});
        const offerDataChannel = offerPeerConnection.createDataChannel('konomitv-offline-download');
        const dataChannels = [offerDataChannel];

        /** ICE 候補を SDP に集約し、外部の STUN サーバーなしでローカル接続を確立できるまで待つ */
        const waitForICEGathering = async (peerConnection: RTCPeerConnection): Promise<void> => {
            if (peerConnection.iceGatheringState === 'complete') return;
            await new Promise<void>((resolve, reject) => {
                const timeoutID = window.setTimeout(() => {
                    peerConnection.removeEventListener('icegatheringstatechange', onICEGatheringStateChange);
                    reject(new Error('WebRTC のローカル接続準備がタイムアウトしました。'));
                }, 5_000);
                const onICEGatheringStateChange = (): void => {
                    if (peerConnection.iceGatheringState !== 'complete') return;
                    window.clearTimeout(timeoutID);
                    peerConnection.removeEventListener('icegatheringstatechange', onICEGatheringStateChange);
                    resolve();
                };
                peerConnection.addEventListener('icegatheringstatechange', onICEGatheringStateChange);
            });
        };

        try {
            answerPeerConnection.addEventListener('datachannel', (event) => {
                dataChannels.push(event.channel);
            }, {once: true});

            // ICE 候補を含む Offer / Answer を同一ページ内で交換し、ネットワーク上の相手を必要としない接続にする
            await offerPeerConnection.setLocalDescription(await offerPeerConnection.createOffer());
            await waitForICEGathering(offerPeerConnection);
            const offerDescription = offerPeerConnection.localDescription;
            if (offerDescription === null) {
                throw new Error('WebRTC の Offer を作成できませんでした。');
            }
            await answerPeerConnection.setRemoteDescription(offerDescription);
            await answerPeerConnection.setLocalDescription(await answerPeerConnection.createAnswer());
            await waitForICEGathering(answerPeerConnection);
            const answerDescription = answerPeerConnection.localDescription;
            if (answerDescription === null) {
                throw new Error('WebRTC の Answer を作成できませんでした。');
            }
            await offerPeerConnection.setRemoteDescription(answerDescription);

            // Chrome が保護対象と判定するのは開いた DataChannel なので、接続完了後に動画転送へ進む
            if (offerDataChannel.readyState !== 'open') {
                await new Promise<void>((resolve, reject) => {
                    const timeoutID = window.setTimeout(() => {
                        reject(new Error('WebRTC のローカル接続がタイムアウトしました。'));
                    }, 5_000);
                    offerDataChannel.addEventListener('open', () => {
                        window.clearTimeout(timeoutID);
                        resolve();
                    }, {once: true});
                });
            }

            return () => {
                dataChannels.forEach(dataChannel => dataChannel.close());
                offerPeerConnection.close();
                answerPeerConnection.close();
            };
        } catch (error) {
            dataChannels.forEach(dataChannel => dataChannel.close());
            offerPeerConnection.close();
            answerPeerConnection.close();
            throw error;
        }
    }

    /**
     * 録画番組 ID ごとに start() の本体処理を直列化する。
     * Web Locks 対応環境ではタブ間も含めて排他し、非対応環境では同一タブ内だけを直列化する。
     */
    private static async withVideoStartLock<T>(videoID: number, operation: () => Promise<T>): Promise<T> {

        if ('locks' in navigator) {
            return await navigator.locks.request(this.getVideoStartLockName(videoID), operation);
        }

        const previous = this.startMutexTailByVideoID.get(videoID) ?? Promise.resolve();
        let releaseCurrent!: () => void;
        const currentGate = new Promise<void>(resolve => {
            releaseCurrent = resolve;
        });
        const queued = previous.then(() => currentGate);
        this.startMutexTailByVideoID.set(videoID, queued);

        await previous;
        try {
            return await operation();
        } finally {
            releaseCurrent();
            if (this.startMutexTailByVideoID.get(videoID) === queued) {
                this.startMutexTailByVideoID.delete(videoID);
            }
        }
    }

    /** 前景保存中だけタブ閉じ警告を有効化する */
    private static updateForegroundDownloadWarning(): void {
        if (this.foregroundLockReleases.size > 0) {
            window.addEventListener('beforeunload', OfflineVideos.onBeforeUnload);
        } else {
            window.removeEventListener('beforeunload', OfflineVideos.onBeforeUnload);
        }
    }

    private static async acquireForegroundLock(jobID: string): Promise<(() => void) | null> {
        if ('locks' in navigator === false) return null;

        let resolveLockAcquired: (() => void) | null = null;
        let rejectLockAcquired: ((reason: unknown) => void) | null = null;
        let resolveLockRelease: (() => void) | null = null;
        let isLockAcquired = false;
        const lockAcquired = new Promise<void>((resolve, reject) => {
            resolveLockAcquired = resolve;
            rejectLockAcquired = reject;
        });
        const lockRelease = new Promise<void>((resolve) => {
            resolveLockRelease = resolve;
        });

        // リクエストを完了させず保持し、別タブが同じジョブを中断済みと誤認するのを防ぐ
        void navigator.locks.request(this.getForegroundLockName(jobID), async () => {
            this.foregroundLockReleases.set(jobID, () => resolveLockRelease?.());
            isLockAcquired = true;
            resolveLockAcquired?.();
            await lockRelease;
            this.foregroundLockReleases.delete(jobID);
            this.updateForegroundDownloadWarning();
        }).catch((error: unknown) => {
            // ロック取得前の API 失敗を呼び出し元へ返し、開始処理を永久待機させない
            if (isLockAcquired === false) rejectLockAcquired?.(error);
        });
        await lockAcquired;
        this.updateForegroundDownloadWarning();
        return () => resolveLockRelease?.();
    }

    /**
     * 保存状態の変更を同一コンテキストと、開いているページへ通知する。
     * Service Worker 内からは EventTarget がページと共有されないため、postMessage でも伝える。
     */
    private static notifyChange(): void {

        OfflineVideos.eventTarget.dispatchEvent(new Event('change'));

        // Service Worker 側の EventTarget はページから参照できないため、開いているクライアントへ直接通知する
        if (typeof window === 'undefined') {
            const serviceWorkerScope = self as unknown as ServiceWorkerGlobalScope;
            void serviceWorkerScope.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
                for (const client of clients) {
                    client.postMessage({ type: 'konomitv-offline-videos-change' });
                }
            });
        }
    }

}

// Service Worker からの保存状態更新をページ側 EventTarget へ橋渡しする
if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event: MessageEvent) => {
        if (event.data?.type === 'konomitv-offline-videos-change') {
            OfflineVideos.eventTarget.dispatchEvent(new Event('change'));
        }
    });
}
