
import mitt from 'mitt';
import { defineStore } from 'pinia';

import { ITweetCapture } from '@/components/Watch/Panel/Twitter.vue';
import { ICommentData } from '@/services/player/managers/LiveCommentManager';
import { IRecordedProgram, IRecordedProgramDefault } from '@/services/Videos';
import useSettingsStore from '@/stores/SettingsStore';


/**
 * プレイヤーに関連するイベントの型
 * PlayerManager 側からのイベントも UI 側からのイベントも PlayerEvents を通じて行う
 */
export type PlayerEvents = {
    // UI コンポーネントからプレイヤーに通知メッセージの送信を要求する
    // DPlayer.notice() の引数と同じで、そのまま DPlayer.notice() に渡される
    SendNotification: {
        message: string;  // 通知メッセージの内容
        duration?: number;  // 通知メッセージの表示時間 (ミリ秒)
        opacity?: number;  // 通知メッセージの透明度
        color?: string;  // 通知メッセージの文字色
    }
    // PlayerManager からプレイヤーの再起動が必要になったことを通知する
    PlayerRestartRequired: {
        message?: string;  // プレイヤーに通知するメッセージ
        is_error_message?: boolean;  // メッセージをエラーメッセージとして表示するか (既定は true)
    };
    // PlayerController.setControlDisplayTimer() をそのまま呼び出す
    SetControlDisplayTimer: {
        event?: Event;  // マウスやタッチイベント (手動実行する際は省略する)
        is_player_region_event?: boolean;  // プレイヤー画面の中で発火したイベントなら true に設定する
        timeout_seconds?: number;  // 何も操作がない場合にコントロール UI を非表示にするまでの秒数
    }
    // CaptureManager からキャプチャの撮影が完了したことを通知する
    CaptureCompleted: {
        capture: Blob;  // キャプチャの Blob
        filename: string;  // キャプチャのファイル名 (UI からの手動ダウンロード時に使う)
    };
    // LiveCommentManager からコメントを受信したことを通知する
    CommentReceived: {
        is_initial_comments: boolean;  // 初期コメントかどうか
        comments: ICommentData[];  // コメントデータのリスト
    }
    // ライブ視聴: LiveCommentManager からコメントを送信したことを通知する
    CommentSendCompleted: {
        comment: ICommentData;  // 送信したコメントデータ (を整形したもの)
    }
};


/**
 * プレイヤー側の再生系ロジックと UI 側で共有される状態を管理するストア
 * 主に PlayerController や PlayerManager から状態変化に合わせて変更された値をリアクティブに UI に反映するためのもの
 */
const usePlayerStore = defineStore('player', {
    state: () => ({

        // 現在視聴画面を表示しているか
        // 既定で表示していない
        is_watching: false,

        // PlayerController が初期化されているか
        is_player_initialized: false,

        // プレイヤーに関連するイベントを発行する EventEmitter
        event_emitter: mitt<PlayerEvents>(),

        // 現在視聴中の録画番組の情報
        // 視聴中の録画番組がない場合は IRecordedProgramDefault を設定すべき (初期値も IRecordedProgramDefault にしている)
        recorded_program: IRecordedProgramDefault as IRecordedProgram,

        // 仮想キーボードが表示されているか
        // 既定で表示されていない想定
        is_virtual_keyboard_display: false,

        // フルスクリーン状態かどうか
        is_fullscreen: false,

        // Document Picture-in-Picture モードかどうか
        is_document_pip: false,

        // コントロールを表示するか
        is_control_display: true,

        // パネルを表示するか
        // panel_display_state が "AlwaysDisplay" なら常に表示し、"AlwaysFold" なら常に折りたたむ
        // "RestorePreviousState" なら showed_panel_last_time の値を使い､前回の状態を復元する
        is_panel_display: (() => {
            const settings_store = useSettingsStore();
            switch (settings_store.settings.panel_display_state) {
                case 'AlwaysDisplay':
                    return true;
                case 'AlwaysFold':
                    return false;
                case 'RestorePreviousState':
                    return settings_store.settings.showed_panel_last_time;
            }
        })(),

        // ライブ視聴: 表示されるパネルのタブ
        tv_panel_active_tab: useSettingsStore().settings.tv_panel_active_tab,

        // ビデオ視聴: 表示されるパネルのタブ
        video_panel_active_tab: useSettingsStore().settings.video_panel_active_tab,

        // パネルの Twitter タブ内で表示されるタブ
        twitter_active_tab: useSettingsStore().settings.twitter_active_tab,

        // リモコンを表示するか
        is_remocon_display: false,

        // ザッピング（「前/次のチャンネル」ボタン or 上下キーショートカット）によるチャンネル移動かどうか
        is_zapping: false,

        // プレイヤーのローディング状態
        // 既定でローディングとする
        is_loading: true,

        // プレイヤーが映像の再生をバッファリングしているか
        // 視聴開始時以外にも、ネットワークが遅くて再生が一時的に途切れたときなどで表示される
        // 既定でバッファリング中とする
        is_video_buffering: true,

        // プレイヤーの再生が停止しているか
        // 既定で再生中とする
        is_video_paused: false,

        // プレイヤーの背景を表示するか
        // 既定で表示しない
        is_background_display: false,

        // プレイヤーの背景の URL
        background_url: '',

        // キーボードショートカットの一覧のモーダルを表示するか
        shortcut_key_modal: false,

        // ライブ視聴: 現在のライブストリームのステータス
        // 既定で null (未視聴) とする
        live_stream_status: null as 'Offline' | 'Standby' | 'ONAir' | 'Idling' | 'Restart' | null,

        // ライブ視聴: ニコニコ実況への接続に失敗した際のエラーメッセージ
        // null のとき、エラーは発生していないとみなす
        live_comment_init_failed_message: null as string | null,

        // ビデオ視聴: 過去ログコメントへの取得に失敗した際のエラーメッセージ
        // null のとき、エラーは発生していないとみなす
        video_comment_init_failed_message: null as string | null,

        // Twitter パネルコンポーネントで利用する、ツイート添付候補のキャプチャのリスト
        // UI 上と KeyboardShortcutManager の両方から操作する必要があるため PlayerStore に持たせている
        twitter_captures: [] as ITweetCapture[],

        // Twitter パネルコンポーネントで利用する、ツイートに添付するキャプチャの Blob データのリスト
        // Twitter パネル本体とキャプチャタブの間で共有するため PlayerStore に持たせている
        twitter_selected_capture_blobs: [] as Blob[],

        // Twitter パネルコンポーネントで利用する、キャプチャを拡大表示するモーダルの表示状態
        // UI 上と KeyboardShortcutManager の両方から操作する必要があるため PlayerStore に持たせている
        twitter_zoom_capture_modal: false,

        // Twitter パネルコンポーネントで利用する、現在モーダルで拡大表示中のキャプチャ
        // UI 上と KeyboardShortcutManager の両方から操作する必要があるため PlayerStore に持たせている
        twitter_zoom_capture: null as ITweetCapture | null,
    }),
    actions: {

        /**
         * 視聴画面を開き、再生処理を開始する際に必ず呼び出さなければならない
         * 呼び出すと自動的に状態がリセットされ、is_watching が true になる
         */
        startWatching(): void {
            this.reset();
            this.is_watching = true;
        },

        /**
         * 視聴画面を閉じ、再生処理を終了する際に必ず呼び出さなければならない
         * 呼び出すと自動的に状態がリセットされ、is_watching が false になる
         */
        stopWatching(): void {
            this.reset();
            this.is_watching = false;
        },

        /**
         * PlayerStore の内容を初期値に戻す
         * startWatching() / stopWatching() で呼び出される
         */
        reset(): void {
            this.is_watching = false;
            this.is_player_initialized = false;
            this.recorded_program = IRecordedProgramDefault;
            this.is_virtual_keyboard_display = false;
            this.is_fullscreen = false;
            this.is_document_pip = false;
            this.is_control_display = true;
            this.is_panel_display = (() => {
                const settings_store = useSettingsStore();
                switch (settings_store.settings.panel_display_state) {
                    case 'AlwaysDisplay':
                        return true;
                    case 'AlwaysFold':
                        return false;
                    case 'RestorePreviousState':
                        return settings_store.settings.showed_panel_last_time;
                }
            })();
            this.tv_panel_active_tab = useSettingsStore().settings.tv_panel_active_tab;
            this.video_panel_active_tab = useSettingsStore().settings.video_panel_active_tab;
            this.twitter_active_tab = useSettingsStore().settings.twitter_active_tab;
            this.is_remocon_display = false;
            this.is_zapping = false;
            this.is_loading = true;
            this.is_video_buffering = true;
            this.is_video_paused = false;
            this.is_background_display = false;
            this.background_url = '';
            this.shortcut_key_modal = false;
            this.live_stream_status = null;
            this.live_comment_init_failed_message = null;
            this.twitter_captures = [];
            this.twitter_zoom_capture_modal = false;
            this.twitter_zoom_capture = null;
        }
    }
});

export default usePlayerStore;
