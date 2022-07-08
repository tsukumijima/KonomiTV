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
                    <span class="watch-header__program-title" v-html="TVUtils.decorateProgramInfo(channel.program_present, 'title')"></span>
                    <span class="watch-header__program-time">{{TVUtils.getProgramTime(channel.program_present, true)}}</span>
                    <v-spacer></v-spacer>
                    <span class="watch-header__now">{{time}}</span>
                </header>
                <div class="watch-player" :class="{'watch-player--loading': is_loading}">
                    <div class="watch-player__background" :class="{'watch-player__background--display': is_background_display}"
                        :style="{backgroundImage: `url(${background_url})`}">
                        <img class="watch-player__background-logo" src="/assets/images/logo.svg">
                    </div>
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
                        :class="{'watch-panel__content--active': panel_active_tab === 'Program'}" :channel="channel" />
                    <Channel class="watch-panel__content"
                        :class="{'watch-panel__content--active': panel_active_tab === 'Channel'}" :channels_list="channels_list" />
                    <Comment class="watch-panel__content" ref="Comment"
                        :class="{'watch-panel__content--active': panel_active_tab === 'Comment'}" :channel="channel" :player="player" />
                </div>
                <div class="watch-panel__navigation">
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': panel_active_tab === 'Program'}"
                         @click="panel_active_tab = 'Program'">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                        <span class="panel-navigation-button__text">番組情報</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': panel_active_tab === 'Channel'}"
                         @click="panel_active_tab = 'Channel'">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                        <span class="panel-navigation-button__text">チャンネル</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': panel_active_tab === 'Comment'}"
                         @click="panel_active_tab = 'Comment'">
                        <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="29px" />
                        <span class="panel-navigation-button__text">コメント</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                         :class="{'panel-navigation-button--active': panel_active_tab === 'Twitter'}"
                         @click="panel_active_tab = 'Twitter'">
                        <Icon class="panel-navigation-button__icon" icon="fa-brands:twitter" width="34px" />
                        <span class="panel-navigation-button__text">Twitter</span>
                    </div>
                </div>
            </div>
        </main>
        <v-dialog max-width="980" transition="slide-y-transition" v-model="shortcut_key_modal">
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
                                                <Icon class="shortcut-key" v-if="key.icon === true" :icon="key.name" height="18px" />
                                                <span class="shortcut-key" v-if="key.icon === false">{{key.name}}</span>
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

import { IChannel, IChannelDefault } from '@/interface';
import Channel from '@/components/TV/Channel.vue';
import Comment from '@/components/TV/Comment.vue';
import Program from '@/components/TV/Program.vue';
import Utils, { TVUtils } from '@/utils';

export default Vue.extend({
    name: 'Watch',
    components: {
        Channel,
        Comment,
        Program,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            TVUtils: TVUtils,

            // 現在時刻
            time: dayjs().format('YYYY/MM/DD HH:mm:ss'),

            // 表示されるパネルのタブ
            panel_active_tab: Utils.getSettingsItem('panel_active_tab'),

            // 背景の URL
            background_url: '',

            // プレイヤーのローディング状態
            // 既定でローディングとする
            is_loading: true,

            // プレイヤーの背景を表示するか
            // 既定で表示しない
            is_background_display: false,

            // コントロールを表示するか
            // 既定で表示する
            is_control_display: true,

            // パネルを表示するか
            // panel_display_state が 'AlwaysDisplay' なら常に表示し、'AlwaysFold' なら常に折りたたむ
            // 'RestorePreviousState' なら is_display_latest_panel の値を使い､前回の状態を復元する
            is_panel_display: (() => {
                switch (Utils.getSettingsItem('panel_display_state')) {
                    case 'AlwaysDisplay':
                        return true;
                    case 'AlwaysFold':
                        return false;
                    case 'RestorePreviousState':
                        return Utils.getSettingsItem('is_display_latest_panel');
                }
            })() as boolean,

            // フルスクリーン状態かどうか
            is_fullscreen: false,

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
            channels_list: new Map() as Map<string, IChannel[]>,

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

            // ***** キャプチャ *****

            // キャプチャボタンの要素
            capture_button: null as HTMLDivElement | null,

            // コメント付きキャプチャボタンの要素
            comment_capture_button: null as HTMLDivElement | null,

            // キャプチャ用の Canvas
            canvas: null as HTMLCanvasElement | null,

            // キャプチャ用の Canvas のコンテキスト
            canvas_context: null as CanvasRenderingContext2D | null,

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
                            { name: '数字キー・テンキーに対応するリモコン番号 (1~12) のチャンネルに切り替える<br style="display:block;content:\'\';margin:5px 0;">（同時に Shift キーを押すと、地デジならBS、BSなら地デジのチャンネルを選局する）', keys: [{name: '1~9, 0, -(=), ^(~)', icon: false}] },
                            { name: '前のチャンネルに切り替える', keys: [{name: 'fluent:arrow-up-12-filled', icon: true}] },
                            { name: '次のチャンネルに切り替える', keys: [{name: 'fluent:arrow-down-12-filled', icon: true}] },
                            { name: 'キーボードショートカットの一覧を表示する', keys: [{name: '／(？)', icon: false}] },
                        ]
                    },
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
                    }
                ],
                right_column: [
                    {
                        name: 'プレイヤー',
                        icon: 'fluent:play-20-filled',
                        icon_height: '20px',
                        shortcuts: [
                            { name: '再生 / 一時停止の切り替え', keys: [{name: 'Space', icon: false}] },
                            { name: 'プレイヤーの音量を上げる', keys: [{name: 'Shift', icon: false}, {name: 'fluent:arrow-up-12-filled', icon: true}] },
                            { name: 'プレイヤーの音量を下げる', keys: [{name: 'Shift', icon: false}, {name: 'fluent:arrow-down-12-filled', icon: true}] },
                            { name: '停止して0.5秒早戻し', keys: [{name: 'fluent:arrow-left-12-filled', icon: true}] },
                            { name: '停止して0.5秒早送り', keys: [{name: 'fluent:arrow-right-12-filled', icon: true}] },
                            { name: 'フルスクリーンの切り替え', keys: [{name: 'F', icon: false}] },
                            { name: 'ライブストリームの同期', keys: [{name: 'W', icon: false}] },
                            { name: 'Picture-in-Picture の表示切り替え', keys: [{name: 'E', icon: false}] },
                            { name: '字幕の表示切り替え', keys: [{name: 'S', icon: false}] },
                            { name: 'コメントの表示切り替え', keys: [{name: 'D', icon: false}] },
                            { name: '映像をキャプチャする', keys: [{name: 'C', icon: false}] },
                            { name: '映像をコメントを付けてキャプチャする', keys: [{name: 'V', icon: false}] },
                            { name: 'コメント入力フォームにフォーカスする', keys: [{name: 'M', icon: false}] },
                        ]
                    }
                ]
            }
        }
    },
    // 開始時に実行
    created() {

        // 初期化
        this.init();

        (async () => {

            // RomSound を鳴らすための AudioContext を生成
            this.romsounds_context = new AudioContext();

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

        })();
    },
    // 終了前に実行
    beforeDestroy() {

        // destroy() を実行
        // 別のページへ遷移するため、DPlayer のインスタンスを確実に破棄する
        // さもなければ、ブラウザがリロードされるまでバックグラウンドで永遠に再生されてしまう
        this.destroy(true);

        // ページ上でキーが押されたときのイベントを削除
        if (this.shortcut_key_handler !== null) {
            document.removeEventListener('keydown', this.shortcut_key_handler);
            this.shortcut_key_handler = null;
        }

        // AudioContext のリソースを解放
        this.romsounds_context.close();
    },
    // チャンネル切り替え時に実行
    // コンポーネント（インスタンス）は再利用される
    // ref: https://router.vuejs.org/ja/guide/advanced/navigation-guards.html#%E3%83%AB%E3%83%BC%E3%83%88%E5%8D%98%E4%BD%8D%E3%82%AB%E3%82%99%E3%83%BC%E3%83%88%E3%82%99
    beforeRouteUpdate(to, from, next) {

        // 前のインスタンスを破棄して終了する
        this.destroy();

        // チャンネル ID を次のチャンネルのものに切り替える
        this.channel_id = to.params.channel_id;

        // 既に取得済みのチャンネル情報で、前・現在・次のチャンネル情報を更新する
        [this.channel_previous, this.channel, this.channel_next]
            = TVUtils.getPreviousAndCurrentAndNextChannel(this.channels_list, this.channel_id);

        // 0.5秒だけ待ってから
        // 連続して押した時などにライブストリームを初期化しないように猶予を設ける
        this.interval_ids.push(window.setTimeout(() => {

            // 現在のインスタンスを初期化する
            this.init();

        }, 500));

        next();
    },
    watch: {
        // 前回視聴画面を開いた際にパネルが表示されていたかどうかを保存
        is_panel_display() {
            Utils.setSettingsItem('is_display_latest_panel', this.is_panel_display);
        }
    },
    methods: {

        // 初期化する
        init() {

            // ローディング中の背景画像をランダムで設定
            this.background_url = Utils.generatePlayerBackgroundURL();

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
                    await this.$router.replace({path: '/not-found/'});
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
                const pinned_channel_type = TVUtils.getChannelType(pinned_channel_id, true);
                pinned_channels.push(this.channels_list.get(pinned_channel_type).find((channel) => {
                    return channel.channel_id === pinned_channel_id;  // チャンネル ID がピン留めされているチャンネルのものと同じ
                }));
            }

            // pinned_channels に何か入っていたらピン留めタブを表示するし、そうでなければ表示しない
            if (pinned_channels.length > 0) {
                this.channels_list.set('ピン留め', pinned_channels);
            } else {
                this.channels_list.delete('ピン留め');
            }

            // 前と次のチャンネル ID を取得する
            [this.channel_previous, , this.channel_next] = TVUtils.getPreviousAndCurrentAndNextChannel(this.channels_list, this.channel_id);

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
                    await this.$router.replace({path: `/tv/watch/${this.channel_previous.channel_id}`});
                });
                navigator.mediaSession.setActionHandler('nexttrack', async () => {  // 次のチャンネルに切り替え
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: this.channel_next.program_present ? this.channel_next.program_present.title : '放送休止',
                        artist: this.channel_next.channel_name,
                        artwork: artwork,
                    });
                    // ルーティングを次のチャンネルに置き換える
                    await this.$router.replace({path: `/tv/watch/${this.channel_next.channel_id}`});
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

                // コメント入力フォームにフォーカスされているときは実行しない
                // タイマーを掛け直してから抜ける
                if (document.activeElement === this.player.template.commentInput) {
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

            // DPlayer を初期化
            this.player = new DPlayer({
                container: this.$el.querySelector('.watch-player__dplayer'),
                theme: '#E64F97',  // テーマカラー
                lang: 'ja-jp',  // 言語
                live: true,  // ライブモード
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
                            for (const quality of ['1080p', '810p', '720p', '540p', '480p', '360p', '240p']) {
                                qualities.push({
                                    name: quality,
                                    type: 'mpegts',
                                    url: `${Utils.api_base_url}/streams/live/${this.channel_id}/${quality}/mpegts`,
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
                            enableWorker: true,  // Web Worker を有効にする
                            liveBufferLatencyChasing: true,  // HTMLMediaElement の内部バッファによるライブストリームの待機時間を追跡する
                            liveBufferLatencyMaxLatency: 3.0,  // HTMLMediaElement で許容するバッファの最大値 (秒単位)
                            liveBufferLatencyMinRemain: 0.5,  // HTMLMediaElement に保持されるバッファの待機時間の最小値 (秒単位)
                        }
                    },
                    // aribb24.js
                    aribb24: {
                        normalFont: '"Windows TV MaruGothic", "Hiragino Maru Gothic Pro", "Yu Gothic Medium", sans-serif',
                        gaijiFont: '"Windows TV MaruGothic", "Hiragino Maru Gothic Pro", "Yu Gothic Medium", sans-serif',
                        forceStrokeColor: 'black',  // 縁取りする色
                        drcsReplacement: true,  // DRCS 文字を対応する Unicode 文字に置換
                        enableRawCanvas: true,  // 高解像度の字幕 Canvas を取得できるように
                        useStrokeText: true,  // 縁取りに strokeText API を利用
                        usePUA: true,  // Unicode 領域の代わりに私用面の領域を利用
                        PRACallback: (index: number) => {  // 文字スーパーの PRA (内蔵音再生コマンド) のコールバックを指定
                            // 設定で文字スーパーが無効なら実行しない
                            if (Utils.getSettingsItem('is_display_superimpose_tv') === false) return;
                            // index に応じた内蔵音を鳴らす
                            // ref: https://ics.media/entry/200427/
                            // ref: https://www.ipentec.com/document/javascript-web-audio-api-change-volume
                            const gain_node = this.romsounds_context.createGain();
                            const buffer_source_node = this.romsounds_context.createBufferSource();
                            buffer_source_node.buffer = this.romsounds_buffers[index];  // 音声データを読み込み
                            buffer_source_node.connect(gain_node);  // GainNode につなげる
                            gain_node.connect(this.romsounds_context.destination);  // 出力につなげる
                            gain_node.gain.value = 3;  // 音量を3倍にする（1倍だと結構小さめ）
                            buffer_source_node.start(0);  // 再生開始
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

            // 画質の切り替えが開始されたとき
            this.player.on('quality_start', () => {

                // ローディング中の背景画像をランダムで設定
                this.background_url = Utils.generatePlayerBackgroundURL();

                // イベントソースを閉じる
                if (this.eventsource !== null) {
                    this.eventsource.close();
                    this.eventsource = null;
                }

                // 新しい EventSource を作成
                // 画質ごとにイベント API は異なるため、一度破棄してから作り直す
                this.initEventHandler();
            });

            // 設定で文字スーパーが有効
            // 字幕が非表示の場合でも、文字スーパーは表示する
            if (Utils.getSettingsItem('is_display_superimpose_tv') === true) {
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

            // 停止状態でかつ再生時間からバッファが 30 秒以上離れていないかを1分おきに監視し、そうなっていたら強制的にシークする
            // mpegts.js の仕様上、MSE に未再生のバッファがたまり過ぎると SourceBuffer が追加できなくなるため、強制的に接続が切断されてしまう
            this.interval_ids.push(window.setInterval(() => {
                if (this.player.video.paused && this.player.video.buffered.end(0) - this.player.video.currentTime > 30) {
                    this.player.sync();
                }
            }, 60 * 1000));

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
        },

        // イベントハンドラーを初期化する
        initEventHandler() {

            // 必ず最初はローディング状態とする
            this.is_loading = true;

            // プレイヤーの背景を非表示にするイベントを登録
            // 実際に再生可能になるのを待ってから実行する
            const on_canplay = () => {
                // 念のためさらに少しだけ待ってから
                window.setTimeout(() => {
                    this.is_loading = false;
                    // ラジオチャンネルでは映像の代わりに背景画像を表示し続ける
                    if (this.channel.is_radiochannel) {
                        this.is_background_display = true;
                    } else {
                        this.is_background_display = false;
                    }
                }, 100);
                this.player.video.oncanplay = null;
                this.player.video.oncanplaythrough = null;
            }
            this.player.video.oncanplay = on_canplay;
            this.player.video.oncanplaythrough = on_canplay;

            // EventSource を作成
            // ラジオチャンネルの場合は見かけ上の品質と API に渡す品質が異なるので、それに合わせる
            const quality_name = (this.channel.is_radiochannel) ? '1080p' : this.player.quality.name;
            this.eventsource = new EventSource(`${Utils.api_base_url}/streams/live/${this.channel_id}/${quality_name}/events`);

            // 初回接続時のイベント
            this.eventsource.addEventListener('initial_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data);

                // ステータスが Standby であれば、プレイヤーの背景を表示する
                if (event.status === 'Standby') {
                    this.is_background_display = true;
                }
            });

            // ステータスが更新されたときのイベント
            this.eventsource.addEventListener('status_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data);
                console.log(`Status: ${event.status} Detail:${event.detail}`);

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

                        // プレイヤーの背景を表示する
                        this.is_background_display = true;

                        break;
                    }

                    // Status: Offline
                    case 'Offline': {

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

        // キャプチャ関連のイベントを初期化する
        initCaptureHandler() {

            // コメント付きキャプチャボタンの HTML を追加
            // insertAdjacentHTML で .dplayer-icons-right の一番左側に配置する
            // この後に通常のキャプチャボタンが insert されるので、実際は左から2番目
            this.$el.querySelector('.dplayer-icons.dplayer-icons-right').insertAdjacentHTML('afterbegin', `
                <div class="dplayer-icon dplayer-comment-capture-icon" aria-label="コメントを付けてキャプチャ"
                    data-balloon-nofocus="" data-balloon-pos="up">
                    <span class="dplayer-icon-content">
                        <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32"><path d="M16 23c-3.309 0-6-2.691-6-6s2.691-6 6-6 6 2.691 6 6-2.691 6-6 6zM16 13c-2.206 0-4 1.794-4 4s1.794 4 4 4c2.206 0 4-1.794 4-4s-1.794-4-4-4zM27 28h-22c-1.654 0-3-1.346-3-3v-16c0-1.654 1.346-3 3-3h3c0.552 0 1 0.448 1 1s-0.448 1-1 1h-3c-0.551 0-1 0.449-1 1v16c0 0.552 0.449 1 1 1h22c0.552 0 1-0.448 1-1v-16c0-0.551-0.448-1-1-1h-11c-0.552 0-1-0.448-1-1s0.448-1 1-1h11c1.654 0 3 1.346 3 3v16c0 1.654-1.346 3-3 3zM24 10.5c0 0.828 0.672 1.5 1.5 1.5s1.5-0.672 1.5-1.5c0-0.828-0.672-1.5-1.5-1.5s-1.5 0.672-1.5 1.5zM15 4c0 0.552-0.448 1-1 1h-4c-0.552 0-1-0.448-1-1v0c0-0.552 0.448-1 1-1h4c0.552 0 1 0.448 1 1v0z"></path></svg>
                    </span>
                </div>
            `);

            // キャプチャボタンの HTML を追加
            // 標準のスクリーンショット機能は貧弱なので、あえて独自に実装している（そのほうが自由度も高くてやりやすい）
            // insertAdjacentHTML で .dplayer-icons-right の一番左側に配置する
            this.$el.querySelector('.dplayer-icons.dplayer-icons-right').insertAdjacentHTML('afterbegin', `
                <div class="dplayer-icon dplayer-capture-icon" aria-label="キャプチャ"
                    data-balloon-nofocus="" data-balloon-pos="up">
                    <span class="dplayer-icon-content">
                        <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32"><path d="M16 23c-3.309 0-6-2.691-6-6s2.691-6 6-6 6 2.691 6 6-2.691 6-6 6zM16 13c-2.206 0-4 1.794-4 4s1.794 4 4 4c2.206 0 4-1.794 4-4s-1.794-4-4-4zM27 28h-22c-1.654 0-3-1.346-3-3v-16c0-1.654 1.346-3 3-3h3c0.552 0 1 0.448 1 1s-0.448 1-1 1h-3c-0.551 0-1 0.449-1 1v16c0 0.552 0.449 1 1 1h22c0.552 0 1-0.448 1-1v-16c0-0.551-0.448-1-1-1h-11c-0.552 0-1-0.448-1-1s0.448-1 1-1h11c1.654 0 3 1.346 3 3v16c0 1.654-1.346 3-3 3zM24 10.5c0 0.828 0.672 1.5 1.5 1.5s1.5-0.672 1.5-1.5c0-0.828-0.672-1.5-1.5-1.5s-1.5 0.672-1.5 1.5zM15 4c0 0.552-0.448 1-1 1h-4c-0.552 0-1-0.448-1-1v0c0-0.552 0.448-1 1-1h4c0.552 0 1 0.448 1 1v0z"></path></svg>
                    </span>
                </div>
            `);

            // キャプチャ用の Canvas を初期化
            // パフォーマンス向上のため、一度作成した Canvas は使い回す
            this.canvas = document.createElement('canvas');
            this.canvas_context = this.canvas.getContext('2d');

            // 映像の解像度を Canvas サイズとして設定
            // 映像が読み込まれた / 画質が変わったときに映像側に Canvas サイズを合わせる
            this.canvas.width = 0;
            this.canvas.height = 0;
            this.player.on('loadedmetadata', () => {
                this.canvas.width = this.player.video.videoWidth;
                this.canvas.height = this.player.video.videoHeight;
            });

            this.capture_button = this.$el.querySelector('.dplayer-icon.dplayer-capture-icon');
            this.comment_capture_button = this.$el.querySelector('.dplayer-icon.dplayer-comment-capture-icon');

            // 表示されているニコニコ実況のコメントを Canvas に描画する関数
            // ZenzaWatch のコードを参考にさせていただいています
            // ref: https://github.com/segabito/ZenzaWatch/blob/master/packages/lib/src/dom/VideoCaptureUtil.js
            const DrawComments = async () => {

                // HTML を SVG 画像の Image に変換する
                // ref: https://web.archive.org/web/2/https://developer.mozilla.org/ja/docs/Web/HTML/Canvas/Drawing_DOM_objects_into_a_canvas
                const HTMLtoSVGImage = async (html: string, width: number, height: number): Promise<HTMLImageElement> => {

                    // SVG の foreignObject を使い、HTML をそのまま SVG に埋め込む
                    // SVG なので、CSS はインラインでないと適用されない…
                    // DPlayer の danmaku.scss の内容のうち、描画に必要なプロパティのみを列挙 (追加変更したものもある)
                    // ref: https://github.com/tsukumijima/DPlayer/blob/master/src/css/danmaku.scss
                    const svg = (`
                        <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
                            <foreignObject width="100%" height="100%">
                                <div xmlns="http://www.w3.org/1999/xhtml">
                                    <style>
                                    .dplayer-danmaku {
                                        position: absolute;
                                        top: 0;
                                        left: 0;
                                        right: 0;
                                        bottom: 0;
                                        color: #fff;
                                        font-size: 29px;
                                        font-family: 'YakuHanJPs', 'Open Sans', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-item {
                                        display: inline-block;
                                        line-height: 1;
                                        font-weight: bold;
                                        font-size: var(--dplayer-danmaku-font-size);
                                        opacity: var(--dplayer-danmaku-opacity);
                                        text-shadow: 1.2px 1.2px 4px rgba(0, 0, 0, 0.9);
                                        white-space: nowrap;
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-item--demo {
                                        position: absolute;
                                        visibility: hidden;
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-item span {
                                        box-decoration-break: clone;
                                        -webkit-box-decoration-break: clone;
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-item.dplayer-danmaku-size-big {
                                        font-size: calc(var(--dplayer-danmaku-font-size) * 1.25);
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-item.dplayer-danmaku-size-small {
                                        font-size: calc(var(--dplayer-danmaku-font-size) * 0.8);
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-right {
                                        position: absolute;
                                        right: 0;
                                    }
                                    .dplayer-danmaku .dplayer-danmaku-top, .dplayer-danmaku .dplayer-danmaku-bottom {
                                        position: absolute;
                                        left: 50%;
                                        transform: translateX(-50%);
                                    }
                                    </style>
                                    ${html}
                                </div>
                            </foreignObject>
                        </svg>
                    `).trim();

                    // Data URL 化して Image オブジェクトにする
                    // わざわざ Blob にするよりこっちのほうが楽
                    const image = new Image();
                    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

                    // Image は onload を使わなくても await Image.decode() でロードできる
                    await image.decode();
                    return image;
                };

                // コメントが表示されている要素の HTML
                let comments_html = (this.player.template.danmaku as HTMLDivElement).outerHTML;

                // スクロール中のコメントは HTML だけでは現在の表示位置が特定できないため、HTML を修正する
                for (const comment of this.$el.querySelectorAll('.dplayer-danmaku-move')) { // コメントの数だけ置換
                    // スクロール中のコメントの表示座標を計算
                    const position = comment.getBoundingClientRect().left - this.player.video.getBoundingClientRect().left;
                    comments_html = comments_html.replace(/transform: translateX\(.*?\);/, `left: ${position}px;`);
                }

                // HTML を画像として取得
                // SVG のサイズはコメントが表示されている要素に合わせる (そうしないとプレイヤー側と一致しない)
                // SVG はベクター画像なので、リサイズしても画質が変わらないはず
                const comments_image = await HTMLtoSVGImage(
                    comments_html,
                    (this.player.template.danmaku as HTMLDivElement).offsetWidth,
                    (this.player.template.danmaku as HTMLDivElement).offsetHeight,
                );

                // コメント描画領域がコントロールの表示によりリサイズされている (=16:9でない) 場合も考慮して、コメント要素の offsetWidth から高さを求める
                // 映像の幅 (ex: 1920) がコメント描画領域の幅 (ex: 1280) の何倍かの割合 (ex: 1.5 (150%))
                const draw_scale_ratio = this.canvas.width / (this.player.template.danmaku as HTMLDivElement).offsetWidth;
                // コメント描画領域の高さを映像の幅に合わせて（コメント描画領域のアスペクト比を維持したまま）拡大した値
                // 映像の高さが 1080 のとき、コントロールがコメント領域と被っていない or 表示されていないなら、この値は 1080 に近くなる
                // 0.5625 (56.25%) = 16:9 の幅を 1 としたときの高さの割合
                const draw_height = (this.player.template.danmaku as HTMLDivElement).offsetHeight * draw_scale_ratio;

                this.canvas_context.drawImage(comments_image, 0, 0, this.canvas.width, draw_height);
            };

            // キャプチャして保存する関数
            // 通常のキャプチャもコメント付きキャプチャも途中まで処理は同じなので、共通化する
            // 映像のみと字幕付き (字幕表示時のみ) の両方のキャプチャを生成する
            const CaptureAndSave = async (with_comments: boolean = false) => {

                // まだ映像の表示準備が終わっていない (Canvas の幅/高さが 0 のまま)
                if (this.canvas.width === 0 && this.canvas.height === 0) {
                    this.player.notice('読み込み中はキャプチャできません。');
                    return;
                }

                // コメントが表示されていないのにコメント付きキャプチャしようとした
                if (this.player.danmaku.showing === false) {
                    this.player.notice('コメントを付けてキャプチャするには、コメント表示をオンにしてください。');
                    return;
                }

                // ファイル名（拡張子なし）
                const filename = `Capture_${dayjs().format('YYYYMMDD-HHmmss')}`;

                // 字幕・文字スーパーの Canvas を取得
                // getRawCanvas() で映像と同じ解像度の Canvas が取得できる
                const caption_canvas: HTMLCanvasElement = this.player.plugins.aribb24Caption.getRawCanvas();
                const superimpose_canvas: HTMLCanvasElement = this.player.plugins.aribb24Superimpose.getRawCanvas();

                // Canvas に映像を描画
                this.canvas_context.drawImage(this.player.video, 0, 0, this.canvas.width, this.canvas.height);

                // 文字スーパーを描画 (表示されている場合)
                // 文字スーパー自体が稀だし、文字スーパーなしでキャプチャ撮りたいユースケースはない…はず
                if (this.player.plugins.aribb24Superimpose.isShowing === true && this.player.plugins.aribb24Superimpose.isPresent()) {
                    this.canvas_context.drawImage(superimpose_canvas, 0, 0, this.canvas.width, this.canvas.height);
                }

                // コメント付きキャプチャ: 追加でニコニコ実況のコメントを描画
                if (with_comments === true) {
                    await DrawComments();
                }

                // 字幕表示時のキャプチャの保存モード: 映像のみ or 両方
                if (['VideoOnly', 'Both'].includes(Utils.getSettingsItem('capture_caption_mode'))) {

                    // 通常のキャプチャ:  Canvas (映像のみ) を画像にエクスポート
                    // コメント付きキャプチャ:  Canvas (映像 + コメント) を画像にエクスポート
                    this.canvas.toBlob((blob) => {

                        // Blob 化に失敗
                        if (blob === null) {
                            this.player.notice('キャプチャの保存に失敗しました…')
                            return;
                        }

                        // キャプチャの保存先: ブラウザ or 両方
                        if (['Browser', 'Both'].includes(Utils.getSettingsItem('capture_save_mode'))) {

                            // キャプチャをダウンロード
                            // TODO: キャプチャを KonomiTV サーバーにアップロードする
                            // TODO: キャプチャを Twitter タブ側に引き渡す
                            Utils.downloadBlobImage(blob, `${filename}.jpg`);
                        }

                        // キャプチャの保存先: KonomiTV サーバーにアップロード or 両方
                        if (['UploadServer', 'Both'].includes(Utils.getSettingsItem('capture_save_mode'))) {

                            // TODO: 未実装
                            this.player.notice('キャプチャの KonomiTV サーバーへのアップロードは未実装です。');
                        }

                    // 保存する画像の品質
                    }, 'image/jpeg', 1);
                }

                // 字幕が表示されているときのみ実行（字幕が表示されていないのにやっても意味がない）
                if (this.player.plugins.aribb24Caption.isShowing === true && this.player.plugins.aribb24Caption.isPresent()) {

                    // コメント付きキャプチャ: 映像と文字スーパーの描画をやり直す
                    // すでに字幕なしキャプチャを生成する過程でコメントを描画してしまっているため、映像描画からやり直す必要がある
                    if (with_comments === true) {
                        this.canvas_context.drawImage(this.player.video, 0, 0, this.canvas.width, this.canvas.height);
                        this.canvas_context.drawImage(superimpose_canvas, 0, 0, this.canvas.width, this.canvas.height);
                    }

                    // 字幕を重ねて描画
                    this.canvas_context.drawImage(caption_canvas, 0, 0, this.canvas.width, this.canvas.height);

                    // コメント付きキャプチャ: 追加でニコニコ実況のコメントを描画
                    if (with_comments === true) {
                        await DrawComments();
                    }

                    // 字幕表示時のキャプチャの保存モード: 字幕キャプチャのみ or 両方
                    if (['CompositingCaption', 'Both'].includes(Utils.getSettingsItem('capture_caption_mode'))) {

                        // 通常のキャプチャ:  Canvas (映像 + 字幕) を画像にエクスポート
                        // コメント付きキャプチャ:  Canvas (映像 + 字幕 + コメント) を画像にエクスポート
                        this.canvas.toBlob((blob) => {

                            // Blob 化に失敗
                            if (blob === null) {
                                this.player.notice('キャプチャの保存に失敗しました…')
                                return;
                            }

                            // キャプチャの保存先: ブラウザ or 両方
                            if (['Browser', 'Both'].includes(Utils.getSettingsItem('capture_save_mode'))) {

                                // キャプチャをダウンロード
                                // TODO: キャプチャを KonomiTV サーバーにアップロードする
                                // TODO: キャプチャを Twitter タブ側に引き渡す
                                Utils.downloadBlobImage(blob, `${filename}_caption.jpg`);
                            }

                            // キャプチャの保存先: KonomiTV サーバーにアップロード or 両方
                            if (['UploadServer', 'Both'].includes(Utils.getSettingsItem('capture_save_mode'))) {

                                // TODO: 未実装
                                this.player.notice('キャプチャの KonomiTV サーバーへのアップロードは未実装です。');
                            }

                        // 保存する画像の品質
                        }, 'image/jpeg', 1);
                    }
                }
            };

            // キャプチャボタンがクリックされたときのイベント
            // ショートカットからのキャプチャでも同じイベントがトリガーされる
            this.capture_button.addEventListener('click', async () => {
                await CaptureAndSave();
            });

            // コメント付きキャプチャボタンがクリックされたときのイベント
            // ショートカットからのキャプチャでも同じイベントがトリガーされる
            this.comment_capture_button.addEventListener('click', async () => {
                await CaptureAndSave(true);
            });
        },

        // ショートカットキーを初期化する
        initShortcutKeyHandler() {

            // ショートカットキーハンドラー
            this.shortcut_key_handler = (event: KeyboardEvent) => {

                // キーリピート（押しっぱなし）状態の場合は基本実行しない
                // 押し続けると何度も同じ動作が実行されて大変な事になる…
                // ただ、キーリピートを使いたい場合もあるので、リピート状態をフラグとして保存する
                let is_repeat = false;
                if (event.repeat) is_repeat = true;

                // キーリピート状態は event.repeat を見る事でだいたい検知できるが、最初の何回かは検知できないこともある
                // そこで、0.1 秒以内に連続して発火したキーイベントは間引きも兼ねて実行しない
                const now = Date.now();
                if (now - this.shortcut_key_pressed_at < (0.1 * 1000)) return;
                this.shortcut_key_pressed_at = now;  // 最終押下時刻を更新

                // input・textarea・contenteditable 状態の要素でなければ
                // 文字入力中にショートカットキーが作動してしまわないように
                const tag = document.activeElement.tagName.toUpperCase();
                const editable = document.activeElement.getAttribute('contenteditable');
                if (tag !== 'INPUT' && tag !== 'TEXTAREA' && editable !== '' && editable !== 'true') {

                    // ***** 数字キーでチャンネルを切り替える *****

                    if (is_repeat === false) {

                        // チャンネルタイプを選択
                        // Shift キーが押されていたらチャンネルタイプを地デジならBSに、BSなら地デジにする
                        let switch_channel_type = this.channel.channel_type;
                        if (event.shiftKey && this.channel.channel_type == 'GR') switch_channel_type = 'BS';
                        if (event.shiftKey && this.channel.channel_type == 'BS') switch_channel_type = 'GR';

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
                            const switch_channel = TVUtils.getChannelFromRemoconID(this.channels_list, switch_channel_type, switch_remocon_id);

                            // チャンネルが取得できていれば、ルーティングをそのチャンネルに置き換える
                            // 押されたキーに対応するリモコン番号のチャンネルがない場合や、現在と同じチャンネル ID の場合は何も起こらない
                            if (switch_channel !== null && switch_channel.channel_id !== this.channel_id) {
                                (async () => await this.$router.replace({path: `/tv/watch/${switch_channel.channel_id}`}))();
                                return;
                            }
                        }
                    }

                    // ***** 上下キーでチャンネルを切り替える *****

                    if (is_repeat === false && event.shiftKey === false) {
                        // ↑キー: 前のチャンネルに切り替え
                        if (event.code === 'ArrowUp') {
                            event.preventDefault();  // デフォルトのイベントを無効化
                            (async () => await this.$router.replace({path: `/tv/watch/${this.channel_previous.channel_id}`}))();
                            return;
                        }
                        // ↓キー: 次のチャンネルに切り替え
                        if (event.code === 'ArrowDown') {
                            event.preventDefault();  // デフォルトのイベントを無効化
                            (async () => await this.$router.replace({path: `/tv/watch/${this.channel_next.channel_id}`}))();
                            return;
                        }
                    }

                    // ***** キーボードショートカットの一覧を表示する *****

                    // /(?)キー: キーボードショートカットの一覧を表示する
                    if (event.code === 'Slash' && is_repeat === false) {
                        this.shortcut_key_modal = !this.shortcut_key_modal;
                        return;
                    }

                    // ***** パネルのタブを切り替える *****

                    if (is_repeat === false) {
                        // Pキー: パネルの表示切り替え
                        if (event.code === 'KeyP') {
                            this.is_panel_display = !this.is_panel_display;
                            return;
                        }
                        // Kキー: 番組情報タブ
                        if (event.code === 'KeyK') {
                            this.panel_active_tab = 'Program';
                            return;
                        }
                        // Lキー: チャンネルタブ
                        if (event.code === 'KeyL') {
                            this.panel_active_tab = 'Channel';
                            return;
                        }
                        // ;(+)キー: コメントタブ
                        if (event.code === 'Semicolon') {
                            this.panel_active_tab = 'Comment';
                            return;
                        }
                        // :(*)キー: Twitterタブ
                        if (event.code === 'Quote') {
                            this.panel_active_tab = 'Twitter';
                            return;
                        }
                    }

                    // ***** プレイヤーのショートカットキー *****

                    // プレイヤーが初期化されていない際や Ctrl or Cmd キーが一緒に押された際に作動しないように
                    if (this.player !== null && !event.ctrlKey && !event.metaKey) {

                        // ←キー: 停止して0.5秒巻き戻し
                        if (event.code === 'ArrowLeft') {
                            event.preventDefault();  // デフォルトのイベントを無効化
                            if (this.player.video.paused === false) this.player.video.pause();
                            this.player.video.currentTime = this.player.video.currentTime - 0.5;
                            return;
                        }
                        // →キー: 停止して0.5秒早送り
                        if (event.code === 'ArrowRight') {
                            event.preventDefault();  // デフォルトのイベントを無効化
                            if (this.player.video.paused === false) this.player.video.pause();
                            this.player.video.currentTime = this.player.video.currentTime + 0.5;
                            return;
                        }
                        // Shift + ↑キー: プレイヤーの音量を上げる
                        if (event.shiftKey === true && event.code === 'ArrowUp') {
                            this.player.volume(this.player.volume() + 0.05);
                        }
                        // Shift + ↓キー: プレイヤーの音量を下げる
                        if (event.shiftKey === true && event.code === 'ArrowDown') {
                            this.player.volume(this.player.volume() - 0.05);
                        }

                        // キーリピートでは実行しないショートカット
                        if (is_repeat === false) {
                            // Spaceキー: 再生/停止
                            if (event.code === 'Space') {
                                this.player.toggle();
                                return;
                            }
                            // Fキー: フルスクリーンの切り替え
                            if (event.code === 'KeyF') {
                                this.player.fullScreen.toggle();
                                return;
                            }
                            // Wキー: ライブストリームの同期
                            if (event.code === 'KeyW') {
                                this.player.sync();
                                return;
                            }
                            // Eキー: Picture-in-Picture の表示切り替え
                            if (event.code === 'KeyE') {
                                if (document.pictureInPictureEnabled) {
                                    this.player.template.pipButton.click();
                                }
                                return;
                            }
                            // Sキー: 字幕の表示切り替え
                            if (event.code === 'KeyS') {
                                this.player.subtitle.toggle();
                                if (!this.player.subtitle.container.classList.contains('dplayer-subtitle-hide')) {
                                    this.player.notice(`${this.player.tran('Show subtitle')}`);
                                } else {
                                    this.player.notice(`${this.player.tran('Hide subtitle')}`);
                                }
                                return;
                            }
                            // Dキー: コメントの表示切り替え
                            if (event.code === 'KeyD') {
                                this.player.template.showDanmaku.click();
                                if (this.player.template.showDanmakuToggle.checked) {
                                    this.player.notice(`${this.player.tran('Show comment')}`);
                                } else {
                                    this.player.notice(`${this.player.tran('Hide comment')}`);
                                }
                                return;
                            }
                            // Cキー: 映像をキャプチャ
                            // キャプチャボタンのクリックイベントを発火させる
                            if (event.code === 'KeyC') {
                                this.capture_button.click();
                            }
                            // Vキー: 映像を実況コメントを付けてキャプチャ
                            // コメント付きキャプチャボタンのクリックイベントを発火させる
                            if (event.code === 'KeyV') {
                                this.comment_capture_button.click();
                            }
                            // Mキー: コメント入力フォームにフォーカス
                            if (event.code === 'KeyM') {
                                event.preventDefault();  // デフォルトのイベントを無効化
                                this.player.controller.show();
                                this.player.comment.show();
                                this.controlDisplayTimer();
                                window.setTimeout(() => this.player.template.commentInput.focus(), 100);
                                return;
                            }
                        }
                    }
                }
            };

            // ページ上でキーが押されたときのイベントを登録
            document.addEventListener('keydown', this.shortcut_key_handler);
        },

        // 破棄する
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

            }, 400));  // 0.4 秒
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
    }
    .dplayer-controller-mask {
        height: 82px !important;
        background: linear-gradient(to bottom, transparent, var(--v-background-base)) !important;
        opacity: 0 !important;
        visibility: hidden;
        @media screen and (max-height: 450px) {
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
                @media screen and (max-height: 450px) {
                    right: 11px !important;
                }
            }
            // ブラウザフルスクリーンボタンを削除（実質あまり意味がないため）
            .dplayer-icon.dplayer-full-in-icon {
                display: none !important;
            }
        }
        .dplayer-comment-box {
            transition: opacity 0.3s ease, visibility 0.3s ease;
        }
    }
    .dplayer-notice {
        padding: 16px 22px !important;
        margin-right: 30px;
        border-radius: 4px !important;
        font-size: 15px !important;
        line-height: 1.6;
        @include tablet {
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
            @media screen and (max-height: 450px) {
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
                @include tablet {
                    left: calc(68px + 16px);
                }
                @media screen and (max-height: 450px) {
                    left: calc(56px + 16px);
                }
            }
        }
        .dplayer-notice {
            left: calc(68px + 30px);
            bottom: 62px;
            @include tablet {
                left: calc(68px + 16px);
            }
            @media screen and (max-height: 450px) {
                left: calc(56px + 16px);
            }
        }
        .dplayer-info-panel {
            top: 82px;
            left: calc(68px + 30px);
            @include tablet {
                left: calc(68px + 16px);
            }
            @media screen and (max-height: 450px) {
                left: calc(56px + 16px);
            }
        }
        .dplayer-comment-setting-box {
            left: calc(68px + 20px);
            @include tablet {
                left: calc(68px + 16px);
            }
            @media screen and (max-height: 450px) {
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
            @media screen and (max-height: 450px) {
                padding-left: 16px !important;
            }
        }
        .dplayer-comment-box, .dplayer-comment-setting-box {
            left: 20px !important;
            @include tablet {
                left: 16px !important;
            }
            @media screen and (max-height: 450px) {
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
            @include tablet {
                left: 16px !important;
            }
            @media screen and (max-height: 450px) {
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
    height: 28px;
    padding: 0px 8px;
    border-radius: 5px;
    background-color: var(--v-background-lighten2);
    font-size: 14.5px;
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
    @media screen and (max-height: 450px) {
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
                @include tablet {
                    padding-left: 16px;
                }
                @media screen and (max-height: 450px) {
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
        @media screen and (max-height: 450px) {
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
            @media screen and (max-height: 450px) {
                height: 32px;
                border-radius: 10px;
            }
        }

        @media screen and (max-height: 450px) {
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
            @media screen and (max-height: 450px) {
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

            @media screen and (max-height: 450px) {
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
                @media screen and (max-height: 450px) {
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

            @include tablet {
                padding-left: calc(68px + 16px);
                padding-right: 16px;
            }
            @media screen and (max-height: 450px) {
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

                @include tablet {
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

                @include tablet {
                    margin-left: 12px;
                }
                @media screen and (max-height: 450px) {
                    font-size: 16px;
                }
            }

            .watch-header__program-time {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 15px;

                @include tablet {
                    margin-left: 8px;
                }
                @media screen and (max-height: 450px) {
                    font-size: 14px;
                }
            }

            .watch-header__now {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 13px;

                @include tablet {
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
                max-width: 100%;
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
                will-change: opacity;
                transition: opacity 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94), visibility 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94);

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

                    @include desktop-medium {
                        height: 30px;
                        right: 34px;
                        bottom: 30px;
                    }

                    @include tablet {
                        height: 25px;
                        right: 30px;
                        bottom: 24px;
                    }
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
                @media screen and (max-height: 450px) {
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
                    @media screen and (max-height: 450px) {
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
                        @media screen and (max-height: 450px) {
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
        @media screen and (max-height: 450px) {
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
            @media screen and (max-height: 450px) {
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
                @media screen and (max-height: 450px) {
                    font-size: 14px;
                }

                &__icon {
                    position: relative;
                    left: -4px;
                    @media screen and (max-height: 450px) {
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
                    @media screen and (max-height: 450px) {
                        width: 38px;
                        height: 22px;
                    }
                }

                &__number {
                    flex-shrink: 0;
                    margin-left: 8px;
                    font-size: 16px;
                    @media screen and (max-height: 450px) {
                        font-size: 14px;
                    }
                }

                &__name {
                    margin-left: 5px;
                    font-size: 16px;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @media screen and (max-height: 450px) {
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
            @media screen and (max-height: 450px) {
                height: 56px;
            }

            .panel-navigation-button {
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                width: 66px;
                height: 56px;
                padding: 6px 5.5px;
                border-radius: 5px;
                color: var(--v-text-base);
                box-sizing: content-box;
                transition: color 0.3s;
                user-select: none;
                cursor: pointer;
                @media screen and (max-height: 450px) {
                    height: 42px;
                    padding: 6px 5.5px 4px;
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
                    @media screen and (max-height: 450px) {
                        margin-top: 2px;
                        font-size: 12px;
                    }
                }
            }
        }
    }
}

</style>