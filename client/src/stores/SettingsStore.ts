
import { defineStore } from 'pinia';

import Settings, { IClientSettings, IMutedCommentKeywords } from '@/services/Settings';
import Utils from '@/utils';


export type VideoQuality = '1080p-60fps' | '1080p' | '810p' | '720p' | '540p' | '480p' | '360p' | '240p';

// LocalStorage に保存される KonomiTV の設定データ
interface ILocalClientSettings {
    pinned_channel_ids: string[];
    showed_panel_last_time: boolean;
    selected_twitter_account_id: number | null;
    saved_twitter_hashtags: string[];
    panel_display_state: 'RestorePreviousState' | 'AlwaysDisplay' | 'AlwaysFold';
    tv_panel_active_tab: 'Program' | 'Channel' | 'Comment' | 'Twitter';
    tv_channel_selection_requires_alt_key: boolean;
    tv_streaming_quality: VideoQuality;
    tv_streaming_quality_cellular: VideoQuality;
    tv_data_saver_mode: boolean;
    tv_data_saver_mode_cellular: boolean;
    tv_low_latency_mode: boolean;
    tv_low_latency_mode_cellular: boolean;
    caption_font: string;
    always_border_caption_text: boolean;
    specify_caption_opacity: boolean;
    caption_opacity: number;
    tv_show_superimpose: boolean;
    tv_show_data_broadcasting: boolean;
    capture_copy_to_clipboard: boolean;
    capture_save_mode: 'Browser' | 'UploadServer' | 'Both';
    capture_caption_mode: 'VideoOnly' | 'CompositingCaption' | 'Both';
    sync_settings: boolean;
    comment_speed_rate: number;
    comment_font_size: number;
    close_comment_form_after_sending: boolean;
    muted_comment_keywords: IMutedCommentKeywords[];
    muted_niconico_user_ids: string[];
    mute_vulgar_comments: boolean;
    mute_abusive_discriminatory_prejudiced_comments: boolean;
    mute_big_size_comments: boolean;
    mute_fixed_comments: boolean;
    mute_colored_comments: boolean;
    mute_consecutive_same_characters_comments: boolean;
    fold_panel_after_sending_tweet: boolean;
    reset_hashtag_when_program_switches: boolean;
    auto_add_watching_channel_hashtag: boolean;
    twitter_active_tab: 'Search' | 'Timeline' | 'Capture';
    tweet_hashtag_position: 'Prepend' | 'Append' | 'PrependWithLineBreak' | 'AppendWithLineBreak';
    tweet_capture_watermark_position: 'None' | 'TopLeft' | 'TopRight' | 'BottomLeft' | 'BottomRight';
}

// 設定データのうち、同期対象の設定キー
// サーバー側の app.schemas.ClientSettings と
// client/src/services/Settings.ts 内の IClientSettings で定義されているものと同じ
const sync_settings_keys = [
    'pinned_channel_ids',
    // showed_panel_last_time: 同期無効
    // selected_twitter_account_id: 同期無効
    'saved_twitter_hashtags',
    'panel_display_state',
    'tv_panel_active_tab',
    'tv_channel_selection_requires_alt_key',
    // tv_streaming_quality: 同期無効
    // tv_streaming_quality_cellular: 同期無効
    // tv_data_saver_mode: 同期無効
    // tv_data_saver_mode_cellular: 同期無効
    // tv_low_latency_mode: 同期無効
    // tv_low_latency_mode_cellular: 同期無効
    'caption_font',
    'always_border_caption_text',
    'specify_caption_opacity',
    'caption_opacity',
    'tv_show_superimpose',
    // tv_show_data_broadcasting: 同期無効
    // capture_copy_to_clipboard: 同期無効
    'capture_save_mode',
    'capture_caption_mode',
    // sync_settings: 同期無効
    'comment_speed_rate',
    'comment_font_size',
    'close_comment_form_after_sending',
    'muted_comment_keywords',
    'muted_niconico_user_ids',
    'mute_vulgar_comments',
    'mute_abusive_discriminatory_prejudiced_comments',
    'mute_big_size_comments',
    'mute_fixed_comments',
    'mute_colored_comments',
    'mute_consecutive_same_characters_comments',
    'fold_panel_after_sending_tweet',
    'reset_hashtag_when_program_switches',
    'auto_add_watching_channel_hashtag',
    'twitter_active_tab',
    'tweet_hashtag_position',
    'tweet_capture_watermark_position',
];

// LocalStorage に保存される KonomiTV の設定データのデフォルト値
const default_settings: ILocalClientSettings = {

    // ***** 設定画面から直接変更できない設定値 *****

    // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
    pinned_channel_ids: [],
    // 前回視聴画面を開いた際にパネルが表示されていたかどうか (同期無効)
    showed_panel_last_time: true,
    // 現在ツイート対象として選択されている Twitter アカウントの ID (同期無効)
    selected_twitter_account_id: null,
    // 保存している Twitter のハッシュタグが入るリスト
    saved_twitter_hashtags: [],

    // ***** 設定 → 全般 *****

    // デフォルトのパネルの表示状態 (Default: 前回の状態を復元する)
    panel_display_state: 'RestorePreviousState',
    // テレビをみるときにデフォルトで表示されるパネルのタブ (Default: 番組情報タブ)
    tv_panel_active_tab: 'Program',
    // チャンネル選局のキーボードショートカットを Alt or Option + 数字キー/テンキーに変更する (Default: オフ)
    tv_channel_selection_requires_alt_key: false,

    // ***** 設定 → 画質 *****

    // テレビのデフォルトのストリーミング画質 (Wi-Fi 回線時) (Default: 1080p) (同期無効)
    tv_streaming_quality: '1080p',
    // テレビのデフォルトのストリーミング画質 (モバイル回線時) (Default: 480p) (同期無効)
    tv_streaming_quality_cellular: '480p',
    // テレビを通信節約モードで視聴する (Wi-Fi 回線時)  (Default: オフ) (同期無効)
    tv_data_saver_mode: false,
    // テレビを通信節約モードで視聴する (モバイル回線時)  (Default: オン) (同期無効)
    tv_data_saver_mode_cellular: true,
    // テレビを低遅延で視聴する (Wi-Fi 回線時)  (Default: 低遅延で視聴する) (同期無効)
    tv_low_latency_mode: true,
    // テレビを低遅延で視聴する (モバイル回線時)  (Default: 低遅延で視聴しない) (同期無効)
    tv_low_latency_mode_cellular: false,

    // ***** 設定 → 字幕 *****

    // 字幕のフォント (Default: Windows TV 丸ゴシック)
    caption_font: 'Windows TV MaruGothic',
    // 字幕の文字を常に縁取って描画する (Default: 常に縁取る)
    always_border_caption_text: true,
    // 字幕の不透明度を指定する (Default: 指定しない)
    specify_caption_opacity: false,
    // 字幕の不透明度 (Default: 50%)
    caption_opacity: 0.5,
    // テレビをみるときに文字スーパーを表示する (Default: 表示する)
    tv_show_superimpose: true,

    // ***** 設定 → データ放送 *****

    // テレビをみるときにデータ放送を表示する (Default: 表示する) (同期無効)
    tv_show_data_broadcasting: true,

    // ***** 設定 → キャプチャ *****

    // キャプチャをクリップボードにコピーする (Default: 無効) (同期無効)
    capture_copy_to_clipboard: false,
    // キャプチャの保存先 (Default: KonomiTV サーバーにアップロード)
    capture_save_mode: 'UploadServer',
    // 字幕が表示されているときのキャプチャの保存モード (Default: 映像のみのキャプチャと、字幕を合成したキャプチャを両方保存する)
    capture_caption_mode: 'Both',

    // ***** 設定 → アカウント *****

    // 設定を同期する (Default: 同期しない) (同期無効)
    sync_settings: false,

    // ***** 設定 → ニコニコ実況 *****

    // コメントの速さ (Default: 1倍)
    comment_speed_rate: 1,
    // コメントのフォントサイズ (Default: 34px)
    comment_font_size: 34,
    // コメント送信後にコメント入力フォームを閉じる (Default: オン)
    close_comment_form_after_sending: true,

    // ***** 設定 → ニコニコ実況 (ミュート設定) *****

    // ミュート済みのコメントのキーワードが入るリスト
    muted_comment_keywords: [],
    // ミュート済みのニコニコユーザー ID が入るリスト
    muted_niconico_user_ids: [],
    // 露骨な表現を含むコメントをミュートする (Default: ミュートする)
    mute_vulgar_comments: true,
    // 罵倒や誹謗中傷、差別的な表現、政治的に偏った表現を含むコメントをミュートする (Default: ミュートする)
    mute_abusive_discriminatory_prejudiced_comments: true,
    // 文字サイズが大きいコメントをミュートする (Default: ミュートする)
    mute_big_size_comments: true,
    // 映像の上下に固定表示されるコメントをミュートする (Default: ミュートしない)
    mute_fixed_comments: false,
    // 色付きのコメントをミュートする (Default: ミュートしない)
    mute_colored_comments: false,
    // 8文字以上同じ文字が連続しているコメントをミュートする (Default: ミュートしない)
    mute_consecutive_same_characters_comments: false,

    // ***** 設定 → Twitter *****

    // ツイート送信後にパネルを折りたたむ (Default: オフ)
    fold_panel_after_sending_tweet: false,
    // 番組が切り替わったときにハッシュタグフォームをリセットする (Default: オン)
    reset_hashtag_when_program_switches: true,
    // 視聴中のチャンネルに対応する局タグを自動で追加する (Default: オン)
    auto_add_watching_channel_hashtag: true,
    // デフォルトで表示される Twitter タブ内のタブ (Default: キャプチャタブ)
    twitter_active_tab: 'Capture',
    // ツイートにつけるハッシュタグの位置 (Default: ツイート本文の後に追加する)
    tweet_hashtag_position: 'Append',
    // ツイートするキャプチャに番組名の透かしを描画する (Default: 透かしを描画しない)
    tweet_capture_watermark_position: 'None',
};

/**
 * LocalStorage の KonomiTV-Settings キーから設定データを取得する
 * @returns 設定データ
 */
export function getLocalStorageSettings(): {[key: string]: any} {
    const settings = localStorage.getItem('KonomiTV-Settings');
    if (settings !== null) {
        return JSON.parse(settings);
    } else {
        // もし LocalStorage に KonomiTV-Settings キーがまだない場合、あらかじめデフォルトの設定値を保存しておく
        setLocalStorageSettings(default_settings);
        return default_settings;
    }
}

/**
 * LocalStorage の KonomiTV-Settings キーに設定データを保存する
 * @param settings 設定データ
 */
export function setLocalStorageSettings(settings: {[key: string]: any}): void {
    localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));
}

/**
 * 与えられた設定データを並び替えたり足りない設定キーを補完したり不要な設定キーを削除したりと整形して返す
 * @param settings 設定データ
 */
function getNormalizedSettings(settings: {[key: string]: any}): ILocalClientSettings {

    // (名前が変わった、廃止されたなどの理由で) 現在の default_settings に存在しない設定キーを排除した上で並び替え
    // 並び替えられていないと設定データの比較がうまくいかない
    const new_settings: {[key: string]: any} = {};
    for (const default_settings_key of Object.keys(default_settings)) {
        if (default_settings_key in settings) {
            new_settings[default_settings_key] = settings[default_settings_key];
        } else {
            // 後のバージョンで追加されたなどの理由で現状の KonomiTV-Settings に存在しない設定キーの場合
            // その設定キーのデフォルト値を取得する
            new_settings[default_settings_key] = default_settings[default_settings_key];
        }
    }

    // この状態の新しい設定データを返す
    return new_settings as ILocalClientSettings;
}

/**
 * 設定データを共有するストア
 */
const useSettingsStore = defineStore('settings', {
    state: () => {

        // ref: https://www.vuemastery.com/blog/refresh-proof-your-pinia-stores/

        // LocalStorage から設定データを取得する
        const settings = getLocalStorageSettings();

        // (名前が変わった、廃止されたなどの理由で) 現在の default_settings に存在しない設定キーを排除した上で並び替え
        const new_settings = getNormalizedSettings(settings);

        // この状態の新しい設定データを LocalStorage に保存する
        setLocalStorageSettings(new_settings);

        // 設定データを Store の state のデフォルト値として返す
        return {
            settings: new_settings as ILocalClientSettings,
        };
    },
    actions: {

        /**
         * エクスポートした JSON ファイルから設定データをインポートする (既存の設定はすべて上書きされる)
         * @param file エクスポートした JSON ファイル
         * @returns インポートに成功したかどうか
         */
        async importClientSettings(file: File): Promise<boolean> {

            // JSON ファイルを読み込む
            const settings_json = await file.text();

            // JSON ファイルをパースする
            let settings = {};
            try {
                settings = JSON.parse(settings_json);
            } catch (error) {
                return false;
            }

            // (名前が変わった、廃止されたなどの理由で) 現在の default_settings に存在しない設定キーを排除した上で並び替え
            const new_settings = getNormalizedSettings(settings);

            // この状態の新しい設定データを LocalStorage に保存し、Store の state に反映する
            // このとき、既存の設定データはすべて上書きされる
            setLocalStorageSettings(new_settings);
            this.settings = new_settings;

            // 設定データをサーバーに同期する
            await this.syncClientSettingsToServer();

            return true;
        },

        /**
         * 設定データを初期状態にリセットする
         */
        async resetClientSettings(): Promise<void> {

            // デフォルトの設定に現在設定の同期がオンになっているかだけ反映した設定データ
            const default_settings_modified: ILocalClientSettings = {
                ...default_settings,
                sync_settings: this.settings.sync_settings,
            };

            // デフォルト値の設定データを LocalStorage に保存し、Store の state に反映する
            setLocalStorageSettings(default_settings_modified);
            this.settings = default_settings_modified;

            // 設定データをサーバーに同期する
            await this.syncClientSettingsToServer();
        },

        /**
         * 設定データのうち、サーバーへの同期対象の設定キーのみで構成されたオブジェクト (IClientSettings と一致する) を返す
         * @returns サーバーへの同期対象の設定キーのみで構成されたオブジェクト
         */
        getSyncableClientSettings(): IClientSettings {

            // 同期対象の設定キーのみで設定データをまとめ直す
            // sync_settings には同期対象外の設定は含まれない
            const sync_settings: {[key: string]: any} = {};
            for (const sync_settings_key of sync_settings_keys) {
                if (sync_settings_key in this.settings) {
                    sync_settings[sync_settings_key] = this.settings[sync_settings_key];
                } else {
                    // 後から追加された設定キーなどの理由で設定キーが現状の KonomiTV-Settings に存在しない場合
                    // その設定キーのデフォルト値を取得する
                    sync_settings[sync_settings_key] = default_settings[sync_settings_key];
                }
            }

            return sync_settings as IClientSettings;
        },

        /**
         * ログイン時かつ同期が有効な場合、サーバーに保存されている設定データをこのクライアントに同期する
         * @param force ログイン中なら同期が有効かに関わらず実行する (デフォルト: false)
         */
        async syncClientSettingsFromServer(force: boolean = false): Promise<void> {

            // ログインしていない時、同期が無効なときは実行しない
            if (Utils.getAccessToken() === null || (this.settings.sync_settings === false && force === false)) {
                return;
            }

            // サーバーから設定データをダウンロード
            const settings_server = await Settings.fetchClientSettings();
            if (settings_server === null) {
                return;  // 取得できなくても後続の処理には影響しないので、サイレントに失敗する
            }

            // クライアントの設定データをサーバーからの設定データで上書き
            for (const [settings_server_key, settings_server_value] of Object.entries(settings_server)) {
                this.settings[settings_server_key] = settings_server_value;
            }
        },

        /**
         * ログイン時かつ同期が有効な場合、このクライアントの設定をサーバーに同期する
         * @param force ログイン中なら同期が有効かに関わらず実行する (デフォルト: false)
         */
        async syncClientSettingsToServer(force: boolean = false): Promise<void> {

            // ログインしていない時、同期が無効なときは実行しない
            if (Utils.getAccessToken() === null || (this.settings.sync_settings === false && force === false)) {
                return;
            }

            // 同期対象の設定キーのみで設定データをまとめ直す
            const sync_settings = this.getSyncableClientSettings();

            // サーバーに設定データをアップロード
            await Settings.updateClientSettings(sync_settings);
        }
    }
});

export default useSettingsStore;
