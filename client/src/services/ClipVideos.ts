import APIClient from '@/services/APIClient';
import Utils from '@/utils';


// クリップ動画に紐づくチャンネル情報
export interface IClipVideoChannel {
    id: number;
    display_channel_id: string;
    network_id: number;
    service_id: number;
    transport_stream_id: number;
    remocon_id: number | null;
    channel_number: string | null;
    type: string;
    name: string;
    jikkyo_force: string | null;
    is_subchannel: boolean;
}

// クリップ動画に紐づくシリーズ情報
export interface IClipVideoSeries {
    id: number;
    title: string;
    description: string | null;
}

// クリップ動画に紐づく録画番組情報
export interface IClipVideoRecordedProgram {
    id: number;
    channel_id: number | null;
    network_id: number | null;
    service_id: number | null;
    event_id: number | null;
    series_id: number | null;
    series_broadcast_period_id: number | null;
    title: string;
    description: string;
    detail: Record<string, string>;
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
    channel: IClipVideoChannel | null;
    series: IClipVideoSeries | null;
    [key: string]: unknown;
}

// クリップ動画情報を表すインターフェイス
export interface IClipSegment {
    start_time?: number;  // 秒指定（start_frame と排他）
    end_time?: number;    // 秒指定（end_frame と排他）
    start_frame?: number; // フレーム指定（start_time と排他）
    end_frame?: number;   // フレーム指定（end_time と排他）
}

export interface IClipVideo {
    id: number;
    recorded_video_id: number;
    recorded_program: IClipVideoRecordedProgram;
    title: string;
    alternate_title: string | null;
    file_path: string;
    file_hash: string;
    file_size: number;
    start_time: number;  // 元動画での開始時刻 (秒)
    end_time: number;  // 元動画での終了時刻 (秒)
    duration: number;  // クリップの長さ (秒)
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
    segments: IClipSegment[];
    created_at: string;
    updated_at: string;
}

// クリップ動画一覧のレスポンス
export interface IClipVideos {
    total: number;
    clip_videos: IClipVideo[];
}

/**
 * クリップ動画 API
 */
class ClipVideos {

    /**
     * クリップ動画一覧を取得する
     * @param sort 並び順 (desc: 新しい順、asc: 古い順)
     * @param page ページ番号 (1始まり)
     * @returns クリップ動画一覧
     */
    static async fetchClipVideos(sort: 'desc' | 'asc' = 'desc', page: number = 1, keyword?: string): Promise<IClipVideos | null> {
        const params: Record<string, string | number> = {
            sort,
            page,
        };
        if (keyword && keyword.trim() !== '') {
            params.keyword = keyword.trim();
        }

        const response = await APIClient.get<IClipVideos>('/clip-videos', {
            params,
        });
        if (response.type === 'success') {
            return response.data;
        }
        return null;
    }

    /**
     * 指定された ID のクリップ動画情報を取得する
     * @param clip_video_id クリップ動画の ID
     * @returns クリップ動画情報
     */
    static async fetchClipVideo(clip_video_id: number): Promise<IClipVideo | null> {
        const response = await APIClient.get<IClipVideo>(`/clip-videos/${clip_video_id}`);
        if (response.type === 'success') {
            return response.data;
        }
        return null;
    }

    /**
     * 指定された ID のクリップ動画を削除する
     * @param clip_video_id クリップ動画の ID
     * @returns 削除が成功したかどうか
     */
    static async deleteClipVideo(clip_video_id: number): Promise<boolean> {
        const response = await APIClient.delete(`/clip-videos/${clip_video_id}`);
        return response.type === 'success';
    }

    /**
     * 指定された ID のクリップ動画のメタデータを再解析する
     * @param clip_video_id クリップ動画の ID
     * @returns 再解析が成功したかどうか
     */
    static async reanalyzeClipVideo(clip_video_id: number): Promise<boolean> {
        const response = await APIClient.post(`/clip-videos/${clip_video_id}/reanalyze`, undefined, {
            timeout: 10 * 60 * 1000,
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'メタデータの再解析に失敗しました。');
            return false;
        }
        return true;
    }

    /**
     * クリップ動画のサムネイルを再生成する
     * @param clip_video_id クリップ動画の ID
     * @param skip_tile_if_exists 既にタイルサムネイルがある場合に再利用するかどうか
     * @returns サムネイル再生成が成功したかどうか
     */
    static async regenerateThumbnail(clip_video_id: number, skip_tile_if_exists: boolean = false): Promise<boolean> {
        const response = await APIClient.post(`/clip-videos/${clip_video_id}/thumbnail/regenerate`, undefined, {
            params: {
                skip_tile_if_exists: skip_tile_if_exists ? 'true' : 'false',
            },
            timeout: 30 * 60 * 1000,
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'サムネイルの再作成に失敗しました。');
            return false;
        }
        return true;
    }

    /**
     * クリップ動画の別タイトルを更新する
     * @param clip_video_id クリップ動画の ID
     * @param alternate_title 設定する別タイトル (null で解除)
     * @returns 更新後のクリップ動画情報
     */
    static async updateClipVideoAlternateTitle(clip_video_id: number, alternate_title: string | null): Promise<IClipVideo | null> {
        const response = await APIClient.post<IClipVideo>(`/clip-videos/${clip_video_id}/alternate-title`, {
            alternate_title,
        });
        if (response.type === 'success') {
            return response.data;
        }
        return null;
    }

    /**
     * クリップ動画のサムネイル URL を取得する
     * @param clip_video_id クリップ動画の ID
     * @returns サムネイル URL
     */
    static getClipVideoThumbnailURL(clip_video_id: number): string {
        return `${Utils.api_base_url}/clip-videos/${clip_video_id}/thumbnail`;
    }
}

export default ClipVideos;
