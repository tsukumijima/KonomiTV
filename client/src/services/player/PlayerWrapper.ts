
import assert from 'assert';

import DPlayer, { DPlayerType } from 'dplayer';
import mpegts from 'mpegts.js';

import APIClient from '@/services/APIClient';
import LiveDataBroadcastingManager from '@/services/player/managers/LiveDataBroadcastingManager';
import LiveEventManager from '@/services/player/managers/LiveEventManager';
import MediaSessionManager from '@/services/player/managers/MediaSessionManager';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { PlayerUtils } from '@/utils';


/**
 * 動画プレイヤーである DPlayer に関連するロジックを丸ごとラップするクラスで、動画再生系ロジックの中核を担う
 * DPlayer の初期化後は DPlayer のイベントなどに合わせて、イベントハンドラーや PlayerManager を管理する
 * このクラスはコンストラクタで指定されたチャンネル or 録画番組の再生に責任を持ち、
 * 他のチャンネル or 録画番組に切り替えられた際は別途新しい PlayerWrapper を作成する
 * await destroy() 後に再度 await init() すると、コンストラクタで設定したチャンネル or 録画番組の動画プレイヤーを再起動できる
 */
class PlayerWrapper {

    // ライブ視聴: 低遅延モードオンでの再生バッファ (秒単位)
    // 0.7 秒程度余裕を持たせる
    private static readonly LIVE_PLAYBACK_BUFFER_SECONDS_LOW_LATENCY = 0.7;

    // ライブ視聴: 低遅延モードオフでの再生バッファ (秒単位)
    // 5秒程度の遅延を許容する
    private static readonly LIVE_PLAYBACK_BUFFER_SECONDS = 5.0;

    // DPlayer のインスタンス
    private player: DPlayer | null = null;

    // それぞれの PlayerManager のインスタンスのリスト
    private player_managers: PlayerManager[] = [];

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // ライブ視聴: 許容する HTMLMediaElement の内部再生バッファの秒数
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly live_playback_buffer_seconds: number;

    // ライブ視聴: mpegts.js のバッファ詰まり対策で定期的に強制シークするインターバルのタイマー ID
    // 保持しておかないと clearInterval() でタイマーを止められない
    private live_force_seek_interval_timer_id: number = 0;

    // handlePlayerControlUIVisibility() で利用するタイマー ID
    // 保持しておかないと clearTimeout() でタイマーを止められない
    private player_control_ui_hide_timer_id: number = 0;

    // RomSound の AudioContext と AudioBuffer のリスト
    private readonly romsounds_context: AudioContext = new AudioContext();
    private readonly romsounds_buffers: AudioBuffer[] = [];

    // 破棄済みかどうか
    private destroyed = false;


    /**
     * コンストラクタ
     * 実際の DPlayer の初期化処理は await init() で行われる
     */
    constructor(playback_mode: 'Live' | 'Video') {

        // 再生モードをセット
        this.playback_mode = playback_mode;

        // 低遅延モードであれば低遅延向けの再生バッファを、そうでなければ通常の再生バッファをセット (秒単位)
        const settings_store = useSettingsStore();
        this.live_playback_buffer_seconds = settings_store.settings.tv_low_latency_mode ?
            PlayerWrapper.LIVE_PLAYBACK_BUFFER_SECONDS_LOW_LATENCY : PlayerWrapper.LIVE_PLAYBACK_BUFFER_SECONDS;

        // 01 ~ 14 まですべての RomSound を読み込む
        for (let index = 1; index <= 14; index++) {
            (async () => {
                // ArrayBuffer をデコードして AudioBuffer にし、すぐ呼び出せるように貯めておく
                // ref: https://ics.media/entry/200427/
                const romsound_url = `/assets/romsounds/${index.toString().padStart(2, '0')}.wav`;
                const romsound_response = await APIClient.get<ArrayBuffer>(romsound_url, {
                    baseURL: '',  // BaseURL を明示的にクライアントのルートに設定
                    responseType: 'arraybuffer',
                });
                if (romsound_response.type === 'success') {
                    this.romsounds_buffers.push(await this.romsounds_context.decodeAudioData(romsound_response.data));
                }
            })();
        }
    }


    /**
     * DPlayer と PlayerManager を初期化し、再生準備を行う
     */
    public async init(): Promise<void> {
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();
        const settings_store = useSettingsStore();

        // 破棄済みかどうかのフラグを下ろす
        this.destroyed = false;

        // mpegts.js を window 直下に入れる
        // こうしないと DPlayer が mpegts.js を認識できない
        (window as any).mpegts = mpegts;

        // DPlayer を初期化
        this.player = new DPlayer({
            // DPlayer を配置する要素
            container: document.querySelector<HTMLDivElement>('.watch-player__dplayer')!,
            // テーマカラー
            theme: '#E64F97',
            // 言語 (日本語固定)
            lang: 'ja-jp',
            // ライブモード (ビデオ視聴では無効)
            live: this.playback_mode === 'Live' ? true : false,
            // ライブモードで同期する際の最小バッファサイズ
            liveSyncMinBufferSize: this.live_playback_buffer_seconds - 0.1,
            // ループ再生 (ライブ視聴では無効)
            loop: this.playback_mode === 'Live' ? false : true,
            // 自動再生
            autoplay: true,
            // AirPlay 機能 (うまく動かないため無効化)
            airplay: false,
            // ショートカットキー（こちらで制御するため無効化）
            hotkey: false,
            // スクリーンショット (こちらで制御するため無効化)
            screenshot: false,
            // CORS を有効化
            crossOrigin: 'anonymous',
            // 音量の初期値
            volume: 1.0,

            // 動画の設定
            video: (() => {

                // 画質リスト
                const qualities: DPlayerType.VideoQuality[] = [];

                // 画質の種類
                const quality_names = ['1080p-60fps', '1080p', '810p', '720p', '540p', '480p', '360p', '240p'];

                // ブラウザが H.265 / HEVC の再生に対応していて、かつ通信節約モードが有効なとき
                // API に渡す画質に -hevc のプレフィックスをつける
                let hevc_prefix = '';
                if (PlayerUtils.isHEVCVideoSupported() && settings_store.settings.tv_data_saver_mode === true) {
                    hevc_prefix = '-hevc';
                }

                // ライブ視聴: チャンネル情報がセットされているはず
                if (this.playback_mode === 'Live') {

                    // ラジオチャンネルの場合
                    // API が受け付ける画質の値は通常のチャンネルと同じだが (手抜き…)、実際の画質は 48KHz/192kbps で固定される
                    // ラジオチャンネルの場合は、1080p と渡しても 48kHz/192kbps 固定の音声だけの MPEG-TS が配信される
                    if (channels_store.channel.current.is_radiochannel === true) {
                        qualities.push({
                            name: '48kHz/192kbps',
                            type: 'mpegts',
                            url: `${Utils.api_base_url}/streams/live/${channels_store.channel.current.display_channel_id}/1080p/mpegts`,
                        });

                    // 通常のチャンネルの場合
                    } else {

                        // 画質リストを作成
                        for (const quality_name of quality_names) {
                            qualities.push({
                                // 1080p-60fps のみ、見栄えの観点から表示上 "1080p (60fps)" と表示する
                                name: quality_name === '1080p-60fps' ? '1080p (60fps)' : quality_name,
                                type: 'mpegts',
                                url: `${Utils.api_base_url}/streams/live/${channels_store.channel.current.display_channel_id}/${quality_name}${hevc_prefix}/mpegts`,
                            });
                        }
                    }

                    // デフォルトの画質
                    // ラジオチャンネルのみ常に 48KHz/192kbps に固定する
                    let default_quality: string = settings_store.settings.tv_streaming_quality;
                    if (channels_store.channel.current.is_radiochannel) {
                        default_quality = '48kHz/192kbps';
                    }

                    return {
                        quality: qualities,
                        defaultQuality: default_quality,
                    };

                // ビデオ視聴: 録画番組情報がセットされているはず
                } else {

                    // 画質リストを作成
                    for (const quality_name of quality_names) {
                        qualities.push({
                            // 1080p-60fps のみ、見栄えの観点から表示上 "1080p (60fps)" と表示する
                            name: quality_name === '1080p-60fps' ? '1080p (60fps)' : quality_name,
                            type: 'hls',
                            // TODO: API URL は未実装なので適当な値を入れておく
                            url: `${Utils.api_base_url}/streams/video/${player_store.recorded_program.id}/${quality_name}${hevc_prefix}/playlist`,
                        });
                    }

                    // TODO: 未実装なので適当な値を返す
                    // 録画ではラジオは考慮しない
                    return {
                        quality: qualities,
                        defaultQuality: '1080p',  // TODO: 未実装なので適当に決めうち
                    };
                }
            })(),

            // コメントの設定
            danmaku: {
                // コメントするユーザー名: 便宜上 KonomiTV に固定 (実際には利用されない)
                user: 'KonomiTV',
                // コメントの流れる速度
                speedRate: settings_store.settings.comment_speed_rate,
                // コメントのフォントサイズ
                fontSize: settings_store.settings.comment_font_size,
                // コメント送信後にコメントフォームを閉じるかどうか
                closeCommentFormAfterSend: settings_store.settings.close_comment_form_after_sending,
            },

            // コメント API バックエンドの設定
            apiBackend: {
                // コメント取得時
                read: (options) => {
                    // ライブ視聴: 空の配列を返す (こうするとコメント0件と認識される)
                    if (this.playback_mode === 'Live') {
                        options.success([]);
                    // ビデオ視聴: 過去ログコメントを取得して返す
                    } else {
                        // TODO: 未実装
                        options.success([]);
                    }
                },
                // コメント送信時
                send: async (options) => {
                    // ライブ視聴: コメントを送信する
                    if (this.playback_mode === 'Live') {
                        // TODO: 未実装
                        options.success();
                    // ビデオ視聴: 過去ログにはコメントできないのでエラーを返す
                    } else {
                        options.error('過去ログ再生中はコメントできません。');
                    }
                },
            },

            // 字幕の設定
            subtitle: {
                type: 'aribb24',  // aribb24.js を有効化
            },

            // 再生プラグインの設定
            pluginOptions: {
                // mpegts.js
                mpegts: {
                    config: {
                        // Web Worker を有効にする
                        enableWorker: true,
                        // Media Source Extensions API 向けの Web Worker を有効にする
                        // メインスレッドから再生処理を分離することで、低スペック端末で DOM 描画の遅延が影響して映像再生が詰まる問題が解消される
                        // MSE in Workers が使えるかは MediaSource.canConstructInDedicatedWorker が true かどうかで判定できる
                        // MediaSource.canConstructInDedicatedWorker は TypeScript の仕様上型定義の追加が難しいため any で回避している
                        // ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaSource/canConstructInDedicatedWorker_static
                        enableMSEWorker: window.MediaSource && (window.MediaSource as any).canConstructInDedicatedWorker === true,
                        // IO 層のバッファを禁止する
                        enableStashBuffer: false,
                        // HTMLMediaElement の内部バッファによるライブストリームの遅延を追跡する
                        // liveBufferLatencyChasing と異なり、いきなり再生時間をスキップするのではなく、
                        // 再生速度を少しだけ上げることで再生を途切れさせることなく遅延を追跡する
                        liveSync: settings_store.settings.tv_low_latency_mode,
                        // 許容する HTMLMediaElement の内部バッファの最大値 (秒単位, 3秒)
                        liveSyncMaxLatency: 3,
                        // HTMLMediaElement の内部バッファ (遅延) が liveSyncMaxLatency を超えたとき、ターゲットとする遅延時間 (秒単位)
                        liveSyncTargetLatency: this.live_playback_buffer_seconds,
                        // ライブストリームの遅延の追跡に利用する再生速度 (x1.1)
                        // 遅延が 3 秒を超えたとき、遅延が playback_buffer_sec を下回るまで再生速度が x1.1 に設定される
                        liveSyncPlaybackRate: 1.1,
                    }
                },
                // aribb24.js
                aribb24: {
                    // 文字スーパーを表示するかどうか
                    disableSuperimposeRenderer: settings_store.settings.tv_show_superimpose === false,
                    // 描画フォント
                    normalFont: `"${settings_store.settings.caption_font}", "Rounded M+ 1m for ARIB", sans-serif`,
                    // 縁取りする色
                    forceStrokeColor: settings_store.settings.always_border_caption_text,
                    // 背景色
                    forceBackgroundColor: (() => {
                        if (settings_store.settings.specify_caption_opacity === true) {
                            const opacity = settings_store.settings.caption_opacity;
                            return `rgba(0, 0, 0, ${opacity})`;
                        } else {
                            return undefined;
                        }
                    })(),
                    // DRCS 文字を対応する Unicode 文字に置換
                    drcsReplacement: true,
                    // 高解像度の字幕 Canvas を取得できるように
                    enableRawCanvas: true,
                    // 縁取りに strokeText API を利用
                    useStroke: true,
                    // Unicode 領域の代わりに私用面の領域を利用 (Windows TV 系フォントのみ)
                    usePUA: (() => {
                        const font = settings_store.settings.caption_font;
                        const context = document.createElement('canvas').getContext('2d')!;
                        context.font = '10px "Rounded M+ 1m for ARIB"';
                        context.fillText('Test', 0, 0);
                        context.font = `10px "${font}"`;
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
                        if (settings_store.settings.tv_show_superimpose === false) return;

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
                    }
                }
            }
        });

        // デバッグ用にプレイヤーインスタンスも window 直下に入れる
        (window as any).player = this.player;

        // DPlayer 側のコントロール UI 非表示タイマーを無効化（上書き）
        // 無効化しておかないと、PlayerWrapper.handlePlayerControlUIVisibility() の処理と競合してしまう
        // 上書き元のコードは https://github.com/tsukumijima/DPlayer/blob/v1.30.2/src/ts/controller.ts#L397-L405 にある
        this.player.controller.setAutoHide = (time: number) => {};

        // プレイヤーのコントロール UI を表示する (初回実行)
        this.handlePlayerControlUIVisibility();

        // DPlayer に動画再生系のイベントハンドラーを登録する
        this.setupVideoPlaybackHandler();

        // DPlayer のフルスクリーン関係のメソッドを無理やり上書きし、KonomiTV の UI と統合する
        this.setupFullscreenHandler();

        // DPlayer の設定パネルを無理やり拡張し、KonomiTV 独自の項目を追加する
        this.setupSettingPanelHandler();

        // PlayerManager からプレイヤーロジックの再起動が必要になったことを通知されたときのイベントハンドラーを登録する
        // このイベントは常にアプリケーション上で1つだけ登録されていなければならない
        // さもなければ使い終わった破棄済みの PlayerWrapper が再起動イベントにより復活し、現在利用中の PlayerWrapper と競合してしまう
        player_store.event_emitter.off('PlayerRestartRequired');  // PlayerRestartRequired イベントの全てのイベントハンドラーを削除
        player_store.event_emitter.on('PlayerRestartRequired', async (event) => {

            // PlayerWrapper を破棄
            await this.destroy();

            // PlayerWrapper を再度初期化
            // この時点で PlayerRestartRequired のイベントハンドラーは再登録されているはず
            await this.init();

            // プレイヤー側にイベントの発火元から送られたメッセージ (プレイヤーロジックを再起動中である旨) を通知する
            // 再初期化により、作り直した DPlayer が再び this.player にセットされているはず
            // 通知を表示してから PlayerWrapper を破棄すると DPlayer の DOM 要素ごと消えてしまうので、DPlayer を作り直した後に通知を表示する
            assert(this.player !== null);
            this.player.notice(event.message, -1, undefined, '#FF6F6A');
        });

        // 各 PlayerManager を初期化・登録
        // ライブ視聴とビデオ視聴で必要な PlayerManager が異なる
        // 一応順序は意図的だがそこまで重要ではない
        if (this.playback_mode === 'Live') {
            // ライブ視聴時に設定する PlayerManager
            this.player_managers = [
                new LiveEventManager(this.player),
                new LiveDataBroadcastingManager(this.player),
                new MediaSessionManager(this.player, this.playback_mode),
            ];
        } else {
            // ビデオ視聴時に設定する PlayerManager
            this.player_managers = [
                new MediaSessionManager(this.player, this.playback_mode),
            ];
        }

        // 登録されている PlayerManager をすべて初期化
        // これにより各 PlayerManager での実際の処理が開始される
        for (const player_manager of this.player_managers) {
            await player_manager.init();
        }
    }


    /**
     * ライブ視聴: 現在の DPlayer の再生バッファを再生位置とバッファ秒数の差から取得する
     * ビデオ視聴時と、取得に失敗した場合は 0 を返す
     * @returns バッファ秒数
     */
    private getPlaybackBufferSeconds(): number {
        assert(this.player !== null);
        if (this.playback_mode === 'Live') {
            let buffered_end = 0;
            if (this.player.video.buffered.length >= 1) {
                buffered_end = this.player.video.buffered.end(0);
            }
            return (Math.round((buffered_end - this.player.video.currentTime) * 1000) / 1000);
        } else {
            return 0;
        }
    }


    /**
     * もしまだ再生が開始できていない場合に再生状態の復旧を試みる
     * 処理の完了を待つ必要はないので、基本 await せず非同期で実行すべき
     */
    private async recoverPlayback(): Promise<void> {
        assert(this.player !== null);

        // 0.5 秒待つ
        await Utils.sleep(0.5);

        // この時点で映像が停止している場合、復旧を試みる
        if (this.player.video.readyState < 3) {
            console.log('player.video.readyState < HAVE_FUTURE_DATA. trying to recover.');

            // 一旦停止して、0.1 秒間を置く
            this.player.video.pause();
            await Utils.sleep(0.1);

            // 再度再生を試みる
            this.player.video.play().catch(() => {
                assert(this.player !== null);
                console.warn('HTMLVideoElement.play() rejected. paused.');
                this.player.pause();
            });
        }
    }


    /**
     * DPlayer に動画再生系のイベントハンドラーを登録する
     * 特にライブ視聴ではここで適切に再生状態の管理 (再生可能かどうか、エラーが発生していないかなど) を行う必要がある
     */
    private setupVideoPlaybackHandler(): void {
        assert(this.player !== null);
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();

        // ライブ視聴: 再生停止状態かつ現在の再生位置からバッファが 30 秒以上離れていないかを 60 秒おきに監視し、そうなっていたら強制的にシークする
        // mpegts.js の仕様上、MSE 側に未再生のバッファが貯まり過ぎると新規に SourceBuffer が追加できなくなるため、強制的に接続が切断されてしまう
        // 再生停止状態でも定期的にシークすることで、バッファが貯まりすぎないように調節する
        if (this.playback_mode === 'Live') {
            this.live_force_seek_interval_timer_id = window.setInterval(() => {
                if (this.player === null) return;
                if ((this.player.video.paused && this.player.video.buffered.length >= 1) &&
                    (this.player.video.buffered.end(0) - this.player.video.currentTime > 30)) {
                    this.player.sync();
                }
            }, 60 * 1000);
        }

        // 再生/停止されたときのイベント
        // デバイスの通知バーからの制御など、ブラウザの画面以外から動画の再生/停止が行われる事もあるため必要
        const on_play_or_pause = () => {
            if (this.player === null) return;
            // まだ設定パネルが表示されていたら非表示にする
            this.player.setting.hide();
            // プレイヤーのコントロール UI を表示する
            this.handlePlayerControlUIVisibility();
        };
        this.player.on('play', on_play_or_pause);
        this.player.on('pause', on_play_or_pause);

        // 再生が一時的に止まってバッファリングしているとき/再び再生されはじめたときのイベント
        // バッファリングの Progress Circular の表示を制御する
        this.player.on('waiting', () => {
            player_store.is_video_buffering = true;
        });
        this.player.on('playing', () => {
            player_store.is_video_buffering = false;
            // 再生が開始できていない場合に再生状態の復旧を試みる
            this.recoverPlayback();
        });

        // 今回 (DPlayer 初期化直後) と画質切り替え開始時の両方のタイミングで実行する必要がある処理
        // mpegts.js などの DPlayer のプラグインは画質切り替え時に一旦破棄されるため、再度イベントハンドラーを登録する必要がある
        const on_init_or_quality_change = async () => {
            assert(this.player !== null);

            // ローディング中の背景画像をランダムに変更
            player_store.background_url = PlayerUtils.generatePlayerBackgroundURL();

            // 実装上画質切り替え後にそのまま対応できない PlayerManager (LiveDataBroadcastingManager など) をここで再起動する
            // 初回実行時はそもそもまだ PlayerManager が一つも初期化されていないので、何も起こらない
            for (const player_manager of this.player_managers) {
                if (player_manager.restart_required_when_quality_switched === true) {
                    await player_manager.destroy();
                    await player_manager.init();
                }
            }

            // ライブ視聴時のみ
            if (this.playback_mode === 'Live') {

                // mpegts.js のエラーログハンドラーを登録
                // 再生中に mpegts.js 内部でエラーが発生した際 (例: デバイスの通信が一時的に切断され、API からのストリーミングが途切れた際) に呼び出される
                // このエラーハンドラーでエラーをキャッチして、PlayerWrapper の再起動を要求する
                // PlayerWrapper 内部なので直接再起動してもいいのだが、PlayerWrapper を再起動させる処理は共通化しておきたい
                this.player.plugins.mpegts?.on(mpegts.Events.ERROR, async (error_type: mpegts.ErrorTypes, detail: mpegts.ErrorDetails) => {
                    player_store.event_emitter.emit('PlayerRestartRequired', {
                        message: `再生中にエラーが発生しました。(${error_type}: ${detail}) プレイヤーロジックを再起動しています…`,
                    });
                });

                // 必ず最初はローディング状態とする
                player_store.is_loading = true;

                // 音量を 0 に設定
                this.player.video.volume = 0;

                // 再生準備ができた段階で再生バッファを調整し、再生準備ができた段階でローディング中の背景画像を非表示にするイベントハンドラーを登録
                // canplay と canplaythrough のどちらかのみが発火することも稀にある？ようなので、念のため両方に登録している
                const on_canplay = async () => {

                    // 自分自身のイベントの登録を解除 (重複実行を回避する)
                    if (this.player === null) return;
                    this.player.video.oncanplay = null;
                    this.player.video.oncanplaythrough = null;

                    // 再生バッファ調整のため、一旦停止させる
                    // this.player.video.pause() を使うとプレイヤーの UI アイコンが停止してしまうので、代わりに playbackRate を使う
                    this.player.video.playbackRate = 0;

                    // 再生バッファが live_playback_buffer_seconds を超えるまで 0.1 秒おきに再生バッファをチェックする
                    // 再生バッファが live_playback_buffer_seconds を切ると再生が途切れやすくなるので (特に動きの激しい映像)、
                    // 再生開始までの時間を若干犠牲にして、再生バッファの調整と同期に時間を割く
                    // live_playback_buffer_seconds の値は mpegts.js に渡す liveSyncTargetLatency プロパティに渡す値と共通
                    let current_playback_buffer_sec = this.getPlaybackBufferSeconds();
                    while (current_playback_buffer_sec < this.live_playback_buffer_seconds) {
                        await Utils.sleep(0.1);
                        current_playback_buffer_sec = this.getPlaybackBufferSeconds();
                    }

                    // 再生バッファ調整のため一旦停止していた再生を再び開始
                    this.player.video.playbackRate = 1;

                    // ローディング状態を解除し、映像を表示する
                    player_store.is_loading = false;

                    // バッファリング中の Progress Circular を非表示にする
                    player_store.is_video_buffering = false;

                    // この時点で再生が開始できていない場合、再生状態の復旧を試みる
                    this.recoverPlayback();

                    if (channels_store.channel.current.is_radiochannel === true) {
                        // ラジオチャンネルでは引き続き映像の代わりとしてローディング中の背景画像を表示し続ける
                        player_store.is_background_display = true;
                    } else {
                        // ローディング中の背景画像をフェードアウト
                        player_store.is_background_display = false;
                    }

                    // 再生開始時に音量を徐々に上げる
                    // いきなり再生されるよりも体験が良い
                    const current_volume = this.player.user.get('volume');
                    while ((this.player.video.volume + 0.05) < current_volume) {
                        // 小数第2位以下を切り捨てて、浮動小数の誤差で 1 (100%) を微妙に超えてしまいエラーになるのを避ける
                        this.player.video.volume = Utils.mathFloor(this.player.video.volume + 0.05, 2);
                        await Utils.sleep(0.02);
                    }
                    this.player.video.volume = current_volume;
                };
                this.player.video.oncanplay = on_canplay;
                this.player.video.oncanplaythrough = on_canplay;
            }
        };

        // 初回実行
        on_init_or_quality_change();

        // 画質切り替え開始時のイベント
        this.player.on('quality_start', on_init_or_quality_change);
    }


    /**
     * DPlayer のフルスクリーン関係のメソッドを無理やり上書きし、KonomiTV の UI と統合する
     * 上書き元のコードは https://github.com/tsukumijima/DPlayer/blob/master/src/ts/fullscreen.ts にある
     */
    private setupFullscreenHandler(): void {
        assert(this.player !== null);
        const player_store = usePlayerStore();

        // フルスクリーンにするコンテナ要素 (ページ全体)
        const fullscreen_container = document.querySelector('.v-application')!;

        // フルスクリーンかどうか
        this.player.fullScreen.isFullScreen = (type?: DPlayerType.FullscreenType) => {
            return !!(document.fullscreenElement || document.webkitFullscreenElement);
        };

        // フルスクリーンをリクエスト
        this.player.fullScreen.request = (type?: DPlayerType.FullscreenType) => {
            assert(this.player !== null);
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
            } else {
                // フルスクリーンがサポートされていない場合はエラーを表示
                this.player.notice('iPhone Safari は動画のフルスクリーン表示に対応していません。', undefined, undefined, '#FF6F6A');
                return;
            }
            // 画面の向きを横に固定 (Screen Orientation API がサポートされている場合)
            if (screen.orientation) {
                screen.orientation.lock('landscape').catch(() => {});
            }
        };

        // フルスクリーンをキャンセル
        this.player.fullScreen.cancel = (type?: DPlayerType.FullscreenType) => {
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
        };

        // フルスクリーン状態が変化した時のイベントハンドラーを登録
        // 複数のイベントを重複登録しないよう、あえて onfullscreenchange を使う
        const fullscreen_handler = () => {
            assert(this.player !== null);
            player_store.is_fullscreen = this.player.fullScreen.isFullScreen() === true;
        };
        if (fullscreen_container.onfullscreenchange !== undefined) {
            fullscreen_container.onfullscreenchange = fullscreen_handler;
        } else if (fullscreen_container.onwebkitfullscreenchange !== undefined) {
            fullscreen_container.onwebkitfullscreenchange = fullscreen_handler;
        }
    }


    /**
     * DPlayer の設定パネルを無理やり拡張し、KonomiTV 独自の項目を追加する
     */
    private setupSettingPanelHandler(): void {
        assert(this.player !== null);
        const player_store = usePlayerStore();

        // 設定パネルにショートカット一覧を表示するボタンを動的に追加する
        // スマホなどのタッチデバイスでは基本キーボードが使えないため、タッチデバイスの場合はボタンを表示しない
        if (Utils.isTouchDevice() === false) {
            this.player.template.settingOriginPanel.insertAdjacentHTML('beforeend', `
            <div class="dplayer-setting-item dplayer-setting-keyboard-shortcut">
                <span class="dplayer-label">キーボードショートカット</span>
                <div class="dplayer-toggle">
                    <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32">
                        <path d="M22 16l-10.105-10.6-1.895 1.987 8.211 8.613-8.211 8.612 1.895 1.988 8.211-8.613z"></path>
                    </svg>
                </div>
            </div>`);

            // ショートカット一覧モーダルを表示するボタンがクリックされたときのイベントハンドラーを登録
            this.player.template.settingOriginPanel.querySelector('.dplayer-setting-keyboard-shortcut')!.addEventListener('click', () => {
                assert(this.player !== null);
                // 設定パネルを閉じる
                this.player.setting.hide();
                // ショートカットキー一覧モーダルを表示する
                player_store.shortcut_key_modal = true;
            });
        }
    }


    /**
     * マウスが動いたりタップされた時に実行するタイマー関数
     * 一定の条件に基づいてプレイヤーのコントロール UI の表示状態を切り替える
     * 3秒間何も操作がなければプレイヤーのコントロール UI を非表示にする
     * 本来は View 側に実装すべきだが、プレイヤー側のロジックとも密接に関連しているため PlayerWrapper に実装した
     * @param event マウスやタッチイベント (手動実行する際は null を渡すか省略する)
     * @param is_player_region_event プレイヤー画面の中で発火したイベントなら true に設定する
     */
    public handlePlayerControlUIVisibility(event: Event | null = null, is_player_region_event: boolean = false): void {

        // タッチデバイスで mousemove 、あるいはタッチデバイス以外で touchmove か click が発火した時は実行じない
        if (Utils.isTouchDevice() === true  && event !== null && (event.type === 'mousemove')) return;
        if (Utils.isTouchDevice() === false && event !== null && (event.type === 'touchmove' || event.type === 'click')) return;

        // 以前セットされたタイマーを止める
        window.clearTimeout(this.player_control_ui_hide_timer_id);

        const player_store = usePlayerStore();

        // 実行された際にプレイヤーのコントロール UI を非表示にするタイマー関数 (setTimeout に渡すコールバック関数)
        const player_control_ui_hide_timer = () => {

            // 万が一実行されたタイミングですでに DPlayer が破棄されていたら何もしない
            if (this.player === null) return;

            // コメント入力フォームが表示されているときは実行しない
            // タイマーを掛け直してから抜ける
            if (this.player.template.controller.classList.contains('dplayer-controller-comment')) {
                this.player_control_ui_hide_timer_id = window.setTimeout(player_control_ui_hide_timer, 3 * 1000);  // 3秒後に再実行
                return;
            }

            // コントロールを非表示にする
            player_store.is_control_display = false;

            // プレイヤーのコントロールと設定パネルを非表示にする
            this.player.controller.hide();
            this.player.setting.hide();
        };

        // 万が一実行されたタイミングですでに DPlayer が破棄されていたら何もしない
        if (this.player === null) return;

        // タッチデバイスかつプレイヤー画面の中がタップされたとき
        if (Utils.isTouchDevice() === true && is_player_region_event === true) {

            // DPlayer 側のコントロール UI の表示状態に合わせる
            if (this.player.controller.isShow()) {

                // コントロールを表示する
                player_store.is_control_display = true;

                // プレイヤーのコントロールを表示する
                this.player.controller.show();

                // 3秒間何も操作がなければコントロールを非表示にする
                // 3秒間の間一度でもタッチされればタイマーが解除されてやり直しになる
                this.player_control_ui_hide_timer_id = window.setTimeout(player_control_ui_hide_timer, 3 * 1000);

            } else {

                // コントロール UI を非表示にする
                player_store.is_control_display = false;

                // DPlayer 側のコントロール UI と設定パネルを非表示にする
                this.player.controller.hide();
                this.player.setting.hide();
            }

        // それ以外の画面がクリックされたとき
        } else {

            // コントロール UI を表示する
            player_store.is_control_display = true;

            // DPlayer 側のコントロール UI を表示する
            this.player.controller.show();

            // 3秒間何も操作がなければコントロールを非表示にする
            // 3秒間の間一度でもマウスが動けばタイマーが解除されてやり直しになる
            this.player_control_ui_hide_timer_id = window.setTimeout(player_control_ui_hide_timer, 3 * 1000);
        }
    }


    /**
     * DPlayer と PlayerManager を破棄し、再生を終了する
     * 常に init() で作成したものが destroy() ですべてクリーンアップされるように実装すべき
     * PlayerWrapper の再起動を行う場合、基本外部から直接 await destroy() と await init() は呼び出さず、代わりに
     * player_store.event_emitter.emit('PlayerRestartRequired', 'プレイヤーロジックを再起動しています…') のようにイベントを発火させるべき
     */
    public async destroy(): Promise<void> {
        assert(this.player !== null);
        const player_store = usePlayerStore();

        // すでに破棄されているのに再度実行してはならない
        assert(this.destroyed === false);

        // 登録されている PlayerManager をすべて破棄
        // CSS アニメーションの関係上、ローディング状態にする前に破棄する必要がある (特に LiveDataBroadcastingManager)
        for (const player_manager of this.player_managers) {
            await player_manager.destroy();
        }
        this.player_managers = [];

        // ローディング中の背景画像を隠す
        player_store.is_background_display = false;

        // 再びローディング状態にする
        player_store.is_loading = true;

        // ローディング状態への移行に伴い、映像がフェードアウトするアニメーション (0.2秒) 分待ってから実行
        // この 0.2 秒の間に音量をフェードアウトさせる
        // なお、ザッピングでチャンネルを連続で切り替えている場合は実行しない (実行しても意味がないため)
        const current_volume = this.player.user.get('volume');
        // 20回 (0.01秒おき) に分けて音量を下げる
        for (let i = 0; i < 20; i++) {
            await Utils.sleep(0.01);
            this.player.video.volume = current_volume * (1 - (i + 1) / 20);
        }

        // タイマーを破棄
        window.clearInterval(this.live_force_seek_interval_timer_id);
        window.clearTimeout(this.player_control_ui_hide_timer_id);

        // DPlayer 本体を破棄
        this.player.destroy();
        this.player = null;

        // 破棄済みかどうかのフラグを立てる
        this.destroyed = true;
    }
}

export default PlayerWrapper;
