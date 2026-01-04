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
        <!-- iOS アプリでは Watch Panel のナビゲーションを使用するため、BottomNavigation は非表示 -->
        <BottomNavigation v-show="!playerStore.is_fullscreen && !is_capacitor_ios" />
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
import BottomNavigation from '@/components/BottomNavigation.vue';
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
        BottomNavigation,
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
            // iOS アプリ（Capacitor）かどうか
            is_capacitor_ios: document.body.classList.contains('capacitor-ios'),
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

        // iOS アプリ（Capacitor）の場合、視聴ページから離れる際は再生を停止
        // ページ遷移時に PiP ではなく再生を止める要件のため
        if (document.body.classList.contains('capacitor-ios')) {
            const video = document.querySelector<HTMLVideoElement>('.watch-player__dplayer video');
            if (video && !video.paused) {
                video.pause();
            }
        }

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
    // コントロール表示時にボタンを表示
    .watch-player__button {
        opacity: 1 !important;
        visibility: visible !important;
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
    // コントロール表示時はヘッダー（タイトル）も表示（scoped スタイルより優先度を上げる）
    .watch-content > .watch-header {
        opacity: 1 !important;
        visibility: visible !important;
    }
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
        // BottomNavigation の高さ分 (56px) + セーフエリア分の余白を追加
        // これがないと BottomNavigation とコンテンツが被ってしまう
        &:not(.watch-container--fullscreen) {
            padding-bottom: calc(56px + env(safe-area-inset-bottom));
        }
    }

    // iOS アプリ（Capacitor）向けのスタイル
    // .v-application でセーフエリアが適用されているが、視聴ページでは別途対応が必要
    body.capacitor-ios & {
        @include smartphone-vertical {
            &:not(.watch-container--fullscreen) {
                // iOS アプリでは .v-application のセーフエリアパディング内にいるため、
                // BottomNavigation の高さ分のみ確保すれば良い
                // セーフエリアは BottomNavigation 側で対応する
                padding-bottom: 56px;
            }
        }
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
        // ヘッダーをオーバーレイ表示（コントロール非表示時は自動で消える）
        .watch-header {
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            z-index: 10 !important;
            background: linear-gradient(to bottom, rgba(0,0,0,0.7), transparent) !important;
            padding-top: env(safe-area-inset-top) !important;
            padding-left: calc(env(safe-area-inset-left) + 16px) !important;
            padding-right: calc(env(safe-area-inset-right) + 16px) !important;
            // 初期状態は非表示（コントロール表示時に visible になる）
            // transition でフェードイン・フェードアウトを実現
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }
        // パネルを非表示
        .watch-panel {
            display: none !important;
        }
        // パネル表示切り替えボタンを非表示
        .switch-button-panel {
            display: none !important;
        }
        // フルスクリーン時はサイドバー表示ボタン（.watch-player__button）を非表示
        .watch-player__button {
            display: none !important;
        }

        // ナビゲーションの分の余白を削除
        .watch-content {
            width: 100% !important;
            height: 100% !important;
            .watch-header {
                // 上書き
            }
            .watch-player {
                width: 100% !important;
                height: 100% !important;

                // iOS Capacitor アプリのフルスクリーン時: コントローラー・シークバーをセーフエリアに合わせる
                // 映像の表示領域（セーフエリア内）に合わせてコントローラーを配置
                body.capacitor-ios & {
                    // コントローラーの下部・左右にセーフエリア分の余白を追加
                    .dplayer-controller {
                        padding-bottom: calc(env(safe-area-inset-bottom) + 6px) !important;
                        padding-left: calc(env(safe-area-inset-left) + 16px) !important;
                        padding-right: calc(env(safe-area-inset-right) + 16px) !important;
                    }
                    &.dplayer-mobile .dplayer-controller {
                        padding-bottom: calc(env(safe-area-inset-bottom) + 6px) !important;
                        padding-left: calc(env(safe-area-inset-left) + 16px) !important;
                        padding-right: calc(env(safe-area-inset-right) + 16px) !important;
                    }
                    // コントローラーマスク（グラデーション背景）もセーフエリア対応
                    .dplayer-controller-mask {
                        height: calc(82px + env(safe-area-inset-bottom)) !important;
                        padding-left: env(safe-area-inset-left) !important;
                        padding-right: env(safe-area-inset-right) !important;
                    }
                    // シークバーの幅もセーフエリア対応（プレイヤーの横幅に合わせる）
                    .dplayer-bar-wrap {
                        width: calc(100% - env(safe-area-inset-left) - env(safe-area-inset-right) - 32px) !important;
                        left: calc(env(safe-area-inset-left) + 16px) !important;
                    }
                    &.dplayer-mobile .dplayer-bar-wrap {
                        width: calc(100% - env(safe-area-inset-left) - env(safe-area-inset-right) - 32px) !important;
                        left: calc(env(safe-area-inset-left) + 16px) !important;
                    }
                    // 左側のアイコン群（時間表示・音量など）のセーフエリア対応
                    .dplayer-icons-left {
                        left: calc(env(safe-area-inset-left) + 16px) !important;
                    }
                    // 右側のアイコン群のセーフエリア対応
                    .dplayer-icons-right {
                        right: calc(env(safe-area-inset-right) + 16px) !important;
                    }
                    // コメント入力欄のセーフエリア対応
                    .dplayer-comment-box {
                        left: calc(env(safe-area-inset-left) + 16px) !important;
                    }
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