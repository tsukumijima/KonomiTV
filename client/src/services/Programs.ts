
/** 番組情報を表すインターフェイス */
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

// TODO: 番組情報 API が開発されたらここに API 定義を書く
