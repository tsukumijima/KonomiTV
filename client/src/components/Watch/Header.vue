<template>
<header class="watch-header">
    <router-link class="watch-header__back-icon" v-ripple :to="playback_mode === 'Live' ? '/tv/' : '/video/'">
        <Icon icon="fluent:arrow-left-12-filled" width="25px" />
    </router-link>
    <img class="watch-header__broadcaster" :src="`${Utils.api_base_url}/channels/${(channelsStore.display_channel_id)}/logo`">
    <span class="watch-header__program-title"
        v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_present, 'title')">
    </span>
    <span class="watch-header__program-time">
        {{ProgramUtils.getProgramTime(channelsStore.channel.current.program_present, true)}}
    </span>
    <v-spacer></v-spacer>
    <span class="watch-header__now">{{time}}</span>
</header>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import Utils, { dayjs, ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'Watch-Header',
    props: {
        playback_mode: {
            type: String as PropType<'Live' | 'Video'>,
            required: true,
        },
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ProgramUtils: ProgramUtils,

            // 現在時刻
            time: dayjs().format('YYYY/MM/DD HH:mm:ss'),

            // 現在時刻更新用のインターバルの ID
            time_interval_id: 0,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore),
    },
    created() {
        // 現在時刻を1秒おきに更新
        this.time_interval_id = window.setInterval(() => this.time = dayjs().format('YYYY/MM/DD HH:mm:ss'), 1 * 1000);
    },
    beforeUnmount() {
        // インターバルをクリア
        window.clearInterval(this.time_interval_id);
    },
});

</script>
<style lang="scss">

.watch-header {
    display: flex;
    align-items: center;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 82px;
    padding-left: calc(68px + 30px);
    padding-right: 30px;
    background: linear-gradient(to bottom, #000000cf, transparent);
    transition: opacity 0.3s, visibility 0.3s;
    opacity: 0;
    visibility: hidden;
    z-index: 5;

    @include tablet-vertical {
        height: 66px;
        padding-left: 16px;
        padding-right: 16px;
    }
    @include smartphone-horizontal {
        padding-left: calc(68px + 16px);
        padding-right: 16px;
    }
    @include smartphone-horizontal {
        height: 66px;
        padding-left: calc(0px + 16px);
    }
    @include smartphone-vertical {
        display: none;
        height: 50px;
        padding-left: 16px;
        padding-right: 16px;
    }

    .watch-header__back-icon {
        display: none;
        @include tablet-vertical {
            display: flex;
            position: relative !important;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 40px;
            height: 40px;
            left: -6px;
            padding: 6px;
            margin-right: 2px;
            border-radius: 50%;
            color: var(--v-text-base);
        }
        @include smartphone-horizontal {
            display: flex;
            position: relative !important;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 36px;
            height: 36px;
            left: -6px;
            padding: 6px;
            margin-right: 2px;
            border-radius: 50%;
            color: var(--v-text-base);
        }
        @include smartphone-vertical {
            display: flex;
            position: relative !important;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 36px;
            height: 36px;
            left: -6px;
            padding: 6px;
            margin-right: 2px;
            border-radius: 50%;
            color: var(--v-text-base);
        }
    }

    .watch-header__broadcaster {
        display: inline-block;
        flex-shrink: 0;
        width: 64px;
        height: 36px;
        border-radius: 5px;
        background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
        object-fit: cover;
        user-select: none;

        @include tablet-vertical {
            width: 48px;
            height: 28px;
            border-radius: 4px;
        }
        @include smartphone-horizontal {
            width: 48px;
            height: 28px;
            border-radius: 4px;
        }
        @include smartphone-vertical {
            display: none;
        }
    }

    .watch-header__program-title {
        margin-left: 18px;
        font-size: 18px;
        font-weight: bold;
        font-feature-settings: "palt" 1;  // 文字詰め
        letter-spacing: 0.05em;  // 字間を少し空ける
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;

        @include tablet-vertical {
            margin-left: 12px;
            font-size: 16px;
        }
        @include smartphone-horizontal {
            margin-left: 12px;
            font-size: 16px;
        }
        @include smartphone-vertical {
            margin-left: 0px;
            font-size: 16px;
        }
    }

    .watch-header__program-time {
        flex-shrink: 0;
        margin-left: 16px;
        font-size: 15px;
        font-weight: 500;

        @include smartphone-horizontal {
            margin-left: 8px;
            font-size: 14px;
        }
        @include smartphone-vertical {
            margin-left: 8px;
            font-size: 14px;
        }
    }

    .watch-header__now {
        flex-shrink: 0;
        margin-left: 16px;
        font-size: 13px;
        font-weight: 500;

        @include smartphone-horizontal {
            display: none;
        }
        @include smartphone-vertical {
            display: none;
        }
    }
}

</style>