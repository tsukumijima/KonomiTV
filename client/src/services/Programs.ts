
import APIClient from '@/services/APIClient';


/** 番組情報を表すインターフェイス */
export interface IProgram {
    id: string;
    channel_id: string;
    network_id: number;
    service_id: number;
    event_id: number;
    title: string;
    description: string;
    detail: { [key: string]: string };
    start_time: string;
    end_time: string;
    duration: number;
    is_free: boolean;
    genres: { major: string; middle: string; }[];
    video_type: string | null;
    video_codec: string | null;
    video_resolution: string | null;
    primary_audio_type: string;
    primary_audio_language: string;
    primary_audio_sampling_rate: string;
    secondary_audio_type: string | null;
    secondary_audio_language: string | null;
    secondary_audio_sampling_rate: string | null;
}

/** 番組情報を表すインターフェイスのデフォルト値 */
export const IProgramDefault: IProgram = {
    id: 'NID0-SID0-EID0',
    channel_id: 'NID0-SID0',
    network_id: 0,
    service_id: 0,
    event_id: 0,
    title: '取得中…',
    description: '取得中…',
    detail: {},
    start_time: '2000-01-01T00:00:00+09:00',
    end_time: '2000-01-01T00:00:00+09:00',
    duration: 0,
    is_free: true,
    genres: [],
    video_type: '映像1080i(1125i)、アスペクト比16:9 パンベクトルなし',
    video_codec: 'MPEG-2',
    video_resolution: '1080i',
    primary_audio_type: '2/0モード(ステレオ)',
    primary_audio_language: '日本語',
    primary_audio_sampling_rate: '48kHz',
    secondary_audio_type: null,
    secondary_audio_language: null,
    secondary_audio_sampling_rate: null,
};

/** 番組情報を表すインターフェイス (present_or_following: Present なら現在放送中、Following なら次の番組であることを示す) */
export interface IProgramPF {
    type: 'IProgramPF';
    present_or_following: 'Present' | 'Following';
    program: IProgram;
}

/**
 * 番組情報リスト API のレスポンス
 */
export interface IPrograms {
    total: number;
    programs: IProgram[];
}

/**
 * 番組検索条件
 */
export interface IProgramSearchCondition {
    is_enabled: boolean;
    keyword: string;
    exclude_keyword: string;
    note: string;
    is_title_only: boolean;
    is_case_sensitive: boolean;
    is_fuzzy_search_enabled: boolean;
    is_regex_search_enabled: boolean;
    service_ranges: IProgramSearchConditionService[] | null;
    genre_ranges: { major: string; middle: string; }[] | null;
    is_exclude_genre_ranges: boolean;
    date_ranges: IProgramSearchConditionDate[] | null;
    is_exclude_date_ranges: boolean;
    duration_range_min: number | null;
    duration_range_max: number | null;
    broadcast_type: 'All' | 'FreeOnly' | 'PaidOnly';
    duplicate_title_check_scope: 'None' | 'SameChannelOnly' | 'AllChannels';
    duplicate_title_check_period_days: number;
}

/**
 * 番組検索条件のチャンネル
 */
export interface IProgramSearchConditionService {
    network_id: number;
    transport_stream_id: number;
    service_id: number;
}

/**
 * 番組検索条件の日付
 */
export interface IProgramSearchConditionDate {
    start_day_of_week: number; // 0-6 (日曜日-土曜日)
    start_hour: number; // 0-23
    start_minute: number; // 0-59
    end_day_of_week: number; // 0-6 (日曜日-土曜日)
    end_hour: number; // 0-23
    end_minute: number; // 0-59
}


/**
 * 番組情報に関する API 操作を提供するクラス
 */
class Programs {

    /**
     * 番組情報を検索する
     * @param program_search_condition 番組検索条件
     * @returns 検索結果の番組情報リスト、取得失敗時は null
     */
    static async searchPrograms(program_search_condition: IProgramSearchCondition): Promise<IPrograms | null> {
        const response = await APIClient.post<IPrograms>('/programs/search', program_search_condition);

        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'This API is only available when the backend is EDCB':
                    APIClient.showGenericError(response, 'この機能は EDCB バックエンド利用時のみ使用できます。');
                    break;
                default:
                    APIClient.showGenericError(response, '番組情報の検索に失敗しました。');
                    break;
            }
            return null;
        }

        return response.data;
    }
}

export default Programs;
