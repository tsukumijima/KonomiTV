
import APIClient from '@/services/APIClient';
import { IProgram, IProgramDefault } from '@/services/Programs';


/** チャンネルタイプの型 */
export type ChannelType = 'GR' | 'BS' | 'CS' | 'CATV' | 'SKY' | 'STARDIGIO';

// チャンネルタイプの型 (実際のチャンネルリストに表示される表現)
export type ChannelTypePretty = 'ピン留め' | '地デジ' | 'BS' | 'CS' | 'CATV' | 'SKY' | 'StarDigio';

/** すべてのチャンネルタイプのチャンネルの情報を表すインターフェイス */
export interface IChannelsList {
    GR: IChannel[];
    BS: IChannel[];
    CS: IChannel[];
    CATV: IChannel[];
    SKY: IChannel[];
    STARDIGIO: IChannel[];
}

/** チャンネル情報を表すインターフェイス */
export interface IChannel {
    id: string;
    network_id: number;
    service_id: number;
    transport_stream_id: number | null;
    remocon_id: number | null;
    channel_id: string;
    channel_number: string;
    channel_name: string;
    channel_type: ChannelType;
    channel_force: number | null;
    channel_comment: number | null;
    is_subchannel: boolean;
    is_radiochannel: boolean;
    is_display: boolean;
    viewers: number;
    program_present: IProgram | null;
    program_following: IProgram | null;
}

/** チャンネル情報を表すインターフェイスのデフォルト値 */
export const IChannelDefault: IChannel = {
    id: 'NID0-SID0',
    network_id: 0,
    service_id: 0,
    transport_stream_id: null,
    remocon_id: null,
    channel_id: 'gr000',
    channel_number: '---',
    channel_name: '取得中…',
    channel_type: 'GR',
    channel_force: null,
    channel_comment: null,
    is_subchannel: false,
    is_radiochannel: false,
    is_display: true,
    viewers: 0,
    program_present: IProgramDefault,
    program_following: IProgramDefault,
};

/** ニコニコ実況のセッション情報を表すインターフェイス */
export interface IJikkyoSession {
    is_success: boolean;
    audience_token: string | null;
    detail: string;
}


class Channels {

    /**
     * すべてのチャンネルの情報を取得する
     * @return すべてのチャンネルの情報
     */
    static async fetchAll(): Promise<IChannelsList | null> {

        // API リクエストを実行
        const response = await APIClient.get<IChannelsList>('/channels');

        // エラー処理
        if ('is_error' in response) {
            APIClient.showGenericError(response, 'チャンネル情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 指定したチャンネルの情報を取得する
     * 現状、処理の見直しにより使用されていない
     * @param channel_id チャンネル ID
     * @return 指定したチャンネルの情報
     */
    static async fetch(channel_id: string): Promise<IChannel | null> {

        // API リクエストを実行
        const response = await APIClient.get<IChannel>(`/channels/${channel_id}`);

        // エラー処理
        if ('is_error' in response) {
            APIClient.showGenericError(response, 'チャンネル情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 指定したチャンネルに紐づくニコニコ実況のセッション情報を取得する
     * @param channel_id チャンネル ID
     * @return 指定したチャンネルに紐づくニコニコ実況のセッション情報
     */
    static async fetchJikkyoSession(channel_id: string): Promise<IJikkyoSession | null> {

        // API リクエストを実行
        const response = await APIClient.get<IJikkyoSession>(`/channels/${channel_id}/jikkyo`);

        // エラー処理
        if ('is_error' in response) {
            APIClient.showGenericError(response, 'ニコニコ実況のセッション情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }
}

export default Channels;
