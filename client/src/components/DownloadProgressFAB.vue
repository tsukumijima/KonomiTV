<template>
    <Transition name="fade">
        <div v-if="hasActiveDownloads" class="download-progress-fab" @click="navigateToOfflineVideos">
            <v-progress-circular
                :model-value="totalProgress"
                :size="64"
                :width="6"
                color="success"
                class="download-progress-fab__progress"
            >
                <span class="download-progress-fab__percentage">{{ totalProgress }}%</span>
            </v-progress-circular>
            <div class="download-progress-fab__icon">
                <Icon icon="fluent:arrow-download-24-filled" width="28px" height="28px" />
            </div>
            <v-tooltip activator="parent" location="left">
                ダウンロード中: {{ activeDownloadsCount }}件
            </v-tooltip>
        </div>
    </Transition>
</template>

<script lang="ts" setup>

import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import DownloadManager from '@/services/DownloadManager';

const router = useRouter();
const route = useRoute();

// FAB を非表示にするページかどうか
const shouldHideFAB = computed(() => {
    // プレイヤーページまたはオフライン動画ページでは非表示
    return route.path.startsWith('/videos/watch/') ||
           route.path.startsWith('/streams/watch/') ||
           route.path.startsWith('/offline-videos');
});

// ダウンロード中のタスクがあるかチェック（プレイヤーページとオフライン動画ページでは非表示）
const hasActiveDownloads = computed(() => {
    if (shouldHideFAB.value) {
        return false;
    }
    return DownloadManager.hasActiveDownloads();
});

// ダウンロード中のタスク数
const activeDownloadsCount = computed(() => {
    return DownloadManager.getActiveDownloads().length;
});

// 全体の進捗
const totalProgress = computed(() => {
    return DownloadManager.getTotalProgress();
});

// オフライン視聴ページに遷移
const navigateToOfflineVideos = () => {
    router.push('/offline-videos');
};

</script>

<style lang="scss" scoped>

.download-progress-fab {
    position: fixed;
    bottom: 32px;
    right: 32px;
    z-index: 9998; // Snackbar より下、他の要素より上
    cursor: pointer;
    transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);

    // スマートフォン縦持ち時は下部ナビゲーションを避ける
    @include smartphone-vertical {
        bottom: calc(env(safe-area-inset-bottom) + 72px);
        right: 16px;
    }

    // タブレット・スマートフォン横持ち時
    @include smartphone-horizontal {
        bottom: 16px;
        right: 16px;
    }

    &:hover {
        transform: scale(1.1);
    }

    &__progress {
        position: relative;
        filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
    }

    &__percentage {
        font-size: 14px;
        font-weight: bold;
        color: rgb(var(--v-theme-success));
    }

    &__icon {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: rgb(var(--v-theme-success));
        pointer-events: none;
        opacity: 0.3;
    }
}

// フェードアニメーション
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

</style>