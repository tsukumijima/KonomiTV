<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="offline-videos-container-wrapper">
                <SPHeaderBar />
                <div class="offline-videos-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'ビデオをみる', path: '/videos/' },
                        { name: 'オフライン視聴', path: '/offline-videos', disabled: true },
                    ]" />

                    <!-- ヘッダー -->
                    <div class="offline-videos__header">
                        <h2 class="offline-videos__title">
                            <span class="offline-videos__title-text">オフライン視聴</span>
                            <v-chip color="warning" size="small" class="ml-3">BETA</v-chip>
                            <div class="offline-videos__title-count">
                                {{ filtered_videos.length }}件
                            </div>
                        </h2>
                        <div class="offline-videos__actions">
                            <!-- 検索ボックス -->
                            <v-text-field
                                v-model="search_query"
                                placeholder="番組名で検索..."
                                class="offline-videos__search"
                                color="primary"
                                bg-color="background-lighten-1"
                                variant="solo"
                                density="comfortable"
                                hide-details
                                clearable
                            >
                                <template #prepend-inner>
                                    <Icon icon="fluent:search-20-regular" width="20px" class="text-text-darken-1" />
                                </template>
                            </v-text-field>
                            <!-- ソート -->
                            <v-select
                                v-model="sort_order"
                                :items="[
                                    { title: '新しい順', value: 'desc' },
                                    { title: '古い順', value: 'asc' },
                                ]"
                                item-title="title"
                                item-value="value"
                                class="offline-videos__sort"
                                color="primary"
                                bg-color="background-lighten-1"
                                variant="solo"
                                density="comfortable"
                                hide-details
                            >
                            </v-select>
                        </div>
                    </div>

                    <!-- Beta 版の説明 -->
                    <v-alert type="info" variant="tonal" class="mb-4" style="flex: none;">
                        <div class="text-body-2">
                            この機能は現在ベータ版です。
                            <br>
                            完全なオフライン視聴には対応していませんが、ネットワークが不安定な環境が再生できます。
                            <br>
                            <strong>⚠️ ダウンロード中はこのページを開いたままにしてください。</strong>ページを閉じたり、デバイスをスリープすると、ダウンロードが一時停止されます。
                            <br>
                            また、ダウンロードが中断された場合、音声と映像の同期がずれる可能性があります。ご了承ください。
                        </div>
                    </v-alert>

                    <!-- ストレージ情報と一括操作ボタン -->
                    <v-card class="mb-4" :style="{ visibility: storage_info ? 'visible' : 'hidden', minHeight: '160px' }">
                        <v-card-text>
                            <div class="d-flex align-center justify-space-between mb-3">
                                <div>
                                    <div class="text-subtitle-1 mb-1">ストレージ使用量</div>
                                    <div class="text-body-2 text-text-darken-1">
                                        {{ storage_info ? `${Utils.formatBytes(storage_info.usage)} / ${Utils.formatBytes(storage_info.quota)} (残り: ${Utils.formatBytes(storage_info.available)})` : '' }}
                                    </div>
                                </div>
                                <v-btn
                                    variant="outlined"
                                    color="secondary"
                                    size="small"
                                    @click="refreshStorageInfo"
                                    :loading="is_refreshing_storage"
                                >
                                    <Icon icon="fluent:arrow-sync-20-regular" width="20px" class="mr-1" />
                                    更新
                                </v-btn>
                            </div>
                            <v-progress-linear
                                :model-value="storage_info ? (storage_info.usage / storage_info.quota) * 100 : 0"
                                color="primary"
                                height="8"
                                rounded
                            ></v-progress-linear>

                            <!-- 一括操作ボタン -->
                            <div class="d-flex align-center justify-space-between mt-3">
                                <div class="d-flex">
                                    <v-btn
                                        variant="outlined"
                                        color="success"
                                        size="small"
                                        @click="resumeAllDownloads"
                                        :disabled="!hasPausedTasks"
                                    >
                                        <Icon icon="fluent:play-24-regular" width="18px" class="mr-1" />
                                        全て再開
                                    </v-btn>
                                    <v-btn
                                        variant="outlined"
                                        color="warning"
                                        size="small"
                                        class="mx-2"
                                        @click="pauseAllDownloads"
                                        :disabled="!hasActiveTasks"
                                    >
                                        <Icon icon="fluent:pause-24-regular" width="18px" class="mr-1" />
                                        全て一時停止
                                    </v-btn>
                                </div>
                                <v-btn
                                    variant="outlined"
                                    color="primary"
                                    size="small"
                                    @click="openPiPWindow"
                                    :disabled="!hasActiveTasks || pipWindow !== null || pipVideo !== null"
                                >
                                    <Icon icon="fluent:picture-in-picture-20-regular" width="18px" class="mr-1" />
                                    バックグラウンドでダウンロード
                                </v-btn>
                            </div>
                        </v-card-text>
                    </v-card>

                    <!-- オフラインビデオリスト -->
                    <div class="offline-videos__grid"
                        :class="{
                            'offline-videos__grid--empty': filtered_videos.length === 0,
                        }">
                        <!-- 空の状態 -->
                        <div class="offline-videos__empty"
                            :class="{
                                'offline-videos__empty--show': filtered_videos.length === 0,
                            }">
                            <div class="offline-videos__empty-content">
                                <Icon class="offline-videos__empty-icon" icon="fluent:cloud-arrow-down-24-regular" width="54px" height="54px" />
                                <h2 v-if="search_query && offline_videos.length > 0">検索結果が見つかりませんでした。</h2>
                                <h2 v-else>オフライン視聴用の動画がありません</h2>
                                <div class="offline-videos__empty-submessage" v-if="!search_query">
                                    ビデオページから動画をダウンロードして、<br class="d-sm-none">オフラインで視聴できます
                                </div>
                            </div>
                        </div>

                        <!-- 動画カードリスト -->
                        <div class="offline-videos__grid-content">
                            <div
                                v-for="video in filtered_videos"
                                :key="`${video.video_id}-${video.quality}`"
                                class="offline-video"
                            >
                                <div class="offline-video__container">
                                    <router-link v-ripple class="offline-video__content"
                                        :to="video.status === 'completed' ? `/videos/watch/${video.video_id}` : { path: '' }"
                                        :class="{
                                            'offline-video__content--disabled': video.status !== 'completed',
                                        }">
                                        <!-- サムネイル -->
                                        <div class="offline-video__thumbnail">
                                            <img
                                                v-if="video.thumbnail_url"
                                                :src="video.thumbnail_url"
                                                :alt="video.title"
                                                class="offline-video__thumbnail-image"
                                            />
                                            <div v-else class="offline-video__thumbnail-placeholder">
                                                <Icon icon="fluent:image-24-regular" width="48px" />
                                            </div>
                                            <!-- 再生オーバーレイ -->
                                            <div class="offline-video__play-overlay">
                                                <Icon icon="fluent:play-circle-48-filled" width="52px" />
                                            </div>
                                        </div>

                                        <!-- 動画情報 -->
                                        <div class="offline-video__info">
                                            <div class="offline-video__title" v-html="ProgramUtils.decorateProgramInfo({ title: video.title } as any, 'title')">
                                            </div>
                                            <div class="offline-video__metadata">
                                                <v-chip size="small" color="primary" class="mr-2">
                                                    {{ video.quality }}
                                                </v-chip>
                                                <v-chip
                                                    size="small"
                                                    :color="getStatusColor(video.status)"
                                                >
                                                    {{ getStatusText(video.status) }}
                                                </v-chip>
                                            </div>

                                            <!-- 完了時の情報 -->
                                            <div v-if="video.status === 'completed'" class="offline-video__details">
                                                <span v-if="video.total_segments > 0">
                                                    {{ video.downloaded_segments }}/{{ video.total_segments }} セグメント
                                                    <span class="mx-2">•</span>
                                                </span>
                                                <span v-if="video.total_size > 0">
                                                    サイズ: {{ Utils.formatBytes(video.total_size) }}
                                                    <span class="mx-2">•</span>
                                                </span>
                                                {{ formatDate(video.created_at) }}
                                            </div>
                                            <!-- 失敗時のエラーメッセージ -->
                                            <div v-if="video.status === 'failed' && video.error_message" class="offline-video__error">
                                                エラー: {{ video.error_message }}
                                            </div>
                                        </div>

                                        <!-- アクションボタン -->
                                        <div class="offline-video__actions">
                                            <!-- ダウンロード中: 一時停止ボタン -->
                                            <v-btn
                                                v-if="video.status === 'downloading'"
                                                icon
                                                variant="text"
                                                size="small"
                                                @click.prevent.stop="pauseDownload(video.video_id, video.quality)"
                                                @mousedown.prevent.stop=""
                                            >
                                                <Icon icon="fluent:pause-24-regular" width="22px" />
                                                <v-tooltip activator="parent" location="top">一時停止</v-tooltip>
                                            </v-btn>

                                            <!-- 一時停止中/失敗時: 再開ボタン -->
                                            <v-btn
                                                v-if="video.status === 'paused' || video.status === 'failed'"
                                                icon
                                                variant="text"
                                                size="small"
                                                color="success"
                                                @click.prevent.stop="resumeDownload(video.video_id, video.quality)"
                                                @mousedown.prevent.stop=""
                                            >
                                                <Icon icon="fluent:play-24-regular" width="22px" />
                                                <v-tooltip activator="parent" location="top">再開</v-tooltip>
                                            </v-btn>

                                            <!-- 削除ボタン -->
                                            <v-btn
                                                icon
                                                variant="text"
                                                size="small"
                                                color="error"
                                                @click.prevent.stop="deleteVideo(video.video_id, video.quality)"
                                                @mousedown.prevent.stop=""
                                            >
                                                <Icon icon="fluent:delete-24-regular" width="22px" />
                                                <v-tooltip activator="parent" location="top">削除</v-tooltip>
                                            </v-btn>
                                        </div>
                                    </router-link>

                                    <!-- ダウンロード進行状況（全幅で表示） -->
                                    <div v-if="video.status === 'downloading' || video.status === 'paused'" class="offline-video__progress-full">
                                        <v-progress-linear
                                            :model-value="video.progress"
                                            :color="video.status === 'paused' ? 'warning' : 'primary'"
                                            height="6"
                                            rounded
                                        ></v-progress-linear>
                                        <div class="offline-video__progress-text">
                                            {{ video.progress }}% ({{ video.downloaded_segments }}/{{ video.total_segments }} セグメント)
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</template>

<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Message from '@/message';
import DownloadManager, { IDownloadTask } from '@/services/DownloadManager';
import OfflineDownload from '@/services/OfflineDownload';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'OfflineVideos',
    components: {
        Breadcrumbs,
        HeaderBar,
        Navigation,
        SPHeaderBar,
    },
    data() {
        return {
            // ストレージ情報
            storage_info: null as { usage: number; quota: number; available: number } | null,
            is_refreshing_storage: false,
            // 検索クエリ
            search_query: '',
            // ソート順
            sort_order: 'desc' as 'desc' | 'asc',
            // Wake Lock（画面スリープ防止）
            wakeLock: null as WakeLockSentinel | null,
            // PiP ウィンドウ
            pipWindow: null as Window | null,
            // 従来の video PiP 用の要素（降級用）
            pipVideo: null as HTMLVideoElement | null,
            pipCanvas: null as HTMLCanvasElement | null,
            pipUpdateInterval: null as number | null,
            // Utils を template で使えるようにする
            Utils: Utils,
            // ProgramUtils を template で使えるようにする
            ProgramUtils: ProgramUtils,
            // DownloadManager を template で使えるようにする
            DownloadManager: DownloadManager,
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
        // オフライン視聴用ビデオ一覧（DownloadManager から取得）
        offline_videos(): IDownloadTask[] {
            // tasks.value を参照することで Vue のリアクティブシステムが変更を検知できる
            return Array.from(DownloadManager.tasks.value.values());
        },
        // フィルタリング・ソートされたビデオリスト
        filtered_videos(): IDownloadTask[] {
            let videos = [...this.offline_videos];

            // 検索クエリでフィルタリング
            if (this.search_query) {
                const query = this.search_query.toLowerCase();
                videos = videos.filter(v => v.title.toLowerCase().includes(query));
            }

            // ソート
            videos.sort((a, b) => {
                if (this.sort_order === 'desc') {
                    return b.created_at - a.created_at;
                } else {
                    return a.created_at - b.created_at;
                }
            });

            return videos;
        },
        // ダウンロード中または一時停止中のタスクがあるか
        hasDownloadingTasks(): boolean {
            return this.offline_videos.some(v => v.status === 'downloading' || v.status === 'paused');
        },
        // 一時停止中のタスクがあるか
        hasPausedTasks(): boolean {
            return this.offline_videos.some(v => v.status === 'paused');
        },
        // ダウンロード中のタスクがあるか
        hasActiveTasks(): boolean {
            return this.offline_videos.some(v => v.status === 'downloading');
        },
    },
    async created() {
        // Cache Storage から完了済みタスクを復元
        await DownloadManager.restoreFromCacheStorage();

        // ストレージ情報を取得
        await this.refreshStorageInfo();

        // ダウンロード進捗に応じてストレージ情報を自動更新
        DownloadManager.onStorageUpdate = () => {
            this.refreshStorageInfo();
        };

        // 完了済みタスクのサイズ情報を更新
        await this.updateCompletedTasksSizes();
    },
    mounted() {
        // ページ可視性変化の監視（バックグラウンドから戻った時に Wake Lock を再取得）
        document.addEventListener('visibilitychange', this.handleVisibilityChange);
    },
    beforeUnmount() {
        // コンポーネント破棄時にコールバックをクリア
        DownloadManager.onStorageUpdate = null;

        // Wake Lock を解放
        this.releaseWakeLock();

        // PiP ウィンドウを閉じる
        this.closePiPWindow();

        // ページ可視性変化の監視を解除
        document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    },
    watch: {
        // ダウンロード中のタスクがある場合は Wake Lock を取得
        hasActiveTasks(newValue: boolean) {
            if (newValue) {
                this.requestWakeLock();
            } else {
                this.releaseWakeLock();
            }
        },
    },
    methods: {
        // ストレージ情報を更新
        async refreshStorageInfo() {
            this.is_refreshing_storage = true;
            try {
                this.storage_info = await OfflineDownload.getStorageQuota();
            } catch (error) {
                console.error('Failed to get storage info:', error);
                Message.error('ストレージ情報の取得に失敗しました');
            } finally {
                this.is_refreshing_storage = false;
            }
        },

        // 完了済みタスクのサイズ情報を更新
        async updateCompletedTasksSizes() {
            const completedTasks = this.offline_videos.filter(v => v.status === 'completed' && v.total_size === 0);
            for (const task of completedTasks) {
                const cachedSize = await OfflineDownload.getCachedVideoSize(task.video_id, task.quality);
                if (cachedSize && cachedSize > 0) {
                    task.total_size = cachedSize;
                    task.downloaded_size = cachedSize;
                }
            }
        },

        // 動画を削除
        async deleteVideo(video_id: number, quality: string) {
            if (!confirm('この動画をオフラインストレージから削除しますか？')) {
                return;
            }

            try {
                await DownloadManager.deleteDownload(video_id, quality);
                await this.refreshStorageInfo();
            } catch (error) {
                console.error('Failed to delete video:', error);
                Message.error('動画の削除中にエラーが発生しました');
            }
        },

        // ダウンロードを一時停止
        async pauseDownload(video_id: number, quality: string) {
            await DownloadManager.pauseDownload(video_id, quality);
        },

        // ダウンロードを再開
        async resumeDownload(video_id: number, quality: string) {
            await DownloadManager.resumeDownload(video_id, quality);
        },

        // 全てのダウンロードを再開
        async resumeAllDownloads() {
            const pausedOrFailedVideos = this.offline_videos.filter(v => v.status === 'paused' || v.status === 'failed');
            for (const video of pausedOrFailedVideos) {
                // 並列に実行せずに順次実行（DownloadManager は一度に1つしか実行できない）
                DownloadManager.resumeDownload(video.video_id, video.quality);
            }
        },

        // 全てのダウンロードを一時停止
        async pauseAllDownloads() {
            const downloadingVideos = this.offline_videos.filter(v => v.status === 'downloading');
            for (const video of downloadingVideos) {
                DownloadManager.pauseDownload(video.video_id, video.quality);
            }
        },

        // ステータスのテキストを取得
        getStatusText(status: string): string {
            switch (status) {
                case 'completed':
                    return '完了';
                case 'downloading':
                    return 'ダウンロード中';
                case 'failed':
                    return '失敗';
                case 'pending':
                    return '待機中';
                case 'paused':
                    return '一時停止中';
                default:
                    return '不明';
            }
        },

        // ステータスの色を取得
        getStatusColor(status: string): string {
            switch (status) {
                case 'completed':
                    return 'success';
                case 'downloading':
                    return 'primary';
                case 'failed':
                    return 'error';
                case 'pending':
                    return 'warning';
                case 'paused':
                    return 'warning';
                default:
                    return 'default';
            }
        },

        // 日時をフォーマット
        formatDate(timestamp: number): string {
            const date = new Date(timestamp);
            return date.toLocaleString('ja-JP', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
            });
        },

        // Wake Lock を取得（画面スリープ防止）
        async requestWakeLock() {
            // Wake Lock API がサポートされているかチェック
            if (!('wakeLock' in navigator)) {
                console.warn('[OfflineVideos] Wake Lock API is not supported');
                return;
            }

            try {
                // 既に取得済みの場合はスキップ
                if (this.wakeLock !== null && !this.wakeLock.released) {
                    return;
                }

                this.wakeLock = await navigator.wakeLock.request('screen');
                console.log('[OfflineVideos] Wake Lock acquired');

                // Wake Lock が解放された時のハンドラ
                this.wakeLock.addEventListener('release', () => {
                    console.log('[OfflineVideos] Wake Lock released');
                });
            } catch (error) {
                console.error('[OfflineVideos] Failed to acquire Wake Lock:', error);
            }
        },

        // Wake Lock を解放
        async releaseWakeLock() {
            if (this.wakeLock !== null && !this.wakeLock.released) {
                try {
                    await this.wakeLock.release();
                    this.wakeLock = null;
                    console.log('[OfflineVideos] Wake Lock manually released');
                } catch (error) {
                    console.error('[OfflineVideos] Failed to release Wake Lock:', error);
                }
            }
        },

        // ページ可視性変化のハンドラ
        async handleVisibilityChange() {
            // ページが再び表示された場合、ダウンロード中なら Wake Lock を再取得
            if (document.visibilityState === 'visible' && this.hasActiveTasks) {
                await this.requestWakeLock();
            }
        },

        // PiP ウィンドウを開く
        async openPiPWindow() {
            // documentPictureInPicture API のサポートチェック
            const supportsDocumentPiP = 'documentPictureInPicture' in window && !Utils.isMobileDevice();

            if (supportsDocumentPiP) {
                // 新しい Document PiP を使用
                await this.openDocumentPiPWindow();
            } else {
                // 降級到従来の video PiP
                await this.openVideoPiPWindow();
            }
        },

        // Document PiP ウィンドウを開く（新しい API）
        async openDocumentPiPWindow() {
            try {
                // 主題色を取得
                const primaryColor = getComputedStyle(document.documentElement)
                    .getPropertyValue('--v-theme-primary').trim();

                // PiP ウィンドウを開く
                this.pipWindow = await (window as any).documentPictureInPicture.requestWindow({
                    width: 400,
                    height: 200,
                });

                // PiP ウィンドウのスタイルを設定
                const pipDocument = this.pipWindow!.document;
                pipDocument.head.innerHTML = `
                    <style>
                        * {
                            margin: 0;
                            padding: 0;
                            box-sizing: border-box;
                        }
                        body {
                            font-family: 'Roboto', sans-serif;
                            background: rgb(${primaryColor});
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            color: white;
                            padding: 20px;
                        }
                        .container {
                            text-align: center;
                            width: 100%;
                        }
                        .title {
                            font-size: 18px;
                            font-weight: 500;
                            margin-bottom: 16px;
                        }
                        .progress-bar {
                            width: 100%;
                            height: 8px;
                            background: rgba(255, 255, 255, 0.3);
                            border-radius: 4px;
                            overflow: hidden;
                            margin-bottom: 12px;
                        }
                        .progress-fill {
                            height: 100%;
                            background: white;
                            border-radius: 4px;
                            transition: width 0.3s ease;
                        }
                        .stats {
                            font-size: 14px;
                            opacity: 0.9;
                        }
                        .task-list {
                            margin-top: 16px;
                            font-size: 13px;
                            opacity: 0.85;
                            max-height: 60px;
                            overflow-y: auto;
                        }
                        .task-item {
                            padding: 4px 0;
                            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                        }
                        .task-item:last-child {
                            border-bottom: none;
                        }
                    </style>
                `;

                pipDocument.body.innerHTML = `
                    <div class="container">
                        <div class="title">📥 ダウンロード中</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="progress"></div>
                        </div>
                        <div class="stats" id="stats">準備中...</div>
                        <div class="task-list" id="tasks"></div>
                    </div>
                `;

                // 進捗を定期的に更新
                const updateProgress = () => {
                    if (!this.pipWindow || this.pipWindow.closed) {
                        return;
                    }

                    const activeDownloads = this.offline_videos.filter(v => v.status === 'downloading');
                    if (activeDownloads.length === 0) {
                        // ダウンロードが全て完了したら PiP を閉じる
                        this.closePiPWindow();
                        return;
                    }

                    const totalProgress = DownloadManager.getTotalProgress();
                    const progressFill = this.pipWindow.document.getElementById('progress');
                    const statsEl = this.pipWindow.document.getElementById('stats');
                    const tasksEl = this.pipWindow.document.getElementById('tasks');

                    if (progressFill) {
                        progressFill.style.width = `${totalProgress}%`;
                    }

                    if (statsEl) {
                        statsEl.textContent = `全体進捗: ${totalProgress}% (${activeDownloads.length} 件のタスク)`;
                    }

                    if (tasksEl) {
                        tasksEl.innerHTML = activeDownloads.map(task => `
                            <div class="task-item">
                                ${task.title.substring(0, 30)}${task.title.length > 30 ? '...' : ''} - ${task.progress}%
                            </div>
                        `).join('');
                    }
                };

                // 初回更新
                updateProgress();

                // 1秒ごとに更新
                const intervalId = setInterval(updateProgress, 1000);

                // PiP ウィンドウが閉じられた時の処理
                this.pipWindow!.addEventListener('pagehide', () => {
                    clearInterval(intervalId);
                    this.pipWindow = null;
                });

                Message.success('PiP ウィンドウを開きました。このページを閉じても、ダウンロードが継続されます。');
            } catch (error) {
                console.error('[OfflineVideos] Failed to open PiP window:', error);
                Message.error('PiP ウィンドウを開けませんでした');
            }
        },

        // PiP ウィンドウを閉じる
        closePiPWindow() {
            if (this.pipWindow && !this.pipWindow.closed) {
                this.pipWindow.close();
                this.pipWindow = null;
            }
            this.closeVideoPiPWindow();
        },

        // 従来の video PiP を開く（降級方案）
        async openVideoPiPWindow() {
            try {
                // Canvas と video 要素を作成
                this.pipCanvas = document.createElement('canvas');
                this.pipCanvas.width = 640;
                this.pipCanvas.height = 360;

                this.pipVideo = document.createElement('video');
                this.pipVideo.muted = true;
                this.pipVideo.playsInline = true;
                this.pipVideo.style.position = 'fixed';
                this.pipVideo.style.bottom = '-9999px';
                document.body.appendChild(this.pipVideo);

                // Canvas から MediaStream を取得
                const stream = this.pipCanvas.captureStream(30); // 30fps
                this.pipVideo.srcObject = stream;

                // 初回描画
                this.drawPiPCanvas();

                // video を再生
                await this.pipVideo.play();

                // PiP モードに入る
                await this.pipVideo.requestPictureInPicture();

                // 定期的に Canvas を更新（前5秒は1秒ごと、その後5秒ごと）
                let updateCount = 0;
                const updateCanvas = () => {
                    this.drawPiPCanvas();
                    updateCount++;

                    // 5回更新したら（5秒経過）、省電モードに切り替え
                    if (updateCount === 5) {
                        if (this.pipUpdateInterval !== null) {
                            clearInterval(this.pipUpdateInterval);
                        }
                        // 省電モード：5秒ごとに更新
                        this.pipUpdateInterval = window.setInterval(() => {
                            this.drawPiPCanvas();
                        }, 5000);
                    }
                };

                // 初期：1秒ごとに更新
                this.pipUpdateInterval = window.setInterval(updateCanvas, 1000);

                // PiP 終了時のハンドラ
                this.pipVideo.addEventListener('leavepictureinpicture', () => {
                    this.closeVideoPiPWindow();
                });

                Message.success('PiP モードを開きました（video モード）');
            } catch (error) {
                console.error('[OfflineVideos] Failed to open video PiP:', error);
                Message.error('PiP を開けませんでした');
                this.closeVideoPiPWindow();
            }
        },

        // Canvas に下載進捗を描画
        drawPiPCanvas() {
            if (!this.pipCanvas) return;

            const ctx = this.pipCanvas.getContext('2d');
            if (!ctx) return;

            const width = this.pipCanvas.width;
            const height = this.pipCanvas.height;

            // 主題色を取得
            const primaryColorRGB = getComputedStyle(document.documentElement)
                .getPropertyValue('--v-theme-primary').trim();

            // 背景を描画
            ctx.fillStyle = `rgb(${primaryColorRGB})`;
            ctx.fillRect(0, 0, width, height);

            // テキストスタイル
            ctx.fillStyle = 'white';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // タイトル
            ctx.font = 'bold 32px sans-serif';
            ctx.fillText('📥 ダウンロード中', width / 2, 60);

            // 進捗情報を取得
            const activeDownloads = this.offline_videos.filter(v => v.status === 'downloading');

            if (activeDownloads.length === 0) {
                // ダウンロード完了
                ctx.font = '24px sans-serif';
                ctx.fillText('ダウンロード完了！', width / 2, height / 2);
                this.closeVideoPiPWindow();
                return;
            }

            const totalProgress = DownloadManager.getTotalProgress();

            // 進捗バー
            const barWidth = width - 80;
            const barHeight = 20;
            const barX = 40;
            const barY = 120;

            // 進捗バー背景
            ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
            ctx.fillRect(barX, barY, barWidth, barHeight);

            // 進捗バー前景
            ctx.fillStyle = 'white';
            ctx.fillRect(barX, barY, (barWidth * totalProgress) / 100, barHeight);

            // 進捗テキスト
            ctx.font = '24px sans-serif';
            ctx.fillText(`全体進捗: ${totalProgress}% (${activeDownloads.length} 件)`, width / 2, 180);

            // タスクリスト
            ctx.font = '18px sans-serif';
            ctx.textAlign = 'left';
            let yOffset = 230;
            const maxTasks = 4;
            activeDownloads.slice(0, maxTasks).forEach(task => {
                const title = task.title.length > 40 ? task.title.substring(0, 40) + '...' : task.title;
                ctx.fillText(`${title} - ${task.progress}%`, 40, yOffset);
                yOffset += 30;
            });

            if (activeDownloads.length > maxTasks) {
                ctx.fillText(`... 他 ${activeDownloads.length - maxTasks} 件`, 40, yOffset);
            }
        },

        // video PiP を閉じる
        closeVideoPiPWindow() {
            if (this.pipUpdateInterval !== null) {
                clearInterval(this.pipUpdateInterval);
                this.pipUpdateInterval = null;
            }

            if (this.pipVideo) {
                if (document.pictureInPictureElement === this.pipVideo) {
                    document.exitPictureInPicture().catch(() => {});
                }
                if (this.pipVideo.parentNode) {
                    this.pipVideo.parentNode.removeChild(this.pipVideo);
                }
                this.pipVideo = null;
            }

            if (this.pipCanvas) {
                this.pipCanvas = null;
            }
        },
    },
});

</script>

<style lang="scss" scoped>

.offline-videos-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.offline-videos-container {
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
        padding: 16px 8px !important;
        padding-top: 8px !important;
    }
}

.offline-videos {
    &__header {
        display: flex;
        align-items: center;
        @include smartphone-vertical {
            flex-direction: column;
            align-items: stretch;
            padding: 0px 8px;
        }
    }

    &__title {
        display: flex;
        align-items: center;
        position: relative;
        font-size: 24px;
        font-weight: 700;
        padding-top: 8px;
        padding-bottom: 20px;
        @include smartphone-vertical {
            font-size: 22px;
            padding-bottom: 16px;
        }

        &-count {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            padding-top: 8px;
            margin-left: 12px;
            font-size: 14px;
            font-weight: 400;
            color: rgb(var(--v-theme-text-darken-1));
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-left: auto;
        @include smartphone-vertical {
            margin-left: 0;
            margin-bottom: 8px;
        }

        :deep(.v-field) {
            padding-right: 4px !important;
        }
        :deep(.v-field__input) {
            padding-left: 12px !important;
            padding-right: 0px !important;
        }
    }

    &__search {
        width: 240px;
        @include smartphone-vertical {
            width: 100%;
        }

        :deep(.v-field__input) {
            font-size: 14px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            min-height: unset !important;
        }
    }

    &__sort {
        width: 103px;
        flex-shrink: 0;

        :deep(.v-field__input) {
            font-size: 14px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            min-height: unset !important;
        }
    }

    &__grid {
        display: flex;
        flex-direction: column;
        position: relative;
        width: 100%;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
        overflow: hidden;

        &--empty {
            min-height: 200px;
        }
    }

    &__grid-content {
        width: 100%;
    }

    &__empty {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        min-height: 200px;
        display: flex;
        justify-content: center;
        align-items: center;
        padding-top: 28px;
        padding-bottom: 40px;
        visibility: hidden;
        opacity: 0;
        transition: visibility 0.2s ease, opacity 0.2s ease;
        pointer-events: none;

        &--show {
            visibility: visible;
            opacity: 1;
        }

        &-content {
            text-align: center;

            .offline-videos__empty-icon {
                color: rgb(var(--v-theme-text-darken-1));
            }

            h2 {
                font-size: 21px;
                margin-top: 8px;
                @include tablet-vertical {
                    font-size: 19px !important;
                }
                @include smartphone-horizontal {
                    font-size: 19px !important;
                }
                @include smartphone-horizontal-short {
                    font-size: 19px !important;
                }
                @include smartphone-vertical {
                    font-size: 19px !important;
                    text-align: center;
                }
            }

            .offline-videos__empty-submessage {
                margin-top: 8px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 15px;
                @include tablet-vertical {
                    font-size: 13px !important;
                    text-align: center;
                }
                @include smartphone-horizontal {
                    font-size: 13px !important;
                    text-align: center;
                }
                @include smartphone-horizontal-short {
                    font-size: 13px !important;
                    text-align: center;
                }
                @include smartphone-vertical {
                    font-size: 13px !important;
                    text-align: center;
                }
            }
        }
    }
}

.offline-video {
    // 最後の項目以外の下にボーダーを追加
    &:not(:last-child) .offline-video__container {
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
    }

    &__container {
        padding: 16px;
        cursor: pointer;
        transition: background 0.15s ease;
        @include smartphone-vertical {
            padding: 12px;
        }

        &:hover {
            background: rgb(var(--v-theme-background-lighten-2));
        }
    }

    &__content {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        color: inherit;
        text-decoration: none;
        @include smartphone-vertical {
            gap: 12px;
        }

        &--disabled {
            cursor: not-allowed;
            opacity: 0.6;

            .offline-video__thumbnail {
                cursor: not-allowed;
            }

            .offline-video__title {
                cursor: not-allowed;
            }
        }
    }

    &__thumbnail {
        position: relative;
        width: 200px;
        height: 112px;
        flex-shrink: 0;
        border-radius: 8px;
        overflow: hidden;
        background: rgb(var(--v-theme-background-lighten-2));
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        @include smartphone-vertical {
            width: 120px;
            height: 67px;
        }

        &:hover .offline-video__play-overlay {
            opacity: 1;
        }
    }

    &__thumbnail-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    &__thumbnail-placeholder {
        color: rgb(var(--v-theme-text-darken-1));
    }

    &__play-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.4);
        color: white;
        opacity: 0;
        transition: opacity 0.2s ease;
    }

    &__info {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }

    &__title {
        font-size: 16px;
        font-weight: 600;
        line-height: 1.4;
        cursor: pointer;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        @include smartphone-vertical {
            font-size: 14px;
        }

        &:hover {
            color: rgb(var(--v-theme-primary));
        }
    }

    &__metadata {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
    }

    &__progress-full {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 12px;
        padding: 0 16px 4px;
        @include smartphone-vertical {
            margin-top: 8px;
            padding: 0 12px 4px;
        }
    }

    &__progress-text {
        font-size: 12px;
        color: rgb(var(--v-theme-text-darken-1));
        text-align: center;
        @include smartphone-vertical {
            font-size: 11px;
        }
    }

    &__details {
        font-size: 13px;
        color: rgb(var(--v-theme-text-darken-1));
        @include smartphone-vertical {
            font-size: 12px;
        }
    }

    &__error {
        font-size: 13px;
        color: rgb(var(--v-theme-error));
        @include smartphone-vertical {
            font-size: 12px;
        }
    }

    &__actions {
        display: flex;
        align-items: flex-start;
        gap: 4px;
        flex-shrink: 0;
        @include smartphone-vertical {
            flex-direction: column;
        }
    }
}

</style>