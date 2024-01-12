
import assert from 'assert';
import { Buffer } from 'buffer';

import * as Comlink from 'comlink';
import * as piexif from 'piexifjs';

import Utils, { dayjs } from '@/utils';


/** キャプチャに合成する際に必要なコメント情報のインターフェイス */
export interface ICaptureCommentData {
    // DOM 上のコメントのコンテナ要素の幅と高さ (px)
    container_width: number;
    container_height: number;
    // コメント全体の不透明度 (0.0 ～ 1.0)
    opacity: number;
    // コメントごとの情報
    comments: {
        // 左上からの座標 (px)
        top: number;
        left: number;
        // コメントの色
        color: string;
        // コメントのフォントサイズ (px)
        font_size: number;
        // コメントのテキスト
        text: string;
    }[];
}

/** キャプチャに書き込む EXIF メタデータのインターフェイス */
export interface ICaptureExifData {
    // キャプチャの撮影時刻 (ISO8601 フォーマット)
    captured_at: string;
    // 番組開始時刻から換算したキャプチャ位置 (秒)
    captured_playback_position: number;
    // チャンネルの network_id
    network_id: number;
    // チャンネルの service_id
    service_id: number;
    // 番組の event_id
    event_id: number;
    // 番組名
    title: string;
    // 番組概要
    description: string;
    // 番組開始時刻 (ISO8601 フォーマット)
    start_time: string;
    // 番組終了時刻 (ISO8601 フォーマット)
    end_time: string;
    // 番組長 (秒)
    duration: number;
    // 字幕のテキスト (キャプチャされた瞬間に字幕が表示されていない場合は null)
    caption_text: string | null;
    // キャプチャに字幕が合成されているかどうか
    is_caption_composited: boolean;
    // キャプチャにコメントが合成されているかどうか
    is_comment_composited: boolean;
}

export interface ICaptureCompositorOptions {
    // 字幕 Canvas 指定時のキャプチャの保存モード
    mode: 'VideoOnly' | 'CompositingCaption' | 'Both';
    // キャプチャした映像
    capture: ImageBitmap;
    // キャプチャした字幕 Canvas (null の場合は字幕を合成しない)
    caption: ImageBitmap | null;
    // キャプチャした文字スーパー Canvas (null の場合は文字スーパーを合成しない)
    superimpose: ImageBitmap | null;
    // キャプチャに合成するコメント情報 (null の場合はコメントを合成しない)
    capture_comment_data: ICaptureCommentData | null;
    // キャプチャに書き込む EXIF メタデータ
    capture_exif_data: ICaptureExifData;
}

export interface ICaptureCompositorResult {
    // 字幕を合成していないキャプチャ画像 (CompositingCaption かつ字幕がある場合は null)
    capture_normal: Blob | null;
    // 字幕を合成したキャプチャ画像 (VideoOnly と、CompositingCaption or Both だが字幕がない場合は null)
    capture_caption: Blob | null;
}

export interface ICaptureCompositor {
    composite(): Promise<ICaptureCompositorResult>;
}

export interface ICaptureCompositorConstructor {
    new (options: ICaptureCompositorOptions): ICaptureCompositor;
    loadFonts(): Promise<void>;
}


/**
 * Web Worker 上でキャプチャに字幕/文字スーパー/コメントを適宜合成し、EXIF メタデータをセットした上で Blob を返す
 * 直接は呼び出さず、CaptureCompositorProxy (Comlink) 経由で Web Worker 上で実行する
 */
class CaptureCompositor implements ICaptureCompositor {

    // フォントをロード済みかどうか
    private static is_loaded_fonts: boolean = false;

    // CaptureCompositor の合成オプション
    private readonly options: ICaptureCompositorOptions;

    /**
     * コンストラクタ
     * @param options 合成するデータと EXIF メタデータ
     */
    constructor(options: ICaptureCompositorOptions) {
        this.options = options;
    }


    /**
     * Web Worker 上に利用するフォントをロードする
     * Web Worker はメインスレッドとは別のスレッドで実行されるため、明示的に Web Worker 側でフォントをロードする必要がある
     */
    public static async loadFonts(): Promise<void> {

        // 既にロード済みの場合は何もしない
        if (this.is_loaded_fonts === true) {
            return;
        }

        // コメント描画に関しては Bold しか利用しない
        const font_faces: FontFace[] = [
            new FontFace('Open Sans', 'url(/assets/fonts/OpenSans-Bold.woff2)', {weight: 'bold'}),
            new FontFace('YakuHanJPs', 'url(/assets/fonts/YakuHanJPs-Bold.woff2)', {weight: 'bold'}),
            new FontFace('Twemoji', 'url(/assets/fonts/Twemoji.woff2)', {weight: 'bold'}),
            new FontFace('Noto Sans JP', 'url(/assets/fonts/NotoSansJP-Bold.woff2)', {weight: 'bold'}),
        ];

        // フォントを一括ロード
        // Web Worker では document.fonts ではなく self.fonts を使う必要がある (落とし穴)
        await Promise.all(font_faces.map((font_face) => font_face.load()));
        for (const font_face of font_faces) {
            self.fonts.add(font_face);
        }
        this.is_loaded_fonts = true;
    }


    /**
     * キャプチャに字幕/文字スーパー/コメントを適宜合成し、EXIF メタデータをセットした上で Blob を返す
     * @returns 字幕なしのキャプチャ画像と、字幕ありのキャプチャ画像の Blob オブジェクト (どちらかが null になる場合がある)
     */
    public async composite(): Promise<ICaptureCompositorResult> {
        console.log('[CaptureCompositor] Composite start:', this.options);
        const start_time = Utils.time();

        // 字幕ありキャプチャ画像を先に合成している理由は、this.compositeInNormalDirectMode() を実行した時点で
        // ImageBitmap が解放されてしまい、その後条件次第で実行される this.compositeInCaptionMode() でキャプチャを描画できなくなるため

        let capture_caption_promise: Promise<Blob | null> | null = null;
        let capture_normal_promise: Promise<Blob | null> | null = null;

        // 字幕ありキャプチャ画像を合成する
        // 通常は CompositingCaption と Both の場合に実行されるが、字幕が指定されていない場合は実行されない
        if (['CompositingCaption', 'Both'].includes(this.options.mode) && this.options.caption !== null) {
            capture_caption_promise = this.compositeInCaptionMode();
        }

        // 字幕なしキャプチャ画像を合成する
        // 通常は VideoOnly と Both の場合に実行されるが、CompositeCaption でも字幕が指定されていない場合は実行される
        if (['VideoOnly', 'Both'].includes(this.options.mode) || (this.options.mode === 'CompositingCaption' && this.options.caption === null)) {
            // 文字スーパーとコメントを合成する必要がない場合は、ImageBitmap のバッファを直接転写する
            if (this.options.superimpose === null && this.options.capture_comment_data === null) {
                capture_normal_promise = this.compositeInNormalDirectMode();
            } else {
                capture_normal_promise = this.compositeInNormalMode();
            }
        }

        // 並列で実行して、結果を待つ
        const [capture_caption, capture_normal] = await Promise.all([capture_caption_promise, capture_normal_promise]);
        console.log('[CaptureCompositor] Composite end:', Utils.mathFloor(Utils.time() - start_time, 3), 'sec');

        return {
            capture_normal: capture_normal,
            capture_caption: capture_caption,
        };
    }


    /**
     * 一切ほかの合成処理を行わず、キャプチャの ImageBitmap のバッファを直接 OffscreenCanvas に転写して合成する
     * 字幕なしキャプチャ画像のうち、文字スーパーやコメントを合成する必要がない場合にのみ利用する
     * このメソッドは ImageBitmap を OffscreenCanvas に移譲して解放するため、このメソッドを呼んだ後に this.options.capture を使うことはできない
     * @returns 字幕なしキャプチャ画像の Blob オブジェクト
     */
    private async compositeInNormalDirectMode(): Promise<Blob> {
        assert(this.options.superimpose === null);
        assert(this.options.capture_comment_data === null);
        const start_time = Utils.time();

        // OffscreenCanvas を生成
        const normal_direct_canvas = new OffscreenCanvas(this.options.capture.width, this.options.capture.height);

        // OffscreenCanvas のコンテキストを取得
        // bitmaprenderer を指定して、ImageBitmap からゼロコピーで描画する
        const normal_direct_canvas_context = normal_direct_canvas.getContext('bitmaprenderer', {alpha: false})!;

        // ImageBitmap を OffscreenCanvas に転送
        normal_direct_canvas_context.transferFromImageBitmap(this.options.capture);
        this.options.capture.close();  // ImageBitmap を解放
        console.log('[CaptureCompositor] Normal (Direct):', Utils.mathFloor(Utils.time() - start_time, 3), 'sec');

        // EXIF メタデータをセットした Blob を返す
        return await this.exportToBlob(normal_direct_canvas, {
            is_caption_composited: false,
            is_comment_composited: false,
        });
    }


    /**
     * 字幕なしキャプチャ画像を合成する
     * @returns 字幕なしキャプチャ画像の Blob オブジェクト
     */
    private async compositeInNormalMode(): Promise<Blob> {
        const start_time = Utils.time();

        // OffscreenCanvas を生成
        const normal_canvas = new OffscreenCanvas(this.options.capture.width, this.options.capture.height);

        // OffscreenCanvas のコンテキストを取得
        // オプションはいずれもパフォーマンス向上のために指定している
        const normal_canvas_context = normal_canvas.getContext('2d', {
            alpha: false,
            desynchronized: true,
            willReadFrequently: false,
        })!;

        // OffscreenCanvas にキャプチャした映像を描画
        normal_canvas_context.drawImage(this.options.capture, 0, 0, normal_canvas.width, normal_canvas.height);

        // 文字スーパーが指定されている場合、OffscreenCanvas にキャプチャした文字スーパーを重ねて描画
        if (this.options.superimpose !== null) {
            normal_canvas_context.drawImage(this.options.superimpose, 0, 0, normal_canvas.width, normal_canvas.height);
        }

        // コメントが指定されている場合、OffscreenCanvas にキャプチャしたコメントを重ねて描画
        if (this.options.capture_comment_data !== null) {
            this.compositeComments(normal_canvas, normal_canvas_context);
        }
        console.log('[CaptureCompositor] Normal:', Utils.mathFloor(Utils.time() - start_time, 3), 'sec');

        // EXIF メタデータをセットした Blob を返す
        return await this.exportToBlob(normal_canvas, {
            is_caption_composited: false,
            is_comment_composited: this.options.capture_comment_data !== null ? true : false,
        });
    }


    /**
     * 字幕ありキャプチャ画像を合成する
     * @returns 字幕ありキャプチャ画像の Blob オブジェクト
     */
    private async compositeInCaptionMode(): Promise<Blob> {
        assert(this.options.caption !== null);
        const start_time = Utils.time();

        // OffscreenCanvas を生成
        const caption_canvas = new OffscreenCanvas(this.options.capture.width, this.options.capture.height);

        // OffscreenCanvas のコンテキストを取得
        // オプションはいずれもパフォーマンス向上のために指定している
        const caption_canvas_context = caption_canvas.getContext('2d', {
            alpha: false,
            desynchronized: true,
            willReadFrequently: false,
        })!;

        // OffscreenCanvas にキャプチャした映像を描画
        caption_canvas_context.drawImage(this.options.capture, 0, 0, caption_canvas.width, caption_canvas.height);

        // 文字スーパーが指定されている場合、OffscreenCanvas にキャプチャした文字スーパーを重ねて描画
        if (this.options.superimpose !== null) {
            caption_canvas_context.drawImage(this.options.superimpose, 0, 0, caption_canvas.width, caption_canvas.height);
        }

        // OffscreenCanvas にキャプチャした字幕を重ねて描画
        caption_canvas_context.drawImage(this.options.caption, 0, 0, caption_canvas.width, caption_canvas.height);

        // コメントが指定されている場合、OffscreenCanvas にキャプチャしたコメントを重ねて描画
        if (this.options.capture_comment_data !== null) {
            this.compositeComments(caption_canvas, caption_canvas_context);
        }
        console.log('[CaptureCompositor] With Caption:', Utils.mathFloor(Utils.time() - start_time, 3), 'sec');

        // EXIF メタデータをセットした Blob を返す
        return await this.exportToBlob(caption_canvas, {
            is_caption_composited: true,
            is_comment_composited: this.options.capture_comment_data !== null ? true : false,
        });
    }


    /**
     * 指定された OffscreenCanvas にコメントを合成する
     * @param canvas コメントを合成する OffscreenCanvas
     * @param context コメントを合成する OffscreenCanvas のコンテキスト
     */
    private compositeComments(canvas: OffscreenCanvas, context: OffscreenCanvasRenderingContext2D): void {
        assert(this.options.capture_comment_data !== null);

        // コメントを描画する一時的な OffscreenCanvas を生成
        // この OffscreenCanvas のサイズは指定された OffscreenCanvas と同じにする
        const comment_canvas = new OffscreenCanvas(canvas.width, canvas.height);

        // OffscreenCanvas のコンテキストを取得
        // オプションはいずれもパフォーマンス向上のために指定している
        const comment_canvas_context = comment_canvas.getContext('2d', {
            alpha: true,  // 透明度を保持する
            desynchronized: true,
            willReadFrequently: false,
        })!;

        // コメントのコンテナ要素の幅と OffscreenCanvas の幅を比較して、どれだけ拡大/縮小して描画するかを計算
        // この値を使って、コメントの座標やフォントサイズを拡大/縮小する
        // コメントのコンテナ要素の高さは可変なので、幅のみを使う
        const magnification_ratio = canvas.width / this.options.capture_comment_data.container_width;

        // 事前に描画する文字のベースラインを top に設定
        // デフォルトのベースラインでは Y 座標が上にずれてしまうため
        comment_canvas_context.textBaseline = 'top';

        // 指定された座標に、指定されたフォントサイズでコメントを描画
        for (const comment of this.options.capture_comment_data.comments) {
            comment_canvas_context.fillStyle = comment.color;
            // UI 側と同じフォント指定なので、明示的にロードせずとも OffscreenCanvas に描画できる状態にあるはず
            comment_canvas_context.font = `bold ${comment.font_size * magnification_ratio}px 'Open Sans', 'YakuHanJPs', 'Twemoji', 'Hiragino Sans', 'Noto Sans JP', sans-serif`;
            // UI 側と同じテキストシャドウを付ける
            comment_canvas_context.shadowOffsetX = 1.2 * magnification_ratio;
            comment_canvas_context.shadowOffsetY = 1.2 * magnification_ratio;
            comment_canvas_context.shadowBlur = 4 * magnification_ratio;
            comment_canvas_context.shadowColor = 'rgba(0, 0, 0, 0.9)';
            comment_canvas_context.fillText(comment.text, comment.left * magnification_ratio, comment.top * magnification_ratio);
        }

        // コメントを描画する OffscreenCanvas を、指定された OffscreenCanvas に合成
        // 合成と同時にコメントレイヤーのサイズを指定された OffscreenCanvas に合わせる (通常はコメントレイヤーの方が小さいので拡大される)
        // 合成する際の透明度は指定された値を使う
        context.globalAlpha = this.options.capture_comment_data.opacity;
        context.drawImage(comment_canvas, 0, 0, canvas.width, canvas.height);
    }


    /**
     * キャプチャ画像に番組情報と撮影時刻、字幕やコメントが合成されているかどうかのメタデータ (EXIF) をセットする
     * @param blob キャプチャ画像の Blob オブジェクト
     * @param options 字幕やコメントが合成されているかどうかのメタデータ (EXIF に書き込まれる)
     * @returns EXIF が追加されたキャプチャ画像の Blob オブジェクト
     */
    private async setEXIFDataToCapture(blob: Blob, options: {
        is_caption_composited: boolean;
        is_comment_composited: boolean;
    }): Promise<Blob> {

        // EXIF 本体にセットする撮影時刻
        // すべてコロンで区切るのがポイント
        const datetime = dayjs(this.options.capture_exif_data.captured_at).format('YYYY:MM:DD HH:mm:ss');

        // EXIF の XPComment 領域に保存するメタデータ
        // is_caption_composited と is_comment_composited の値を既存の capture_exif_data に反映する
        const capture_exif_data: ICaptureExifData = {
            ...this.options.capture_exif_data,
            is_caption_composited: options.is_caption_composited,
            is_comment_composited: options.is_comment_composited,
        };

        // 保存する EXIF メタデータを構築
        // ref: 「カメラアプリで体感するWeb App」4.2
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
                [piexif.TagValues.ImageIFD.XPComment]: [...Buffer.from(JSON.stringify(capture_exif_data), 'ucs2')],
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
        // 戻り値は EXIF が追加された画像のバイナリ文字列 (なぜ未だにバイナリ文字列で実装されてるのか信じられん…)
        const blob_string_with_exif = piexif.insert(exif_string, blob_string);

        // 画像のバイナリ文字列を ArrayBuffer に変換
        // ref: 「カメラアプリで体感するWeb App」4.2
        const buffer = new Uint8Array(blob_string_with_exif.length);
        for (let index = 0; index < buffer.length; index++) {
            buffer[index] = blob_string_with_exif.charCodeAt(index) & 0xff;
        }

        // 新しい Blob を返す
        return new Blob([buffer], {type: blob.type});
    }


    /**
     * OffscreenCanvas を EXIF メタデータをセットした Blob にエクスポートする
     * @param canvas エクスポートする OffscreenCanvas
     * @param options 字幕やコメントが合成されているかどうかのメタデータ (EXIF に書き込まれる)
     * @returns 変換された Blob
     */
    private async exportToBlob(canvas: OffscreenCanvas, options: {
        is_caption_composited: boolean;
        is_comment_composited: boolean;
    }): Promise<Blob> {

        // OffscreenCanvas を Blob に変換
        // JPEG 画像の品質は 99% にした方が若干 Blob 変換までの速度が速い (？)
        const start_time = Utils.time();
        const blob = await canvas.convertToBlob({type: 'image/jpeg', quality: 0.99});

        // Blob に EXIF メタデータをセットして返す
        const blob_with_exif = await this.setEXIFDataToCapture(blob, options);
        console.log('[CaptureCompositor] Export to Blob:', Utils.mathFloor(Utils.time() - start_time, 3), 'sec');

        return blob_with_exif;
    }
}

// Comlink にクラスをエクスポート
Comlink.expose(CaptureCompositor);
