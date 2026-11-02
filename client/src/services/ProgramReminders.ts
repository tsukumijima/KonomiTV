import type { IChannel } from '@/services/Channels';
import type { IProgram } from '@/services/Programs';


/** 放送予定と、その番組をリマインドする理由。設定ストアを通じて端末間で同期する。 */
export interface IProgramReminder {
    key: string;
    program: IProgram;
    channel: Pick<IChannel, 'id' | 'name' | 'display_channel_id'>;
    source: 'Manual' | 'Recommended';
    status: 'Scheduled' | 'Dismissed';
    reasons: string[];
    created_at: number;
    /** 登録・照合時のキーワード。削除後も通知予定の絞り込みに使用する。未設定は既存保存データ。 */
    keyword_matches?: IProgramReminderKeyword[];
}

/** キーワードの ID・名前と、表示名を含む検索条件の完全一致に使うキー。 */
export interface IProgramReminderKeyword {
    id: string;
    name: string;
    /** 検索条件を保存順に直列化した値。条件を保持していなかった旧データでは未設定。 */
    condition_key?: string;
}

/** 1つの条件内は AND、複数の条件間は OR で番組を推薦する。 */
export interface IProgramRecommendationRule {
    id: string;
    name: string;
    keyword: string;
    exclude_keyword: string;
    genre: string | null;
    is_title_only: boolean;
    is_free_only: boolean;
    is_enabled: boolean;
}

/** この端末で作成したお知らせ。表示済みの判定にも使用する。 */
export interface IProgramReminderNotice {
    id: string;
    reminder_key: string;
    title: string;
    channel_name: string;
    start_time: string;
    end_time: string;
    display_channel_id: string;
    message: string;
    created_at: number;
    is_read: boolean;
}

/** 番組表から取得した放送予定。録画予約などの可変な情報は保持しない。 */
export interface IProgramReminderCandidate {
    program: IProgram;
    channel: IProgramReminder['channel'];
}

/** 選択式の設定画面に表示する、放送開始前のお知らせ時刻。 */
export const PROGRAM_REMINDER_LEAD_TIMES = [
    { title: '1週間前', value: 10080 },
    { title: '1日前', value: 1440 },
    { title: '3時間前', value: 180 },
    { title: '30分前', value: 30 },
    { title: '5分前', value: 5 },
    { title: '放送開始時', value: 0 },
];

/** 通知時刻の入力単位。保存済みの分単位の設定は、秒に換算して入力・判定する。 */
export const PROGRAM_REMINDER_TIME_UNITS = [
    { title: '日前', value: 'Day', seconds: 86400 },
    { title: '時間前', value: 'Hour', seconds: 3600 },
    { title: '分前', value: 'Minute', seconds: 60 },
    { title: '秒前', value: 'Second', seconds: 1 },
] as const;

export type ProgramReminderTimeUnit = typeof PROGRAM_REMINDER_TIME_UNITS[number]['value'];

/** 通知予定や候補を、キーワードごとに表示するためのグループ。 */
export interface IProgramReminderGroup {
    key: string;
    name: string;
    reminders: IProgramReminder[];
}
