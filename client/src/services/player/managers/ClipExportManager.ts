
import DPlayer from 'dplayer';

import PlayerManager from '@/services/player/PlayerManager';
import usePlayerStore from '@/stores/PlayerStore';


/**
 * クリップ書き出しマネージャー
 * ビデオ視聴時の録画番組クリップ書き出しボタンの制御を行う
 */
class ClipExportManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
    public readonly restart_required_when_quality_switched = false;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // クリップ書き出しボタンの要素
    private clip_export_button?: HTMLElement;

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     * @param playback_mode 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
     */
    constructor(player: DPlayer, playback_mode: 'Live' | 'Video') {
        this.player = player;
        this.playback_mode = playback_mode;
    }


    /**
     * クリップ書き出しボタンとクリックイベントのセットアップを行う
     * ビデオ視聴時のみ有効
     */
    public async init(): Promise<void> {

        // ライブ視聴時は何もしない
        if (this.playback_mode === 'Live') {
            return;
        }

        // 万が一すでにクリップ書き出しボタンが存在していた場合は削除する
        const current_clip_export_button = this.player.container.querySelector('.dplayer-clip-export-icon');
        if (current_clip_export_button !== null) {
            current_clip_export_button.remove();
        }

        // コメント付きキャプチャボタンが追加されるまで待機 (最大3秒)
        // CaptureManager と並行初期化されるため、少し待つ必要がある
        let comment_capture_button: Element | null = null;
        for (let i = 0; i < 30; i++) {
            comment_capture_button = this.player.container.querySelector('.dplayer-comment-capture-icon');
            if (comment_capture_button) {
                break;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        // クリップ書き出しボタンの HTML を追加
        // コメント付きキャプチャボタンの後ろに配置
        if (comment_capture_button) {
            comment_capture_button.insertAdjacentHTML('afterend', `
                <div class="dplayer-icon dplayer-clip-export-icon" aria-label="クリップ書き出し"
                    data-balloon-nofocus="" data-balloon-pos="up">
                    <span class="dplayer-icon-content">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19,3L13,9L15,11L22,4V3M12,12.5A0.5,0.5 0 0,1 11.5,12A0.5,0.5 0 0,1 12,11.5A0.5,0.5 0 0,1 12.5,12A0.5,0.5 0 0,1 12,12.5M6,20A2,2 0 0,1 4,18C4,16.89 4.9,16 6,16A2,2 0 0,1 8,18C8,19.11 7.1,20 6,20M6,8A2,2 0 0,1 4,6C4,4.89 4.9,4 6,4A2,2 0 0,1 8,6C8,7.11 7.1,8 6,8M9.64,7.64C9.87,7.14 10,6.59 10,6A4,4 0 0,0 6,2A4,4 0 0,0 2,6A4,4 0 0,0 6,10C6.59,10 7.14,9.87 7.64,9.64L10,12L7.64,14.36C7.14,14.13 6.59,14 6,14A4,4 0 0,0 2,18A4,4 0 0,0 6,22A4,4 0 0,0 10,18C10,17.41 9.87,16.86 9.64,16.36L12,14L19,21H22V20L9.64,7.64Z"/></svg>
                    </span>
                </div>
            `);
            this.clip_export_button = this.player.container.querySelector('.dplayer-clip-export-icon')!;

            // クリップ書き出しボタンがクリックされたときのイベントを登録
            this.clip_export_button.addEventListener('click', () => this.openClipExportPanel());
        } else {
            console.warn('[ClipExportManager] Comment capture button not found. Clip export button will not be added.');
        }
    }


    /**
     * クリップ書き出しパネルを開く
     */
    private openClipExportPanel(): void {
        // PlayerStore 経由でパネルを開く
        const playerStore = usePlayerStore();
        
        // パネルを開く
        playerStore.is_panel_display = true;
        playerStore.video_panel_active_tab = 'ClipExport';
        
        // DPlayer インスタンスをパネルに渡す
        playerStore.event_emitter.emit('ClipExportPanelOpened', { player: this.player });
    }


    /**
     * クリップ書き出しボタンを破棄する
     */
    public async destroy(): Promise<void> {
        if (this.clip_export_button) {
            this.clip_export_button.remove();
        }
    }
}

export default ClipExportManager;
