
import APIClient from  '@/services/APIClient';
import { IChannel } from '@/services/Channels';
import { CommentUtils } from '@/utils';

/** ソート順序を表す型 */
export type SortOrder = 'desc' | 'asc';

/** マイリストのソート順序を表す型 */
export type MylistSortOrder = 'mylist_added_desc' | 'mylist_added_asc' | 'recorded_desc' | 'recorded_asc';

/** 録画ファイル情報を表すインターフェース */
export interface IRecordedVideo {
    id: number;
    status: 'Recording' | 'Recorded' | 'AnalysisFailed';
    file_path: string;
    file_hash: string;
    file_size: number;
    file_created_at: string;
    file_modified_at: string;
    recording_start_time: string | null;
    recording_end_time: string | null;
    duration: number;
    container_format: 'MPEG-TS' | 'MPEG-4';
    video_codec: 'MPEG-2' | 'H.264' | 'H.265';
    video_codec_profile: 'High' | 'High 10' | 'Main' | 'Main 10' | 'Baseline';
    video_scan_type: 'Interlaced' | 'Progressive';
    video_frame_rate: number;
    video_resolution_width: number;
    video_resolution_height: number;
    primary_audio_codec: 'AAC-LC';
    primary_audio_channel: 'Monaural' | 'Stereo' | '5.1ch';
    primary_audio_sampling_rate: number;
    secondary_audio_codec: 'AAC-LC' | null;
    secondary_audio_channel: 'Monaural' | 'Stereo' | '5.1ch' | null;
    secondary_audio_sampling_rate: number | null;
    has_key_frames: boolean;
    cm_sections: { start_time: number; end_time: number; }[] | null;
    created_at: string;
    updated_at: string;
}

/** 録画ファイル情報を表すインターフェースのデフォルト値 */
export const IRecordedVideoDefault: IRecordedVideo = {
    id: -1,
    status: 'Recorded',
    file_path: '',
    file_hash: '',
    file_size: 0,
    file_created_at: '2000-01-01T00:00:00+09:00',
    file_modified_at: '2000-01-01T00:00:00+09:00',
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
    has_key_frames: false,
    cm_sections: null,
    created_at: '2000-01-01T00:00:00+09:00',
    updated_at: '2000-01-01T00:00:00+09:00',
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
    created_at: string;
    updated_at: string;
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
    created_at: '2000-01-01T00:00:00+09:00',
    updated_at: '2000-01-01T00:00:00+09:00',
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
     * 録画番組一覧を取得する
     * @param order ソート順序 ('desc' or 'asc' or 'ids')
     * @param page ページ番号
     * @param ids 録画番組の ID のリスト
     * @returns 録画番組一覧情報 or 録画番組一覧情報の取得に失敗した場合は null
     */
    static async fetchVideos(order: 'desc' | 'asc' | 'ids' = 'desc', page: number = 1, ids: number[] | null = null): Promise<IRecordedPrograms | null> {

        // API リクエストを実行
        const response = await APIClient.get<IRecordedPrograms>('/videos', {
            params: {
                order,
                page,
                ids,
            },
            // 録画番組の ID のリストを FastAPI が受け付ける &ids=1&ids=2&ids=3&... の形式にエンコードする
            // ref: https://github.com/axios/axios/issues/5058#issuecomment-1272107602
            paramsSerializer: {
                indexes: null,
            },
        });

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組一覧を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 録画番組を検索する
     * @param query 検索キーワード
     * @param order ソート順序 ('desc' or 'asc')
     * @param page ページ番号
     * @returns 検索結果の録画番組一覧情報 or 検索に失敗した場合は null
     */
    static async searchVideos(query: string, order: 'desc' | 'asc' = 'desc', page: number = 1): Promise<IRecordedPrograms | null> {

        // API リクエストを実行
        const response = await APIClient.get<IRecordedPrograms>('/videos/search', {
            params: {
                query,
                order,
                page,
            },
        });

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組の検索に失敗しました。');
            return null;
        }

        return response.data;
    }


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


    /**
     * 録画番組のメタデータを再解析する
     * @param video_id 録画番組の ID
     * @returns メタデータ再解析に成功した場合は true
     */
    static async reanalyzeVideo(video_id: number): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post(`/videos/${video_id}/reanalyze`, undefined, {
            // 数分以上かかるのでタイムアウトを 10 分に設定
            timeout: 10 * 60 * 1000,
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'メタデータの再解析に失敗しました。');
                    break;
            }
            return false;
        }

        return true;
    }


    /**
     * 録画番組のサムネイルを再生成する
     * @param video_id 録画番組の ID
     * @returns サムネイルの再生成に成功した場合は true
     */
    static async regenerateThumbnail(video_id: number): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post(`/videos/${video_id}/thumbnail/regenerate`, undefined, {
            // 数分以上かかるのでタイムアウトを 30 分に設定
            timeout: 30 * 60 * 1000,
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'サムネイルの再生成に失敗しました。');
                    break;
            }
            return false;
        }

        return true;
    }

    /**
     * 録画番組を削除する
     * @param video_id 録画番組の ID
     * @returns 削除に成功した場合は true
     */
    static async deleteVideo(video_id: number): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.delete(`/videos/${video_id}`);

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, '録画ファイルの削除に失敗しました。');
                    break;
            }
            return false;
        }

        return true;
    }
}

export default Videos;
