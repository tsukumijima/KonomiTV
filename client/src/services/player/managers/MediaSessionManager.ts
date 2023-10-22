

import DPlayer from 'dplayer';

import router from '@/router';
import { ILiveChannel } from '@/services/Channels';
import PlayerManager from '@/services/player/PlayerManager';
import { IRecordedProgram } from '@/services/Videos';
import useChannelsStore from '@/stores/ChannelsStore';


/**
 * MediaSession API を使いメディア通知を管理する PlayerManager
 */
class MediaSessionManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerWrapper に示す値
    public readonly restart_required_when_quality_switched = false;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // ライブ視聴: 視聴対象のチャンネル情報の参照
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly channel: ILiveChannel | null = null;

    // ビデオ視聴: 視聴対象の録画番組情報の参照
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly recorded_program: IRecordedProgram | null = null;

    // 破棄済みかどうか
    private destroyed = false;

    /**
     * コンストラクタ
     * @param player DPlayer のインスタンス
     * @param channel_or_recorded_program 視聴対象のチャンネル情報または録画番組情報
     */
    constructor(player: DPlayer, channel_or_recorded_program: ILiveChannel | IRecordedProgram) {
        this.player = player;

        // 引数の型に応じて channel または recorded_program をセット
        if ('recorded_video' in channel_or_recorded_program) {
            this.recorded_program = channel_or_recorded_program;
        } else {
            this.channel = channel_or_recorded_program;
        }
    }


    /**
     * MediaSession 情報をブラウザに登録する
     * 再生中のチャンネル情報・番組情報・録画番組情報が変更された場合は、一度破棄してから再度実行する必要がある
     */
    public async init(): Promise<void> {

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
            if (this.channel !== null) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: this.channel.program_present?.title ?? '放送休止',
                    artist: this.channel.name,
                    artwork: live_artwork,
                });
            // ビデオ視聴: 番組タイトル・シリーズタイトル・サムネイルを表示
            // シリーズタイトルが取得できていない場合は番組タイトルが代わりに設定される
            } else if (this.recorded_program !== null) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: this.recorded_program.title,
                    artist: this.recorded_program.series_title ?? this.recorded_program.title,
                    artwork: video_artwork,
                });
            }

            // 再生速度や再生位置が変更された際に MediaSession の情報を更新する
            // ライブ視聴時は再生位置自体が無限なので何も起こらない
            this.player.on('ratechange', this.updateMediaSessionPositionState);
            this.player.on('seeking', this.updateMediaSessionPositionState);
            this.player.on('seeked', this.updateMediaSessionPositionState);

            // メディア通知上のボタンが押されたときのイベント
            // 再生
            navigator.mediaSession.setActionHandler('play', () => this.player?.play());
            // 停止
            navigator.mediaSession.setActionHandler('pause', () => this.player?.pause());
            // 前の再生位置にシーク
            navigator.mediaSession.setActionHandler('seekbackward', (details) => {
                // ライブ視聴: 何もしない
                // ビデオ視聴: 10 秒早戻し
                if (this.recorded_program !== null) {
                    const seek_offset = details.seekOffset ?? 10;  // デフォルト: 10 秒早戻し
                    this.player.seek(this.player.video.currentTime - seek_offset);
                }
            });
            // 次の再生位置にシーク
            navigator.mediaSession.setActionHandler('seekforward', (details) => {
                // ライブ視聴: 何もしない
                // ビデオ視聴: 10 秒早送り
                if (this.recorded_program !== null) {
                    const seek_offset = details.seekOffset ?? 10;  // デフォルト: 10 秒早送り
                    this.player.seek(this.player.video.currentTime + seek_offset);
                }
            });
            // 前のトラックに移動
            navigator.mediaSession.setActionHandler('previoustrack', async () => {
                // ライブ視聴: 前のチャンネルに切り替え
                if (this.channel !== null) {
                    const channels_store = useChannelsStore();
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: channels_store.channel.previous.program_present?.title ?? '放送休止',
                        artist: channels_store.channel.previous.name,
                        artwork: live_artwork,
                    });
                    // ルーティングを前のチャンネルに置き換える
                    await router.push({path: `/tv/watch/${channels_store.channel.previous.display_channel_id}`});
                // ビデオ視聴: シリーズ番組の前の話数に切り替え
                } else if (this.recorded_program !== null) {
                    // TODO: 未実装
                }
            });
            // 次のトラックに移動
            navigator.mediaSession.setActionHandler('nexttrack', async () => {  // 次のチャンネルに切り替え
                // ライブ視聴: 次のチャンネルに切り替え
                if (this.channel !== null) {
                    const channels_store = useChannelsStore();
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: channels_store.channel.next.program_present?.title ?? '放送休止',
                        artist: channels_store.channel.next.name,
                        artwork: live_artwork,
                    });
                    // ルーティングを次のチャンネルに置き換える
                    await router.push({path: `/tv/watch/${channels_store.channel.next.display_channel_id}`});
                // ビデオ視聴: シリーズ番組の次の話数に切り替え
                } else if (this.recorded_program !== null) {
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
        if (this.destroyed === true) return;

        if ('setPositionState' in navigator.mediaSession) {
            // ライブ視聴
            if (this.channel !== null) {
                navigator.mediaSession.setPositionState({
                    duration: Infinity,  // ライブ視聴では長さは無限大
                    playbackRate: 1.0,  // ライブ視聴では常に再生速度は 1.0 になる
                });
            // ビデオ視聴
            } else if (this.recorded_program !== null) {
                navigator.mediaSession.setPositionState({
                    duration: this.player.video.duration,  // 現在の動画の長さを設定
                    playbackRate: this.player.video.playbackRate,  // 現在の動画の再生速度を設定
                    position: this.player.video.currentTime,  // 現在の動画の再生位置を設定
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
