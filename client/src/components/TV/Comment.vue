<template>
    <div class="comment-container">
        <section class="comment-header">
            <h2 class="comment-header__title">
                <Icon class="comment-header__title-icon" icon="bi:chat-left-text-fill" height="18.5px" />
                <span class="comment-header__title-text">コメント</span>
            </h2>
            <button v-ripple class="comment-header__button ml-auto">
                <Icon icon="heroicons-solid:filter" height="11px" />
                <span class="ml-1">コメントフィルター</span>
            </button>
        </section>
        <DynamicScroller class="comment-list" :direction="'vertical'" :items="comment_list" :min-item-size="34">
            <template v-slot="{item, active}">
            <DynamicScrollerItem :item="item" :active="active"  :size-dependencies="[item.text]">
                <div class="comment">
                    <span class="comment__text">{{item.text}}</span>
                    <span class="comment__time">{{item.time}}</span>
                </div>
            </DynamicScrollerItem>
            </template>
        </DynamicScroller>
    </div>
</template>
<script lang="ts">

import { AxiosResponse } from 'axios';
import dayjs from 'dayjs';
import Vue, { PropType } from 'vue';

import { IChannel } from '@/interface';
import Mixin from '@/views/TV/Mixin.vue';

export default Mixin.extend({
    name: 'Comment',
    props: {
        // チャンネル情報
        channel_props: {
            type: Object as PropType<IChannel>,
            required: true,
        },
        // プレイヤーのインスタンス
        player: {
            type: null as PropType<any>,  // 代入当初は null になるため苦肉の策
            required: true,
        }
    },
    data() {
        return {

            // コメントリストの配列
            comment_list: [] as {[key: string]: number | string}[],

            // 視聴セッションの WebSocket のインスタンス
            watch_session: null as WebSocket | null,

            // コメントセッションの WebSocket のインスタンス
            comment_session: null as WebSocket | null,

            // 座席維持用のタイマーのインターバル ID
            keep_seat_interval_id: 0,

            // ResizeObserver のインスタンス
            resize_observer: null as ResizeObserver | null,

            // ResizeObserver の監視対象の要素
            resize_observer_element: null as Element | null,
        }
    },
    // 終了前に実行
    beforeDestroy() {

        // destroy() を実行
        this.destroy();

        // ResizeObserver を終了
        this.resize_observer.unobserve(this.resize_observer_element);
    },
    watch: {

        // チャンネル情報が変更されたとき
        // created() だとチャンネル情報の取得前に実行してしまう
        // this が変わってしまうのでアロー関数は使えない
        async channel_props(new_channel:IChannel, old_channel:IChannel) {

            // 前のチャンネル情報と次のチャンネル情報で channel_id が変わってたら
            if (new_channel.channel_id !== old_channel.channel_id) {

                // 0.5秒だけ待ってから
                // 連続してチャンネルを切り替えた時などに毎回コメントサーバーに接続しないように猶予を設ける
                // ただし、最初 (channel_id が gr000 の初期値になっている) だけは待たずに実行する
                if (old_channel.channel_id !== 'gr000') {
                    await new Promise(resolve => setTimeout(resolve, 0.5 * 1000));
                    // 0.5 秒待った結果、channel_id が既に変更されているので終了
                    if (this.channel_props.channel_id !== new_channel.channel_id) {
                        return;
                    }
                }

                // 前の視聴セッション・コメントセッションを破棄
                this.destroy();

                // 視聴セッションを初期化
                const comment_session_info = await this.initWatchSession();

                // コメントセッションを初期化
                await this.initCommentSession(comment_session_info);

                // リサイズ時のイベントを初期化
                await this.initReserveObserver();
            }
        }
    },
    methods: {

        // 視聴セッションを初期化
        async initWatchSession(): Promise<{[key: string]: string | null}> {

            // セッション情報を取得
            let watch_session_info: AxiosResponse;
            try {
                watch_session_info = await Vue.axios.get(`${this.api_base_url}/channels/${this.channel_props.channel_id}/jikkyo`);
            } catch (error) {
                throw new Error(error);  // エラー内容を表示
            }

            // セッション情報を取得できなかった
            if (watch_session_info.data.is_success === false) {
                throw new Error(watch_session_info.data.detail);  // エラー内容を表示
            }

            // イベント内で値を返すため、Promise で包む
            return new Promise((resolve) => {

                // 視聴セッション WebSocket を開く
                this.watch_session = new WebSocket(watch_session_info.data.audience_token);

                // 視聴セッション WebSocket を開いたとき
                this.watch_session.addEventListener('open', () => {

                    // 視聴セッションをリクエスト
                    // 某所で限定公開されている公式ドキュメントいわく、stream フィールドは Optional らしい
                    // サーバー負荷軽減のため、映像が不要な場合は必ず省略してくださいとのこと
                    this.watch_session.send(JSON.stringify({
                        'type': 'startWatching',
                        'data': {
                            'reconnect': false,
                        },
                    }));
                });

                // 視聴セッション WebSocket からメッセージを受信したとき
                this.watch_session.addEventListener('message', async (event) => {

                    // 受信したメッセージ
                    const message = JSON.parse(event.data);

                    switch (message.type) {

                        // 部屋情報（実際には統合されていて、全てアリーナ扱いになっている）
                        case 'room': {

                            // コメントサーバーへの接続情報の入ったオブジェクトを返す
                            // デバッグ用で実際には使わないものもある
                            return resolve({
                                // コメントサーバーへの接続情報
                                'thread_id': message.data.threadId,
                                'your_post_key': (message.data.yourPostKey ? message.data.yourPostKey : null),
                                'message_server': message.data.messageServer.uri,
                            });
                        }

                        // 座席情報
                        case 'seat': {

                            // keepIntervalSec の秒数ごとに keepSeat を送信して座席を維持する
                            this.keep_seat_interval_id = window.setInterval(() => {
                                // セッションがまだ開いていれば
                                if (this.watch_session.readyState === 1) {
                                    // 座席を維持
                                    this.watch_session.send(JSON.stringify({
                                        'type': 'keepSeat',
                                    }));
                                // setInterval を解除
                                } else {
                                    window.clearInterval(this.keep_seat_interval_id);
                                }
                            }, message.data.keepIntervalSec * 1000);
                            break;
                        }

                        // ping-pong
                        case 'ping': {

                            // pong を返してセッションを維持する
                            // 送り返さなかった場合勝手にセッションが閉じられてしまう
                            this.watch_session.send(JSON.stringify({
                                'type': 'pong',
                            }));
                            break;
                        }

                        // エラー情報
                        case 'error': {

                            // エラー情報
                            let error:string;
                            switch (message.data.code) {

                                case 'CONNECT_ERROR':
                                    error = 'コメントサーバーに接続できません。';
                                break;
                                case 'CONTENT_NOT_READY':
                                    error = 'ニコニコ実況が配信できない状態です。';
                                break;
                                case 'NO_THREAD_AVAILABLE':
                                    error = 'コメントスレッドを取得できません。';
                                break;
                                case 'NO_ROOM_AVAILABLE':
                                    error = 'コメント部屋を取得できません。';
                                break;
                                case 'NO_PERMISSION':
                                    error = 'API にアクセスする権限がありません。';
                                break;
                                case 'NOT_ON_AIR':
                                    error = 'ニコニコ実況が放送中ではありません。';
                                break;
                                case 'BROADCAST_NOT_FOUND':
                                    error = 'ニコニコ実況の配信情報を取得できません。';
                                break;
                                case 'INTERNAL_SERVERERROR':
                                    error = 'ニコニコ実況でサーバーエラーが発生しています。';
                                break;
                                default:
                                    error = `ニコニコ実況でエラーが発生しています。(${message.data.code})`;
                                break;
                            }

                            // エラー情報を表示
                            console.log(`error occurred. code: ${message.data.code}`);
                            if (this.player.danmaku.showing) {
                                this.player.notice(error);
                            }

                            break;
                        }

                        // 再接続を求められた
                        case 'reconnect': {

                            // 前の視聴セッション・コメントセッションを破棄
                            this.destroy();

                            // waitTimeSec に記載の秒数だけ待ってから再接続する
                            await new Promise(resolve => setTimeout(resolve, message.data.waitTimeSec * 1000));
                            if (this.player.danmaku.showing) {
                                this.player.notice('ニコニコ実況に再接続しています…');
                            }

                            // 視聴セッションを再初期化
                            // ドキュメントには reconnect で送られてくる audienceToken で再接続しろと書いてあるんだけど、
                            // 確実性的な面で実装が面倒なので当面このままにしておく
                            const comment_session_info = await this.initWatchSession();

                            // コメントセッションを再初期化
                            await this.initCommentSession(comment_session_info);

                            break;
                        }

                        // 視聴セッションが閉じられた（4時のリセットなど）
                        case 'disconnect': {

                            // 実際に接続が閉じられる前に disconnect イベントが送られてきたので、onclose イベントを削除する
                            // onclose イベントが発火するのは不意に切断されたときなど最終手段
                            if (this.watch_session) this.watch_session.onclose = null;

                            // 接続切断の理由
                            let disconnect_reason;
                            switch (message.data.reason) {

                                case 'TAKEOVER':
                                    disconnect_reason = 'ニコニコ実況の番組から追い出されました。';
                                break;
                                case 'NO_PERMISSION':
                                    disconnect_reason = 'ニコニコ実況の番組の座席を取得できませんでした。';
                                break;
                                case 'END_PROGRAM':
                                    disconnect_reason = 'ニコニコ実況がリセットされたか、コミュニティの番組が終了しました。';
                                break;
                                case 'PING_TIMEOUT':
                                    disconnect_reason = 'コメントサーバーとの接続生存確認に失敗しました。';
                                break;
                                case 'TOO_MANY_CONNECTIONS':
                                    disconnect_reason = 'ニコニコ実況の同一ユーザからの接続数上限を越えています。';
                                break;
                                case 'TOO_MANY_WATCHINGS':
                                    disconnect_reason = 'ニコニコ実況の同一ユーザからの視聴番組数上限を越えています。';
                                break;
                                case 'CROWDED':
                                    disconnect_reason = 'ニコニコ実況の番組が満席です。';
                                break;
                                case 'MAINTENANCE_IN':
                                    disconnect_reason = 'ニコニコ実況はメンテナンス中です。';
                                break;
                                case 'SERVICE_TEMPORARILY_UNAVAILABLE':
                                    disconnect_reason = 'ニコニコ実況で一時的にサーバーエラーが発生しています。';
                                break;
                                default:
                                    disconnect_reason = `ニコニコ実況との接続が切断されました。(${message.data.reason})`;
                                break;
                            }

                            // 接続切断の理由を表示
                            console.log(`disconnected. reason: ${message.data.reason}`);
                            if (this.player.danmaku.showing) {
                                this.player.notice(disconnect_reason);
                            }

                            // 前の視聴セッション・コメントセッションを破棄
                            this.destroy();

                            // 5 秒ほど待ってから再接続する
                            await new Promise(resolve => setTimeout(resolve, 5 * 1000));
                            if (this.player.danmaku.showing) {
                                this.player.notice('ニコニコ実況に再接続しています…');
                            }

                            // 視聴セッションを再初期化
                            const comment_session_info = await this.initWatchSession();

                            // コメントセッションを再初期化
                            await this.initCommentSession(comment_session_info);

                            break;
                        }
                    }
                });


                // 視聴セッションの接続が閉じられたとき（ネットワークが切断された場合など）
                // イベントを無効化しやすいように敢えて onclose で実装する
                this.watch_session.onclose = async (event) => {

                    // 接続切断の理由を表示
                    console.log(`disconnected. code: ${event.code}`);
                    if (this.player.danmaku.showing) {
                        this.player.notice(`ニコニコ実況との接続が切断されました。(code: ${event.code})`);
                    }

                    // 前の視聴セッション・コメントセッションを破棄
                    this.destroy();

                    // 10 秒ほど待ってから再接続する
                    // ニコ生側から切断された場合と異なりネットワークが切断された可能性が高いので、間を多めに取る
                    await new Promise(resolve => setTimeout(resolve, 10 * 1000));
                    if (this.player.danmaku.showing) {
                        this.player.notice('ニコニコ実況に再接続しています…');
                    }

                    // 視聴セッションを再初期化
                    const comment_session_info = await this.initWatchSession();

                    // コメントセッションを再初期化
                    await this.initCommentSession(comment_session_info);
                };
            });
        },

        // コメントセッションを初期化
        async initCommentSession(comment_session_info: {[key: string]: string | null}) {

            // コメントリストの要素
            const comment_list_element = document.querySelector('.comment-list');

            // 最初に送信されてくるコメントを受信し終えたかどうかのフラグ
            let is_received_initial_comment = false;

            // コメントセッション WebSocket を開く
            this.comment_session = new WebSocket(comment_session_info.message_server);

            // コメントセッション WebSocket を開いたとき
            this.comment_session.addEventListener('open', () => {

                // コメント送信をリクエスト
                // このコマンドを送らないとコメントが送信されてこない
                this.comment_session.send(JSON.stringify([
                    { 'ping': {'content': 'rs:0'} },
                    { 'ping': {'content': 'ps:0'} },
                    {
                        'thread': {
                            'version': '20061206',  // 設定必須
                            'thread': comment_session_info.thread_id,  // スレッド ID
                            'threadkey': comment_session_info.your_post_key,  // スレッドキー
                            'user_id': '',  // ユーザー ID
                            'res_from': -50,  // 最初にコメントを 50 個送信する
                        }
                    },
                    { 'ping': {'content': 'pf:0'} },
                    { 'ping': {'content': 'rf:0'} },
                ]));
            });

            // 視聴セッション WebSocket からメッセージを受信したとき
            this.comment_session.addEventListener('message', async (event_raw) => {

                // イベントを取得
                const event = JSON.parse(event_raw.data);

                // thread メッセージのみ
                if (event.thread !== undefined) {

                    // 接続成功のコールバックを DPlayer に通知
                    if (event.thread.resultcode === 0) {

                    // 接続失敗のコールバックを DPlayer に通知
                    } else {
                        const message = 'コメントサーバーに接続できませんでした。';
                        console.error('Error: ' + message);
                    }
                }

                // ping メッセージのみ
                // rf:0 が送られてきたら初回コメントの受信は完了
                if (event.ping !== undefined && event.ping.content === 'rf:0') {

                    // フラグを立てる
                    is_received_initial_comment = true;

                    // 0.01 秒待った上でさらに2回実行しないと完全に最下部までスクロールされない…（ブラウザの描画バグ？）
                    // this.$nextTick() は効かなかった
                    for (let index = 0; index < 3; index++) {
                        await new Promise(resolve => setTimeout(resolve, 0.01 * 1000));
                        comment_list_element.scrollTop = comment_list_element.scrollHeight;
                    }
                }

                // コメントを取得
                const comment = event.chat;

                // コメントがない or 広告用など特殊な場合は弾く
                if (comment === undefined ||
                    comment.content === undefined ||
                    comment.content.match(/\/[a-z]+ /)) {
                    return;
                }

                // 自分のコメントも表示しない
                if (comment.yourpost && comment.yourpost === 1) {
                    return;
                }

                // 色・位置
                let color = '#FFEAEA';  // 色のデフォルト
                let position = 'right';  // 位置のデフォルト
                if (comment.mail !== undefined && comment.mail !== null) {
                    // コマンドをスペースで区切って配列にしたもの
                    const command = comment.mail.replace('184', '').split(' ');
                    for (const item of command) {  // コマンドごとに
                        if (this.getCommentColor(item) !== null) {
                            color = this.getCommentColor(item);
                        }
                        if (this.getCommentPosition(item) !== null) {
                            position = this.getCommentPosition(item);
                        }
                    }
                }

                // 配信に発生する遅延分待ってから
                // 現状だいたい1秒くらいなので暫定で決め打ち
                // 最初に受信したコメントはリアルタイムなコメントではないため、遅らせないように
                if (is_received_initial_comment) {
                    await new Promise(resolve => setTimeout(resolve, 1 * 1000));
                }

                // コメントリストのコメントが 500 件を超えたら古いものから順に削除する
                // 仮想スクロールとはいえ、さすがに 500 件を超えると重くなりそう
                if (this.comment_list.length > 500) {
                    this.comment_list.shift();
                }

                // コメントリストに追加
                // コメント投稿時刻はフォーマットしてから
                this.comment_list.push({
                    id: comment.no,
                    text: comment.content,
                    time: dayjs(comment.date * 1000).format('HH:mm:ss'),
                });

                // コメントリストのスクロールを最下部に固定
                // 最初に受信したコメントは上の処理で一括でスクロールさせる
                if (is_received_initial_comment) {
                    // 0.01 秒待った上でさらに3回実行しないと完全に最下部までスクロールされない…（ブラウザの描画バグ？）
                    // this.$nextTick() は効かなかった
                    for (let index = 0; index < 3; index++) {
                        await new Promise(resolve => setTimeout(resolve, 0.01 * 1000));
                        comment_list_element.scrollTop = comment_list_element.scrollHeight;
                    }
                }

                // コメント描画 (再生時のみ)
                // 最初に受信したコメントはリアルタイムなコメントではないため、描画しないように
                if (is_received_initial_comment) {
                    if (!this.player.video.paused){
                        this.player.danmaku.draw({
                            text: comment.content,
                            color: color,
                            type: position,
                        });
                    }
                }
            });
        },

        // リサイズ時のイベントを初期化
        async initReserveObserver() {

            // 監視対象の要素
            this.resize_observer_element = document.querySelector('.watch-player');

            // タイムアウト ID
            // 一時的に無効にした transition を有効化する際に利用する
            let animation_timeout_id = null;

            // プレイヤーの要素がリサイズされた際に発火するイベント
            const on_resize = () => {

                // 映像の要素
                const video_element = document.querySelector('.dplayer-video-wrap-aspect');

                // コメント描画領域の要素
                const comment_area_element = (document.querySelector('.dplayer-danmaku') as HTMLElement);

                // プレイヤー全体と映像の高さの差（レターボックス）から、コメント描画領域の高さを狭める必要があるかを判定する
                // 2で割っているのは単体の差を測るため
                const letter_box_height = (this.resize_observer_element.clientHeight - video_element.clientHeight) / 2;

                // 70px or 54px (高さが 450px 以下) 以下ならヘッダー（番組名などの表示）と被るので対応する
                const threshold = window.matchMedia('(max-height: 450px)').matches ? 50 : 66;
                if (letter_box_height < threshold) {

                    // コメント描画領域に必要な上下マージン
                    const comment_area_vertical_margin = (threshold - letter_box_height) * 2;

                    // 狭めるコメント描画領域の幅
                    // 映像の要素の幅をそのまま利用する
                    const comment_area_width = video_element.clientWidth;

                    // 狭めるコメント描画領域の高さ
                    const comment_area_height = video_element.clientHeight - comment_area_vertical_margin;

                    // 狭めるコメント描画領域のアスペクト比を求める
                    // https://tech.arc-one.jp/asepct-ratio/
                    const gcd = (x: number, y: number) => {  // 最大公約数を求める関数
                        if(y === 0) return x;
                        return gcd(y, x % y);
                    }
                    // 幅と高さの最大公約数を求める
                    const gcd_result = gcd(comment_area_width, comment_area_height);
                    // 幅と高さをそれぞれ最大公約数で割ってアスペクト比を算出
                    const comment_area_height_aspect = `${comment_area_width / gcd_result} / ${comment_area_height / gcd_result}`;

                    // 一時的に transition を無効化する
                    // アスペクト比の設定は連続して行われるが、その際に transition が適用されるとワンテンポ遅れたアニメーションになってしまう
                    comment_area_element.style.transition = 'none';

                    // コメント描画領域に算出したアスペクト比を設定する
                    comment_area_element.style.setProperty('--comment-area-aspect-ratio', comment_area_height_aspect);

                    // コメント描画領域に必要な上下マージンを設定する
                    comment_area_element.style.setProperty('--comment-area-vertical-margin', `${comment_area_vertical_margin}px`);

                    // 以前セットされた setTimeout() を止める
                    window.clearTimeout(animation_timeout_id);

                    // 0.2秒後に実行する
                    // 0.2秒より前にもう一度リサイズイベントが来た場合はタイマーがクリアされるため実行されない
                    window.setTimeout(() => {

                        // 再び transition を有効化する
                        comment_area_element.style.transition = '';

                    }, 0.2 * 1000);

                } else {

                    // コメント描画領域に設定したアスペクト比・上下マージンを削除する
                    comment_area_element.style.removeProperty('--comment-area-aspect-ratio');
                    comment_area_element.style.removeProperty('--comment-area-vertical-margin');
                }
            }

            // 要素の監視を開始
            this.resize_observer = new ResizeObserver(on_resize);
            this.resize_observer.observe(this.resize_observer_element);
        },

        /**
         * ニコニコの色指定を 16 進数カラーコードに置換する
         * @param {string} color ニコニコの色指定
         * @return {string} 16 進数カラーコード
         */
        getCommentColor(color: string): string {
            const color_table = {
                'red': '#E54256',
                'pink': '#FF8080',
                'orange': '#FFC000',
                'yellow': '#FFE133',
                'green': '#64DD17',
                'cyan': '#39CCFF',
                'blue': '#0000FF',
                'purple': '#D500F9',
                'black': '#1E1310',
                'white': '#FFEAEA',
                'white2': '#CCCC99',
                'niconicowhite': '#CCCC99',
                'red2': '#CC0033',
                'truered': '#CC0033',
                'pink2': '#FF33CC',
                'orange2': '#FF6600',
                'passionorange': '#FF6600',
                'yellow2': '#999900',
                'madyellow': '#999900',
                'green2': '#00CC66',
                'elementalgreen': '#00CC66',
                'cyan2': '#00CCCC',
                'blue2': '#3399FF',
                'marineblue': '#3399FF',
                'purple2': '#6633CC',
                'nobleviolet': '#6633CC',
                'black2': '#666666',
            };
            if (color_table[color] !== undefined) {
                return color_table[color];
            } else {
                return null;
            }
        },

        /**
         * ニコニコの位置指定を DPlayer の位置指定に置換する
         * @param {string} position ニコニコの位置指定
         * @return {string} DPlayer の位置指定
         */
        getCommentPosition(position: string): string {
            switch (position) {
                case 'ue':
                    return 'top';
                case 'naka':
                    return 'right';
                case 'shita':
                    return 'bottom';
                default:
                    return null;
            }
        },

        // 破棄する
        destroy() {

            // コメントリストをクリア
            this.comment_list = [];

            // 視聴セッションを閉じる
            if (this.watch_session !== null) {
                this.watch_session.onclose = null;  // WebSocket が閉じられた際のイベントを削除
                this.watch_session.close();  // WebSocket を閉じる
                this.watch_session = null;  // null に戻す
            }

            // コメントセッションを閉じる
            if (this.comment_session !== null) {
                this.comment_session.onclose = null;  // WebSocket が閉じられた際のイベントを削除
                this.comment_session.close();  // WebSocket を閉じる
                this.comment_session = null;  // null に戻す
            }

            // 座席保持用のタイマーをクリア
            window.clearInterval(this.keep_seat_interval_id);
        }
    }
});

</script>
<style lang="scss" scoped>

.comment-container {
    display: flex;
    flex-direction: column;

    .comment-header {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        width: 100%;
        height: 26px;
        padding-left: 16px;
        padding-right: 16px;
        @media screen and (max-height: 450px) {
            margin-top: 12px;
        }

        &__title {
            display: flex;
            align-items: center;
            font-size: 18.5px;
            font-weight: bold;
            line-height: 145%;
            @media screen and (max-height: 450px) {
                font-size: 16.5px;
            }

            &-icon {
                margin-bottom: -3px;  // 高さ調整
                @media screen and (max-height: 450px) {
                    height: 17.5px;
                }
            }
            &-text {
                margin-left: 12px;
            }
        }

        &__button {
            display: flex;
            align-items: center;
            height: 26px;
            padding: 0 9px;
            border-radius: 4px;
            background: var(--v-background-lighten3);
            font-size: 11px;
            line-height: 1.8;
            letter-spacing: 0;
        }
    }

    .comment-list {
        width: 100%;
        height: 100%;
        margin-top: 16px;
        padding-left: 16px;
        padding-right: 10px;
        padding-bottom: 12px;
        overflow-y: scroll !important;
        @media screen and (max-height: 450px) {
            margin-top: 12px;
        }

        .comment {
            display: flex;
            align-items: center;
            min-height: 28px;
            padding-top: 6px;
            word-break: break-all;

            &__text {
                font-size: 13px;
            }

            &__time {
                flex-shrink: 0;
                margin-left: auto;
                padding-left: 8px;
                color: var(--v-text-darken1);
                font-size: 13px;
            }
        }
    }
}

</style>