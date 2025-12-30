<template>
    <router-link class="timetable-channel-header" :to="`/tv/watch/${channel.display_channel_id}`"
        :style="{ width: `${width}px` }">
        <!-- チャンネルロゴ -->
        <img class="timetable-channel-header__logo" loading="lazy" decoding="async"
            :src="`${Utils.api_base_url}/channels/${channel.id}/logo`"
            :alt="channel.name">
        <!-- チャンネル情報 -->
        <div class="timetable-channel-header__info">
            <span class="timetable-channel-header__number">{{ channel.channel_number }}</span>
            <span class="timetable-channel-header__name">{{ truncatedChannelName }}</span>
        </div>
    </router-link>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import { ITimeTableChannel } from '@/services/Programs';
import Utils from '@/utils';

// Props
const props = defineProps<{
    channel: ITimeTableChannel['channel'];
    width: number;
}>();

/**
 * 幅に応じて短縮されたチャンネル名
 * 狭い幅ではチャンネル名を短くして表示する
 */
const truncatedChannelName = computed(() => {
    const name = props.channel.name;
    // 幅が狭い場合 (120px 以下) は最大6文字に制限
    if (props.width <= 120) {
        return name.length > 6 ? name.slice(0, 6) + '…' : name;
    }
    // 幅が中程度 (150px 以下) は最大10文字に制限
    if (props.width <= 150) {
        return name.length > 10 ? name.slice(0, 10) + '…' : name;
    }
    // それ以上は全文表示
    return name;
});

</script>
<style lang="scss" scoped>

.timetable-channel-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    gap: 4px;
    padding: 6px 8px;
    background: rgb(var(--v-theme-background-lighten-1));
    border-right: 1px solid rgb(var(--v-theme-background-lighten-2));
    text-decoration: none;
    color: inherit;
    cursor: pointer;
    transition: background-color 0.15s ease;

    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }

    // タッチデバイスでは hover を無効化
    @media (hover: none) {
        &:hover {
            background: rgb(var(--v-theme-background-lighten-1));
        }
    }

    // チャンネルロゴ
    &__logo {
        width: 48px;
        height: 28px;
        object-fit: contain;
        border-radius: 3px;
    }

    // チャンネル情報
    &__info {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 4px;
        min-width: 0;
        max-width: 100%;
    }

    // チャンネル番号
    &__number {
        flex-shrink: 0;
        padding: 1px 4px;
        font-size: 10px;
        font-weight: bold;
        line-height: 1;
        color: rgb(var(--v-theme-text));
        background: rgb(var(--v-theme-background-lighten-2));
        border-radius: 3px;
        white-space: nowrap;
    }

    // チャンネル名
    &__name {
        font-size: 11px;
        font-weight: 500;
        color: rgb(var(--v-theme-text));
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
}

</style>
