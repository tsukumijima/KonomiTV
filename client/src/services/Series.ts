
import APIClient from '@/services/APIClient';
import { IChannel } from '@/services/Channels';
import { IRecordedProgram } from '@/services/Videos';


/** シリーズ情報を表すインターフェース */
export interface ISeries {
    id: number;
    title: string;
    description: string;
    genres: { major: string; middle: string; }[];
    broadcast_periods: ISeriesBroadcastPeriod[];
    created_at: string;
    updated_at: string;
}

/** シリーズ情報リストを表すインターフェース */
export interface ISeriesList {
    total: number;
    series_list: ISeries[];
}

/** シリーズ放送期間を表すインターフェース */
export interface ISeriesBroadcastPeriod {
    channel: IChannel;
    start_date: string;
    end_date: string;
    recorded_programs: IRecordedProgram[];
}


class Series {

    /**
     * シリーズ一覧を取得する
     * @param order ソート順序 ('desc' or 'asc')
     * @param page ページ番号
     * @returns シリーズ一覧情報 or シリーズ一覧情報の取得に失敗した場合は null
     */
    static async fetchSeriesList(order: 'desc' | 'asc' = 'desc', page: number = 1): Promise<ISeriesList | null> {

        // API リクエストを実行
        const response = await APIClient.get<ISeriesList>('/series', {
            params: {
                order,
                page,
            },
        });

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'シリーズ一覧を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * シリーズ番組を検索する
     * @param query 検索キーワード
     * @param order ソート順序 ('desc' or 'asc')
     * @param page ページ番号
     * @returns 検索結果のシリーズ番組一覧情報 or 検索に失敗した場合は null
     */
    static async searchSeries(query: string, order: 'desc' | 'asc' = 'desc', page: number = 1): Promise<ISeriesList | null> {

        // API リクエストを実行
        const response = await APIClient.get<ISeriesList>('/series/search', {
            params: {
                query,
                order,
                page,
            },
        });

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'シリーズ番組の検索に失敗しました。');
            return null;
        }

        return response.data;
    }


    /**
     * シリーズ情報を取得する
     * @param series_id シリーズ ID
     * @returns シリーズ情報 or シリーズ情報の取得に失敗した場合は null
     */
    static async fetchSeries(series_id: number): Promise<ISeries | null> {

        // API リクエストを実行
        const response = await APIClient.get<ISeries>(`/series/${series_id}`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'シリーズ情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }
}

export default Series;
