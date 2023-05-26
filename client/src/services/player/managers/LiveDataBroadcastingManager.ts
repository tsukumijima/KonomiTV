
import * as Comlink from 'comlink';
import dayjs from 'dayjs';
import DPlayer from 'dplayer';
import { BMLBrowser, BMLBrowserFontFace } from 'web-bml/client/bml_browser';
import { RemoteControl } from 'web-bml/client/remote_controller_client';
import { ResponseMessage } from 'web-bml/server/ws_api';

import router from '@/router';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/store/ChannelsStore';
import useSettingsStore from '@/store/SettingsStore';
import Utils, { PlayerUtils, ProgramUtils } from '@/utils';
import { ILivePSIArchivedDataDecoder } from '@/workers/LivePSIArchivedDataDecoder';


// LivePSIArchivedDataDecoder を Web Worker で動作させるためのラッパー
// Comlink を使い、Web Worker とメインスレッド間でオブジェクトをやり取りする
const worker = new Worker(new URL('@/workers/LivePSIArchivedDataDecoder', import.meta.url));
const LivePSIArchivedDataDecoderWorker =
    Comlink.wrap<new (psi_archived_data_api_url: string) => Comlink.Remote<ILivePSIArchivedDataDecoder>>(worker);


class LiveDataBroadcastingManager implements PlayerManager {

    // BML 用フォント
    static readonly round_gothic: BMLBrowserFontFace = {
        source: 'url("https://cdn.jsdelivr.net/gh/googlefonts/kosugi-maru@main/fonts/webfonts/KosugiMaru-Regular.woff2"), local("sans-serif")',
    };
    static readonly square_gothic: BMLBrowserFontFace = {
        source: 'url("https://cdn.jsdelivr.net/gh/googlefonts/kosugi@main/fonts/webfonts/Kosugi-Regular.woff2"), local("sans-serif")',
    };

    private player: DPlayer;
    private display_channel_id: string;
    private media_element: HTMLElement;
    private container_element: HTMLElement | null = null;

    // DPlayer のリサイズを監視する ResizeObserver
    private resize_observer: ResizeObserver | null = null;

    // BML ブラウザのインスタンス
    // Vue.js は data() で設定した変数を再帰的に監視するが、BMLBrowser 内の JS-Interpreter のインスタンスが
    // Vue.js の監視対象に入ると謎のエラーが発生してしまうため、プロパティを Hard Private にして監視対象から外す
    #bml_browser: BMLBrowser | null = null;

    // BML ブラウザの幅と高さ
    private bml_browser_width: number = 960;
    private bml_browser_height: number = 540;

    // BML ブラウザを破棄中かどうか
    private is_bml_browser_destroying: boolean = false;

    // PSI/SI アーカイブデータデコーダーのインスタンス
    private live_psi_archived_data_decoder: Comlink.Remote<Comlink.Remote<ILivePSIArchivedDataDecoder>> | null = null;

    constructor(options: {
        player: DPlayer;
        display_channel_id: string;
    }) {
        this.player = options.player;
        this.display_channel_id = options.display_channel_id;

        // 映像が入る DOM 要素
        // DPlayer 内の dplayer-video-wrap-aspect をそのまま使う (中に映像と字幕が含まれる)
        this.media_element = this.player.template.videoWrapAspect;
    }


    /**
     * LiveDataBroadcastingManager での処理を開始する
     * EDCB Legacy WebUI での実装を参考にした
     * ref: https://github.com/xtne6f/EDCB/blob/work-plus-s-230212/ini/HttpPublic/legacy/util.lua#L444-L497
     */
    public async init(): Promise<void> {

        const channels_store = useChannelsStore();
        const is_data_broadcasting_enabled = useSettingsStore().settings.tv_show_data_broadcasting;
        console.log(`[LiveDataBroadcastingManager] BMLBrowser: ${is_data_broadcasting_enabled ? 'enabled' : 'disabled'}`);

        // データ放送機能有効時のみ
        if (is_data_broadcasting_enabled === true) {

            // BML ブラウザが入る DOM 要素
            // DPlayer 内の dplayer-video-wrap の中に動的に追加する (映像レイヤーより下)
            // 要素のスタイルは Watch.vue で定義されている
            this.container_element = document.createElement('div');
            this.container_element.classList.add('dplayer-bml-browser');
            this.container_element = this.player.template.videoWrap.insertAdjacentElement('afterbegin', this.container_element) as HTMLElement;

            // リモコンを初期化
            const remote_control = new RemoteControl(
                document.querySelector('.remote-control')!,
                document.querySelector('.remote-control-receiving-status')!,
            );

            // BML ブラウザの初期化
            const this_ = this;
            this.#bml_browser = new BMLBrowser({
                mediaElement: document.createElement('p'),  // ここではダミーの p 要素を渡す
                containerElement: this.container_element,
                indicator: remote_control,
                storagePrefix: 'KonomiTV-BMLBrowser_',
                nvramPrefix: 'nvram_',
                broadcasterDatabasePrefix: '',
                videoPlaneModeEnabled: true,
                fonts: {
                    roundGothic: LiveDataBroadcastingManager.round_gothic,
                    squareGothic: LiveDataBroadcastingManager.square_gothic,
                },
                // Greg: 受信機の電源を切るまでグローバルに持続するメモリ
                greg: {
                    getReg(index: number) {
                        let Greg: string[];
                        if (window.sessionStorage.getItem('KonomiTV-BMLBrowser-Greg') === null) {
                            // 初回は Greg を初期化する
                            Greg = [...new Array(64)].map(_ => '');
                        } else {
                            // 2回目以降は SessionStorage 内の Greg を復元する
                            Greg = JSON.parse(window.sessionStorage.getItem('KonomiTV-BMLBrowser-Greg')!);
                        }
                        return Greg[index] ?? '';
                    },
                    setReg(index: number, value: string) {
                        let Greg: string[];
                        if (window.sessionStorage.getItem('KonomiTV-BMLBrowser-Greg') === null) {
                            // 初回は Greg を初期化する
                            Greg = [...new Array(64)].map(_ => '');
                        } else {
                            // 2回目以降は SessionStorage 内の Greg を復元する
                            Greg = JSON.parse(window.sessionStorage.getItem('KonomiTV-BMLBrowser-Greg')!);
                        }
                        Greg[index] = value;
                        window.sessionStorage.setItem('KonomiTV-BMLBrowser-Greg', JSON.stringify(Greg));
                    },
                },
                // データ放送からのチャンネル切り替え機能
                epg: {
                    tune(network_id: number, transport_stream_id: number, service_id: number): boolean {
                        // チャンネルリストから network_id と service_id が一致するチャンネルを探す
                        // transport_stream_id は Mirakurun バックエンドの場合は存在しないため使わない
                        // network_id + service_id だけで一意になる
                        for (const channels of Object.values(channels_store.channels_list)) {
                            for (const channel of channels) {
                                if (channel.network_id === network_id && channel.service_id === service_id) {
                                    // 少し待ってからチャンネルを切り替える（チャンネル切り替え時にデータ放送側から音が鳴る可能性があるため）
                                    Utils.sleep(0.3).then(() => router.push({path: `/tv/watch/${channel.display_channel_id}`}));
                                    return true;
                                }
                            }
                        }
                        // network_id と service_id が一致するチャンネルが見つからなかった
                        // 3秒間エラーメッセージを表示する
                        console.error(`[LiveDataBroadcastingManager] Channel not found (network_id: ${network_id} / service_id: ${service_id})`);
                        this_.player.notice(`切り替え先のチャンネルが見つかりませんでした。(network_id: ${network_id} / service_id: ${service_id})`, 3000, undefined, '#FF6F6A');
                        // 非同期で LiveDataBroadcastingManager を再起動
                        Utils.sleep(3).then(async () => {
                            await this_.destroy();
                            await this_.init();
                        });
                        return false;
                    }
                },
                // 双方向 (ネット接続) 機能
                ip: {
                    getConnectionType(): number {
                        // ARIB STD-B24 第二分冊 (2/2) 第二編 付属3 5.6.5.2 表5-12
                        // 1: PSTN
                        // 100: ISDN
                        // 200: PHS
                        // 201: PHS (PIAFS2.0)
                        // 202: PHS (PIAFS2.1)
                        // 300: Mobile phone
                        // 301: Mobile phone (PDC)
                        // 302: Mobile phone (PDC-P)
                        // 303: Mobile phone (DS-CDMA)
                        // 304: Mobile phone(MC-CDMA)
                        // 305: Mobile phone (CDMA CelluarSystem)
                        // 401: Ethernet (PPPoE)
                        // 402: Ethernet (Fixed IP)
                        // 403: Ethernet (DHCP)
                        // NaN: 失敗
                        return 403;
                    },
                    isIPConnected(): number {
                        // ARIB STD-B24 第二分冊 (2/2) 第二編 付属3 5.6.5.2 表5-14
                        // 0: IP 接続は確立していない
                        // 1: IP 接続は自動接続によって確立している
                        // 2: IP 接続は connectPPP() / connectPPPWithISPParams() により確立している
                        // NaN 失敗
                        return 0;
                    },
                },
                // エラー発生時のメッセージ表示
                // 3秒間プレイヤーにエラーメッセージを表示する
                showErrorMessage(title: string, message: string, code?: string): void {
                    this_.player.notice(`${title}<br>${message} (${code})`, 3000, undefined, '#FF6F6A');
                }
            });
            this.bml_browser_width = 960;
            this.bml_browser_height = 540;
            console.log('[LiveDataBroadcastingManager] BMLBrowser initialized.');

            // リモコンに BML ブラウザを設定
            remote_control.content = this.#bml_browser.content;

            // BML ブラウザがロードされたときのイベント
            this.#bml_browser.addEventListener('load', (event) => {
                console.log('[LiveDataBroadcastingManager] BMLBrowser: load', event.detail);

                // 映像の要素をデータ放送内に移動
                this.moveVideoElementToBMLBrowser();

                // BML ブラウザの要素に幅と高さを設定
                this.bml_browser_width = event.detail.resolution.width;
                this.bml_browser_height = event.detail.resolution.height;
                this.container_element?.style.setProperty('--bml-browser-width', `${this.bml_browser_width}px`);
                this.container_element?.style.setProperty('--bml-browser-height', `${this.bml_browser_height}px`);

                // データ放送画面の拡大/縮小率を再計算
                this.calculateBMLBrowserScaleFactor(this.player.template.videoWrap.clientWidth, this.player.template.videoWrap.clientHeight);
            });

            // BML ブラウザの表示状態が変化したときのイベント
            this.#bml_browser.addEventListener('invisible', (event) => {
                if (event.detail === true) {
                    // 非表示状態
                    // データ放送内に移動していた映像の要素を DPlayer に戻す
                    console.log('[LiveDataBroadcastingManager] BMLBrowser: invisible');
                    this.moveVideoElementToDPlayer();
                } else {
                    // 表示状態
                    // 映像の要素をデータ放送内に移動
                    console.log('[LiveDataBroadcastingManager] BMLBrowser: visible');
                    this.moveVideoElementToBMLBrowser();
                }
            });

            // BML ブラウザ内の映像のサイズが変化したときのイベント
            this.#bml_browser.addEventListener('videochanged', (event) => {
                console.log('[LiveDataBroadcastingManager] BMLBrowser: videochanged', event.detail);
            });

            // DPlayer のリサイズを監視する ResizeObserver を開始
            this.resize_observer = new ResizeObserver((entries: ResizeObserverEntry[]) => {
                // データ放送画面の拡大/縮小率を再計算
                const entry = entries[0];
                this.calculateBMLBrowserScaleFactor(entry.contentRect.width, entry.contentRect.height);
            });
            this.resize_observer.observe(this.player.template.videoWrap);
        }

        // ここからはデータ放送機能無効時も実行される (番組情報をリアルタイムに更新するため)

        // ライブ PSI/SI アーカイブデータストリーミング API の URL を作成
        const api_quality = PlayerUtils.extractAPIQualityFromDPlayer(this.player);
        const api_url = `${Utils.api_base_url}/streams/live/${this.display_channel_id}/${api_quality}/psi-archived-data`;

        // ライブ PSI/SI アーカイブデータデコーダーを初期化
        // Comlink を挟んでいる関係上コンストラクタにも関わらず Promise を返すため await する必要がある
        this.live_psi_archived_data_decoder = await new LivePSIArchivedDataDecoderWorker(api_url);

        // デコードを開始
        // デコーダーは Web Worker 上で実行される (コールバックを Comlink.proxy() で包むのがポイント)
        this.live_psi_archived_data_decoder.run(Comlink.proxy(async (message: ResponseMessage) => {

            // 番組情報イベントを受信し次第 ChannelsStore を更新
            // これで現在放送中の番組情報がリアルタイムに反映される
            if (message.type == 'programInfo') {
                // イベント ID
                if (message.eventId) {
                    channels_store.channel.current.program_present.event_id = message.eventId;
                }
                // 番組タイトル
                if (message.eventName) {
                    channels_store.channel.current.program_present.title = ProgramUtils.formatString(message.eventName);
                }
                // 番組開始時刻・番組終了時刻・番組長
                if (message.startTimeUnixMillis) {
                    const start_time = ProgramUtils.convertTimestampToISO8601(message.startTimeUnixMillis);
                    channels_store.channel.current.program_present.start_time = start_time;
                    if (message.durationSeconds) {
                        channels_store.channel.current.program_present.end_time =
                            dayjs(start_time).add(message.durationSeconds, 'seconds').toISOString();
                        channels_store.channel.current.program_present.duration = message.durationSeconds;
                    } else {
                        // 開始時刻はあるが番組長がない場合、放送時間未定として扱う
                        // duration が -1 の場合、ProgramUtils.getProgramTime() は「放送時間未定」と表示する
                        channels_store.channel.current.program_present.end_time = start_time;
                        channels_store.channel.current.program_present.duration = -1;  // -1 を設定する
                    }
                }
            }

            // TS ストリームのデコード結果を BML ブラウザにそのまま送信する
            if (is_data_broadcasting_enabled === true) {
                this.#bml_browser?.emitMessage(message);
            }
        }));
    }


    /**
     * データ放送画面の拡大/縮小率を再計算し、CSS カスタムプロパティに設定する
     * データ放送は 960×540 か 720×480 の固定サイズなので、レスポンシブにするために transform: scale() を使っている
     * @param container_width BML ブラウザが入るコンテナ要素の幅
     * @param container_height BML ブラウザが入るコンテナ要素の高さ
     */
    private calculateBMLBrowserScaleFactor(container_width: number, container_height: number): void {

        // 高さは BML ブラウザの高さをそのまま利用するが、横幅は常に高さに対して常に 16:9 の比率になるようにする
        // BML ブラウザのサイズが 960×540 なら問題ないが、720×480 の場合は 854×480 として計算される
        const scale_factor_width = container_width / (this.bml_browser_height * 16 / 9);
        const scale_factor_height = container_height / this.bml_browser_height;

        // transform: scale() での拡大率を算出
        const scale_factor = Math.min(scale_factor_width, scale_factor_height);

        // (BMLブラウザの高さに対して 16:9 の比率の幅)÷(BMLブラウザの幅) で横に引き伸ばす倍率を算出
        // 854÷720 の場合、約 1.185 倍になる
        const magnification = (this.bml_browser_height * 16 / 9) / this.bml_browser_width;

        // データ放送画面の拡大/縮小率を CSS カスタムプロパティとして設定
        this.container_element?.style.setProperty('--bml-browser-scale-factor-width', `${scale_factor * magnification}`);
        this.container_element?.style.setProperty('--bml-browser-scale-factor-height', `${scale_factor}`);
    }


    /**
     * 映像の DOM 要素を DPlayer から BML ブラウザ (データ放送) 内に移動する
     */
    private moveVideoElementToBMLBrowser(): void {

        // BML ブラウザの破棄中にイベントが発火した場合は何もしない
        if (this.is_bml_browser_destroying) {
            return;
        }

        // getVideoElement() に失敗した (=現在データ放送に映像が表示されていない) 場合は何もしない
        if (this.#bml_browser?.getVideoElement() === null) {
            return;
        }

        // ダミーで渡した p 要素があれば削除
        if (this.#bml_browser?.getVideoElement()?.firstElementChild instanceof HTMLParagraphElement) {
            this.#bml_browser?.getVideoElement()?.firstElementChild?.remove();
        }

        // データ放送内に映像の要素を入れる
        this.#bml_browser?.getVideoElement()?.appendChild(this.media_element);

        // データ放送内での表示用にスタイルを調整
        this.media_element.style.width = '100%';
        this.media_element.style.height = '100%';
        for (const child of this.media_element.children) {
            (child as HTMLElement).style.display = 'block';
            (child as HTMLElement).style.visibility = 'visible';
            if (child instanceof HTMLVideoElement) {
                (child as HTMLVideoElement).style.width = '100%';
                (child as HTMLVideoElement).style.height = '100%';
                (child as HTMLVideoElement).style.objectFit = 'fill';
            }
        }
    }


    /**
     * 映像の DOM 要素を BML ブラウザ (データ放送) から DPlayer 内に移動する
     */
    private moveVideoElementToDPlayer(): void {

        // BML ブラウザの破棄中にイベントが発火した場合は何もしない
        if (this.is_bml_browser_destroying) {
            return;
        }

        // データ放送内に移動していた映像の要素を DPlayer に戻す (BML ブラウザより上のレイヤーに配置)
        // BML ブラウザの破棄前に行う必要がある
        if (this.container_element !== null) {
            this.player.template.videoWrap.insertBefore(this.media_element, this.container_element.nextElementSibling);
        }

        // データ放送内での表示用に調整していたスタイルを戻す
        this.media_element.style.width = '';
        this.media_element.style.height = '';
        for (const child of this.media_element.children) {
            (child as HTMLElement).style.display = '';
            (child as HTMLElement).style.visibility = '';
            if (child instanceof HTMLVideoElement) {
                (child as HTMLVideoElement).style.width = '';
                (child as HTMLVideoElement).style.height = '';
                (child as HTMLVideoElement).style.objectFit = '';
            }
        }
    }


    /**
     * LiveDataBroadcastingManager での処理を終了し、破棄する
     */
    public async destroy(): Promise<void> {

        // ライブ PSI/SI アーカイブデータデコーダーを終了
        if (this.live_psi_archived_data_decoder !== null) {
            // タイミングの関係なのかチャンネル切り替え時の映像のフェードアウトが効かなくなるため、await してはいけない
            this.live_psi_archived_data_decoder.destroy();
            this.live_psi_archived_data_decoder = null;
        }

        // データ放送機能有効時のみ
        const is_data_broadcasting_enabled = useSettingsStore().settings.tv_show_data_broadcasting;
        if (is_data_broadcasting_enabled === true) {

            // DPlayer のリサイズを監視する ResizeObserver を終了
            if (this.resize_observer !== null) {
                this.resize_observer.disconnect();
                this.resize_observer = null;
            }

            // データ放送内に移動していた映像の要素を DPlayer に戻す
            this.moveVideoElementToDPlayer();

            // BML ブラウザを破棄
            this.is_bml_browser_destroying = true;
            await this.#bml_browser?.destroy();
            this.is_bml_browser_destroying = false;
            this.#bml_browser = null;
            console.log('[LiveDataBroadcastingManager] BMLBrowser destroyed.');

            // BML ブラウザの要素を削除
            this.container_element?.remove();
        }
    }
}

export default LiveDataBroadcastingManager;
