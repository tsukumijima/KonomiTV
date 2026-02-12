
import * as Comlink from 'comlink';
import DPlayer from 'dplayer';
import { isEqual } from 'ohash';
import { AribKeyCode, BMLBrowser, BMLBrowserFontFace } from 'web-bml';

import router from '@/router';
import APIClient from '@/services/APIClient';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { PlayerUtils } from '@/utils';
import { ILivePSIArchivedDataDecoder } from '@/workers/LivePSIArchivedDataDecoder';
import LivePSIArchivedDataDecoderProxy from '@/workers/LivePSIArchivedDataDecoderProxy';


/**
 * ライブ視聴: データ放送機能を管理する PlayerManager
 */
class LiveDataBroadcastingManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
    public readonly restart_required_when_quality_switched = true;

    // BML 用フォント
    public static readonly ROUND_GOTHIC: BMLBrowserFontFace = {
        source: 'url("/assets/fonts/KosugiMaru-Regular.woff2"), local("sans-serif")',
    };
    public static readonly SQUARE_GOTHIC: BMLBrowserFontFace = {
        source: 'url("/assets/fonts/Kosugi-Regular.woff2"), local("sans-serif")',
    };

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    private readonly media_element: HTMLElement;
    private container_element: HTMLElement | null = null;
    private readonly remocon_element: HTMLElement;
    private readonly remocon_data_broadcasting_element: HTMLElement;
    private remocon_button_event_abort_controller: AbortController | null = null;

    // DPlayer のリサイズを監視する ResizeObserver
    private resize_observer: ResizeObserver | null = null;

    // BML ブラウザのインスタンス
    // Vue.js は data() で設定した変数を再帰的に監視するが、BMLBrowser 内の JS-Interpreter のインスタンスが
    // Vue.js の監視対象に入ると謎のエラーが発生してしまうため、プロパティを Hard Private にして監視対象から外す
    #bml_browser: BMLBrowser | null = null;

    // BML ブラウザの幅と高さ
    private bml_browser_width: number = 960;
    private bml_browser_height: number = 540;

    // BML ブラウザが数字キーを文字入力などに利用中かどうか
    private is_bml_browser_using_numeric_key: boolean = false;

    // BML ブラウザを破棄中かどうか
    private is_bml_browser_destroying: boolean = false;

    // 動画の要素が BML ブラウザ上に移動されているかどうか
    private is_video_element_moved_to_bml_browser: boolean = false;

    // PSI/SI アーカイブデータデコーダーのインスタンス
    private live_psi_archived_data_decoder: Comlink.Remote<ILivePSIArchivedDataDecoder> | null = null;

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     */
    constructor(player: DPlayer) {
        this.player = player;

        // 映像が入る DOM 要素
        // DPlayer 内の dplayer-video-wrap-aspect をそのまま使う (中に映像と字幕が含まれる)
        this.media_element = this.player.template.videoWrapAspect;

        // リモコンの DOM 要素
        this.remocon_element = document.querySelector('.remote-control')!;
        this.remocon_data_broadcasting_element = this.remocon_element.querySelector('.remote-control-data-broadcasting')!;
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

        // リモコンのボタンを初期化
        this.initRemoconButtons();

        // データ放送機能有効時のみ
        if (is_data_broadcasting_enabled === true) {

            // BML ブラウザが入る DOM 要素
            // DPlayer 内の dplayer-video-wrap の中に動的に追加する (映像レイヤーより下)
            // 要素のスタイルは Watch.vue で定義されている
            this.container_element = document.createElement('div');
            this.container_element.classList.add('dplayer-bml-browser');
            this.container_element = this.player.template.videoWrap.insertAdjacentElement('afterbegin', this.container_element) as HTMLElement;

            // リモコンのボタンを有効化
            // データ放送機能無効時はボタンを無効のままにする
            this.toggleRemoconButtonsEnabled(true);

            // リモコンをローディング状態にする
            this.toggleRemoconButtonsLoading(true);

            // BML ブラウザの初期化
            const this_ = this;
            this.#bml_browser = new BMLBrowser({
                mediaElement: document.createElement('p'),  // ここではダミーの p 要素を渡す
                containerElement: this.container_element,
                storagePrefix: 'KonomiTV-BMLBrowser_',
                nvramPrefix: 'nvram_',
                broadcasterDatabasePrefix: '',
                videoPlaneModeEnabled: true,
                fonts: {
                    roundGothic: LiveDataBroadcastingManager.ROUND_GOTHIC,
                    squareGothic: LiveDataBroadcastingManager.SQUARE_GOTHIC,
                },
                // ステータス更新時のイベント
                indicator: {
                    setUrl(name: string, loading: boolean) {
                        this_.toggleRemoconButtonsLoading(loading);
                    },
                    setNetworkingGetStatus(connecting: boolean) {
                        this_.toggleRemoconButtonsLoading(connecting);
                    },
                    setNetworkingPostStatus(connecting: boolean) {
                        this_.toggleRemoconButtonsLoading(connecting);
                    },
                    setReceivingStatus(receiving: boolean) {
                        // 何もしない
                    },
                    setEventName(name: string) {
                        // 何もしない
                    }
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
                    tune(network_id: number, transport_stream_id: number, service_id: number) {
                        // 選局対象のチャンネルが現在視聴中のチャンネルと同じ場合
                        if (channels_store.channel.current.network_id === network_id && channels_store.channel.current.service_id === service_id) {
                            // 非同期で LiveDataBroadcastingManager を再起動
                            // チャンネル切り替え後は BML ブラウザがフリーズするため
                            (async () => {
                                await this_.destroy();
                                await this_.init();
                            })();
                            return true;
                        }
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
                        // エラーメッセージを表示し終わったタイミングで、非同期で LiveDataBroadcastingManager を再起動
                        // チャンネル切り替えに失敗すると BML ブラウザがフリーズするため
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
                        if (useSettingsStore().settings.enable_internet_access_from_data_broadcasting === true) {
                            return 1;
                        } else {
                            return 0;
                        }
                    },
                    // サーバー側のプロキシ API 経由で HTTP GET リクエストを送信し、レスポンスを受け取る
                    async get(uri: string) {
                        // データ放送からのインターネットアクセスが無効なときは何もしない
                        if (useSettingsStore().settings.enable_internet_access_from_data_broadcasting === false) {
                            return {};
                        }
                        // サーバー側のプロキシ API 経由で HTTP GET リクエストを送信する
                        const response = await APIClient.get<ArrayBuffer>(`/data-broadcasting/request/${uri}`, {
                            // レスポンスを ArrayBuffer として受け取る
                            responseType: 'arraybuffer',
                            // すべてのステータスコードで AxiosError にならないようにする
                            validateStatus: () => true,
                        });
                        // HTTP リクエスト自体に失敗した (何も返さない)
                        if (response.type === 'error') {
                            return {};
                        }
                        // HTTP リクエストに成功した
                        return {
                            statusCode: response.status,
                            headers: Utils.convertAxiosHeadersToFetchHeaders(response.headers),
                            response: new Uint8Array(response.data),
                        };
                    },
                    // サーバー側のプロキシ API 経由で HTTP POST リクエストを送信し、レスポンスを受け取る
                    async transmitTextDataOverIP(uri: string, body: Uint8Array) {
                        // データ放送からのインターネットアクセスが無効なときは何もしない
                        if (useSettingsStore().settings.enable_internet_access_from_data_broadcasting === false) {
                            return {
                                resultCode: NaN,
                                statusCode: '',
                                response: new Uint8Array(),
                            };
                        }
                        // サーバー側のプロキシ API 経由で HTTP POST リクエストを送信する
                        const response = await APIClient.post<ArrayBuffer>(`/data-broadcasting/request/${uri}`, body, {
                            // 受け取ったフォームデータをそのまま送信する
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            // レスポンスを ArrayBuffer として受け取る
                            responseType: 'arraybuffer',
                            // すべてのステータスコードで AxiosError にならないようにする
                            validateStatus: () => true,
                        });
                        // HTTP リクエストに失敗した
                        if (response.type === 'error') {
                            // HTTP リクエスト自体に失敗した
                            return {
                                resultCode: NaN,
                                statusCode: '',
                                response: new Uint8Array(),
                            };
                        }
                        // HTTP リクエストに成功した
                        return {
                            resultCode: 1,
                            statusCode: response.status.toString(),
                            response: new Uint8Array(response.data),
                        };
                    },
                    // サーバー側のプロキシ API 経由でインターネット接続状態を確認する
                    async confirmIPNetwork(destination: string, isICMP: boolean, timeoutMillis: number) {
                        // データ放送からのインターネットアクセスが無効なときは何もしない
                        if (useSettingsStore().settings.enable_internet_access_from_data_broadcasting === false) {
                            return null;
                        }
                        interface DataBroadcastingInternetStatus {
                            success: boolean;
                            ip_address: string | null;
                            response_time_milliseconds: number | null;
                        }
                        const response = await APIClient.get<DataBroadcastingInternetStatus>(`/data-broadcasting/internet-status?${new URLSearchParams({
                            destination,
                            is_icmp: isICMP ? 'true' : 'false',
                            timeout_milliseconds: timeoutMillis.toString()
                        })}`, {
                            // すべてのステータスコードで AxiosError にならないようにする
                            validateStatus: () => true,
                        });
                        // HTTP リクエスト自体に失敗した
                        if (response.type === 'error') {
                            return null;
                        }
                        // HTTP リクエストに成功した
                        return {
                            success: response.data.success,
                            ipAddress: response.data.ip_address,
                            responseTimeMillis: response.data.response_time_milliseconds,
                        };
                    }
                },
                // エラー発生時のメッセージ表示
                // 3秒間プレイヤーにエラーメッセージを表示する
                showErrorMessage(title: string, message: string, code?: string): void {
                    this_.player.notice(`${title}<br>${message} (${code})`, 3000, undefined, '#FF6F6A');
                }
            });
            this.bml_browser_width = 960;
            this.bml_browser_height = 540;

            // BML ブラウザが保持する FontFace をこの時点で全て明示的にロードしておき、画面のチラつきを防ぐ
            for (const font of (this.#bml_browser as any).fonts) {
                font.load();  // ロード完了を待たない
            }

            // BML ブラウザがロードされたときのイベント
            this.#bml_browser.addEventListener('load', (event) => {
                console.log('[LiveDataBroadcastingManager] BMLBrowser: load', event.detail);

                // BML ブラウザの要素に幅と高さを設定
                this.bml_browser_width = event.detail.resolution.width;
                this.bml_browser_height = event.detail.resolution.height;
                this.container_element?.style.setProperty('--bml-browser-width', `${this.bml_browser_width}px`);
                this.container_element?.style.setProperty('--bml-browser-height', `${this.bml_browser_height}px`);

                // データ放送画面の拡大/縮小率を再計算
                this.calculateBMLBrowserScaleFactor(this.player.template.videoWrap.clientWidth, this.player.template.videoWrap.clientHeight);

                // 映像の要素をデータ放送内に移動
                this.moveVideoElementToBMLBrowser();
            });

            // BML ブラウザの表示状態が変化したときのイベント
            this.#bml_browser.addEventListener('invisible', (event) => {
                if (event.detail === true) {
                    // 非表示状態
                    // データ放送内に移動していた映像の要素を DPlayer に戻す
                    console.log('[LiveDataBroadcastingManager] BMLBrowser: invisible');
                    this.moveVideoElementToDPlayer();
                    // BML ブラウザのコンテナ要素を display: none にする
                    if (this.container_element !== null) {
                        this.container_element.style.display = 'none';
                    }
                } else {
                    // 表示状態
                    // 映像の要素をデータ放送内に移動
                    console.log('[LiveDataBroadcastingManager] BMLBrowser: visible');
                    this.moveVideoElementToBMLBrowser();
                    // BML ブラウザのコンテナ要素を display: block にする
                    if (this.container_element !== null) {
                        this.container_element.style.display = 'block';
                    }
                }
            });

            // 現在 BML ブラウザ上で利用しているボタンの一覧が変化したときのイベント
            this.#bml_browser.addEventListener('usedkeylistchanged', (event) => {
                // usedKeyList の中に numeric-tuning が含まれている場合は、データ放送が数字キーを利用中
                this.is_bml_browser_using_numeric_key = [...event.detail.usedKeyList].includes('numeric-tuning');
            });

            // DPlayer のリサイズを監視する ResizeObserver を開始
            this.resize_observer = new ResizeObserver((entries: ResizeObserverEntry[]) => {
                // データ放送画面の拡大/縮小率を再計算
                const entry = entries[0];
                this.calculateBMLBrowserScaleFactor(entry.contentRect.width, entry.contentRect.height);
            });
            this.resize_observer.observe(this.player.template.videoWrap);
        }

        // ここからはデータ放送機能無効時も実行される
        // PSI/SI アーカイブデータは、UI 上の番組情報をリアルタイムに更新する用途でも利用している

        // ライブ PSI/SI アーカイブデータデコーダーを初期化
        // Comlink を挟んでいる関係上、コンストラクタにも関わらず Promise を返すため await する必要がある
        const api_quality = PlayerUtils.extractLiveAPIQualityFromDPlayer(this.player);
        this.live_psi_archived_data_decoder = await new LivePSIArchivedDataDecoderProxy(channels_store.channel.current, api_quality);

        // デコードを開始
        // デコーダーは Web Worker 上で実行される (コールバックを Comlink.proxy() で包むのがポイント)
        this.live_psi_archived_data_decoder.run(Comlink.proxy(async (message) => {

            // データ放送有効時のみ
            if (this.#bml_browser !== null) {

                // PMT (Program Map Table) イベント
                if (message.type === 'pmt') {

                    // データ放送がチャンネルに含まれているかどうか
                    // AdditionalAribBXMLInfo を含むコンポーネントが一つでも存在するかどうかで判定
                    const is_bml_available = message.components.some((component) => component.bxmlInfo !== undefined);
                    console.log(`[LiveDataBroadcastingManager] BMLBrowser: ${is_bml_available ? 'available' : 'unavailable'}`);

                    // データ放送がチャンネルに含まれていない場合
                    if (is_bml_available === false) {

                        // リモコンのローディング状態を解除
                        // PMT にデータ放送用情報が含まれるようになるまでは、データ放送が利用できる見込みはない
                        this.toggleRemoconButtonsLoading(false);

                        // リモコンのボタンを無効化
                        this.toggleRemoconButtonsEnabled(false);

                    // データ放送がチャンネルに含まれている場合
                    // データ放送がチャンネルに含まれていなかったが、後から含まれるようになったケースを想定
                    // この時点ではローディングは終わっていないので、ローディング状態は解除しない
                    } else {

                        // リモコンのボタンを有効化
                        this.toggleRemoconButtonsEnabled(true);
                    }
                }

                // TS ストリームのデコード結果を BML ブラウザにそのまま送信する
                // IProgramPF は KonomiTV の UI 表示用の番組情報イベントなので、BML ブラウザには送信しない
                if (message.type !== 'IProgramPF') {
                    this.#bml_browser.emitMessage(message);
                }
            }

            // 番組情報イベント (KonomiTV の UI 表示用)
            // 現在放送中/次に放送される番組情報を ChannelsStore を経由し UI 側にリアルタイムに反映する
            if (message.type === 'IProgramPF') {
                // EIT[p/f] は同一番組情報が高頻度で流れてくることがあるため、
                // 変更がない場合は store への再代入を抑止し、watcher が過剰に呼び出される連鎖を防ぐ
                if (message.present_or_following === 'Present') {
                    if (isEqual(channels_store.current_program_present, message.program) === false) {
                        channels_store.current_program_present = message.program;
                    }
                } else if (message.present_or_following === 'Following') {
                    if (isEqual(channels_store.current_program_following, message.program) === false) {
                        channels_store.current_program_following = message.program;
                    }
                }
            }
        }));

        console.log('[LiveDataBroadcastingManager] Initialized.');
    }


    /**
     * リモコンのボタンを初期化する
     */
    private initRemoconButtons(): void {
        const channels_store = useChannelsStore();

        // リモコンのボタンのクリックイベントを一括で削除するための AbortController
        this.remocon_button_event_abort_controller = new AbortController();

        // リモコンのボタンをクリックしたときのイベントを登録
        const buttons = this.remocon_element.querySelectorAll('button');
        for (const button of buttons) {
            button.addEventListener('click', async () => {

                // ARIB 仕様上のキーコード
                const arib_key_code = (parseInt(button.dataset.aribKeyCode!) as AribKeyCode);

                // リモコン ID (番号キーのみ)
                const remocon_id = button.dataset.remoconId ? parseInt(button.dataset.remoconId) : null;

                // 番号キーでかつ現在データ放送が番号キーを使っていない場合は、そのチャンネルに切り替える
                if (remocon_id !== null && this.is_bml_browser_using_numeric_key === false) {

                    // 切り替え先のチャンネルを取得する
                    // チャンネルタイプは現在視聴中のチャンネルと同じ
                    const switch_channel_type = channels_store.channel.current.type;
                    const switch_channel = channels_store.getChannelByRemoconID(switch_channel_type, remocon_id);

                    // チャンネルが取得できていれば、ルーティングをそのチャンネルに置き換える
                    // 押されたキーに対応するリモコン ID のチャンネルがない場合や、現在と同じチャンネル ID の場合は何も起こらない
                    if (switch_channel !== null && switch_channel.display_channel_id !== channels_store.display_channel_id) {
                        router.push({path: `/tv/watch/${switch_channel.display_channel_id}`});
                    }
                    return;

                // それ以外の場合は、BML ブラウザにキーイベントを送信する
                // データ放送機能無効時は何もしない
                // TODO: BML ブラウザがクラッシュした場合 processKeyDown() あたりから例外が送出されるが、途中で握り潰されている？のかキャッチできない
                } else {
                    if (this.#bml_browser !== null) {
                        if (remocon_id === 10) {
                            // リモコン番号が 10 の場合のみ、"0" のキーイベントも送信する
                            this.#bml_browser.content.processKeyDown(AribKeyCode.Digit0);
                            this.#bml_browser.content.processKeyUp(AribKeyCode.Digit0);
                            await Utils.sleep(0.1);  // 若干待つのがポイント
                        }
                        this.#bml_browser.content.processKeyDown(arib_key_code);
                        this.#bml_browser.content.processKeyUp(arib_key_code);
                    }
                }

            }, {signal: this.remocon_button_event_abort_controller.signal});
        }
    }


    /**
     * リモコンのデータ放送ボタンの表示状態をローディングかどうかで切り替える
     */
    private toggleRemoconButtonsLoading(loading: boolean): void {
        if (loading === true) {
            this.remocon_data_broadcasting_element.classList.add('remote-control-data-broadcasting--loading');
        } else {
            this.remocon_data_broadcasting_element.classList.remove('remote-control-data-broadcasting--loading');
        }
    }


    /**
     * リモコンのデータ放送ボタンの有効/無効をローディングかどうかで切り替える
     * 初期状態 (Vue SFC の HTML 上) では無効になっているので、BML ブラウザの初期化時に有効にする
     */
    private toggleRemoconButtonsEnabled(enabled: boolean): void {
        if (enabled === true) {
            this.remocon_data_broadcasting_element.classList.remove('remote-control-data-broadcasting--disabled');
        } else {
            this.remocon_data_broadcasting_element.classList.add('remote-control-data-broadcasting--disabled');
        }
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
     * データ放送が読み込まれるか、表示状態になるときに呼び出される
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
            }
        }
        // BML ブラウザのアスペクト比が 16:9 以外のケース (運用上は 720×480 のみ該当) に限定して適用する
        if (this.bml_browser_width / this.bml_browser_height !== 16 / 9) {
            const magnification = (this.bml_browser_height * 16 / 9) / this.bml_browser_width;
            this.media_element.style.transform = `scaleY(${magnification})`;
            this.media_element.style.transformOrigin = 'center center';
            // 上記ケースでは親要素に映像のアスペクト比を矯正する目的で
            // scaleY() が設定されるため、Canvas 要素のみ親要素の scaleY() を打ち消す縮小方向の scaleY() を設定する
            for (const child of this.media_element.children) {
                if (child instanceof HTMLCanvasElement) {
                    child.style.transform = `scaleY(${1 / magnification})`;
                    child.style.transformOrigin = 'center center';
                }
            }
        } else {
            this.media_element.style.transform = '';
            this.media_element.style.transformOrigin = '';
            for (const child of this.media_element.children) {
                if (child instanceof HTMLCanvasElement) {
                    child.style.transform = '';
                    child.style.transformOrigin = '';
                }
            }
        }

        this.is_video_element_moved_to_bml_browser = true;
    }


    /**
     * 映像の DOM 要素を BML ブラウザ (データ放送) から DPlayer 内に移動する
     * データ放送が非表示状態になるか、破棄されるときに呼び出される
     */
    private moveVideoElementToDPlayer(): void {

        // BML ブラウザの破棄中にイベントが発火した場合は何もしない
        if (this.is_bml_browser_destroying) {
            return;
        }

        // 既に DPlayer 内に映像の要素がある場合は何もしない
        if (this.is_video_element_moved_to_bml_browser === false) {
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
            }
            if (child instanceof HTMLCanvasElement) {
                child.style.transform = '';
                child.style.transformOrigin = '';
            }
        }
        this.media_element.style.transform = '';
        this.media_element.style.transformOrigin = '';

        this.is_video_element_moved_to_bml_browser = false;
    }


    /**
     * LiveDataBroadcastingManager での処理を終了し、破棄する
     */
    public async destroy(): Promise<void> {
        const channels_store = useChannelsStore();

        // ライブ PSI/SI アーカイブデータデコーダーを終了
        if (this.live_psi_archived_data_decoder !== null) {
            // タイミングの関係なのかチャンネル切り替え時の映像のフェードアウトが効かなくなるため、await してはいけない
            this.live_psi_archived_data_decoder.destroy();
            this.live_psi_archived_data_decoder = null;
        }

        // ChannelsStore に設定したリアルタイム番組情報を削除
        // ここで削除しないと再度更新されるまで channels_store.channel.current で古い番組情報が参照され続けてしまう
        // ストリーミングが開始され EPG から再度最新の番組情報を取得するまでの間は、サーバー API から取得した番組情報が表示される
        channels_store.current_program_present = null;
        channels_store.current_program_following = null;

        // リモコンの各ボタンに登録していたリスナーを削除
        if (this.remocon_button_event_abort_controller !== null) {
            this.remocon_button_event_abort_controller.abort();
            this.remocon_button_event_abort_controller = null;
        }

        // ここからはデータ放送機能有効時のみ実行
        if (this.#bml_browser !== null) {

            // リモコンのボタンを再び無効化
            this.toggleRemoconButtonsEnabled(false);

            // リモコンを再びローディング状態に戻す
            this.toggleRemoconButtonsLoading(true);

            // DPlayer のリサイズを監視する ResizeObserver を終了
            if (this.resize_observer !== null) {
                this.resize_observer.disconnect();
                this.resize_observer = null;
            }

            // データ放送内に移動していた映像の要素を DPlayer に戻す
            this.moveVideoElementToDPlayer();

            // BML ブラウザを破棄
            this.is_bml_browser_destroying = true;
            await this.#bml_browser.destroy();
            this.is_bml_browser_destroying = false;
            this.#bml_browser = null;

            // BML ブラウザの要素を削除
            this.container_element?.remove();

            console.log('[LiveDataBroadcastingManager] Destroyed.');
        }
    }
}

export default LiveDataBroadcastingManager;
