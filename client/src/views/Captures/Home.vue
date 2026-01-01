<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="captures-container-wrapper">
                <SPHeaderBar />
                <div class="captures-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'トップ', path: '/' },
                        { name: 'キャプチャ', path: '/captures/', disabled: true },
                    ]" />
                    <CaptureList
                        class="captures-container__list"
                        :class="{'captures-container__list--loading': captures.length === 0 && is_loading}"
                        title="最近のキャプチャ"
                        :captures="captures"
                        :is-loading="is_loading"
                        :show-more-button="true"
                        @more="$router.push('/captures/all/')"
                        @delete="fetchAllCaptures"
                    />
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>
import { onMounted, onUnmounted, ref } from 'vue';
import Breadcrumbs from '@/components/Breadcrumbs.vue';
import CaptureList from '@/components/Captures/CaptureList.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import { Captures, ICapture } from '@/services/Captures';
// キャプチャのリスト
const captures = ref<ICapture[]>([]);
const is_loading = ref(true);
const autoRefreshInterval = ref<number | null>(null);
// 自動更新の間隔 (ミリ秒)
const AUTO_REFRESH_INTERVAL = 30 * 1000;  // 30秒
// 表示上限
const DISPLAY_LIMIT = 6;
// キャプチャリストを取得
const fetchAllCaptures = async () => {
    is_loading.value = true;
    const result = await Captures.fetchCaptures();
    if (result) {
        // 最近のキャプチャのみ表示
        captures.value = result.slice(0, DISPLAY_LIMIT);
    }
    is_loading.value = false;
};
// 自動更新を開始
const startAutoRefresh = () => {
    if (autoRefreshInterval.value === null) {
        fetchAllCaptures(); // 初回更新
        autoRefreshInterval.value = window.setInterval(fetchAllCaptures, AUTO_REFRESH_INTERVAL);
    }
};
// 自動更新を停止
const stopAutoRefresh = () => {
    if (autoRefreshInterval.value !== null) {
        clearInterval(autoRefreshInterval.value);
        autoRefreshInterval.value = null;
    }
};
onMounted(() => {
    startAutoRefresh();
});
onUnmounted(() => {
    stopAutoRefresh();
});
</script>
<style lang="scss" scoped>
.captures-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;
}
.captures-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    padding: 20px;
    margin: 0 auto;
    min-width: 0;
    max-width: 1200px;
    @include smartphone-horizontal {
        padding: 16px 20px !important;
    }
    @include smartphone-vertical {
        padding: 8px 8px 20px !important;
    }
    &__list--loading {
        :deep(.capture-list__grid) {
            min-height: 180px;
        }
    }
}
</style>