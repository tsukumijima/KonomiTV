
// 番組情報を表すインターフェイス
export interface IProgram {
    id: string;
    network_id: number;
    service_id: number;
    event_id: number;
    channel_id: string;
    title: string;
    description: string;
    detail: {[key: string]: string};
    start_time: string;
    end_time: string;
    duration: number;
    is_free: boolean;
    genre: {major: string; middle: string}[];
    video_type: string;
    video_codec: string;
    video_resolution: string;
    primary_audio_type: string;
    primary_audio_language: string;
    primary_audio_sampling_rate: string;
    secondary_audio_type: string | null;
    secondary_audio_language: string | null;
    secondary_audio_sampling_rate: string | null;
}

// 番組情報を表すインターフェイスのデフォルト値
export const IProgramDefault: IProgram = {
    id: 'NID0-SID0',
    service_id: 0,
    network_id: 0,
    event_id: 0,
    channel_id: 'gr000',
    title: '取得中…',
    description: '取得中…',
    detail: {},
    start_time: '2000-01-01T00:00:00+09:00',
    end_time: '2000-01-01T00:00:00+09:00',
    duration: 0,
    is_free: true,
    genre: [],
    video_type: '映像1080i(1125i)、アスペクト比16:9 パンベクトルなし',
    video_codec: 'mpeg2',
    video_resolution: '1080i',
    primary_audio_type: '2/0モード(ステレオ)',
    primary_audio_language: '日本語',
    primary_audio_sampling_rate: '48kHz',
    secondary_audio_type: null,
    secondary_audio_language: null,
    secondary_audio_sampling_rate: null,
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
    channel_type: string;
    channel_force: number | null;
    channel_comment: number | null;
    is_subchannel: boolean;
    is_display: boolean;
    viewers: number;
    program_present: IProgram;
    program_following: IProgram;
}

// チャンネル情報を表すインターフェイスのデフォルト値
export const IChannelDefault: IChannel = {
    id: 'NID0-SID0',
    service_id: 0,
    network_id: 0,
    transport_stream_id: null,
    remocon_id: null,
    channel_id: 'gr000',
    channel_number: '---',
    channel_name: '取得中…',
    channel_type: 'GR',
    channel_force: null,
    channel_comment: null,
    is_subchannel: false,
    is_display: true,
    viewers: 0,
    program_present: IProgramDefault,
    program_following: IProgramDefault,
}
