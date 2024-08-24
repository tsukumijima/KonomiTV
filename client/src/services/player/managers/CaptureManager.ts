
import assert from 'assert';

import * as Comlink from 'comlink';
import { convertBlobToPng, copyBlobToClipboard } from 'copy-image-clipboard';
import DPlayer from 'dplayer';

import Captures from '@/services/Captures';
import PlayerManager from '@/services/player/PlayerManager';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { dayjs } from '@/utils';
import { ICaptureCommentData, ICaptureExifData } from '@/workers/CaptureCompositor';
import CaptureCompositorProxy from '@/workers/CaptureCompositorProxy';


/**
 * キャプチャボタンとクリックイベントをセットアップし、キャプチャの合成と保存を行う PlayerManager
 */
class CaptureManager implements PlayerManager {

    // ユーザー操作により DPlayer 側で画質が切り替わった際、この PlayerManager の再起動が必要かどうかを PlayerController に示す値
    public readonly restart_required_when_quality_switched = false;

    // DPlayer のインスタンス
    // 設計上コンストラクタ以降で変更すべきでないため readonly にしている
    private readonly player: DPlayer;

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // キャプチャボタンの HTML 要素
    private capture_button: HTMLDivElement | null = null;
    private comment_capture_button: HTMLDivElement | null = null;

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
     * キャプチャボタンとクリックイベントのセットアップを行う
     */
    public async init(): Promise<void> {

        // 万が一すでにキャプチャボタンが存在していた場合は削除する
        const current_capture_button = this.player.container.querySelector('.dplayer-capture-icon');
        const current_comment_capture_button = this.player.container.querySelector('.dplayer-comment-capture-icon');
        if (current_capture_button !== null) {
            current_capture_button.remove();
        }
        if (current_comment_capture_button !== null) {
            current_comment_capture_button.remove();
        }

        // キャプチャボタンの HTML を追加
        // 標準のスクリーンショット機能は貧弱なので、あえて独自に実装している（そのほうが自由度も高くてやりやすい）
        this.player.container.querySelector('.dplayer-player-restart-icon')!.insertAdjacentHTML('afterend', `
            <div class="dplayer-icon dplayer-capture-icon" aria-label="キャプチャ"
                data-balloon-nofocus="" data-balloon-pos="up">
                <span class="dplayer-icon-content">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M16 23c-3.309 0-6-2.691-6-6s2.691-6 6-6 6 2.691 6 6-2.691 6-6 6zM16 13c-2.206 0-4 1.794-4 4s1.794 4 4 4c2.206 0 4-1.794 4-4s-1.794-4-4-4zM27 28h-22c-1.654 0-3-1.346-3-3v-16c0-1.654 1.346-3 3-3h3c0.552 0 1 0.448 1 1s-0.448 1-1 1h-3c-0.551 0-1 0.449-1 1v16c0 0.552 0.449 1 1 1h22c0.552 0 1-0.448 1-1v-16c0-0.551-0.448-1-1-1h-11c-0.552 0-1-0.448-1-1s0.448-1 1-1h11c1.654 0 3 1.346 3 3v16c0 1.654-1.346 3-3 3zM24 10.5c0 0.828 0.672 1.5 1.5 1.5s1.5-0.672 1.5-1.5c0-0.828-0.672-1.5-1.5-1.5s-1.5 0.672-1.5 1.5zM15 4c0 0.552-0.448 1-1 1h-4c-0.552 0-1-0.448-1-1v0c0-0.552 0.448-1 1-1h4c0.552 0 1 0.448 1 1v0z"></path></svg>
                </span>
            </div>
        `);
        this.capture_button = this.player.container.querySelector('.dplayer-capture-icon')!;

        // コメント付きキャプチャボタンの HTML を追加
        this.capture_button.insertAdjacentHTML('afterend', `
            <div class="dplayer-icon dplayer-comment-capture-icon" aria-label="コメントを付けてキャプチャ"
                data-balloon-nofocus="" data-balloon-pos="up">
                <span class="dplayer-icon-content">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 37 32"><path d="M34.18 18.5682H24.4869C23.4829 18.5682 22.6693 19.3525 22.6693 20.32V27.314C22.6693 28.2815 23.4829 29.0658 24.4869 29.0658H26.3045V27.9118H29.916L26.1407 31.3811L26.8138 32L30.0067 29.0658H34.18C35.1835 29.0658 35.9976 28.2815 35.9976 27.314V20.32C35.9976 19.3521 35.1835 18.5682 34.18 18.5682ZM34.786 26.7441C34.786 27.3888 34.2436 27.9118 33.5744 27.9118H29.9813L29.9487 27.8817L29.916 27.9118H25.0925C24.4233 27.9118 23.8809 27.3888 23.8809 26.7441V20.9037C23.8809 20.2585 24.4233 19.7355 25.0925 19.7355H33.574C34.2432 19.7355 34.7855 19.6749 34.7855 20.3196V26.7437L34.786 26.7441ZM26.4773 22.9422C25.9521 22.9422 25.5253 23.3337 25.5253 23.8172C25.5253 24.3007 25.9516 24.6918 26.4773 24.6918C27.0033 24.6918 27.4297 24.3003 27.4297 23.8172C27.4297 23.3341 27.0033 22.9422 26.4773 22.9422ZM32.1892 22.9422C31.6631 22.9422 31.2372 23.3337 31.2372 23.8172C31.2372 24.3007 31.6631 24.6918 32.1892 24.6918C32.7152 24.6918 33.1412 24.3003 33.1412 23.8172C33.1412 23.3341 32.7152 22.9422 32.1892 22.9422ZM29.3337 22.9422C28.8076 22.9422 28.3817 23.3337 28.3817 23.8172C28.3817 24.3007 28.8076 24.6918 29.3337 24.6918C29.8589 24.6918 30.2856 24.3003 30.2856 23.8172C30.2856 23.3341 29.8593 22.9422 29.3337 22.9422Z"/><path fill-rule="evenodd" clip-rule="evenodd" d="M16 23C12.691 23 10 20.309 10 17C10 13.691 12.691 11 16 11C19.309 11 22 13.691 22 17C22 20.309 19.309 23 16 23ZM16 13C13.794 13 12 14.794 12 17C12 19.206 13.794 21 16 21C18.206 21 20 19.206 20 17C20 14.794 18.206 13 16 13ZM30 9V16.4888H28V9C28 8.449 27.552 8 27 8H16C15.448 8 15 7.552 15 7C15 6.448 15.448 6 16 6H27C28.654 6 30 7.346 30 9ZM20.5905 28V26H5C4.449 26 4 25.552 4 25V9C4 8.449 4.449 8 5 8H8C8.552 8 9 7.552 9 7C9 6.448 8.552 6 8 6H5C3.346 6 2 7.346 2 9V25C2 26.654 3.346 28 5 28H20.5905ZM24 10.5C24 11.328 24.672 12 25.5 12C26.328 12 27 11.328 27 10.5C27 9.672 26.328 9 25.5 9C24.672 9 24 9.672 24 10.5ZM15 4C15 4.552 14.552 5 14 5H10C9.448 5 9 4.552 9 4C9 3.448 9.448 3 10 3H14C14.552 3 15 3.448 15 4Z"/></svg>
                </span>
            </div>
        `);
        this.comment_capture_button = this.player.container.querySelector('.dplayer-comment-capture-icon')!;

        // キャプチャボタンがクリックされたときのイベントを登録
        // キャプチャボタンがクリックされたら、非同期でキャプチャと保存を行う
        this.capture_button.addEventListener('click', () => this.captureAndSave(false));
        this.comment_capture_button.addEventListener('click', () => this.captureAndSave(true));

        // 事前に CaptureCompositor 側でフォントをロードしておく
        await CaptureCompositorProxy.loadFonts();

        console.log('[CaptureManager] Initialized.');
    }


    /**
     * キャプチャボタンのハイライト (ボタンの周囲が赤くなる) を追加する
     * @param comment_capture_button_instead 代わりにコメント付きキャプチャボタンの方をハイライトするか
     */
    private addHighlight(comment_capture_button_instead: boolean = false): void {
        assert(this.capture_button !== null && this.comment_capture_button !== null);
        if (comment_capture_button_instead) {
            this.comment_capture_button.classList.add('dplayer-capturing');
        } else {
            this.capture_button.classList.add('dplayer-capturing');
        }
    }


    /**
     * キャプチャボタンのハイライト (ボタンの周囲が赤くなる) を外す
     * @param comment_capture_button_instead 代わりにコメント付きキャプチャボタンの方のハイライトを外すか
     */
    private removeHighlight(comment_capture_button_instead: boolean = false): void {
        assert(this.capture_button !== null && this.comment_capture_button !== null);
        if (comment_capture_button_instead) {
            this.comment_capture_button.classList.remove('dplayer-capturing');
        } else {
            this.capture_button.classList.remove('dplayer-capturing');
        }
    }


    /**
     * キャプチャに合成する際に必要なコメント情報を生成する
     * @returns キャプチャに合成する際に必要なコメント情報
     */
    private createCaptureCommentData(): ICaptureCommentData | null {

        const capture_comment_data: ICaptureCommentData = {
            // DOM 上のコメントのコンテナ要素の幅と高さ (px)
            container_width: this.player.danmaku!.container.offsetWidth,
            container_height: this.player.danmaku!.container.offsetHeight,
            // コメント全体の不透明度 (0.0 ～ 1.0)
            opacity: this.player.danmaku!._opacity,
            // コメントごとの情報
            comments: [],
        };

        // 各コメントの DOM 要素を取得
        const selector = '.dplayer-danmaku-item:not(.dplayer-danmaku-item--demo)';
        for (const comment_element of this.player.danmaku!.container.querySelectorAll<HTMLDivElement>(selector)) {

            // コメントのテキストが null の場合はスキップ (基本ないはず)
            if (comment_element.textContent === null) {
                continue;
            }

            // 取得したスタイル情報を基に、描画する上で必要となるコメント情報を構築
            const computed_style = window.getComputedStyle(comment_element);
            capture_comment_data.comments.push({
                // スクロール中・固定表示中のコメントの表示座標を計算
                top: comment_element.getBoundingClientRect().top - this.player.danmaku!.container.getBoundingClientRect().top,
                left: comment_element.getBoundingClientRect().left - this.player.danmaku!.container.getBoundingClientRect().left,
                // コメントの色
                color: computed_style.color,
                // コメントのフォントサイズ (px)
                font_size: parseFloat(computed_style.fontSize.replaceAll('px', '')),
                // コメントのテキスト
                text: comment_element.textContent.trim(),  // 念のため前後の空白を削除
            });
        }

        // もしコメントが一つもなかった場合は null を返す
        if (capture_comment_data.comments.length === 0) {
            return null;
        }

        return capture_comment_data;
    }


    /**
     * キャプチャした画像の EXIF に書き込むメタデータ情報を生成する
     * ライブ視聴時とビデオ視聴時で設定するメタデータが異なる
     * 現在時刻をキャプチャの撮影時刻として EXIF メタデータに設定するので、このメソッドはキャプチャを撮影する直前にのみ呼び出すこと
     * is_caption_composited / is_comment_composited のみ、実際の状態に合わせて CaptureCompositor 側で上書きされる
     * @returns キャプチャした画像の EXIF に書き込むメタデータ情報
     */
    private createCaptureExifData(): ICaptureExifData {
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();

        // 現在の時刻 (ISO8601 フォーマット)
        // 現在時刻をキャプチャの撮影時刻として EXIF に書き込む
        const captured_at = dayjs().format();

        // 字幕がプレイヤー上で表示されているかどうか
        // 字幕自体は存在するが表示されていない場合は false になる
        const aribb24_caption = this.player.plugins.aribb24Caption!;
        const is_caption_showing = ((aribb24_caption as any).isShowing === true && aribb24_caption.isPresent());

        // 字幕がプレイヤー上で表示されている場合、表示中の字幕のテキストを取得
        // 取得した字幕のテキストは、キャプチャに字幕が合成されているかに関わらず、常に EXIF メタデータに書き込まれる
        // 字幕が表示されていない場合は null を入れ、キャプチャしたシーンで字幕が表示されていなかったことを明示する
        const caption_text = is_caption_showing ? aribb24_caption.getTextContent() : null;

        // ライブ視聴: 現在視聴中のチャンネル情報・番組情報を EXIF メタデータに設定
        let capture_exif_data: ICaptureExifData;
        if (this.playback_mode === 'Live') {
            capture_exif_data = {
                captured_at: captured_at,
                captured_playback_position: -1,  // 後の処理で設定するが、ここでは実装上の都合で -1 を入れておく
                network_id: channels_store.channel.current.network_id,
                service_id: channels_store.channel.current.service_id,
                event_id: channels_store.channel.current.program_present?.event_id ?? -1,
                title: channels_store.channel.current.program_present?.title ?? '放送休止',
                description: channels_store.channel.current.program_present?.description ?? '',
                start_time: channels_store.channel.current.program_present?.start_time ?? '2000-01-01T00:00:00+09:00',
                end_time: channels_store.channel.current.program_present?.end_time ?? '2000-01-01T00:00:00+09:00',
                duration: channels_store.channel.current.program_present?.duration ?? 0,
                caption_text: caption_text,
                is_caption_composited: false,  // 字幕が合成されているか (実際の状態に合わせて CaptureCompositor 側で上書きされる)
                is_comment_composited: false,  // コメントが合成されているか (実際の状態に合わせて CaptureCompositor 側で上書きされる)
            };
        // ビデオ視聴: 現在視聴中の録画番組情報を EXIF メタデータに設定
        } else {
            capture_exif_data = {
                captured_at: captured_at,
                captured_playback_position: -1,  // 後の処理で設定するが、ここでは実装上の都合で -1 を入れておく
                network_id: player_store.recorded_program.network_id ?? -1,
                service_id: player_store.recorded_program.service_id ?? -1,
                event_id: player_store.recorded_program.event_id ?? -1,
                title: player_store.recorded_program.title,
                description: player_store.recorded_program.description,
                start_time: player_store.recorded_program.start_time,
                end_time: player_store.recorded_program.end_time,
                duration: player_store.recorded_program.duration,
                caption_text: caption_text,
                is_caption_composited: false,  // 字幕が合成されているか (実際の状態に合わせて CaptureCompositor 側で上書きされる)
                is_comment_composited: false,  // コメントが合成されているか (実際の状態に合わせて CaptureCompositor 側で上書きされる)
            };
        }

        // 番組開始時刻換算のキャプチャ時刻 (秒) を設定
        // ライブ視聴: 現在進行形で放送されているので、番組開始時刻からの経過時間 (現在時刻 - 番組開始時刻) を設定する
        if (this.playback_mode === 'Live') {
            capture_exif_data.captured_playback_position = dayjs().diff(dayjs(capture_exif_data.start_time), 'second', true);
        // ビデオ視聴: 動画の現在の再生位置から、録画開始マージンを引いた値を設定する
        // これで (録画開始マージンが取得できていない場合以外は) ライブ視聴時と比較可能な値になる
        } else {
            capture_exif_data.captured_playback_position = this.player.video.currentTime - player_store.recorded_program.recording_start_margin;
        }

        return capture_exif_data;
    }


    /**
     * 映像をキャプチャし、設定で指定された方法で保存する
     * 映像のみと字幕付き (字幕表示時のみ) の両方のキャプチャを生成できる
     * @param is_comment_composite キャプチャにコメントを合成するかどうか
     */
    private async captureAndSave(is_comment_composite: boolean): Promise<void> {
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();
        const settings_store = useSettingsStore();
        const start_time = Utils.time();

        // ***** バリデーション *****

        // ラジオチャンネルを視聴している場合 (映像がないのでキャプチャできない)
        // この場合映像の幅/高さも 0 になるので、このチェックは必ず先に行う
        if (this.playback_mode === 'Live' && channels_store.channel.current.is_radiochannel === true) {
            this.player.notice('ラジオチャンネルはキャプチャできません。', undefined, undefined, '#FF6F6A');
            return;
        }

        // まだ映像の表示準備が終わっていない (映像の幅/高さが 0 のまま)
        if (this.player.video.videoWidth === 0 && this.player.video.videoHeight === 0) {
            this.player.notice('読み込み中はキャプチャできません。', undefined, undefined, '#FF6F6A');
            return;
        }

        // コメントが表示されていないのにコメント付きでキャプチャしようとした
        if (is_comment_composite === true && this.player.danmaku!.showing === false) {
            this.player.notice('コメントを付けてキャプチャするには、コメント表示をオンにしてください。', undefined, undefined, '#FF6F6A');
            return;
        }

        // ***** キャプチャの事前準備 *****

        // キャプチャ中はキャプチャボタンをハイライトする
        this.addHighlight(is_comment_composite);

        // aribb24js.CanvasID3Renderer のインスタンスを取得
        // PlayerController での実装上、aribb24.js (字幕) は必ず有効になっている
        const aribb24_caption = this.player.plugins.aribb24Caption!;
        // aribb24.js (文字スーパー) はビデオ視聴では常に無効なほか、ライブ視聴でも設定によっては無効になる
        const aribb24_superimpose = this.player.plugins.aribb24Superimpose ?? null;

        // 字幕・文字スーパーの Canvas を取得
        // getRawCanvas() で映像と同じ解像度の Canvas が取得できる
        const caption_canvas = aribb24_caption.getRawCanvas()!;
        const superimpose_canvas = aribb24_superimpose?.getRawCanvas() ?? null;

        // 字幕/文字スーパーが表示されているか
        const is_caption_showing = ((aribb24_caption as any).isShowing === true && aribb24_caption.isPresent());
        const is_superimpose_showing = (aribb24_superimpose && (aribb24_superimpose as any).isShowing === true && aribb24_superimpose.isPresent());

        // ***** キャプチャの実行・字幕/文字スーパー/コメントを合成 *****

        // 高速化のため、Promise.all() で並列に実行する
        const create_image_bitmap_results = await Promise.all([
            // 現在再生中の動画のキャプチャを ImageBitmap として取得
            createImageBitmap(this.player.video),
            // 字幕が表示されていれば、字幕の Canvas を ImageBitmap として取得
            is_caption_showing ? createImageBitmap(caption_canvas) : null,
            // 文字スーパーが表示されていれば、文字スーパーの Canvas を ImageBitmap として取得
            is_superimpose_showing ? createImageBitmap(superimpose_canvas!) : null,
        ]);
        const image_bitmaps = create_image_bitmap_results.filter((image_bitmap) => image_bitmap !== null) as ImageBitmap[];
        const capture_image_bitmap = create_image_bitmap_results[0];
        const caption_image_bitmap = create_image_bitmap_results[1];
        const superimpose_image_bitmap = create_image_bitmap_results[2];

        // キャプチャにコメントを合成する場合、コメントを取得する
        const capture_comment_data = is_comment_composite ? this.createCaptureCommentData() : null;

        // キャプチャに書き込む EXIF メタデータを取得
        // is_caption_composited / is_comment_composited のみ、実際の状態に合わせて CaptureCompositor 側で上書きされる
        const capture_exif_data = this.createCaptureExifData();

        // キャプチャの合成を実行し、字幕なしキャプチャと字幕ありキャプチャを生成する
        // Web Worker 側に ImageBitmap を移譲するため、Comlink.transfer() を使う
        // 第二引数に (第一引数内のオブジェクトに含まれる) 移譲する Transferable オブジェクトを渡す
        console.log('\u001b[36m[CaptureManager] Composite start:');
        const capture_compositor_start_time = Utils.time();
        const capture_compositor = await new CaptureCompositorProxy(Comlink.transfer({
            mode: settings_store.settings.capture_caption_mode,
            capture: capture_image_bitmap,
            caption: caption_image_bitmap,
            superimpose: superimpose_image_bitmap,
            capture_comment_data: capture_comment_data,
            capture_exif_data: capture_exif_data,
        }, image_bitmaps));
        const result = await capture_compositor.composite();
        console.log('\u001b[36m[CaptureManager] Composite end:', Utils.mathFloor(Utils.time() - capture_compositor_start_time, 3), 'sec');

        // ファイル名（拡張子なし）
        // TODO: ファイル名パターンを設定で変更できるようにする
        const filename_base = `Capture_${dayjs().format('YYYYMMDD-HHmmss')}`;
        const filename_normal = `${filename_base}.jpg`;  // 字幕なしキャプチャ
        const filename_caption = `${filename_base}_caption.jpg`;  // 字幕ありキャプチャ

        // ***** キャプチャの保存 *****

        // 字幕なしキャプチャ
        // 必ず字幕なしキャプチャから保存する
        if (result.capture_normal !== null) {

            // 生成した Blob をイベントリスナーに送信する
            player_store.event_emitter.emit('CaptureCompleted', {
                capture: result.capture_normal,
                filename: filename_normal,
            });

            // キャプチャの保存先: ブラウザでダウンロード or 両方
            if (['Browser', 'Both'].includes(settings_store.settings.capture_save_mode)) {
                Utils.downloadBlobData(result.capture_normal, filename_normal);
            }

            // キャプチャの保存先: KonomiTV サーバーにアップロード or 両方
            // 時間がかかるし完了を待つ必要がないので非同期
            if (['UploadServer', 'Both'].includes(settings_store.settings.capture_save_mode)) {
                Captures.uploadCapture(result.capture_normal, filename_normal);
            }
        }

        // 字幕ありキャプチャ
        if (result.capture_caption !== null) {

            // 生成した Blob をイベントリスナーに送信する
            player_store.event_emitter.emit('CaptureCompleted', {
                capture: result.capture_caption,
                filename: filename_normal,
            });

            // キャプチャの保存先: ブラウザでダウンロード or 両方
            if (['Browser', 'Both'].includes(settings_store.settings.capture_save_mode)) {
                Utils.downloadBlobData(result.capture_caption, filename_caption);
            }

            // キャプチャの保存先: KonomiTV サーバーにアップロード or 両方
            // アップロードに時間が掛かる上、完了を待つ必要もないので非同期
            if (['UploadServer', 'Both'].includes(settings_store.settings.capture_save_mode)) {
                Captures.uploadCapture(result.capture_caption, filename_caption);
            }
        }

        // キャプチャが終わったので、キャプチャボタンのハイライトを削除する
        // ただし、キャプチャに掛かった時間が 0.1 秒未満の場合は、0.1 秒経過後にハイライトを削除する (すぐに削除すると一瞬すぎて見えないため)
        const total_time = Utils.mathFloor(Utils.time() - start_time, 3);
        if (total_time < 0.1) {
            setTimeout(() => this.removeHighlight(is_comment_composite), 100);
        } else {
            this.removeHighlight(is_comment_composite);
        }
        console.log('\u001b[36m[CaptureManager] Total:', total_time, 'sec');

        // ***** クリップボードへのキャプチャ画像のコピー *****

        // キャプチャ画像をクリップボードにコピーする設定が有効な場合、クリップボードにコピーする
        // クリップボードへのコピーにはかなり時間がかかるので、ハイライトを削除してからバックグラウンドで実行する
        // 残念ながらクリップボード操作は Web Worker 上では行えないので、メインスレッド側で実行している
        if (settings_store.settings.capture_copy_to_clipboard === true) {
            for (const capture of [result.capture_normal, result.capture_caption]) {
                if (capture !== null) {
                    try {
                        await copyBlobToClipboard(await convertBlobToPng(capture));
                    } catch (error) {
                        this.player.notice('クリップボードへのキャプチャのコピーに失敗しました。', undefined, undefined, '#FF6F6A');
                        console.error(error);
                    }
                }
            }
        }
    }


    /**
     * 何もしない
     * 本来であれば init() で動的に追加したキャプチャボタンの HTML 要素を削除するべきだが、
     * 実装上 PlayerController の破棄が完了する前にボタンを削除してしまうと、キャプチャボタンだけ一瞬消える不恰好な状態になってしまう
     * このため、代わりに init() 側にすでにキャプチャボタンが追加済みであれば一旦削除する処理を入れている
     */
    public async destroy(): Promise<void> {

        // 何もしない
        console.log('[CaptureManager] Destroyed.');
    }
}

export default CaptureManager;
