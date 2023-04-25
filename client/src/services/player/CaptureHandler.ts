
import { Buffer } from 'buffer';

import { convertBlobToPng, copyBlobToClipboard } from 'copy-image-clipboard';
import dayjs from 'dayjs';
import DPlayer from 'dplayer';
import 'dayjs/locale/ja';
import * as piexif from 'piexifjs';

import Captures from '@/services/Captures';
import useChannelsStore from '@/store/ChannelsStore';
import useSettingsStore from '@/store/SettingsStore';
import Utils from '@/utils';


// キャプチャに書き込む EXIF メタデータのインターフェイス
interface ICaptureExifData {
    captured_at: string;
    captured_playback_position: number;
    network_id: number;
    service_id: number;
    event_id: number;
    title: string;
    description: string;
    start_time: string;
    end_time: string;
    duration: number;
    caption_text: string | null;
    is_caption_composited: boolean;
    is_comment_composited: boolean;
}

// CaptureHandler.setEXIFDataToCapture() のオプションのインターフェイス
interface ISetEXIFDataToCaptureOptions {
    network_id: number;
    service_id: number;
    event_id: number;
    title: string;
    description: string;
    start_time: string;
    end_time: string;
    duration: number;
    caption_text: string | null;
    is_caption_composited: boolean;
    is_comment_composited: boolean;
}


class CaptureHandler {

    private player: DPlayer;
    private player_container: HTMLElement;
    private captured_callback: (blob: Blob, filename: string) => void;
    private capture_button: HTMLDivElement;
    private comment_capture_button: HTMLDivElement;
    private canvas: OffscreenCanvas | HTMLCanvasElement;
    private canvas_context: OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
    private settings_store = useSettingsStore();

    constructor(player: DPlayer, captured_callback: (blob: Blob, filename: string) => void) {

        this.player = player;
        this.player_container = this.player.container;
        this.captured_callback = captured_callback;

        // コメント付きキャプチャボタンの HTML を追加
        // insertAdjacentHTML で .dplayer-icons-right の一番左側に配置する
        // この後に通常のキャプチャボタンが insert されるので、実際は左から2番目
        // TODO: ボタンのデザインをコメント付きだと分かるようなものに変更する
        this.player_container.querySelector('.dplayer-icons.dplayer-icons-right').insertAdjacentHTML('afterbegin', `
            <div class="dplayer-icon dplayer-comment-capture-icon" aria-label="コメントを付けてキャプチャ"
                data-balloon-nofocus="" data-balloon-pos="up">
                <span class="dplayer-icon-content">
                    <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32"><path d="M16 23c-3.309 0-6-2.691-6-6s2.691-6 6-6 6 2.691 6 6-2.691 6-6 6zM16 13c-2.206 0-4 1.794-4 4s1.794 4 4 4c2.206 0 4-1.794 4-4s-1.794-4-4-4zM27 28h-22c-1.654 0-3-1.346-3-3v-16c0-1.654 1.346-3 3-3h3c0.552 0 1 0.448 1 1s-0.448 1-1 1h-3c-0.551 0-1 0.449-1 1v16c0 0.552 0.449 1 1 1h22c0.552 0 1-0.448 1-1v-16c0-0.551-0.448-1-1-1h-11c-0.552 0-1-0.448-1-1s0.448-1 1-1h11c1.654 0 3 1.346 3 3v16c0 1.654-1.346 3-3 3zM24 10.5c0 0.828 0.672 1.5 1.5 1.5s1.5-0.672 1.5-1.5c0-0.828-0.672-1.5-1.5-1.5s-1.5 0.672-1.5 1.5zM15 4c0 0.552-0.448 1-1 1h-4c-0.552 0-1-0.448-1-1v0c0-0.552 0.448-1 1-1h4c0.552 0 1 0.448 1 1v0z"></path></svg>
                </span>
            </div>
        `);

        // キャプチャボタンの HTML を追加
        // 標準のスクリーンショット機能は貧弱なので、あえて独自に実装している（そのほうが自由度も高くてやりやすい）
        // insertAdjacentHTML で .dplayer-icons-right の一番左側に配置する
        this.player_container.querySelector('.dplayer-icons.dplayer-icons-right').insertAdjacentHTML('afterbegin', `
            <div class="dplayer-icon dplayer-capture-icon" aria-label="キャプチャ"
                data-balloon-nofocus="" data-balloon-pos="up">
                <span class="dplayer-icon-content">
                    <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32"><path d="M16 23c-3.309 0-6-2.691-6-6s2.691-6 6-6 6 2.691 6 6-2.691 6-6 6zM16 13c-2.206 0-4 1.794-4 4s1.794 4 4 4c2.206 0 4-1.794 4-4s-1.794-4-4-4zM27 28h-22c-1.654 0-3-1.346-3-3v-16c0-1.654 1.346-3 3-3h3c0.552 0 1 0.448 1 1s-0.448 1-1 1h-3c-0.551 0-1 0.449-1 1v16c0 0.552 0.449 1 1 1h22c0.552 0 1-0.448 1-1v-16c0-0.551-0.448-1-1-1h-11c-0.552 0-1-0.448-1-1s0.448-1 1-1h11c1.654 0 3 1.346 3 3v16c0 1.654-1.346 3-3 3zM24 10.5c0 0.828 0.672 1.5 1.5 1.5s1.5-0.672 1.5-1.5c0-0.828-0.672-1.5-1.5-1.5s-1.5 0.672-1.5 1.5zM15 4c0 0.552-0.448 1-1 1h-4c-0.552 0-1-0.448-1-1v0c0-0.552 0.448-1 1-1h4c0.552 0 1 0.448 1 1v0z"></path></svg>
                </span>
            </div>
        `);

        this.comment_capture_button = this.player_container.querySelector('.dplayer-comment-capture-icon');
        this.capture_button = this.player_container.querySelector('.dplayer-capture-icon');

        // キャプチャ用の Canvas を初期化
        // パフォーマンス向上のため、一度作成した Canvas は使い回す
        // OffscreenCanvas が使えるなら使う (OffscreenCanvas の方がパフォーマンスが良い)
        this.canvas = ('OffscreenCanvas' in window) ? new OffscreenCanvas(0, 0) : document.createElement('canvas');
        this.canvas_context = this.canvas.getContext('2d', {
            alpha: false,
            desynchronized: true,
            willReadFrequently: false,
        }) as OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;

        // 映像の解像度を Canvas サイズとして設定
        // 映像が読み込まれた / 画質が変わった際に Canvas のサイズを映像のサイズに合わせる
        this.canvas.width = 0;
        this.canvas.height = 0;
        player.on('loadedmetadata', async () => {
            this.canvas.width = player.video.videoWidth;
            this.canvas.height = player.video.videoHeight;
            // 映像サイズがちゃんと設定されるまで繰り返す (Safari 対策)
            while (this.canvas.width === 0 && this.canvas.height === 0) {
                await Utils.sleep(0.1);
                this.canvas.width = player.video.videoWidth;
                this.canvas.height = player.video.videoHeight;
            }
        });
    }


    /**
     * 映像をキャプチャして保存する
     * 映像のみと字幕付き (字幕表示時のみ) の両方のキャプチャを生成できる
     * @param with_comments キャプチャにコメントを合成するかどうか
     */
    public async captureAndSave(with_comments: boolean): Promise<void> {

        const total_time = Utils.time();

        // チャンネル情報を取得 (ライブ視聴画面のみ、ビデオ視聴画面では null になる)
        const channels_store = useChannelsStore();
        const channel = channels_store.is_showing_live ? channels_store.channel.current : null;

        // ***** バリデーション *****

        // ラジオチャンネルを視聴している場合 (当然映像がないのでキャプチャできない)
        if (channel !== null && channel.is_radiochannel === true) {
            this.player.notice('ラジオチャンネルはキャプチャできません。');
            return;
        }

        // まだ映像の表示準備が終わっていない (Canvas の幅/高さが 0 のまま)
        if (this.canvas.width === 0 && this.canvas.height === 0) {
            this.player.notice('読み込み中はキャプチャできません。');
            return;
        }

        // コメントが表示されていないのにコメント付きキャプチャしようとした
        if (with_comments === true && this.player.danmaku.showing === false) {
            this.player.notice('コメントを付けてキャプチャするには、コメント表示をオンにしてください。');
            return;
        }

        // ***** キャプチャの下準備 *****

        // キャプチャ中はキャプチャボタンをハイライトする
        this.addHighlight(with_comments);

        // ファイル名（拡張子なし）
        // TODO: ファイル名パターンを変更できるようにする
        const filename_base = `Capture_${dayjs().format('YYYYMMDD-HHmmss')}`;
        const filename = `${filename_base}.jpg`;  // 字幕なしキャプチャ
        const filename_caption = `${filename_base}_caption.jpg`;  // 字幕ありキャプチャ

        // 字幕・文字スーパーの Canvas を取得
        // getRawCanvas() で映像と同じ解像度の Canvas が取得できる
        const caption_canvas: HTMLCanvasElement = this.player.plugins.aribb24Caption.getRawCanvas();
        const superimpose_canvas: HTMLCanvasElement = this.player.plugins.aribb24Superimpose.getRawCanvas();

        // 字幕が表示されているか
        // @ts-ignore
        const is_caption_showing = (this.player.plugins.aribb24Caption.isShowing === true &&
                                    this.player.plugins.aribb24Caption.isPresent());

        // 文字スーパーが表示されているか
        // @ts-ignore
        const is_superimpose_showing = (this.player.plugins.aribb24Superimpose.isShowing === true &&
                                        this.player.plugins.aribb24Superimpose.isPresent());

        // 字幕が表示されている場合、表示中の字幕のテキストを取得
        // 取得した字幕のテキストは、キャプチャに字幕が合成されているかに関わらず、常に EXIF メタデータに書き込まれる
        // 字幕が表示されていない場合は null を入れ、キャプチャしたシーンで字幕が表示されていなかったことを明示する
        const caption_text = is_caption_showing ? this.player.plugins.aribb24Caption.getTextContent() : null;

        // EXIF に書き込むメタデータを取得する
        // ライブ視聴画面では、番組情報から EXIF に書き込むメタデータを取得する
        let exif_options: ISetEXIFDataToCaptureOptions;
        if (channel !== null) {
            exif_options = {
                network_id: channel.program_present.network_id,
                service_id: channel.program_present.service_id,
                event_id: channel.program_present.event_id,
                title: channel.program_present.title,
                description: channel.program_present.description,
                start_time: channel.program_present.start_time,
                end_time: channel.program_present.end_time,
                duration: channel.program_present.duration,
                caption_text: caption_text,
                is_caption_composited: false,  // 後で上書きされる
                is_comment_composited: false,  // 後で上書きされる
            };
        // ビデオ視聴画面では、録画番組情報から EXIF に書き込むメタデータを取得する
        } else {
            // TODO
        }

        // エクスポートして保存する共通処理
        const export_and_save = async (
            canvas: OffscreenCanvas | HTMLCanvasElement,
            filename: string,
            exif_options: ISetEXIFDataToCaptureOptions,
        ): Promise<Blob | false> => {

            // Canvas を Blob にエクスポート
            const time = Utils.time();
            let blob: Blob;
            try {
                blob = await this.exportToBlob(canvas);
            } catch (error) {
                console.log(error);
                this.player.notice('キャプチャの保存に失敗しました…');
                return false;
            }
            console.log('[CaptureHandler] Export to Blob:', Utils.mathFloor(Utils.time() - time, 3), 'sec');

            // キャプチャに番組情報などのメタデータ (EXIF) をセット
            blob = await this.setEXIFDataToCapture(blob, exif_options);

            // キャプチャの保存先: ブラウザでダウンロード or 両方
            if (['Browser', 'Both'].includes(this.settings_store.settings.capture_save_mode)) {
                Utils.downloadBlobData(blob, filename);
            }

            // キャプチャの保存先: KonomiTV サーバーにアップロード or 両方
            // 時間がかかるし完了を待つ必要がないので非同期
            if (['UploadServer', 'Both'].includes(this.settings_store.settings.capture_save_mode)) {
                Captures.uploadCapture(blob, filename);
            }

            return blob;
        };

        // ***** 映像のキャプチャ *****

        // null はまだキャプチャしていないことを、false はキャプチャに失敗したことを表す
        let capture_normal: {blob: Blob, filename: string} | null | false = null;
        let capture_caption: {blob: Blob, filename: string} | null | false = null;

        // 映像の ImageBitmap を取得
        const image_bitmap = await createImageBitmap(this.player.video);

        // もし映像以外に追加で合成するものがないなら、処理の高速化のために ImageBitmap をそのまま Canvas に転送して Blob 化する
        // コメントキャプチャではない & 文字スーパーが表示されていない (=合成処理を行う必要がない) &
        // (字幕が表示されていない or 字幕が表示されているが合成しないように設定されている) 場合
        // コメント付きキャプチャではなく、かつ字幕のない番組では大半がここの処理を通ることになる
        if (with_comments === false && is_superimpose_showing === false &&
            (is_caption_showing === false || this.settings_store.settings.capture_caption_mode === 'VideoOnly')) {

            // OffscreenCanvas が使えるなら使う (OffscreenCanvas の方がパフォーマンスが良い)
            const bitmap_canvas = ('OffscreenCanvas' in window) ?
                new OffscreenCanvas(image_bitmap.width, image_bitmap.height) : document.createElement('canvas');
            bitmap_canvas.width = image_bitmap.width;
            bitmap_canvas.height = image_bitmap.height;
            const canvas_context = bitmap_canvas.getContext('bitmaprenderer', {alpha: false}) as ImageBitmapRenderingContext;

            // Canvas に映像がキャプチャされた ImageBitmap を転送
            // 描画ではなくゼロコピーで転送しているらしい…？
            canvas_context.transferFromImageBitmap(image_bitmap);
            image_bitmap.close();  // 今後使うことはないので明示的に閉じる

            // ファイル名
            // 保存モードが「字幕キャプチャのみ」のとき (=字幕キャプチャのみをキャプチャする設定にしていたが、字幕がそもそもないとき) は、
            // 便宜上字幕ありキャプチャと同じファイル名で保存する
            const filename_real =
                (this.settings_store.settings.capture_caption_mode === 'CompositingCaption') ? filename_caption : filename;

            // Blob にエクスポートして保存
            // false が返ってきた場合は失敗を意味する
            const blob = await export_and_save(bitmap_canvas, filename_real, {
                ...exif_options,
                is_caption_composited: false,
                is_comment_composited: false,
            });
            if (blob !== false) {
                capture_normal = {blob: blob, filename: filename_real};
            } else {
                capture_normal = false;  // キャプチャのエクスポートに失敗
            }

            // キャプチャの Blob をコールバック関数に渡す
            // ここでコールバック関数に渡した Blob が Twitter タブのキャプチャリストに送られる
            if (capture_normal !== false) {
                this.captured_callback(capture_normal.blob, capture_normal.filename);
            }

        // ***** 通常実行 (Canvas にキャプチャ以外のデータを重ねて描画する必要があるケース) *****
        } else {

            const promises: Promise<void>[] = [];

            // Canvas に映像がキャプチャされた ImageBitmap を描画
            this.canvas_context.drawImage(image_bitmap, 0, 0, this.canvas.width, this.canvas.height);

            // 文字スーパーを描画 (表示されている場合)
            // 文字スーパー自体が稀だし、文字スーパーなしでキャプチャ撮りたいユースケースはない…はず
            if (is_superimpose_showing === true) {
                this.canvas_context.drawImage(superimpose_canvas, 0, 0, this.canvas.width, this.canvas.height);
            }

            // コメント付きキャプチャ: 追加でニコニコ実況のコメントを描画
            let comments_image: HTMLImageElement | null = null;
            if (with_comments === true) {
                comments_image = await this.createCommentsImage();
                await this.drawComments(comments_image);
            }

            // ***** 映像のみのキャプチャを保存 *****

            // 字幕表示時のキャプチャの保存モード: 映像のみ or 両方
            // 保存モードが「字幕キャプチャのみ」になっているが字幕が表示されていない場合も実行する
            if (['VideoOnly', 'Both'].includes(this.settings_store.settings.capture_caption_mode) || is_caption_showing === false) {

                promises.push((async () => {

                    // ファイル名
                    // 保存モードが「字幕キャプチャのみ」のとき (=字幕キャプチャのみをキャプチャする設定にしていたが、字幕がそもそもないとき) は、
                    // 便宜上字幕ありキャプチャと同じファイル名で保存する
                    const filename_real =
                        (this.settings_store.settings.capture_caption_mode === 'CompositingCaption') ? filename_caption : filename;

                    // Blob にエクスポートして保存
                    const blob = await export_and_save(this.canvas, filename_real, {
                        ...exif_options,
                        is_caption_composited: false,
                        is_comment_composited: with_comments,
                    });
                    if (blob !== false) {
                        capture_normal = {blob: blob, filename: filename_real};
                    } else {
                        capture_normal = false;  // キャプチャのエクスポートに失敗
                    }

                    // キャプチャの Blob をコールバック関数に渡す
                    // ここでコールバック関数に渡した Blob が Twitter タブのキャプチャリストに送られる
                    if (capture_normal !== false) {
                        this.captured_callback(capture_normal.blob, capture_normal.filename);
                    }

                })());
            }

            // ***** 字幕付きのキャプチャを保存 *****

            // 字幕表示時のキャプチャの保存モード: 字幕キャプチャのみ or 両方
            // 字幕が表示されているときのみ実行（字幕が表示されていないのにやっても意味がない）
            if (['CompositingCaption', 'Both'].includes(this.settings_store.settings.capture_caption_mode) && is_caption_showing === true) {

                promises.push((async () => {

                    // コメント付きキャプチャ: 映像と文字スーパーの描画をやり直す
                    // すでに字幕なしキャプチャを生成する過程でコメントを描画してしまっているため、映像描画からやり直す必要がある
                    if (with_comments === true) {
                        this.canvas_context.drawImage(image_bitmap, 0, 0, this.canvas.width, this.canvas.height);
                        if (is_superimpose_showing === true) {
                            this.canvas_context.drawImage(superimpose_canvas, 0, 0, this.canvas.width, this.canvas.height);
                        }
                    }
                    image_bitmap.close();  // 今後使うことはないので明示的に閉じる

                    // 字幕を重ねて描画
                    this.canvas_context.drawImage(caption_canvas, 0, 0, this.canvas.width, this.canvas.height);

                    // コメント付きキャプチャ: 追加でニコニコ実況のコメントを描画
                    if (with_comments === true) {
                        await this.drawComments(comments_image);
                    }

                    // Blob にエクスポートして保存
                    const blob = await export_and_save(this.canvas, filename_caption, {
                        ...exif_options,
                        is_caption_composited: true,
                        is_comment_composited: with_comments,
                    });
                    if (blob !== false) {
                        capture_caption = {blob: blob, filename: filename_caption};
                    } else {
                        capture_caption = false;  // キャプチャのエクスポートに失敗
                    }

                    // キャプチャの Blob をコールバック関数に渡す
                    // ここでコールバック関数に渡した Blob が Twitter タブのキャプチャリストに送られる
                    if (capture_caption !== false) {
                        // 字幕表示時のキャプチャの保存モードが「両方 (Both)」のときのみ、映像のみのキャプチャの生成が終わるまで待ってから実行
                        // 必ずキャプチャリストへの追加が [映像のみ] → [字幕付き] の順序で行われるようにする
                        if (this.settings_store.settings.capture_caption_mode === 'Both') {
                            while (capture_normal === null) {
                                // Blob (成功) か false (失敗) が capture_normal に入るまでループ
                                await Utils.sleep(0.01);
                            }
                        }
                        this.captured_callback(capture_caption.blob, capture_caption.filename);
                    }

                })());
            }

            // すべてのキャプチャ処理が終わるまで待つ
            await Promise.all(promises);
        }

        console.log('[CaptureHandler] Total:', Utils.mathFloor(Utils.time() - total_time, 3), 'sec');

        // キャプチャボタンのハイライトを削除する
        this.removeHighlight(with_comments);

        // Twitter タブのキャプチャリストに送る処理が最優先なので、コールバックを実行しきった後に時間のかかるクリップボードへのコピーを行う
        for (const capture of [capture_normal, capture_caption]) {

            // クリップボードへのコピーが有効なら、キャプチャの Blob をクリップボードにコピー
            // PNG 以外は受け付けないそうなので、JPEG を PNG に変換してからコピーしている
            if (this.settings_store.settings.capture_copy_to_clipboard && capture !== null && capture !== false) {
                try {
                    await copyBlobToClipboard(await convertBlobToPng(capture.blob));
                } catch (error) {
                    this.player.notice('クリップボードへのキャプチャのコピーに失敗しました…');
                    console.error(error);
                }
            }
        }
    }


    /**
     * キャプチャボタンをハイライトする
     * @param with_comments コメント付きキャプチャボタンをハイライトするか
     */
    private addHighlight(with_comments: boolean = false): void {
        if (with_comments) {
            this.comment_capture_button.classList.add('dplayer-capturing');
        } else {
            this.capture_button.classList.add('dplayer-capturing');
        }
    }


    /**
     * キャプチャボタンのハイライトを外す
     * @param with_comments コメント付きキャプチャボタンのハイライトを外すか
     */
    private removeHighlight(with_comments: boolean = false): void {
        if (with_comments) {
            this.comment_capture_button.classList.remove('dplayer-capturing');
        } else {
            this.capture_button.classList.remove('dplayer-capturing');
        }
    }


    /**
     * DPlayer から取得したコメント HTML を SVG 画像の HTMLImageElement に変換する
     * ZenzaWatch のコードを参考にしている
     * ref: https://github.com/segabito/ZenzaWatch/blob/master/packages/lib/src/dom/VideoCaptureUtil.js
     * ref: https://web.archive.org/web/2/https://developer.mozilla.org/ja/docs/Web/HTML/Canvas/Drawing_DOM_objects_into_a_canvas
     * @param html DPlayer から取得したコメント HTML
     * @param width SVG 画像の幅
     * @param height SVG 画像の高さ
     * @returns SVG 画像の HTMLImageElement
     */
    private async commentsHTMLtoSVGImage(html: string, width: number, height: number): Promise<HTMLImageElement> {

        // SVG の foreignObject を使い、HTML をそのまま SVG に埋め込む
        // SVG なので、CSS はインラインでないと適用されない…
        // DPlayer の danmaku.scss の内容のうち、描画に必要なプロパティのみを列挙 (追加変更したものもある)
        // ref: https://github.com/tsukumijima/DPlayer/blob/master/src/css/danmaku.scss
        const svg = (`
            <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
                <foreignObject width="100%" height="100%">
                    <div xmlns="http://www.w3.org/1999/xhtml">
                        <style>
                        .dplayer-danmaku {
                            position: absolute;
                            top: 0;
                            left: 0;
                            right: 0;
                            bottom: 0;
                            color: #fff;
                            font-size: 29px;
                            font-family: 'YakuHanJPs', 'Open Sans', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
                        }
                        .dplayer-danmaku .dplayer-danmaku-item {
                            display: inline-block;
                            line-height: 1;
                            font-weight: bold;
                            font-size: var(--dplayer-danmaku-font-size);
                            opacity: var(--dplayer-danmaku-opacity);
                            text-shadow: 1.2px 1.2px 4px rgba(0, 0, 0, 0.9);
                            white-space: nowrap;
                        }
                        .dplayer-danmaku .dplayer-danmaku-item--demo {
                            position: absolute;
                            visibility: hidden;
                        }
                        .dplayer-danmaku .dplayer-danmaku-item span {
                            box-decoration-break: clone;
                            -webkit-box-decoration-break: clone;
                        }
                        .dplayer-danmaku .dplayer-danmaku-item.dplayer-danmaku-size-big {
                            font-size: calc(var(--dplayer-danmaku-font-size) * 1.25);
                        }
                        .dplayer-danmaku .dplayer-danmaku-item.dplayer-danmaku-size-small {
                            font-size: calc(var(--dplayer-danmaku-font-size) * 0.8);
                        }
                        .dplayer-danmaku .dplayer-danmaku-right {
                            position: absolute;
                            right: 0;
                        }
                        .dplayer-danmaku .dplayer-danmaku-top, .dplayer-danmaku .dplayer-danmaku-bottom {
                            position: absolute;
                            left: 50%;
                            transform: translateX(-50%);
                        }
                        </style>
                        ${html}
                    </div>
                </foreignObject>
            </svg>
        `).trim();

        // Data URL 化して Image オブジェクトにする
        // わざわざ Blob にするよりこっちのほうが楽
        const image = new Image();
        image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

        // Image は onload を使わなくても await Image.decode() でロードできる
        await image.decode();
        return image;
    }


    /**
     * DPlayer から表示中のコメントを取得し、SVG 画像の HTMLImageElement を作成する
     * @returns 表示されているコメントが描画された HTMLImageElement
     */
    private async createCommentsImage(): Promise<HTMLImageElement> {

        // コメントが表示されている要素の HTML を取得する
        let comments_html = this.player.template.danmaku.outerHTML;

        // HTML を取得するだけではスクロール中コメントの表示位置が特定できないため、HTML を修正する
        for (const comment of this.player_container.querySelectorAll('.dplayer-danmaku-move')) { // コメントの数だけ置換
            // スクロール中のコメントの表示座標を計算
            const position = comment.getBoundingClientRect().left - this.player.video.getBoundingClientRect().left;
            comments_html = comments_html.replace(/transform: translateX\(.*?\);/, `left: ${position}px;`)
                .replaceAll('border: 2px solid #E64F97;', '');
        }

        // HTML を画像として取得
        // SVG のサイズはコメントが表示されている要素に合わせる (そうしないとプレイヤー側と一致しない)
        // SVG はベクター画像なので、リサイズしても画質が変わらないはず
        return await this.commentsHTMLtoSVGImage(
            comments_html,
            this.player.template.danmaku.offsetWidth,
            this.player.template.danmaku.offsetHeight,
        );
    }


    /**
     * 現在表示されているニコニコ実況のコメントを Canvas に描画する
     */
    private async drawComments(comments_image: HTMLImageElement): Promise<void> {

        // コメント描画領域がコントロールの表示によりリサイズされている (=16:9でない) 場合も考慮して、コメント要素の offsetWidth から高さを求める
        // 映像の横解像度 (ex: 1920) がコメント描画領域の幅 (ex: 1280) の何倍かの割合 (ex: 1.5 (150%))
        const draw_scale_ratio = this.canvas.width / this.player.template.danmaku.offsetWidth;

        // コメント描画領域の高さを映像の横解像度に合わせて（コメント描画領域のアスペクト比を維持したまま）拡大した値
        // 映像の縦解像度が 1080 のとき、コントロールがコメント領域と被っていない or 表示されていないなら、この値は 1080 に近くなる
        const draw_height = this.player.template.danmaku.offsetHeight * draw_scale_ratio;

        this.canvas_context.drawImage(comments_image, 0, 0, this.canvas.width, draw_height);
    }


    /**
     * Canvas もしくは OffscreenCanvas に描画されている画像を Blob に変換する
     * JPEG 画像の品質は 99% にした方が若干 Blob 変換までの速度が速い (？)
     * @param canvas Canvas もしくは OffscreenCanvas
     * @returns Blob 化した画像
     */
    private async exportToBlob(canvas: HTMLCanvasElement | OffscreenCanvas): Promise<Blob> {
        if ('OffscreenCanvas' in window && canvas instanceof OffscreenCanvas) {
            return await canvas.convertToBlob({type: 'image/jpeg', quality: 0.99});
        } else if (canvas instanceof HTMLCanvasElement) {
            return new Promise((resolve, reject) => {
                canvas.toBlob((blob) => {
                    if (blob !== null) {
                        resolve(blob);
                    } else {
                        reject(new Error('Failed to convert canvas to blob'));
                    }
                }, 'image/jpeg', 0.99);
            });
        }
    }


    /**
     * キャプチャ画像に番組情報と撮影時刻、字幕やコメントが合成されているかどうかのメタデータ (EXIF) をセットする
     * @param blob キャプチャ画像の Blob オブジェクト
     * @param options EXIF にセットする番組情報データ・字幕テキスト・字幕が合成されているかどうか・コメントが合成されているかどうか
     * @returns EXIF が追加されたキャプチャ画像の Blob オブジェクト
     */
    private async setEXIFDataToCapture(blob: Blob, options: ISetEXIFDataToCaptureOptions): Promise<Blob> {

        // 番組開始時刻換算のキャプチャ時刻 (秒)
        const captured_playback_position = dayjs().diff(dayjs(options.start_time), 'second', true);

        // EXIF の XPComment 領域に入れるメタデータの JSON オブジェクト
        // 撮影時刻とチャンネル・番組を一意に特定できる情報を入れる
        const json: ICaptureExifData = {
            captured_at: dayjs().format('YYYY-MM-DDTHH:mm:ss+09:00'),  // ISO8601 フォーマットのキャプチャ時刻
            captured_playback_position: captured_playback_position,  // 番組開始時刻換算のキャプチャ時刻 (秒)
            network_id: options.network_id,    // 番組が放送されたチャンネルのネットワーク ID
            service_id: options.service_id,    // 番組が放送されたチャンネルのサービス ID
            event_id: options.event_id,        // 番組のイベント ID
            title: options.title,              // 番組タイトル
            description: options.description,  // 番組概要
            start_time: options.start_time,    // 番組開始時刻 (ISO8601 フォーマット)
            end_time: options.end_time,        // 番組終了時刻 (ISO8601 フォーマット)
            duration: options.duration,        // 番組長 (秒)
            caption_text: options.caption_text,        // 字幕のテキスト (キャプチャした瞬間に字幕が表示されていなかったときは null)
            is_caption_composited: options.is_caption_composited,  // 字幕が合成されているか
            is_comment_composited: options.is_comment_composited,  // コメントが合成されているか
        };

        // 保存する EXIF メタデータを構築
        // ref: 「カメラアプリで体感するWeb App」4.2
        const datetime = dayjs().format('YYYY:MM:DD HH:mm:ss');  // すべてコロンで区切るのがポイント
        const exif: piexif.IExif = {
            '0th': {
                // 必須らしいプロパティ
                // とりあえずデフォルト値 (?) を設定しておく
                [piexif.TagValues.ImageIFD.XResolution]: [72, 1],
                [piexif.TagValues.ImageIFD.YResolution]: [72, 1],
                [piexif.TagValues.ImageIFD.ResolutionUnit]: 2,
                [piexif.TagValues.ImageIFD.YCbCrPositioning]: 1,
                // 撮影時刻
                [piexif.TagValues.ImageIFD.DateTime]: datetime,
                // ソフトウェア名
                [piexif.TagValues.ImageIFD.Software]: `KonomiTV version ${Utils.version}`,
                // Microsoft 拡張のコメント領域（エクスプローラーで出てくるコメント欄と同じもの）
                // ref: https://stackoverflow.com/a/66186660/17124142
                [piexif.TagValues.ImageIFD.XPComment]: [...Buffer.from(JSON.stringify(json), 'ucs2')],
            },
            'Exif': {
                // 必須らしいプロパティ
                // とりあえずデフォルト値 (?) を設定しておく
                [piexif.TagValues.ExifIFD.ExifVersion]: '0230',
                [piexif.TagValues.ExifIFD.ComponentsConfiguration]: '\x01\x02\x03\x00',
                [piexif.TagValues.ExifIFD.FlashpixVersion]: '0100',
                [piexif.TagValues.ExifIFD.ColorSpace]: 1,
                // 撮影時刻
                [piexif.TagValues.ExifIFD.DateTimeOriginal]: datetime,
                [piexif.TagValues.ExifIFD.DateTimeDigitized]: datetime,
            },
        };
        const exif_string = piexif.dump(exif);  // バイナリ文字列に変換した EXIF データ

        // piexifjs はバイナリ文字列か DataURL しか受け付けないので、Blob をバイナリ文字列に変換
        const blob_string: string = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsBinaryString(blob);  // バイナリ文字列で読み込む
        });

        // 画像に EXIF を挿入
        // 戻り値は EXIF が追加された画像のバイナリ文字列 (なぜ未だにバイナリ文字列で実装してるんだ…)
        const blob_string_new = piexif.insert(exif_string, blob_string);

        // 画像のバイナリ文字列を ArrayBuffer に変換
        // ref: 「カメラアプリで体感するWeb App」4.2
        const buffer = new Uint8Array(blob_string_new.length);
        for (let index = 0; index < buffer.length; index++) {
            buffer[index] = blob_string_new.charCodeAt(index) & 0xff;
        }

        // 新しい Blob を返す
        return new Blob([buffer], {type: blob.type});
    }
}

export default CaptureHandler;
