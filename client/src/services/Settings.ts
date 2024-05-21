
import APIClient from '@/services/APIClient';
import { getSyncableClientSettings } from '@/stores/SettingsStore';


/**
 * ミュート対象のコメントのキーワードのインターフェイス
 */
export interface IMutedCommentKeywords {
    match: 'partial' | 'forward' | 'backward' | 'exact' | 'regex';
    pattern: string;
}

/**
 * サーバーに保存されるクライアント設定を表すインターフェース
 * サーバー側の app.config.ClientSettings で定義されているものと同じ
 */
export interface IClientSettings {
    // showed_panel_last_time: 同期無効
    // selected_twitter_account_id: 同期無効
    saved_twitter_hashtags: string[];
    pinned_channel_ids: string[];
    panel_display_state: 'RestorePreviousState' | 'AlwaysDisplay' | 'AlwaysFold';
    tv_panel_active_tab: 'Program' | 'Channel' | 'Comment' | 'Twitter';
    video_panel_active_tab: 'RecordedProgram' | 'Series' | 'Comment' | 'Twitter';
    tv_channel_selection_requires_alt_key: boolean;
    // tv_streaming_quality: 同期無効
    // tv_streaming_quality_cellular: 同期無効
    // tv_data_saver_mode: 同期無効
    // tv_data_saver_mode_cellular: 同期無効
    // tv_low_latency_mode: 同期無効
    // tv_low_latency_mode_cellular: 同期無効
    // video_streaming_quality: 同期無効
    // video_streaming_quality_cellular: 同期無効
    // video_data_saver_mode: 同期無効
    // video_data_saver_mode_cellular: 同期無効
    caption_font: string;
    always_border_caption_text: boolean;
    specify_caption_opacity: boolean;
    caption_opacity: number;
    tv_show_superimpose: boolean;
    video_show_superimpose: boolean;
    // tv_show_data_broadcasting: 同期無効
    // enable_internet_access_from_data_broadcasting: 同期無効
    capture_save_mode: 'Browser' | 'UploadServer' | 'Both';
    capture_caption_mode: 'VideoOnly' | 'CompositingCaption' | 'Both';
    // capture_copy_to_clipboard: 同期無効
    // sync_settings: 同期無効
    comment_speed_rate: number;
    comment_font_size: number;
    close_comment_form_after_sending: boolean;
    mute_vulgar_comments: boolean;
    mute_abusive_discriminatory_prejudiced_comments: boolean;
    mute_big_size_comments: boolean;
    mute_fixed_comments: boolean;
    mute_colored_comments: boolean;
    mute_consecutive_same_characters_comments: boolean;
    muted_comment_keywords: IMutedCommentKeywords[];
    muted_niconico_user_ids: string[];
    fold_panel_after_sending_tweet: boolean;
    reset_hashtag_when_program_switches: boolean;
    auto_add_watching_channel_hashtag: boolean;
    twitter_active_tab: 'Search' | 'Timeline' | 'Capture';
    tweet_hashtag_position: 'Prepend' | 'Append' | 'PrependWithLineBreak' | 'AppendWithLineBreak';
    tweet_capture_watermark_position: 'None' | 'TopLeft' | 'TopRight' | 'BottomLeft' | 'BottomRight';
}

/**
 * サーバー設定を表すインターフェース
 * サーバー側の app.config.ServerSettings で定義されているものと同じ
 */
export interface IServerSettings {
    general: {
        backend: 'EDCB' | 'Mirakurun';
        always_receive_tv_from_mirakurun: boolean;
        edcb_url: string;
        mirakurun_url: string;
        encoder: 'FFmpeg' | 'QSVEncC' | 'NVEncC' | 'VCEEncC' | 'rkmppenc';
        program_update_interval: number;
        debug: boolean;
        debug_encoder: boolean;
    };
    server: {
        port: number;
        custom_https_certificate: string | null;
        custom_https_private_key: string | null;
    };
    tv: {
        max_alive_time: number;
        debug_mode_ts_path: string | null;
    };
    video: {
        recorded_folders: string[];
    };
    capture: {
        upload_folders: string[];
    };
}

/* サーバー設定を表すインターフェースのデフォルト値 */
export const IServerSettingsDefault: IServerSettings = {
    general: {
        backend: 'EDCB',
        always_receive_tv_from_mirakurun: false,
        edcb_url: 'tcp://127.0.0.1:4510/',
        mirakurun_url: 'http://127.0.0.1:40772/',
        encoder: 'FFmpeg',
        program_update_interval: 5.0,
        debug: false,
        debug_encoder: false,
    },
    server: {
        port: 7000,
        custom_https_certificate: null,
        custom_https_private_key: null,
    },
    tv: {
        max_alive_time: 10,
        debug_mode_ts_path: null,
    },
    video: {
        recorded_folders: [],
    },
    capture: {
        upload_folders: [],
    },
};


class Settings {

    /**
     * クライアント設定を取得する
     * @return クライアント設定 (取得に失敗した場合は null)
     */
    static async fetchClientSettings(): Promise<IClientSettings | null> {

        // API リクエストを実行
        const response = await APIClient.get<IClientSettings>('/settings/client');

        // エラー処理 (基本起こらないはず & 実行できなくても後続の処理に影響しないため何もしない)
        if (response.type === 'error') {
            return null;
        }

        // クライアント側の IClientSettings とサーバー側の app.config.ClientSettings は、バージョン差などで微妙に並び替え順序などが異なることがある
        // JSON シリアライズでの文字列比較を正しく行うため、厳密にクライアント側の IClientSettings と一致するように変換する
        return getSyncableClientSettings(response.data);
    }


    /**
     * クライアント設定を更新する
     * @param settings クライアント設定
     */
    static async updateClientSettings(settings: IClientSettings): Promise<void> {

        // API リクエストを実行
        // 正常時は 204 No Content が返るし、エラーは基本起こらないはずなので何もしない
        await APIClient.put<IClientSettings>('/settings/client', settings);
    }


    /**
     * サーバー設定を取得する
     * @return サーバー設定 (取得に失敗した場合は null)
     */
    static async fetchServerSettings(): Promise<IServerSettings | null> {

        // API リクエストを実行
        const response = await APIClient.get<IServerSettings>('/settings/server');

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サーバー設定を取得できませんでした。');
                    break;
            }
            return null;
        }

        return response.data;
    }

    /**
     * サーバー設定を更新する
     * @param settings サーバー設定
     * @return 成功した場合は true
     */
    static async updateServerSettings(settings: IServerSettings): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.put<IServerSettings>('/settings/server', settings);

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サーバー設定を更新できませんでした。');
                    break;
            }
            return false;
        }

        return true;
    }
}

export default Settings;
