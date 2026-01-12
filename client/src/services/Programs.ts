import type { Dayjs } from 'dayjs';

import APIClient from '@/services/APIClient';
import { IChannel } from '@/services/Channels';


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
 * 番組表 API のレスポンス
 */
export interface ITimeTable {
    channels: ITimeTableChannel[];
    date_range: ITimeTableDateRange;
}

/**
 * 番組表の日付範囲
 */
export interface ITimeTableDateRange {
    earliest: string;
    latest: string;
}

/**
 * 番組表向けのチャンネル情報
 * チャンネル基本情報と、そのチャンネルで放送される番組リストを含む
 */
export interface ITimeTableChannel {
    channel: IChannel;
    programs: ITimeTableProgram[];
    // サブチャンネルのリスト (8時間ルールで独立列として表示されないサブチャンネルのみ)
    subchannels: ITimeTableSubchannel[] | null;
}

/**
 * 番組表向けのサブチャンネル情報
 */
export interface ITimeTableSubchannel {
    channel: IChannel;
    programs: ITimeTableProgram[];
}

/**
 * 番組表向けの番組情報 (IProgram に予約情報を追加したもの)
 */
export interface ITimeTableProgram extends IProgram {
    reservation: ITimeTableProgramReservation | null;
}

/**
 * 番組表向けの録画予約情報
 */
export interface ITimeTableProgramReservation {
    id: number;
    status: 'Reserved' | 'Recording' | 'Disabled';
    recording_availability: 'Full' | 'Partial' | 'Unavailable';
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
                    APIClient.showGenericError(response, '番組検索機能は EDCB バックエンド選択時のみ利用できます。');
                    break;
                default:
                    APIClient.showGenericError(response, '番組情報の検索に失敗しました。');
                    break;
            }
            return null;
        }

        return response.data;
    }


    /**
     * 番組表データを取得する
     * @param start_time 開始日時
     * @param end_time 終了日時
     * @param channel_type チャンネルタイプ (省略時は全種別)
     * @param pinned_channel_ids チャンネル ID リスト (ピン留め用、指定時は channel_type より優先)
     * @returns 番組表データ、取得失敗時は null
     */
    static async fetchTimeTable(
        start_time: Dayjs,
        end_time: Dayjs,
        channel_type?: 'GR' | 'BS' | 'CS' | 'CATV' | 'SKY' | 'BS4K',
        pinned_channel_ids?: string[],
    ): Promise<ITimeTable | null> {

        // API リクエストのパラメータを構築
        // toISOString() は UTC で出力されるため、JST タイムゾーン付きの ISO 8601 形式で送信する
        const params = new URLSearchParams();
        params.set('start_time', start_time.format('YYYY-MM-DDTHH:mm:ssZ'));
        params.set('end_time', end_time.format('YYYY-MM-DDTHH:mm:ssZ'));

        // channel_type を指定
        if (channel_type !== undefined) {
            params.set('channel_type', channel_type);
        }

        // pinned_channel_ids を指定 (channel_type より優先される)
        if (pinned_channel_ids !== undefined && pinned_channel_ids.length > 0) {
            params.set('pinned_channel_ids', pinned_channel_ids.join(','));
        }

        // API リクエストを実行
        const response = await APIClient.get<ITimeTable>(`/programs/timetable?${params.toString()}`);

        if (response.type === 'error') {
            APIClient.showGenericError(response, '番組表データの取得に失敗しました。');
            return null;
        }

        return response.data;
    }
}

export default Programs;
