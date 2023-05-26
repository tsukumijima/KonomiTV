
import DPlayer from 'dplayer';

/**
 * API 上設定できる動画の画質
 */
type APIVideoQuality = (
    '1080p-60fps' |
    '1080p-60fps-hevc' |
    '1080p' |
    '1080p-hevc' |
    '810p' |
    '810p-hevc' |
    '720p' |
    '720p-hevc' |
    '540p' |
    '540p-hevc' |
    '480p' |
    '480p-hevc' |
    '360p' |
    '360p-hevc' |
    '240p' |
    '240p-hevc'
);



/**
 * プレイヤー周りのユーティリティ
 */
export class PlayerUtils {

    /**
     * プレイヤーの背景画像をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景画像の URL
     */
    public static generatePlayerBackgroundURL(): string {
        const background_count = 50;  // 50種類から選択
        const random = (Math.floor(Math.random() * background_count) + 1);
        return `/assets/images/player-backgrounds/${random.toString().padStart(2, '0')}.jpg`;
    }


    /**
     * 現在のブラウザで H.265 / HEVC 映像が再生できるかどうかを取得する
     * ref: https://github.com/StaZhu/enable-chromium-hevc-hardware-decoding#mediacapabilities
     * @returns 再生できるなら true、できないなら false
     */
    public static isHEVCVideoSupported(): boolean {
        // hvc1.1.6.L123.B0 の部分は呪文 (HEVC であることと、そのプロファイルを示す値らしい)
        return document.createElement('video').canPlayType('video/mp4; codecs="hvc1.1.6.L123.B0"') === 'probably';
    }


    /**
     * DPlayer のインスタンスから API で設定できる画質を取得する
     * @param player DPlayer のインスタンス
     * @returns API で設定できる画質 (取得できなかった場合は null)
     */
    public static extractAPIQualityFromDPlayer(player: DPlayer): APIVideoQuality | null {
        if (player.quality === null) {
            return null;
        }
        const regex = /streams\/live\/[a-z0-9]*\/(.*)\/(mpegts|ll-hls)/;
        const match = player.quality.url.match(regex);
        return match ? (match[1] as APIVideoQuality) : null;
    }
}
