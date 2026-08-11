<template>
    <router-link v-if="variant === 'header'" v-ripple class="offline-download-badge" to="/offline-videos/"
        v-ftooltip="activeJobCount > 0 ? `${activeJobCount}件のオフライン保存を処理中` : 'オフライン保存'">
        <Icon icon="fluent:cloud-arrow-down-16-regular" width="23px" />
        <span v-if="activeJobCount > 0">{{activeJobCount}}</span>
    </router-link>
    <span v-else-if="variant === 'overlay' && activeJobCount > 0" class="offline-download-badge__overlay">{{activeJobCount}}</span>
</template>
<script lang="ts" setup>

import { useOfflineDownloadJobCount } from '@/utils/useOfflineDownloadJobCount';

withDefaults(defineProps<{
    // header: ヘッダー用の独立リンク / overlay: ナビゲーションアイコン上の件数バッジ
    variant?: 'header' | 'overlay';
}>(), {
    variant: 'header',
});

const { activeJobCount } = useOfflineDownloadJobCount();

</script>
<style lang="scss" scoped>

.offline-download-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    width: 42px;
    height: 42px;
    border-radius: 50%;
    color: rgb(var(--v-theme-text));

    @include smartphone-vertical {
        margin-top: 4px;
        width: 36px;
        height: 36px;
    }

    span {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        top: 1px;
        right: 0;
        min-width: 17px;
        height: 17px;
        padding: 0 4px;
        border-radius: 9px;
        color: white;
        background: rgb(var(--v-theme-primary));
        font-size: 10px;
        font-weight: bold;
    }
}

.offline-download-badge__overlay {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: -2px;
    right: -6px;
    min-width: 17px;
    height: 17px;
    padding: 0 4px;
    border-radius: 9px;
    color: white;
    background: rgb(var(--v-theme-primary));
    font-size: 10px;
    font-weight: bold;
    pointer-events: none;
}

</style>
