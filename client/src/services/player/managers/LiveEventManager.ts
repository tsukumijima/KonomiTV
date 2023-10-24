
import assert from 'assert';

import DPlayer from 'dplayer';

import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';


/** ライブストリームステータス API から受信するイベントのインターフェイス */
interface ILiveStreamStatusEvent {
    // 現在のライブストリームのステータス
    status: 'Offline' | 'Standby' | 'ONAir' | 'Idling' | 'Restart';
    // 現在のライブストリームのステータス詳細
    detail: string;
    // ライブストリームの開始時刻 (UNIX タイムスタンプ)
    started_at: number;
    // ライブストリームの最終更新時刻 (UNIX タイムスタンプ)
    updated_at: number;
    // このライブストリームを視聴しているクライアント数
    client_count: number;
}


/**
 * ライブ視聴: ライブストリームのステータスを監視し随時 UI に反映する PlayerManager
 */
class LiveEventManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerWrapper に示す値
    public readonly restart_required_when_quality_switched = true;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // EventSource のインスタンス
    private eventsource: EventSource | null = null;

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     */
    constructor(player: DPlayer) {
        this.player = player;
    }


    /**
     * サーバー側のライブストリームステータス API (Server-Sent Events) に接続し、ライブストリームのステータス監視を開始する
     */
    public async init(): Promise<void> {
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();

        // EventSource を初期化し、Server-Sent Events のストリーミングを開始する
        // PlayerManager の設計上、同一の PlayerManager インスタンスはチャンネルが変更されない限り再利用される可能性がある
        // 接続先の API URL は DPlayer 上で再生中の画質設定によって変化するため、
        // 画質切り替え後の再起動も想定しコンストラクタではなくあえて init() 内で API URL を取得している
        const eventsource_url = this.player.quality!.url.replace('/mpegts', '/events');
        this.eventsource = new EventSource(eventsource_url);

        // 初回接続時のイベント
        this.eventsource.addEventListener('initial_update', (event_raw: MessageEvent) => {

            // イベントを取得
            const event: ILiveStreamStatusEvent = JSON.parse(event_raw.data);
            console.log(`[initial_update] Status: ${event.status} / Detail: ${event.detail}`);

            // ステータスごとに処理を振り分け
            switch (event.status) {

                // Status: Standby
                case 'Standby': {

                    // バッファリング中の Progress Circular を表示
                    player_store.is_video_buffering = true;

                    // プレイヤーの背景を表示する
                    player_store.is_background_display = true;

                    break;
                }
            }
        });

        // ステータスが更新されたときのイベント
        this.eventsource.addEventListener('status_update', async (event_raw: MessageEvent) => {

            // イベントを取得
            const event: ILiveStreamStatusEvent = JSON.parse(event_raw.data);
            console.log(`[status_update] Status: ${event.status} / Detail: ${event.detail}`);

            // 視聴者数を更新
            channels_store.updateChannel(channels_store.display_channel_id, {
                ...channels_store.channel.current,
                viewer_count: event.client_count,
            });

            // ステータスごとに処理を振り分け
            switch (event.status) {

                // Status: Standby
                case 'Standby': {

                    // ステータス詳細をプレイヤーに表示
                    if (this.player.template.notice.textContent!.includes('画質を') === false) {  // 画質切り替えの通知なら上書きしない
                        this.player.notice(event.detail, -1);
                    }

                    // バッファリング中の Progress Circular を表示
                    player_store.is_video_buffering = true;

                    // プレイヤーの背景を表示する
                    player_store.is_background_display = true;

                    break;
                }

                // Status: ONAir
                case 'ONAir': {

                    // ステータス詳細をプレイヤーから削除
                    if (this.player.template.notice.textContent!.includes('画質を') === false) {  // 画質切り替えの通知なら上書きしない
                        this.player.notice(this.player.template.notice.textContent!, 0.000001);
                    }

                    // ライブストリーミングが開始される前にチャンネルを切り替えた際、稀にコメントが流れないことがある不具合のワークアラウンド
                    // TODO: リファクタリングで不要になってるかも？
                    if (this.player.container.classList.contains('dplayer-paused')) {
                        this.player.container.classList.remove('dplayer-paused');
                        this.player.container.classList.add('dplayer-playing');
                    }

                    // 前のプレイヤーインスタンスの Picture-in-Picture ウインドウが残っている場合、終了させてからもう一度切り替える
                    // チャンネル切り替えが完了しても前の Picture-in-Picture ウインドウは再利用されないため、一旦終了させるしかない
                    if (document.pictureInPictureElement) {
                        document.exitPictureInPicture();
                        this.player.video.requestPictureInPicture();
                    }

                    break;
                }

                // Status: Idling
                case 'Idling': {

                    // 本来誰も視聴していないことを示す Idling ステータスを受信している場合、何らかの理由で
                    // ライブストリーミング API への接続が切断された可能性が高いので、PlayerWrapper にプレイヤーロジックの再起動を要求する
                    player_store.event_emitter.emit('PlayerRestartRequired', {
                        message: 'ストリーミング接続が切断されました。プレイヤーロジックを再起動しています…',
                    });

                    break;
                }

                // Status: Restart
                case 'Restart': {

                    // エンコーダーがクラッシュしたなどの理由でライブストリームが再起動中なので、
                    // PlayerWrapper にプレイヤーロジックの再起動を要求する
                    player_store.event_emitter.emit('PlayerRestartRequired', {
                        // ステータス詳細 (再起動に至った理由) をプレイヤーに表示
                        message: event.detail,
                    });

                    // バッファリング中の Progress Circular を表示 (不要だとは思うけど念のため)
                    player_store.is_video_buffering = true;

                    // プレイヤーの背景を表示する (不要だとは思うけど念のため)
                    player_store.is_background_display = true;

                    break;
                }

                // Status: Offline
                // 基本的に Offline は放送休止中やエラーなどで復帰の見込みがない状態
                case 'Offline': {

                    // 「ライブストリームは Offline です。」のステータス詳細を受信すること自体が不正な状態
                    // ストリーミング API への接続が切断された可能性が高いので、PlayerWrapper にプレイヤーロジックの再起動を要求する
                    if (event.detail === 'ライブストリームは Offline です。') {
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: 'ストリーミング接続が切断されました。プレイヤーロジックを再起動しています…',
                        });
                    }

                    // ステータス詳細をプレイヤーに表示
                    this.player.notice(event.detail, -1);
                    this.player.video.onerror = () => {
                        // 動画の読み込みエラーが送出された際に DPlayer に表示中の通知メッセージを上書きする
                        this.player.notice(event.detail, -1);
                        this.player.video.onerror = null;
                    };

                    // 既に描画されたコメントをクリア
                    this.player.danmaku!.clear();

                    // 動画を停止する
                    this.player.video.pause();

                    // プレイヤーの背景を表示する
                    player_store.is_background_display = true;

                    // バッファリング中の Progress Circular を非表示にする
                    player_store.is_loading = false;
                    player_store.is_video_buffering = false;

                    break;
                }
            }
        });

        // ステータス詳細が更新されたときのイベント
        this.eventsource.addEventListener('detail_update', (event_raw: MessageEvent) => {

            // イベントを取得
            const event: ILiveStreamStatusEvent = JSON.parse(event_raw.data);
            console.log(`[detail_update] Status: ${event.status} Detail:${event.detail}`);

            // 視聴者数を更新
            channels_store.updateChannel(channels_store.display_channel_id, {
                ...channels_store.channel.current,
                viewer_count: event.client_count,
            });

            // ステータスごとに処理を振り分け
            switch (event.status) {

                // Status: Standby
                case 'Standby': {

                    // ステータス詳細をプレイヤーに表示
                    this.player.notice(event.detail, -1);

                    // プレイヤーの背景を表示する
                    player_store.is_background_display = true;

                    break;
                }
            }
        });

        // クライアント数 (だけ) が更新されたときのイベント
        this.eventsource.addEventListener('clients_update', (event_raw: MessageEvent) => {

            // イベントを取得
            const event: ILiveStreamStatusEvent = JSON.parse(event_raw.data);

            // 視聴者数を更新
            channels_store.updateChannel(channels_store.display_channel_id, {
                ...channels_store.channel.current,
                viewer_count: event.client_count,
            });
        });
    }


    /**
     * サーバー側のライブストリームステータス API (Server-Sent Events) への接続を切断し、ライブストリームのステータス監視を停止する
     */
    public async destroy(): Promise<void> {
        assert(this.eventsource !== null);

        // EventSource を破棄し、Server-Sent Events のストリーミングを終了する
        this.eventsource.close();
        this.eventsource = null;
    }
}

export default LiveEventManager;
