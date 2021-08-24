<template>
    <div class="route-container">
        <nav class="watch-navigation">
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/tv/">
                <Icon class="watch-navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/video/">
                <Icon class="watch-navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/schedules/">
                <Icon class="watch-navigation__link-icon" icon="fluent:calendar-ltr-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/captures/">
                <Icon class="watch-navigation__link-icon" icon="fluent:image-multiple-24-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/watchlist/">
                <Icon class="watch-navigation__link-icon" icon="ic:round-playlist-play" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/history/">
                <Icon class="watch-navigation__link-icon" icon="fluent:history-16-regular" width="26px" />
            </router-link>
            <v-spacer></v-spacer>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/settings/">
                <Icon class="watch-navigation__link-icon" icon="fluent:settings-20-regular" width="26px" />
            </router-link>
            <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active" to="/version/">
                <Icon class="watch-navigation__link-icon" icon="fluent:info-16-regular" width="26px" />
            </router-link>
        </nav>
        <main class="watch-container" :class="{'watch-container--panel-display': is_panel_display}">
            <div class="watch-content">
                <header class="watch-header">
                    <img class="watch-header__broadcaster" :src="`${api_base_url}/channels/${($route.params.channel_id)}/logo`">
                    <span class="watch-header__program-title" v-html="decorateProgramInfo(channel.program_present, 'title')"></span>
                    <span class="watch-header__program-time">{{getProgramTime(channel.program_present, true)}}</span>
                    <v-spacer></v-spacer>
                    <span class="watch-header__now">{{time}}</span>
                </header>
                <div class="watch-player">
                    <div class="watch-player__dplayer"></div>
                    <div class="watch-player__button">
                        <div v-ripple class="switch-button switch-button-up">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-left-24-filled" width="31px" rotate="1" />
                        </div>
                        <div v-ripple class="switch-button switch-button-panel switch-button-panel--open"
                            @click="is_panel_display = !is_panel_display">
                            <Icon class="switch-button-icon" icon="fluent:navigation-16-filled" width="31px" />
                        </div>
                        <div v-ripple class="switch-button switch-button-down">
                            <Icon class="switch-button-icon" icon="fluent:ios-arrow-right-24-filled" width="31px" rotate="1" />
                        </div>
                    </div>
                </div>
            </div>
            <div class="watch-panel">
                <div class="watch-panel__header">
                    <div v-ripple class="panel-close-button" @click="is_panel_display = false">
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
                <div class="watch-panel__content">
                    <section class="program-info">
                        <h1 class="program-info__title" v-html="decorateProgramInfo(channel.program_present, 'title')"></h1>
                        <div class="program-info__time">{{getProgramTime(channel.program_present)}}</div>
                        <div class="program-info__description" v-html="decorateProgramInfo(channel.program_present, 'description')"></div>
                        <div class="program-info__next-title">
                            <span class="program-info__next-title-decorate">NEXT</span>
                            <Icon class="program-info__next-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                        </div>
                        <span class="program-info__next-title-text" v-html="decorateProgramInfo(channel.program_following, 'title')"></span>
                        <div class="program-info__next-time">{{getProgramTime(channel.program_following)}}</div>
                        <div class="program-info__status">
                            <Icon icon="fa-solid:eye" height="14px" />
                            <span class="ml-2">{{channel.watching}}</span>
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
                <div class="watch-panel__navigation">
                    <div v-ripple class="panel-navigation-button panel-navigation-button--active">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                        <span class="panel-navigation-button__text">番組情報</span>
                    </div>
                    <div v-ripple class="panel-navigation-button">
                        <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                        <span class="panel-navigation-button__text">チャンネル</span>
                    </div>
                    <div v-ripple class="panel-navigation-button">
                        <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="31px" />
                        <span class="panel-navigation-button__text">コメント</span>
                    </div>
                    <div v-ripple class="panel-navigation-button">
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
// @ts-ignore  JS 製なので型定義がないし、作ろうとするとまためんどいので黙殺
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

            // 現在時刻
            time: dayjs().format('YYYY/MM/DD HH:mm:ss'),

            // パネルが表示されているか
            // 既定で表示する
            is_panel_display: true,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [],

            // チャンネル ID
            channel_id: this.$route.params.channel_id,

            // チャンネル情報
            // 情報取得が完了するまでの間表示される初期値を定義
            channel: {
                "id": "NID0-SID0",
                "service_id": 0,
                "network_id": 0,
                "remocon_id": 0,
                "channel_id": "gr000",
                "channel_number": "---",
                "channel_name": "取得中…",
                "channel_type": "GR",
                "channel_force": 0,
                "channel_comment": 0,
                "is_subchannel": false,
                "is_display": true,
                "watching": 0,
                "program_present": {
                    "id": "NID0-SID0-EID0",
                    "channel_id": "gr000",
                    "title": "取得中…",
                    "description": "取得中…",
                    "detail": {},
                    "start_time": "2000-01-01T00:00:00+09:00",
                    "end_time": "2000-01-01T00:00:00+09:00",
                    "duration": 0,
                    "is_free": true,
                    "genre": [],
                    "video_type": "",
                    "video_codec": "",
                    "video_resolution": "",
                    "audio_type": "",
                    "audio_sampling_rate": "",
                },
                "program_following": {
                    "id": "NID0-SID0-EID0",
                    "channel_id": "gr000",
                    "title": "取得中…",
                    "description": "取得中…",
                    "detail": {},
                    "start_time": "2000-01-01T00:00:00+09:00",
                    "end_time": "2000-01-01T00:00:00+09:00",
                    "duration": 0,
                    "is_free": true,
                    "genre": [],
                    "video_type": "",
                    "video_codec": "",
                    "video_resolution": "",
                    "audio_type": "",
                    "audio_sampling_rate": "",
                }
            },

            // チャンネル情報リスト
            channels_list: null,

            // プレイヤー (DPlayer) のインスタンス
            player: null,

            // イベントソースのインスタンス
            eventsource: null,
        }
    },
    // 開始時に実行
    created() {

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
    // 終了前に実行
    beforeDestroy() {

        // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
        // clearInterval() と clearTimeout() は中身共通なので問題ない
        for (const interval_id in this.interval_ids) {
            clearInterval(parseInt(interval_id));  // 型推論がうまく効かないのでこうなる…つらい
        }

        // プレイヤーを破棄する
        this.player.destroy();

        // イベントソースを閉じる
        this.eventsource.close();
    },
    methods: {

        // チャンネル情報一覧を取得し、画面を更新する
        update() {

            // チャンネル ID が未定義なら実行しない（フェイルセーフ）
            if (this.$route.params.channel_id === undefined) {
                return;
            }

            // チャンネル情報 API にアクセス
            Vue.axios.get(`${this.api_base_url}/channels/${this.$route.params.channel_id}`).then((response) => {

                // チャンネル情報を代入
                this.channel = response.data;

                // まだ初期化されていなければ、プレイヤーを初期化
                if (this.player === null) {
                    this.initPlayer();
                }

                // チャンネル情報一覧 API にアクセス
                // チャンネル情報 API と同時にアクセスするとむしろレスポンスが遅くなるので、返ってくるのを待ってから実行
                Vue.axios.get(`${this.api_base_url}/channels`).then((response) => {

                    // is_display が true のチャンネルのみに絞り込むフィルタ関数
                    // 放送していないサブチャンネルを表示から除外する
                    function filter(channel: any) {
                        return channel.is_display;
                    }

                    // チャンネルリストを再構築
                    // 1つでもチャンネルが存在するチャンネルタイプのみ表示するように
                    // たとえば SKY (スカパー！プレミアムサービス) のタブは SKY に属すチャンネルが1つもない（=受信できない）なら表示されない
                    this.channels_list = {};
                    if (response.data.GR.length > 0) this.channels_list['地デジ'] = response.data.GR.filter(filter);
                    if (response.data.BS.length > 0) this.channels_list['BS'] = response.data.BS.filter(filter);
                    if (response.data.CS.length > 0) this.channels_list['CS'] = response.data.CS.filter(filter);
                    if (response.data.SKY.length > 0) this.channels_list['SKY'] = response.data.SKY.filter(filter);
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
                    url: `${this.api_base_url}/streams/live/${this.channel_id}/${this.preferred_quality}/mpegts`,
                    type: 'mpegts',
                },
                // コメント設定
                // danmaku: {
                //     id: 'Konomi',
                //     user: 'Konomi',
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

            // イベントハンドラーを初期化
            this.initEventHandler();
        },

        // イベントハンドラーを初期化する
        initEventHandler() {

            // EventSource を作成
            this.eventsource = new EventSource(`${this.api_base_url}/streams/live/${this.channel_id}/${this.preferred_quality}/events`);

            // ステータスが更新されたとき
            this.eventsource.addEventListener('status_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data.replace(/'/g, '"'));
                console.log(event);

                // クライアント数を更新
                this.channel.watching = event.clients_count;

                // ステータスごとに処理を振り分け
                switch (event.status) {

                    // Status: Standby
                    case 'Standby': {

                        // ステータス詳細をプレイヤーに表示
                        this.player.notice(event.detail);

                        break;
                    }

                    // Status: Restart
                    case 'Restart': {

                        // ステータス詳細をプレイヤーに表示
                        this.player.notice(event.detail);

                        // プレイヤーを再起動する
                        this.player.switchVideo({
                            url: `${this.api_base_url}/streams/live/${this.channel_id}/${this.preferred_quality}/mpegts`,
                            type: 'mpegts',
                        });

                        // 再起動しただけでは自動再生されないので、明示的に
                        this.player.play();

                        break;
                    }

                    // Status: Offline
                    case 'Offline': {

                        // ステータス詳細をプレイヤーに表示
                        this.player.notice(event.detail);

                        // イベントソースを閉じる（復帰の見込みがないため）
                        this.eventsource.close();

                        break;
                    }
                }
            });

            // ステータス詳細が更新されたとき
            this.eventsource.addEventListener('detail_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data.replace(/'/g, '"'));
                console.log(event);

                // クライアント数を更新
                this.channel.watching = event.clients_count;

                // Standby のときだけプレイヤーに表示
                if (event.status === 'Standby') {
                    this.player.notice(event.detail);
                }
            });

            // クライアント数が更新されたとき
            this.eventsource.addEventListener('clients_update', (event_raw: MessageEvent) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data.replace(/'/g, '"'));
                console.log(event);

                // クライアント数を更新
                this.channel.watching = event.clients_count;
            });
        }
    }
});
</script>

<style lang="scss">
// DPlayer のスタイル上書き
.dplayer-controller {
    padding-left: calc(68px + 14px);
    padding-bottom: 6px;

    .dplayer-icons {
        bottom: auto;
    }

    .dplayer-controller-mask {
        height: 82px;
        background: linear-gradient(to bottom, transparent, var(--v-background-base));
    }
}
.dplayer-notice {
    left: calc(68px + 30px);
}
.dplayer-info-panel {
    top: 82px;
    left: calc(68px + 30px);
}
</style>

<style lang="scss" scoped>
.route-container {
    background: #000000 !important;
}
.watch-navigation {
    display: flex;
    flex-direction: column;
    position: fixed;
    padding: 22px 8px;
    padding-top: 87px;
    width: 68px;
    top: 0px;
    left: 0px;
    bottom: 0px;
    background: #2F221F80;
    z-index: 1;

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

.watch-container {
    display: flex;
    width: calc(100% + 352px);  // パネルの幅分はみ出す
    transition: width 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);

    // パネル表示時
    &--panel-display {
        width: calc(100%);  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: var(--v-primary-base);
        }
    }

    .watch-content {
        display: flex;
        position: relative;
        width: 100%;

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
            z-index: 2;

            .watch-header__broadcaster {
                display: inline-block;
                flex-shrink: 0;
                width: 64px;
                height: 36px;
                border-radius: 5px;
                background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                object-fit: cover;
                user-select: none;
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
            }

            .watch-header__program-time {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 15px;
            }

            .watch-header__now {
                flex-shrink: 0;
                margin-left: 16px;
                font-size: 13px;
            }
        }

        .watch-player {
            display: flex;
            position: relative;
            width: 100%;
            height: 100vh;
            background-size: contain;
            background-position: center;

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

                .switch-button {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    width: 48px;
                    height: 48px;
                    background: #2F221FC0;
                    border-radius: 7px;
                    user-select: none;
                    cursor: pointer;

                    .switch-button-icon {
                        position: relative;
                    }

                    &-up > .switch-button-icon {
                        top: 6px;
                        left: 1px;
                    }
                    &-panel > .switch-button-icon {
                        top: 1.5px;
                        transition: color 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);
                    }
                    &-down > .switch-button-icon {
                        bottom: 4px;
                        left: 1px;
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

        .watch-panel__content {
            height: 100%;
            padding-left: 16px;
            padding-right: calc(16px - 10px);  // スクロールバーの幅を引く
            overflow-y: scroll;

            .program-info {
                .program-info__title {
                    font-size: 22px;
                    font-weight: bold;
                    line-height: 140%;
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
                    line-height: 165%;
                    overflow-wrap: break-word;
                    font-feature-settings: "palt" 1;  // 文字詰め
                    letter-spacing: 0.07em;  // 字間を少し空ける
                }
                .program-info__next-title {
                    display: flex;
                    align-items: center;
                    margin-top: 16px;
                    color: var(--v-text-darken1);
                    font-size: 14px;
                    &-decorate {
                        flex-shrink: 0;
                    }
                    &-icon {
                        flex-shrink: 0;
                        margin-left: 3px;
                        font-size: 15px;
                    }
                    &-text {
                        display: -webkit-box;
                        margin-top: 2px;
                        color: var(--v-text-darken1);
                        font-size: 14px;
                        overflow: hidden;
                        -webkit-line-clamp: 2;  // 2行までに制限
                        -webkit-box-orient: vertical;
                    }
                }
                .program-info__next-time {
                    margin-top: 4px;
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
                        line-height: 165%;
                        overflow-wrap: break-word;
                        white-space: pre-wrap;  // \n で改行する
                        font-feature-settings: "palt" 1;  // 文字詰め
                        letter-spacing: 0.07em;  // 字間を少し空ける
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
                padding: 6px 4px;
                border-radius: 5px;
                color: var(--v-text-base);
                box-sizing: content-box;
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
