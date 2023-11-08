<template>
    <div class="route-container">
        <main class="watch-container" :class="{
                'watch-container--control-display': playerStore.is_control_display,
                'watch-container--panel-display': Utils.isSmartphoneVertical() || Utils.isTabletVertical() ? true : playerStore.is_panel_display,
                'watch-container--fullscreen': playerStore.is_fullscreen,
            }">
            <WatchNavigation />
            <div class="watch-content"
                 @mousemove="($event) => player_controller?.setControlDisplayTimer($event, true)"
                 @touchmove="($event) => player_controller?.setControlDisplayTimer($event, true)"
                 @click="($event) => player_controller?.setControlDisplayTimer($event, true)">
                <WatchHeader :playback_mode="'Live'" />
                <WatchPlayer :playback_mode="'Live'" />
            </div>
            <WatchPanel :playback_mode="'Live'" />
        </main>
        <BottomNavigation />
        <KeyboardShortcutList :playback_mode="'Live'" />
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import BottomNavigation from '@/components/BottomNavigation.vue';
import WatchHeader from '@/components/Watch/Header.vue';
import KeyboardShortcutList from '@/components/Watch/KeyboardShortcutList.vue';
import WatchNavigation from '@/components/Watch/Navigation.vue';
import WatchPanel from '@/components/Watch/Panel.vue';
import WatchPlayer from '@/components/Watch/Player.vue';
import PlayerController from '@/services/player/PlayerController';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { ProgramUtils } from '@/utils';

export default Vue.extend({
    name: 'TV-Watch',
    components: {
        BottomNavigation,
        KeyboardShortcutList,
        WatchHeader,
        WatchNavigation,
        WatchPanel,
        WatchPlayer,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ProgramUtils: ProgramUtils,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [] as number[],

            // PlayerController のインスタンス
            player_controller: null as PlayerController | null,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore, useSettingsStore),
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

        // チャンネル ID をセット
        this.channelsStore.display_channel_id = this.$route.params.display_channel_id;

        // 再生セッションを初期化
        this.init();
    },
    // チャンネル切り替え時に実行
    // コンポーネント（インスタンス）は再利用される
    // ref: https://v3.router.vuejs.org/ja/guide/advanced/navigation-guards.html#%E3%83%AB%E3%83%BC%E3%83%88%E5%8D%98%E4%BD%8D%E3%82%AB%E3%82%99%E3%83%BC%E3%83%88%E3%82%99
    beforeRouteUpdate(to, from, next) {

        // 前の再生セッションを破棄して終了する
        // このとき this.interval_ids に登録された setTimeout がキャンセルされるため、
        // 後述の 0.5 秒の間にザッピングにより他のチャンネルに切り替えた場合は this.init() は実行されない
        const destroy_promise = this.destroy();

        // チャンネル ID を次のチャンネルのものに切り替える
        this.channelsStore.display_channel_id = to.params.display_channel_id;

        (async () => {

            // ザッピング（「前/次のチャンネル」ボタン or 上下キーショートカット）によるチャンネル移動時のみ、
            // 0.5秒だけ待ってから新しい再生セッションを初期化する
            // 連続してチャンネルを切り替えた際に毎回再生処理を開始しないように猶予を設ける
            if (this.playerStore.is_zapping === true) {
                this.playerStore.is_zapping = false;
                this.interval_ids.push(window.setTimeout(() => {
                    destroy_promise.then(() => this.init());  // destroy() の実行完了を待ってから初期化する
                }, 0.5 * 1000));

            // 通常のチャンネル移動時は、すぐに再生セッションを初期化する
            } else {
                destroy_promise.then(() => this.init());  // destroy() の実行完了を待ってから初期化する
            }
        })();

        // 次のルートに置き換え
        next();
    },
    // 終了前に実行
    beforeDestroy() {

        // destroy() を実行
        // 別のページへ遷移するため、DPlayer のインスタンスを確実に破棄する
        // さもなければ、ブラウザがリロードされるまでバックグラウンドで永遠に再生され続けてしまう
        // 不正な ID のため 404 ページに遷移されるときは実行しない
        if (this.channelsStore.channel.current.display_channel_id !== 'gr999') {
            this.destroy();
        }

        // このページから離れるので、チャンネル ID を gr000 (ダミー値) に戻す
        this.channelsStore.display_channel_id = 'gr000';

        // PlayerStore に視聴画面を閉じたことを伝える
        this.playerStore.stopWatching();

        // 仮想キーボード周りの操作をブラウザに戻す
        if ('virtualKeyboard' in navigator) {
            navigator.virtualKeyboard.overlaysContent = false;
        }
    },
    watch: {
        // 前回視聴画面を開いた際にパネルが表示されていたかどうかを随時保存する
        'playerStore.is_panel_display': {
            handler() {
                this.settingsStore.settings.showed_panel_last_time = this.playerStore.is_panel_display;
            }
        }
    },
    methods: {

        // 再生セッションを初期化する
        async init() {

            // 00秒までの残り秒数を取得
            // 現在 16:01:34 なら 26 (秒) になる
            const residue_second = 60 - new Date().getSeconds();

            // 00秒になるまで待ってから実行するタイマー
            // 番組は基本1分単位で組まれているため、20秒や45秒など中途半端な秒数で更新してしまうと番組情報の反映が遅れてしまう
            this.interval_ids.push(window.setTimeout(() => {

                // この時点で00秒なので、チャンネル情報を更新
                this.channelsStore.update(true);

                // 以降、30秒おきにチャンネル情報を更新
                this.interval_ids.push(window.setInterval(() => {
                    this.channelsStore.update(true);
                }, 30 * 1000));

            }, residue_second * 1000));

            // チャンネル情報を更新 (初回)
            await this.channelsStore.update();

            // チャンネル ID が未定義なら実行しない（フェイルセーフ）
            if (this.$route.params.display_channel_id === undefined) {
                return;
            }

            // もし現時点でチャンネル ID が gr999 だった場合、チャンネル情報に存在しない不正な ID なので、404 ページにリダイレクト
            if (this.channelsStore.channel.current.display_channel_id === 'gr999') {
                this.$router.push({path: '/not-found/'});
                return;
            }

            // PlayerController を初期化
            this.player_controller = new PlayerController('Live');
            await this.player_controller.init();
        },

        // 再生セッションを破棄する
        // チャンネルを切り替える際に実行される
        async destroy() {

            // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
            // clearInterval() と clearTimeout() は中身共通なので問題ない
            for (const interval_id of this.interval_ids) {
                window.clearInterval(interval_id);
            }

            // interval_ids をクリア
            this.interval_ids = [];

            // PlayerController を破棄
            if (this.player_controller !== null) {
                await this.player_controller.destroy();
                this.player_controller = null;
            }
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

// フルスクリーン+コントロール表示時
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

</style>
<style lang="scss" scoped>

.route-container {
    height: 100vh !important;
    height: calc(100dvh - env(safe-area-inset-bottom)) !important;
    background: var(--v-black-base) !important;
    overflow: hidden;
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
        padding-bottom: 56px;
    }

    // コントロール表示時
    &.watch-container--control-display {
        .watch-content {
            cursor: auto !important;
        }
        .watch-navigation, .watch-header, .watch-player__button {
            opacity: 1 !important;
            visibility: visible !important;
        }
    }

    // パネル表示時
    &.watch-container--panel-display {
        width: 100%;  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: var(--v-primary-base);
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
    }
}

</style>