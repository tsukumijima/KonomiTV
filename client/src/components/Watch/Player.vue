<template>
    <div class="watch-player" :class="{
        'watch-player--loading': playerStore.is_loading,
        'watch-player--virtual-keyboard-display': playerStore.is_virtual_keyboard_display && Utils.hasActiveElementClass('dplayer-comment-input'),
        'watch-player--video': playback_mode === 'Video',
    }">
        <div class="watch-player__background-wrapper">
            <div class="watch-player__background" :class="{
                'watch-player__background--display': playerStore.is_background_display,
                'watch-player__background--background-hide': settingsStore.settings.show_player_background_image === false,
            }"
                :style="{backgroundImage: `url(${playerStore.background_url})`}">
                <img class="watch-player__background-logo" src="/assets/images/logo.svg">
            </div>
        </div>
        <v-progress-circular indeterminate size="60" width="6" class="watch-player__buffering"
            :class="{'watch-player__buffering--display': playerStore.is_video_buffering}">
        </v-progress-circular>
        <div class="watch-player__dplayer"></div>
        <div class="watch-player__dplayer-setting-cover"
            :class="{'watch-player__dplayer-setting-cover--display': playerStore.is_player_setting_panel_open}"
            @click="handleSettingCoverClick"></div>
        <div class="watch-player__button"
                @mousemove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})"
                @touchmove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})"
                @click="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})">
            <div v-ripple class="switch-button switch-button-up" v-ftooltip.top="'前のチャンネル'" v-if="playback_mode === 'Live'"
                @click="playerStore.is_zapping = true; $router.push({path: `/tv/watch/${channelsStore.channel.previous.display_channel_id}`})">
                <Icon class="switch-button-icon" icon="fluent:ios-arrow-left-24-filled" width="32px" style="transform: rotate(90deg)" />
            </div>
            <div v-ripple class="switch-button switch-button-panel"
                :class="{'switch-button-panel--open': playerStore.is_panel_display}"
                @click="playerStore.is_panel_display = !playerStore.is_panel_display">
                <Icon class="switch-button-icon" icon="fluent:navigation-16-filled" width="32px" />
            </div>
            <div v-ripple class="switch-button switch-button-down" v-ftooltip.bottom="'次のチャンネル'" v-if="playback_mode === 'Live'"
                    @click="playerStore.is_zapping = true; $router.push({path: `/tv/watch/${channelsStore.channel.next.display_channel_id}`})">
                <Icon class="switch-button-icon" icon="fluent:ios-arrow-right-24-filled" width="33px" style="transform: rotate(90deg)" />
            </div>
        </div>
    </div>
</template>
<script setup lang="ts">

import { PropType } from 'vue';

import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';

// Props の定義
defineProps({
    playback_mode: {
        type: String as PropType<'Live' | 'Video'>,
        required: true,
    },
});

// Store の初期化
const channelsStore = useChannelsStore();
const playerStore = usePlayerStore();
const settingsStore = useSettingsStore();

// watch-player__dplayer-setting-cover がクリックされたとき、設定パネルを閉じる
const handleSettingCoverClick = () => {
    const dplayer_mask = document.querySelector<HTMLDivElement>('.dplayer-mask');
    if (dplayer_mask) {
        // dplayer-mask をクリックすることで、player.setting.hide() が内部的に呼び出され、設定パネルが閉じられる
        dplayer_mask.click();
    }
};

</script>
<style lang="scss">

// DPlayer のデフォルトスタイルを上書き
.watch-player__dplayer {
    @include smartphone-vertical {
        overflow: visible !important;
    }
    svg circle, svg path {
        fill: rgb(var(--v-theme-text)) !important;
    }
    .dplayer-video-wrap {
        background: transparent !important;
        .dplayer-video-wrap-aspect {
            transition: opacity 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94);
            opacity: 1;
        }
        .dplayer-danmaku {
            max-width: 100%;
            max-height: calc(100% - var(--comment-area-vertical-margin, 0px));
            aspect-ratio: var(--comment-area-aspect-ratio, 16 / 9);
            transition: max-height 0.5s cubic-bezier(0.42, 0.19, 0.53, 0.87), aspect-ratio 0.5s cubic-bezier(0.42, 0.19, 0.53, 0.87);
            will-change: aspect-ratio;
            overflow: hidden;
        }
        .dplayer-bml-browser {
            display: block;
            position: absolute;
            width: var(--bml-browser-width, 960px);
            height: var(--bml-browser-height, 540px);
            color: rgb(0, 0, 0);
            overflow: hidden;
            transform-origin: center;
            transform: scale(var(--bml-browser-scale-factor-width, 1), var(--bml-browser-scale-factor-height, 1));
            transition: opacity 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94);
            opacity: 1;
            aspect-ratio: 16 / 9;
        }
        .dplayer-danloading {
            display: none !important;
        }
        .dplayer-loading-icon {
            // ローディング表示は自前でやるため不要
            display: none !important;
        }
    }
    .dplayer-controller-mask {
        height: 82px !important;
        background: linear-gradient(to bottom, transparent, #000000cf) !important;
        opacity: 0 !important;
        visibility: hidden;
        transition: opacity 0.3s ease, visibility 0.3s ease !important;
        @include tablet-vertical {
            height: 66px !important;
        }
        @include smartphone-horizontal {
            height: 66px !important;
        }
        @include smartphone-vertical {
            height: 66px !important;
        }
    }

    .dplayer-controller {
        padding-left: calc(68px + 18px) !important;
        padding-right: calc(0px + 18px) !important;
        padding-bottom: 6px !important;
        transition: opacity 0.3s ease, visibility 0.3s ease;
        opacity: 0 !important;
        visibility: hidden;
        @include tablet-vertical {
            padding-left: calc(0px + 18px) !important;
            padding-right: calc(0px + 18px) !important;
        }
        @include smartphone-horizontal {
            padding-left: calc(0px + 18px) !important;
            padding-right: calc(0px + 18px) !important;
        }
        @include smartphone-vertical {
            padding-left: calc(0px + 18px) !important;
            padding-right: calc(0px + 18px) !important;
        }

        .dplayer-bar-wrap {
            bottom: 54px !important;
            width: calc(100% - 68px - (18px * 2));
            box-sizing: border-box;
            @include tablet-vertical {
                width: calc(100% - (18px * 2));
            }
            @include smartphone-horizontal {
                width: calc(100% - (18px * 2));
            }
            @include smartphone-vertical {
                width: calc(100% - (18px * 2));
            }
        }
        .dplayer-icons {
            bottom: auto !important;
            &.dplayer-icons-left {
                .dplayer-time, .dplayer-live-badge {
                    color: rgb(var(--v-theme-text)) !important;
                }
                .dplayer-volume {
                    .dplayer-volume-bar {
                        background: rgb(var(--v-theme-text)) !important;
                    }
                    // Document Picture-in-Picture ウインドウでは非表示
                    @media all and (display-mode: picture-in-picture) {
                        display: none;
                    }
                }
            }
            &.dplayer-icons-right {
                right: 22px !important;
                @include tablet-vertical {
                    right: 11px !important;
                }
                @include smartphone-horizontal {
                    right: 11px !important;
                }
                @include smartphone-vertical {
                    right: 11px !important;
                }
            }
            .dplayer-icon {
                @include tablet-vertical {
                    &.dplayer-pip-icon:after {
                        left: 25%;
                    }
                    &.dplayer-full-icon:after {
                        left: -20%;
                    }
                    // Document Picture-in-Picture ウインドウでは Picture-in-Picture ボタンのツールチップを左に寄せる
                    &.dplayer-pip-icon:after {
                        @media all and (display-mode: picture-in-picture) {
                            left: -25%;
                        }
                    }
                }
                @include smartphone-horizontal {
                    &.dplayer-pip-icon:after {
                        left: 25%;
                    }
                    &.dplayer-full-icon:after {
                        left: -20%;
                    }
                    // Document Picture-in-Picture ウインドウでは Picture-in-Picture ボタンのツールチップを左に寄せる
                    &.dplayer-pip-icon:after {
                        @media all and (display-mode: picture-in-picture) {
                            left: -25%;
                        }
                    }
                }
                @include smartphone-vertical {
                    &.dplayer-pip-icon:after {
                        left: 25%;
                    }
                    &.dplayer-full-icon:after {
                        left: -20%;
                    }
                    // Document Picture-in-Picture ウインドウでは Picture-in-Picture ボタンのツールチップを左に寄せる
                    &.dplayer-pip-icon:after {
                        @media all and (display-mode: picture-in-picture) {
                            left: -25%;
                        }
                    }
                }
                &.dplayer-capture-icon, &.dplayer-comment-capture-icon {
                    transition: background-color 0.08s ease;
                    border-radius: 6px;
                    &.dplayer-capturing {
                        background: rgb(var(--v-theme-secondary-lighten-1));
                        .dplayer-icon-content {
                            opacity: 1;
                        }
                    }
                }
                &.dplayer-comment-capture-icon {
                    padding: 7.3px !important;
                    @include smartphone-vertical {
                        padding: 5.4px !important;
                    }
                }
                // ブラウザフルスクリーンボタンを削除（実質あまり意味がないため）
                &.dplayer-full-in-icon {
                    display: none !important;
                }
                // Document Picture-in-Picture ウインドウでは非表示
                &.dplayer-full-icon {
                    @media all and (display-mode: picture-in-picture) {
                        display: none;
                    }
                }
            }
        }
        .dplayer-comment-box {
            transition: opacity 0.3s ease, visibility 0.3s ease !important;
            .dplayer-comment-setting-icon {
                z-index: 5;
            }
            .dplayer-comment-input {
                transition: box-shadow 0.09s ease;
                appearance: none;
                -webkit-appearance: none;
                &:focus {
                    box-shadow: rgba(79, 130, 230, 60%) 0 0 0 3.5px;
                }
                // iOS Safari でフォーカス時にズームされる問題への対処
                @supports (-webkit-touch-callout: none) {
                    @include smartphone-horizontal {
                        width: calc(100% * 1.142857) !important;
                        height: calc(100% * 1.142857) !important;
                        font-size: 16px !important;
                        transform: scale(0.875);
                        transform-origin: 0 0;
                    }
                    @include smartphone-vertical {
                        width: calc(100% * 1.142857) !important;
                        height: calc(100% * 1.142857) !important;
                        font-size: 16px !important;
                        transform: scale(0.875);
                        transform-origin: 0 0;
                    }
                }
            }
        }
    }
    .dplayer-notice {
        padding: 16px 22px !important;
        margin-right: 30px;
        border-radius: 4px !important;
        font-size: 15px !important;
        line-height: 1.6;
        @include tablet-vertical {
            top: auto;
            left: 16px !important;
            padding: 12px 16px !important;
            margin-right: 16px;
            font-size: 13.5px !important;
        }
        @include smartphone-horizontal {
            padding: 12px 16px !important;
            margin-right: 16px;
            font-size: 13.5px !important;
        }
        @include smartphone-vertical {
            top: auto;
            left: 16px !important;
            padding: 12px 16px !important;
            margin-right: 16px;
            font-size: 13.5px !important;
        }
    }
    .dplayer-info-panel {
        transition: top 0.3s, left 0.3s;
    }
    .dplayer-setting-box {
        z-index: 10 !important;
        @include tablet-vertical {
            height: calc(100% - 60px) !important;
        }
        .dplayer-setting-origin-panel {
            .dplayer-setting-item.dplayer-setting-lshaped-screen-crop,
            .dplayer-setting-item.dplayer-setting-keyboard-shortcut {
                // Document Picture-in-Picture ウインドウでは非表示
                @media all and (display-mode: picture-in-picture) {
                    display: none;
                }
            }
        }
        .dplayer-setting-audio-panel {
            // 副音声がない番組で副音声を選択できないように
            .dplayer-setting-audio-item.dplayer-setting-audio-item--disabled {
                pointer-events: none;  // クリックイベントを無効化
                .dplayer-label {
                    color: #AAAAAA;  // グレーアウト
                }
            }
        }
    }
    .dplayer-comment-setting-box {
        z-index: 10 !important;
        .dplayer-comment-setting-title {
            color: rgb(var(--v-theme-text));
        }
        .dplayer-comment-setting-type, .dplayer-comment-setting-size {
            span {
                border: 1px solid rgb(var(--v-theme-text));
            }
            input:checked + span {
                background: rgb(var(--v-theme-text));
            }
        }
    }

    // モバイルのみ適用されるスタイル
    &.dplayer-mobile {
        .dplayer-controller {
            padding-left: calc(68px + 30px) !important;
            padding-right: calc(0px + 30px) !important;
            .dplayer-bar-wrap {
                bottom: 51px !important;
                width: calc(100% - 68px - (30px * 2));
                @include tablet-vertical {
                    width: calc(100% - (18px * 2));
                }
                @include smartphone-horizontal {
                    width: calc(100% - (18px * 2));
                }
                @include smartphone-vertical {
                    // スマホ縦画面のみ、シークバーをプレイヤーの下辺に配置
                    width: 100%;
                    left: 0px !important;
                    bottom: -6px !important;
                    z-index: 100;
                }
                .dplayer-thumb {
                    // タッチデバイスのみ、コントロール表示時は常にシークバーのつまみを表示する
                    @media (hover: none) {
                        transform: scale(1) !important;
                    }
                }
            }
            @include tablet-vertical {
                padding-left: calc(0px + 18px) !important;
                padding-right: calc(0px + 18px) !important;
            }
            @include smartphone-horizontal {
                padding-left: calc(0px + 18px) !important;
                padding-right: calc(0px + 18px) !important;
            }
            @include smartphone-vertical {
                padding-left: calc(0px + 18px) !important;
                padding-right: calc(0px + 18px) !important;
            }
        }
        &.dplayer-hide-controller .dplayer-controller {
            transform: none !important;
        }
    }

    // 狭小幅デバイスのみ適用されるスタイル
    &.dplayer-narrow {
        .dplayer-icons.dplayer-icons-right {
            right: 14px !important;
        }
    }
}

// ロード中は DPlayer 内の動画と BML ブラウザを非表示にする
.watch-player.watch-player--loading {
    .watch-player__dplayer {
        .dplayer-video-wrap-aspect, .dplayer-bml-browser {
            opacity: 0 !important;
        }
    }
}

// 仮想キーボード表示時
.watch-player.watch-player--virtual-keyboard-display {
    .watch-player__dplayer {
        .dplayer-controller-mask {
            position: absolute;
            bottom: env(keyboard-inset-height, 0px) !important;
            @include tablet-vertical {
                bottom: 0px !important;
            }
            @include smartphone-vertical {
                bottom: 0px !important;
            }
        }
        .dplayer-icons.dplayer-comment-box {
            position: absolute;
            bottom: calc(env(keyboard-inset-height, 0px) + 4px) !important;
            @include tablet-vertical {
                bottom: 6px !important;
            }
            @include smartphone-vertical {
                bottom: 6px !important;
            }
        }
    }
}

// ビデオ視聴時のみ適用されるスタイル
.watch-player.watch-player--video {
    .watch-player__dplayer {
        // コメント送信用ボタンを削除
        .dplayer-controller .dplayer-icons .dplayer-comment {
            display: none !important;
        }
    }
}

// Safari のみ、アイコンに hover しても opacity が変わらないようにする
// hover すると 1px ずれてしまい見苦しくなる Safari の描画バグを回避するための苦肉の策
// ref: https://qiita.com/Butterthon/items/10e6b58d883236aa3838
_::-webkit-full-page-media, _:future, :root .dplayer-icon:hover .dplayer-icon-content {
    opacity: 0.8 !important;
}

</style>
<style lang="scss" scoped>

.watch-player {
    display: flex;
    position: relative;
    width: 100%;
    height: 100%;
    background-size: contain;
    background-position: center;
    @include tablet-vertical {
        aspect-ratio: 16 / 9;
    }
    @include smartphone-vertical {
        aspect-ratio: 16 / 9;
    }

    &.watch-player--video {
        .watch-player__button {
            right: 0px;
            .switch-button {
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        }
    }

    .watch-player__dplayer-setting-cover {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        z-index: 50;

        &--display {
            // タッチデバイスかつスマホ縦画面のみ、設定パネルを開いた時にカバーを表示する
            @media (hover: none) {
                @include smartphone-vertical {
                    opacity: 1;
                    visibility: visible;
                }
            }
        }
    }

    .watch-player__background-wrapper {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;

        .watch-player__background {
            position: relative;
            top: 50%;
            left: 50%;
            max-height: 100%;
            aspect-ratio: 16 / 9;
            transform: translate(-50%, -50%);
            background-blend-mode: overlay;
            background-color: rgba(14, 14, 18, 0.35);
            background-size: cover;
            background-image: none;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94), visibility 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94);
            will-change: opacity;

            &--display {
                opacity: 1;
                visibility: visible;
            }
            &--background-hide {
                background-image: none !important;
                background-color: #101010;
            }

            .watch-player__background-logo {
                display: inline-block;
                position: absolute;
                height: 34px;
                right: 56px;
                bottom: 44px;
                filter: drop-shadow(0px 0px 5px rgb(var(--v-theme-black)));

                @include tablet-vertical {
                    height: 30px;
                    right: 34px;
                    bottom: 30px;
                }
                @include smartphone-horizontal {
                    height: 25px;
                    right: 30px;
                    bottom: 24px;
                }
                @include smartphone-vertical {
                    height: 22px;
                    right: 30px;
                    bottom: 24px;
                }
            }
        }
    }

    .watch-player__buffering {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: rgb(var(--v-theme-background-lighten-3));
        filter: drop-shadow(0px 0px 3px rgba(0, 0, 0, 0.3));
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94), visibility 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94);
        will-change: opacity;
        z-index: 3;
        pointer-events: none;  // クリックイベントを無効化 (重要)

        &--display {
            opacity: 1;
            visibility: visible;
        }
    }

    .watch-player__dplayer {
        width: 100%;
    }

    .watch-player__button {
        display: flex;
        justify-content: space-around;
        flex-direction: column;
        position: absolute;
        top: 50%;
        right: 28px;
        height: 190px;
        transform: translateY(-50%);
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        @include tablet-vertical {
            right: 15px;
            height: 128px;
        }
        @include smartphone-horizontal {
            right: 15px;
            height: 155px;
        }
        @include smartphone-vertical {
            right: 15px;
            height: 100px;
        }

        // Document Picture-in-Picture ウインドウでは非表示
        @media all and (display-mode: picture-in-picture) {
            display: none;
        }

        .switch-button {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 48px;
            height: 48px;
            color: rgb(var(--v-theme-text));
            background: #2F221FC0;
            border-radius: 7px;
            transition: background-color 0.15s;
            user-select: none;
            cursor: pointer;
            @include smartphone-horizontal {
                width: 38px;
                height: 38px;
                border-radius: 5px;
            }
            @include smartphone-vertical {
                width: 38px;
                height: 38px;
                border-radius: 5px;
            }

            &:hover {
                background: #2F221FF0;
            }
            // タッチデバイスで hover を無効にする
            @media (hover: none) {
                &:hover {
                    background: #2F221FC0;
                }
            }

            svg {
                @include smartphone-horizontal {
                    height: 27px;
                }
                @include smartphone-vertical {
                    height: 27px;
                }
            }

            .switch-button-icon {
                position: relative;
            }

            &-up > .switch-button-icon {
                top: 6px;
            }
            &-panel {
                &.switch-button-panel--open {
                    color: rgb(var(--v-theme-primary));
                }
                @include tablet-vertical {
                    display: none;
                }
                @include smartphone-vertical {
                    display: none;
                }
            }
            &-panel > .switch-button-icon {
                top: 1.5px;
                transition: color 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);
            }
            &-down > .switch-button-icon {
                bottom: 4px;
            }
        }
    }
}

</style>