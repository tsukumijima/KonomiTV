<template>
    <div class="route-container">
        <main class="watch-container" :class="{
                'watch-container--control-display': is_control_display,
                'watch-container--panel-display': is_panel_display,
                'watch-container--fullscreen': is_fullscreen,
            }">
            <nav class="watch-navigation"
                 @mousemove="controlDisplayTimer($event)"
                 @touchmove="controlDisplayTimer($event)"
                 @click="controlDisplayTimer($event)">
                <router-link v-ripple class="watch-navigation__icon" to="/tv/">
                    <img class="watch-navigation__icon-image" src="/assets/images/icon.svg" width="23px">
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'テレビをみる'" to="/tv/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'ビデオをみる'"  to="/videos/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'番組表'" to="/timetable/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:calendar-ltr-20-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'キャプチャ'" to="/captures/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:image-multiple-24-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'ウォッチリスト'" to="/watchlists/">
                    <Icon class="watch-navigation__link-icon" icon="ic:round-playlist-play" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'視聴履歴'" to="/histories/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:history-16-regular" width="26px" />
                </router-link>
                <v-spacer></v-spacer>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                             v-tooltip.right="'設定'" to="/settings/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:settings-20-regular" width="26px" />
                </router-link>
                <a v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
                   v-tooltip.right="`version ${Utils.version}`" href="https://github.com/tsukumijima/KonomiTV">
                    <Icon class="watch-navigation__link-icon" icon="fluent:info-16-regular" width="26px" />
                </a>
            </nav>
            <div class="watch-content"
                 @mousemove="controlDisplayTimer($event, true)"
                 @touchmove="controlDisplayTimer($event, true)"
                 @click="controlDisplayTimer($event, true)">
                <header class="watch-header">
                    <img class="watch-header__broadcaster" :src="`${Utils.api_base_url}/channels/${($route.params.channel_id)}/logo`">
                    <span class="watch-header__program-title" v-html="ProgramUtils.decorateProgramInfo(channel.program_present, 'title')"></span>
                    <span class="watch-header__program-time">{{ProgramUtils.getProgramTime(channel.program_present, true)}}</span>
                    <v-spacer></v-spacer>
                    <span class="watch-header__now">{{time}}</span>
                </header>
                <div class="watch-player" :class="{'watch-player--loading': is_loading}">
                    <div class="watch-player__background" :class="{'watch-player__background--display': is_background_display}"
                        :style="{backgroundImage: `url(${background_url})`}">
                        <img class="watch-player__background-logo" src="/assets/images/logo.svg">
                    </div>
                    <v-progress-circular indeterminate size="60" width="6" class="watch-player__buffering"
                        :class="{'watch-player__buffering--display': is_video_buffering && (is_loading || (player !== null && !player.video.paused))}">
                    </v-progress-circular>
                    <div class="watch-player__dplayer"></div>
                    <div class="watch-player__button"
                         @mousemove="controlDisplayTimer($event)"
                         @touchmove="controlDisplayTimer($event)"
                         @click="controlDisplayTimer($event)">
                        <router-link v-ripple class="switch-button switch-button-up" :to="`/tv/watch/${channel_previous.channel_id}`"
                                     v-tooltip.top="'前のチャンネル'">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-left-24-filled" width="32px" rotate="1" />
                        </router-link>
                        <div v-ripple class="switch-button switch-button-panel switch-button-panel--open"
                             @click="is_panel_display = !is_panel_display">
                            <Icon class="switch-button-icon" icon="fluent:navigation-16-filled" width="32px" />
                        </div>
                        <router-link v-ripple class="switch-button switch-button-down" :to="`/tv/watch/${channel_next.channel_id}`"
                                     v-tooltip.bottom="'次のチャンネル'">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-right-24-filled" width="33px" rotate="1" />
                        </router-link>
                    </div>
                </div>
            </div>
            <div class="watch-panel"
                 @mousemove="controlDisplayTimer($event)"
                 @touchmove="controlDisplayTimer($event)"
                 @click="controlDisplayTimer($event)">
                <div class="watch-panel__header">
                    <div v-ripple class="panel-close-button" @click="is_panel_display = false">
                        <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
                        <span class="panel-close-button__text">閉じる</span>
                    </div>
                    <v-spacer></v-spacer>
                    <div class="panel-broadcaster">
                        <img class="panel-broadcaster__icon" :src="`${Utils.api_base_url}/channels/${($route.params.channel_id)}/logo`">
                        <div class="panel-broadcaster__number">{{channel.channel_number}}</div>
                        <div class="panel-broadcaster__name">{{channel.channel_name}}</div>
                    </div>
                </div>
                <div class="watch-panel__content-container">
                    <Program class="watch-panel__content"
                        :class="{'watch-panel__content--active': tv_panel_active_tab === 'Program'}" :channel="channel" />
                    <Channel class="watch-panel__content"
                        :class="{'watch-panel__content--active': tv_panel_active_tab === 'Channel'}" :channels_list="channels_list" />
                    <Comment class="watch-panel__content" ref="Comment"
                        :class="{'watch-panel__content--active': tv_panel_active_tab === 'Comment'}" :channel="channel" :player="player" />
                    <Twitter class="watch-panel__content" ref="Twitter" @panel_folding_requested="is_panel_display = false"
                        :class="{'watch-panel__content--active': tv_panel_active_tab === 'Twitter'}" :channel="channel" :player="player" />
                </div>
                <div class="watch-panel__navigation">
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': tv_panel_active_tab === 'Program'}"
                         @click="tv_panel_active_tab = 'Program'">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                        <span class="panel-navigation-button__text">番組情報</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': tv_panel_active_tab === 'Channel'}"
                         @click="tv_panel_active_tab = 'Channel'">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                        <span class="panel-navigation-button__text">チャンネル</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': tv_panel_active_tab === 'Comment'}"
                         @click="tv_panel_active_tab = 'Comment'">
                        <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="29px" />
                        <span class="panel-navigation-button__text">コメント</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': tv_panel_active_tab === 'Twitter'}"
                         @click="tv_panel_active_tab = 'Twitter'">
                        <Icon class="panel-navigation-button__icon" icon="fa-brands:twitter" width="34px" />
                        <span class="panel-navigation-button__text">Twitter</span>
                    </div>
                </div>
            </div>
        </main>
        <v-dialog max-width="1000" transition="slide-y-transition" v-model="shortcut_key_modal">
            <v-card>
                <v-card-title class="px-5 pt-4 pb-3 d-flex align-center font-weight-bold">
                    <Icon icon="fluent:keyboard-20-filled" height="28px" />
                    <span class="ml-3">キーボードショートカット</span>
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
                <v-divider></v-divider>
                <v-card-actions class="px-5 py-3">
                    <v-spacer></v-spacer>
                    <v-btn color="background lighten-2 px-3" elevation="0" @click="shortcut_key_modal = false">閉じる</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>
<script lang="ts">

import { AxiosResponse } from 'axios';
import dayjs from 'dayjs';
// @ts-ignore  JavaScript で書かれているので型定義がなく、作ろうとするとややこしくなるので黙殺
import DPlayer from 'dplayer';
import mpegts from 'mpegts.js';
import Vue from 'vue';

import { ChannelTypePretty, IChannel, IChannelDefault } from '@/interface';
import Channel from '@/components/Panel/Channel.vue';
import Comment from '@/components/Panel/Comment.vue';
import Program from '@/components/Panel/Program.vue';
import Twitter from '@/components/Panel/Twitter.vue';
import Utils, { ChannelUtils, PlayerCaptureHandler, PlayerUtils, ProgramUtils } from '@/utils';

// 低遅延モードオン時の再生バッファ (秒単位)
// これ以上小さくすると再生が詰まりやすくなる印象
const PLAYBACK_BUFFER_SEC_LOW_LATENCY = 1.5;

// 低遅延モードオフ時の再生バッファ (秒単位)
// 3秒程度の遅延を許容する
const PLAYBACK_BUFFER_SEC = 3.0;

export default Vue.extend({
    name: 'TV-Watch',
    components: {
        Channel,
        Comment,
        Program,
        Twitter,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ProgramUtils: ProgramUtils,

            // 現在時刻
            time: dayjs().format('YYYY/MM/DD HH:mm:ss'),

            // 表示されるパネルのタブ
            tv_panel_active_tab: Utils.getSettingsItem('tv_panel_active_tab'),

            // 背景の URL
            background_url: '',

            // プレイヤーのローディング状態
            // 既定でローディングとする
            is_loading: true,

            // プレイヤーが映像の再生をバッファリングしているか
            // 視聴開始時以外にも、ネットワークが遅くて再生が一時的に途切れたときなどで表示される
            // 既定でバッファリング中とする
            is_video_buffering: true,

            // プレイヤーの背景を表示するか
            // 既定で表示しない
            is_background_display: false,

            // コントロールを表示するか
            // 既定で表示する
            is_control_display: true,

            // パネルを表示するか
            // panel_display_state が 'AlwaysDisplay' なら常に表示し、'AlwaysFold' なら常に折りたたむ
            // 'RestorePreviousState' なら showed_panel_last_time の値を使い､前回の状態を復元する
            is_panel_display: (() => {
                switch (Utils.getSettingsItem('panel_display_state')) {
                    case 'AlwaysDisplay':
                        return true;
                    case 'AlwaysFold':
                        return false;
                    case 'RestorePreviousState':
                        return Utils.getSettingsItem('showed_panel_last_time');
                }
            })() as boolean,

            // フルスクリーン状態かどうか
            is_fullscreen: false,

            // IME 変換中かどうか
            is_ime_composing: false,

            // プレイヤーからのコメント送信から間もないかどうか
            is_comment_send_just_did: false,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [] as number[],

            // コントロール表示切り替え用のインターバル ID
            // 混ぜるとダメなので独立させる
            control_interval_id: 0,

            // ***** チャンネル *****

            // チャンネル ID
            channel_id: this.$route.params.channel_id,

            // チャンネル情報
            // IChannelDefault に情報取得が完了するまでの間表示される初期値が定義されている
            channel: IChannelDefault,

            // 前のチャンネルのチャンネル情報
            channel_previous: IChannelDefault,

            // 次のチャンネルのチャンネル情報
            channel_next: IChannelDefault,

            // チャンネル情報リスト
            channels_list: new Map() as Map<ChannelTypePretty, IChannel[]>,

            // ***** プレイヤー *****

            // プレイヤー (DPlayer) のインスタンス
            player: null,

            // RomSound の AudioContext
            romsounds_context: null as AudioContext | null,

            // RomSound の AudioBuffer（音声データ）が入るリスト
            romsounds_buffers: [] as AudioBuffer[] | null,

            // イベントソースのインスタンス
            eventsource: null as EventSource | null,

            // フルスクリーン状態が切り替わったときのハンドラー
            fullscreen_handler: null as () => void | null,

            // キャプチャハンドラーのインスタンス
            capture_handler: null as PlayerCaptureHandler | null,

            // ***** キーボードショートカット *****

            // ショートカットキーのハンドラー
            shortcut_key_handler: null as (event: KeyboardEvent) => void | null,

            // ショートカットキーの最終押下時刻のタイムスタンプ
            shortcut_key_pressed_at: Date.now(),

            // キーボードショートカットの一覧のモーダルを表示するか
            shortcut_key_modal: false,

            // キーボードショートカットの一覧に表示するショートカットキーのリスト
            shortcut_key_list: {
                left_column: [
                    {
                        name: '全般',
                        icon: 'fluent:home-20-filled',
                        icon_height: '22px',
                        shortcuts: [
                            { name: '数字キー・テンキーに対応するリモコン番号 (1~12) の地デジチャンネルに切り替える', keys: [{name: '1~9, 0, -(=), ^(~)', icon: false}] },
                            { name: '数字キー・テンキーに対応するリモコン番号 (1~12) の BS チャンネルに切り替える', keys: [{name: 'Shift', icon: false}, {name: '1~9, 0, -(=), ^(~)', icon: false}] },
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
        }
    },
    // 開始時に実行
    async created() {

        // 再生セッションを初期化
        this.init();

        // RomSound を鳴らすための AudioContext を生成
        this.romsounds_context = new AudioContext();

        // 01 ~ 14 まですべての RomSound を読み込む
        for (let index = 1; index <= 14; index++) {

            // ArrayBuffer として RomSound を取得
            const url = `/assets/romsounds/${index.toString().padStart(2, '0')}.wav`;
            const audio_data = await Vue.axios.get(url, {
                baseURL: '',  // BaseURL を明示的にクライアントのルートに設定
                responseType: 'arraybuffer',
            });

            // ArrayBuffer をデコードして AudioBuffer にし、すぐ呼び出せるように貯めておく
            // ref: https://ics.media/entry/200427/
            this.romsounds_buffers.push(await this.romsounds_context.decodeAudioData(audio_data.data));
        }
    },
    // 終了前に実行
    beforeDestroy() {

        // destroy() を実行
        // 別のページへ遷移するため、DPlayer のインスタンスを確実に破棄する
        // さもなければ、ブラウザがリロードされるまでバックグラウンドで永遠に再生され続けてしまう
        this.destroy(true);

        // AudioContext のリソースを解放
        this.romsounds_context.close();
    },
    // チャンネル切り替え時に実行
    // コンポーネント（インスタンス）は再利用される
    // ref: https://router.vuejs.org/ja/guide/advanced/navigation-guards.html#%E3%83%AB%E3%83%BC%E3%83%88%E5%8D%98%E4%BD%8D%E3%82%AB%E3%82%99%E3%83%BC%E3%83%88%E3%82%99
    beforeRouteUpdate(to, from, next) {

        // 前の再生セッションを破棄して終了する
        this.destroy();

        // チャンネル ID を次のチャンネルのものに切り替える
        this.channel_id = to.params.channel_id;

        // 既に取得済みのチャンネル情報で、前・現在・次のチャンネル情報を更新する
        [this.channel_previous, this.channel, this.channel_next]
            = ChannelUtils.getPreviousAndCurrentAndNextChannel(this.channels_list, this.channel_id);

        // 0.5秒だけ待ってから、新しい再生セッションを初期化する
        // 連続して押した時などに毎回再生処理を開始しないように猶予を設ける
        this.interval_ids.push(window.setTimeout(() => this.init(), 500));

        next();
    },
    watch: {
        // 前回視聴画面を開いた際にパネルが表示されていたかどうかを保存
        is_panel_display() {
            Utils.setSettingsItem('showed_panel_last_time', this.is_panel_display);
        }
    },
    methods: {

        // 再生セッションを初期化する
        init() {

            // ローディング中の背景画像をランダムで設定
            this.background_url = PlayerUtils.generatePlayerBackgroundURL();

            // コントロール表示タイマーを実行
            this.controlDisplayTimer();

            // チャンネル情報を取得
            this.update();

            // 現在時刻を1秒おきに更新
            this.interval_ids.push(window.setInterval(() => {
                this.time = dayjs().format('YYYY/MM/DD HH:mm:ss');
            }, 1 * 1000));

            // 00秒までの残り秒数
            // 現在 16:01:34 なら 26 (秒) になる
            const residue_second = 60 - (Math.floor(new Date().getTime() / 1000) % 60);

            // 00秒になるまで待ってから
            // 番組は基本1分単位で組まれているため、20秒や45秒など中途半端な秒数で更新してしまうと反映が遅れてしまう
            this.interval_ids.push(window.setTimeout(() => {

                // チャンネル情報を更新
                this.update();

                // チャンネル情報を定期的に更新
                this.interval_ids.push(window.setInterval(() => {
                    this.update();
                }, 30 * 1000));  // 30秒おき

            }, residue_second * 1000));
        },

        // チャンネル情報一覧を取得し、画面を更新する
        async update() {

            // チャンネル ID が未定義なら実行しない（フェイルセーフ）
            if (this.$route.params.channel_id === undefined) {
                return;
            }

            // チャンネル情報 API にアクセス
            let channel_response: AxiosResponse;
            try {
                channel_response = await Vue.axios.get(`/channels/${this.channel_id}`);
            } catch (error) {

                // エラー内容を表示
                console.error(error);

                // ステータスコードが 422（チャンネルが存在しない）なら 404 ページにリダイレクト
                // 正確には 404 ページ自体がルートとして存在するわけじゃないけど、そもそも存在しないページなら 404 になるので
                if (error.response && error.response.status === 422 && error.response.data.detail === 'Specified channel_id was not found') {
                    await this.$router.push({path: '/not-found/'});
                }

                // 処理を中断
                return;
            }

            // チャンネル情報を代入
            this.channel = channel_response.data;

            // プレイヤーがまだ初期化されていない or 他のチャンネルからの切り替えですでにプレイヤーが初期化されているけど破棄が可能
            // update() 自体は初期化時以外にも1分ごとに定期実行されるため、その際に毎回プレイヤーを再初期化しないようにする
            if (this.player === null || this.player.KonomiTVCanDestroy === true) {

                // プレイヤー (DPlayer) 周りのセットアップ
                this.initPlayer();

                // サーバーから送られてくるメッセージのイベントハンドラーを初期化
                this.initEventHandler();

                // キャプチャのイベントハンドラーを初期化
                this.initCaptureHandler();

                // ショートカットキーのイベントハンドラーを初期化
                // 事前に前のイベントハンドラーを削除しておかないと、重複してキー操作が実行されてしまう
                // 直前で実行しないと上下キーでのチャンネル操作が動かなくなる
                document.removeEventListener('keydown', this.shortcut_key_handler);
                this.initShortcutKeyHandler();
            }

            // 副音声がない番組でプレイヤー上で副音声に切り替えられないように
            // 音声多重放送でもデュアルモノでもない番組のみ
            if ((this.channel.program_present === null) ||
               ((this.channel.program_present.primary_audio_type !== '1/0+1/0モード(デュアルモノ)') &&
                (this.channel.program_present.secondary_audio_type === null))) {

                // クラスを付与
                this.player.template.audioItem[1].classList.add('dplayer-setting-audio-item--disabled');

                // 現在副音声が選択されている可能性を考慮し、明示的に主音声に切り替える
                if (this.player.plugins.mpegts) {
                    window.setTimeout(() => {  // プレイヤーの初期化が完了するまで少し待つ
                        this.player.template.audioItem[0].classList.add('dplayer-setting-audio-current');
                        this.player.template.audioItem[1].classList.remove('dplayer-setting-audio-current');
                        this.player.template.audioValue.textContent = this.player.tran('Primary audio');
                        try {
                            this.player.plugins.mpegts.switchPrimaryAudio();
                        } catch (error) {
                            // pass
                        }
                    }, 300);
                }

            // 音声多重放送かデュアルモノなので、副音声への切り替えを有効化
            } else {

                // クラスを削除
                this.player.template.audioItem[1].classList.remove('dplayer-setting-audio-item--disabled');
            }

            // チャンネル情報一覧 API にアクセス
            // チャンネル情報 API と同時にアクセスするとむしろレスポンスが遅くなるので、返ってくるのを待ってから実行
            let channels_response: AxiosResponse;
            try {
                channels_response = await Vue.axios.get('/channels');
            } catch (error) {
                console.error(error);   // エラー内容を表示
                return;
            }

            // is_display が true または現在表示中のチャンネルのみに絞り込むフィルタ関数
            // 放送していないサブチャンネルを表示から除外する
            const filter = (channel: IChannel) => {
                return channel.is_display || this.channel_id === channel.channel_id;
            }

            // チャンネルリストを再構築
            // 1つでもチャンネルが存在するチャンネルタイプのみ表示するように
            // たとえば SKY (スカパー！プレミアムサービス) のタブは SKY に属すチャンネルが1つもない（=受信できない）なら表示されない
            this.channels_list = new Map();
            this.channels_list.set('ピン留め', []);  // ピン留めタブの準備
            if (channels_response.data.GR.length > 0) this.channels_list.set('地デジ', channels_response.data.GR.filter(filter));
            if (channels_response.data.BS.length > 0) this.channels_list.set('BS', channels_response.data.BS.filter(filter));
            if (channels_response.data.CS.length > 0) this.channels_list.set('CS', channels_response.data.CS.filter(filter));
            if (channels_response.data.CATV.length > 0) this.channels_list.set('CATV', channels_response.data.CATV.filter(filter));
            if (channels_response.data.SKY.length > 0) this.channels_list.set('SKY', channels_response.data.SKY.filter(filter));
            if (channels_response.data.STARDIGIO.length > 0) this.channels_list.set('StarDigio', channels_response.data.STARDIGIO.filter(filter));

            // ピン留めされているチャンネルの ID を取得
            const pinned_channel_ids = Utils.getSettingsItem('pinned_channel_ids');

            // ピン留めされているチャンネル情報のリスト
            const pinned_channels = [] as IChannel[];

            // チャンネル ID が一致したチャンネルの情報を保存する
            for (const pinned_channel_id of pinned_channel_ids) {
                const pinned_channel_type = ChannelUtils.getChannelType(pinned_channel_id, true) as ChannelTypePretty;
                const pinned_channel = this.channels_list.get(pinned_channel_type).find((channel) => {
                    return channel.channel_id === pinned_channel_id;  // チャンネル ID がピン留めされているチャンネルのものと同じ
                });
                // チャンネル情報を取得できているときだけ
                // サブチャンネルをピン留めしたが、マルチ編成が終了して現在は放送していない場合などに備える (BS142 など)
                // 現在放送していないチャンネルは this.channels_list に入れた段階で弾いているため、チャンネル情報を取得できない
                if (pinned_channel !== undefined) {
                    pinned_channels.push(pinned_channel);
                }
            }

            // pinned_channels に何か入っていたらピン留めタブを表示するし、そうでなければ表示しない
            if (pinned_channels.length > 0) {
                this.channels_list.set('ピン留め', pinned_channels);
            } else {
                this.channels_list.delete('ピン留め');
            }

            // 前と次のチャンネル ID を取得する
            [this.channel_previous, , this.channel_next] = ChannelUtils.getPreviousAndCurrentAndNextChannel(this.channels_list, this.channel_id);

            // MediaSession API を使い、メディア通知の表示をカスタマイズ
            if ('mediaSession' in navigator) {

                // アートワークとして表示するアイコン
                const artwork = [
                    {src: '/assets/images/icons/icon-maskable-192px.png', sizes: '192x192', type: 'image/png'},
                    {src: '/assets/images/icons/icon-maskable-512px.png', sizes: '512x512', type: 'image/png'},
                ];

                // メディア通知の表示をカスタマイズ
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: this.channel.program_present ? this.channel.program_present.title : '放送休止',
                    artist: this.channel.channel_name,
                    artwork: artwork,
                });

                // 再生状況のステータスを設定
                if ('setPositionState' in navigator.mediaSession) {
                    navigator.mediaSession.setPositionState({
                        duration: 0,  // ライブなので0（長さなしを表すらしい）に設定
                        playbackRate: 1,  // ライブなので再生速度は常に1になる
                    });
                }

                // メディア通知上のボタンが押されたときのイベント
                navigator.mediaSession.setActionHandler('play', () => { this.player.play() });  // 再生
                navigator.mediaSession.setActionHandler('pause', () => { this.player.pause() });  // 停止
                navigator.mediaSession.setActionHandler('previoustrack', async () => {  // 前のチャンネルに切り替え
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: this.channel_previous.program_present ? this.channel_previous.program_present.title : '放送休止',
                        artist: this.channel_previous.channel_name,
                        artwork: artwork,
                    });
                    // ルーティングを前のチャンネルに置き換える
                    await this.$router.push({path: `/tv/watch/${this.channel_previous.channel_id}`});
                });
                navigator.mediaSession.setActionHandler('nexttrack', async () => {  // 次のチャンネルに切り替え
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: this.channel_next.program_present ? this.channel_next.program_present.title : '放送休止',
                        artist: this.channel_next.channel_name,
                        artwork: artwork,
                    });
                    // ルーティングを次のチャンネルに置き換える
                    await this.$router.push({path: `/tv/watch/${this.channel_next.channel_id}`});
                });
            }
        },

        // マウスが動いたりタップされた時のイベント
        // 3秒間何も操作がなければコントロールを非表示にする
        controlDisplayTimer(event: Event | null = null, is_player_event: boolean = false) {

            // タッチデバイスかどうか
            // DPlayer の UA 判定コードと同一
            const is_touch_device = /iPhone|iPad|iPod|Windows|Macintosh|Android|Mobile/i.test(navigator.userAgent) && 'ontouchend' in document;

            // タッチデバイスで mousemove 、あるいはタッチデバイス以外で touchmove か click が発火した時は実行じない
            if (is_touch_device == true  && event !== null && event.type === 'mousemove') return;
            if (is_touch_device == false && event !== null && (event.type === 'touchmove' || event.type === 'click')) return;

            // 以前セットされたタイマーを止める
            window.clearTimeout(this.control_interval_id);

            // setTimeout に渡すタイマー関数
            const timeout = () => {

                // コメント入力フォームが表示されているときは実行しない
                // タイマーを掛け直してから抜ける
                if (this.player !== null && this.player.template.controller.classList.contains('dplayer-controller-comment')) {
                    this.control_interval_id = window.setTimeout(timeout, 3 * 1000);
                    return;
                }

                // コントロールを非表示にする
                this.is_control_display = false;

                // プレイヤーのコントロールと設定パネルを非表示にする
                if (this.player !== null) {
                    this.player.controller.hide();
                    this.player.setting.hide();
                }
            }

            // タッチデバイスでプレイヤー画面がクリックされたとき
            if (is_touch_device === true && is_player_event === true) {

                // プレイヤーのコントロールの表示状態に合わせる
                if (this.player.controller.isShow()) {

                    // コントロールを表示する
                    this.is_control_display = true;

                    // プレイヤーのコントロールを表示する
                    this.player.controller.show();

                    // 3秒間何も操作がなければコントロールを非表示にする
                    // 3秒間の間一度でもマウスが動けばタイマーが解除されてやり直しになる
                    this.control_interval_id = window.setTimeout(timeout, 3 * 1000);

                } else {

                    // コントロールを非表示にする
                    this.is_control_display = false;

                    // プレイヤーのコントロールと設定パネルを非表示にする
                    this.player.controller.hide();
                    this.player.setting.hide();
                }

            // それ以外の画面がクリックされたとき
            } else {

                // コントロールを表示する
                this.is_control_display = true;

                // プレイヤーのコントロールを表示する
                if (this.player !== null) {
                    this.player.controller.show();
                }

                // 3秒間何も操作がなければコントロールを非表示にする
                // 3秒間の間一度でもマウスが動けばタイマーが解除されてやり直しになる
                this.control_interval_id = window.setTimeout(timeout, 3 * 1000);
            }
        },

        // プレイヤーを初期化する
        initPlayer() {

            // mpegts.js を window 直下に入れる
            // こうしないと DPlayer が mpegts.js を認識できない
            (window as any).mpegts = mpegts;

            // すでに DPlayer が初期化されている場合は破棄する
            // チャンネル切り替え時などが該当する
            if (this.player !== null && this.player.KonomiTVCanDestroy === true) {
                try {
                    this.player.destroy();
                } catch (error) {
                    // mpegts.js をうまく破棄できない場合
                    if (this.player.plugins.mpegts !== undefined) {
                        this.player.plugins.mpegts.destroy();
                    }
                }
                this.player = null;
            }

            // 低遅延モードであれば低遅延向けの再生バッファを、そうでなければ通常の再生バッファをセット (秒単位)
            const playback_buffer_sec = Utils.getSettingsItem('tv_low_latency_mode') ?
                PLAYBACK_BUFFER_SEC_LOW_LATENCY : PLAYBACK_BUFFER_SEC;

            // DPlayer を初期化
            this.player = new DPlayer({
                container: this.$el.querySelector('.watch-player__dplayer'),
                theme: '#E64F97',  // テーマカラー
                lang: 'ja-jp',  // 言語
                live: true,  // ライブモード
                liveSyncMinBufferSize: playback_buffer_sec,  // ライブモードで同期する際の最小バッファサイズ
                loop: false,  // ループ再生 (ライブのため無効化)
                airplay: false,  // AirPlay 機能 (うまく動かないため無効化)
                autoplay: true,  // 自動再生
                hotkey: false,  // ショートカットキー（こちらで制御するため無効化）
                screenshot: false,  // スクリーンショット (こちらで制御するため無効化)
                volume: 1.0,  // 音量の初期値
                // 映像
                video: {
                    // デフォルトの品質
                    // ラジオチャンネルでは常に 48KHz/192kbps に固定する
                    defaultQuality: (this.channel.is_radiochannel) ? '48kHz/192kbps' : Utils.getSettingsItem('tv_streaming_quality'),
                    // 品質リスト
                    quality: (() => {
                        const qualities = [];
                        // ラジオチャンネル
                        // API が受け付ける品質の値は通常のチャンネルと同じだが (手抜き…)、実際の品質は 48KHz/192kbps で固定される
                        // ラジオチャンネルの場合は、1080p と渡しても 48kHz/192kbps 固定の音声だけの MPEG-TS が配信される
                        if (this.channel.is_radiochannel) {
                            qualities.push({
                                name: '48kHz/192kbps',
                                type: 'mpegts',
                                url: `${Utils.api_base_url}/streams/live/${this.channel_id}/1080p/mpegts`,
                            });
                        // 通常のチャンネル
                        } else {
                            // ブラウザが H.265 / HEVC の再生に対応していて、かつ通信節約モードが有効なとき
                            // API に渡す画質に -hevc のプレフィックスをつける
                            let hevc_prefix = '';
                            if (PlayerUtils.isHEVCVideoSupported() && Utils.getSettingsItem('tv_data_saver_mode') === true) {
                                hevc_prefix = '-hevc';
                            }
                            for (const quality of ['1080p-60fps', '1080p', '810p', '720p', '540p', '480p', '360p', '240p']) {
                                qualities.push({
                                    name: quality === '1080p-60fps' ? '1080p (60fps)' : quality,
                                    type: 'mpegts',
                                    url: `${Utils.api_base_url}/streams/live/${this.channel_id}/${quality}${hevc_prefix}/mpegts`,
                                });
                            }
                        }
                        return qualities;
                    })(),
                },
                // コメント
                danmaku: {
                    user: 'KonomiTV',  // 便宜上 KonomiTV に固定
                    speedRate: Utils.getSettingsItem('comment_speed_rate'),  // コメントの流れる速度
                    fontSize: Utils.getSettingsItem('comment_font_size'),  // コメントのフォントサイズ
                },
                // コメント API バックエンド
                apiBackend: {
                    // コメント受信時
                    read: (options) => {
                        // 成功したことにして通知を抑制
                        options.success([{}]);
                    },
                    // コメント送信時
                    send: async (options) => {
                        // Comment コンポーネント内のコメント送信メソッドを呼び出す
                        // ref: https://stackoverflow.com/a/65729556/17124142 ($refs への型設定)
                        await (this.$refs.Comment as InstanceType<typeof Comment>).sendComment(options);
                    },
                },
                // プラグイン
                pluginOptions: {
                    // mpegts.js
                    mpegts: {
                        config: {
                            // Web Worker を有効にする
                            enableWorker: true,
                            // HTMLMediaElement の内部バッファによるライブストリームの遅延を追跡する
                            // liveBufferLatencyChasing と異なり、いきなり再生時間をスキップするのではなく、
                            // 再生速度を少しだけ上げることで再生を途切れさせることなく遅延を追跡する
                            liveSync: Utils.getSettingsItem('tv_low_latency_mode'),
                            // 許容する HTMLMediaElement の内部バッファの最大値 (秒単位, 3秒)
                            liveSyncMaxLatency: 3,
                            // HTMLMediaElement の内部バッファ (遅延) が liveSyncMaxLatency を超えたとき、ターゲットとする遅延時間 (秒単位)
                            liveSyncTargetLatency: playback_buffer_sec,
                            // ライブストリームの遅延の追跡に利用する再生速度 (x1.1)
                            // 遅延が 3 秒を超えたとき、遅延が playback_buffer_sec を下回るまで再生速度が x1.1 に設定される
                            liveSyncPlaybackRate: 1.1,
                        }
                    },
                    // aribb24.js
                    aribb24: {
                        // 描画フォント
                        normalFont: `"${Utils.getSettingsItem('caption_font')}", sans-serif`,
                        // 縁取りする色
                        forceStrokeColor: Utils.getSettingsItem('always_border_caption_text') ? true : false,
                        // 背景色
                        forceBackgroundColor: Utils.getSettingsItem('specify_caption_background_color') ?
                            Utils.getSettingsItem('caption_background_color') : null,
                        // DRCS 文字を対応する Unicode 文字に置換
                        drcsReplacement: true,
                        // 高解像度の字幕 Canvas を取得できるように
                        enableRawCanvas: true,
                        // 縁取りに strokeText API を利用
                        useStrokeText: true,
                        // Unicode 領域の代わりに私用面の領域を利用 (Windows TV 系フォントのみ)
                        usePUA: (() => {
                            const font = Utils.getSettingsItem('caption_font') as string;
                            const context = document.createElement('canvas').getContext('2d');
                            context.font = `10px ${font}`;
                            context.fillText('Test', 0, 0);
                            if (font.startsWith('Windows TV')) {
                                return true;
                            } else {
                                return false;
                            }
                        })(),
                        // 文字スーパーの PRA (内蔵音再生コマンド) のコールバックを指定
                        PRACallback: async (index: number) => {

                            // 設定で文字スーパーが無効なら実行しない
                            if (Utils.getSettingsItem('tv_show_superimpose') === false) return;

                            // index に応じた内蔵音を鳴らす
                            // ref: https://ics.media/entry/200427/
                            // ref: https://www.ipentec.com/document/javascript-web-audio-api-change-volume

                            // 自動再生ポリシーに引っかかったなどで AudioContext が一時停止されている場合、一度 resume() する必要がある
                            // resume() するまでに何らかのユーザーのジェスチャーが行われているはず…
                            // なくても動くこともあるみたいだけど、念のため
                            if (this.romsounds_context.state === 'suspended') {
                                await this.romsounds_context.resume();
                            }

                            // index で指定された音声データを読み込み
                            const buffer_source_node = this.romsounds_context.createBufferSource();
                            buffer_source_node.buffer = this.romsounds_buffers[index];

                            // GainNode につなげる
                            const gain_node = this.romsounds_context.createGain();
                            buffer_source_node.connect(gain_node);

                            // 出力につなげる
                            gain_node.connect(this.romsounds_context.destination);

                            // 音量を元の wav の3倍にする (1倍だと結構小さめ)
                            gain_node.gain.value = 3;

                            // 再生開始
                            buffer_source_node.start(0);
                        },
                    }
                },
                // 字幕
                subtitle: {
                    type: 'aribb24',  // aribb24.js を有効化
                }
            });

            // デバッグ用にプレイヤーインスタンスも window 直下に入れる
            (window as any).player = this.player;

            // プレイヤー側のコントロール非表示タイマーを無効化（上書き）
            // 無効化しておかないと、controlDisplayTimer() と競合してしまう
            // 上書き元のコードは https://github.com/tsukumijima/DPlayer/blob/master/src/js/controller.js#L387-L395 にある
            this.player.controller.setAutoHide = (time: number) => {};

            // ***** コメント送信時のイベントハンドラー *****

            // コメントが送信されたときに、プレイヤーからのコメント送信から間もないかどうかのフラグを立てる (0.1秒後に解除する)
            // コメントを送信するとコメント入力フォームへのフォーカスが外れるため、ページ全体の keydown イベントでは
            // Enter キーの押下がコメント送信由来のイベントかキャプチャ拡大表示由来のイベントかを判断できない
            // そこで、コメント入力フォームフォーカス中に Enter キーが押された場合（=コメント送信時）に 0.1 秒間フラグを立てることで、
            // ショートカットキーハンドラーがコメント送信由来のイベントであることを判定できるようにしている
            this.player.template.commentInput.addEventListener('keydown', (event) => {
                if (event.code === 'Enter') {
                    this.is_comment_send_just_did = true;
                    setTimeout(() => this.is_comment_send_just_did = false, 100);
                }
            });

            // 「コメント送信後にコメント入力フォームを閉じる」がオフになっている時のために、プレイヤー側のコメント送信関数を上書き
            // 上書き部分以外の処理内容は概ね https://github.com/tsukumijima/DPlayer/blob/master/src/js/comment.js に準じる
            this.player.comment.send = () => {

                // コメント入力フォームへのフォーカスを外す (「コメント送信後にコメント入力フォームを閉じる」がオンのときだけ)
                if (Utils.getSettingsItem('close_comment_form_after_sending') === true) {
                this.player.template.commentInput.blur();
                }

                // 空コメントを弾く
                if (!this.player.template.commentInput.value.replace(/^\s+|\s+$/g, '')) {
                    this.player.notice(this.player.tran('Please input danmaku content!'));
                    return;
                }

                // コメントを送信
                this.player.danmaku.send(
                    {
                        text: this.player.template.commentInput.value,
                        color: this.player.container.querySelector('.dplayer-comment-setting-color input:checked').value,
                        type: this.player.container.querySelector('.dplayer-comment-setting-type input:checked').value,
                        size: this.player.container.querySelector('.dplayer-comment-setting-size input:checked').value,
                    },
                    // 送信完了後にコメント入力フォームを閉じる ([コメント送信後にコメント入力フォームを閉じる] がオンのときだけ)
                    () => {
                        if (Utils.getSettingsItem('close_comment_form_after_sending') === true) {
                            this.player.comment.hide();
                        }
                    },
                    true,
                );

                // 重複送信を防ぐ
                this.player.template.commentInput.value = '';
            };

            // ***** 設定パネルのショートカット一覧へのリンクのイベントハンドラー *****

            // 設定パネルにショートカット一覧を表示するリンクを動的に追加する
            // タッチデバイスでは実行しない
            const is_touch_device = /iPhone|iPad|iPod|Macintosh|Android|Mobile/i.test(navigator.userAgent) && 'ontouchend' in document;
            if (is_touch_device === false) {
                this.player.template.settingOriginPanel.insertAdjacentHTML('beforeend', `
                <div class="dplayer-setting-item dplayer-setting-keyboard-shortcut">
                    <span class="dplayer-label">キーボードショートカット</span>
                    <div class="dplayer-toggle">
                        <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32">
                            <path d="M22 16l-10.105-10.6-1.895 1.987 8.211 8.613-8.211 8.612 1.895 1.988 8.211-8.613z"></path>
                        </svg>
                    </div>
                </div>`)

                // 設定パネルの高さを再設定
                const settingOriginPanelHeight = this.player.template.settingOriginPanel.scrollHeight;
                this.player.template.settingBox.style.clipPath = `inset(calc(100% - ${settingOriginPanelHeight}px) 0 0 round 7px)`;

                // 設定パネルのショートカット一覧を表示するリンクがクリックされたときのイベント
                // リアクティブではないので、手動でやらないといけない…
                this.$el.querySelector('.dplayer-setting-keyboard-shortcut').addEventListener('click', () => {
                    this.player.setting.hide();  // 設定パネルを閉じる
                    this.shortcut_key_modal = true;
                });
            }

            // ***** フルスクリーンのイベントハンドラー *****

            // フルスクリーンにするコンテナ要素（ページ全体）
            const fullscreen_container = document.querySelector('.v-application');
            this.fullscreen_handler = () => this.is_fullscreen = this.player.fullScreen.isFullScreen();
            if (fullscreen_container.onfullscreenchange !== undefined) {
                fullscreen_container.addEventListener('fullscreenchange', this.fullscreen_handler);
            } else {
                fullscreen_container.addEventListener('webkitfullscreenchange', this.fullscreen_handler);
            }

            // DPlayer のフルスクリーン関係のメソッドを無理やり上書きし、KonomiTV の UI と統合する
            // 上書き元のコードは https://github.com/tsukumijima/DPlayer/blob/master/src/js/fullscreen.js にある
            // フルスクリーンかどうか
            this.player.fullScreen.isFullScreen = (type: string) => {
                return !!(document.fullscreenElement || document.webkitFullscreenElement);
            }
            // フルスクリーンをリクエスト
            this.player.fullScreen.request = (type: string) => {

                // すでにフルスクリーンだったらキャンセルする
                if (this.player.fullScreen.isFullScreen()) {
                    this.player.fullScreen.cancel();
                    return;
                }

                // フルスクリーンをリクエスト
                // Safari は webkit のベンダープレフィックスが必要
                fullscreen_container.requestFullscreen = fullscreen_container.requestFullscreen || fullscreen_container.webkitRequestFullscreen;
                if (fullscreen_container.requestFullscreen) {
                    fullscreen_container.requestFullscreen();
                }

                // 画面の向きを横に固定 (Screen Orientation API がサポートされている場合)
                if (screen.orientation) {
                    screen.orientation.lock('landscape').catch(() => {});
                }
            }
            // フルスクリーンをキャンセル
            this.player.fullScreen.cancel = (type: string) => {

                // フルスクリーンを終了
                // Safari は webkit のベンダープレフィックスが必要
                document.exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen;
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }

                // 画面の向きの固定を解除
                if (screen.orientation) {
                    screen.orientation.unlock();
                }
            }

            // ***** 再生/停止/画質切り替え時のイベントハンドラー *****

            // 再生/停止されたとき
            // 通知バーからの制御など、画面から以外の外的要因で再生/停止が行われる事もある
            const on_play_or_pause = () => {

                // まだ設定パネルが表示されていたら非表示にする
                this.player.setting.hide();

                // コントロールを表示する
                this.controlDisplayTimer();
            }
            this.player.on('play', on_play_or_pause);
            this.player.on('pause', on_play_or_pause);

            // 画質の切り替えが開始されたときのイベント
            this.player.on('quality_start', () => {

                // ローディング中の背景画像をランダムで設定
                this.background_url = PlayerUtils.generatePlayerBackgroundURL();

                // イベントソースを閉じる
                if (this.eventsource !== null) {
                    this.eventsource.close();
                    this.eventsource = null;
                }

                // 新しい EventSource を作成
                // 画質ごとにイベント API は異なるため、一度破棄してから作り直す
                this.initEventHandler();
            });

            // 停止状態でかつ再生時間からバッファが 30 秒以上離れていないかを1分おきに監視し、そうなっていたら強制的にシークする
            // mpegts.js の仕様上、MSE に未再生のバッファがたまり過ぎると SourceBuffer が追加できなくなるため、強制的に接続が切断されてしまう
            this.interval_ids.push(window.setInterval(() => {
                if (this.player.video.paused && this.player.video.buffered.end(0) - this.player.video.currentTime > 30) {
                    this.player.sync();
                }
            }, 60 * 1000));

            // ***** 文字スーパーのイベントハンドラー *****

            // 設定で文字スーパーが有効
            // 字幕が非表示の場合でも、文字スーパーは表示する
            if (Utils.getSettingsItem('tv_show_superimpose') === true) {
                this.player.plugins.aribb24Superimpose.show();
                this.player.on('subtitle_hide', () => {
                    this.player.plugins.aribb24Superimpose.show();
                });
            // 設定で文字スーパーが無効
            } else {
                this.player.plugins.aribb24Superimpose.hide();
                this.player.on('subtitle_show', () => {
                    this.player.plugins.aribb24Superimpose.hide();
                });
            }
        },

        // イベントハンドラーを初期化する
        initEventHandler() {

            // ***** プレイヤー再生開始時のイベントハンドラー *****

            // 必ず最初はローディング状態とする
            this.is_loading = true;

            // 音量を 0 に設定
            this.player.video.volume = 0;

            // 再生バッファを調整し、再生準備ができた段階でプレイヤーの背景を非表示にするイベントを登録
            // 実際に再生可能になるのを待ってから実行する
            // 画質切り替え時にも実行する必要があるので、あえてこの位置に記述している
            const on_canplay = () => {

                // 自分自身のイベントを登録解除 (重複実行を避ける)
                this.player.video.oncanplay = null;
                this.player.video.oncanplaythrough = null;

                // 再生バッファ調整のため、一旦停止させる
                // this.player.video.pause() を使うとプレイヤーの UI アイコンが停止してしまうので、代わりに playbackRate を使う
                this.player.video.playbackRate = 0;

                // 念のためさらに少しだけ待ってから
                // あえて await で待たずに非同期コールバックで実行している
                window.setTimeout(async () => {

                    // 再生バッファを取得する (取得に失敗した場合は 0 を返す)
                    const get_playback_buffer_sec = (): number => {
                        try {
                            return (Math.round((this.player.video.buffered.end(0) - this.player.video.currentTime) * 1000) / 1000);
                        } catch (error) {
                            // まだ再生準備が整っていないなどの理由で、再生バッファの取得に失敗した場合
                            return 0;
                        }
                    }

                    // 低遅延モードであれば低遅延向けの再生バッファを、そうでなければ通常の再生バッファをセット (秒単位)
                    const playback_buffer_sec = Utils.getSettingsItem('tv_low_latency_mode') ?
                        PLAYBACK_BUFFER_SEC_LOW_LATENCY : PLAYBACK_BUFFER_SEC;

                    // 再生バッファが playback_buffer_sec を超えるまで 0.1 秒おきに再生バッファをチェックする
                    // 再生バッファが playback_buffer_sec を切ると再生が途切れやすくなるので (特に動きの激しい映像)、
                    // 再生開始までの時間を若干犠牲にして、再生バッファの調整と同期に時間を割く
                    // playback_buffer_sec の値は mpegts.js に渡す liveSyncTargetLatency プロパティに渡す値と共通
                    let current_playback_buffer_sec = get_playback_buffer_sec();
                    while (current_playback_buffer_sec < playback_buffer_sec) {
                        await Utils.sleep(0.1);
                        current_playback_buffer_sec = get_playback_buffer_sec();
                    }

                    // 再生開始
                    this.player.video.playbackRate = 1;

                    // 再生が一時的に止まってバッファリングしているとき/再び再生されはじめたときのイベント
                    // バッファリングの Progress Circular の表示を制御する
                    // 同期が終わってからの方が都合が良い
                    this.player.video.addEventListener('waiting', () => this.is_video_buffering = true);
                    this.player.video.addEventListener('playing', () => this.is_video_buffering = false);

                    // ローディング状態を解除し、映像を表示する
                    this.is_loading = false;

                    // バッファリング中の Progress Circular を非表示にする
                    this.is_video_buffering = false;

                    if (this.channel.is_radiochannel) {
                        // ラジオチャンネルでは引き続き映像の代わりとして背景画像を表示し続ける
                        this.is_background_display = true;
                    } else {
                        // 背景画像をフェードアウト
                        this.is_background_display = false;
                    }

                    // 再生開始時に音量を徐々に上げる
                    // いきなり再生されるよりも体験が良い
                    const current_volume: number = this.player.user.get('volume');
                    while ((this.player.video.volume + 0.05) < current_volume) {
                        // 小数第2位以下を切り捨てて、浮動小数の誤差で 1 (100%) を微妙に超えてしまいエラーになるのを避ける
                        this.player.video.volume = Utils.mathFloor(this.player.video.volume + 0.05, 2);
                        await Utils.sleep(0.02);
                    }
                    this.player.video.volume = current_volume;

                }, 100);
            }
            this.player.video.oncanplay = on_canplay;
            this.player.video.oncanplaythrough = on_canplay;

            // ***** KonomiTV サーバーのイベント API のイベントハンドラー *****

            // EventSource を作成
            this.eventsource = new EventSource((this.player.quality.url as string).replace('/mpegts', '/events'));

            // 初回接続時のイベント
            this.eventsource.addEventListener('initial_update', (event_raw: MessageEvent) => {

                // ステータスが Standby であれば
                const event = JSON.parse(event_raw.data);
                if (event.status === 'Standby') {

                    // バッファリング中の Progress Circular を表示
                    this.is_video_buffering = true;

                    // プレイヤーの背景を表示する
                    this.is_background_display = true;
                }
            });

            // ステータスが更新されたときのイベント
            this.eventsource.addEventListener('status_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data);
                console.log(`Status: ${event.status} / Detail: ${event.detail}`);

                // 視聴者数を更新
                this.channel.viewers = event.clients_count;

                // ステータスごとに処理を振り分け
                switch (event.status) {

                    // Status: Standby
                    case 'Standby': {

                        // ステータス詳細をプレイヤーに表示
                        if (!this.player.template.notice.textContent.includes('画質を')) {  // 画質切り替えの表示を上書きしない
                            this.player.notice(event.detail, -1);
                        }

                        // バッファリング中の Progress Circular を表示
                        this.is_video_buffering = true;

                        // プレイヤーの背景を表示する
                        this.is_background_display = true;
                        break;
                    }

                    // Status: ONAir
                    case 'ONAir': {

                        // ステータス詳細をプレイヤーから削除
                        if (!this.player.template.notice.textContent.includes('画質を')) {  // 画質切り替えの表示を上書きしない
                            this.player.notice(this.player.template.notice.textContent, 0.000001);
                        }

                        // 前のプレイヤーインスタンスの Picture-in-Picture ウインドウが残っている場合、終了させてからもう一度切り替える
                        // チャンネル切り替えが完了しても前の Picture-in-Picture ウインドウは再利用されないため、一旦終了させるしかない
                        if (document.pictureInPictureElement) {
                            document.exitPictureInPicture();
                            this.player.video.requestPictureInPicture();
                        }
                        break;
                    }

                    // Status: Restart
                    case 'Restart': {

                        // ステータス詳細をプレイヤーに表示
                        this.player.notice(event.detail, -1);

                        // プレイヤーを再起動する
                        this.player.switchVideo({
                            url: this.player.quality.url,
                            type: this.player.quality.type,
                        });

                        // 再起動しただけでは自動再生されないので、明示的に
                        this.player.play();

                        // バッファリング中の Progress Circular を表示
                        this.is_video_buffering = true;

                        // プレイヤーの背景を表示する
                        this.is_background_display = true;
                        break;
                    }

                    // Status: Offline
                    case 'Offline': {

                        // 基本的に Offline は放送休止中やエラーなどで復帰の見込みがない状態

                        // ステータス詳細をプレイヤーに表示
                        // 動画の読み込みエラーが送出された時にメッセージを上書きする
                        this.player.notice(event.detail, -1);
                        this.player.video.onerror = () => {
                            this.player.notice(event.detail, -1);
                            this.player.video.onerror = null;
                        }

                        // 描画されたコメントをクリア
                        this.player.danmaku.clear()

                        // 動画を停止する
                        this.player.video.pause();

                        // イベントソースを閉じる（復帰の見込みがないため）
                        this.eventsource.close();

                        // プレイヤーの背景を表示する
                        this.is_background_display = true;

                        // バッファリング中の Progress Circular を非表示にする
                        this.is_loading = false;
                        this.is_video_buffering = false;
                        break;
                    }
                }
            });

            // ステータス詳細が更新されたときのイベント
            this.eventsource.addEventListener('detail_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data);
                console.log(`Status: ${event.status} Detail:${event.detail}`);

                // 視聴者数を更新
                this.channel.viewers = event.clients_count;

                // Standby のときだけプレイヤーに表示
                if (event.status === 'Standby') {
                    this.player.notice(event.detail, -1);

                    // プレイヤーの背景を表示する
                    if (!this.is_background_display) {
                        this.is_background_display = true;
                    }
                }
            });

            // クライアント数（だけ）が更新されたときのイベント
            this.eventsource.addEventListener('clients_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data);

                // 視聴者数を更新
                this.channel.viewers = event.clients_count;
            });
        },

        // ショートカットキーを初期化する
        initShortcutKeyHandler() {

            const twitter_component = (this.$refs.Twitter as InstanceType<typeof Twitter>);
            const tweet_form_element = twitter_component.$el.querySelector<HTMLDivElement>('.tweet-form__textarea');

            // IME 変換中の状態を保存する
            for (const element of document.querySelectorAll('input[type=text],input[type=search],textarea')) {
                element.addEventListener('compositionstart', () => this.is_ime_composing = true);
                element.addEventListener('compositionend', () => this.is_ime_composing = false);
            }

            // ショートカットキーハンドラー
            this.shortcut_key_handler = async (event: KeyboardEvent) => {

                const tag = document.activeElement.tagName.toUpperCase();
                const editable = document.activeElement.getAttribute('contenteditable');

                // 矢印キーのデフォルトの挙動（スクロール）を抑制
                // キーリピート周りで間引かれるイベントでも event.preventDefault() しないとスクロールしてしまうため、
                // 一番最初のタイミングでやっておく
                // input・textarea・contenteditable 状態の要素では実行しない
                if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.code) &&
                    (tag !== 'INPUT' && tag !== 'TEXTAREA' && editable !== '' && editable !== 'true')) {
                    event.preventDefault();
                }

                // キーリピート（押しっぱなし）状態の場合は基本実行しない
                // 押し続けると何度も同じ動作が実行されて大変な事になる…
                // ただ、キーリピートを使いたい場合もあるので、リピート状態をフラグとして保存する
                let is_repeat = false;
                if (event.repeat) is_repeat = true;

                // キーリピート状態は event.repeat を見る事でだいたい検知できるが、最初の何回かは検知できないこともある
                // そこで、0.05 秒以内に連続して発火したキーイベントは間引きも兼ねて実行しない
                const now = Date.now();
                if (now - this.shortcut_key_pressed_at < (0.05 * 1000)) return;
                this.shortcut_key_pressed_at = now;  // 最終押下時刻を更新

                // 無名関数の中で実行する
                const result = await (async (): Promise<boolean> => {

                    // ***** ツイート入力フォームにフォーカスを当てる/フォーカスを外す *****

                    // ツイート入力フォームにフォーカスしているときもこのショートカットが動くようにする
                    // 以降の if 文で textarea フォーカス時のイベントをすべて弾いてしまっているため、前に持ってきている
                    // Tab キーに割り当てている関係で、IME 変換中は実行しない（IME 変換中に実行すると文字変換ができなくなる）
                    if (((tag !== 'INPUT' && tag !== 'TEXTAREA' && editable !== '' && editable !== 'true') ||
                        (document.activeElement === tweet_form_element)) && this.is_ime_composing === false) {
                        if (event.code === 'Tab') {

                            // ツイート入力フォームにフォーカスがすでに当たっていたら、フォーカスを外して終了
                            if (document.activeElement === tweet_form_element) {
                                tweet_form_element.blur();
                                return true;
                            }

                            // パネルを開く
                            this.is_panel_display = true;

                            // どのタブを開いていたかに関係なく Twitter タブに切り替える
                            this.tv_panel_active_tab = 'Twitter';

                            // ツイート入力フォームの textarea 要素にフォーカスを当てる
                            tweet_form_element.focus();

                            // フォーカスを当てると勝手に横方向にスクロールされてしまうので、元に戻す
                            this.$el.scrollLeft = 0;

                            window.setTimeout(() => {

                                // 他のタブから切り替えると一発でフォーカスが当たらないことがあるので、ちょっとだけ待ってから念押し
                                // $nextTick() だと上手くいかなかった…
                                tweet_form_element.focus();

                                // フォーカスを当てると勝手に横方向にスクロールされてしまうので、元に戻す
                                this.$el.scrollLeft = 0;

                            }, 100);  // 0.1秒

                            return true;
                        }
                    }

                    // ***** ツイートを送信する *****

                    // ツイート入力フォームにフォーカスしているときもこのショートカットが動くようにする
                    // Twitter タブ以外を開いているときは実行しない
                    // 以降の if 文で textarea フォーカス時のイベントをすべて弾いてしまっているため、前に持ってきている
                    if (((tag !== 'INPUT' && tag !== 'TEXTAREA' && editable !== '' && editable !== 'true') ||
                        (document.activeElement === tweet_form_element)) &&
                        this.tv_panel_active_tab === 'Twitter' &&
                        this.is_ime_composing === false) {
                        // (Ctrl or Cmd or Shift) + Enter
                        // Shift + Enter は隠し機能（間違えたとき用）
                        if ((event.ctrlKey || event.metaKey || event.shiftKey) && event.code === 'Enter') {
                            twitter_component.$el.querySelector<HTMLDivElement>('.tweet-button').click();
                            return true;
                        }
                    }

                    // ***** コメント入力フォームを閉じる *****

                    // プレイヤーが初期化されていない時・Shift / Alt キーが一緒に押された時に作動しないように
                    if (this.player !== null && !event.shiftKey && !event.altKey) {

                        // コメント入力フォームが表示されているときのみ
                        if (this.player.template.controller.classList.contains('dplayer-controller-comment')) {
                            // Ctrl or Cmd + M
                            if ((event.ctrlKey || event.metaKey) && event.code === 'KeyM') {
                                this.player.comment.hide();
                                return true;
                            }
                        }
                    }

                    // input・textarea・contenteditable 状態の要素でなければ
                    // 文字入力中にショートカットキーが作動してしまわないように
                    if (tag !== 'INPUT' && tag !== 'TEXTAREA' && editable !== '' && editable !== 'true') {

                        // キーリピートでない時・Ctrl / Cmd / Alt キーが一緒に押された時に作動しないように
                        if (is_repeat === false && !event.ctrlKey && !event.metaKey && !event.altKey) {

                            // ***** 数字キーでチャンネルを切り替える *****

                            // Ctrl / Cmd キーが同時押しされていたら BS チャンネルの方を選局する
                            const switch_channel_type = (event.shiftKey) ? 'BS' : 'GR';

                            // 1～9キー
                            let switch_remocon_id = null;
                            if (event.code === 'Digit1' || event.code === 'Digit2' || event.code === 'Digit3' ||
                                event.code === 'Digit4' || event.code === 'Digit5' || event.code === 'Digit6' ||
                                event.code === 'Digit7' || event.code === 'Digit8' || event.code === 'Digit9') {
                                switch_remocon_id = Number(event.code.replace('Digit', ''));
                            }
                            // 0キー: 10に割り当て
                            if (event.code === 'Digit0') switch_remocon_id = 10;
                            // -キー: 11に割り当て
                            if (event.code === 'Minus') switch_remocon_id = 11;
                            // ^キー: 12に割り当て
                            if (event.code === 'Equal') switch_remocon_id = 12;
                            // 1～9キー (テンキー)
                            if (event.code === 'Numpad1' || event.code === 'Numpad2' || event.code === 'Numpad3' ||
                                event.code === 'Numpad4' || event.code === 'Numpad5' || event.code === 'Numpad6' ||
                                event.code === 'Numpad7' || event.code === 'Numpad8' || event.code === 'Numpad9') {
                                switch_remocon_id = Number(event.code.replace('Numpad', ''));
                            }
                            // 0キー (テンキー): 10に割り当て
                            if (event.code === 'Numpad0') switch_remocon_id = 10;

                            // この時点でリモコン番号が取得できていたら実行
                            if (switch_remocon_id !== null) {

                                // 切り替え先のチャンネルを取得する
                                const switch_channel = ChannelUtils.getChannelFromRemoconID(
                                    this.channels_list, switch_channel_type, switch_remocon_id);

                                // チャンネルが取得できていれば、ルーティングをそのチャンネルに置き換える
                                // 押されたキーに対応するリモコン番号のチャンネルがない場合や、現在と同じチャンネル ID の場合は何も起こらない
                                if (switch_channel !== null && switch_channel.channel_id !== this.channel_id) {
                                    await this.$router.push({path: `/tv/watch/${switch_channel.channel_id}`});
                                    return true;
                                }
                            }
                        }

                        // キーリピートでない時・Ctrl / Cmd / Shift / Alt キーが一緒に押された時に作動しないように
                        if (is_repeat === false && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {

                            // ***** キーボードショートカットの一覧を表示する *****

                            // /(?)キー: キーボードショートカットの一覧を表示する
                            if (event.code === 'Slash') {
                                this.shortcut_key_modal = !this.shortcut_key_modal;
                                return true;
                            }

                            // ***** パネルのタブを切り替える *****

                            // Pキー: パネルの表示切り替え
                            if (event.code === 'KeyP') {
                                this.is_panel_display = !this.is_panel_display;
                                return true;
                            }
                            // Kキー: 番組情報タブ
                            if (event.code === 'KeyK') {
                                this.tv_panel_active_tab = 'Program';
                                return true;
                            }
                            // Lキー: チャンネルタブ
                            if (event.code === 'KeyL') {
                                this.tv_panel_active_tab = 'Channel';
                                return true;
                            }
                            // ;(+)キー: コメントタブ
                            if (event.code === 'Semicolon') {
                                this.tv_panel_active_tab = 'Comment';
                                return true;
                            }
                            // :(*)キー: Twitterタブ
                            if (event.code === 'Quote') {
                                this.tv_panel_active_tab = 'Twitter';
                                return true;
                            }

                            // ***** Twitter タブ内のタブを切り替える *****

                            // [(「): ツイート検索タブ
                            if (event.code === 'BracketRight') {
                                twitter_component.twitter_active_tab = 'Search';
                                return true;
                            }
                            // ](」): タイムラインタブ
                            if (event.code === 'Backslash') {
                                twitter_component.twitter_active_tab = 'Timeline';
                                return true;
                            }
                            // \(￥)キー: キャプチャタブ
                            if (event.code === 'IntlRo') {
                                twitter_component.twitter_active_tab = 'Capture';
                                return true;
                            }
                        }

                        // Twitter タブ内のキャプチャタブが表示されている & Ctrl / Cmd / Shift / Alt のいずれも押されていないときだけ
                        // キャプチャタブが表示されている時は、プレイヤー操作側の矢印キー/スペースキーのショートカットは動作しない（キーが重複するため）
                        if (this.tv_panel_active_tab === 'Twitter' && twitter_component.twitter_active_tab === 'Capture' &&
                            (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey)) {

                            // ***** キャプチャにフォーカスする *****

                            if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.code)) {

                                // キャプチャリストに一枚もキャプチャがない
                                if (twitter_component.captures.length === 0) return false;

                                // まだどのキャプチャにもフォーカスされていない場合は、一番新しいキャプチャにフォーカスして終了
                                if (twitter_component.captures.some(capture => capture.focused === true) === false) {
                                    twitter_component.captures[twitter_component.captures.length - 1].focused = true;
                                    return true;
                                }

                                // 現在フォーカスされているキャプチャのインデックスを取得
                                const focused_capture_index = twitter_component.captures.findIndex(capture => capture.focused === true);

                                // ↑キー: 2つ前のキャプチャにフォーカスする
                                // キャプチャリストは2列で並んでいるので、2つ後のキャプチャが現在フォーカスされているキャプチャの直上になる
                                if (event.code === 'ArrowUp') {
                                    // 2つ前のキャプチャがないなら実行しない
                                    if (focused_capture_index - 2 < 0) return false;
                                    twitter_component.captures[focused_capture_index - 2].focused = true;
                                }

                                // ↓キー: 2つ後のキャプチャにフォーカスする
                                // キャプチャリストは2列で並んでいるので、2つ後のキャプチャが現在フォーカスされているキャプチャの直下になる
                                if (event.code === 'ArrowDown') {
                                    // 2つ後のキャプチャがないなら実行しない
                                    if (focused_capture_index + 2 > (twitter_component.captures.length - 1)) return false;
                                    twitter_component.captures[focused_capture_index + 2].focused = true;
                                }

                                // ←キー: 1つ前のキャプチャにフォーカスする
                                if (event.code === 'ArrowLeft') {
                                    // 1つ前のキャプチャがないなら実行しない
                                    if (focused_capture_index - 1 < 0) return false;
                                    twitter_component.captures[focused_capture_index - 1].focused = true;
                                }

                                // ←キー: 1つ後のキャプチャにフォーカスする
                                if (event.code === 'ArrowRight') {
                                    // 1つ後のキャプチャがないなら実行しない
                                    if (focused_capture_index + 1 > (twitter_component.captures.length - 1)) return false;
                                    twitter_component.captures[focused_capture_index + 1].focused = true;
                                }

                                // 現在フォーカスされているキャプチャのフォーカスを外す
                                twitter_component.captures[focused_capture_index].focused = false;

                                // 拡大表示のモーダルが開かれている場合は、フォーカスしたキャプチャをモーダルにセット
                                // こうすることで、QuickLook みたいな挙動になる
                                const focused_capture = twitter_component.captures.find(capture => capture.focused === true);
                                if (twitter_component.zoom_capture_modal === true) {
                                    twitter_component.zoom_capture = focused_capture;
                                }

                                // 現在フォーカスされているキャプチャが見える位置までスクロール
                                // block: 'nearest' の指定で、上下どちらにスクロールしてもフォーカスされているキャプチャが常に表示されるようになる
                                const focused_capture_element =
                                    twitter_component.$el.querySelector(`img[src="${focused_capture.image_url}"]`).parentElement;
                                if (is_repeat) {
                                    // キーリピート状態ではスムーズスクロールがフォーカスの移動に追いつけずスクロールの挙動がおかしくなるため、
                                    // スムーズスクロールは無効にしてある
                                    focused_capture_element.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'auto'});
                                } else {
                                    focused_capture_element.scrollIntoView({block: 'nearest', inline: 'nearest', behavior: 'smooth'});
                                }
                                return true;
                            }

                            // ***** キャプチャを拡大表示する/拡大表示を閉じる *****

                            if (event.code === 'Enter') {

                                // Enter キーの押下がプレイヤー側のコメント送信由来のイベントの場合は実行しない
                                if (this.is_comment_send_just_did) return false;

                                // すでにモーダルが開かれている場合は、どのキャプチャが拡大表示されているかに関わらず閉じる
                                if (twitter_component.zoom_capture_modal === true) {
                                    twitter_component.zoom_capture_modal = false;
                                    return true;
                                }

                                // 現在フォーカスされているキャプチャを取得
                                // まだどのキャプチャにもフォーカスされていない場合は実行しない
                                const focused_capture = twitter_component.captures.find(capture => capture.focused === true);
                                if (focused_capture === undefined) return false;

                                // モーダルを開き、モーダルで拡大表示するキャプチャとしてセット
                                twitter_component.zoom_capture = focused_capture;
                                twitter_component.zoom_capture_modal = true;
                                return true;
                            }

                            // ***** キャプチャを選択する/選択を解除する *****

                            if (event.code === 'Space') {

                                // 現在フォーカスされているキャプチャを取得
                                // まだどのキャプチャにもフォーカスされていない場合は実行しない
                                const focused_capture = twitter_component.captures.find(capture => capture.focused === true);
                                if (focused_capture === undefined) return false;

                                // 「キャプチャリスト内のキャプチャがクリックされたときのイベント」を呼ぶ
                                // 選択されていなければ選択され、選択されていれば選択が解除される
                                // キャプチャの枚数制限などはすべて clickCapture() の中で処理される
                                twitter_component.clickCapture(focused_capture);
                                return true;
                            }
                        }

                        // ***** 上下キーでチャンネルを切り替える *****

                        // キーリピートでない時・Ctrl / Cmd / Shift / Alt キーが一緒に押された時に作動しないように
                        if (is_repeat === false && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {

                            // ↑キー: 前のチャンネルに切り替え
                            if (event.code === 'ArrowUp') {
                                await this.$router.push({path: `/tv/watch/${this.channel_previous.channel_id}`});
                                return true;
                            }
                            // ↓キー: 次のチャンネルに切り替え
                            if (event.code === 'ArrowDown') {
                                await this.$router.push({path: `/tv/watch/${this.channel_next.channel_id}`});
                                return true;
                            }
                        }

                        // ***** プレイヤーのショートカットキー *****

                        // プレイヤーが初期化されていない時・Shift / Alt キーが一緒に押された時に作動しないように
                        if (this.player !== null && !event.shiftKey && !event.altKey) {

                            // Ctrl / Cmd + ↑キー: プレイヤーの音量を上げる
                            if ((event.ctrlKey || event.metaKey) && event.code === 'ArrowUp') {
                                this.player.volume(this.player.volume() + 0.05);
                                return true;
                            }
                            // Ctrl / Cmd + ↓キー: プレイヤーの音量を下げる
                            if ((event.ctrlKey || event.metaKey) && event.code === 'ArrowDown') {
                                this.player.volume(this.player.volume() - 0.05);
                                return true;
                            }
                            // Ctrl / Cmd + ←キー: 停止して0.5秒巻き戻し
                            if ((event.ctrlKey || event.metaKey) && event.code === 'ArrowLeft') {
                                if (this.player.video.paused === false) this.player.video.pause();
                                this.player.video.currentTime = this.player.video.currentTime - 0.5;
                                return true;
                            }
                            // Ctrl / Cmd + →キー: 停止して0.5秒早送り
                            if ((event.ctrlKey || event.metaKey) && event.code === 'ArrowRight') {
                                if (this.player.video.paused === false) this.player.video.pause();
                                this.player.video.currentTime = this.player.video.currentTime + 0.5;
                                return true;
                            }
                        }

                        // プレイヤーが初期化されていない時・Ctrl / Cmd / Alt キーが一緒に押された時に作動しないように
                        if (this.player !== null && !event.ctrlKey && !event.metaKey && !event.altKey) {

                            // Shift + Spaceキー + キーリピートでない時 + Twitter タブ表示時 + キャプチャタブ表示時: 再生/停止
                            if (event.shiftKey === true && event.code === 'Space' && is_repeat === false &&
                                this.tv_panel_active_tab === 'Twitter' && twitter_component.twitter_active_tab === 'Capture') {
                                this.player.toggle();
                                return true;
                            }
                        }

                        // プレイヤーが初期化されていない時・キーリピートでない時・Ctrl / Cmd / Shift / Alt キーが一緒に押された時に作動しないように
                        if (this.player !== null && is_repeat === false && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {

                            // Spaceキー: 再生/停止
                            if (event.code === 'Space') {
                                this.player.toggle();
                                return true;
                            }
                            // Fキー: フルスクリーンの切り替え
                            if (event.code === 'KeyF') {
                                this.player.fullScreen.toggle();
                                return true;
                            }
                            // Wキー: ライブストリームの同期
                            if (event.code === 'KeyW') {
                                this.player.sync();
                                return true;
                            }
                            // Eキー: Picture-in-Picture の表示切り替え
                            if (event.code === 'KeyE') {
                                if (document.pictureInPictureEnabled) {
                                    this.player.template.pipButton.click();
                                }
                                return true;
                            }
                            // Sキー: 字幕の表示切り替え
                            if (event.code === 'KeyS') {
                                this.player.subtitle.toggle();
                                if (!this.player.subtitle.container.classList.contains('dplayer-subtitle-hide')) {
                                    this.player.notice(`${this.player.tran('Show subtitle')}`);
                                } else {
                                    this.player.notice(`${this.player.tran('Hide subtitle')}`);
                                }
                                return true;
                            }
                            // Dキー: コメントの表示切り替え
                            if (event.code === 'KeyD') {
                                this.player.template.showDanmaku.click();
                                if (this.player.template.showDanmakuToggle.checked) {
                                    this.player.notice(`${this.player.tran('Show comment')}`);
                                } else {
                                    this.player.notice(`${this.player.tran('Hide comment')}`);
                                }
                                return true;
                            }
                            // Cキー: 映像をキャプチャ
                            if (event.code === 'KeyC') {
                                await this.capture_handler.captureAndSave(this.channel, false);
                                return true;
                            }
                            // Vキー: 映像を実況コメントを付けてキャプチャ
                            if (event.code === 'KeyV') {
                                await this.capture_handler.captureAndSave(this.channel, true);
                                return true;
                            }
                            // Mキー: コメント入力フォームにフォーカス
                            if (event.code === 'KeyM') {
                                this.player.controller.show();
                                this.player.comment.show();
                                this.controlDisplayTimer();
                                window.setTimeout(() => this.player.template.commentInput.focus(), 100);
                                return true;
                            }
                        }
                    }
                    return false;
                })();

                // 無名関数を実行した後の戻り値が true ならショートカットキーの操作を実行したことになるので、デフォルトのキー操作を封じる
                if (result === true) {
                    event.preventDefault();
                }
            };

            // ページ上でキーが押されたときのイベントを登録
            document.addEventListener('keydown', this.shortcut_key_handler);
        },

        // キャプチャ関連のイベントを初期化する
        initCaptureHandler() {

            // キャプチャハンドラーを初期化
            this.capture_handler = new PlayerCaptureHandler(this.player, (blob: Blob, filename: string) => {
                (this.$refs.Twitter as InstanceType<typeof Twitter>).addCaptureList(blob, filename);
            });

            // キャプチャボタンがクリックされたときのイベント
            // ショートカットからのキャプチャでも同じイベントがトリガーされる
            const capture_button = this.$el.querySelector('.dplayer-icon.dplayer-capture-icon');
            capture_button.addEventListener('click', async () => {
                await this.capture_handler.captureAndSave(this.channel, false);
            });

            // コメント付きキャプチャボタンがクリックされたときのイベント
            // ショートカットからのキャプチャでも同じイベントがトリガーされる
            const comment_capture_button = this.$el.querySelector('.dplayer-icon.dplayer-comment-capture-icon');
            comment_capture_button.addEventListener('click', async () => {
                await this.capture_handler.captureAndSave(this.channel, true);
            });
        },


        // 再生セッションを破棄する
        // チャンネルを切り替える際に実行される
        destroy(is_destroy_player = false) {

            // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
            // clearInterval() と clearTimeout() は中身共通なので問題ない
            for (const interval_id of this.interval_ids) {
                window.clearInterval(interval_id);
            }

            // コントロール表示制御用タイマーを止める
            window.clearTimeout(this.control_interval_id);

            // interval_ids をクリア
            this.interval_ids = [];

            // 再びローディング状態にする
            this.is_loading = true;

            // プレイヤーの背景を隠す
            this.is_background_display = false;

            // プレイヤーに破棄が可能なフラグをつける
            this.player.KonomiTVCanDestroy = true;

            // イベントソースを閉じる
            if (this.eventsource !== null) {
                this.eventsource.close();
                this.eventsource = null;
            }

            // アニメーション分待ってから実行
            this.interval_ids.push(window.setTimeout(() => {

                // プレイヤーを停止する
                this.player.video.pause();

                // is_destroy_player が true の時は、ここで DPlayer 自体を破棄する
                // false の時は次の initPlayer() が実行されるまで破棄されない
                if (is_destroy_player === true && this.player !== null) {
                    try {
                        this.player.destroy();
                    } catch (error) {
                        // mpegts.js をうまく破棄できない場合
                        if (this.player.plugins.mpegts !== undefined) {
                            this.player.plugins.mpegts.destroy();
                        }
                    }
                    this.player = null;
                }

            }, 0.4 * 1000));  // 0.4 秒
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
            transition: opacity 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94);
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
        background: linear-gradient(to bottom, transparent, var(--v-background-base)) !important;
        opacity: 0 !important;
        visibility: hidden;
        @include smartphone-horizontal {
            height: 66px !important;
        }
    }
    .dplayer-controller {
        padding-left: calc(68px + 18px) !important;
        padding-bottom: 6px !important;
        transition: opacity 0.3s ease, visibility 0.3s ease;
        opacity: 0 !important;
        visibility: hidden;

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
                @include smartphone-horizontal {
                    right: 11px !important;
                }
            }
            // ブラウザフルスクリーンボタンを削除（実質あまり意味がないため）
            .dplayer-icon.dplayer-full-in-icon {
                display: none !important;
            }
            .dplayer-icon {
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
        }
    }
    .dplayer-notice {
        padding: 16px 22px !important;
        margin-right: 30px;
        border-radius: 4px !important;
        font-size: 15px !important;
        line-height: 1.6;
        @include smartphone-horizontal {
            padding: 12px 16px !important;
            margin-right: 16px;
            font-size: 13.5px !important;
        }
    }
    .dplayer-info-panel {
        transition: top 0.3s, left 0.3s;
    }
    .dplayer-setting-box {
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
        .dplayer-comment-setting-type {
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
            @include smartphone-horizontal {
                padding-left: calc(56px + 18px) !important;
            }
        }
        &.dplayer-hide-controller .dplayer-controller {
            transform: none !important;
        }
    }
}

// ロード中は動画を非表示にする
.watch-player--loading .dplayer-video-wrap-aspect {
    opacity: 0 !important;
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
                @include smartphone-horizontal {
                    left: calc(68px + 16px);
                }
                @include smartphone-horizontal {
                    left: calc(56px + 16px);
                }
            }
        }
        .dplayer-notice {
            left: calc(68px + 30px);
            bottom: 62px;
            @include smartphone-horizontal {
                left: calc(68px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(56px + 16px);
            }
        }
        .dplayer-info-panel {
            top: 82px;
            left: calc(68px + 30px);
            @include smartphone-horizontal {
                left: calc(68px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(56px + 16px);
            }
        }
        .dplayer-comment-setting-box {
            left: calc(68px + 20px);
            @include smartphone-horizontal {
                left: calc(68px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(56px + 16px);
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
    .watch-player__dplayer .dplayer-danmaku {
        max-height: 100% !important;
        aspect-ratio: 16 / 9 !important;
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
            @include smartphone-horizontal {
                padding-left: 16px !important;
            }
        }
        .dplayer-comment-box, .dplayer-comment-setting-box {
            left: 20px !important;
            @include smartphone-horizontal {
                left: 16px !important;
            }
            @include smartphone-horizontal {
                left: 16px !important;
            }
        }
    }
}
// フルスクリーン+コントロール表示時
.watch-container.watch-container--fullscreen.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-notice, .dplayer-info-panel {
            left: 30px !important;
            @include smartphone-horizontal {
                left: 16px !important;
            }
            @include smartphone-horizontal {
                left: 16px !important;
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
    background: var(--v-black-base) !important;
    overflow: hidden;
    // iOS Safari で 100vh にアドレスバーが含まれてしまう問題を回避する
    @supports (-webkit-touch-callout: none) {
        height: -webkit-fill-available !important;
    }
}
.watch-container {
    display: flex;
    width: calc(100% + 352px);  // パネルの幅分はみ出す
    height: 100%;
    transition: width 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);
    @include smartphone-horizontal {
        width: calc(100% + 310px); // パネルの幅分はみ出す
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
        width: calc(100%);  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: var(--v-primary-base);
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
                @include smartphone-horizontal {
                    padding-left: 16px;
                }
                @include smartphone-horizontal {
                    padding-left: 16px;
                }
            }
        }
    }

    .watch-navigation {
        display: flex;
        flex-direction: column;
        position: fixed;
        width: 68px;
        top: 0px;
        left: 0px;
        // スマホ・タブレットのブラウザでアドレスバーが完全に引っ込むまでビューポートの高さが更新されず、
        // その間下に何も背景がない部分ができてしまうのを防ぐ
        bottom: -100px;
        padding: 18px 8px 122px;
        background: #2F221F80;
        transition: opacity 0.3s, visibility 0.3s;
        opacity: 0;
        visibility: hidden;
        z-index: 2;
        @include smartphone-horizontal {
            width: 56px;
            padding: 18px 6px 122px;
        }

        .watch-navigation__icon {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 52px;
            margin-bottom: 17px;
            border-radius: 11px;
            font-size: 16px;
            color: var(--v-text-base);
            transition: background-color 0.15s;
            text-decoration: none;
            user-select: none;
            @include smartphone-horizontal {
                height: 32px;
                border-radius: 10px;
            }
        }

        @include smartphone-horizontal {
            // スペースを確保するため、スペーサーを非表示に
            div.spacer {
                display: none;
            }
        }

        .watch-navigation__link {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 52px;
            border-radius: 11px;
            font-size: 16px;
            color: var(--v-text-base);
            transition: background-color 0.15s;
            text-decoration: none;
            user-select: none;
            @include smartphone-horizontal {
                height: 44px;
                border-radius: 10px;
                // スペースを確保するため、設定・バージョン情報のアイコンを非表示に
                &:nth-last-child(1), &:nth-last-child(2) {
                    display: none;
                }
            }

            &:hover {
                background: #433532A0;
            }

            @include smartphone-horizontal {
                &-icon {
                    width: 26px;
                    height: 26px;
                }
            }

            &--active {
                color: var(--v-primary-base);
                background: #433532A0;
            }
            + .watch-navigation__link {
                margin-top: 4px;
                @include smartphone-horizontal {
                    margin-top: auto;
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
            background: linear-gradient(to bottom, var(--v-background-base), transparent);
            transition: opacity 0.3s, visibility 0.3s;
            opacity: 0;
            visibility: hidden;
            z-index: 1;

            @include smartphone-horizontal {
                padding-left: calc(68px + 16px);
                padding-right: 16px;
            }
            @include smartphone-horizontal {
                height: 66px;
                padding-left: calc(56px + 16px);
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

                @include smartphone-horizontal {
                    width: 48px;
                    height: 28px;
                    border-radius: 4px;
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

                @include smartphone-horizontal {
                    margin-left: 12px;
                }
                @include smartphone-horizontal {
                    font-size: 16px;
                }
            }

            .watch-header__program-time {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 15px;

                @include smartphone-horizontal {
                    margin-left: 8px;
                }
                @include smartphone-horizontal {
                    font-size: 14px;
                }
            }

            .watch-header__now {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 13px;

                @include smartphone-horizontal {
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

            .watch-player__background {
                position: absolute;
                top: 50%;
                left: 50%;
                width: 100%;
                max-height: 100%;
                padding-top: min(56.25%, 100vh);
                aspect-ratio: 16 / 9;
                background-blend-mode: overlay;
                background-color: rgba(14, 14, 18, 0.35);
                background-size: cover;
                background-image: none;
                transform: translate(-50%, -50%);
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

                    @include tablet-horizontal {
                        height: 30px;
                        right: 34px;
                        bottom: 30px;
                    }

                    @include smartphone-horizontal {
                        height: 25px;
                        right: 30px;
                        bottom: 24px;
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
                @include smartphone-horizontal {
                    right: 15px;
                    height: 155px;
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
                    }

                    .switch-button-icon {
                        position: relative;
                    }

                    &-up > .switch-button-icon {
                        top: 6px;
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

    .watch-panel {
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        width: 352px;
        height: 100%;
        background: var(--v-background-base);
        @include smartphone-horizontal {
            width: 310px;
        }

        .watch-panel__header {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            width: 100%;
            height: 70px;
            padding-left: 16px;
            padding-right: 16px;
            @include smartphone-horizontal {
                display: none;
            }

            .panel-close-button {
                display: flex;
                position: relative;
                align-items: center;
                flex-shrink: 0;
                left: -4px;
                height: 35px;
                padding: 0 4px;
                border-radius: 5px;
                font-size: 16px;
                user-select: none;
                cursor: pointer;
                @include smartphone-horizontal {
                    font-size: 14px;
                }

                &__icon {
                    position: relative;
                    left: -4px;
                    @include smartphone-horizontal {
                        height: 22px;
                    }
                }
                &__text {
                    font-weight: bold;
                }
            }

            .panel-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;
                margin-left: 16px;

                &__icon {
                    display: inline-block;
                    flex-shrink: 0;
                    width: 43px;
                    height: 24px;
                    border-radius: 3px;
                    background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                    object-fit: cover;
                    user-select: none;
                    @include smartphone-horizontal {
                        width: 38px;
                        height: 22px;
                    }
                }

                &__number {
                    flex-shrink: 0;
                    margin-left: 8px;
                    font-size: 16px;
                    @include smartphone-horizontal {
                        font-size: 14px;
                    }
                }

                &__name {
                    margin-left: 5px;
                    font-size: 16px;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include smartphone-horizontal {
                        font-size: 14px;
                    }
                }
            }
        }

        .watch-panel__content-container {
            position: relative;
            height: 100%;

            .watch-panel__content {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: var(--v-background-base);
                transition: opacity 0.3s, visibility 0.3s;
                opacity: 0;
                visibility: hidden;

                &--active {
                    opacity: 1;
                    visibility: visible;
                }
            }
        }

        .watch-panel__navigation {
            display: flex;
            align-items: center;
            justify-content: space-evenly;
            flex-shrink: 0;
            height: 77px;
            background: var(--v-background-lighten1);
            @include smartphone-horizontal {
                height: 56px;
            }

            .panel-navigation-button {
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                width: 77px;
                height: 56px;
                padding: 6px 0px;
                border-radius: 5px;
                color: var(--v-text-base);
                box-sizing: content-box;
                transition: color 0.3s;
                user-select: none;
                cursor: pointer;
                @include smartphone-horizontal {
                    height: 42px;
                    padding: 6px 0px 4px;
                }

                &--active {
                    color: var(--v-primary-base);
                }

                &__icon {
                    height: 30px;
                }
                &__text {
                    margin-top: 5px;
                    font-size: 13px;
                    @include smartphone-horizontal {
                        margin-top: 2px;
                        font-size: 12px;
                    }
                }
            }
        }
    }
}

</style>