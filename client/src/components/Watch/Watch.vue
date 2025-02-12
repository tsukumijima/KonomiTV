<template>
    <div class="route-container">
        <main class="watch-container" :class="{
                'watch-container--control-display': playerStore.is_control_display,
                'watch-container--panel-display': Utils.isSmartphoneVertical() || Utils.isTabletVertical() ? true : playerStore.is_panel_display,
                'watch-container--fullscreen': playerStore.is_fullscreen,
                'watch-container--document-pip': playerStore.is_document_pip,
                'watch-container--video': playback_mode === 'Video',
            }">
            <WatchNavigation />
            <div class="watch-content"
                 @mousemove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event, is_player_region_event: true})"
                 @touchmove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event, is_player_region_event: true})"
                 @click="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event, is_player_region_event: true})">
                <WatchHeader :playback_mode="playback_mode" />
                <WatchPlayer :playback_mode="playback_mode" />
            </div>
            <WatchPanel :playback_mode="playback_mode" />
        </main>
        <KeyboardShortcutList :playback_mode="playback_mode" />
        <LShapedScreenCropSettings />
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import WatchHeader from '@/components/Watch/Header.vue';
import KeyboardShortcutList from '@/components/Watch/KeyboardShortcutList.vue';
import LShapedScreenCropSettings from '@/components/Watch/LShapedScreenCropSettings.vue';
import WatchNavigation from '@/components/Watch/Navigation.vue';
import WatchPanel from '@/components/Watch/Panel.vue';
import WatchPlayer from '@/components/Watch/Player.vue';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';

// ライブ視聴・ビデオ視聴共通の視聴画面
export default defineComponent({
    name: 'Watch',
    components: {
        KeyboardShortcutList,
        LShapedScreenCropSettings,
        WatchHeader,
        WatchNavigation,
        WatchPanel,
        WatchPlayer,
    },
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
        };
    },
    computed: {
        ...mapStores(usePlayerStore, useSettingsStore),
    },
    watch: {
        // 前回視聴画面を開いた際にパネルが表示されていたかどうかを随時保存する
        'playerStore.is_panel_display': {
            handler() {
                this.settingsStore.settings.showed_panel_last_time = this.playerStore.is_panel_display;
            }
        }
    },
    // 開始時に実行
    created() {

        // Virtual Keyboard API に対応している場合は、仮想キーボード周りの操作を自力で行うことをブラウザに伝える
        // この視聴画面のみ
        if ('virtualKeyboard' in navigator) {
            navigator.virtualKeyboard.overlaysContent = true;
            // 仮想キーボードが表示されたり閉じられたときのイベント
            navigator.virtualKeyboard.ongeometrychange = (event) => {
                if (event.target.boundingRect.width === 0 && event.target.boundingRect.height === 0) {
                    this.playerStore.is_virtual_keyboard_display = false;
                } else {
                    this.playerStore.is_virtual_keyboard_display = true;
                }
            };
        }

        // PlayerStore に視聴画面を開いたことを伝える
        // 視聴画面に入るまでに変更されているかもしれない初期値を反映させる
        this.playerStore.startWatching();
    },
    // 終了前に実行
    beforeUnmount() {

        // PlayerStore に視聴画面を閉じたことを伝える
        this.playerStore.stopWatching();

        // 仮想キーボード周りの操作をブラウザに戻す
        if ('virtualKeyboard' in navigator) {
            navigator.virtualKeyboard.overlaysContent = false;
        }
    }
});

</script>
<style lang="scss">

// 上書きしたいスタイル

// コントロール表示時
.watch-container.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-controller-mask, .dplayer-controller {
            opacity: 1 !important;
            visibility: visible !important;
            .dplayer-comment-box {
                left: calc(68px + 20px);
                @include tablet-vertical {
                    left: calc(0px + 16px);
                }
                @include smartphone-horizontal {
                    left: calc(0px + 16px);
                }
                @include smartphone-vertical {
                    left: calc(0px + 16px);
                }
            }
        }
        .dplayer-notice {
            left: calc(68px + 30px);
            bottom: 62px;
            @include tablet-vertical {
                left: calc(0px + 16px);
                bottom: 62px !important;
            }
            @include smartphone-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-vertical {
                left: calc(0px + 16px);
                bottom: 62px !important;
            }
        }
        .dplayer-info-panel {
            top: 82px;
            left: calc(68px + 30px);
            @include tablet-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-vertical {
                left: calc(0px + 16px);
            }
        }
        .dplayer-comment-setting-box {
            left: calc(68px + 20px);
            @include tablet-vertical {
                left: calc(0px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-vertical {
                left: calc(0px + 16px);
            }
        }
        .dplayer-mobile .dplayer-mobile-icon-wrap {
            opacity: 0.7 !important;
            visibility: visible !important;
        }
    }
}

// コントロール非表示時
.watch-container:not(.watch-container--control-display) {
    .watch-player__dplayer {
        .dplayer-danmaku {
            max-height: 100% !important;
            aspect-ratio: 16 / 9 !important;
        }
        .dplayer-notice {
            bottom: 20px !important;
        }
    }
}

// 非フルスクリーン時
.watch-container:not(.watch-container--fullscreen) {
    .watch-player__dplayer.dplayer-mobile {
        .dplayer-setting-box {
            @include smartphone-vertical {
                // スマホ縦画面かつ非フルスクリーン時のみ、設定パネルを画面下部にオーバーレイ配置
                position: fixed;
                left: 0px !important;
                right: 0px !important;
                bottom: env(safe-area-inset-bottom) !important;  // iPhone X 以降の Home Indicator の高さ分
                width: 100% !important;
                height: 100% !important;
                background: rgb(var(--v-theme-background));
                transform: translateY(40%) !important;
                z-index: 100 !important;
            }
            &.dplayer-setting-box-open {
                transform: translateY(0%) !important;
            }
        }
    }
}
// フルスクリーン時
.watch-container.watch-container--fullscreen {
    .watch-player__dplayer {
        .dplayer-controller {
            padding-left: 20px !important;
        }
        &.dplayer-mobile .dplayer-controller {
            padding-left: 30px !important;
            @include tablet-vertical {
                padding-left: 16px !important;
            }
            @include smartphone-horizontal {
                padding-left: 16px !important;
            }
            @include smartphone-vertical {
                padding-left: 16px !important;
            }
        }
        .dplayer-comment-box, .dplayer-comment-setting-box {
            left: 20px !important;
            @include tablet-vertical {
                left: 16px !important;
            }
            @include smartphone-horizontal {
                left: 16px !important;
            }
            @include smartphone-vertical {
                left: 16px !important;
            }
        }
    }
    .watch-header__back-icon {
        display: none !important;
    }
}

// フルスクリーン時 + コントロール表示時
.watch-container.watch-container--fullscreen.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-notice, .dplayer-info-panel {
            left: 30px !important;
            @include tablet-vertical {
                left: 16px !important;
            }
            @include smartphone-horizontal {
                left: 16px !important;
            }
            @include smartphone-vertical {
                left: 16px !important;
            }
        }
    }
}

// Document Picture-in-Picture 時
.watch-container.watch-container--document-pip {
    // ナビゲーションを強制表示
    .watch-navigation {
        opacity: 1 !important;
        visibility: visible !important;
    }
}

// ビデオ視聴時 + コントロール表示時のみ適用されるスタイル
.watch-container.watch-container--video.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-notice {
            bottom: 74px !important;
        }
        &.dplayer-mobile .dplayer-notice {
            bottom: 71px !important;
            @include smartphone-vertical {
                bottom: 50px !important;
            }
        }
    }
}

// ビデオ視聴時 + フルスクリーン時のみ適用されるスタイル
.watch-container.watch-container--video.watch-container--fullscreen {
    .watch-player__dplayer {
        .dplayer-bar-wrap {
            width: calc(100% - (18px * 2)) !important;
        }
        &.dplayer-mobile .dplayer-bar-wrap {
            width: calc(100% - (30px * 2));
            @include tablet-horizontal {
                width: calc(100% - (30px * 2)) !important;
            }
            @include tablet-vertical {
                width: calc(100% - (18px * 2)) !important;
            }
            @include smartphone-horizontal {
                width: calc(100% - (18px * 2)) !important;
            }
            @include smartphone-vertical {
                width: calc(100% - (18px * 2)) !important;
            }
        }
    }
}

// Document Picture-in-Picture 時の「ピクチャー イン ピクチャーを再生しています」のテキスト
.watch-container {
    .playing-in-pip {
        display: flex;
        flex-direction: column;
        gap: 20px;
        align-items: center;
        justify-content: center;
        width: 100%;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 24px;
        padding: 20px;
        @include smartphone-vertical {
            aspect-ratio: 16 / 9;
        }

        &__close-button {
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 15px;
            background: rgb(var(--v-theme-background-lighten-1));
            transition: background-color 0.15s;
            cursor: pointer;

            &:hover {
                background: rgb(var(--v-theme-background-lighten-2));
            }
        }
    }
}

</style>
<style lang="scss" scoped>

.route-container {
    height: 100vh !important;
    height: 100dvh !important;
    border-bottom: env(safe-area-inset-bottom) solid rgb(var(--v-theme-background));  // Home Indicator 分浮かせる余白の背景色
    background: rgb(var(--v-theme-black)) !important;
    overflow: hidden;
    // タブレット横画面・スマホ横画面のみ Home Indicator 分浮かせる余白の背景色を rgb(var(--v-theme-black)) にする
    // 映像の左右の黒い余白と背景色を合わせる
    @include tablet-horizontal {
        border-bottom: env(safe-area-inset-bottom) solid rgb(var(--v-theme-black));
    }
    @include smartphone-horizontal {
        border-bottom: env(safe-area-inset-bottom) solid rgb(var(--v-theme-black));
    }
}

.watch-container {
    display: flex;
    width: calc(100% + 352px);  // パネルの幅分はみ出す
    height: 100%;
    transition: width 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);
    @include tablet-vertical {
        flex-direction: column;
        width: 100%;
    }
    @include smartphone-horizontal {
        width: calc(100% + 310px); // パネルの幅分はみ出す
    }
    @include smartphone-vertical {
        flex-direction: column;
        width: 100%;
    }

    // コントロール表示時
    &.watch-container--control-display {
        .watch-content {
            cursor: auto !important;
        }
        .watch-navigation, .watch-header {
            opacity: 1 !important;
            visibility: visible !important;
        }
        // :deep() で子コンポーネントにも CSS が効くようにする
        // ref: https://qiita.com/buntafujikawa/items/b1703a2a4344fd326fe0
        .watch-player :deep() {
            .watch-player__button {
                opacity: 1 !important;
                visibility: visible !important;
            }
        }
    }

    // パネル表示時
    &.watch-container--panel-display {
        width: 100%;  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: rgb(var(--v-theme-primary));
        }

        // タッチデバイスのみ、content-visibility: visible で明示的にパネルを描画する
        .watch-panel {
            @media (hover: none) {
                content-visibility: auto;
            }
        }
    }
    @include tablet-vertical {
        width: 100%;
        .watch-panel {
            @media (hover: none) {
                content-visibility: auto;
            }
        }
    }
    @include smartphone-vertical {
        width: 100%;
        .watch-panel {
            @media (hover: none) {
                content-visibility: auto;
            }
        }
    }

    // フルスクリーン時
    &.watch-container--fullscreen {

        // ナビゲーションを非表示
        .watch-navigation {
            display: none;
        }
        // ナビゲーションの分の余白を削除
        .watch-content {
            .watch-header {
                padding-left: 30px;
                @include tablet-vertical {
                    padding-left: 16px;
                }
                @include smartphone-horizontal {
                    padding-left: 16px;
                }
                @include smartphone-horizontal {
                    padding-left: 16px;
                }
            }
        }
    }

    .watch-content {
        display: flex;
        position: relative;
        width: 100%;
        cursor: none;
        @include smartphone-vertical {
            z-index: 5;  // スマホ縦画面のみ、シークバーのつまみを少しはみ出るように配置する
        }
    }
}

</style>