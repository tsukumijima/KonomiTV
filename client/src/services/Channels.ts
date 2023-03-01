
import APIClient from '@/services/APIClient';
import { IProgram } from '@/services/Programs';


// チャンネルタイプの型
export type ChannelType = 'GR' | 'BS' | 'CS' | 'CATV' | 'SKY' | 'STARDIGIO';

// すべてのチャンネルの情報を表すインターフェイス
export interface IChannels {
    GR: IChannel[];
    BS: IChannel[];
    CS: IChannel[];
    CATV: IChannel[];
    SKY: IChannel[];
    STARDIGIO: IChannel[];
}

// チャンネル情報を表すインターフェイス
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
    program_present: IProgram;
    program_following: IProgram;
}

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
    static async fetchAll(): Promise<IChannels | null> {

        // API リクエストを実行
        const response = await APIClient.get<IChannels>('/channels');

        // エラー処理
        if ('is_error' in response) {
            return null;
        }

        return response.data;
    }


    /**
     * 指定したチャンネルの情報を取得する
     * @param channel_id チャンネル ID
     * @return 指定したチャンネルの情報
     */
    static async fetch(channel_id: string): Promise<IChannel | null> {

        // API リクエストを実行
        const response = await APIClient.get<IChannel>(`/channels/${channel_id}`);

        // エラー処理
        if ('is_error' in response) {
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
            return null;
        }

        return response.data;
    }
}

export default Channels;
