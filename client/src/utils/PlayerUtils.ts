
import DPlayer from 'dplayer';


/**
 * ライブストリーミング API で設定できる動画の画質
 */
type LiveAPIVideoQuality = (
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
 * 録画番組ストリーミング API で設定できる動画の画質
 */
type VideoAPIVideoQuality = (
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
     * DPlayer のインスタンスからライブストリーミング API で設定できる画質を取得する
     * @param player DPlayer のインスタンス
     * @returns API で設定できる画質 (取得できなかった場合は基本復旧不能だが、一応 "1080p" を返す)
     */
    static extractLiveAPIQualityFromDPlayer(player: DPlayer): LiveAPIVideoQuality {
        if (player.quality === null) {
            return '1080p';
        }
        const regex = /streams\/live\/[a-z0-9-]*\/(.*)\/mpegts/;
        const match = player.quality.url.match(regex);
        return match ? (match[1] as LiveAPIVideoQuality) : '1080p';
    }


    /**
     * DPlayer のインスタンスから録画番組ストリーミング API で設定できる画質を取得する
     * @param player DPlayer のインスタンス
     * @returns API で設定できる画質 (取得できなかった場合は基本復旧不能だが、一応 "1080p" を返す)
     */
    static extractVideoAPIQualityFromDPlayer(player: DPlayer): VideoAPIVideoQuality {
        if (player.quality === null) {
            return '1080p';
        }
        const regex = /streams\/video\/[0-9]*\/(.*)\/playlist/;
        const match = player.quality.url.match(regex);
        return match ? (match[1] as VideoAPIVideoQuality) : '1080p';
    }


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
     * Network Information API から現在接続されているネットワーク回線の種類を取得する
     * navigator.connection.type が利用できない場合は null を返す
     * "Wi-Fi" には Cellular 以外のすべてのネットワークが含まれる
     * @returns ネットワークの種類 (Wi-Fi / Cellular)、取得できなかった場合は null
     */
    static getNetworkCircuitType(): 'Wi-Fi' | 'Cellular' | null {
        if (navigator.connection && navigator.connection.type) {
            switch (navigator.connection.type) {
                case 'cellular':
                    return 'Cellular';
                default:
                    return 'Wi-Fi';
            }
        } else {
            console.warn('[PlayerUtils] navigator.connection.type is not available.');
            return null;
        }
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
