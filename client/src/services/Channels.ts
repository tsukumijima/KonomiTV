
import APIClient from '@/services/APIClient';
import { IProgram, IProgramDefault } from '@/services/Programs';


/** チャンネルタイプの型 */
export type ChannelType = 'GR' | 'BS' | 'CS' | 'CATV' | 'SKY' | 'BS4K';

// チャンネルタイプの型 (実際のチャンネルリストに表示される表現)
export type ChannelTypePretty = 'ピン留め' | '地デジ' | 'BS' | 'CS' | 'CATV' | 'SKY' | 'BS4K';

/** 地デジ放送エリアの型 (北海道は7分割、計53選択肢) */
export type TerrestrialRegion =
    | '北海道（札幌）' | '北海道（函館）' | '北海道（旭川）' | '北海道（帯広）'
    | '北海道（釧路）' | '北海道（北見）' | '北海道（室蘭）'
    | '青森県' | '岩手県' | '宮城県' | '秋田県' | '山形県' | '福島県'
    | '茨城県' | '栃木県' | '群馬県' | '埼玉県' | '千葉県' | '東京都' | '神奈川県'
    | '新潟県' | '富山県' | '石川県' | '福井県' | '山梨県' | '長野県'
    | '岐阜県' | '静岡県' | '愛知県' | '三重県'
    | '滋賀県' | '京都府' | '大阪府' | '兵庫県' | '奈良県' | '和歌山県'
    | '鳥取県' | '島根県' | '岡山県' | '広島県' | '山口県'
    | '徳島県' | '香川県' | '愛媛県' | '高知県'
    | '福岡県' | '佐賀県' | '長崎県' | '熊本県' | '大分県' | '宮崎県' | '鹿児島県' | '沖縄県';

/** チャンネル情報を表すインターフェイス */
export interface IChannel {
    id: string;
    display_channel_id: string;
    network_id: number;
    service_id: number;
    transport_stream_id: number | null;
    remocon_id: number;
    channel_number: string;
    type: ChannelType;
    name: string;
    // 地デジチャンネルの地域名のリスト (デバッグ用)
    // 広域放送局の場合は複数の地域名が含まれる
    // 地デジ以外のチャンネルまたは地域が特定できない場合は null
    terrestrial_regions: TerrestrialRegion[] | null;
    jikkyo_force: number | null;
    is_subchannel: boolean;
    is_radiochannel: boolean;
    is_watchable: boolean;
}

/** 現在放送中のチャンネル情報を表すインターフェイス */
export interface ILiveChannel extends IChannel {
    // 以下はすべて動的に生成される TV ライブストリーミング用の追加カラム
    is_display: boolean;
    viewer_count: number;
    program_present: IProgram | null;
    program_following: IProgram | null;
}

/** 現在放送中のチャンネル情報を表すインターフェイスのデフォルト値 */
export const ILiveChannelDefault: ILiveChannel = {
    id: 'NID0-SID0',
    display_channel_id: 'gr000',
    network_id: 0,
    service_id: 0,
    transport_stream_id: null,
    remocon_id: 0,
    channel_number: '---',
    type: 'GR',
    name: '取得中…',
    jikkyo_force: null,
    is_subchannel: false,
    is_radiochannel: false,
    is_watchable: true,
    terrestrial_regions: null,
    is_display: true,
    viewer_count: 0,
    program_present: IProgramDefault,
    program_following: IProgramDefault,
};

/** すべてのチャンネルタイプの現在放送中のチャンネルの情報を表すインターフェイス */
export interface ILiveChannelsList {
    GR: ILiveChannel[];
    BS: ILiveChannel[];
    CS: ILiveChannel[];
    CATV: ILiveChannel[];
    SKY: ILiveChannel[];
    BS4K: ILiveChannel[];
}

/** ニコニコ実況の WebSocket API の情報を表すインターフェイス */
export interface IJikkyoWebSocketInfo {
    watch_session_url: string | null;
    nicolive_watch_session_url: string | null;
    nicolive_watch_session_error: string | null;
    comment_session_url: string | null;
    is_nxjikkyo_exclusive: boolean;
}


class Channels {

    /**
     * すべてのチャンネルの情報を取得する
     * @return すべてのチャンネルの情報
     */
    static async fetchAllChannels(): Promise<ILiveChannelsList | null> {

        // API リクエストを実行
        const response = await APIClient.get<ILiveChannelsList>('/channels');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'チャンネル情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 指定したチャンネルの情報を取得する
     * 現状、処理の見直しにより使用されていない
     * @param channel_id チャンネル ID (id or display_channel_id)
     * @return 指定したチャンネルの情報
     */
    static async fetch(channel_id: string): Promise<ILiveChannel | null> {

        // API リクエストを実行
        const response = await APIClient.get<ILiveChannel>(`/channels/${channel_id}`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'チャンネル情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 指定されたチャンネルに対応する、ニコニコ実況・NX-Jikkyo とコメントを送受信するための WebSocket API の情報を取得する
     * @param channel_id チャンネル ID (id or display_channel_id)
     * @return ニコニコ実況・NX-Jikkyo とコメントを送受信するための WebSocket API の情報
     */
    static async fetchWebSocketInfo(channel_id: string): Promise<IJikkyoWebSocketInfo | null> {

        // API リクエストを実行
        const response = await APIClient.get<IJikkyoWebSocketInfo>(`/channels/${channel_id}/jikkyo`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'コメント送受信用 WebSocket API の情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }
}

export default Channels;
