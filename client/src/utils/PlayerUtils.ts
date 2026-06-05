
import DPlayer from 'dplayer';


/**
 * ライブ/録画番組ストリーミング API でベース画質として設定できる動画の画質
 */
type APIBaseVideoQuality = (
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
 * ライブストリーミング API で設定できる動画の画質
 */
type LiveAPIVideoQuality = (
    APIBaseVideoQuality |
    `${APIBaseVideoQuality}-10bit` |
    `${APIBaseVideoQuality}-24fps` |
    `${APIBaseVideoQuality}-10bit-24fps`
);

/**
 * 録画番組ストリーミング API で設定できる動画の画質
 */
type VideoAPIVideoQuality = (
    APIBaseVideoQuality |
    `${APIBaseVideoQuality}-10bit` |
    `${APIBaseVideoQuality}-24fps` |
    `${APIBaseVideoQuality}-10bit-24fps`
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
     * DPlayer のインスタンスから URL クエリパラメーターにある session_id を取得する
     * @param player DPlayer のインスタンス
     * @returns URL クエリパラメーターにある session_id (取得できなかった場合は null)
     */
    static extractSessionIdFromDPlayer(player: DPlayer): string | null {
        if (player.quality === null) {
            return null;
        }
        const url = new URL(player.quality.url);
        return url.searchParams.get('session_id');
    }


    /**
     * プレイヤーの背景写真をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景写真の URL
     */
    static generatePlayerBackgroundURL(): string {
        const background_count = 90;  // 90種類から選択
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
                // 複数の Android 端末での検証の結果、モバイル回線 (4G/5G) に接続されているにも関わらず "unknown" が返されることがある
                // 一方 Wi-Fi 接続時は確実に "wi-fi" が返されるため、"unknown" の場合は "Cellular" として扱う
                case 'unknown':
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


    /**
     * 現在のブラウザで H.265 / HEVC Main10 映像がスムーズに再生できるかどうかを取得する
     * @returns スムーズに再生できるなら true、できないなら false
     */
    static async isHEVC10bitVideoSupported(): Promise<boolean> {
        const video_content_type = 'video/mp4; codecs="hvc1.2.1.L123.B0"';
        const audio_content_type = 'audio/mp4; codecs="mp4a.40.2"';

        // HEVC 10bit は透過的に有効化するため、MediaCapabilities で滑らかに再生できると判断できる環境だけを対象にする
        // ここで対象外になっても通常の HEVC 8bit で再生できるため、互換性を優先する
        if (navigator.mediaCapabilities === undefined) {
            return false;
        }

        // mpegts.js は映像と音声の SourceBuffer を別々に作る
        // 合成した MIME 文字列では実際に再生できる環境まで弾くことがあるため、実際の投入単位で確認する
        if (typeof MediaSource === 'undefined' ||
            MediaSource.isTypeSupported(video_content_type) === false ||
            MediaSource.isTypeSupported(audio_content_type) === false) {
            return false;
        }

        try {
            const decoding_info = await navigator.mediaCapabilities.decodingInfo({
                type: 'media-source',
                audio: {
                    contentType: audio_content_type,
                    channels: '2',
                    bitrate: 192000,
                    samplerate: 48000,
                },
                video: {
                    contentType: video_content_type,
                    width: 1920,
                    height: 1080,
                    bitrate: 5200000,
                    framerate: 60,
                },
            });
            return decoding_info.supported === true && decoding_info.smooth === true;
        } catch (error) {
            // MediaCapabilities API の実装差で例外が出ても、通常の HEVC 8bit 再生へ戻せば視聴は継続できる
            console.warn('[PlayerUtils] Failed to check HEVC 10bit playback support.', error);
            return false;
        }
    }
}
