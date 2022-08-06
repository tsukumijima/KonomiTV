
/**
 * 共通ユーティリティ
 */
export default class Utils {

    // バージョン情報
    // ビルド時の環境変数 (vue.config.js に記載) から取得
    static readonly version: string = process.env.VUE_APP_VERSION;

    // バックエンドの API のベース URL
    static readonly api_base_url = (() => {
        if (process.env.NODE_ENV === 'development') {
            // デバッグ時はポートを 7000 に強制する
            return `${window.location.protocol}//${window.location.hostname}:7000/api`;
        } else {
            // ビルド後は同じポートを使う
            return `${window.location.protocol}//${window.location.host}/api`;
        }
    })();

    // デフォルトの設定値
    // (同期無効) とある項目は、デバイス間で同期するとかえって面倒なことになりそうなため同期されない設定
    // ここを変えたときはサーバー側の app.schemas も変更すること
    static readonly default_settings = {

        // ***** 設定画面から直接変更できない設定値 *****

        // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
        pinned_channel_ids: [] as string[],

        // 前回視聴画面を開いた際にパネルが表示されていたかどうか (同期無効)
        is_display_latest_panel: true as boolean,

        // 現在ツイート対象として選択されている Twitter アカウントの ID (同期無効)
        selected_twitter_account_id: null as number | null,

        // 保存している Twitter のハッシュタグが入るリスト
        saved_twitter_hashtags: [] as string[],

        // ***** 設定 → 全般 *****

        // テレビのストリーミング画質 (Default: 1080p) (同期無効)
        tv_streaming_quality: '1080p' as ('1080p' | '810p' | '720p' | '540p' | '480p' | '360p' | '240p'),

        // テレビをみるときに文字スーパーを表示する (Default: 表示する)
        is_display_superimpose_tv: true as boolean,

        // 既定のパネルの表示状態 (Default: 前回の状態を復元する)
        panel_display_state: 'RestorePreviousState' as ('RestorePreviousState' | 'AlwaysDisplay' | 'AlwaysFold'),

        // 既定で表示されるパネルのタブ (Default: 番組情報タブ)
        panel_active_tab: 'Program' as ('Program' | 'Channel' | 'Comment' | 'Twitter'),

        // キャプチャの保存先 (Default: ブラウザでダウンロード)
        capture_save_mode: 'Browser' as ('Browser' | 'UploadServer' | 'Both'),

        // 字幕が表示されているときのキャプチャの保存モード (Default: 映像のみのキャプチャと、字幕を合成したキャプチャを両方保存する)
        capture_caption_mode: 'Both' as ('VideoOnly' | 'CompositingCaption' | 'Both'),

        // ***** 設定 → ニコニコ実況 *****

        // コメントの速さ (Default: 1倍)
        comment_speed_rate: 1 as number,

        // コメントのフォントサイズ (Default: 34px)
        comment_font_size: 34 as number,

        // コメントの遅延時間 (Default: 1.5秒) (同期無効)
        comment_delay_time: 1.5 as number,

        // ***** 設定 → Twitter *****

        // 既定で表示される Twitter タブ内のタブ (Default: キャプチャタブ)
        twitter_active_tab: 'Capture' as ('Search' | 'Timeline' | 'Capture'),

        // ツイートにつけるハッシュタグの位置 (Default: ツイート本文の後に追加する)
        tweet_hashtag_position: 'Append' as ('Prepend' | 'Append' | 'PrependWithLineBreak' | 'AppendWithLineBreak'),

        // ツイートするキャプチャに番組名の透かしを描画する (Default: 透かしを描画しない)
        tweet_capture_watermark_position: 'None' as ('None' | 'TopLeft' | 'TopRight' | 'BottomLeft' | 'BottomRight'),
    };


    /**
     * 設定を LocalStorage から取得する
     * @param key 設定のキー名
     * @returns 設定されている値
     */
    static getSettingsItem(key: string): any | null {

        // LocalStorage から KonomiTV-Settings を取得
        // データは JSON で管理し、LocalStorage 上の一つのキーにまとめる
        // キーが存在しない場合はデフォルトの設定値を使う
        const settings: object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utils.default_settings;

        // そのキーが保存されているときだけ、設定値を返す
        if (key in settings) {
            return settings[key];
        } else {
            // デフォルトの設定値にあればそれを使う
            if (key in this.default_settings) {
                return this.default_settings[key];
            } else {
                return null;
            }
        }
    }


    /**
     * 設定を LocalStorage に保存する
     * @param key 設定のキー名
     * @param value 設定する値
     */
    static setSettingsItem(key: string, value: any): void {

        // LocalStorage から KonomiTV-Settings を取得
        const settings: object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utils.default_settings;

        // そのキーが default_settings に定義されているときだけ
        // バージョン違いなどで LocalStorage には登録されていないキーだが default_settings には登録されているケースが発生し得るため
        if (key in this.default_settings) {

            // 設定値を新しい値で置き換え
            settings[key] = value;

            // LocalStorage に保存
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));
        }
    }


    /**
     * アクセストークンを LocalStorage から取得する
     * @returns JWT アクセストークン（ログインしていない場合は null が返る）
     */
    static getAccessToken(): string | null {

        // LocalStorage の取得結果をそのまま返す
        // LocalStorage.getItem() はキーが存在しなければ（=ログインしていなければ）null を返す
        return localStorage.getItem('KonomiTV-AccessToken');
    }


    /**
     * アクセストークンを LocalStorage に保存する
     * @param access_token 発行された JWT アクセストークン
     */
    static saveAccessToken(access_token: string): void {

        // そのまま LocalStorage に保存
        localStorage.setItem('KonomiTV-AccessToken', access_token);
    }


    /**
     * ブラウザが実行されている OS に応じて、"Ctrl" または "Cmd" を返す
     * キーボードショートカットのコンビネーションキーの説明を OS によって分けるために使う
     * @returns ブラウザが実行されている OS が Mac なら Cmd を、それ以外なら Ctrl を返す
     */
    static CtrlOrCmd(): 'Ctrl' | 'Cmd' {
        // iPhone・iPad で純正キーボードを接続した場合も一応想定して、iPhone・iPad も含める（動くかは未検証）
        return /iPhone|iPad|Macintosh/i.test(navigator.userAgent) ? 'Cmd' : 'Ctrl';
    }


    /**
     * アクセストークンを LocalStorage から削除する
     * アクセストークンを削除することで、ログアウト相当になる
     */
    static deleteAccessToken(): void {

        // LocalStorage に KonomiTV-AccessToken キーが存在しない
        if (localStorage.getItem('KonomiTV-AccessToken') === null) return;

        // KonomiTV-AccessToken キーを削除
        localStorage.removeItem('KonomiTV-AccessToken');
    }


    /**
     * Blob に格納されている画像をブラウザにダウンロードさせる
     * @param blob HTMLCanvasElement.toBlob() で取得した Blob オブジェクト
     * @param filename 保存するファイル名
     */
    static downloadBlobImage(blob: Blob, filename: string): void {

        // Blob URL を発行
        const blob_url = URL.createObjectURL(blob);

        // 画像をダウンロード
        const link = document.createElement('a');
        link.download = filename;
        link.href = blob_url;
        link.click();

        // Blob URL を破棄
        URL.revokeObjectURL(blob_url);
    }


    /**
     * innerHTML しても問題ないように HTML の特殊文字をエスケープする
     * PHP の htmlspecialchars() と似たようなもの
     * @param content HTML エスケープされてないテキスト
     * @returns HTML エスケープされたテキスト
     */
    static escapeHTML(content: string): string {

        // HTML エスケープが必要な文字
        // ref: https://www.php.net/manual/ja/function.htmlspecialchars.php
        const html_escape_table = {
            '&': '&amp;',
            '"': '&quot;',
            '\'': '&apos;',
            '<': '&lt;',
            '>': '&gt;',
        };

        // ref: https://qiita.com/noriaki/items/4bfef8d7cf85dc1035b3
        return content.replace(/[&"'<>]/g, (match) => {
            return html_escape_table[match];
        });
    }


    /**
     * OAuth 連携時のポップアップを画面中央に表示するための windowFeatures 文字列を取得する
     * ref: https://qiita.com/catatsuy/items/babce8726ea78f5d25b1
     * @returns window.open() で使う windowFeatures 文字列
     */
    static getWindowFeatures(): string {

        // ポップアップウインドウのサイズ
        const popupSizeWidth = 650;
        const popupSizeHeight = window.screen.height >= 800 ? 800 : window.screen.height - 100;

        // ポップアップウインドウの位置
        const posTop = (window.screen.height - popupSizeHeight) / 2;
        const posLeft = (window.screen.width - popupSizeWidth) / 2;

        return `toolbar=0,status=0,top=${posTop},left=${posLeft},width=${popupSizeWidth},height=${popupSizeHeight},modal=yes,alwaysRaised=yes`;
    }


    /**
     * async/await でスリープ的なもの
     * @param seconds 待機する秒数
     * @returns Promise を返すので、await sleep(1); のように使う
     */
    static async sleep(seconds: number): Promise<number> {
        return await new Promise(resolve => setTimeout(resolve, seconds * 1000));
    }


    /**
     * 指定された値の型の名前を取得する
     * ref: https://qiita.com/amamamaou/items/ef0b797156b324bb4ef3
     * @returns 指定された値の型の名前
     */
    static typeof(value: any): string {
        return Object.prototype.toString.call(value).slice(8, -1).toLowerCase();
    }


    /**
     * 文字列中に含まれる URL をリンクの HTML に置き換える
     * @param text 置換対象の文字列
     * @returns URL をリンクに置換した文字列
     */
    static URLtoLink(text: string): string {

        // HTML の特殊文字で表示がバグらないように、事前に HTML エスケープしておく
        text = Utils.escapeHTML(text);

        // ref: https://www.softel.co.jp/blogs/tech/archives/6099
        const pattern = /(https?:\/\/[-A-Z0-9+&@#/%?=~_|!:,.;]*[-A-Z0-9+&@#/%=~_|])/ig;
        return text.replace(pattern, '<a href="$1" target="_blank">$1</a>');
    }
}
