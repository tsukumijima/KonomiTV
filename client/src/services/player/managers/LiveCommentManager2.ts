
import { throttle } from '@github/mini-throttle';
import dayjs from 'dayjs';
import DPlayer, { DPlayerType } from 'dplayer';

import Channels from '@/services/Channels';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import Utils, { CommentUtils } from '@/utils';


export interface ICommentData {
    id: number;
    text: string;
    time: string;
    user_id: string;
    my_post: boolean;
}

interface IWatchSessionInfo {
    is_success: boolean;
    detail: string;
    message_server_url?: string;
    thread_id?: string;
    your_post_key?: string;
}


/**
 * ライブ視聴: ニコニコ実況からリアルタイムに受信したコメントを DPlayer やイベントリスナーに送信する PlayerManager
 */
class LiveCommentManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerWrapper に示す値
    public readonly restart_required_when_quality_switched = false;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // 視聴セッションの WebSocket のインスタンス
    private watch_session: WebSocket | null = null;

    // コメントセッションの WebSocket のインスタンス
    private comment_session: WebSocket | null = null;

    // vpos を計算する基準となる時刻のタイムスタンプ
    private vpos_base_timestamp: number = 0;

    // 座席維持用のタイマーのインターバル ID
    private keep_seat_interval_id: number | null = null;

    // destroy() 時に EventListener を全解除するための AbortController
    private abort_controller: AbortController = new AbortController();

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     */
    constructor(player: DPlayer) {
        this.player = player;
    }


    /**
     * ニコニコ実況に接続し、セッションを初期化する
     */
    public async init(): Promise<void> {

        // 視聴セッションを初期化
        const watch_session_info = await this.initWatchSession();
        if (watch_session_info.is_success === false) {
            console.error(`[LiveCommentManager][WatchSession] Error: ${watch_session_info.detail}`);
            // 通常発生しないエラーメッセージ (サーバーエラーなど) はプレイヤー側にも通知する
            if ((watch_session_info.detail !== 'このチャンネルはニコニコ実況に対応していません。') &&
                (watch_session_info.detail !== '現在放送中のニコニコ実況がありません。')) {
                this.player.notice(watch_session_info.detail, undefined, undefined, '#FF6F6A');
            }
            return;
        }

        // 視聴セッションを初期化できた場合のみ、
        // 取得したコメントサーバーへの接続情報を使い、非同期でコメントセッションを初期化
        this.initCommentSession(watch_session_info);
    }


    /**
     * 視聴セッションを初期化する
     * @returns コメントサーバーへの接続情報 or エラー情報
     */
    private async initWatchSession(): Promise<IWatchSessionInfo> {
        const channels_store = useChannelsStore();

        // サーバーから disconnect メッセージが送られてきた際のフラグ
        let is_disconnect_message_received = false;

        // セッション情報を取得
        const watch_session_info = await Channels.fetchJikkyoSession(channels_store.display_channel_id);
        if (watch_session_info === null) {
            return {
                is_success: false,
                detail: 'ニコニコ実況のセッション情報を取得できませんでした。',
            };
        }
        if (watch_session_info.is_success === false) {
            return {
                is_success: false,
                detail: watch_session_info.detail,
            };
        }

        // 視聴セッション WebSocket を開く
        this.watch_session = new WebSocket(watch_session_info.audience_token!);

        // 視聴セッションの接続が開かれたとき
        this.watch_session.addEventListener('open', () => {

            // 視聴セッションをリクエスト
            // 公式ドキュメントいわく、stream フィールドは Optional らしい
            // サーバー負荷軽減のため、映像が不要な場合は必ず省略してくださいとのこと
            this.watch_session?.send(JSON.stringify({
                type: 'startWatching',
                data: {
                    'reconnect': false,
                },
            }));

        }, { signal: this.abort_controller.signal });

        // 視聴セッションの接続が閉じられたとき（ネットワークが切断された場合など）
        this.watch_session.addEventListener('close', async (event) => {

            // すでに disconnect メッセージが送られてきている場合は何もしない
            if (is_disconnect_message_received === true) {
                return;
            }

            // 接続切断の理由を表示
            console.error(`[LiveCommentManager][WatchSession] Connection closed. (Code: ${event.code})`);
            this.player.notice(`ニコニコ実況との接続が切断されました。(Code: ${event.code})`, undefined, undefined, '#FF6F6A');

            // 10 秒ほど待ってから再接続する
            // ニコ生側から切断された場合と異なりネットワークが切断された可能性が高いので、間を多めに取る
            await Utils.sleep(10);
            await this.reconnect();

        }, { signal: this.abort_controller.signal });

        // 視聴セッション WebSocket からメッセージを受信したとき
        // 視聴セッションはコメント送信時のために維持し続ける必要がある
        // 以下はいずれも視聴セッションを維持し続けたり、エラーが発生した際に再接続するための処理
        this.watch_session.addEventListener('message', async (event) => {
            if (this.watch_session === null) return;

            // 各メッセージタイプに対応する処理を実行
            const message = JSON.parse(event.data);
            switch (message.type) {

                // 座席情報
                case 'seat': {
                    // すでにタイマーが設定されている場合は何もしない
                    if (this.keep_seat_interval_id !== null) {
                        break;
                    }
                    // keepIntervalSec の秒数ごとに keepSeat を送信して座席を維持する
                    this.keep_seat_interval_id = window.setInterval(() => {
                        if (this.watch_session && this.watch_session.readyState === WebSocket.OPEN) {
                            // セッションがまだ開いていれば、座席を維持する
                            this.watch_session.send(JSON.stringify({type: 'keepSeat'}));
                        } else {
                            // セッションが閉じられている場合は、タイマーを停止する
                            window.clearInterval(this.keep_seat_interval_id ?? 0);
                        }
                    }, message.data.keepIntervalSec * 1000);
                    break;
                }

                // ping-pong
                case 'ping': {
                    // pong を返してセッションを維持する
                    // 送り返さなかった場合、勝手にセッションが閉じられてしまう
                    this.watch_session.send(JSON.stringify({type: 'pong'}));
                    break;
                }

                // エラー情報
                case 'error': {
                    // COMMENT_POST_NOT_ALLOWED と INVALID_MESSAGE に関しては sendComment() の方で処理するので、ここでは何もしない
                    if (message.data.code === 'COMMENT_POST_NOT_ALLOWED' || message.data.code === 'INVALID_MESSAGE') {
                        break;
                    }

                    let error = `ニコニコ実況でエラーが発生しています。(Code: ${message.data.code})`;
                    switch (message.data.code) {
                        case 'CONNECT_ERROR':
                            error = 'ニコニコ実況のコメントサーバーに接続できません。';
                            break;
                        case 'CONTENT_NOT_READY':
                            error = 'ニコニコ実況が配信できない状態です。';
                            break;
                        case 'NO_THREAD_AVAILABLE':
                            error = 'ニコニコ実況のコメントスレッドを取得できません。';
                            break;
                        case 'NO_ROOM_AVAILABLE':
                            error = 'ニコニコ実況のコメント部屋を取得できません。';
                            break;
                        case 'NO_PERMISSION':
                            error = 'ニコニコ実況の API にアクセスする権限がありません。';
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
                    }

                    // エラー情報を表示
                    console.error(`[LiveCommentManager][WatchSession] Error occurred. (Code: ${message.data.code})`);
                    this.player.notice(error, undefined, undefined, '#FF6F6A');

                    // 5 秒ほど待ってから再接続する
                    await Utils.sleep(5);
                    await this.reconnect();
                    break;
                }

                // 再接続を求められた
                case 'reconnect': {
                    // waitTimeSec に記載の秒数だけ待ってから再接続する
                    // 公式ドキュメントには reconnect で送られてくる audienceToken で再接続しろと書いてあるんだけど、
                    // 確実性的な面で実装が面倒なので当面このままにしておく
                    await this.reconnect();
                    break;
                }

                // 視聴セッションが閉じられた（4時のリセットなど）
                case 'disconnect': {
                    // 実際に接続が閉じられる前に disconnect メッセージが送られてきたので、
                    // WebSocket の close メッセージを実行させないようにする
                    is_disconnect_message_received = true;

                    // 接続切断の理由
                    let disconnect_reason = `ニコニコ実況との接続が切断されました。(${message.data.reason})`;
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
                    }

                    // 接続切断の理由を表示
                    console.error(`[LiveCommentManager][WatchSession] Disconnected. (Reason: ${message.data.reason})`);
                    this.player.notice(disconnect_reason);

                    // 5 秒ほど待ってから再接続する
                    await Utils.sleep(5);
                    await this.reconnect();
                    break;
                }
            }

        }, { signal: this.abort_controller.signal });

        // コメントサーバーへの接続情報を返す
        // イベント内で値を返すため、Promise で包む
        return new Promise((resolve) => {
            this.watch_session!.addEventListener('message', async (event) => {
                const message = JSON.parse(event.data);
                if (message.type === 'room') {

                    // vpos の基準時刻のタイムスタンプを取得 (ミリ秒単位)
                    // vpos は番組開始時間からの累計秒数
                    this.vpos_base_timestamp = dayjs(message.data.vposBaseTime).valueOf();

                    // コメントサーバーへの接続情報を返す
                    console.log(`[LiveCommentManager][WatchSession] Connected.\nThread ID: ${message.data.threadId}\n`);
                    return resolve({
                        is_success: true,
                        detail: '視聴セッションを取得しました。',
                        // コメントサーバーへの接続情報
                        message_server_url: message.data.messageServer.uri,
                        // コメントサーバー上のスレッド ID
                        thread_id: message.data.threadId,
                        // メッセージサーバーから受信するコメント (chat メッセージ) に yourpost フラグを付けるためのキー
                        your_post_key: (message.data.yourPostKey ? message.data.yourPostKey : null),
                    });
                }
            }, { signal: this.abort_controller.signal });
        });
    }


    /**
     * コメントセッションを初期化する
     * @param comment_session_info コメントサーバーへの接続情報
     */
    private initCommentSession(comment_session_info: IWatchSessionInfo): void {
        const player_store = usePlayerStore();

        // 初回接続時に一括で送信されてくる過去コメントを受信し終えるまで格納するバッファ
        const initial_comments_buffer: ICommentData[] = [];

        // 初回接続時に一括で送信されてくる過去コメントを受信し終えたかどうかのフラグ
        let initial_comments_received = false;

        // 受信したコメントを一時的に格納するバッファ (スロットル用)
        const comments_buffer: ICommentData[] = [];

        // コメントセッション WebSocket を開く
        this.comment_session = new WebSocket(comment_session_info.message_server_url!);

        // コメントセッション WebSocket を開いたとき
        this.comment_session.addEventListener('open', () => {
            if (this.comment_session === null) return;

            // コメント送信をリクエスト
            // このコマンドを送らないとコメントが送信されてこない
            this.comment_session.send(JSON.stringify([
                {ping: {content: 'rs:0'}},
                {ping: {content: 'ps:0'}},
                {
                    thread: {
                        version: '20061206',  // 設定必須
                        thread: comment_session_info.thread_id,  // スレッド ID
                        threadkey: comment_session_info.your_post_key,  // スレッドキー
                        user_id: '',  // ユーザー ID（設定不要らしい）
                        res_from: -50,  // 最初にコメントを 50 個送信する
                    }
                },
                {ping: {content: 'pf:0'}},
                {ping: {content: 'rf:0'}},
            ]));

        }, { signal: this.abort_controller.signal });

        // 受信したコメントをイベントリスナーに送信する関数
        // スロットルを設定し、100ms 未満の間隔でイベントが発火しないようにする
        const emit_comments = throttle(() => {
            player_store.event_emitter.emit('LiveCommentReceived', {
                is_initial_comments: false,
                comments: comments_buffer,
            });
            // バッファを空にする
            comments_buffer.length = 0;
        }, 100);

        // コメントセッション WebSocket からメッセージを受信したとき
        this.comment_session.addEventListener('message', async (event) => {

            // メッセージを取得
            const message = JSON.parse(event.data);

            // 接続失敗
            if (message.thread !== undefined) {
                if (message.thread.resultcode !== 0) {
                    console.error(`[LiveCommentManager][CommentSession] Connection failed. (Code: ${message.thread.resultcode})`);
                    return;
                }
            }

            // ping メッセージのみ
            // rf:0 が送られてきたら初回接続時に一括で送信されてくる過去コメントの受信は完了している
            // この時点で初期コメントを一気にイベントリスナーに送信する
            if (message.ping !== undefined && message.ping.content === 'rf:0') {
                initial_comments_received = true;
                player_store.event_emitter.emit('LiveCommentReceived', {
                    is_initial_comments: true,
                    comments: initial_comments_buffer,
                });
                return;
            }

            // コメントデータを取得
            const comment = message.chat;

            // コメントデータが不正な場合 or 自分のコメントの場合は弾く
            if ((comment === undefined || comment.content === undefined || comment.content === '') ||
                (comment.yourpost && comment.yourpost === 1)) {
                return;
            }

            // コメントコマンドをパース
            const { color, position, size } = CommentUtils.parseCommentCommand(comment.mail);

            // ミュート対象のコメントかどうかを判定し、もしそうならここで弾く
            if (CommentUtils.isMutedComment(comment.content, comment.user_id, color, position, size)) {
                return;
            }

            // コメントリストへ追加するオブジェクト
            const comment_data: ICommentData = {
                id: comment.no,
                text: comment.content,
                time: dayjs(comment.date * 1000).format('HH:mm:ss'),
                user_id: comment.user_id,
                my_post: false,
            };

            // もしまだ初期コメントを受信し終えていないなら、バッファに格納して終了
            // 初期コメントはプレイヤーには描画しないため問題ない
            if (initial_comments_received === false) {
                initial_comments_buffer.push(comment_data);
                return;
            }

            // 配信で発生する遅延分待ってから
            // おおよその遅延時間は video.buffered.end(0) - video.currentTime で取得できる
            let buffered_end = 0;
            if (this.player.video.buffered.length >= 1) {
                buffered_end = this.player.video.buffered.end(0);
            }
            const comment_delay_time = buffered_end - this.player.video.currentTime;
            // console.log(`[LiveCommentManager][CommentSession] Delay: ${comment_delay_time} sec.`)
            await Utils.sleep(comment_delay_time);

            // プレイヤーにコメントを描画する (映像再生時のみ)
            if (this.player.video.paused === false) {
                this.player.danmaku!.draw({
                    text: comment.content,
                    color: color,
                    type: position,
                    size: size,
                });
            }

            // コメントを一時バッファに格納し、スロットルを設定してイベントリスナーに送信する
            // コメントの受信間隔が 100ms 以上あれば、今回のコールバックで取得したコメントがダイレクトにイベントリスナーに送信される
            comments_buffer.push(comment_data);
            emit_comments();

        }, { signal: this.abort_controller.signal });
    }


    /**
     * ニコニコ実況にコメントを送信する
     * @param options DPlayer のコメントオプション
     */
    public sendComment(options: DPlayerType.APIBackendSendOptions): void {

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

        // DPlayer 上のコメント位置を表す値とニコニコの位置コマンド定義のマッピング
        const position_table = {
            'top': 'ue',
            'right': 'naka',
            'bottom': 'shita',
        };

        // vpos を計算 (10ミリ秒単位)
        // 番組開始時間からの累計秒らしいけど、なぜ指定しないといけないのかは不明
        // 小数点以下は丸めないとコメントサーバー側で投稿エラーになる
        const vpos = Math.round((dayjs().valueOf() - this.vpos_base_timestamp) / 10);

        // 視聴セッションが null か、接続が切れている場合は弾く
        if (this.watch_session === null || this.watch_session.readyState !== WebSocket.OPEN) {
            console.error('[LiveCommentManager][WatchSession] Comment sending failed. (Connection is not established.)');
            options.error('コメントの送信に失敗しました。WebSocket 接続が確立されていません。');
            return;
        }

        // コメントを送信
        this.watch_session.send(JSON.stringify({
            'type': 'postComment',
            'data': {
                // コメント本文
                'text': options.data.text,
                // コメントの色
                'color': color_table[options.data.color.toUpperCase()],
                // コメント位置
                'position': position_table[options.data.type],
                // コメントサイズ (DPlayer とニコニコで表現が共通なため、変換不要)
                'size': options.data.size,
                // 番組開始時間からの累計秒 (10ミリ秒単位)
                'vpos': vpos,
                // 匿名コメント (184) にするかどうか
                'isAnonymous': true,
            }
        }));

        // コメント送信のレスポンスを取得
        const abort_controller = new AbortController();
        this.watch_session.addEventListener('message', (event) => {
            const message = JSON.parse(event.data);
            switch (message.type) {

                // postCommentResult が送られてきた → コメント送信に成功している
                case 'postCommentResult': {
                    // コメント成功を DPlayer にコールバックで通知
                    options.success();

                    // イベントリスナーを削除
                    abort_controller.abort();
                    break;
                }

                // コメント送信直後に error が送られてきた → コメント送信に失敗している
                case 'error': {
                    // コメント失敗を DPlayer にコールバックで通知
                    let error = `コメントの送信に失敗しました。(${message.data.code})`;
                    switch (message.data.code) {
                        case 'COMMENT_POST_NOT_ALLOWED':
                            error = 'コメントが許可されていません。';
                            break;
                        case 'INVALID_MESSAGE':
                            error = 'コメント内容が無効です。';
                            break;
                    }
                    console.error(`[LiveCommentManager][WatchSession] Comment sending failed. (Code: ${message.data.code})`);
                    options.error(error);

                    // イベントリスナーを解除
                    abort_controller.abort();
                    break;
                }
            }
        }, { signal: abort_controller.signal });
    }


    /**
     * 同じ設定でニコニコ実況に再接続する
     */
    private async reconnect(): Promise<void> {
        console.warn('[LiveCommentManager][WatchSession] Reconnecting...');
        this.player.notice('ニコニコ実況に再接続しています…');

        // 前の視聴セッション・コメントセッションを破棄
        await this.destroy();

        // 視聴セッションを再初期化
        const watch_session_info = await this.initWatchSession();
        if (watch_session_info.is_success === false) {
            // 無条件にエラーメッセージをプレイヤーに通知
            console.error('[LiveCommentManager][WatchSession] Reconnection failed.');
            this.player.notice(watch_session_info.detail, undefined, undefined, '#FF6F6A');
            return;
        }

        // 視聴セッションを初期化できた場合のみ、
        // 取得したコメントサーバーへの接続情報を使い、非同期でコメントセッションを初期化
        this.initCommentSession(watch_session_info);
    }


    /**
     * 視聴セッションとコメントセッションをそれぞれ閉じる
     */
    public async destroy(): Promise<void> {

        // セッションに紐いているすべての EventListener を解除
        // 再接続する場合に備えて AbortController を作り直す
        this.abort_controller.abort();
        this.abort_controller = new AbortController();

        // 視聴セッションを閉じる
        if (this.watch_session !== null) {
            this.watch_session.close();  // WebSocket を閉じる
            this.watch_session = null;  // null に戻す
        }

        // コメントセッションを閉じる
        if (this.comment_session !== null) {
            this.comment_session.close();  // WebSocket を閉じる
            this.comment_session = null;  // null に戻す
        }

        // 座席保持用のタイマーをクリア
        if (this.keep_seat_interval_id !== null) {
            window.clearInterval(this.keep_seat_interval_id);
            this.keep_seat_interval_id = null;
        }
        this.vpos_base_timestamp = 0;

        console.log('[LiveCommentManager][WatchSession] Destroyed.');
    }
}

export default LiveCommentManager;
