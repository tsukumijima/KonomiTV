
import { IChannel } from '@/services/Channels';


/** 録画番組情報を表すインターフェース */
export interface IRecordedProgram {
    id: number;
    recorded_video: IRecordedVideo;
    recording_start_margin: number;
    recording_end_margin: number;
    is_partially_recorded: boolean;
    channel: IChannel | null;
    network_id: number | null;
    service_id: number | null;
    event_id: number | null;
    series_id: number | null;
    series_broadcast_period_id: number | null;
    title: string;
    series_title: string | null;
    episode_number: string | null;
    subtitle: string | null;
    description: string;
    detail: { [key: string]: string };
    start_time: string;
    end_time: string;
    duration: number;
    is_free: boolean;
    genres: {major: string; middle: string;}[];
    primary_audio_type: string;
    primary_audio_language: string;
    secondary_audio_type: string | null;
    secondary_audio_language: string | null;
}

/** 録画番組情報リストを表すインターフェース */
export interface IRecordedPrograms {
    total: number;
    recorded_programs: IRecordedProgram[];
}

/** 録画ファイル情報を表すインターフェース */
export interface IRecordedVideo {
    id: number;
    file_path: string;
    file_hash: string;
    file_size: number;
    recording_start_time: string | null;
    recording_end_time: string | null;
    duration: number;
    container_format: 'MPEG-TS';
    video_codec: 'MPEG-2' | 'H.264' | 'H.265';
    video_codec_profile: 'High' | 'High 10' | 'Main' | 'Main 10' | 'Baseline';
    video_scan_type: 'Interlaced' | 'Progressive';
    video_frame_rate: number;
    video_resolution_width: number;
    video_resolution_height: number;
    primary_audio_codec: 'AAC-LC' | 'HE-AAC' | 'MP2';
    primary_audio_channel: 'Monaural' | 'Stereo' | '5.1ch';
    primary_audio_sampling_rate: number;
    secondary_audio_codec: 'AAC-LC' | 'HE-AAC' | 'MP2' | null;
    secondary_audio_channel: 'Monaural' | 'Stereo' | '5.1ch' | null;
    secondary_audio_sampling_rate: number | null;
    cm_sections: {start_time: number; end_time: number;}[];
}
