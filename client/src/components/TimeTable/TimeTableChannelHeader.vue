<template>
    <router-link class="timetable-channel-header" :to="`/tv/watch/${channel.display_channel_id}`"
        v-ftooltip.bottom="tooltipText"
        :style="{
            width: `${width}px`,
            height: `${height}px`,
            '--timetable-channel-logo-width': `${logoWidth}px`,
            '--timetable-channel-logo-height': `${logoHeight}px`,
            '--timetable-channel-number-size': `${numberFontSize}px`,
            '--timetable-channel-name-size': `${nameFontSize}px`,
        }">
        <!-- チャンネルロゴ -->
        <div class="timetable-channel-header__logo-wrapper">
            <img class="timetable-channel-header__logo" loading="lazy" decoding="async"
                :src="`${Utils.api_base_url}/channels/${channel.id}/logo`"
                :alt="channel.name">
        </div>
        <!-- チャンネル情報 -->
        <div class="timetable-channel-header__info">
            <span class="timetable-channel-header__number">{{ channel.channel_number }}</span>
            <span class="timetable-channel-header__name">{{ channel.name }}</span>
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
    height: number;
    // ウィンドウリサイズ時に再計算をトリガーするためのカウンター (親から受け取る)
    resizeTrigger: number;
}>();

const logoWidth = computed(() => {
    return Math.round(Math.min(46, Math.max(32, props.width * 0.27)));
});

const logoHeight = computed(() => {
    return Math.round(logoWidth.value * (3 / 4));
});

const numberFontSize = computed(() => {
    return Math.min(14, Math.max(13, props.width * 0.06));
});

const nameFontSize = computed(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _trigger = props.resizeTrigger;
    return Math.min(13.5, Math.max(Utils.isSmartphoneVertical() ? 10 : 12, props.width * 0.08));
});

const tooltipText = computed(() => {
    return `${props.channel.name} を視聴`;
});

</script>
<style lang="scss" scoped>

.timetable-channel-header {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    flex-shrink: 0;
    box-sizing: border-box;
    gap: 6px;
    padding: 0px 4px;
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
    &__logo-wrapper {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        width: var(--timetable-channel-logo-width);
        height: var(--timetable-channel-logo-height);
        border-radius: 4px;
        overflow: hidden;
        background: rgb(var(--v-theme-background-lighten-2));
    }

    &__logo {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    // チャンネル情報
    &__info {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
        min-width: 0;
        max-width: 100%;
    }

    // チャンネル番号
    &__number {
        flex-shrink: 0;
        padding: 0px 1px;
        font-size: var(--timetable-channel-number-size);
        font-weight: bold;
        line-height: 1;
        color: rgb(var(--v-theme-text));
        border-radius: 3px;
        white-space: nowrap;
    }

    // チャンネル名
    &__name {
        font-size: var(--timetable-channel-name-size);
        font-weight: 500;
        color: rgb(var(--v-theme-text));
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
        max-width: 100%;
    }
}

</style>
