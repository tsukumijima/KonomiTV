
import mitt from 'mitt';
import { defineStore } from 'pinia';

import { ICommentData } from '@/services/player/managers/LiveCommentManager2';
import { IRecordedProgram, IRecordedProgramDefault } from '@/services/Videos';


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
    // PlayerManager からプレイヤーロジックの再起動が必要になったことを通知する
    PlayerRestartRequired: {
        message: string;  // プレイヤーに通知するメッセージ
    };
    // CaptureManager からキャプチャの撮影が完了したことを通知する
    CaptureCompleted: {
        capture: Blob;  // キャプチャの Blob
        filename: string;  // キャプチャのファイル名 (UI からの手動ダウンロード時に使う)
    };
    // ライブ視聴: LiveCommentManager からコメントを受信したことを通知する
    LiveCommentReceived: {
        is_initial_comments: boolean;  // 初期コメントかどうか
        comments: ICommentData[];  // コメントデータのリスト
    }
    // ライブ視聴: LiveCommentManager からコメントを送信したことを通知する
    LiveCommentSendCompleted: {
        comment: ICommentData;  // 送信したコメントデータ (を整形したもの)
    }
};


/**
 * プレイヤー側の再生ロジックと UI 表示側で共有される状態を管理するストア
 * 主に PlayerWrapper や PlayerManager から状態変化に合わせて変更された値を UI に反映するためのもの
 */
const usePlayerStore = defineStore('player', {
    state: () => ({

        // プレイヤーに関連するイベントを発行する EventEmitter
        event_emitter: mitt<PlayerEvents>(),

        // 現在視聴中の録画番組の情報
        // 視聴中の録画番組がない場合は IRecordedProgramDefault を設定すべき (初期値も IRecordedProgramDefault にしている)
        recorded_program: IRecordedProgramDefault as IRecordedProgram,

        // コントロールを表示するか (既定で表示する)
        is_control_display: true,

        // フルスクリーン状態かどうか
        is_fullscreen: false,

        // 仮想キーボードが表示されているか
        // 既定で表示されていない想定
        is_virtual_keyboard_display: false,

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

        // ライブ視聴: ニコニコ実況への接続に失敗した際のエラーメッセージ
        // null のとき、エラーは発生していないとみなす
        live_comment_init_failed_message: null as string | null,
    }),
});

export default usePlayerStore;
