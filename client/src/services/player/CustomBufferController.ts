
import Hls, { BufferController, FragmentTracker } from 'hls.js';


/**
 * hls.js のバッファコントローラーを拡張し、サーバーサイドイベントと連携してバッファ範囲を管理するクラス
 * 大元の hls.js の実装がほとんど private なのでやむを得ず @ts-ignore を多用している
 * biim の pseudo.html の実装を KonomiTV 向けに移植したもの
 * ref: https://github.com/tsukumijima/biim/blob/main/pseudo.html
 */
// @ts-ignore
class CustomBufferController extends BufferController {

    // バッファフラッシュ時のイベントハンドラー（独自）
    private onCustomBufferFlushingHandler: () => void;

    // バッファフラッシュを抑制するフラグ
    private dontFlush: boolean = false;

    // SSE の EventSource インスタンス
    private sse: EventSource | null = null;

    // サーバーからのバッファ範囲情報
    private serverBufferingRange: { begin: number, end: number } | null = null;


    constructor(hls: Hls, fragmentTracker: FragmentTracker) {
        super(hls, fragmentTracker);
        this.onCustomBufferFlushingHandler = this.onCustomBufferFlushing.bind(this);
        this.dontFlush = false;

        // 副音声プレイリストの初回読み込みでは、hls.js が音声の取得開始位置を映像の再生開始時点へ戻す
        // プレイリストの解析後、セグメント取得が始まる前に現在位置へ合わせ、保持中の TS から副音声を取得する
        hls.on(Hls.Events.AUDIO_TRACK_UPDATED, () => {
            const media = hls.media;
            // 再生開始前は設定済みの startPosition を使い、再生中の切り替えでは現在位置を使う
            if (media !== null && media.readyState > 0) {
                hls.startLoad(media.currentTime);
            }
        });
    }

    /**
     * バッファリセット時のイベントハンドラー（上書き）
     */
    protected onBufferReset(): void {
        if (this.dontFlush) {
            this.dontFlush = false;
            return;
        }
        // 親クラスの onBufferReset を呼び出す
        // @ts-ignore
        super.onBufferReset();
    }


    /**
     * メディアアタッチ時のイベントハンドラー（上書き）
     */
    protected onMediaAttaching(event: any, data: any): void {
        // 親クラスの onMediaAttaching を呼び出す
        // @ts-ignore
        super.onMediaAttaching(event, data);
        // HLS インスタンスと HTMLMediaElement を取得
        // @ts-ignore
        const hls: Hls = this.hls;
        // @ts-ignore
        const media: HTMLMediaElement = this.media;
        // seeking イベントのリスナーを登録
        media.addEventListener('seeking', this.onCustomBufferFlushingHandler);
        // SSE の接続を開始
        const bufferURL = new URL(hls.url!);
        bufferURL.pathname = bufferURL.pathname.replace(/\/playlist$/, '/buffer');
        // Buffer API にはセッション ID だけを渡す
        bufferURL.searchParams.delete('type');
        this.sse = new EventSource(bufferURL);
        this.sse.addEventListener('buffer_range_update', (event) => {
            this.serverBufferingRange = JSON.parse(event.data);
            console.log('[CustomBufferController] Updated Server Buffering Range:', this.serverBufferingRange);
        });
    }


    /**
     * メディアデタッチ時のイベントハンドラー（上書き）
     */
    protected onMediaDetaching(): void {
        // HTMLMediaElement を取得
        // @ts-ignore
        const media: HTMLMediaElement = this.media;
        // seeking イベントのリスナーを削除
        media.removeEventListener('seeking', this.onCustomBufferFlushingHandler);
        // SSE の接続を終了
        if (this.sse) {
            this.sse.close();
            this.sse = null;
        }
        // 親クラスの onMediaDetaching を呼び出す
        // @ts-ignore
        super.onMediaDetaching();
    }


    /**
     * バッファフラッシュ時のイベントハンドラー（独自）
     */
    private onCustomBufferFlushing(): void {
        // HLS インスタンスと HTMLMediaElement を取得
        // @ts-ignore
        const hls: Hls = this.hls;
        // @ts-ignore
        const media: HTMLMediaElement = this.media;
        if (!media) return;

        // シーク位置がバッファの範囲内かチェック
        let isInBufferedRange = false;
        let isAtEnd = false;
        const duration = media.duration;

        // クライアント側のバッファ範囲をチェック
        for (let i = 0; i < media.buffered.length; i++) {
            if (media.currentTime >= media.buffered.start(i) &&
                media.currentTime <= media.buffered.end(i)) {
                isInBufferedRange = true;
                break;
            }
        }
        // サーバー側のバッファ範囲をチェック
        if (this.serverBufferingRange &&
            media.currentTime >= this.serverBufferingRange.begin &&
            media.currentTime <= this.serverBufferingRange.end) {
            isInBufferedRange = true;
        }
        // 再生が終了しているかチェック
        if (media.currentTime >= duration - 0.5) {  // 0.5秒の余裕を持たせる
            isAtEnd = true;
        }

        // バッファ範囲外かつ再生終了でない場合のみフラッシュとマニフェストの再読み込みを実行
        console.log('[CustomBufferController] Server Buffering Range:', this.serverBufferingRange, 'Current Time:', media.currentTime);
        if (!isInBufferedRange && !isAtEnd) {
            console.log('[CustomBufferController] Flushing Buffer...');
            hls.trigger(Hls.Events.BUFFER_FLUSHING, {
                startOffset: 0,
                endOffset: Number.POSITIVE_INFINITY,
                type: null,
            });
            this.dontFlush = true;
            // マニフェストの再読み込み
            // URL のクエリパラメータを解析し、cache_key を更新または追加
            // セッション ID を生成 (セッション ID は UUID の - で区切って一番左側のみを使う)
            const url = new URL(hls.url!);
            url.searchParams.set('cache_key', crypto.randomUUID().split('-')[0]);

            // Master Playlist の再読み込みでは hls.js が既定の音声トラックへ戻るため、現在の選択をトラック更新後に復元する
            const selectedAudioTrack = hls.audioTrack;
            hls.once(Hls.Events.AUDIO_TRACKS_UPDATED, () => {
                if (selectedAudioTrack >= 0 && selectedAudioTrack < hls.audioTracks.length) {
                    hls.audioTrack = selectedAudioTrack;
                }
            });
            hls.trigger(Hls.Events.MANIFEST_LOADING, {
                url: url.toString()
            });
        }
    }
}

export default CustomBufferController;
