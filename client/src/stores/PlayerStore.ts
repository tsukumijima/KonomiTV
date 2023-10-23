
import mitt from 'mitt';
import { defineStore } from 'pinia';

import { IRecordedProgram, IRecordedProgramDefault } from '@/services/Videos';


/** プレイヤーに関するイベントの型 */
export type PlayerEvents = {
    // PlayerManager からプレイヤーロジックの再起動が必要になったことを通知する (message: プレイヤーに通知するメッセージ)
    PlayerRestartRequired: { message: string; };
};


/**
 * プレイヤー側の再生ロジックと UI 表示側で共有される状態を管理するストア
 * 主に PlayerWrapper や PlayerManager から状態変化に合わせて変更された値を UI に反映するためのもの
 */
const usePlayerStore = defineStore('player', {
    state: () => ({

        // プレイヤーに関するイベントを発行する EventEmitter
        event_emitter: mitt<PlayerEvents>(),

        // 現在視聴中の録画番組の情報
        // 視聴中の録画番組がない場合は IRecordedProgramDefault を設定すべき (初期値も IRecordedProgramDefault にしている)
        recorded_program: IRecordedProgramDefault as IRecordedProgram,

        // コントロールを表示するか (既定で表示する)
        is_control_display: true,

        // フルスクリーン状態かどうか
        is_fullscreen: false,

        // プレイヤーのローディング状態
        // 既定でローディングとする
        is_loading: true,

        // プレイヤーが映像の再生をバッファリングしているか
        // 視聴開始時以外にも、ネットワークが遅くて再生が一時的に途切れたときなどで表示される
        // 既定でバッファリング中とする
        is_video_buffering: true,

        // プレイヤーの背景を表示するか
        // 既定で表示しない
        is_background_display: false,

        // プレイヤーの背景の URL
        background_url: '',

        // キーボードショートカットの一覧のモーダルを表示するか
        shortcut_key_modal: false,
    }),
});

export default usePlayerStore;
