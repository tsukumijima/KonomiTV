
import APIClient from  '@/services/APIClient';
import { IChannel } from '@/services/Channels';
import { CommentUtils } from '@/utils';


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
    cm_sections: { start_time: number; end_time: number; }[];
}

/** 録画ファイル情報を表すインターフェースのデフォルト値 */
export const IRecordedVideoDefault: IRecordedVideo = {
    id: -1,
    file_path: '',
    file_hash: '',
    file_size: 0,
    recording_start_time: null,
    recording_end_time: null,
    duration: 0,
    container_format: 'MPEG-TS',
    video_codec: 'MPEG-2',
    video_codec_profile: 'High',
    video_scan_type: 'Interlaced',
    video_frame_rate: 29.97,
    video_resolution_width: 1440,
    video_resolution_height: 1080,
    primary_audio_codec: 'AAC-LC',
    primary_audio_channel: 'Stereo',
    primary_audio_sampling_rate: 48000,
    secondary_audio_codec: null,
    secondary_audio_channel: null,
    secondary_audio_sampling_rate: null,
    cm_sections: [],
};

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
    genres: { major: string; middle: string; }[];
    primary_audio_type: string;
    primary_audio_language: string;
    secondary_audio_type: string | null;
    secondary_audio_language: string | null;
}

/** 録画番組情報を表すインターフェースのデフォルト値 */
export const IRecordedProgramDefault: IRecordedProgram = {
    id: -1,
    recorded_video: IRecordedVideoDefault,
    recording_start_margin: 0,
    recording_end_margin: 0,
    is_partially_recorded: false,
    channel: null,
    network_id: null,
    service_id: null,
    event_id: null,
    series_id: null,
    series_broadcast_period_id: null,
    title: '取得中…',
    series_title: null,
    episode_number: null,
    subtitle: null,
    description: '取得中…',
    detail: {},
    start_time: '2000-01-01T00:00:00+09:00',
    end_time: '2000-01-01T00:00:00+09:00',
    duration: 0,
    is_free: true,
    genres: [],
    primary_audio_type: '2/0モード(ステレオ)',
    primary_audio_language: '日本語',
    secondary_audio_type: null,
    secondary_audio_language: null,
};

/** 録画番組情報リストを表すインターフェース */
export interface IRecordedPrograms {
    total: number;
    recorded_programs: IRecordedProgram[];
}

/** 過去ログコメントを表すインターフェース */
export interface IJikkyoComment {
    time: number;
    type: 'top' | 'right' | 'bottom';
    size: 'big' | 'medium' | 'small';
    color: string;
    author: string;
    text: string;
}

/** 過去ログコメントのリストを表すインターフェース */
export interface IJikkyoComments {
    is_success: boolean;
    comments: IJikkyoComment[];
    detail: string;
}


class Videos {

    /**
     * 録画番組情報を取得する
     * @param video_id 録画番組の ID
     * @returns 録画番組情報 or 録画番組情報の取得に失敗した場合は null
     */
    static async fetchVideo(video_id: number): Promise<IRecordedProgram | null> {

        // API リクエストを実行
        const response = await APIClient.get<IRecordedProgram>(`/videos/${video_id}`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 録画番組の放送中に投稿されたニコニコ実況の過去ログコメントを取得する
     * @param video_id 録画番組の ID
     * @returns 過去ログコメントのリスト
     */
    static async fetchVideoJikkyoComments(video_id: number): Promise<IJikkyoComments> {

        // API リクエストを実行
        const response = await APIClient.get<IJikkyoComments>(`/videos/${video_id}/jikkyo`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, '過去ログコメントを取得できませんでした。');
            return {
                is_success: false,
                comments: [],
                detail: '過去ログコメントを取得できませんでした。',
            };
        }

        // ミュート対象のコメントを除外して返す
        response.data.comments = response.data.comments.filter((comment) => {
            return CommentUtils.isMutedComment(comment.text, comment.author, comment.color, comment.type, comment.size) === false;
        });
        return response.data;
    }
}

export default Videos;
