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
        <div v-ripple class="comment-scroll-button elevation-5" @click="is_manual_scroll = false; scrollCommentList(true);"
             :class="{'comment-scroll-button--display': is_manual_scroll}">
            <Icon icon="fluent:arrow-down-12-filled" height="29px" />
        </div>
    </div>
</template>
<script lang="ts">

import { AxiosResponse } from 'axios';
import dayjs from 'dayjs';
import Vue, { PropType } from 'vue';

import { IChannel, IDPlayerDanmakuSendOptions, IUser } from '@/interface';
import Utils from '@/utils';

export default Vue.extend({
    name: 'Comment',
    props: {
        // チャンネル情報
        channel: {
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

            // 手動スクロール状態かどうか
            is_manual_scroll: false,

            // 自動スクロール中かどうか
            // 自動スクロール中の場合、scroll イベントが発火しても無視する
            is_auto_scrolling: false,

            // ユーザーアカウントの情報
            // ログインしていない場合は null になる
            user: null as IUser | null,

            // コメントリストの配列
            comment_list: [] as {[key: string]: number | string}[],

            // コメントリストの要素
            comment_list_element: null as HTMLElement | null,

            // 視聴セッションの WebSocket のインスタンス
            watch_session: null as WebSocket | null,

            // コメントセッションの WebSocket のインスタンス
            comment_session: null as WebSocket | null,

            // 視聴セッション・コメントセッションの初期化に失敗した際のエラーメッセージ
            // 視聴中チャンネルのニコニコ実況がないときなどに発生する
            initialize_failed_message: null as string | null,

            // vpos を計算する基準となる時刻のタイムスタンプ
            vpos_base_timestamp: 0,

            // 座席維持用のタイマーのインターバル ID
            keep_seat_interval_id: 0,

            // ResizeObserver のインスタンス
            resize_observer: null as ResizeObserver | null,

            // ResizeObserver の監視対象の要素
            resize_observer_element: null as HTMLElement | null,
        }
    },
    // 終了前に実行
    beforeDestroy() {

        // destroy() を実行
        this.destroy();

        // ResizeObserver を終了
        if (this.resize_observer !== null) {
            this.resize_observer.unobserve(this.resize_observer_element);
        }
    },
    watch: {

        // チャンネル情報が変更されたとき
        // created() だとチャンネル情報の取得前に実行してしまう
        // this が変わってしまうのでアロー関数は使えない
        async channel(new_channel: IChannel, old_channel: IChannel) {

            // 前のチャンネル情報と次のチャンネル情報で channel_id が変わってたら
            if (new_channel.channel_id !== old_channel.channel_id) {

                // 0.5秒だけ待ってから
                // 連続してチャンネルを切り替えた時などに毎回コメントサーバーに接続しないように猶予を設ける
                // ただし、最初 (channel_id が gr000 の初期値になっている) だけは待たずに実行する
                if (old_channel.channel_id !== 'gr000') {
                    await Utils.sleep(0.5);
                    // 0.5 秒待った結果、channel_id が既に変更されているので終了
                    if (this.channel.channel_id !== new_channel.channel_id) {
                        return;
                    }
                }

                // 前の視聴セッション・コメントセッションを破棄
                this.destroy();

                // コメントリストの要素を取得
                if (this.comment_list_element === null) {
                    this.comment_list_element = this.$el.querySelector('.comment-list');
                }

                // 現在コメントリストがユーザーイベントでスクロールされているかどうか
                let is_user_scrolling = false;

                // mousedown → mouseup 中: スクロールバーをマウスでドラッグ
                // 残念ながらスクロールバーのドラッグ中は mousemove のイベントが発火しないため、直接 is_user_scrolling を設定する
                this.comment_list_element.onmousedown = (event: MouseEvent) => {
                    // コメントリストの要素の左上を起点としたカーソルのX座標を求める
                    const x = event.clientX - this.comment_list_element.getBoundingClientRect().left;
                    // 座標が clientWidth 以上であれば、スクロールバー上で mousedown されたものとする
                    if (x > this.comment_list_element.clientWidth) is_user_scrolling = true;
                }
                this.comment_list_element.onmouseup = (event: MouseEvent) => {
                    // コメントリストの要素の左上を起点としたカーソルのX座標を求める
                    const x = event.clientX - this.comment_list_element.getBoundingClientRect().left;
                    // 座標が clientWidth 以上であれば、スクロールバー上で mouseup されたものとする
                    if (x > this.comment_list_element.clientWidth) is_user_scrolling = false;
                }

                // ユーザーによるスクロールイベントで is_user_scrolling を true にする
                // 0.1 秒後に false にする（継続してイベントが発火すれば再び true になる）
                const on_user_scrolling = () => {
                    is_user_scrolling = true;
                    window.setTimeout(() => is_user_scrolling = false, 100);
                }

                // 現在コメントリストがドラッグされているかどうか
                let is_dragging = false;
                // touchstart → touchend 中: スクロールバーをタップでドラッグ
                this.comment_list_element.ontouchstart = () => is_dragging = true;
                this.comment_list_element.ontouchend = () => is_dragging = false;
                // touchmove + is_dragging 中: コメントリストをタップでドラッグしてスクロール
                this.comment_list_element.ontouchmove = () => is_dragging === true ? on_user_scrolling(): '';

                // wheel 中: マウスホイールの回転
                this.comment_list_element.onwheel = on_user_scrolling;

                // コメントリストがスクロールされた際、自動スクロール中でない&ユーザーイベントで操作されていれば、手動スクロールモードに設定
                // 手動スクロールモードでは自動スクロールを行わず、ユーザーがコメントリストをスクロールできるようにする
                this.comment_list_element.onscroll = async () => {

                    // scroll イベントは自動スクロールでも発火してしまうので、ユーザーイベントによるスクロールかを確認しないといけない
                    // 自動スクロール中かどうかは is_auto_scrolling が true のときで判定できるはずだが、
                    // コメントが多くなると is_auto_scrolling が false なのに scroll イベントが遅れて発火してしまうことがある
                    if (this.is_auto_scrolling === false && is_user_scrolling === true) {

                        // 手動スクロールを有効化
                        this.is_manual_scroll = true;

                        // イベント発火時点では scrollTop の値が完全に下にスクロールされていない場合があるため、0.1秒だけ待つ
                        await Utils.sleep(0.1);

                        // 一番下までスクロールしていたら自動スクロールに戻す
                        if ((this.comment_list_element.scrollTop + this.comment_list_element.offsetHeight) >
                            (this.comment_list_element.scrollHeight - 10)) {  // 一番下から 10px 以内
                            this.is_manual_scroll = false;  // 手動スクロールを無効化
                        }
                    }
                }

                // リサイズ時のイベントを初期化
                await this.initReserveObserver();

                // ユーザーアカウントの情報を取得
                try {
                    this.user = (await Vue.axios.get('/users/me')).data;
                } catch (error) {
                    this.user = null;
                }

                try {

                    // 視聴セッションを初期化
                    const comment_session_info = await this.initWatchSession();

                    // vpos の基準時刻のタイムスタンプを取得
                    // vpos は番組開始時間からの累計秒（10ミリ秒単位）
                    this.vpos_base_timestamp = dayjs(comment_session_info['vpos_base_time']).unix() * 100;

                    // コメントセッションを初期化
                    await this.initCommentSession(comment_session_info);

                } catch (error) {

                    // 初期化に失敗した場合のエラーメッセージを保存しておく
                    // 初期化に失敗したのにコメントを送信しようとした際に表示するもの
                    this.initialize_failed_message = error.message;
                    console.error(error.toString());
                }
            }
        }
    },
    methods: {

        // 視聴セッションを初期化
        async initWatchSession(): Promise<{[key: string]: string | null}> {

            // セッション情報を取得
            let watch_session_info: AxiosResponse;
            try {
                watch_session_info = await Vue.axios.get(`/channels/${this.channel.channel_id}/jikkyo`);
            } catch (error) {
                throw new Error(error);  // エラー内容をコンソールに表示して終了
            }

            // セッション情報を取得できなかった
            if (watch_session_info.data.is_success === false) {

                // 一部を除くエラーメッセージはプレイヤーにも通知する
                if ((watch_session_info.data.detail !== 'このチャンネルのニコニコ実況はありません。') &&
                    (watch_session_info.data.detail !== '現在放送中のニコニコ実況がありません。')) {
                    this.player.notice(watch_session_info.data.detail);
                }

                throw new Error(watch_session_info.data.detail);  // エラー内容をコンソールに表示して終了
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
                                'message_server': message.data.messageServer.uri,
                                // コメントサーバー上のスレッド ID
                                'thread_id': message.data.threadId,
                                // vpos を計算する基準となる時刻 (ISO8601形式)
                                'vpos_base_time': message.data.vposBaseTime,
                                // メッセージサーバーから受信するコメント (chat メッセージ) に yourpost フラグを付けるためのキー
                                'your_post_key': (message.data.yourPostKey ? message.data.yourPostKey : null),
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

                            // waitTimeSec に記載の秒数だけ待ってから再接続する
                            await Utils.sleep(message.data.waitTimeSec);
                            if (this.player.danmaku.showing) {
                                this.player.notice('ニコニコ実況に再接続しています…');
                            }

                            // 前の視聴セッション・コメントセッションを破棄
                            this.destroy();

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

                            // 5 秒ほど待ってから再接続する
                            await Utils.sleep(5);
                            if (this.player.danmaku.showing) {
                                this.player.notice('ニコニコ実況に再接続しています…');
                            }

                            // 前の視聴セッション・コメントセッションを破棄
                            this.destroy();

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

                    // 10 秒ほど待ってから再接続する
                    // ニコ生側から切断された場合と異なりネットワークが切断された可能性が高いので、間を多めに取る
                    await Utils.sleep(10);
                    if (this.player.danmaku.showing) {
                        this.player.notice('ニコニコ実況に再接続しています…');
                    }

                    // 前の視聴セッション・コメントセッションを破棄
                    this.destroy();

                    // 視聴セッションを再初期化
                    const comment_session_info = await this.initWatchSession();

                    // コメントセッションを再初期化
                    await this.initCommentSession(comment_session_info);
                };
            });
        },

        // コメントセッションを初期化
        async initCommentSession(comment_session_info: {[key: string]: string | null}) {

            // タブが非表示状態のときにコメントを格納する配列
            // タブが表示状態になったらコメントリストにのみ表示する（遅れているのでプレイヤーには表示しない）
            let comment_list_buffer = [];

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

                    // コメントリストを一番下にスクロール
                    // 初回コメントは量が多いので、一括でスクロールする
                    this.scrollCommentList();
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

                // 色・位置・サイズ
                let color = '#FFEAEA';  // コメント色のデフォルト
                let position = 'right'; // コメント位置のデフォルト
                let size = 'medium';    // コメントサイズのデフォルト
                if (comment.mail !== undefined && comment.mail !== null) {

                    // コマンドをスペースで区切って配列にしたもの (184 は事前に除外)
                    const commands = comment.mail.replace('184', '').split(' ');

                    for (const command of commands) {  // コマンドごとに
                        // コメント色指定コマンドがあれば取得
                        if (this.getCommentColor(command) !== null) {
                            color = this.getCommentColor(command);
                        }
                        // コメント位置指定コマンドがあれば取得
                        if (this.getCommentPosition(command) !== null) {
                            position = this.getCommentPosition(command);
                        }
                        // コメントサイズ指定コマンドがあれば取得
                        // コメントサイズのコマンドは DPlayer とニコニコで共通なので、変換の必要はない
                        if (command === 'big' || command === 'medium' || command === 'small') {
                            size = command;
                        }
                    }
                }

                // 配信に発生する遅延分待ってから
                // 現状だいたい1秒くらいなので暫定で決め打ち
                // 最初に受信したコメントはリアルタイムなコメントではないため、遅らせないように
                if (is_received_initial_comment) {
                    const comment_delay_time = Utils.getSettingsItem('comment_delay_time');
                    await Utils.sleep(comment_delay_time);
                }

                // コメントリストのコメントが 500 件を超えたら古いものから順に削除する
                // 仮想スクロールとはいえ、さすがに 500 件を超えると重くなりそう
                if (this.comment_list.length > 500) {
                    this.comment_list.shift();
                }

                // コメントリストへ追加するオブジェクト
                // コメント投稿時刻はフォーマットしてから
                const comment_dict = {
                    id: comment.no,
                    text: comment.content,
                    time: dayjs(comment.date * 1000).format('HH:mm:ss'),
                };

                // タブが非表示状態のときは、バッファにコメントを追加するだけで終了する
                // ここで追加すると、タブが表示状態になったときに一斉に描画されて大変なことになる
                if (document.visibilityState === 'hidden') {
                    comment_list_buffer.push(comment_dict);
                    return;
                }

                // コメントリストに追加
                this.comment_list.push(comment_dict);

                // // コメントリストを一番下にスクロール
                // 最初に受信したコメントは上の処理で一括でスクロールさせる
                if (is_received_initial_comment) {
                    this.scrollCommentList();
                }

                // コメント描画 (再生時のみ)
                // 最初に受信したコメントはリアルタイムなコメントではないため、描画しないように
                if (is_received_initial_comment) {
                    if (!this.player.video.paused){
                        this.player.danmaku.draw({
                            text: comment.content,
                            color: color,
                            type: position,
                            size: size,
                        });
                    }
                }
            });

            // タブの表示/非表示の状態が切り替わったときのイベント
            // 表示状態になったときにバッファにあるコメントをコメントリストに表示する
            document.onvisibilitychange = () => {
                if (document.visibilityState === 'visible') {
                    this.comment_list.push(...comment_list_buffer);  // コメントリストに一括で追加
                    comment_list_buffer = [];  // バッファをクリア
                    this.scrollCommentList();  // コメントリストをスクロール
                }
            };
        },

        // コメントを送信する
        async sendComment(options: IDPlayerDanmakuSendOptions) {

            // 初期化に失敗しているときは実行せず、保存しておいたエラーメッセージを表示する
            if (this.initialize_failed_message !== null) {
                options.error(this.initialize_failed_message);
                return;
            }

            // 未ログイン時
            if (this.user === null) {
                options.error('コメントするには、KonomiTV アカウントにログインしてください。');
                return;
            }

            // ニコニコアカウント未連携時
            if (this.user.niconico_user_id === null) {
                options.error('コメントするには、ニコニコアカウントと連携してください。');
                return;
            }

            // 一般会員ではコメント位置の指定 (ue, shita) が無視されるので、事前にエラーにしておく
            if (this.user.niconico_user_premium === false && (options.data.type === 'top' || options.data.type === 'bottom')) {
                options.error('コメントを上下に固定するには、ニコニコアカウントのプレミアム会員登録が必要です。');
                return;
            }

            // 一般会員ではコメントサイズ大きめの指定 (big) が無視されるので、事前にエラーにしておく
            if (this.user.niconico_user_premium === false && options.data.size === 'big') {
                options.error('コメントサイズを大きめに設定するには、ニコニコアカウントのプレミアム会員登録が必要です。');
                return;
            }

            // DPlayer 上のコメント色（カラーコード）とニコニコの色コマンド定義のマッピング
            const color_table = {
                '#FFEAEA': 'white',
                '#F02840': 'red',
                '#FD7E80': 'pink',
                '#FDA708': 'orange',
                '#FFE133': 'yellow',
                '#64DD17': 'green',
                '#00D4F5': 'cyan',
                '#4763FF': 'blue',
            };

            // DPlayer 上のコメント位置を表す数値とニコニコの位置コマンド定義のマッピング
            const position_table = {
                'top': 'ue',
                'right': 'naka',
                'bottom': 'shita',
            };

            // vpos を計算 (10ミリ秒単位)
            // 番組開始時間からの累計秒らしいけど、なぜ指定しないといけないのかは不明
            const vpos = Math.floor(new Date().getTime() / 10) - this.vpos_base_timestamp;

            // コメントを送信
            this.watch_session.send(JSON.stringify({
                'type': 'postComment',
                'data': {
                    'text': options.data.text,  // コメント本文
                    'color': color_table[options.data.color.toUpperCase()],  // コメントの色
                    'position': position_table[options.data.type],  // コメント位置
                    'size': options.data.size,  // コメントサイズ (DPlayer とニコニコで表現が共通)
                    'vpos': vpos,  // 番組開始時間からの累計秒（10ミリ秒単位）
                    'isAnonymous': true,  // 匿名コメント (184)
                }
            }));

            // コメント送信のレスポンスを取得
            // 簡単にイベントリスナーを削除できるため、あえて onmessage で実装している
            this.watch_session.onmessage = (event) => {

                // 受信したメッセージ
                const message = JSON.parse(event.data);

                switch (message.type) {

                    // postCommentResult
                    // これが送られてくる → コメント送信に成功している
                    case 'postCommentResult': {

                        // コメント成功のコールバックを DPlayer に通知
                        options.success();

                        // イベントリスナーを削除
                        this.watch_session.onmessage = null;
                        break;
                    }

                    // error
                    // コメント送信直後に error が送られてきた → コメント送信に失敗している
                    case 'error': {

                        // エラーメッセージ
                        let error = `コメントの送信に失敗しました。(${message.data.code})`;
                        switch (message.data.code) {
                            case 'COMMENT_POST_NOT_ALLOWED': {
                                error = 'コメントが許可されていません。';
                                break;
                            }
                            case 'INVALID_MESSAGE': {
                                error = 'コメント内容が無効です。';
                                break;
                            }
                        }

                        // コメント失敗のコールバックを DPlayer に通知
                        options.error(error);

                        // イベントリスナーを解除
                        this.watch_session.onmessage = null;
                        break;
                    }
                }
            };
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
                if (this.resize_observer_element === null || this.resize_observer_element.clientHeight === null) return;
                if (video_element === null || video_element.clientHeight === null) return;
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

            // 0.4 秒待ってから初回実行
            // チャンネル切り替え後、再初期化されたプレイヤーに適用するため（早いと再初期化前のプレイヤーに適用されてしまう）
            window.setTimeout(on_resize, 0.4 * 1000);
        },

        // コメントリストを一番下までスクロールする
        async scrollCommentList(smooth: boolean = false) {

            // 手動スクロールモードの時は実行しない
            if (this.is_manual_scroll === true) return;

            // 自動スクロール中のフラグを立てる
            this.is_auto_scrolling = true;

            // 0.01 秒待って実行し、念押しで2回実行しないと完全に最下部までスクロールされない…（ブラウザの描画バグ？）
            // this.$nextTick() は効かなかった
            for (let index = 0; index < 3; index++) {
                await Utils.sleep(0.01);
                if (smooth === true) {  // スムーズスクロール
                    this.comment_list_element.scrollTo({top: this.comment_list_element.scrollHeight, left: 0, behavior: 'smooth'});
                } else {
                    this.comment_list_element.scrollTo(0, this.comment_list_element.scrollHeight);
                }
            }

            // 0.1 秒待つ（重要）
            await Utils.sleep(0.1);

            // 自動スクロール中のフラグを降ろす
            this.is_auto_scrolling = false;
        },

        /**
         * ニコニコの色指定を 16 進数カラーコードに置換する
         * @param {string} color ニコニコの色指定
         * @return {string} 16 進数カラーコード
         */
        getCommentColor(color: string): string {
            const color_table = {
                'white': '#FFEAEA',
                'red': '#F02840',
                'pink': '#FD7E80',
                'orange': '#FDA708',
                'yellow': '#FFE133',
                'green': '#64DD17',
                'cyan': '#00D4F5',
                'blue': '#4763FF',
                'purple': '#D500F9',
                'black': '#1E1310',
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

            // タブの表示/非表示の状態が切り替わったときのイベントを削除
            document.onvisibilitychange = null;

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

    .comment-scroll-button {
        display: flex;
        align-items: center;
        justify-content: center;
        position: absolute;
        left: 0px;
        right: 0px;
        bottom: 22px;
        width: 42px;
        height: 42px;
        margin: 0 auto;
        border-radius: 50%;
        background: var(--v-primary-base);
        transition: background-color 0.15s, opacity 0.3s, visibility 0.3s;
        visibility: hidden;
        opacity: 0;
        user-select: none;
        cursor: pointer;

        &--display {
            opacity: 1;
            visibility: visible;
        }
    }
}

</style>