
import DPlayer from 'dplayer';
import { Deinterlacer } from 'mpeg2toh264/yadif';
import { watch } from 'vue';
import { bmlBrowserFontNames } from 'web-bml';

import KeyboardShortcutManager from '@/services/player/managers/KeyboardShortcutManager';
import LiveDataBroadcastingManager from '@/services/player/managers/LiveDataBroadcastingManager';
import PlayerManager from '@/services/player/PlayerManager';
import usePlayerStore from '@/stores/PlayerStore';


/**
 * Document Picture-in-Picture を管理する PlayerManager
 * 実装簡素化のため、HTMLVideoElement.requestPictureInPicture() による映像のみの Picture-in-Picture 開始処理を乗っ取る形で実装している
 * こうすることで、別途新たにキーボードショートカットやクリックイベントを実装する必要がなくなる
 */
class DocumentPiPManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
    public readonly restart_required_when_quality_switched = false;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // 視聴画面内のコンテンツ全体の DOM 要素
    private readonly watch_content_element: HTMLDivElement;

    // 視聴画面内のプレイヤーヘッダーの DOM 要素
    // .watch-content の下に .watch-header があることを前提としている
    private readonly watch_header_element: HTMLDivElement;

    // 視聴画面内のプレイヤー全体の DOM 要素
    // .watch-content の下に .watch-player があることを前提としている
    private readonly watch_player_element: HTMLDivElement;

    // ネイティブの HTMLVideoElement.requestPictureInPicture() メソッド
    private request_picture_in_picture: (() => Promise<PictureInPictureWindow>) | null = null;

    // 元画面に残した video 要素と、PinP 内でその寸法を維持する要素
    private retained_video: {
        video: HTMLVideoElement;
        container: HTMLElement;
        placeholder: HTMLDivElement;
        host: HTMLDivElement;
        original_style: string | null;
        resize_observer: ResizeObserver;
        update_aspect_ratio: () => void;
    } | null = null;

    // 画質切り替え時、デインタレーサーの生成前に元画面へ移した video 要素
    private pending_video: { video: HTMLVideoElement; anchor: Comment; host: HTMLDivElement } | null = null;

    // PinP の開始待ち中に PlayerManager が破棄されたことを判定するフラグ
    private is_destroying = false;


    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     * @param playback_mode 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
     */
    constructor(player: DPlayer, playback_mode: 'Live' | 'Video') {
        this.player = player;
        this.playback_mode = playback_mode;
        this.watch_content_element = document.querySelector<HTMLDivElement>('.watch-content')!;
        this.watch_header_element = document.querySelector<HTMLDivElement>('.watch-header')!;
        this.watch_player_element = document.querySelector<HTMLDivElement>('.watch-player')!;
    }


    /**
     * Document Picture-in-Picture を開始するイベントハンドラーを登録する
     */
    public async init(): Promise<void> {
        this.is_destroying = false;
        const player_store = usePlayerStore();

        // Document Picture-in-Picture API がサポートされていない場合は何もしない
        if (('documentPictureInPicture' in window) === false) {
            console.log('[DocumentPiPManager] Initialized. (Document Picture-in-Picture API is not supported.)');
            return;
        }

        // DPlayer 上で Picture-in-Picture が開始された際のイベントを登録
        // HTMLVideoElement.requestPictureInPicture() に上書きしてイベントハンドラーを登録している
        const new_request_picture_in_picture = async () => {

            // すでに Document Picture-in-Picture が開始されている場合は終了
            // この時 Document Picture-in-Picture ウインドウでは pagehide イベントが発火する
            if (documentPictureInPicture.window) {
                documentPictureInPicture.window.close();
                return {} as PictureInPictureWindow;  // 無理やり PictureInPictureWindow 型にキャスト
            }

            // 下記のコードの実装にあたり、以下のリンクを参考にした
            // ref: https://document-picture-in-picture-api.glitch.me/script.js
            // ref: https://developer.chrome.com/docs/web-platform/document-picture-in-picture
            // ref: https://medium.com/@abhishek_guy/guide-to-use-the-document-picture-in-picture-api-51ecfac058f7
            // Chrome 134 以降では、条件を満たす場合、KonomiTV からタブを切り替えた際に自動的に Document Picture-in-Picture が開始される
            // ref: https://developer.chrome.com/blog/automatic-picture-in-picture-media-playback?hl=ja

            // Document Picture-in-Picture ウインドウが表示された時のイベントを登録
            // すでに登録されている場合は上書きされる
            documentPictureInPicture.onenter = (event) => {
                console.log('[DocumentPiPManager] Picture-in-Picture window entered.');
                player_store.is_document_pip = true;
                // コントロール表示タイマーをリセット
                player_store.event_emitter.emit('SetControlDisplayTimer', {
                    is_player_region_event: true,
                    timeout_seconds: 0,
                });
            };

            // Document Picture-in-Picture の開始をリクエスト
            // ここで指定する幅・高さはあくまで初期値で、ユーザーが手動でリサイズした後はリサイズ後の値が利用される
            const pip_window = await documentPictureInPicture.requestWindow({
                width: 540,
                height: 304,
            });
            if (this.is_destroying) {
                pip_window.close();
                return {} as PictureInPictureWindow;
            }

            // Dark Reader 拡張機能を使っている場合、何故か Document Picture-in-Picture ウインドウでは
            // サイトごとの無効化設定に関わらずダークモード CSS が追加されてしまうため、Dark Reader 自体を無効化する
            // ref: https://github.com/darkreader/darkreader/blob/main/CONTRIBUTING.md#disabling-dark-reader-on-your-site
            const lock = pip_window.document.createElement('meta');
            lock.name = 'darkreader-lock';
            pip_window.document.head.appendChild(lock);

            // すべてのスタイルシートを Document Picture-in-Picture ウインドウにコピー
            // 以前の仕様には copyStyleSheets オプションがあったが、議論の末に削除されてしまったらしい
            [...document.styleSheets].forEach((style_sheet) => {
                try {
                    const cssRules = [...style_sheet.cssRules].map((rule) => rule.cssText).join('');
                    const style = document.createElement('style');
                    style.textContent = cssRules;
                    pip_window.document.head.appendChild(style);
                } catch (e) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.type = style_sheet.type;
                    link.media = style_sheet.media.mediaText;
                    link.href = style_sheet.href!;
                    pip_window.document.head.appendChild(link);
                }
            });

            // データ放送用のフォントを読み込む
            // web-bml 側でロードしたフォントはメインウインドウにしか存在しないため、別途ロードする必要がある
            const round_gothic_font = new FontFace(bmlBrowserFontNames.roundGothic, LiveDataBroadcastingManager.ROUND_GOTHIC.source);
            round_gothic_font.load();
            pip_window.document.fonts.add(round_gothic_font);
            const square_gothic_font = new FontFace(bmlBrowserFontNames.squareGothic, LiveDataBroadcastingManager.SQUARE_GOTHIC.source);
            square_gothic_font.load();
            pip_window.document.fonts.add(square_gothic_font);

            // body 要素を .watch-container に見立ててクラスを追加
            pip_window.document.body.classList.add('watch-container');
            pip_window.document.body.classList.add('watch-container--fullscreen');

            // player_store.is_control_display が変更された時に .watch-container--control-display クラスを追加・削除する
            const stop_control_display_watcher = watch(() => player_store.is_control_display, (value) => {
                if (value) {
                    pip_window.document.body.classList.add('watch-container--control-display');
                } else {
                    pip_window.document.body.classList.remove('watch-container--control-display');
                }
            });

            // Document Picture-in-Picture ウインドウに DOM 要素を移動
            const watch_content = pip_window.document.createElement('div');
            watch_content.classList.add('watch-content');
            watch_content.style.height = '100vh';  // ここで 100vh を指定しないと、Chrome 131 以降データ放送表示時に高さが 0px になり PiP ウインドウが真っ黒になる

            // Canvas 表示時は、フレーム通知の予約先が閉じる PinP の Document に切り替わらないよう、video 要素を元画面に残す
            const deinterlacer = this.player.plugins.mpeg2toh264?.deinterlacer;
            if (deinterlacer instanceof Deinterlacer && deinterlacer.container !== this.player.video) {
                this.retainVideoElement(this.player.video, deinterlacer.container);
            }
            watch_content.append(this.watch_header_element);
            watch_content.append(this.watch_player_element);
            pip_window.document.body.append(watch_content);

            // メインウインドウ側に「ピクチャー イン ピクチャーを再生しています」というテキストを追加
            const playing_in_pip_container = document.createElement('div');
            playing_in_pip_container.classList.add('playing-in-pip');
            const playing_in_pip_text = document.createElement('span');
            playing_in_pip_text.classList.add('playing-in-pip__text');
            playing_in_pip_text.textContent = 'Picture-in-Picture を再生しています';
            playing_in_pip_container.append(playing_in_pip_text);
            const playing_in_pip_close_button = document.createElement('button');
            playing_in_pip_close_button.classList.add('playing-in-pip__close-button');
            playing_in_pip_close_button.textContent = 'Picture-in-Picture を終了';
            playing_in_pip_close_button.onclick = () => pip_window.close();
            playing_in_pip_container.append(playing_in_pip_close_button);
            this.watch_content_element.append(playing_in_pip_container);

            // Document Picture-in-Picture ウインドウにマウスカーソルが入った際のイベントを登録
            // コントロール UI の表示状態に影響する
            const event_listener = (event: Event) => {
                player_store.event_emitter.emit('SetControlDisplayTimer', {
                    event: event,
                    is_player_region_event: true,
                    // Document Picture-in-Picture ウインドウではコントロール UI を非表示にするまでの秒数を短くする
                    timeout_seconds: 1.25,
                });
            };
            watch_content.addEventListener('mousemove', event_listener);
            watch_content.addEventListener('touchmove', event_listener);
            watch_content.addEventListener('click', event_listener);

            // キーボードショートカットを登録
            // 通常 KeyboardShortcutManager は PlayerController で管理されるが、この Document Picture-in-Picture ウインドウには
            // キーボードショートカットイベントが登録されておらず、さらにウインドウが閉じられればウインドウ内に登録したイベントも全削除されるため、
            // 別途このウインドウにおいてキーボードショートカットを管理する KeyboardShortcutManager を生成・初期化している
            // 第3引数に Document Picture-in-Picture ウインドウの Document オブジェクトを渡しているのがポイント
            const keyboard_shortcut_manager = new KeyboardShortcutManager(this.player, this.playback_mode, pip_window.document);
            keyboard_shortcut_manager.init();  // 完了を待たない

            // Document Picture-in-Picture ウインドウが閉じられた際のイベントを登録
            // すでに登録されている場合は上書きされる
            pip_window.onpagehide = () => {
                player_store.is_document_pip = false;
                // is_control_display の watcher を停止
                stop_control_display_watcher();
                // キーボードショートカットを削除
                keyboard_shortcut_manager.destroy();  // 完了を待たない
                // メインウインドウ側の「ピクチャー イン ピクチャーを再生しています」テキストを削除
                playing_in_pip_container.remove();
                // DOM 要素を視聴画面内に戻す
                this.watch_content_element.append(this.watch_header_element);
                this.watch_content_element.append(this.watch_player_element);
                this.restoreVideoElement();
                console.log('[DocumentPiPManager] Picture-in-Picture window exited.');
            };

            return {} as PictureInPictureWindow;  // 無理やり PictureInPictureWindow 型にキャスト
        };

        // オリジナルのブラウザネイティブ実装の HTMLVideoElement.requestPictureInPicture() メソッドを退避
        this.request_picture_in_picture = this.player.video.requestPictureInPicture;
        // 独自のフックで上書きする
        this.player.video.requestPictureInPicture = new_request_picture_in_picture;

        // 新しいデインタレーサーの生成後、元画面で作られた Canvas のコンテナだけを PinP 内の元の位置へ移す
        this.player.on('quality_start', () => {
            this.restoreRetainedVideoElement();
            const pending_video = this.pending_video;
            if (pending_video === null) {
                return;
            }
            this.pending_video = null;
            const deinterlacer = this.player.plugins.mpeg2toh264?.deinterlacer;
            if (deinterlacer instanceof Deinterlacer && deinterlacer.container !== pending_video.video) {
                this.retainVideoElement(pending_video.video, deinterlacer.container, pending_video.host);
                pending_video.anchor.replaceWith(deinterlacer.container);
            } else {
                pending_video.anchor.replaceWith(pending_video.video);
                pending_video.host.remove();
            }
        });

        // 画質切り替え後に新しい映像要素が生成されるため、画質切り替え後に再度フックする
        this.player.on('quality_end', () => {
            if (!this.player || !this.player.video) {
                return;
            }
            // 画質切り替え後の this.player.video は切り替え前の this.player.video とは
            // 異なる HTMLVideoElement のインスタンスとなるため、再度オリジナルの関数を退避した上で、独自のフックを適用する
            this.request_picture_in_picture = this.player.video.requestPictureInPicture;
            this.player.video.requestPictureInPicture = new_request_picture_in_picture;
        });

        console.log('[DocumentPiPManager] Initialized.');
    }


    /**
     * 画質切り替えで作られた video 要素を、フレーム通知の登録前に元画面へ移す
     * @param video 新しい video 要素
     */
    public prepareVideoElement(video: HTMLVideoElement): void {
        if (('documentPictureInPicture' in window) === false || documentPictureInPicture.window === null) {
            return;
        }
        this.restoreVideoElement();

        // Canvas の生成後に同じ位置へ戻せるよう、PinP 内に目印を置く
        const anchor = document.createComment('');
        video.before(anchor);
        const host = document.createElement('div');
        host.style.cssText = 'position:fixed;left:-10000px;top:0;width:640px;height:360px;pointer-events:none;overflow:hidden';
        document.body.append(host);
        host.append(video);
        this.pending_video = { video, anchor, host };
    }


    /**
     * video 要素を元画面に残し、表示用コンテナの寸法を代替要素で維持する
     * @param video 元画面に残す video 要素
     * @param container Canvas と video 要素を囲むコンテナ
     * @param host 画質切り替え時に作成済みの格納先
     */
    private retainVideoElement(video: HTMLVideoElement, container: HTMLElement, host = document.createElement('div')): void {
        const original_style = video.getAttribute('style');
        const placeholder = document.createElement('div');
        // データ放送の CSS が子要素にも適用されるため、位置・表示・高さも明示する
        placeholder.style.cssText = 'position:relative;display:block;width:99999px;max-width:100%;height:auto';
        const update_aspect_ratio = () => {
            placeholder.style.aspectRatio = `${video.videoWidth || 1920} / ${video.videoHeight || 1080}`;
        };
        update_aspect_ratio();
        container.insertBefore(placeholder, video);

        // display:none でデコードやレイアウトを止めず、元画面の表示領域外に配置する
        host.style.cssText = 'position:fixed;left:-10000px;top:0;pointer-events:none;overflow:hidden';
        document.body.append(host);
        host.append(video);
        video.style.cssText = 'position:relative;display:block;width:100%;height:100%;left:0;top:0;object-fit:contain';

        // クロップの transform が適用される前の寸法を使い、映像の拡大が二重に掛からないようにする
        const update_size = () => {
            host.style.width = `${placeholder.offsetWidth}px`;
            host.style.height = `${placeholder.offsetHeight}px`;
        };
        // video 側の ResizeObserver と同じ通知中に寸法を変えると通知が循環するため、次の描画へ送る
        const resize_observer = new ResizeObserver(() => window.requestAnimationFrame(() => {
            if (this.retained_video?.video === video) {
                update_size();
            }
        }));
        resize_observer.observe(placeholder);
        video.addEventListener('resize', update_aspect_ratio);
        this.retained_video = { video, container, placeholder, host, original_style, resize_observer, update_aspect_ratio };
        update_size();
    }


    /**
     * 元画面に残していた video 要素を表示用コンテナへ戻す
     */
    private restoreRetainedVideoElement(): void {
        const retained_video = this.retained_video;
        if (retained_video === null) {
            return;
        }
        this.retained_video = null;
        const { video, container, placeholder, host, original_style, resize_observer, update_aspect_ratio } = retained_video;
        resize_observer.disconnect();
        video.removeEventListener('resize', update_aspect_ratio);
        // 画質切り替えでデインタレーサーが破棄済みなら、video 要素はすでに DPlayer の元の位置へ戻されている
        if (container.isConnected && placeholder.isConnected) {
            container.insertBefore(video, placeholder);
        }
        placeholder.remove();
        if (original_style === null) {
            video.removeAttribute('style');
        } else {
            video.setAttribute('style', original_style);
        }
        host.remove();
    }


    /**
     * PinP の終了時に、生成待ちの video 要素も含めて元の配置へ戻す
     */
    private restoreVideoElement(): void {
        this.restoreRetainedVideoElement();
        if (this.pending_video !== null) {
            this.pending_video.anchor.replaceWith(this.pending_video.video);
            this.pending_video.host.remove();
            this.pending_video = null;
        }
    }


    /**
     * Document Picture-in-Picture を開始するイベントハンドラーを削除する
     */
    public async destroy(): Promise<void> {

        this.is_destroying = true;

        // Document Picture-in-Picture API がサポートされていない場合は何もしない
        if (('documentPictureInPicture' in window) === false) {
            console.log('[DocumentPiPManager] Destroyed. (Document Picture-in-Picture API is not supported.)');
            return;
        }

        // Document Picture-in-Picture がまだ開始されている場合は終了
        if (documentPictureInPicture.window !== null) {
            documentPictureInPicture.window.close();
        }
        this.restoreVideoElement();

        // Document Picture-in-Picture ウインドウが表示された時のイベントを削除
        documentPictureInPicture.onenter = null;

        // DPlayer 上で Picture-in-Picture が開始された際のイベントを削除
        if (this.request_picture_in_picture !== null) {
            this.player.video.requestPictureInPicture = this.request_picture_in_picture;  // 元のメソッドに戻す
        }

        console.log('[DocumentPiPManager] Destroyed.');
    }
}

export default DocumentPiPManager;
