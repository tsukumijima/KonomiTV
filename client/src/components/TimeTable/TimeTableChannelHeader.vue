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
            <span class="timetable-channel-header__name">{{ channel.name }}</span>
        </div>
    </router-link>
</template>
<script lang="ts" setup>

import { ITimeTableChannel } from '@/services/Programs';
import Utils from '@/utils';

// Props
defineProps<{
    channel: ITimeTableChannel['channel'];
    width: number;
}>();

</script>
<style lang="scss" scoped>

.timetable-channel-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    padding: 4px 8px;
    background: rgb(var(--v-theme-background-lighten-1));
    border-right: 1px solid rgb(var(--v-theme-background-lighten-2));
    text-decoration: none;
    color: inherit;
    cursor: pointer;
    transition: background-color 0.15s ease;

    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }

    // チャンネルロゴ
    &__logo {
        width: 40px;
        height: 24px;
        object-fit: contain;
        border-radius: 2px;
    }

    // チャンネル情報
    &__info {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-top: 2px;
        min-width: 0;
        max-width: 100%;
    }

    // チャンネル番号
    &__number {
        font-size: 10px;
        font-weight: bold;
        color: rgb(var(--v-theme-text-darken-1));
        white-space: nowrap;
    }

    // チャンネル名
    &__name {
        font-size: 11px;
        color: rgb(var(--v-theme-text));
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
}

</style>
