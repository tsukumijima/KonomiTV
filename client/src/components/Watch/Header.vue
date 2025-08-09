<template>
    <header class="watch-header" :class="{'watch-header--video': playback_mode === 'Video'}">
        <router-link class="watch-header__back-icon" v-ripple :to="playback_mode === 'Live' ? '/tv/' : '/videos/'">
            <Icon icon="fluent:chevron-left-12-filled" width="21px" />
        </router-link>
        <img class="watch-header__broadcaster" v-if="playback_mode === 'Live'"
            :src="`${Utils.api_base_url}/channels/${channelsStore.channel.current.id}/logo`">
        <span class="watch-header__program-title" v-html="ProgramUtils.decorateProgramInfo(
            playback_mode === 'Live' ? channelsStore.channel.current.program_present : playerStore.recorded_program, 'title'
        )"></span>
        <span class="watch-header__program-time">
            {{ProgramUtils.getProgramTime(playback_mode === 'Live' ? channelsStore.channel.current.program_present : playerStore.recorded_program, true)}}
        </span>
        <v-spacer></v-spacer>
        <span class="watch-header__now">{{time}}</span>
    </header>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import type { Dayjs } from 'dayjs';

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
            Utils: Object.freeze(Utils),
            ProgramUtils: Object.freeze(ProgramUtils),

            // 現在時刻
            time: dayjs().format(Utils.isSmartphoneHorizontal() ? 'HH:mm:ss' : 'YYYY/MM/DD HH:mm:ss'),
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore),
    },
    methods: {
        formatTime(time_obj: Dayjs): string {
            const is_sp_h = Utils.isSmartphoneHorizontal();
            const formatted = time_obj.format(is_sp_h ? 'HH:mm:ss' : 'YYYY/MM/DD HH:mm:ss');
            return Utils.apply28HourClock(formatted);
        },
        updateTimeCore(): number {
            const time = dayjs();
            this.time = this.formatTime(time);
            const ms = time.millisecond();
            return ms > 800 ? 500 : 1000 - ms;
        },
        uptimeTime() {
            setTimeout(() => {
                this.uptimeTime();
            }, this.updateTimeCore());
        },
    },
    created() {
        // 初期表示の時刻を設定
        this.time = this.formatTime(dayjs());
        setTimeout(() => {
            this.uptimeTime();
        }, 1000);
    },
    beforeUnmount() {
        this.uptimeTime = ()=>{ };
    },
});

</script>
<style lang="scss" scoped>

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
        height: 50px;
        padding-left: 16px;
        padding-right: 16px;
    }

    &.watch-header--video {
        .watch-header__program-time {
            font-size: 13px;
            @include smartphone-vertical {
                display: none;
            }
        }
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
            left: -8px;
            padding: 6px;
            margin-right: -3px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
        }
        @include smartphone-horizontal {
            display: flex;
            position: relative !important;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 36px;
            height: 36px;
            left: -8px;
            padding: 6px;
            margin-right: -3px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
        }
        @include smartphone-vertical {
            display: flex;
            position: relative !important;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 36px;
            height: 36px;
            left: -8px;
            padding: 6px;
            margin-right: -6px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
        }
    }

    .watch-header__broadcaster {
        display: inline-block;
        flex-shrink: 0;
        width: 64px;
        height: 36px;
        margin-right: 18px;
        border-radius: 5px;
        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
        object-fit: cover;
        user-select: none;

        @include tablet-vertical {
            width: 48px;
            height: 28px;
            margin-right: 12px;
            border-radius: 4px;
        }
        @include smartphone-horizontal {
            width: 36px;
            height: 28px;
            margin-right: 12px;
            border-radius: 4px;
        }
        @include smartphone-vertical {
            display: none;
            margin-right: 0px;
        }
    }

    .watch-header__program-title {
        font-size: 18px;
        font-weight: bold;
        font-feature-settings: "palt" 1;  // 文字詰め
        letter-spacing: 0.05em;  // 字間を少し空ける
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;

        @include tablet-vertical {
            font-size: 16px;
        }
        @include smartphone-horizontal {
            font-size: 16px;
        }
        @include smartphone-vertical {
            font-size: 14px;
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
            font-size: 13px;
        }
    }

    .watch-header__now {
        flex-shrink: 0;
        margin-left: 16px;
        font-size: 13px;
        font-weight: 500;

        @include smartphone-horizontal {
            margin-left: 8px;
        }
        @include smartphone-vertical {
            display: none;
        }
    }
}

</style>