<template>
    <div class="capture-list">
        <div class="capture-list__header" v-if="!hideHeader">
            <h2 class="capture-list__title">
                <span class="capture-list__title-text">{{ title }}</span>
                <div class="capture-list__title-count">
                    <template v-if="isLoading">
                        <Icon icon="line-md:loading-twotone-loop" class="mr-1 spin" width="20px" height="20px" />
                    </template>
                    <template v-else>{{ captures.length }}件</template>
                </div>
            </h2>
            <div class="capture-list__actions">
                <v-btn v-if="showRefreshButton"
                    variant="text"
                    class="capture-list__refresh-button mr-2"
                    :loading="isLoading"
                    :disabled="isLoading"
                    @click="$emit('refresh')">
                    <Icon icon="fluent:arrow-sync-16-regular" width="20px" height="20px" />
                    <span class="ml-1">更新</span>
                </v-btn>
                <v-btn v-if="showMoreButton"
                    variant="text"
                    class="capture-list__more"
                    @click="$emit('more')">
                    <span class="text-primary">もっと見る</span>
                    <Icon icon="fluent:chevron-right-12-regular" width="18px" class="ml-1 text-text-darken-1" style="margin: 0px -4px;" />
                </v-btn>
            </div>
        </div>
        <div class="capture-list__grid"
            :class="{
                'capture-list__grid--loading': isLoading,
                'capture-list__grid--empty': captures.length === 0 && showEmptyMessage,
            }">
            <div class="capture-list__empty"
                :class="{
                    'capture-list__empty--show': captures.length === 0 && showEmptyMessage && !isLoading,
                }">
                <div class="capture-list__empty-content">
                    <Icon class="capture-list__empty-icon" :icon="emptyIcon" width="54px" height="54px" />
                    <h2 v-html="emptyMessage"></h2>
                    <div class="capture-list__empty-submessage"
                        v-if="emptySubMessage" v-html="emptySubMessage"></div>
                </div>
            </div>
            <div class="capture-list__grid-content">
                <v-card v-for="capture in captures" :key="capture.name" class="capture-card" @click="openDrawer(capture)">
                    <v-img :src="capture.url" aspect-ratio="1.7778" class="align-end">
                        <v-card-title class="capture-card__title">
                            <div v-if="capture.program_title" class="capture-card__title-text">{{ capture.program_title }}</div>
                            <div v-else class="capture-card__title-text">{{ capture.name }}</div>
                            <div v-if="capture.time" class="capture-card__title-time">{{ dayjs(capture.time).format('YYYY/MM/DD HH:mm:ss') }}</div>
                        </v-card-title>
                    </v-img>
                </v-card>
            </div>
        </div>
        <CaptureDetailDrawer v-model="is_drawer_showing" :capture="selected_capture" @delete="$emit('delete')" />
        <div class="capture-list__image-viewer" :class="{'capture-list__image-viewer--visible': is_drawer_showing}">
            <v-img v-if="selected_capture" :src="selected_capture.url" cover class="capture-list__image-viewer-image"></v-img>
        </div>
    </div>
</template>
<script lang="ts" setup>
import { ref } from 'vue';
import CaptureDetailDrawer from '@/components/Captures/CaptureDetailDrawer.vue';
import { ICapture } from '@/services/Captures';
import { dayjs } from '@/utils';
withDefaults(defineProps<{
    title: string;
    captures: ICapture[];
    hideHeader?: boolean;
    showRefreshButton?: boolean;
    showMoreButton?: boolean;
    showEmptyMessage?: boolean;
    emptyIcon?: string;
    emptyMessage?: string;
    emptySubMessage?: string;
    isLoading?: boolean;
}>(), {
    hideHeader: false,
    showRefreshButton: false,
    showMoreButton: false,
    showEmptyMessage: true,
    emptyIcon: 'fluent:image-multiple-24-regular',
    emptyMessage: 'キャプチャはまだありません。',
    emptySubMessage: '視聴画面からキャプチャを撮影できます。',
    isLoading: false,
});
defineEmits<{
    (e: 'refresh'): void;
    (e: 'more'): void;
    (e: 'delete'): void;
}>();
// ドロワーの表示状態
const is_drawer_showing = ref(false);
const selected_capture = ref<ICapture | null>(null);
// ドロワーを開く
const openDrawer = (capture: ICapture) => {
    // すでに同じキャプチャでドロワーが開いている場合は閉じる
    if (is_drawer_showing.value && selected_capture.value?.name === capture.name) {
        is_drawer_showing.value = false;
        selected_capture.value = null;
    } else {
        selected_capture.value = capture;
        is_drawer_showing.value = true;
    }
};
</script>
<style lang="scss" scoped>
.capture-list {
    position: relative;
    &__image-viewer {
        position: fixed;
        top: 0;
        left: 0;
        right: 370px;
        bottom: 0;
        background: transparent;
        z-index: 1009;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 48px;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.25s ease, visibility 0.25s ease;
        pointer-events: none;
        &--visible {
            opacity: 1;
            visibility: visible;
        }
        @media (max-width: 960px) {
            display: none;
        }
    }
    &__image-viewer-image {
        max-width: 100%;
        max-height: 100%;
        border-radius: 8px;
    }
    &__header {
        display: flex;
        align-items: center;
        padding: 0px 8px;
    }
    &__title {
        display: flex;
        align-items: center;
        font-size: 24px;
        font-weight: 700;
        padding-top: 8px;
        padding-bottom: 20px;
    }
    &__title-count {
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
    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
    }
    &__refresh-button {
        padding: 0 10px;
        font-size: 15px;
        letter-spacing: 0.05em;
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
        position: relative;
        border-radius: 8px;
        overflow: hidden;
        background: rgb(var(--v-theme-background-lighten-1));
        padding: 16px;
        transition: padding-right 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
        &--drawer-visible {
            padding-right: 370px;
            @media (max-width: 480px) {
                padding-right: calc(100vw - 32px);
            }
        }
        &--loading {
            .capture-list__grid-content {
                visibility: hidden;
                opacity: 0;
            }
        }
        &--empty {
            min-height: 200px;
        }
    }
    &__grid-content {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 16px;
        transition: visibility 0.2s ease, opacity 0.2s ease;
    }
    .capture-card {
        cursor: pointer;
        transition: all 0.2s ease-in-out;
        &:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        }
    }
    .capture-card__title {
        background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0) 100%);
        color: white;
        padding: 12px 16px;
        white-space: normal;
        line-height: 1.5;
    }
    .capture-card__title-text {
        font-size: 1rem;
        font-weight: 700;
    }
    .capture-card__title-time {
        font-size: 0.8rem;
        opacity: 0.9;
        margin-top: 2px;
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
        padding-bottom: 12px;
        visibility: hidden;
        opacity: 0;
        transition: visibility 0.2s ease, opacity 0.2s ease;
        &--show {
            visibility: visible;
            opacity: 1;
        }
        &-content {
            text-align: center;
            .capture-list__empty-icon {
                color: rgb(var(--v-theme-text-darken-1));
            }
            h2 {
                margin-top: 4px;
                font-size: 21px;
            }
            .capture-list__empty-submessage {
                margin-top: 8px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 15px;
            }
        }
    }
}
</style>