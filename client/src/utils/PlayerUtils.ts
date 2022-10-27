
import { Buffer } from 'buffer';
import dayjs from 'dayjs';
import 'dayjs/locale/ja';
import * as piexif from 'piexifjs';

import { ICaptureExifData, IProgram } from '@/interface';
import Utils from './Utils';

/**
 * プレイヤー周りのユーティリティ
 */
export class PlayerUtils {

    /**
     * プレイヤーの背景画像をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景画像の URL
     */
    static generatePlayerBackgroundURL(): string {
        const background_count = 12;  // 12種類から選択
        const random = (Math.floor(Math.random() * background_count) + 1);
        return `/assets/images/player-backgrounds/${random.toString().padStart(2, '0')}.jpg`;
    }


    /**
     * 現在のブラウザで H.265 / HEVC 映像が再生できるかどうかを取得する
     * @returns 再生できるなら true、できないなら false
     */
     static isHEVCVideoSupported(): boolean {
        // hvc1.1.1.L123.B0 の部分は呪文 (HEVC であることと、そのプロファイルを示す値らしい)
        return document.createElement('video').canPlayType('video/mp4;codecs=hvc1.1.1.L123.B0') === 'probably';
    }


    /**
     * キャプチャ画像に番組情報と撮影時刻、字幕やコメントが合成されているかどうかのメタデータ (EXIF) をセットする
     * @param blob キャプチャ画像の Blob オブジェクト
     * @param program EXIF にセットする番組情報オブジェクト
     * @param caption_text 字幕のテキスト (キャプチャしたときに字幕が表示されていなければ null)
     * @param is_caption_composited 字幕が合成されているか
     * @param is_comment_composited コメントが合成されているか
     * @returns EXIF が追加されたキャプチャ画像の Blob オブジェクト
     */
    static async setEXIFDataToCapture(
        blob: Blob,
        program: IProgram,
        caption_text: string | null,
        is_caption_composited: boolean,
        is_comment_composited: boolean,
    ): Promise<Blob> {

        // 番組開始時刻換算のキャプチャ時刻 (秒)
        const captured_playback_position = dayjs().diff(dayjs(program.start_time), 'second', true);

        // EXIF の XPComment 領域に入れるメタデータの JSON オブジェクト
        // 撮影時刻とチャンネル・番組を一意に特定できる情報を入れる
        const json: ICaptureExifData = {
            captured_at: dayjs().format('YYYY-MM-DDTHH:mm:ss+09:00'),  // ISO8601 フォーマットのキャプチャ時刻
            captured_playback_position: captured_playback_position,  // 番組開始時刻換算のキャプチャ時刻 (秒)
            network_id: program.network_id,    // 番組が放送されたチャンネルのネットワーク ID
            service_id: program.service_id,    // 番組が放送されたチャンネルのサービス ID
            event_id: program.event_id,        // 番組のイベント ID
            title: program.title,              // 番組タイトル
            description: program.description,  // 番組概要
            start_time: program.start_time,    // 番組開始時刻 (ISO8601 フォーマット)
            end_time: program.end_time,        // 番組終了時刻 (ISO8601 フォーマット)
            duration: program.duration,        // 番組長 (秒)
            caption_text: caption_text,        // 字幕のテキスト (キャプチャした瞬間に字幕が表示されていなかったときは null)
            is_caption_composited: is_caption_composited,  // 字幕が合成されているか
            is_comment_composited: is_comment_composited,  // コメントが合成されているか
        }

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
