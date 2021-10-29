<template>
    <div class="route-container">
        <main class="watch-container" :class="{
            'watch-container--control-visible': is_control_visible,
            'watch-container--panel-visible': is_panel_visible,
        }" v-on:mousemove="controlVisibleTimer" v-on:touchmove="controlVisibleTimer">
            <nav class="watch-navigation">
                <router-link v-ripple class="watch-navigation__icon" to="/tv/">
                    <img class="watch-navigation__icon-image" src="/assets/img/icon.svg" width="23px">
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/tv/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/videos/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/schedules/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:calendar-ltr-20-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/captures/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:image-multiple-24-regular" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/watchlists/">
                    <Icon class="watch-navigation__link-icon" icon="ic:round-playlist-play" width="26px" />
                </router-link>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/histories/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:history-16-regular" width="26px" />
                </router-link>
                <v-spacer></v-spacer>
                <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/settings/">
                    <Icon class="watch-navigation__link-icon" icon="fluent:settings-20-regular" width="26px" />
                </router-link>
                <a v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" href="https://github.com/tsukumijima/KonomiTV">
                    <Icon class="watch-navigation__link-icon" icon="fluent:info-16-regular" width="26px" />
                </a>
            </nav>
            <div class="watch-content">
                <header class="watch-header">
                    <img class="watch-header__broadcaster" :src="`${api_base_url}/channels/${($route.params.channel_id)}/logo`">
                    <span class="watch-header__program-title" v-html="decorateProgramInfo(channel.program_present, 'title')"></span>
                    <span class="watch-header__program-time">{{getProgramTime(channel.program_present, true)}}</span>
                    <v-spacer></v-spacer>
                    <span class="watch-header__now">{{time}}</span>
                </header>
                <div class="watch-player" :class="{'watch-player__background--visible': is_background_visible}">
                    <div class="watch-player__background" :style="{backgroundImage: `url(${background_url})`}">
                        <img class="watch-player__background-logo" src="/assets/img/logo.svg">
                    </div>
                    <div class="watch-player__dplayer"></div>
                    <div class="watch-player__button">
                        <router-link v-ripple class="switch-button switch-button-up" :to="`/tv/watch/${channel_previous.channel_id}`">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-left-24-filled" width="32px" rotate="1" />
                        </router-link>
                        <div v-ripple class="switch-button switch-button-panel switch-button-panel--open"
                            @click="is_panel_visible = !is_panel_visible">
                            <Icon class="switch-button-icon" icon="fluent:navigation-16-filled" width="32px" />
                        </div>
                        <router-link v-ripple class="switch-button switch-button-down" :to="`/tv/watch/${channel_next.channel_id}`">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-right-24-filled" width="33px" rotate="1" />
                        </router-link>
                    </div>
                </div>
            </div>
            <div class="watch-panel">
                <div class="watch-panel__header">
                    <div v-ripple class="panel-close-button" @click="is_panel_visible = false">
                        <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
                        <span class="panel-close-button__text">閉じる</span>
                    </div>
                    <v-spacer></v-spacer>
                    <div class="panel-broadcaster">
                        <img class="panel-broadcaster__icon" :src="`${api_base_url}/channels/${($route.params.channel_id)}/logo`">
                        <div class="panel-broadcaster__number">{{channel.channel_number}}</div>
                        <div class="panel-broadcaster__name">{{channel.channel_name}}</div>
                    </div>
                </div>
                <div class="watch-panel__content-container">
                    <div class="watch-panel__content program-container"
                        :class="{'watch-panel__content--active': tab_active === 'program'}">
                        <section class="program-info">
                            <h1 class="program-info__title" v-html="decorateProgramInfo(channel.program_present, 'title')"></h1>
                            <div class="program-info__time">{{getProgramTime(channel.program_present)}}</div>
                            <div class="program-info__description" v-html="decorateProgramInfo(channel.program_present, 'description')"></div>
                            <div class="program-info__genre-container">
                                <div class="program-info__genre" v-for="(genre, genre_index) in getAttribute(channel.program_present, 'genre', [])" :key="genre_index">
                                    {{genre.major}} / {{genre.middle}}
                                </div>
                            </div>
                            <div class="program-info__next">
                                <span class="program-info__next-decorate">NEXT</span>
                                <Icon class="program-info__next-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                            </div>
                            <span class="program-info__next-title" v-html="decorateProgramInfo(channel.program_following, 'title')"></span>
                            <div class="program-info__next-time">{{getProgramTime(channel.program_following)}}</div>
                            <div class="program-info__status">
                                <Icon icon="fa-solid:eye" height="14px" />
                                <span class="ml-2">{{channel.viewers}}</span>
                                <Icon class="ml-5" icon="fa-solid:fire-alt" height="14px" />
                                <span class="ml-2">{{getAttribute(channel, 'channel_force', '-')}}</span>
                                <Icon class="ml-5" icon="bi:chat-left-text-fill" height="14px" />
                                <span class="ml-2">{{getAttribute(channel, 'channel_comment', '-')}}</span>
                            </div>
                        </section>
                        <section class="program-detail-container">
                            <div class="program-detail" v-for="(detail_text, detail_heading) in getAttribute(channel.program_present, 'detail', {})" :key="detail_heading">
                                <h2 class="program-detail__heading">{{detail_heading}}</h2>
                                <div class="program-detail__text">{{detail_text}}</div>
                            </div>
                        </section>
                    </div>
                    <div class="watch-panel__content channels-container"
                        :class="{'watch-panel__content--active': tab_active === 'channel'}">
                        <v-tabs centered class="channels-tab" v-model="tab">
                            <v-tab class="channels-tab__item" v-for="(channels, channels_type) in channels_list" :key="channels_type">{{channels_type}}</v-tab>
                        </v-tabs>
                        <v-tabs-items class="channels-list" v-model="tab">
                            <v-tab-item class="channels" v-for="(channels, channels_type) in channels_list" :key="channels_type">
                                <router-link v-ripple class="channel" v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.channel_id}`">
                                    <div class="channel__broadcaster">
                                        <img class="channel__broadcaster-icon" :src="`${api_base_url}/channels/${channel.channel_id}/logo`">
                                        <div class="channel__broadcaster-content">
                                            <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.channel_name}}</span>
                                            <div class="channel__broadcaster-status">
                                                <Icon icon="fa-solid:fire-alt" height="10px" />
                                                <span class="ml-1">{{getAttribute(channel, 'channel_force', '-')}}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="channel__program-present">
                                        <span class="channel__program-present-title" v-html="decorateProgramInfo(channel.program_present, 'title')"></span>
                                        <span class="channel__program-present-time">{{getProgramTime(channel.program_present)}}</span>
                                    </div>
                                    <div class="channel__program-following">
                                        <div class="channel__program-following-title">
                                            <span class="channel__program-following-title-decorate">NEXT</span>
                                            <Icon class="channel__program-following-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                                            <span class="channel__program-following-title-text" v-html="decorateProgramInfo(channel.program_following, 'title')"></span>
                                        </div>
                                        <span class="channel__program-following-time">{{getProgramTime(channel.program_following)}}</span>
                                    </div>
                                    <div class="channel__progressbar">
                                        <div class="channel__progressbar-progress" :style="`width:${getProgramProgress(channel.program_present)}%;`"></div>
                                    </div>
                                </router-link>
                            </v-tab-item>
                        </v-tabs-items>
                    </div>
                </div>
                <div class="watch-panel__navigation">
                    <div v-ripple class="panel-navigation-button"
                        :class="{'panel-navigation-button--active': tab_active === 'program'}"
                        @click="tab_active = 'program'">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                        <span class="panel-navigation-button__text">番組情報</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                        :class="{'panel-navigation-button--active': tab_active === 'channel'}"
                        @click="tab_active = 'channel'">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                        <span class="panel-navigation-button__text">チャンネル</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                        :class="{'panel-navigation-button--active': tab_active === 'comment'}"
                        @click="tab_active = 'comment'">
                        <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="29px" />
                        <span class="panel-navigation-button__text">コメント</span>
                    </div>
                    <div v-ripple class="panel-navigation-button"
                        :class="{'panel-navigation-button--active': tab_active === 'twitter'}"
                        @click="tab_active = 'twitter'">
                        <Icon class="panel-navigation-button__icon" icon="fa-brands:twitter" width="34px" />
                        <span class="panel-navigation-button__text">Twitter</span>
                    </div>
                </div>
            </div>
        </main>
    </div>
</template>

<script lang="ts">
import Vue from 'vue';
import mixins from 'vue-typed-mixins'
import mixin from '@/mixins';
import dayjs from 'dayjs';
// @ts-ignore  JavaScript で書かれているので型定義がなく、作ろうとするとややこしくなるので黙殺
import DPlayer from 'dplayer';
import mpegts from 'mpegts.js';
import { Icon } from '@iconify/vue2';

export default mixins(mixin).extend({
    name: 'Home',
    components: {
        Icon,
    },
    data() {
        return {

            // タブの状態管理
            tab: null,

            // アクティブなタブ
            tab_active: 'program',

            // 現在時刻
            time: dayjs().format('YYYY/MM/DD HH:mm:ss'),

            // 背景の URL
            background_url: '/assets/img/player-background1.jpg',

            // プレイヤーの背景を表示するか
            // 既定で表示しない
            is_background_visible: false,

            // コントロールを表示するか
            // 既定で表示する
            is_control_visible: true,

            // パネルを表示するか
            // 既定で表示する
            is_panel_visible: true,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [],

            // コントロール表示切り替え用のインターバル ID
            // 混ぜるとダメなので独立させる
            control_interval_id: 0,

            // チャンネル ID
            channel_id: this.$route.params.channel_id,

            // チャンネル情報
            // 情報取得が完了するまでの間表示される初期値を定義
            channel: {
                'id': 'NID0-SID0',
                'service_id': 0,
                'network_id': 0,
                'remocon_id': 0,
                'channel_id': 'gr000',
                'channel_number': '---',
                'channel_name': '取得中…',
                'channel_type': 'GR',
                'channel_force': 0,
                'channel_comment': 0,
                'is_subchannel': false,
                'is_display': true,
                'viewers': 0,
                'program_present': {
                    'id': 'NID0-SID0-EID0',
                    'channel_id': 'gr000',
                    'title': '取得中…',
                    'description': '取得中…',
                    'detail': {},
                    'start_time': '2000-01-01T00:00:00+09:00',
                    'end_time': '2000-01-01T00:00:00+09:00',
                    'duration': 0,
                    'is_free': true,
                    'genre': [],
                    'video_type': '',
                    'video_codec': '',
                    'video_resolution': '',
                    'audio_type': '',
                    'audio_sampling_rate': '',
                },
                'program_following': {
                    'id': 'NID0-SID0-EID0',
                    'channel_id': 'gr000',
                    'title': '取得中…',
                    'description': '取得中…',
                    'detail': {},
                    'start_time': '2000-01-01T00:00:00+09:00',
                    'end_time': '2000-01-01T00:00:00+09:00',
                    'duration': 0,
                    'is_free': true,
                    'genre': [],
                    'video_type': '',
                    'video_codec': '',
                    'video_resolution': '',
                    'audio_type': '',
                    'audio_sampling_rate': '',
                }
            },

            // 前のチャンネルのチャンネル情報
            channel_previous: {
                'channel_id': 'gr000',
            },

            // 次のチャンネルのチャンネル情報
            channel_next: {
                'channel_id': 'gr000',
            },

            // チャンネル情報リスト
            channels_list: {},

            // プレイヤー (DPlayer) のインスタンス
            player: null,

            // イベントソースのインスタンス
            eventsource: null,
        }
    },
    // 開始時に実行
    created() {

        // init() を実行
        this.init();
    },
    // 終了前に実行
    beforeDestroy() {

        // destroy() を実行
        this.destroy();
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
            = this.getPreviousAndCurrentAndNextChannel(this.channel_id, this.channels_list);

        // 0.7秒だけ待ってから
        // 連続して押した時などにライブストリームを初期化しないように猶予を設ける
        this.interval_ids.push(setTimeout(() => {

            // 現在のインスタンスを初期化する
            this.init();

        }, 700));

        next();
    },
    methods: {

        // 初期化する
        init() {

            // 背景を4種類からランダムで設定
            this.background_url = `/assets/img/player-background${(Math.floor(Math.random() * 4) + 1)}.jpg`;

            // コントロール表示タイマーを実行
            this.controlVisibleTimer();

            // チャンネル情報を取得
            this.update();

            // 現在時刻を1秒おきに更新
            this.interval_ids.push(setInterval(() => {
                this.time = dayjs().format('YYYY/MM/DD HH:mm:ss');
            }, 1 * 1000));

            // 00秒までの残り秒数
            // 現在 16:01:34 なら 26 (秒) になる
            const residue_second = 60 - (Math.floor(new Date().getTime() / 1000) % 60);

            // 00秒になるまで待ってから
            // 番組は基本1分単位で組まれているため、20秒や45秒など中途半端な秒数で更新してしまうと反映が遅れてしまう
            this.interval_ids.push(setTimeout(() => {

                // チャンネル情報を更新
                this.update();

                // チャンネル情報を定期的に更新
                this.interval_ids.push(setInterval(() => {
                    this.update();
                }, 60 * 1000));  // 1分おき

            }, residue_second * 1000));
        },

        // チャンネル情報一覧を取得し、画面を更新する
        update() {

            // チャンネル ID が未定義なら実行しない（フェイルセーフ）
            if (this.$route.params.channel_id === undefined) {
                return;
            }

            // チャンネル情報 API にアクセス
            Vue.axios.get(`${this.api_base_url}/channels/${this.channel_id}`).then((response) => {

                // チャンネル情報を代入
                this.channel = response.data;

                // まだ初期化されていなければ
                if (this.player === null) {

                    // プレイヤーを初期化
                    this.initPlayer();

                    // イベントハンドラーを初期化
                    this.initEventHandler();
                }

                // チャンネル情報一覧 API にアクセス
                // チャンネル情報 API と同時にアクセスするとむしろレスポンスが遅くなるので、返ってくるのを待ってから実行
                Vue.axios.get(`${this.api_base_url}/channels`).then((response) => {

                    // is_display が true または現在表示中のチャンネルのみに絞り込むフィルタ関数
                    // 放送していないサブチャンネルを表示から除外する
                    const channel_id = this.channel_id;
                    function filter(channel: any) {
                        return channel.is_display || channel_id === channel.channel_id;
                    }

                    // チャンネルリストを再構築
                    // 1つでもチャンネルが存在するチャンネルタイプのみ表示するように
                    // たとえば SKY (スカパー！プレミアムサービス) のタブは SKY に属すチャンネルが1つもない（=受信できない）なら表示されない
                    this.channels_list = {};
                    if (response.data.GR.length > 0) this.channels_list['地デジ'] = response.data.GR.filter(filter);
                    if (response.data.BS.length > 0) this.channels_list['BS'] = response.data.BS.filter(filter);
                    if (response.data.CS.length > 0) this.channels_list['CS'] = response.data.CS.filter(filter);
                    if (response.data.SKY.length > 0) this.channels_list['SKY'] = response.data.SKY.filter(filter);

                    // 前と次のチャンネル ID を取得する
                    [this.channel_previous, , this.channel_next]
                        = this.getPreviousAndCurrentAndNextChannel(this.channel_id, this.channels_list);
                });

            // リクエスト失敗時
            }).catch((error) => {

                // エラー内容を表示
                console.error(error);

                // ステータスコードが 422（チャンネルが存在しない）なら 404 ページにリダイレクト
                // 正確には 404 ページ自体がルートとして存在するわけじゃないけど、そもそも存在しないページなら 404 になるので
                if (error.response && error.response.status === 422 && error.response.data.detail === 'Specified channel_id was not found') {
                    window.location.href = '/404/';
                }
            });
        },

        // マウスが動いた時のイベント
        // 3秒間何も操作がなければコントロールを非表示にする
        controlVisibleTimer() {

            // 以前セットされた setTimeout() を止める
            clearTimeout(this.control_interval_id);

            // コントロールを表示する
            this.is_control_visible = true;

            // 3秒間何も操作がなければコントロールを非表示にする
            // 3秒間の間一度でもマウスが動けばタイマーが解除されてやり直しになる
            this.control_interval_id = setTimeout(() => {

                // コントロールを非表示にする
                this.is_control_visible = false;

                // プレイヤーのコントロールと設定パネルを隠す
                if (this.player !== null) {
                    this.player.controller.hide();
                    this.player.setting.hide();
                }
            }, 3 * 1000);
        },

        // 前・現在・次のチャンネル情報を取得する
        getPreviousAndCurrentAndNextChannel(channel_id: string, channels_list: any): Array<any> {

            // 前後のチャンネルを取得
            const channels = channels_list[this.getChannelType(channel_id, true)];
            for (let index = 0; index < channels.length; index++) {
                const element = channels[index];

                // チャンネル ID が一致したときだけ
                if (element.channel_id === channel_id) {

                    // インデックスが最初か最後の時はそれぞれ最後と最初にインデックスを一周させる
                    let previous_index = index - 1;
                    if (previous_index === -1) previous_index = channels.length - 1;
                    let next_index = index + 1;
                    if (next_index === channels.length) next_index = 0;

                    // 前・現在・次のチャンネル情報を返す
                    return [channels[previous_index], channels[index], channels[next_index]];
                }
            }
        },

        // プレイヤーを初期化する
        initPlayer() {

            // mpegts を window 空間に入れる
            (window as any).mpegts = mpegts;

            // DPlayer を初期化
            this.player = new DPlayer({
                container: document.querySelector('.watch-player__dplayer'),
                volume: 1.0,
                autoplay: true,
                screenshot: true,
                airplay: false,
                live: true,
                loop: true,
                lang: 'ja-jp',
                theme: '#E64F97',
                // 読み込む m3u8 を指定する
                video: {
                    defaultQuality: this.default_quality,
                    quality: [
                        {
                            name: '1080p',
                            type: 'mpegts',
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/1080p/mpegts`,
                        },
                        {
                            name: '720p',
                            type: 'mpegts',
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/720p/mpegts`,
                        },
                        {
                            name: '540p',
                            type: 'mpegts',
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/540p/mpegts`,
                        },
                        {
                            name: '480p',
                            type: 'mpegts',
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/480p/mpegts`,
                        },
                        {
                            name: '360p',
                            type: 'mpegts',
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/360p/mpegts`,
                        },
                        {
                            name: '240p',
                            type: 'mpegts',
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/240p/mpegts`,
                        },
                    ],
                },
                // コメント設定
                // danmaku: {
                //     id: 'KonomiTV',
                //     user: 'KonomiTV',
                //     api: '',
                //     bottom: '10%',
                //     height: 35,
                //     unlimited: false,
                // },
                pluginOptions: {
                    // mpegts.js
                    mpegts: {
                        config: {
                            enableWorker: true,
                            liveBufferLatencyChasing: true,
                            liveBufferLatencyMaxLatency: 3.0,
                            liveBufferLatencyMinRemain: 0.5,
                        }
                    },
                    // aribb24.js
                    aribb24: {
                        normalFont: '"Windows TV MaruGothic","Hiragino Maru Gothic Pro","Yu Gothic Medium",sans-serif',
                        gaijiFont: '"Windows TV MaruGothic","Hiragino Maru Gothic Pro","Yu Gothic Medium",sans-serif',
                        forceStrokeColor: 'black',  // 縁取りする色
                        drcsReplacement: true,  // DRCS 文字を対応する Unicode 文字に置換
                        enableRawCanvas: true,  // 高解像度の字幕 Canvas を取得できるように
                        useStrokeText: true,  // 縁取りに strokeText API を利用
                    }
                },
                subtitle: {
                    type: 'aribb24',
                }
            });

            // デバッグ用にプレイヤーインスタンスも window 名前空間に入れる
            (window as any).player = this.player;

            // プレイヤーがタップされた時、dplayer-hide-controller がついていたらコントロールを非表示にする
            this.player.container.addEventListener('click', () => {
                if (this.player.container.classList.contains('dplayer-hide-controller')) {

                    // 以前セットされた setTimeout() を止める
                    clearTimeout(this.control_interval_id);

                    // 明示的にプレイヤーのコントロールを非表示にする
                    this.player.controller.hide();

                    // コントロールを非表示にする
                    this.is_control_visible = false;
                }
            });

            // 画質の切り替えが開始されたとき
            this.player.on('quality_start', () => {

                // 背景を4種類からランダムで設定
                this.background_url = `/assets/img/player-background${(Math.floor(Math.random() * 4) + 1)}.jpg`;

                // イベントソースを閉じる
                if (this.eventsource !== null) {
                    this.eventsource.close();
                    this.eventsource = null;
                }

                // 新しい EventSource を作成
                // 画質ごとにイベント API は異なるため、一度破棄してから作り直す
                this.initEventHandler();

            });

            // MediaSession API を使い、メディア通知の表示をカスタマイズ
            if ('mediaSession' in navigator) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: this.channel.program_present.title,
                    artist: this.channel.channel_name,
                    artwork: [
                        {src: `${this.api_base_url}/channels/${(this.channel_id)}/logo`, sizes: '256x256', type: 'image/png'},
                    ]
                });
            }
        },

        // イベントハンドラーを初期化する
        initEventHandler() {

            // EventSource を作成
            this.eventsource = new EventSource(`${this.api_base_url}/streams/live/${this.channel_id}/${this.player.quality.name}/events`);

            // ステータスが更新されたとき
            this.eventsource.addEventListener('status_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data.replace(/'/g, '"'));
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
                        this.is_background_visible = true;

                        break;
                    }

                    // Status: ONAir
                    case 'ONAir': {

                        // ステータス詳細をプレイヤーから削除
                        if (!this.player.template.notice.textContent.includes('画質を')) {  // 画質切り替えの表示を上書きしない
                            this.player.notice(this.player.template.notice.textContent, 0.000001);
                        }

                        // プレイヤーの背景を非表示にする
                        this.is_background_visible = false;

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
                        this.is_background_visible = true;

                        break;
                    }

                    // Status: Offline
                    case 'Offline': {

                        // 少し送らせてからステータス詳細をプレイヤーに表示
                        setTimeout(() => {
                            this.player.notice(event.detail, -1);
                        }, 100);

                        // イベントソースを閉じる（復帰の見込みがないため）
                        this.eventsource.close();

                        // プレイヤーの背景を表示する
                        this.is_background_visible = true;

                        break;
                    }
                }
            });

            // ステータス詳細が更新されたとき
            this.eventsource.addEventListener('detail_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data.replace(/'/g, '"'));
                console.log(`Status: ${event.status} Detail:${event.detail}`);

                // 視聴者数を更新
                this.channel.viewers = event.clients_count;

                // Standby のときだけプレイヤーに表示
                if (event.status === 'Standby') {
                    this.player.notice(event.detail, -1);

                    // プレイヤーの背景を表示する
                    if (!this.is_background_visible) {
                        this.is_background_visible = true;
                    }

                    // バッファリングしています…の場合
                    if (event.detail === 'バッファリングしています…') {

                        // 再生可能になったらプレイヤーの背景を非表示にする
                        this.player.video.oncanplay = () => {
                            this.is_background_visible = false;
                            this.player.video.oncanplay = null;
                        }
                    }
                }
            });

            // クライアント数（だけ）が更新されたとき
            this.eventsource.addEventListener('clients_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data.replace(/'/g, '"'));

                // 視聴者数を更新
                this.channel.viewers = event.clients_count;
            });
        },

        // 破棄する
        destroy() {

            // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
            // clearInterval() と clearTimeout() は中身共通なので問題ない
            for (const interval_id of this.interval_ids) {
                clearInterval(parseInt(interval_id));
            }

            // interval_ids をクリア
            this.interval_ids = [];

            // プレイヤーを破棄する
            if (this.player !== null) {
                try {
                    this.player.destroy();
                } catch (error) {
                    // mpegts.js がうまく初期化できない場合
                    this.player.plugins.mpegts.destroy();
                }
                this.player = null;
            }

            // イベントソースを閉じる
            if (this.eventsource !== null) {
                this.eventsource.close();
                this.eventsource = null;
            }
        }
    }
});
</script>

<style lang="scss">
// DPlayer のスタイルの上書き
.dplayer svg circle, .dplayer svg path {
    fill: var(--v-text-base) !important;
}
.dplayer-quality-icon, .dplayer-quality-list, .dplayer-time, .dplayer-live-badge {
    color: var(--v-text-base) !important;
}
.dplayer-quality-list {
    border-radius: 4px !important;
    .dplayer-quality-item {
        height: 30px !important;
        line-height: 30px !important;
    }
}
.dplayer-volume-bar {
    background: var(--v-text-base) !important;
}
.dplayer-video-wrap {
    background: transparent !important;
}
.dplayer-video-wrap-aspect {
    transition: opacity 0.3s;
    opacity: 1;
}
.watch-player__background--visible .dplayer-video-wrap-aspect {
    opacity: 0;
}
.dplayer-controller-mask {
    height: 82px !important;
    background: linear-gradient(to bottom, transparent, var(--v-background-base)) !important;
    opacity: 0 !important;
    visibility: hidden;
}
.dplayer-controller {
    padding-left: calc(68px + 18px) !important;
    padding-bottom: 6px !important;
    opacity: 0 !important;
    visibility: hidden;

    .dplayer-icons {
        bottom: auto !important;
    }
}
.dplayer-mobile.dplayer-hide-controller .dplayer-controller {
    transform: none !important;
}
.dplayer-notice {
    padding: 16px 22px !important;
    border-radius: 4px !important;
    font-size: 15px !important;
}
.dplayer-info-panel {
    transition: top 0.3s, left 0.3s;
}
.watch-container {
    // コントロール表示時
    &--control-visible {
        .dplayer-controller-mask, .dplayer-controller {
            opacity: 1 !important;
            visibility: visible !important;
        }
        .dplayer-notice {
            left: calc(68px + 30px);
            bottom: 62px;
        }
        .dplayer-info-panel {
            top: 82px;
            left: calc(68px + 30px);
        }
        .dplayer-mobile .dplayer-mobile-icon-wrap {
            opacity: 0.7 !important;
            visibility: visible !important;
        }
    }
}

// 上書きしたいスタイル
.v-tabs-bar {
    height: 58px;
    background: linear-gradient(to bottom, var(--v-background-base) calc(100% - 3px), var(--v-background-lighten1) 3px);  // 下線を引く

    .v-tabs-slider-wrapper {
        height: 3px !important;
        transition: left 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
    }
}
.channels-container .v-tabs-bar {
    height: 48px;
}
</style>

<style lang="scss" scoped>
.route-container {
    background: var(--v-black-base) !important;
    overflow: hidden;
}
.watch-container {
    display: flex;
    width: calc(100% + 352px);  // パネルの幅分はみ出す
    transition: width 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);

    // コントロール表示時
    &--control-visible {
        .watch-content {
            cursor: auto !important;
        }
        .watch-navigation, .watch-header, .watch-player__button {
            opacity: 1 !important;
            visibility: visible !important;
        }
    }

    // パネル表示時
    &--panel-visible {
        width: calc(100%);  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: var(--v-primary-base);
        }
    }

    .watch-navigation {
        display: flex;
        flex-direction: column;
        position: fixed;
        padding: 22px 8px;
        padding-top: 18px;
        width: 68px;
        top: 0px;
        left: 0px;
        bottom: 0px;
        background: #2F221F80;
        transition: opacity 0.3s, visibility 0.3s;
        opacity: 0;
        visibility: hidden;
        z-index: 2;

        // スマホ・タブレットのブラウザでアドレスバーが完全に引っ込むまでビューポートの高さが更新されず、
        // その間下に何も背景がない部分ができてしまうのを防ぐ
        &:after {
            content: '';
            position: absolute;
            top: 100%;
            left: -8px;
            width: calc(100% + 8px);
            height: 100px;
            background: #2F221F80;
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

            &:hover {
                background: #433532A0;
            }

            &--active {
                color: var(--v-primary-base);
                background: #433532A0;
            }
            + .watch-navigation__link {
                margin-top: 4px;
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

                @include tablet {
                    margin-left: 0;
                }
            }

            .watch-header__program-time {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 15px;

                @include tablet {
                    margin-left: 8px;
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
            height: 100vh;
            background-size: contain;
            background-position: center;

            &.watch-player__background--visible > .watch-player__background {
                opacity: 1;
                visibility: visible;
            }

            .watch-player__background {
                position: absolute;
                top: 50%;
                left: 50%;
                width: 100%;
                max-width: 100%;
                max-height: 100%;
                aspect-ratio: 16 / 9;
                transform: translate(-50%,-50%);
                background-blend-mode: color-burn;
                background-color: rgba(14, 14, 18, 40%);
                background-size: cover;
                background-image: none;
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s, visibility 0.3s;

                .watch-player__background-logo {
                    display: inline-block;
                    position: absolute;
                    height: 34px;
                    right: 56px;
                    bottom: 44px;
                    filter: drop-shadow(0px 0px 4px var(--v-black-base));

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
                right: 20px;
                height: 190px;
                transform: translateY(-50%);
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.3s, visibility 0.3s;

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

                    &:hover {
                        background: #2F221FF0;
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
        height: 100vh;
        background: var(--v-background-base);

        .watch-panel__header {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            width: 100%;
            height: 70px;
            padding-left: 16px;
            padding-right: 16px;

            .panel-close-button {
                display: flex;
                position: relative;
                align-items: center;
                flex-shrink: 0;
                left: -4px;
                height: 35px;
                padding: 0 4px;
                border-radius: 5px;
                user-select: none;
                cursor: pointer;

                &__icon {
                    position: relative;
                    left: -4px;
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
                }

                &__number {
                    flex-shrink: 0;
                    margin-left: 8px;
                    font-size: 16px;
                }

                &__name {
                    margin-left: 5px;
                    font-size: 16px;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
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
                overflow-y: auto;

                &--active {
                    opacity: 1;
                    visibility: visible;
                }

                &.program-container {
                    padding-left: 16px;
                    padding-right: 16px;

                    .program-info {
                        .program-info__title {
                            font-size: 22px;
                            font-weight: bold;
                            line-height: 145%;
                            font-feature-settings: "palt" 1;  // 文字詰め
                            letter-spacing: 0.05em;  // 字間を少し空ける
                        }
                        .program-info__time {
                            margin-top: 8px;
                            color: var(--v-text-darken1);
                            font-size: 14px;
                        }
                        .program-info__description {
                            margin-top: 12px;
                            color: var(--v-text-darken1);
                            font-size: 12px;
                            line-height: 168%;
                            overflow-wrap: break-word;
                            font-feature-settings: "palt" 1;  // 文字詰め
                            letter-spacing: 0.08em;  // 字間を少し空ける
                        }
                        .program-info__genre-container {
                            display: flex;
                            flex-wrap: wrap;
                            margin-top: 10px;

                            .program-info__genre {
                                display: inline-block;
                                font-size: 10.5px;
                                padding: 3px;
                                margin-top: 4px;
                                margin-right: 4px;
                                border-radius: 4px;
                                background: var(--v-background-lighten2);
                            }
                        }
                        .program-info__next {
                            display: flex;
                            align-items: center;
                            margin-top: 18px;
                            color: var(--v-text-darken1);
                            font-size: 14px;
                            font-weight: bold;
                            &-decorate {
                                flex-shrink: 0;
                            }
                            &-icon {
                                flex-shrink: 0;
                                margin-left: 3px;
                                font-size: 15px;
                            }
                        }
                        .program-info__next-title {
                            display: -webkit-box;
                            margin-top: 2px;
                            color: var(--v-text-darken1);
                            font-size: 14px;
                            overflow: hidden;
                            -webkit-line-clamp: 2;  // 2行までに制限
                            -webkit-box-orient: vertical;
                        }
                        .program-info__next-time {
                            margin-top: 3px;
                            color: var(--v-text-darken1);
                            font-size: 12px;
                        }
                        .program-info__status {
                            display: flex;
                            align-items: center;
                            margin-top: 16px;
                            font-size: 15px;
                            color: var(--v-text-darken1);
                        }
                    }

                    .program-detail-container {
                        margin-top: 24px;
                        margin-bottom: 24px;

                        .program-detail {
                            margin-top: 16px;

                            .program-detail__heading {
                                font-size: 18px;
                            }
                            .program-detail__text {
                                margin-top: 8px;
                                color: var(--v-text-darken1);
                                font-size: 12px;
                                line-height: 168%;
                                overflow-wrap: break-word;
                                white-space: pre-wrap;  // \n で改行する
                                font-feature-settings: "palt" 1;  // 文字詰め
                                letter-spacing: 0.08em;  // 字間を少し空ける
                            }
                        }
                    }
                }

                &.channels-container {
                    display: flex;
                    flex-direction: column;

                    .channels-tab {
                        position: sticky;
                        flex: none;
                        top: 0px;
                        padding-left: 16px;
                        padding-right: 16px;
                        padding-bottom: 16px;
                        background:var(--v-background-base);
                        z-index: 1;

                        .channels-tab__item {
                            width: 88px;
                            padding: 0;
                            color: var(--v-text-base) !important;
                            font-size: 15px;
                        }
                    }

                    .channels-list {
                        padding-left: 16px;
                        padding-right: 16px;
                        padding-bottom: 16px;
                        background: transparent !important;
                        overflow: inherit;

                        .channels {
                            display: flex;
                            justify-content: center;
                            flex-direction: column;

                            // 1630px 以上で幅を 445px に固定
                            @media screen and (min-width: 1630px) {
                                & {
                                    grid-template-columns: repeat(auto-fit, 445px);
                                }
                            }

                            .channel {
                                display: flex;
                                flex-direction: column;
                                position: relative;
                                margin-top: 12px;
                                padding: 10px 12px 14px 12px;
                                border-radius: 11px;
                                color: var(--v-text-base);
                                background: var(--v-background-lighten1);
                                transition: background-color 0.15s;
                                overflow: hidden;  // progressbar を切り抜くために必要
                                text-decoration: none;
                                user-select: none;
                                cursor: pointer;

                                &:hover {
                                    background: var(--v-background-lighten2);
                                }
                                &:first-of-type {
                                    margin-top: 0px;
                                }

                                .channel__broadcaster {
                                    display: flex;
                                    height: 28px;

                                    &-icon {
                                        display: inline-block;
                                        flex-shrink: 0;
                                        width: 48px;
                                        height: 100%;
                                        border-radius: 4px;
                                        background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                                        object-fit: cover;
                                    }

                                    &-content {
                                        display: flex;
                                        align-items: center;
                                        margin-left: 12px;
                                        width: 100%;
                                        min-width: 0;
                                    }

                                    &-name {
                                        font-size: 14.5px;
                                        overflow: hidden;
                                        white-space: nowrap;
                                        text-overflow: ellipsis;
                                    }

                                    &-status {
                                        display: flex;
                                        align-items: center;
                                        flex-shrink: 0;
                                        margin-top: 1px;
                                        margin-left: 8px;
                                        font-size: 8px;
                                        color: var(--v-text-darken1);
                                    }
                                }

                                .channel__program-present {
                                    display: flex;
                                    flex-direction: column;

                                    &-title {
                                        display: -webkit-box;
                                        margin-top: 8px;
                                        font-size: 13.5px;
                                        font-weight: 700;
                                        font-feature-settings: "palt" 1;  // 文字詰め
                                        letter-spacing: 0.07em;  // 字間を少し空ける
                                        overflow: hidden;
                                        -webkit-line-clamp: 2;  // 2行までに制限
                                        -webkit-box-orient: vertical;
                                    }

                                    &-time {
                                        margin-top: 4px;
                                        color: var(--v-text-darken1);
                                        font-size: 11.5px;
                                    }
                                }

                                .channel__program-following {
                                    display: flex;
                                    flex-direction: column;
                                    margin-top: 4px;
                                    color: var(--v-text-darken1);
                                    font-size: 11.5px;

                                    &-title {
                                        display: flex;
                                        align-items: center;

                                        &-decorate {
                                                flex-shrink: 0;
                                        }
                                        &-icon {
                                                flex-shrink: 0;
                                                margin-left: 3px;
                                        }
                                        &-text {
                                                margin-left: 2px;
                                                overflow: hidden;
                                                white-space: nowrap;
                                                text-overflow: ellipsis;  // はみ出た部分を … で省略
                                        }
                                    }

                                    &-time {
                                        margin-top: 1px;
                                    }
                                }

                                .channel__progressbar {
                                    position: absolute;
                                    left: 0;
                                    right: 0;
                                    bottom: 0;
                                    height: 4px;
                                    background: var(--v-gray-base);

                                    &-progress {
                                        height: 4px;
                                        background: var(--v-primary-base);
                                        transition: width 0.3s;
                                    }
                                }
                            }
                        }
                    }
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

                &--active {
                    color: var(--v-primary-base);
                }

                &__icon {
                    height: 30px;
                }
                &__text {
                    margin-top: 5px;
                    font-size: 13px;
                }
            }
        }
    }
}
</style>
