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
        <span class="watch-header__now">
            <Icon v-if="is_showing_original_broadcast_time" class="watch-header__timeshift-icon" icon="fluent:history-16-regular" width="16px" />
            {{time}}
        </span>
    </header>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import type { Dayjs } from 'dayjs';

import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
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

            // 現在時刻 (ライブ再生時は現在時刻、録画再生時は設定に応じて録画当時の時刻または現在時刻)
            time: dayjs().format(Utils.isSmartphoneHorizontal() ? 'HH:mm:ss' : 'YYYY/MM/DD HH:mm:ss'),

            // 録画再生時の再生位置 (秒)
            playback_position: 0,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore, useSettingsStore),

        // 元の放送時刻を表示すべきかどうか
        // 録画再生時かつ設定がオンの場合に true
        is_showing_original_broadcast_time(): boolean {
            return this.playback_mode === 'Video' && this.settingsStore.settings.show_original_broadcast_time_during_playback === true;
        },
    },
    methods: {
        formatTime(time_obj: Dayjs): string {
            const is_sp_h = Utils.isSmartphoneHorizontal();
            const formatted = time_obj.format(is_sp_h ? 'HH:mm:ss' : 'YYYY/MM/DD HH:mm:ss');
            return Utils.apply28HourClock(formatted);
        },
        // 元の放送時刻を計算する
        getOriginalBroadcastTime(): Dayjs {
            const recorded_program = this.playerStore.recorded_program;
            // 録画開始時刻を取得 (recording_start_time があればそちらを優先、なければ番組の開始時刻を使用)
            const recording_start_time = recorded_program.recorded_video.recording_start_time ?? recorded_program.start_time;
            // 録画開始時刻に再生位置を加算して元の放送時刻を計算
            return dayjs(recording_start_time).add(this.playback_position, 'second');
        },
        updateTimeCore(): number {
            // 元の放送時刻を表示すべき場合は、元の放送時刻を計算して表示
            if (this.is_showing_original_broadcast_time === true) {
                // 再生中の場合のみ、元の放送時刻を計算して表示
                // 一時停止中の場合は、一時停止した時点の時刻がそのまま表示される
                if (this.playerStore.is_video_paused === false) {
                    this.time = this.formatTime(this.getOriginalBroadcastTime());
                }
                // 再生位置から計算した時刻なので、現在時刻の秒境界に同期させる必要はない
                // 単に 1 秒ごとに更新する
                return 1000;
            } else {
                // 通常は現在時刻を表示
                const now = dayjs();
                this.time = this.formatTime(now);
                // 現在時刻モードでは秒の境界にぴったり合わせて更新
                const ms = now.millisecond();
                return ms > 800 ? 500 : 1000 - ms;
            }
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

        // 録画再生時: 再生位置が変更されたときに playback_position を更新
        this.playerStore.event_emitter.on('PlaybackPositionChanged', (event) => {
            this.playback_position = event.playback_position;
            // シーク時は即座に表示を更新
            if (this.is_showing_original_broadcast_time === true) {
                this.time = this.formatTime(this.getOriginalBroadcastTime());
            }
        });
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
        display: flex;
        align-items: center;
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

        .watch-header__timeshift-icon {
            flex-shrink: 0;
            margin-right: 4px;
            opacity: 0.8;
        }
    }
}

</style>