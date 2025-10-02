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
                            この機能は現在ベータ版です。完全なオフライン視聴には対応していませんが、一度キャッシュした動画はネットワークが不安定な環境でも再生できます。
                        </div>
                        <div class="text-body-2 mt-2">
                            <strong>⚠️ ダウンロード中はこのページを開いたままにしてください。</strong>ページを閉じたり、デバイスをスリープすると、ダウンロードが一時停止されます。
                        </div>
                        <div class="text-body-2 mt-2">
                            また、ダウンロードが中断された場合、音声と映像の同期がずれる可能性があります。ご了承ください。
                        </div>
                    </v-alert>

                    <!-- ストレージ情報と一括操作ボタン -->
                    <v-card class="mb-4" v-if="storage_info">
                        <v-card-text>
                            <div class="d-flex align-center justify-space-between mb-3">
                                <div>
                                    <div class="text-subtitle-1 mb-1">ストレージ使用量</div>
                                    <div class="text-body-2 text-text-darken-1">
                                        {{ Utils.formatBytes(storage_info.usage) }} / {{ Utils.formatBytes(storage_info.quota) }}
                                        (残り: {{ Utils.formatBytes(storage_info.available) }})
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
                                :model-value="(storage_info.usage / storage_info.quota) * 100"
                                color="primary"
                                height="8"
                                rounded
                            ></v-progress-linear>

                            <!-- 一括操作ボタン -->
                            <div class="d-flex gap-2 mt-3">
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
                                    @click="pauseAllDownloads"
                                    :disabled="!hasActiveTasks"
                                >
                                    <Icon icon="fluent:pause-24-regular" width="18px" class="mr-1" />
                                    全て一時停止
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
                                    <div class="offline-video__content">
                                        <!-- サムネイル -->
                                        <div class="offline-video__thumbnail" @click="playVideo(video.video_id)">
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
                                            <div class="offline-video__title" @click="playVideo(video.video_id)" v-html="ProgramUtils.decorateProgramInfo({ title: video.title } as any, 'title')">
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

                                            <!-- ダウンロード進行状況 -->
                                            <div v-if="video.status === 'downloading' || video.status === 'paused'" class="offline-video__progress">
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

                                            <!-- 完了時の情報 -->
                                            <div v-else-if="video.status === 'completed'" class="offline-video__details">
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
                                            <div v-else-if="video.status === 'failed' && video.error_message" class="offline-video__error">
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
                                                @click="pauseDownload(video.video_id, video.quality)"
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
                                                @click="resumeDownload(video.video_id, video.quality)"
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
                                                @click="deleteVideo(video.video_id, video.quality)"
                                            >
                                                <Icon icon="fluent:delete-24-regular" width="22px" />
                                                <v-tooltip activator="parent" location="top">削除</v-tooltip>
                                            </v-btn>
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
            return DownloadManager.getAllTasks();
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
    beforeUnmount() {
        // コンポーネント破棄時にコールバックをクリア
        DownloadManager.onStorageUpdate = null;
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

        // 動画を再生
        playVideo(video_id: number) {
            this.$router.push(`/videos/watch/${video_id}`);
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
        @include smartphone-vertical {
            gap: 12px;
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

    &__progress {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    &__progress-text {
        font-size: 12px;
        color: rgb(var(--v-theme-text-darken-1));
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