<template>
    <div class="capture-detail-drawer__scrim"
        :class="{ 'capture-detail-drawer__scrim--visible': isVisible }"
        @click="handleClose"></div>

    <div class="capture-detail-drawer"
        :class="{
            'capture-detail-drawer--visible': isVisible,
            'capture-detail-drawer--bottom-sheet': display.smAndDown.value,
        }">
        <div class="capture-detail-drawer__header">
            <div class="capture-detail-drawer__title">キャプチャ情報</div>
            <v-spacer></v-spacer>
            <v-btn icon variant="flat" @click="handleClose">
                <v-icon icon="mdi-close" />
            </v-btn>
        </div>

        <v-img v-if="capture && display.smAndDown.value" :src="capture.url" aspect-ratio="1.7778" class="capture-detail-drawer__image"></v-img>

        <div v-if="capture" class="capture-detail-drawer__content">
            <div class="capture-detail-drawer__property">
                <div class="capture-detail-drawer__property-label">ファイル名</div>
                <div class="capture-detail-drawer__property-value">{{ capture.name }}</div>
            </div>
            <div v-if="capture.time" class="capture-detail-drawer__property">
                <div class="capture-detail-drawer__property-label">時間</div>
                <div class="capture-detail-drawer__property-value">{{ dayjs(capture.time).format('YYYY/MM/DD HH:mm:ss') }}</div>
            </div>
            <div v-if="capture.program_title" class="capture-detail-drawer__property">
                <div class="capture-detail-drawer__property-label">番組</div>
                <div class="capture-detail-drawer__property-value">{{ capture.channel_name }} - {{ capture.program_title }}</div>
            </div>
            <div class="capture-detail-drawer__property">
                <div class="capture-detail-drawer__property-label">サイズ</div>
                <div class="capture-detail-drawer__property-value">{{ Utils.formatBytes(capture.size) }}</div>
            </div>
        </div>

        <div class="capture-detail-drawer__footer">
            <v-btn
                v-if="!display.smAndDown.value"
                class="mb-4"
                block
                size="large"
                variant="tonal"
                @click="isFullscreenShowing = true">
                <v-icon icon="mdi-fullscreen" class="mr-1" size="large" />
                <span>全画面表示</span>
            </v-btn>
            <v-btn color="secondary" block size="large" @click="downloadCapture">
                <v-icon icon="mdi-download" class="mr-2" />
                <span>ダウンロード</span>
            </v-btn>
            <v-btn class="mt-4" color="error" block size="large" @click="deleteCapture">
                <v-icon icon="mdi-delete" class="mr-2" />
                <span>削除</span>
            </v-btn>
        </div>
    </div>

    <!-- 全画面表示ビューワー -->
    <div v-if="isFullscreenShowing && capture" class="fullscreen-viewer" @click.self="isFullscreenShowing = false">
        <img :src="capture.url" class="fullscreen-viewer__image" @click.stop>
        <v-btn
            class="fullscreen-viewer__close-button"
            icon="mdi-close"
            size="large"
            variant="flat"
            @click="isFullscreenShowing = false">
        </v-btn>
    </div>

    <!-- 削除確認ダイアログ -->
    <v-dialog v-model="isDeleteDialogShowing" max-width="715">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                キャプチャを削除しますか？
            </v-card-title>
                <div v-if="capture" class="mb-4 text-center">
                    <div class="text-h7 text-text mb-2">{{ capture.name }}</div>
                </div>
            <v-card-text class="pt-2 pb-0">
                <div class="warning-banner warning-banner--normal">
                    <Icon icon="fluent:info-16-regular" class="warning-banner__icon" />
                    <span class="warning-banner__text warning-banner__text--large">
                        この操作は元に戻せません。
                    </span>
                </div>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer></v-spacer>
                <v-btn color="text" variant="text" @click="isDeleteDialogShowing = false">
                    <Icon icon="fluent:dismiss-20-regular" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn class="px-3" color="error" variant="flat" @click="confirmDelete">
                    <Icon icon="fluent:delete-20-regular" width="18px" height="18px" />
                    <span class="ml-1">削除</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script lang="ts" setup>
import { onUnmounted,computed, ref, watch } from 'vue';
import { useDisplay } from 'vuetify';

import Message from '@/message';
import { Captures, ICapture } from '@/services/Captures';
import Utils, { dayjs } from '@/utils';

const props = defineProps<{
    capture: ICapture | null;
    modelValue: boolean;
}>();

const emit = defineEmits<{
    (e: 'update:modelValue', value: boolean): void;
    (e: 'delete'): void;
}>();

const display = useDisplay();
const isFullscreenShowing = ref(false);
const isVisible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value),
});

// ドロワーが開かれたら、ページ全体のスクロールを無効化する
watch(isVisible, (newValue) => {
    if (newValue) {
        document.documentElement.classList.add('v-overlay-scroll-blocked');
    } else {
        // フルスクリーン表示がアクティブでない場合のみスクロールロックを解除
        if (isFullscreenShowing.value === false) {
            document.documentElement.classList.remove('v-overlay-scroll-blocked');
        }
    }
});

// フルスクリーン表示が開かれたら、ページ全体のスクロールを無効化する
watch(isFullscreenShowing, (newValue) => {
    if (newValue) {
        document.documentElement.classList.add('v-overlay-scroll-blocked');
    } else {
        // ドロワーが非表示の場合のみスクロールロックを解除
        if (isVisible.value === false) {
            document.documentElement.classList.remove('v-overlay-scroll-blocked');
        }
    }
});

// コンポーネントがアンマウントされる際にスクロールロックを解除
onUnmounted(() => {
    document.documentElement.classList.remove('v-overlay-scroll-blocked');
});

const handleClose = () => {
    isVisible.value = false;
};
const downloadCapture = async () => {
    if (!props.capture) return;
    try {
        const response = await fetch(props.capture.url);
        if (!response.ok) {
            throw new Error('Failed to fetch capture image.');
        }
        const blob = await response.blob();
        Utils.downloadBlobData(blob, props.capture.name);
        Message.success('キャプチャをダウンロードしました。');
    } catch (error) {
        console.error('Failed to download capture:', error);
        Message.error('キャプチャのダウンロードに失敗しました。');
    }
};
const isDeleteDialogShowing = ref(false);
const deleteCapture = async () => {
    if (!props.capture) return;
    isDeleteDialogShowing.value = true;
};
const confirmDelete = async () => {
    if (!props.capture) return;
    isDeleteDialogShowing.value = false;
    const result = await Captures.deleteCapture(props.capture.url);
    if (result) {
        Message.success('キャプチャを削除しました。');
        emit('delete');
        handleClose();
    }
};

</script>

<style lang="scss" scoped>
.warning-banner {
    display: flex;
    align-items: center;
    padding: 12px;
    border-radius: 5px;
    color: rgb(var(--v-theme-text));
    background-color: rgb(var(--v-theme-background-lighten-2));
    &--normal {
        background-color: rgb(var(--v-theme-background-lighten-2));
    }
    &--recording {
        color: rgb(var(--v-theme-error));
        background-color: rgba(var(--v-theme-error), 0.1);
    }
    &--keyword {
        color: rgb(var(--v-theme-secondary));
        background-color: rgba(var(--v-theme-secondary), 0.1);
    }
    &__icon {
        flex-shrink: 0;
        margin-right: 8px;
    }
    &__text {
        font-size: 13.5px;
        &--large {
            font-size: 15px;
        }
    }
}
.capture-detail-drawer__scrim {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1008;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.25s ease, visibility 0.25s ease;
    pointer-events: none;
    &--visible {
        opacity: 1;
        visibility: visible;
        pointer-events: auto;
    }
}
.capture-detail-drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 370px;
    display: flex;
    flex-direction: column;
    background: rgb(var(--v-theme-background));
    border-top-left-radius: 16px;
    border-bottom-left-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16);
    z-index: 1010;
    transform: translateX(100%);
    transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1), border-radius 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
    &--visible {
        transform: translateX(0);
    }
    // ボトムシート用のスタイル
    &--bottom-sheet {
        top: auto;
        left: 0;
        right: 0;
        bottom: 0;
        width: 100% !important;
        border-top-left-radius: 16px;
        border-top-right-radius: 16px;
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        transform: translateY(100%);
        &.capture-detail-drawer--visible {
            transform: translateY(0);
        }
    }
    @media (max-width: 480px) {
        width: calc(100vw - 32px);
    }
    &__header {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        padding: 8px 8px 8px 20px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-top-left-radius: 16px;
        border-top-right-radius: 0;
        transition: border-radius 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
        .capture-detail-drawer--bottom-sheet & {
            border-top-right-radius: 16px;
        }
    }
    &__title {
        font-size: 20px;
        font-weight: 700;
    }
    &__image {
        flex-shrink: 0;
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
    }
    &__content {
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        padding: 24px;
        overflow-y: auto;
    }
    &__property {
        margin-bottom: 20px;
        &:last-of-type {
            margin-bottom: 0;
        }
    }
    &__property-label {
        font-size: 13px;
        color: rgb(var(--v-theme-text-darken-1));
        margin-bottom: 6px;
    }
    &__property-value-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
    }
    &__property-value {
        font-size: 15px;
        font-weight: 500;
        &--path {
            font-family: 'M PLUS 1p', sans-serif;
            word-break: break-all;
            line-height: 1.6;
        }
    }
    &__fullscreen-button {
        margin-top: 12px;
        align-self: flex-end;
    }
    &__footer {
        padding: 16px;
        border-top: 1px solid rgb(var(--v-theme-background-lighten-2));
    }
}
.fullscreen-viewer {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    z-index: 1011; // ドロワーより手前に表示
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 0px 16px;
    cursor: zoom-out;
    &__image {
        max-width: 100%;
        max-height: 100%;
        border-radius: 4px;
        box-shadow: 0 0 40px rgba(0, 0, 0, 0.5);
        cursor: default;
        @media (max-width: 600px) {
            transform: rotate(90deg);
            max-width: 100vh;
            max-height: 100vw;
        }
    }
    &__close-button {
        position: absolute;
        right: 16px;
        bottom: 16px;
        background-color: rgba(0, 0, 0, 0.5);
        color: white;
        &:hover {
            background-color: rgba(0, 0, 0, 0.7);
        }
    }
}
</style>