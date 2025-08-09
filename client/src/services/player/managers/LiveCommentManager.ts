
import { throttle } from '@github/mini-throttle';
import DPlayer, { DPlayerType } from 'dplayer';

import Channels from '@/services/Channels';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';
import Utils, { dayjs, CommentUtils } from '@/utils';


export interface ICommentData {
    id: number;
    text: string;
    time: string;
    playback_position: number;
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
 * ライブ視聴: ニコニコ実況または NX-Jikkyo からリアルタイムに受信したコメントを DPlayer やイベントリスナーに送信する PlayerManager
 */
class LiveCommentManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
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

    // 再接続中かどうか
    private reconnecting = false;

    // 破棄済みかどうか
    private destroyed = false;

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     */
    constructor(player: DPlayer) {
        this.player = player;
    }


    private get watch_session_type(): 'ニコニコ実況' | 'NX-Jikkyo ' {
        // 英字と日本語の間にスペースを入れるため、意図的に "NX-Jikkyo " の末尾にスペースを付けている
        return this.watch_session?.url.includes('nicovideo.jp') === true ? 'ニコニコ実況' : 'NX-Jikkyo ';
    }


    /**
     * ニコニコ実況または NX-Jikkyo に接続し、セッションを初期化する
     */
    public async init(): Promise<void> {
        const player_store = usePlayerStore();
        const user_store = useUserStore();

        // 破棄済みかどうかのフラグを下ろす
        this.destroyed = false;

        // ユーザー情報を事前にキャッシュさせておく
        await user_store.fetchUser();

        // 視聴セッションを初期化
        const watch_session_info = await this.initWatchSession();
        if (watch_session_info.is_success === false) {

            // 初期化に失敗した際のエラーメッセージを設定する
            // UI 側のエラー表示に利用されるほか、null から string になったことで初期化に失敗したことを示す
            player_store.live_comment_init_failed_message = watch_session_info.detail;
            console.error(`[LiveCommentManager][WatchSession] Error: ${watch_session_info.detail}`);

            // 通常発生しないエラーメッセージ (サーバーエラーなど) はプレイヤー側にも通知する
            if (watch_session_info.detail !== 'このチャンネルはニコニコ実況に対応していません。') {
                if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
                    this.player.notice(watch_session_info.detail, undefined, undefined, '#FF6F6A');
                }
            }
            return;
        }

        // 視聴セッションを初期化できた場合のみ、
        // 取得したコメントサーバーへの接続情報を使い、非同期でコメントセッションを初期化
        this.initCommentSession(watch_session_info);

        console.log('[LiveCommentManager] Initialized.');
    }


    /**
     * 視聴セッションを初期化する
     * @returns コメントサーバーへの接続情報 or エラー情報
     */
    private async initWatchSession(): Promise<IWatchSessionInfo> {
        const channels_store = useChannelsStore();
        const settings_store = useSettingsStore();
        const user_store = useUserStore();

        // サーバーから disconnect メッセージが送られてきた際のフラグ
        let is_disconnect_message_received = false;

        // 視聴セッション WebSocket の URL を取得
        // 実際は旧ニコニコ生放送の WebSocket API と互換性がある NX-Jikkyo の WebSocket API の URL が返る
        const websocket_info = await Channels.fetchWebSocketInfo(channels_store.channel.current.id);
        if (websocket_info === null) {
            return {
                is_success: false,
                detail: 'コメント受信用 WebSocket API の情報を取得できませんでした。',
            };
        }
        // チャンネルに対応するニコニコ実況チャンネルが存在しない場合
        if (websocket_info.watch_session_url === null) {
            return {
                is_success: false,
                detail: 'このチャンネルはニコニコ実況に対応していません。',
            };
        }

        // ニコニコ生放送と NX-Jikkyo のどちらの視聴セッションに接続するかを決定
        // デフォルト: NX-Jikkyo の視聴セッションに接続する
        let watch_session_url = websocket_info.watch_session_url;

        // 「可能であればニコニコ実況にコメントする」設定がオンのときのみ
        // ニコニコ生放送の視聴セッション WebSocket URL を取得できなかった場合もコメント受信と NX-Jikkyo へのコメント送信は可能なので、
        // 致命的なエラーとはせずあえて警告メッセージにとどめている
        if (settings_store.settings.prefer_posting_to_nicolive === true) {

            // ニコニコ生放送の視聴セッション WebSocket URL の取得に成功した場合のみ、
            // NX-Jikkyo ではなくニコニコ生放送で現在放送中の実況番組の視聴セッションに接続する
            if (websocket_info.nicolive_watch_session_url !== null) {
                console.log('[LiveCommentManager][WatchSession] Post comments to Nicolive.');
                watch_session_url = websocket_info.nicolive_watch_session_url;

            // ニコニコ実況に存在しない実況チャンネル (ex: BS日テレ): コンソールにのみ警告を表示
            // 頻度が多い上エラーではなく予期された挙動であり、毎回表示するのは鬱陶しいため
            } else if (websocket_info.is_nxjikkyo_exclusive === true) {
                console.warn('[LiveCommentManager][WatchSession] Failed to get Nicolive watch session URL. (This channel is exclusive to NX-Jikkyo.)');

            // KonomiTV アカウントにログインしていないために視聴セッション WebSocket URL を取得できなかった: コンソールにのみ警告を表示
            // ニコニコ実況を使わない人にとって、わざわざ設定をオフにしないとこのメッセージが消せないのはストレスなので、警告メッセージとしては表示しない
            } else if (user_store.user === null) {
                console.warn('[LiveCommentManager][WatchSession] Failed to get Nicolive watch session URL. (Not logged in to KonomiTV)');

            // ニコニコアカウントと連携していないために視聴セッション WebSocket URL を取得できなかった: コンソールにのみ警告を表示
            // ニコニコ実況を使わない人にとって、わざわざ設定をオフにしないとこのメッセージが消せないのはストレスなので、警告メッセージとしては表示しない
            } else if (user_store.user?.niconico_user_id === null) {
                console.warn('[LiveCommentManager][WatchSession] Failed to get Nicolive watch session URL. (Not linked with Niconico account)');

            // ニコニコ生放送からエラーが返された: 普通発生しないため警告メッセージとして表示
            } else if (websocket_info.nicolive_watch_session_error !== null) {
                console.warn(`[LiveCommentManager][WatchSession] Failed to get Nicolive watch session URL. (${websocket_info.nicolive_watch_session_error})`);
                this.player.notice(`${websocket_info.nicolive_watch_session_error}代わりに NX-Jikkyo にコメントします。`, undefined, undefined, '#FFA86A');
            }
        }

        // 視聴セッション WebSocket を開く
        console.log(`[LiveCommentManager][WatchSession] Connected to ${watch_session_url}`);
        this.watch_session = new WebSocket(watch_session_url);

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
        const on_close = async (event: CloseEvent | Event) => {

            // すでに disconnect メッセージが送られてきている場合は何もしない
            if (is_disconnect_message_received === true) {
                return;
            }

            // 接続切断の理由を表示
            const code = (event instanceof CloseEvent) ? event.code : 'Error';
            if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
                this.player.notice(`${this.watch_session_type}との接続が切断されました。(Code: ${code})`, undefined, undefined, '#FF6F6A');
            }
            console.error(`[LiveCommentManager][WatchSession] Connection closed. (Code: ${code})`);

            // 3 秒ほど待ってから再接続する
            // ニコ生側から切断された場合と異なりネットワークが切断された可能性が高いので、間を多めに取る
            await Utils.sleep(3);
            await this.reconnect();

        };
        this.watch_session.addEventListener('close', on_close, { signal: this.abort_controller.signal });
        this.watch_session.addEventListener('error', on_close, { signal: this.abort_controller.signal });

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

                    let error = `${this.watch_session_type}でエラーが発生しています。(Code: ${message.data.code})`;
                    switch (message.data.code) {
                        case 'CONNECT_ERROR':
                            error = `${this.watch_session_type}のコメントサーバーに接続できません。`;
                            break;
                        case 'CONTENT_NOT_READY':
                            error = `${this.watch_session_type}が配信できない状態です。`;
                            break;
                        case 'NO_THREAD_AVAILABLE':
                            error = `${this.watch_session_type}のコメントスレッドを取得できません。`;
                            break;
                        case 'NO_ROOM_AVAILABLE':
                            error = `${this.watch_session_type}のコメント部屋を取得できません。`;
                            break;
                        case 'NO_PERMISSION':
                            error = `${this.watch_session_type}の API にアクセスする権限がありません。`;
                            break;
                        case 'NOT_ON_AIR':
                            error = `${this.watch_session_type}が放送中ではありません。`;
                            break;
                        case 'BROADCAST_NOT_FOUND':
                            error = `${this.watch_session_type}の配信情報を取得できません。`;
                            break;
                        case 'INTERNAL_SERVERERROR':
                            error = `${this.watch_session_type}でサーバーエラーが発生しています。`;
                            break;
                    }

                    // エラー情報を表示
                    if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
                        this.player.notice(error, undefined, undefined, '#FF6F6A');
                    }
                    console.error(`[LiveCommentManager][WatchSession] Error occurred. (Code: ${message.data.code})`);

                    // 3 秒ほど待ってから再接続する
                    await Utils.sleep(3);
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
                    let disconnect_reason = `${this.watch_session_type}との接続が切断されました。(${message.data.reason})`;
                    switch (message.data.reason) {
                        case 'TAKEOVER':
                            disconnect_reason = `${this.watch_session_type}の番組から追い出されました。`;
                            break;
                        case 'NO_PERMISSION':
                            disconnect_reason = `${this.watch_session_type}の番組の座席を取得できませんでした。`;
                            break;
                        case 'END_PROGRAM':
                            disconnect_reason = `${this.watch_session_type}がリセットされたか、コミュニティの番組が終了しました。`;
                            break;
                        case 'PING_TIMEOUT':
                            disconnect_reason = 'コメントサーバーとの接続生存確認に失敗しました。';
                            break;
                        case 'TOO_MANY_CONNECTIONS':
                            disconnect_reason = `${this.watch_session_type}の同一ユーザからの接続数上限を越えています。`;
                            break;
                        case 'TOO_MANY_WATCHINGS':
                            disconnect_reason = `${this.watch_session_type}の同一ユーザからの視聴番組数上限を越えています。`;
                            break;
                        case 'CROWDED':
                            disconnect_reason = `${this.watch_session_type}の番組が満席です。`;
                            break;
                        case 'MAINTENANCE_IN':
                            disconnect_reason = `${this.watch_session_type}はメンテナンス中です。`;
                            break;
                        case 'SERVICE_TEMPORARILY_UNAVAILABLE':
                            disconnect_reason = `${this.watch_session_type}で一時的にサーバーエラーが発生しています。`;
                            break;
                    }

                    // 接続切断の理由を表示
                    if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
                        this.player.notice(disconnect_reason, undefined, undefined, '#FF6F6A');
                    }
                    console.error(`[LiveCommentManager][WatchSession] Disconnected. (Reason: ${message.data.reason})`);

                    // 3 秒ほど待ってから再接続する
                    await Utils.sleep(3);
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

                // 2024/08/05 以降のニコニコ生放送では room メッセージは廃止されており、現在は NX-Jikkyo のみが送信している
                if (message.type === 'room') {

                    // vpos の基準時刻のタイムスタンプを取得 (ミリ秒単位)
                    // vpos は番組開始時間からの累計秒数
                    this.vpos_base_timestamp = dayjs(message.data.vposBaseTime).valueOf();

                    // コメントサーバーへの接続情報を返す
                    console.log(`[LiveCommentManager][WatchSession] Connected.\nThread ID: ${message.data.threadId}`);
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

                // 2024/08/05 以降のニコニコ生放送では room メッセージの代わりに messageServer メッセージが送信されてくる
                // messageServer メッセージでは NDGR 新メッセージサーバーへの接続先 URL が返されるが、以前と異なり WebSocket ではないため
                // CORS 制限で直接接続することはできずプロトコルも全く別物なので、コメントセッションは常に NX-Jikkyo のニコニコ生放送互換 API に接続する
                } else if (message.type === 'messageServer') {

                    // vpos の基準時刻のタイムスタンプを取得 (ミリ秒単位)
                    // vpos は番組開始時間からの累計秒数
                    this.vpos_base_timestamp = dayjs(message.data.vposBaseTime).valueOf();

                    // hashedUserId: 匿名コメント投稿時に用いられる自身のユーザ ID (ログインユーザのみ取得可能)
                    // 自身が投稿したコメントかどうかを判別する上で使用可能
                    const hashed_user_id = message.data.hashedUserId;

                    // コメントサーバーへの接続情報を返す
                    console.log('[LiveCommentManager][WatchSession] Connected.');
                    return resolve({
                        is_success: true,
                        detail: '視聴セッションを取得しました。',
                        // コメントサーバーへの接続情報
                        // 常に NX-Jikkyo のニコニコ生放送互換 API に接続する
                        message_server_url: websocket_info.comment_session_url!,
                        // コメントサーバー上のスレッド ID
                        // 現在放送中 (アクティブ) なスレッドに自動接続するために意図的に空文字を設定
                        thread_id: '',
                        // メッセージサーバーから受信するコメント (chat メッセージ) に yourpost フラグを付けるためのキー
                        // NX-Jikkyo のニコニコ生放送互換 API において、yourPostKey (threadkey) はコメントのユーザー ID と同一
                        // ニコニコ実況から NX-Jikkyo にインポートされたコメントのユーザー ID には nicolive: の Prefix が付与される仕様を利用し、
                        // ハッシュ化された匿名ユーザー ID から NX-Jikkyo 上で使える threadkey を算出している
                        your_post_key: `nicolive:${hashed_user_id}`,
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
        const user_store = useUserStore();

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
                        res_from: -100,  // 最初にコメントを 100 個送信する
                    }
                },
                {ping: {content: 'pf:0'}},
                {ping: {content: 'rf:0'}},
            ]));

        }, { signal: this.abort_controller.signal });

        // コメントセッションの接続が閉じられたとき（ネットワークが切断された場合など）
        const on_close = async (event: CloseEvent | Event) => {

            // 接続切断の理由を表示
            const code = (event instanceof CloseEvent) ? event.code : 'Error';
            if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
                this.player.notice(`NX-Jikkyo との接続が切断されました。(Code: ${code})`, undefined, undefined, '#FF6F6A');
            }
            console.error(`[LiveCommentManager][CommentSession] Connection closed. (Code: ${code})`);

            // 3 秒ほど待ってから再接続する
            // ニコ生側から切断された場合と異なりネットワークが切断された可能性が高いので、間を多めに取る
            // 視聴セッション側が同時に切断され再接続中の場合、this.reconnect() は何も行わない
            await Utils.sleep(3);
            await this.reconnect();
        };
        this.comment_session.addEventListener('close', on_close, { signal: this.abort_controller.signal });
        this.comment_session.addEventListener('error', on_close, { signal: this.abort_controller.signal });

        // 受信したコメントをイベントリスナーに送信する関数
        // スロットルを設定し、333ms 未満の間隔でイベントが発火しないようにする
        const emit_comments = throttle(() => {
            if (Utils.isSafari() === false) {
                console.debug('[LiveCommentManager][CommentSession] Comments buffer length:', comments_buffer.length);
            }
            if (this.destroyed === false) {  // まだ破棄されていない場合のみイベントを発火
                player_store.event_emitter.emit('CommentReceived', {
                    is_initial_comments: false,
                    comments: comments_buffer,
                });
            }
            // バッファを空にする
            comments_buffer.length = 0;
        }, 333);

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
                if (this.destroyed === false) {  // まだ破棄されていない場合のみイベントを発火
                    player_store.event_emitter.emit('CommentReceived', {
                        is_initial_comments: true,
                        comments: initial_comments_buffer,
                    });
                }
                return;
            }

            // コメントデータを取得
            const comment = message.chat;

            // コメントデータが不正な場合 or 自分が投稿したコメントの場合は弾く
            // ただし初期コメント受信中のみ、自分が投稿したコメントであっても通常コメント同様に続行する
            // yourpost キーが設定されているコメントだけでなく、非匿名コメントにおいてニコニコユーザー ID が一致するコメントも弾く
            // ニコニコ実況に投稿された非匿名コメントのユーザー ID は nicolive:1234567 のような形式で送信されてくる
            if ((comment === undefined || comment.content === undefined || comment.content === '') ||
                (comment.yourpost && comment.yourpost === 1 && initial_comments_received === true) ||
                (user_store.user?.niconico_user_id?.toString() === comment.user_id.replace('nicolive:', ''))) {
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
                time: Utils.apply28HourClock(dayjs(comment.date * 1000).format('HH:mm:ss')),
                playback_position: this.player.video.currentTime,
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
            const comment_delay_time = Math.max(buffered_end - this.player.video.currentTime, 0);
            if (Utils.isSafari() === false) {
                console.debug(`[LiveCommentManager][CommentSession] Delay: ${comment_delay_time} sec.`);
            }
            await Utils.sleep(comment_delay_time);

            // コメントを一時バッファに格納し、スロットルを設定してイベントリスナーに送信する
            // コメントの受信間隔が 333ms 以上あれば、今回のコールバックで取得したコメントがダイレクトにイベントリスナーに送信される
            comments_buffer.push(comment_data);
            emit_comments();

            // プレイヤーにコメントを描画する (映像再生時のみ)
            if (this.player.video.paused === false) {
                this.player.danmaku!.draw({
                    text: comment.content,
                    color: color,
                    type: position,
                    size: size,
                });
            }

        }, { signal: this.abort_controller.signal });
    }


    /**
     * ニコニコ実況または NX-Jikkyo にコメントを送信する
     * DPlayer からコメントオプションを受け取り、成功 or 失敗をコールバックで通知する
     * @param options DPlayer のコメントオプション
     */
    public sendComment(options: DPlayerType.APIBackendSendOptions): void {
        const player_store = usePlayerStore();
        const settings_store = useSettingsStore();
        const user_store = useUserStore();

        // 初期化に失敗しているときは実行せず、保存しておいたエラーメッセージを表示する
        if (player_store.live_comment_init_failed_message !== null) {
            options.error(player_store.live_comment_init_failed_message);
            return;
        }

        // 「可能であればニコニコ実況にコメントする」がオンかつニコニコアカウントと連携できていないときは、
        // フォールバックで代わりに NX-Jikkyo にコメントが投稿される旨を通知する
        if (settings_store.settings.prefer_posting_to_nicolive === true) {
            if (user_store.user === null) {
                this.player.notice('ニコニコ実況にコメントするには、KonomiTV アカウントにログインしてください。代わりに NX-Jikkyo にコメントします。',
                    undefined, undefined, '#FFA86A');
            } else if (user_store.user.niconico_user_id === null) {
                this.player.notice('ニコニコ実況にコメントするには、ニコニコアカウントと連携してください。代わりに NX-Jikkyo にコメントします。',
                    undefined, undefined, '#FFA86A');
            }
        }

        // 視聴セッションの接続先がニコニコ生放送のときのみのバリデーション
        if (this.watch_session_type === 'ニコニコ実況') {
            if (user_store.user?.niconico_user_premium === false && (options.data.type === 'top' || options.data.type === 'bottom')) {
                options.error('ニコニコ実況でコメントを上下に固定するには、ニコニコアカウントのプレミアム会員登録が必要です。');
                return;
            }
            if (user_store.user?.niconico_user_premium === false && options.data.size === 'big') {
                options.error('ニコニコ実況でコメントサイズを大きめに設定するには、ニコニコアカウントのプレミアム会員登録が必要です。');
                return;
            }
        }

        // 視聴セッションが null か、接続が既に切れている場合
        if (this.watch_session === null || this.watch_session.readyState !== WebSocket.OPEN) {
            console.error('[LiveCommentManager][WatchSession] Comment sending failed. (Connection is not established.)');
            options.error('コメントの送信に失敗しました。WebSocket 接続が確立されていません。');
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

                    // 送信したコメントを整形してコメントリストに送信
                    player_store.event_emitter.emit('CommentSendCompleted', {
                        comment: {
                            id: Utils.time(),  // ID は取得できないので現在の時間をユニークな ID として利用する
                            text: options.data.text,  // コメント本文
                            time: Utils.apply28HourClock(dayjs().format('HH:mm:ss')),  // 現在時刻
                            playback_position: this.player.video.currentTime,  // 現在の再生位置
                            user_id: `${user_store.user?.niconico_user_id ?? 'Unknown'}`,  // ニコニコユーザー ID
                            my_post: true,  // 自分のコメントであることを示すフラグ
                        }
                    });

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
     * 同じ設定でニコニコ実況または NX-Jikkyo に再接続する
     */
    private async reconnect(): Promise<void> {
        const player_store = usePlayerStore();

        // 現在再接続中ではない && 視聴セッションとコメントセッションのどちらも開かれている場合のみ終了
        // 現在再接続中であっても視聴セッションとコメントセッションのどちらかが閉じられている場合は、
        // this.initWatchSession() から再帰的に reconnect() が呼ばれた可能性が高いため続行する
        const is_watch_session_closed = (this.watch_session !== null &&
            (this.watch_session.readyState === WebSocket.CLOSING || this.watch_session.readyState === WebSocket.CLOSED));
        const is_comment_session_closed = (this.comment_session !== null &&
            (this.comment_session.readyState === WebSocket.CLOSING || this.comment_session.readyState === WebSocket.CLOSED));
        if (this.reconnecting === true &&
            is_watch_session_closed === false &&
            is_comment_session_closed === false) {
            return;
        }

        // 再接続を開始
        this.reconnecting = true;
        console.warn('[LiveCommentManager] Reconnecting...');
        if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
            this.player.notice(`${this.watch_session_type}に再接続しています…`);
        }

        // 前の視聴セッション・コメントセッションを破棄
        await this.destroy();

        // 視聴セッションを再初期化
        const watch_session_info = await this.initWatchSession();
        if (watch_session_info.is_success === false) {

            // 初期化に失敗した際のエラーメッセージを設定する
            // UI 側のエラー表示に利用されるほか、null から string になったことで初期化に失敗したことを示す
            player_store.live_comment_init_failed_message = watch_session_info.detail;
            console.error('[LiveCommentManager] Reconnection failed.');

            // 無条件にエラーメッセージをプレイヤーに通知
            if (this.player.template.notice.textContent!.includes('再起動しています…') === false) {
                this.player.notice(watch_session_info.detail, undefined, undefined, '#FF6F6A');
            }

            // 視聴セッションへの接続情報自体を取得できなかったので再接続を諦める
            // 視聴セッションへの接続情報は取得できたが、また WebSocket が予期せず閉じられてしまった場合は
            // 上記 this.initWatchSession() 内で再度この this.reconnect() が再帰的に呼ばれる
            this.reconnecting = false;
            return;
        }

        // 視聴セッションを初期化できた場合のみ、
        // 取得したコメントサーバーへの接続情報を使い、非同期でコメントセッションを初期化
        this.initCommentSession(watch_session_info);

        // ここまできたら再初期化が完了しているので破棄済みかどうかのフラグを false にする
        // ここでフラグを false にしないと再接続後にコメントリストにコメントが送信されない
        this.destroyed = false;

        // 再接続完了
        this.reconnecting = false;
        console.warn('[LiveCommentManager] Reconnected.');
    }


    /**
     * 視聴セッションとコメントセッションをそれぞれ閉じる
     */
    public async destroy(): Promise<void> {
        const player_store = usePlayerStore();

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

        // 初期化に失敗した際のエラーメッセージを削除
        player_store.live_comment_init_failed_message = null;

        // 破棄済みかどうかのフラグを立てる
        this.destroyed = true;

        console.log('[LiveCommentManager] Destroyed.');
    }
}

export default LiveCommentManager;
