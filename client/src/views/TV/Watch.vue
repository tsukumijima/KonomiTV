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
                <header class="watch-header">
                    <router-link class="watch-header__back-icon" v-ripple to="/tv/">
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
                <div class="watch-player" :class="{
                    'watch-player--loading': playerStore.is_loading,
                    'watch-player--virtual-keyboard-display': playerStore.is_virtual_keyboard_display && Utils.hasActiveElementClass('dplayer-comment-input'),
                }">
                    <div class="watch-player__background-wrapper">
                        <div class="watch-player__background" :class="{'watch-player__background--display': playerStore.is_background_display}"
                            :style="{backgroundImage: `url(${playerStore.background_url})`}">
                            <img class="watch-player__background-logo" src="/assets/images/logo.svg">
                        </div>
                    </div>
                    <v-progress-circular indeterminate size="60" width="6" class="watch-player__buffering"
                        :class="{'watch-player__buffering--display': playerStore.is_video_buffering}">
                    </v-progress-circular>
                    <div class="watch-player__dplayer"></div>
                    <div class="watch-player__button"
                         @mousemove="($event) => player_controller?.setControlDisplayTimer($event)"
                         @touchmove="($event) => player_controller?.setControlDisplayTimer($event)"
                         @click="($event) => player_controller?.setControlDisplayTimer($event)">
                        <div v-ripple class="switch-button switch-button-up" v-tooltip.top="'前のチャンネル'"
                            @click="playerStore.is_zapping = true; $router.push({path: `/tv/watch/${channelsStore.channel.previous.display_channel_id}`})">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-left-24-filled" width="32px" rotate="1" />
                        </div>
                        <div v-ripple class="switch-button switch-button-panel switch-button-panel--open"
                            @click="playerStore.is_panel_display = !playerStore.is_panel_display">
                            <Icon class="switch-button-icon" icon="fluent:navigation-16-filled" width="32px" />
                        </div>
                        <div v-ripple class="switch-button switch-button-down" v-tooltip.bottom="'次のチャンネル'"
                             @click="playerStore.is_zapping = true; $router.push({path: `/tv/watch/${channelsStore.channel.next.display_channel_id}`})">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-right-24-filled" width="33px" rotate="1" />
                        </div>
                    </div>
                </div>
            </div>
            <WatchPanel :playback_mode="'Live'" />
        </main>
        <v-dialog max-width="1050" transition="slide-y-transition" v-model="playerStore.shortcut_key_modal">
            <v-card>
                <v-card-title class="px-5 pt-4 pb-3 d-flex align-center font-weight-bold">
                    <Icon icon="fluent:keyboard-20-filled" height="28px" />
                    <span class="ml-3">キーボードショートカット</span>
                    <v-spacer></v-spacer>
                    <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="playerStore.shortcut_key_modal = false">
                        <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                    </div>
                </v-card-title>
                <div class="px-5 pb-4">
                    <v-row>
                        <v-col cols="6" v-for="(shortcut_key_column, shortcut_key_column_name) in shortcut_key_list" :key="shortcut_key_column_name">
                            <div class="mt-3" v-for="shortcut_keys in shortcut_key_column" :key="shortcut_keys.name">
                                <div class="text-subtitle-1 d-flex align-center font-weight-bold">
                                    <Icon :icon="shortcut_keys.icon" :height="shortcut_keys.icon_height" />
                                    <span class="ml-2">{{shortcut_keys.name}}</span>
                                </div>
                                <div class="mt-3" v-for="shortcut in shortcut_keys.shortcuts" :key="shortcut.name">
                                    <div class="text-subtitle-2 mt-2 d-flex align-center font-weight-medium">
                                        <span class="mr-2" v-html="shortcut.name"></span>
                                        <div class="ml-auto d-flex align-center flex-shrink-0">
                                            <div class="ml-auto d-flex align-center" v-for="(key, index) in shortcut.keys" :key="key.name">
                                                <span class="shortcut-key">
                                                    <Icon v-show="key.icon === true" :icon="key_name" height="18px"
                                                        v-for="key_name in key.name.split(';')" :key="key_name" />
                                                    <span v-if="key.icon === false" v-html="key.name"></span>
                                                </span>
                                                <span class="shortcut-key-plus" v-if="index < (shortcut.keys.length - 1)">+</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </v-col>
                    </v-row>
                </div>
            </v-card>
        </v-dialog>
        <BottomNavigation />
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import BottomNavigation from '@/components/BottomNavigation.vue';
import WatchNavigation from '@/components/Watch/Navigation.vue';
import WatchPanel from '@/components/Watch/Panel.vue';
import PlayerController from '@/services/player/PlayerController';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { dayjs, ProgramUtils } from '@/utils';

export default Vue.extend({
    name: 'TV-Watch',
    components: {
        BottomNavigation,
        WatchNavigation,
        WatchPanel,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ProgramUtils: ProgramUtils,

            // 現在時刻
            time: dayjs().format('YYYY/MM/DD HH:mm:ss'),

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [] as number[],

            // ***** プレイヤー *****

            // PlayerController のインスタンス
            player_controller: null as PlayerController | null,

            // ***** キーボードショートカット *****

            // キーボードショートカットの一覧に表示するショートカットキーのリスト
            shortcut_key_list: {
                left_column: [
                    {
                        name: '全般',
                        icon: 'fluent:home-20-filled',
                        icon_height: '22px',
                        shortcuts: [
                            { name: '数字キー/テンキーに対応するリモコン番号 (1~12) の地デジチャンネルに切り替える', keys: [{name: '1~9, 0, -(=), ^(~)', icon: false}] },
                            { name: '数字キー/テンキーに対応するリモコン番号 (1~12) の BS チャンネルに切り替える', keys: [{name: 'Shift', icon: false}, {name: '1~9, 0, -(=), ^(~)', icon: false}] },
                            { name: '前のチャンネルに切り替える', keys: [{name: 'fluent:arrow-up-12-filled', icon: true}] },
                            { name: '次のチャンネルに切り替える', keys: [{name: 'fluent:arrow-down-12-filled', icon: true}] },
                            { name: 'キーボードショートカットの一覧を表示する', keys: [{name: '／(？)', icon: false}] },
                        ]
                    },
                    {
                        name: 'プレイヤー',
                        icon: 'fluent:play-20-filled',
                        icon_height: '20px',
                        shortcuts: [
                            { name: '再生 / 一時停止の切り替え', keys: [{name: 'Space', icon: false}] },
                            { name: '再生 / 一時停止の切り替え (キャプチャタブ表示時)', keys: [{name: 'Shift', icon: false}, {name: 'Space', icon: false}] },
                            { name: 'プレイヤーの音量を上げる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-up-12-filled', icon: true}] },
                            { name: 'プレイヤーの音量を下げる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-down-12-filled', icon: true}] },
                            { name: '停止して0.5秒早戻し', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-left-12-filled', icon: true}] },
                            { name: '停止して0.5秒早送り', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-right-12-filled', icon: true}] },
                            { name: 'フルスクリーンの切り替え', keys: [{name: 'F', icon: false}] },
                            { name: 'ライブストリームの同期', keys: [{name: 'W', icon: false}] },
                            { name: 'Picture-in-Picture の表示切り替え', keys: [{name: 'E', icon: false}] },
                            { name: '字幕の表示切り替え', keys: [{name: 'S', icon: false}] },
                            { name: 'コメントの表示切り替え', keys: [{name: 'D', icon: false}] },
                            { name: '映像をキャプチャする', keys: [{name: 'C', icon: false}] },
                            { name: '映像をコメントを付けてキャプチャする', keys: [{name: 'V', icon: false}] },
                            { name: 'コメント入力フォームにフォーカスする', keys: [{name: 'M', icon: false}] },
                            { name: 'コメント入力フォームを閉じる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'M', icon: false}] },
                            { name: 'コメントを送信する', keys: [{name: 'コメント入力フォームを表示', icon: false}, {name: 'Enter', icon: false}] },
                        ]
                    },
                ],
                right_column: [
                    {
                        name: 'パネル',
                        icon: 'fluent:panel-right-20-filled',
                        icon_height: '24px',
                        shortcuts: [
                            { name: 'パネルの表示切り替え', keys: [{name: 'P', icon: false}] },
                            { name: '番組情報タブを表示する', keys: [{name: 'K', icon: false}] },
                            { name: 'チャンネルタブを表示する', keys: [{name: 'L', icon: false}] },
                            { name: 'コメントタブを表示する', keys: [{name: '；(＋)', icon: false}] },
                            { name: 'Twitter タブを表示する', keys: [{name: '：(＊)', icon: false}] },
                        ]
                    },
                    {
                        name: 'Twitter',
                        icon: 'fa-brands:twitter',
                        icon_height: '22px',
                        shortcuts: [
                            { name: 'ツイート検索タブを表示する', keys: [{name: '［ (「)', icon: false}] },
                            { name: 'タイムラインタブを表示する', keys: [{name: '］ (」)', icon: false}] },
                            { name: 'キャプチャタブを表示する', keys: [{name: '＼(￥)', icon: false}] },
                            { name: 'ツイート入力フォームにフォーカスを当てる/フォーカスを外す', keys: [{name: 'Tab', icon: false}] },
                            { name: 'キャプチャにフォーカスする', keys: [{name: 'キャプチャタブを表示', icon: false}, {name: 'fluent:arrow-up-12-filled;fluent:arrow-down-12-filled;fluent:arrow-left-12-filled;fluent:arrow-right-12-filled', icon: true}] },
                            { name: 'キャプチャを拡大表示する/<br>キャプチャの拡大表示を閉じる', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Enter', icon: false}] },
                            { name: 'キャプチャを選択する/<br>キャプチャの選択を解除する', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Space', icon: false}] },
                            { name: 'クリップボード内の画像を<br>キャプチャとして取り込む', keys: [{name: 'ツイート入力<br>フォームにフォーカス', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'V', icon: false}] },
                            { name: 'ツイートを送信する', keys: [{name: 'Twitter タブを表示', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'Enter', icon: false}] },
                        ]
                    },
                ]
            }
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

        // チャンネル選局のキーボードショートカットを Alt or Option + 数字キー/テンキーに変更する設定が有効なら、
        // キーボードショートカット一覧に反映する
        if (this.settingsStore.settings.tv_channel_selection_requires_alt_key === true) {
            this.shortcut_key_list.left_column[0].shortcuts[0].keys.unshift({name: Utils.AltOrOption(), icon: false});
            this.shortcut_key_list.left_column[0].shortcuts[1].keys.unshift({name: Utils.AltOrOption(), icon: false});
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

            // 現在時刻を1秒おきに更新
            this.interval_ids.push(window.setInterval(() => this.time = dayjs().format('YYYY/MM/DD HH:mm:ss'), 1 * 1000));

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

// DPlayer のスタイルの上書き
.watch-player__dplayer {
    svg circle, svg path {
        fill: var(--v-text-base) !important;
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
        padding-bottom: 6px !important;
        transition: opacity 0.3s ease, visibility 0.3s ease;
        opacity: 0 !important;
        visibility: hidden;
        @include tablet-vertical {
            padding-left: calc(0px + 18px) !important;
        }
        @include smartphone-horizontal {
            padding-left: calc(0px + 18px) !important;
        }
        @include smartphone-vertical {
            padding-left: calc(0px + 18px) !important;
        }

        .dplayer-time, .dplayer-live-badge {
            color: var(--v-text-base) !important;
        }
        .dplayer-volume-bar {
            background: var(--v-text-base) !important;
        }
        .dplayer-icons {
            bottom: auto !important;
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
            // ブラウザフルスクリーンボタンを削除（実質あまり意味がないため）
            .dplayer-icon.dplayer-full-in-icon {
                display: none !important;
            }
            .dplayer-icon {
                @include tablet-vertical {
                    &.dplayer-pip-icon:after {
                        left: 25%;
                    }
                    &.dplayer-full-icon:after {
                        left: -20%;
                    }
                }
                @include smartphone-horizontal {
                    &.dplayer-pip-icon:after {
                        left: 25%;
                    }
                    &.dplayer-full-icon:after {
                        left: -20%;
                    }
                }
                @include smartphone-vertical {
                    &.dplayer-pip-icon:after {
                        left: 25%;
                    }
                    &.dplayer-full-icon:after {
                        left: -20%;
                    }
                }
                &.dplayer-capture-icon, &.dplayer-comment-capture-icon {
                    transition: background-color 0.08s ease;
                    border-radius: 6px;
                    &.dplayer-capturing {
                        background: var(--v-secondary-lighten1);
                        .dplayer-icon-content {
                            opacity: 1;
                        }
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
        @include smartphone-vertical {
            height: calc(100% - 60px) !important;
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
        .dplayer-comment-setting-title {
            color: var(--v-text-base);
        }
        .dplayer-comment-setting-type, .dplayer-comment-setting-size {
            span {
                border: 1px solid (--v-text-base);
            }
            input:checked + span {
                background: var(--v-text-base);
            }
        }
    }

    // モバイルのみ適用されるスタイル
    &.dplayer-mobile {
        .dplayer-controller {
            padding-left: calc(68px + 30px) !important;
            @include tablet-vertical {
                padding-left: calc(0px + 18px) !important;
            }
            @include smartphone-horizontal {
                padding-left: calc(0px + 18px) !important;
            }
            @include smartphone-vertical {
                padding-left: calc(0px + 18px) !important;
            }
        }
        &.dplayer-hide-controller .dplayer-controller {
            transform: none !important;
        }
    }
}

// ロード中は動画と BML ブラウザを非表示にする
.watch-player--loading {
    .dplayer-video-wrap-aspect, .dplayer-bml-browser {
        opacity: 0 !important;
    }
}

// Safari のみ、アイコンに hover しても opacity が変わらないようにする
// hover すると 1px ずれてしまい見苦しくなる Safari の描画バグを回避するための苦肉の策
// ref: https://qiita.com/Butterthon/items/10e6b58d883236aa3838
_::-webkit-full-page-media, _:future, :root .dplayer-icon:hover .dplayer-icon-content {
    opacity: 0.8 !important;
}

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

// ショートカットキーの表示スタイル
.shortcut-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    min-width: 32px;
    min-height: 28px;
    padding: 3px 8px;
    border-radius: 5px;
    background-color: var(--v-background-lighten2);
    font-size: 14.5px;
    text-align: center;
}
.shortcut-key-plus {
    display: inline-block;
    margin: 0px 5px;
    flex-shrink: 0;
}

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

                    .watch-player__background-logo {
                        display: inline-block;
                        position: absolute;
                        height: 34px;
                        right: 56px;
                        bottom: 44px;
                        filter: drop-shadow(0px 0px 5px var(--v-black-base));

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
                color: var(--v-background-lighten3);
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

                .switch-button {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    width: 48px;
                    height: 48px;
                    color: var(--v-text-base);
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
    }
}

</style>