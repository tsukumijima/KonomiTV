

import DPlayer from 'dplayer';
import { watch } from 'vue';

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


    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     */
    constructor(player: DPlayer) {
        this.player = player;
        this.watch_content_element = document.querySelector<HTMLDivElement>('.watch-content')!;
        this.watch_header_element = document.querySelector<HTMLDivElement>('.watch-header')!;
        this.watch_player_element = document.querySelector<HTMLDivElement>('.watch-player')!;
    }


    /**
     * Document Picture-in-Picture を開始するイベントハンドラーを登録する
     */
    public async init(): Promise<void> {
        const player_store = usePlayerStore();

        // Document Picture-in-Picture API がサポートされていない場合は何もしない
        if (('documentPictureInPicture' in window) === false) {
            console.log('[DocumentPiPManager] Initialized. (Document Picture-in-Picture API is not supported.)');
            return;
        }

        // DPlayer 上で Picture-in-Picture が開始された際のイベントを登録
        // HTMLVideoElement.requestPictureInPicture() に上書きしてイベントハンドラーを登録している
        this.request_picture_in_picture = this.player.video.requestPictureInPicture;  // 元のメソッドを退避
        this.player.video.requestPictureInPicture = async () => {

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

            // Document Picture-in-Picture ウインドウが表示された時のイベントを登録
            // すでに登録されている場合は上書きされる
            documentPictureInPicture.onenter = (event) => {
                player_store.is_document_pip = true;
                console.log('[DocumentPiPManager] Picture-in-Picture window entered.');
            };

            // Document Picture-in-Picture の開始をリクエスト
            const pip_window = await documentPictureInPicture.requestWindow({
                width: 540,
                height: 304,
            });

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

            // Dark Reader 拡張機能のサイトごとの無効化設定に関わらずダークモード CSS が追加されてしまうので、
            // Dark Reader 自体を無効化する
            // ref: https://github.com/darkreader/darkreader/blob/main/CONTRIBUTING.md#disabling-dark-reader-on-your-site
            const lock = pip_window.document.createElement('meta');
            lock.name = 'darkreader-lock';
            pip_window.document.head.appendChild(lock);

            // body 要素を .watch-container に見立ててクラスを追加
            pip_window.document.body.classList.add('watch-container');
            pip_window.document.body.classList.add('watch-container--fullscreen');
            pip_window.document.body.classList.add('watch-container--control-display');

            // player_store.is_control_display が変更された時に .watch-container--control-display クラスを追加・削除する
            watch(() => player_store.is_control_display, (value) => {
                if (value) {
                    pip_window.document.body.classList.add('watch-container--control-display');
                } else {
                    pip_window.document.body.classList.remove('watch-container--control-display');
                }
            });

            // Document Picture-in-Picture ウインドウに DOM 要素を移動
            const watch_content = pip_window.document.createElement('div');
            watch_content.classList.add('watch-content');
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

            // Document Picture-in-Picture ウインドウが閉じられた際のイベントを登録
            pip_window.addEventListener('pagehide', () => {
                player_store.is_document_pip = false;
                // メインウインドウ側の「ピクチャー イン ピクチャーを再生しています」テキストを削除
                playing_in_pip_container.remove();
                // DOM 要素を視聴画面内に戻す
                this.watch_content_element.append(this.watch_header_element);
                this.watch_content_element.append(this.watch_player_element);
                console.log('[DocumentPiPManager] Picture-in-Picture window exited.');
            });

            return {} as PictureInPictureWindow;  // 無理やり PictureInPictureWindow 型にキャスト
        };

        console.log('[DocumentPiPManager] Initialized.');
    }


    /**
     * Document Picture-in-Picture を開始するイベントハンドラーを削除する
     */
    public async destroy(): Promise<void> {

        // Document Picture-in-Picture API がサポートされていない場合は何もしない
        if (('documentPictureInPicture' in window) === false) {
            console.log('[DocumentPiPManager] Destroyed. (Document Picture-in-Picture API is not supported.)');
            return;
        }

        // Document Picture-in-Picture がまだ開始されている場合は終了
        if (documentPictureInPicture.window !== null) {
            documentPictureInPicture.window.close();
        }

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
