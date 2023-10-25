

import DPlayer from 'dplayer';

import router from '@/router';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';


/**
 * MediaSession API を使いメディア通知を管理する PlayerManager
 */
class MediaSessionManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerWrapper に示す値
    public readonly restart_required_when_quality_switched = false;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // 破棄済みかどうか
    private destroyed = false;

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
     * MediaSession 情報をブラウザに登録する
     * 再生中のチャンネル情報・番組情報・録画番組情報が変更された場合は、一度破棄してから再度実行する必要がある
     */
    public async init(): Promise<void> {
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();

        // 破棄済みかどうかのフラグを下ろす
        this.destroyed = false;

        // MediaSession API を使い、メディア通知の表示をカスタマイズ
        if ('mediaSession' in navigator) {

            // ライブ視聴でアートワークとして表示するアイコン
            const live_artwork = [
                {src: '/assets/images/icons/icon-maskable-192px.png', sizes: '192x192', type: 'image/png'},
                {src: '/assets/images/icons/icon-maskable-512px.png', sizes: '512x512', type: 'image/png'},
            ];

            // ビデオ視聴でアートワークとして表示する番組サムネイル
            // TODO: ちゃんと録画番組のサムネイルを設定すべき
            const video_artwork = [
                {src: '/assets/images/icons/icon-maskable-192px.png', sizes: '192x192', type: 'image/png'},
                {src: '/assets/images/icons/icon-maskable-512px.png', sizes: '512x512', type: 'image/png'},
            ];

            // メディア通知の表示をカスタマイズ
            // ライブ視聴: 番組タイトル・チャンネル名・アイコンを表示
            if (this.playback_mode === 'Live') {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: channels_store.channel.current.program_present?.title ?? '放送休止',
                    artist: channels_store.channel.current.name,
                    artwork: live_artwork,
                });
            // ビデオ視聴: 番組タイトル・シリーズタイトル・サムネイルを表示
            // シリーズタイトルが取得できていない場合は番組タイトルが代わりに設定される
            } else {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: player_store.recorded_program.title,
                    artist: player_store.recorded_program.series_title ?? player_store.recorded_program.title,
                    artwork: video_artwork,
                });
            }

            // 再生速度や再生位置が変更された際に MediaSession の情報を更新する
            // ライブ視聴時は再生位置自体が無限なので何も起こらない
            this.player.on('ratechange', this.updateMediaSessionPositionState.bind(this));
            this.player.on('seeking', this.updateMediaSessionPositionState.bind(this));
            this.player.on('seeked', this.updateMediaSessionPositionState.bind(this));

            // メディア通知上のボタンが押されたときのイベント
            // 再生
            navigator.mediaSession.setActionHandler('play', () => this.player?.play());
            // 停止
            navigator.mediaSession.setActionHandler('pause', () => this.player?.pause());
            // 前/次の再生位置にシーク (ビデオ視聴時のみ)
            if (this.playback_mode === 'Video') {
                // 前の再生位置にシーク
                navigator.mediaSession.setActionHandler('seekbackward', (details) => {
                    const seek_offset = details.seekOffset ?? 10;  // デフォルト: 10 秒早戻し
                    this.player.seek(this.player.video.currentTime - seek_offset);
                });
                // 次の再生位置にシーク
                navigator.mediaSession.setActionHandler('seekforward', (details) => {
                    const seek_offset = details.seekOffset ?? 10;  // デフォルト: 10 秒早送り
                    this.player.seek(this.player.video.currentTime + seek_offset);
                });
                // イベントで渡された再生位置にシーク
                navigator.mediaSession.setActionHandler('seekto', (details) => {
                    this.player.seek(details.seekTime!);
                });
            }
            // 前のトラックに移動
            navigator.mediaSession.setActionHandler('previoustrack', async () => {
                // ライブ視聴: 前のチャンネルに切り替え
                if (this.playback_mode === 'Live') {
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: channels_store.channel.previous.program_present?.title ?? '放送休止',
                        artist: channels_store.channel.previous.name,
                        artwork: live_artwork,
                    });
                    // ルーティングを前のチャンネルに置き換える
                    await router.push({path: `/tv/watch2/${channels_store.channel.previous.display_channel_id}`});
                // ビデオ視聴: シリーズ番組の前の話数に切り替え
                } else {
                    // TODO: 未実装
                }
            });
            // 次のトラックに移動
            navigator.mediaSession.setActionHandler('nexttrack', async () => {  // 次のチャンネルに切り替え
                // ライブ視聴: 次のチャンネルに切り替え
                if (this.playback_mode === 'Live') {
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: channels_store.channel.next.program_present?.title ?? '放送休止',
                        artist: channels_store.channel.next.name,
                        artwork: live_artwork,
                    });
                    // ルーティングを次のチャンネルに置き換える
                    await router.push({path: `/tv/watch2/${channels_store.channel.next.display_channel_id}`});
                // ビデオ視聴: シリーズ番組の次の話数に切り替え
                } else {
                    // TODO: 未実装
                }
            });
        }
    }


    /**
     * メディア通知上の再生位置を更新する
     */
    private updateMediaSessionPositionState(): void {

        // 破棄済みなら何もしない
        // DPlayer に登録したイベントから破棄後のタイミングでこのメソッドが呼ばれる可能性がなくもないので、念のため
        if (this.destroyed === true) {
            return;
        }

        if ('setPositionState' in navigator.mediaSession) {
            // ライブ視聴
            if (this.playback_mode === 'Live') {
                navigator.mediaSession.setPositionState({
                    // 仕様上は duration に Infinity を設定すべきだが、実際には Infinity を設定すると Chrome でエラーになる…
                    // ワークアラウンドで 0 を設定しておく (今の所問題なく動作している)
                    duration: 0,
                    // ライブ視聴では常に再生速度は 1.0 になる
                    playbackRate: 1.0,
                });
            // ビデオ視聴
            } else {
                navigator.mediaSession.setPositionState({
                    // 現在の動画の長さ
                    duration: this.player.video.duration,
                    // 現在の動画の再生速度
                    playbackRate: this.player.video.playbackRate,
                    // 現在の動画の再生位置
                    position: this.player.video.currentTime,
                });
            }
        }
    }


    /**
     * MediaSession 情報をブラウザから削除する
     */
    public async destroy(): Promise<void> {

        // DPlayer からイベントを削除
        // 現状 off() がないので this.player.events.events を直接操作する
        for (const event_name of ['ratechange', 'seeking', 'seeked']) {
            for(const event of this.player.events.events[event_name]) {
                if (event === this.updateMediaSessionPositionState) {
                    this.player.events.events[event_name] = this.player.events.events[event_name].filter((e: any) => e !== event);
                }
            }
        }

        // MediaSession API を使い、メディア通知の表示をリセット
        if ('mediaSession' in navigator) {
            navigator.mediaSession.metadata = null;
            navigator.mediaSession.setActionHandler('play', null);
            navigator.mediaSession.setActionHandler('pause', null);
            navigator.mediaSession.setActionHandler('seekbackward', null);
            navigator.mediaSession.setActionHandler('seekforward', null);
            navigator.mediaSession.setActionHandler('previoustrack', null);
            navigator.mediaSession.setActionHandler('nexttrack', null);
            if ('setPositionState' in navigator.mediaSession) {
                navigator.mediaSession.setPositionState({});  // 空のオブジェクトを渡して状態をリセット
            }
        }

        // 破棄済みかどうかのフラグを立てる
        this.destroyed = true;
    }
}

export default MediaSessionManager;
