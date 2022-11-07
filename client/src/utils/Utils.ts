
import Vue from 'vue';

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
    // ここを変えたときはサーバー側の app.schemas.ClientSettings も変更すること
    static readonly default_settings = {

        // ***** 設定画面から直接変更できない設定値 *****

        // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
        pinned_channel_ids: [] as string[],

        // 前回視聴画面を開いた際にパネルが表示されていたかどうか (同期無効)
        showed_panel_last_time: true as boolean,

        // 現在ツイート対象として選択されている Twitter アカウントの ID (同期無効)
        selected_twitter_account_id: null as number | null,

        // 保存している Twitter のハッシュタグが入るリスト
        saved_twitter_hashtags: [] as string[],

        // ***** 設定 → 全般 *****

        // テレビのストリーミング画質 (Default: 1080p) (同期無効)
        tv_streaming_quality: '1080p' as ('1080p-60fps' | '1080p' | '810p' | '720p' | '540p' | '480p' | '360p' | '240p'),

        // テレビを通信節約モードで視聴する (Default: オフ) (同期無効)
        tv_data_saver_mode: false as boolean,

        // テレビを低遅延で視聴する (Default: 低遅延で視聴する) (同期無効)
        tv_low_latency_mode: true as boolean,

        // テレビをみるときに文字スーパーを表示する (Default: 表示する)
        tv_show_superimpose: true as boolean,

        // 既定のパネルの表示状態 (Default: 前回の状態を復元する)
        panel_display_state: 'RestorePreviousState' as ('RestorePreviousState' | 'AlwaysDisplay' | 'AlwaysFold'),

        // テレビをみるときに既定で表示されるパネルのタブ (Default: 番組情報タブ)
        tv_panel_active_tab: 'Program' as ('Program' | 'Channel' | 'Comment' | 'Twitter'),

        // 字幕のフォント (Default: Windows TV 丸ゴシック)
        caption_font: 'Windows TV MaruGothic' as string,

        // 字幕の文字を常に縁取って描画する (Default: 常に縁取る)
        always_border_caption_text: true as boolean,

        // 字幕の背景色を指定する (Default: 指定しない)
        specify_caption_background_color: false as boolean,

        // 字幕の背景色 (Default: 不透明度が 50% の黒)
        caption_background_color: '#00000080' as string,

        // キャプチャをクリップボードにコピーする (Default: 有効) (同期無効)
        capture_copy_to_clipboard: true as boolean,

        // キャプチャの保存先 (Default: ブラウザでダウンロード)
        capture_save_mode: 'Browser' as ('Browser' | 'UploadServer' | 'Both'),

        // 字幕が表示されているときのキャプチャの保存モード (Default: 映像のみのキャプチャと、字幕を合成したキャプチャを両方保存する)
        capture_caption_mode: 'Both' as ('VideoOnly' | 'CompositingCaption' | 'Both'),

        // ***** 設定 → アカウント *****

        // 設定を同期する (Default: 同期しない) (同期無効)
        sync_settings: false as boolean,

        // ***** 設定 → ニコニコ実況 *****

        // コメントの速さ (Default: 1倍)
        comment_speed_rate: 1 as number,

        // コメントのフォントサイズ (Default: 34px)
        comment_font_size: 34 as number,

        // コメントの遅延時間 (Default: 1.75秒) (同期無効)
        comment_delay_time: 1.75 as number,

        // コメント送信後にコメント入力フォームを閉じる (Default: オン)
        close_comment_form_after_sending: true as boolean,

        // ***** 設定 → Twitter *****

        // ツイート送信後にパネルを閉じる (Default: オフ)
        fold_panel_after_sending_tweet: false as boolean,

        // 既定で表示される Twitter タブ内のタブ (Default: キャプチャタブ)
        twitter_active_tab: 'Capture' as ('Search' | 'Timeline' | 'Capture'),

        // ツイートにつけるハッシュタグの位置 (Default: ツイート本文の後に追加する)
        tweet_hashtag_position: 'Append' as ('Prepend' | 'Append' | 'PrependWithLineBreak' | 'AppendWithLineBreak'),

        // ツイートするキャプチャに番組名の透かしを描画する (Default: 透かしを描画しない)
        tweet_capture_watermark_position: 'None' as ('None' | 'TopLeft' | 'TopRight' | 'BottomLeft' | 'BottomRight'),
    };

    // 同期対象の設定キー
    // サーバー側の app.schemas.ClientSettings に定義されているものと同じ
    static readonly sync_settings_keys = [
        'pinned_channel_ids',
        'saved_twitter_hashtags',
        'tv_show_superimpose',
        'panel_display_state',
        'tv_panel_active_tab',
        'caption_font',
        'always_border_caption_text',
        'specify_caption_background_color',
        'caption_background_color',
        'capture_save_mode',
        'capture_caption_mode',
        'comment_speed_rate',
        'comment_font_size',
        'close_comment_form_after_sending',
        'fold_panel_after_sending_tweet',
        'twitter_active_tab',
        'tweet_hashtag_position',
        'tweet_capture_watermark_position',
    ];

    // 設定をサーバーにアップロード中かどうか
    // これが true のときは、定期的なサーバーからの設定ダウンロードを行わない
    static uploading_settings: boolean = false;


    /**
     * 設定を LocalStorage から取得する
     * @param key 設定のキー名
     * @returns 設定されている値
     */
    static getSettingsItem(key: string): any | null {

        // もし KonomiTV-Settings キーがまだない場合、あらかじめデフォルトの設定値を保存しておく
        if (localStorage.getItem('KonomiTV-Settings') === null) {
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(Utils.default_settings));
        }

        // LocalStorage から KonomiTV-Settings を取得
        // データは JSON で管理し、LocalStorage 上の一つのキーにまとめる
        const settings: {[key: string]: any} = JSON.parse(localStorage.getItem('KonomiTV-Settings'));

        // そのキーが保存されているときだけ、設定値を返す
        if (key in settings) {
            return settings[key];
        } else {
            // デフォルトの設定値にあればそれを使う
            if (key in Utils.default_settings) {
                return Utils.default_settings[key];
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

        // もし KonomiTV-Settings キーがまだない場合、あらかじめデフォルトの設定値を保存しておく
        if (localStorage.getItem('KonomiTV-Settings') === null) {
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(Utils.default_settings));
        }

        // LocalStorage から KonomiTV-Settings を取得
        const settings: {[key: string]: any} = JSON.parse(localStorage.getItem('KonomiTV-Settings'));

        // 設定値を新しい値で置き換え
        settings[key] = value;

        // (名前が変わった、廃止されたなどの理由で) 現在の default_settings に存在しない設定キーを排除した上で並び替え
        // 並び替えられていないと設定データの比較がうまくいかない
        const new_settings: {[key: string]: any} = {};
        for (const default_settings_key of Object.keys(Utils.default_settings)) {
            if (default_settings_key in settings) {
                new_settings[default_settings_key] = settings[default_settings_key];
            } else {
                // 後から追加された設定キーなどの理由で設定キーが現状の KonomiTV-Settings に存在しない場合
                // その設定キーのデフォルト値を取得する
                new_settings[default_settings_key] = Utils.default_settings[default_settings_key];
            }
        }

        // LocalStorage に保存
        localStorage.setItem('KonomiTV-Settings', JSON.stringify(new_settings));

        // 更新された設定をサーバーに同期 (同期有効時のみ)
        Utils.syncClientSettingsToServer();
    }


    /**
     * ログイン時かつ同期が有効な場合、サーバーに保存されている設定データをこのクライアントに同期する
     * @param force ログイン中なら同期が有効かに関わらず実行する (デフォルト: false)
     */
    static async syncServerSettingsToClient(force = false): Promise<void> {

        // LocalStorage から KonomiTV-Settings を取得
        const settings: {[key: string]: any} = JSON.parse(localStorage.getItem('KonomiTV-Settings'));

        // ログインしていない時、同期が無効なときは実行しない
        if (Utils.getAccessToken() === null || (settings.sync_settings === false && force === false)) {
            return;
        }

        // 設定データをアップロード中のときは、動作が競合しないように終わるまで待つ
        while (Utils.uploading_settings === true) {
            await Utils.sleep(0.1);
        }

        try {

            // サーバーから設定データをダウンロード
            const server_settings: {[key: string]: any} = (await Vue.axios.get('/settings/client')).data;

            // クライアントの設定値をサーバーからの設定値で上書き
            for (const [server_settings_key, server_settings_value] of Object.entries(server_settings)) {
                settings[server_settings_key] = server_settings_value;
            }

            // LocalStorage に保存
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));

        } catch (error) {
            // 何らかの理由でエラーになったときは何もしない
        }
    }


    /**
     * ログイン時かつ同期が有効な場合、このクライアントの設定をサーバーに同期する
     * @param force ログイン中なら同期が有効かに関わらず実行する (デフォルト: false)
     */
    static async syncClientSettingsToServer(force = false): Promise<void> {

        // LocalStorage から KonomiTV-Settings を取得
        const settings: {[key: string]: any} = JSON.parse(localStorage.getItem('KonomiTV-Settings'));

        // ログインしていない時、同期が無効なときは実行しない
        if (Utils.getAccessToken() === null || (settings.sync_settings === false && force === false)) {
            return;
        }

        // 設定データのアップロード開始
        Utils.uploading_settings = true;

        // 同期対象の設定キーのみで設定データをまとめ直す
        // sync_settings には同期対象外の設定は含まれない
        const sync_settings: {[key: string]: any} = {};
        for (const sync_settings_key of Utils.sync_settings_keys) {
            if (sync_settings_key in settings) {
                sync_settings[sync_settings_key] = settings[sync_settings_key];
            } else {
                // 後から追加された設定キーなどの理由で設定キーが現状の KonomiTV-Settings に存在しない場合
                // その設定キーのデフォルト値を取得する
                sync_settings[sync_settings_key] = Utils.default_settings[sync_settings_key];
            }
        }

        // サーバーに設定データをアップロード
        try {
            await Vue.axios.put('/settings/client', sync_settings);
        } catch (error) {
            // 何もしない
        }

        // 設定データのアップロード終了
        Utils.uploading_settings = false;
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
     * ブラウザが実行されている OS に応じて、"Ctrl" または "Cmd" を返す
     * キーボードショートカットのコンビネーションキーの説明を OS によって分けるために使う
     * @returns ブラウザが実行されている OS が Mac なら Cmd を、それ以外なら Ctrl を返す
     */
    static CtrlOrCmd(): 'Ctrl' | 'Cmd' {
        // iPhone・iPad で純正キーボードを接続した場合も一応想定して、iPhone・iPad も含める（動くかは未検証）
        return /iPhone|iPad|Macintosh/i.test(navigator.userAgent) ? 'Cmd' : 'Ctrl';
    }


    /**
     * Blob に格納されているデータをブラウザにダウンロードさせる
     * @param blob Blob オブジェクト
     * @param filename 保存するファイル名
     */
    static downloadBlobData(blob: Blob, filename: string): void {

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
     * 現在フォーカスを持っている要素に指定された CSS クラスが付与されているか
     * @param class_name 存在を確認する CSS クラス名
     * @returns document.activeElement が class_name で指定したクラスを持っているかどうか
     */
    static hasActiveElementClass(class_name: string): boolean {
        if (document.activeElement === null) return false;
        return document.activeElement.classList.contains(class_name);
    }


    /**
     * 表示画面がスマホ横画面かどうか
     * @returns スマホ横画面なら true を返す
     */
    static isSmartphoneHorizontal(): boolean {
        return window.matchMedia('(max-width: 1000px) and (max-height: 450px)').matches;
    }


    /**
     * 表示画面がスマホ縦画面かどうか
     * @returns スマホ縦画面なら true を返す
     */
    static isSmartphoneVertical(): boolean {
        return window.matchMedia('(max-width: 600px) and (min-height: 450.01px)').matches;
    }


    /**
     * 表示画面がタブレット横画面かどうか
     * @returns タブレット横画面なら true を返す
     */
    static isTabletHorizontal(): boolean {
        return window.matchMedia('(max-width: 1264px) and (max-height: 850px)').matches;
    }


    /**
     * 表示画面がタブレット縦画面かどうか
     * @returns タブレット縦画面なら true を返す
     */
    static isTabletVertical(): boolean {
        return window.matchMedia('(max-width: 850px) and (min-height: 850.01px)').matches;
    }


    /**
     * 任意の桁で切り捨てする
     * ref: https://qiita.com/nagito25/items/0293bc317067d9e6c560#comment-87f0855f388953843037
     * @param value 切り捨てする数値
     * @param base どの桁で切り捨てするか (-1 → 10の位 / 3 → 小数第3位）
     * @return 切り捨てした値
     */
    static mathFloor(value: number, base: number = 0): number {
        return Math.floor(value * (10**base)) / (10**base);
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
     * 現在時刻の UNIX タイムスタンプを取得する (デバッグ用)
     * @returns 現在時刻の UNIX タイムスタンプ
     */
    static time(): number {
        return Date.now() / 1000;
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
