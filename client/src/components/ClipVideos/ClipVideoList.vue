<template>
    <div class="clip-video-list" :class="{'clip-video-list--show-sort': !hideSort}">
        <div class="clip-video-list__header" v-if="!hideHeader">
            <h2 class="clip-video-list__title">
                <div v-if="showBackButton" v-ripple class="clip-video-list__title-back" @click="$router.back()">
                    <Icon icon="fluent:chevron-left-12-filled" width="27px" />
                </div>
                <span class="clip-video-list__title-text">{{title}}</span>
                <div class="clip-video-list__title-count" v-if="!showMoreButton">
                    <template v-if="isLoading">
                        <Icon icon="line-md:loading-twotone-loop" class="mr-1 spin" width="20px" height="20px" />
                        <span>読み込み中...</span>
                    </template>
                    <template v-else>{{displayTotal}}件</template>
                </div>
            </h2>
            <div class="clip-video-list__actions">
                <v-select v-if="!hideSort"
                    v-model="sort_order"
                    :items="[
                        { title: '新しい順', value: 'desc' },
                        { title: '古い順', value: 'asc' },
                    ]"
                    item-title="title"
                    item-value="value"
                    class="clip-video-list__sort"
                    color="primary"
                    bg-color="background-lighten-1"
                    variant="solo"
                    density="comfortable"
                    hide-details
                    @update:model-value="$emit('update:sortOrder', $event)">
                </v-select>
                <v-btn v-if="showMoreButton"
                    variant="text"
                    class="clip-video-list__more"
                    @click="$emit('more')">
                    <span class="text-primary">もっと見る</span>
                    <Icon icon="fluent:chevron-right-12-regular" width="18px" class="ml-1 text-text-darken-1" style="margin: 0px -4px;" />
                </v-btn>
            </div>
        </div>
        <div class="clip-video-list__grid"
            :class="{
                'clip-video-list__grid--loading': isLoading,
                'clip-video-list__grid--empty': displayTotal === 0 && showEmptyMessage,
            }">
            <div class="clip-video-list__empty"
                :class="{
                    'clip-video-list__empty--show': displayTotal === 0 && showEmptyMessage && !isLoading,
                }">
                <div class="clip-video-list__empty-content">
                    <Icon class="clip-video-list__empty-icon" icon="fluent:video-clip-20-regular" width="54px" height="54px" />
                    <h2>クリップ動画がありません</h2>
                    <div class="clip-video-list__empty-submessage">録画番組からクリップを作成すると、<br class="d-sm-none">ここに表示されます。</div>
                </div>
            </div>
            <div class="clip-video-list__grid-content">
                <ClipVideoItem
                    v-for="clipVideo in displayClipVideos"
                    :key="clipVideo.id"
                    :clipVideo="clipVideo"
                    @deleted="handleClipVideoDeleted"
                    @updated="handleClipVideoUpdated"
                />
            </div>
        </div>
        <div class="clip-video-list__pagination" v-if="!hidePagination && displayTotal > 0">
            <v-pagination
                v-model="current_page"
                active-color="primary"
                density="comfortable"
                :length="Math.ceil(displayTotal / 30)"
                :total-visible="Utils.isSmartphoneVertical() ? 5 : 7"
                @update:model-value="$emit('update:page', $event)">
            </v-pagination>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { ref, watch } from 'vue';

import ClipVideoItem from '@/components/ClipVideos/ClipVideoItem.vue';
import { IClipVideo } from '@/services/ClipVideos';
import Utils from '@/utils';

type SortOrder = 'desc' | 'asc';

// Props
const props = withDefaults(defineProps<{
    title: string;
    clipVideos: IClipVideo[];
    total: number;
    page?: number;
    sortOrder?: SortOrder;
    hideHeader?: boolean;
    hideSort?: boolean;
    hidePagination?: boolean;
    showMoreButton?: boolean;
    showBackButton?: boolean;
    showEmptyMessage?: boolean;
    isLoading?: boolean;
}>(), {
    page: 1,
    sortOrder: 'desc',
    hideHeader: false,
    hideSort: false,
    hidePagination: false,
    showMoreButton: false,
    showBackButton: false,
    showEmptyMessage: true,
    isLoading: false,
});

// Emits
defineEmits<{
    (e: 'update:page', page: number): void;
    (e: 'update:sortOrder', order: SortOrder): void;
    (e: 'more'): void;
    (e: 'delete', clip_video_id: number): void;
    (e: 'clipVideoUpdated', clipVideo: IClipVideo): void;
}>();

// 現在のページ番号
const current_page = ref(props.page);

// 並び順
const sort_order = ref<SortOrder>(props.sortOrder);

// 内部で管理するクリップ動画リスト
const displayClipVideos = ref<IClipVideo[]>([...props.clipVideos]);
// 内部で管理する合計数
const displayTotal = ref<number>(props.total);

// props の page が変更されたら current_page を更新
watch(() => props.page, (newPage) => {
    current_page.value = newPage;
});

// props の sortOrder が変更されたら sort_order を更新
watch(() => props.sortOrder, (newOrder) => {
    sort_order.value = newOrder;
});

// props の clipVideos が変更されたら displayClipVideos を更新
watch(() => props.clipVideos, (newClipVideos) => {
    displayClipVideos.value = [...newClipVideos];
});

// props の total が変更されたら displayTotal を更新
watch(() => props.total, (newTotal) => {
    displayTotal.value = newTotal;
});

// クリップ動画が削除された時の処理
const handleClipVideoDeleted = (id: number) => {
    // 内部のクリップ動画リストから削除されたクリップ動画を除外
    displayClipVideos.value = displayClipVideos.value.filter(clipVideo => clipVideo.id !== id);
    // 合計数を1減らす
    displayTotal.value--;
};

// クリップ動画が更新された時の処理
const handleClipVideoUpdated = (updatedClipVideo: IClipVideo) => {
    displayClipVideos.value = displayClipVideos.value.map(clipVideo =>
        clipVideo.id === updatedClipVideo.id ? updatedClipVideo : clipVideo,
    );
    emit('clipVideoUpdated', updatedClipVideo);
};

</script>
<style lang="scss" scoped>

.clip-video-list {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;

    &--show-sort {
        .clip-video-list__grid {
            @include smartphone-vertical {
                margin-top: 3px;
            }
        }
    }

    &__header {
        display: flex;
        align-items: center;
        @include smartphone-vertical {
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

        &-back {
            display: none;
            position: absolute;
            left: -8px;
            padding: 6px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
            cursor: pointer;
            @include smartphone-vertical {
                display: flex;
            }

            & + .clip-video-list__title-text {
                @include smartphone-vertical {
                    margin-left: 32px;
                }
            }
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

            .spin {
                animation: spin 1.15s linear infinite;
            }

            @keyframes spin {
                from {
                    transform: rotate(0deg);
                }
                to {
                    transform: rotate(360deg);
                }
            }
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
        :deep(.v-field) {
            padding-right: 4px !important;
        }
        :deep(.v-field__input) {
            padding-left: 12px !important;
            padding-right: 0px !important;
        }

        .v-select {
            width: 103px;
        }
    }

    &__sort {
        :deep(.v-field__input) {
            font-size: 14px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            min-height: unset !important;
        }
    }

    &__more {
        margin-bottom: 12px;
        padding: 0px 10px;
        font-size: 15px;
        letter-spacing: 0.05em;
        @include smartphone-vertical {
            margin-bottom: 6px;
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

        &--loading {
            .clip-video-list__grid-content {
                visibility: hidden;
                opacity: 0;
            }
        }
        &--empty {
            height: 100%;
            min-height: 200px;
        }

        .clip-video-list__grid-content {
            height: 100%;
            transition: visibility 0.2s ease, opacity 0.2s ease;
        }

        :deep(.clip-video-item) {
            // 最後の項目以外の下にボーダーを追加
            &:not(:last-child) > .clip-video-item__container {
                border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
            }
        }
    }

    &__pagination {
        display: flex;
        justify-content: center;
        margin-top: 24px;
        @include smartphone-vertical {
            margin-top: 20px;
        }
    }

    &__empty {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        padding-top: 28px;
        padding-bottom: 40px;
        flex-grow: 1;
        visibility: hidden;
        opacity: 0;
        transition: visibility 0.2s ease, opacity 0.2s ease;

        &--show {
            visibility: visible;
            opacity: 1;
        }

        &-content {
            text-align: center;

            .clip-video-list__empty-icon {
                color: rgb(var(--v-theme-text-darken-1));
            }

            h2 {
                font-size: 21px;
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

            .clip-video-list__empty-submessage {
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
                    margin-top: 7px !important;
                    line-height: 1.65;
                }
            }
        }
    }
}

</style>
