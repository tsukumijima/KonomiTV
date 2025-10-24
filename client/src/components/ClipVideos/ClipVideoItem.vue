<template>
    <router-link v-ripple class="clip-video-item" :to="`/clip-videos/watch/${clipVideo.id}`">
        <div class="clip-video-item__container">
            <div class="clip-video-item__thumbnail">
                <img class="clip-video-item__thumbnail-image" loading="lazy" decoding="async"
                    :src="thumbnailUrl">
                <div class="clip-video-item__thumbnail-duration">{{ formattedDuration }}</div>
            </div>
            <div class="clip-video-item__content">
                <div class="clip-video-item__content-title">{{ displayTitle }}</div>
                <div class="clip-video-item__content-meta">
                    <div class="clip-video-item__content-meta-broadcaster" v-if="clipVideo.recorded_program.channel">
                        <img class="clip-video-item__content-meta-broadcaster-icon" loading="lazy" decoding="async"
                            :src="`${Utils.api_base_url}/channels/${clipVideo.recorded_program.channel.id}/logo`">
                        <span class="clip-video-item__content-meta-broadcaster-name">Ch: {{clipVideo.recorded_program.channel.channel_number}} {{clipVideo.recorded_program.channel.name}}</span>
                    </div>
                    <div class="clip-video-item__content-meta-broadcaster" v-else>
                        <span class="clip-video-item__content-meta-broadcaster-name">チャンネル情報なし</span>
                    </div>
                    <div class="clip-video-item__content-meta-time">{{ formatDate(clipVideo.created_at) }}</div>
                </div>
                <div class="clip-video-item__content-description">{{ clipVideo.recorded_program.description }}</div>
            </div>
            <div class="clip-video-item__menu">
                <v-menu location="bottom end" :close-on-content-click="true">
                    <template v-slot:activator="{ props }">
                        <div v-ripple class="clip-video-item__menu-button"
                            v-bind="props"
                            @click.prevent.stop=""
                            @mousedown.prevent.stop="">
                            <svg width="19px" height="19px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M9.5 13a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0"/>
                            </svg>
                        </div>
                    </template>
                    <v-list density="compact" bg-color="background-lighten-1" class="clip-video-item__menu-list">
                        <v-list-item @click="show_clip_video_info = true">
                            <template v-slot:prepend>
                                <svg width="20px" height="20px" viewBox="0 0 16 16">
                                    <path fill="currentColor" d="M8.499 7.5a.5.5 0 1 0-1 0v3a.5.5 0 0 0 1 0zm.25-2a.749.749 0 1 1-1.499 0a.749.749 0 0 1 1.498 0M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1M2 8a6 6 0 1 1 12 0A6 6 0 0 1 2 8"></path>
                                </svg>
                            </template>
                            <v-list-item-title class="ml-3">クリップ動画情報を表示</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="show_alternate_title_dialog = true">
                            <template v-slot:prepend>
                                <Icon icon="fluent:rename-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">別タイトルを編集</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="downloadClipVideo">
                            <template v-slot:prepend>
                                <Icon icon="fluent:arrow-download-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">クリップ動画をダウンロード ({{ formattedFileSize }})</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="reanalyzeClipVideo">
                            <template v-slot:prepend>
                                <Icon icon="fluent:book-arrow-clockwise-20-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">メタデータを再解析</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="regenerateThumbnail(true)" v-ftooltip="'既存のサムネイルタイルを再利用し代表サムネイルのみを更新します'">
                            <template v-slot:prepend>
                                <Icon icon="fluent:image-arrow-counterclockwise-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">サムネイルを更新</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="regenerateThumbnail(false)" v-ftooltip="'サムネイルを完全に作り直します（数分かかります）'">
                            <template v-slot:prepend>
                                <Icon icon="fluent:image-arrow-counterclockwise-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">サムネイルを再作成</v-list-item-title>
                        </v-list-item>
                        <v-divider></v-divider>
                        <v-list-item @click="showDeleteConfirmation" class="clip-video-item__menu-list-item--danger">
                            <template v-slot:prepend>
                                <Icon icon="fluent:delete-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">クリップ動画を削除</v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </div>
        </div>
    </router-link>
    <ClipVideoInfoDialog :clipVideo="clipVideo" v-model:show="show_clip_video_info" />
    <ClipVideoAlternateTitleDialog :clipVideo="clipVideo" v-model:show="show_alternate_title_dialog" @saved="handleAlternateTitleSaved" />

    <!-- クリップ動画削除確認ダイアログ -->
    <v-dialog max-width="750" v-model="show_delete_confirmation">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">本当にクリップ動画を削除しますか？</v-card-title>
            <v-card-text class="pt-2 pb-0">
                <div class="delete-confirmation__title mb-4">{{ displayTitle }}</div>
                <div class="text-error-lighten-1 font-weight-bold">
                    このクリップ動画に関連するすべてのデータが削除されます。<br>
                    元に戻すことはできません。本当にクリップ動画を削除しますか？
                </div>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer></v-spacer>
                <v-btn color="text" variant="text" @click="show_delete_confirmation = false">
                    <Icon icon="fluent:dismiss-20-regular" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn class="px-3" color="error" variant="flat" @click="deleteClipVideo">
                    <Icon icon="fluent:delete-20-regular" width="18px" height="18px" />
                    <span class="ml-1">クリップ動画を削除</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed, ref, watch } from 'vue';

import Message from '@/message';
import ClipVideoInfoDialog from '@/components/ClipVideos/Dialogs/ClipVideoInfoDialog.vue';
import ClipVideoAlternateTitleDialog from '@/components/ClipVideos/Dialogs/ClipVideoAlternateTitleDialog.vue';
import ClipVideos, { IClipVideo } from '@/services/ClipVideos';
import Utils from '@/utils';
import useUserStore from '@/stores/UserStore';

// Props
const props = defineProps<{
    clipVideo: IClipVideo;
}>();

// Emits
const emit = defineEmits<{
    (e: 'deleted', id: number): void;
    (e: 'updated', clipVideo: IClipVideo): void;
}>();

// クリップ情報ダイアログの表示状態
const show_clip_video_info = ref(false);
// 削除確認ダイアログの表示状態
const show_delete_confirmation = ref(false);
// 別タイトル編集ダイアログの表示状態
const show_alternate_title_dialog = ref(false);

// 別タイトルの現在値
const current_alternate_title = ref<string | null>(props.clipVideo.alternate_title);

// 別タイトルが更新された際に同期する
watch(() => props.clipVideo.alternate_title, (value) => {
    current_alternate_title.value = value ?? null;
});

// ユーザーストア
const userStore = useUserStore();

// サムネイル URL
const thumbnailUrl = computed(() => {
    return ClipVideos.getClipVideoThumbnailURL(props.clipVideo.id);
});

// 再生時間のフォーマット
const formattedDuration = computed(() => {
    const totalSeconds = Math.floor(props.clipVideo.duration);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
});

// 表示用タイトル
const displayTitle = computed(() => {
    const alternate = current_alternate_title.value?.trim();
    if (alternate && alternate.length > 0) {
        return alternate;
    }
    return props.clipVideo.title;
});

// 日付のフォーマット
const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
        return '今日';
    } else if (diffDays === 1) {
        return '昨日';
    } else if (diffDays < 7) {
        return `${diffDays}日前`;
    } else {
        return date.toLocaleDateString('ja-JP', { year: 'numeric', month: 'numeric', day: 'numeric' });
    }
};

// クリップ動画のダウンロード
const downloadClipVideo = () => {
    window.location.href = `${Utils.api_base_url}/clip-videos/${props.clipVideo.id}/download`;
};

// ファイルサイズのフォーマット
const formattedFileSize = computed(() => Utils.formatBytes(props.clipVideo.file_size));

// クリップ動画のメタデータ再解析
const reanalyzeClipVideo = async () => {
    Message.success('メタデータの再解析を開始します。完了までしばらくお待ちください。');
    const result = await ClipVideos.reanalyzeClipVideo(props.clipVideo.id);
    if (result === true) {
        Message.success('メタデータの再解析が完了しました。');
    }
};

// サムネイルの再生成
const regenerateThumbnail = async (skip_tile_if_exists: boolean) => {
    Message.success('サムネイルの再作成を開始しました。完了までしばらくお待ちください。');
    const result = await ClipVideos.regenerateThumbnail(props.clipVideo.id, skip_tile_if_exists);
    if (result === true) {
        Message.success('サムネイルの再作成が完了しました。');
    }
};

// クリップ動画削除確認ダイアログを表示
const showDeleteConfirmation = () => {
    if (userStore.user === null || userStore.user.is_admin === false) {
        Message.warning('クリップ動画を削除するには管理者権限が必要です。\n管理者アカウントでログインし直してください。');
        return;
    }
    show_delete_confirmation.value = true;
};

// クリップ動画を削除
const deleteClipVideo = async () => {
    show_delete_confirmation.value = false;
    Message.info('クリップ動画の削除を開始します。完了までしばらくお待ちください。');

    const success = await ClipVideos.deleteClipVideo(props.clipVideo.id);
    if (success) {
        Message.success('クリップ動画を削除しました。');
        emit('deleted', props.clipVideo.id);
    } else {
        Message.error('クリップ動画の削除に失敗しました。');
    }
};

// 別タイトル保存後の処理
const handleAlternateTitleSaved = (updatedClipVideo: IClipVideo) => {
    current_alternate_title.value = updatedClipVideo.alternate_title ?? null;
    emit('updated', updatedClipVideo);
};

</script>
<style lang="scss" scoped>

.clip-video-item {
    display: flex;
    position: relative;
    width: 100%;
    height: 125px;
    padding: 0px 16px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s;
    text-decoration: none;
    user-select: none;
    box-sizing: border-box;
    cursor: pointer;
    content-visibility: auto;
    contain-intrinsic-height: auto 125px;
    @include smartphone-vertical {
        height: auto;
        padding: 0px 9px;
        contain-intrinsic-height: auto 115px;
    }

    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }
    // タッチデバイスで hover を無効にする
    @media (hover: none) {
        &:hover {
            background: rgb(var(--v-theme-background-lighten-1));
        }
    }

    &__container {
        display: flex;
        align-items: center;
        width: 100%;
        height: 100%;
        padding: 12px 0px;
        @include smartphone-vertical {
            padding: 8px 0px;
        }
    }

    &__thumbnail {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        aspect-ratio: 16 / 9;
        height: 100%;
        border-radius: 4px;
        overflow: hidden;
        position: relative;
        @include smartphone-vertical {
            width: 120px;
            height: auto;
            aspect-ratio: 3 / 2;
        }

        &-image {
            width: 100%;
            border-radius: 4px;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            @include smartphone-vertical {
                aspect-ratio: 3 / 2;
            }
        }

        &-duration {
            position: absolute;
            right: 4px;
            bottom: 4px;
            padding: 3px 4px;
            border-radius: 2px;
            background: rgba(0, 0, 0, 0.7);
            color: #fff;
            font-size: 11px;
            line-height: 1;
            @include smartphone-vertical {
                font-size: 10.5px;
            }
        }
    }

    &__content {
        display: flex;
        flex-direction: column;
        justify-content: center;
        flex-grow: 1;
        min-width: 0;  // magic!
        margin-left: 16px;
        margin-right: 40px;
        @include tablet-vertical {
            margin-right: 16px;
        }
        @include smartphone-horizontal {
            margin-right: 20px;
        }
        @include smartphone-vertical {
            margin-left: 12px;
            margin-right: 0px;
        }

        &-title {
            display: -webkit-box;
            font-size: 17px;
            font-weight: 600;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 1;  // 1行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                font-size: 15px;
                line-height: 1.4;
                -webkit-line-clamp: 2;  // 2行までに制限
            }
            @include smartphone-horizontal {
                font-size: 14px;
            }
            @include smartphone-vertical {
                margin-right: 12px;
                font-size: 13px;
                line-height: 1.4;
                -webkit-line-clamp: 2;  // 2行までに制限
            }
        }

        &-meta {
            display: flex;
            align-items: center;
            margin-top: 4px;
            font-size: 13.8px;
            @include tablet-vertical {
                flex-wrap: wrap;
            }
            @include smartphone-horizontal {
                margin-top: 6px;
                flex-direction: column;
                align-items: flex-start;
            }
            @include smartphone-vertical {
                flex-direction: column;
                align-items: flex-start;
                margin-top: 4px;
                font-size: 12px;
            }

            &-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;  // magic!

                &-icon {
                    flex-shrink: 0;
                    width: 28px;
                    height: 16px;
                    margin-right: 10px;
                    border-radius: 2px;
                    // 読み込まれるまでのアイコンの背景
                    background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                    object-fit: cover;
                    @include smartphone-horizontal {
                        margin-right: 8px;
                    }
                    @include smartphone-vertical {
                        margin-right: 4px;
                        width: 24px;
                        height: 14px;
                    }
                }

                &-name {
                    color: rgb(var(--v-theme-text-darken-1));
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include tablet-vertical {
                        font-size: 13px;
                    }
                    @include smartphone-horizontal {
                        font-size: 13px;
                    }
                    @include smartphone-vertical {
                        margin-left: 4px;
                        font-size: 11.5px;
                    }
                }
            }

            &-time {
                display: inline-block;
                flex-shrink: 0;
                margin-left: auto;
                color: rgb(var(--v-theme-text-darken-1));
                height: 16px;
                line-height: 15.5px;
                @include desktop {
                    min-width: 140px;
                }
                @include tablet-horizontal {
                    min-width: 140px;
                }
                @include tablet-vertical {
                    margin-top: 2px;
                    margin-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    margin-top: 2px;
                    margin-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-vertical {
                    margin-top: 1px;
                    margin-left: 0px;
                    font-size: 11px;
                }
            }
        }

        &-description {
            display: -webkit-box;
            margin-top: 6px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 11.5px;
            line-height: 1.55;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                margin-top: 3.5px;
                font-size: 11px;
                -webkit-line-clamp: 1;  // 1行までに制限
            }
            @include smartphone-horizontal {
                margin-top: 3.5px;
                font-size: 11px;
            }
            @include smartphone-vertical {
                margin-top: 2.5px;
                margin-right: 12px;
                font-size: 10px;
                line-height: 1.45;
            }
        }
    }

    &__menu {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        position: absolute;
        top: 50%;
        right: 12px;
        transform: translateY(-50%);
        cursor: pointer;
        @include tablet-vertical {
            right: 6px;
        }
        @include smartphone-horizontal {
            right: 6px;
        }
        @include smartphone-vertical {
            right: 4px;
        }

        &-button {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            color: rgb(var(--v-theme-text-darken-1));
            border-radius: 50%;
            transition: color 0.15s ease, background-color 0.15s ease;
            user-select: none;
            @include tablet-vertical {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }
            @include smartphone-horizontal {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }
            @include smartphone-vertical {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }

            &:before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                border-radius: inherit;
                background-color: currentColor;
                color: inherit;
                opacity: 0;
                transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
                pointer-events: none;
            }
            &:hover {
                color: rgb(var(--v-theme-text));
                &:before {
                    opacity: 0.15;
                }
            }
            // タッチデバイスで hover を無効にする
            @media (hover: none) {
                &:hover {
                    &:before {
                        opacity: 0;
                    }
                }
            }
        }

        &-list {
            :deep(.v-list-item-title) {
                font-size: 14px !important;
            }

            :deep(.v-list-item) {
                min-height: 36px !important;
            }
        }
    }
}

.delete-confirmation {
    &__title {
        padding: 12px;
        background-color: rgb(var(--v-theme-background-lighten-1));
        border-radius: 4px;
        font-size: 14px;
        word-break: break-all;
        white-space: pre-wrap;
    }
}

.clip-video-item__menu-list-item--danger {
    color: rgb(var(--v-theme-error)) !important;
}

</style>
