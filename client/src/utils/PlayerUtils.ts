
/**
 * プレイヤー周りのユーティリティ
 */
export class PlayerUtils {

    /**
     * プレイヤーの背景画像をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景画像の URL
     */
    static generatePlayerBackgroundURL(): string {
        const background_count = 50;  // 50種類から選択
        const random = (Math.floor(Math.random() * background_count) + 1);
        return `/assets/images/player-backgrounds/${random.toString().padStart(2, '0')}.jpg`;
    }


    /**
     * 現在のブラウザで H.265 / HEVC 映像が再生できるかどうかを取得する
     * ref: https://github.com/StaZhu/enable-chromium-hevc-hardware-decoding#mediacapabilities
     * @returns 再生できるなら true、できないなら false
     */
    static isHEVCVideoSupported(): boolean {
        // hvc1.1.6.L123.B0 の部分は呪文 (HEVC であることと、そのプロファイルを示す値らしい)
        return document.createElement('video').canPlayType('video/mp4; codecs="hvc1.1.6.L123.B0"') === 'probably';
    }
}
