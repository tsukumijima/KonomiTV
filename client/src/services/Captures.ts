
import { AxiosError } from 'axios';

import Message from '@/message';
import APIClient from '@/services/APIClient';
import Utils, { Semaphore } from '@/utils';


/** キャプチャの一覧 */
export interface ICaptures {
    captures: ICapture[];
    programs: ICaptureProgram[];
    next_cursor: string | null;
}

/** キャプチャ */
export interface ICapture {
    id: number;
    file_hash: string;
    file_size: number;
    captured_at: string;
    broadcast_at: string | null;
    image_width: number;
    image_height: number;
    metadata_status: 'Parsed' | 'NoMetadata' | 'Invalid';
    playback_position: number | null;
    caption_text: string | null;
    is_caption_composited: boolean;
    is_comment_composited: boolean;
    capture_program_id: number | null;
    is_favorite: boolean | null;
    tag_ids: number[] | null;
}

/** キャプチャに埋め込まれた番組情報を、番組キーごとにまとめたもの */
export interface ICaptureProgram {
    id: number;
    network_id: number;
    service_id: number;
    event_id: number;
    start_time: string;
    // 放送時間未定の番組で撮ったキャプチャだけで作った放送回は、終了時刻と番組長が不明なので null になる
    end_time: string | null;
    duration: number | null;
    title: string;
    description: string;
    channel: ICaptureChannel | null;
    recorded_program_ids: number[];
}

/** キャプチャの番組に紐づくチャンネル */
export interface ICaptureChannel {
    id: string;
    display_channel_id: string;
    name: string;
    type: string;
}

/** 日付ごとのキャプチャの件数 */
export interface ICaptureSections {
    sections: ICaptureSection[];
    total: number;
}

/** 1日分のキャプチャの件数 */
export interface ICaptureSection {
    date: string;
    count: number;
}

/** 番組ごとのキャプチャのまとまりの一覧 */
export interface ICapturePrograms {
    programs: ICaptureProgramAlbum[];
    next_cursor: string | null;
}

/** 枚数と代表のキャプチャを含む、番組ごとのキャプチャのまとまり */
export interface ICaptureProgramAlbum extends ICaptureProgram {
    capture_count: number;
    cover_capture: ICapture;
}

/** キャプチャのタグ */
export interface ICaptureTag {
    id: number;
    name: string;
    capture_count: number;
    created_at: string;
    updated_at: string;
}

/** キャプチャの削除の結果 */
export interface ICaptureDeleteResult {
    deleted_capture_ids: number[];
    failed_capture_ids: number[];
}

/** キャプチャの詳細 (番組と実ファイルの場所を含む) */
export interface ICaptureDetail extends ICapture {
    program: ICaptureProgram | null;
    files: ICaptureFile[];
}

/** キャプチャの実ファイルの場所 */
export interface ICaptureFile {
    file_name: string;
    file_path: string;
    status: 'Available' | 'Missing' | 'Invalid';
}

/** キャプチャの一覧の並び順 */
export type CaptureSortOrder = 'CapturedAtDesc' | 'CapturedAtAsc' | 'BroadcastAtDesc' | 'BroadcastAtAsc' | 'PlaybackPosition';

/** 放送回の一覧の並び順 */
export type CaptureProgramSortOrder = 'BroadcastAtDesc' | 'BroadcastAtAsc';

/** タイムラインの時間の軸 (撮影日時か放送日時か) */
export type CaptureTimelineAxis = 'CapturedAt' | 'BroadcastAt';

/** 検索語を探す範囲 (1つも指定しない場合は、字幕・番組名・番組概要・チャンネル名・ファイル名のすべてから探す) */
export type CaptureQueryTarget = 'CaptionText' | 'ProgramTitle' | 'ProgramDescription';

/** キャプチャの一覧と日付ごとの件数の絞り込み */
export interface ICaptureFilter {
    capture_program_id?: number | null;
    recorded_program_id?: number | null;
    network_id?: number | null;
    service_id?: number | null;
    event_id?: number | null;
    start_time?: string | null;
    is_favorite?: boolean | null;
    tag_id?: number | null;
    is_caption_composited?: boolean | null;
    is_comment_composited?: boolean | null;
    has_caption_text?: boolean | null;
    has_metadata?: boolean | null;
    query?: string | null;
    query_targets?: CaptureQueryTarget[] | null;
}


class Captures {

    // 同時アップロード数の上限 & セマフォインスタンス
    private static readonly MAX_CONCURRENT_UPLOADS = 5;
    private static readonly semaphore = new Semaphore(Captures.MAX_CONCURRENT_UPLOADS);

    /**
     * キャプチャをサーバーにアップロードし保存する
     * @param blob キャプチャ画像の Blob
     * @param filename サーバーに保存するときのファイル名
     */
    static async uploadCapture(blob: Blob, filename: string): Promise<void> {

        // リトライループ
        // 成功するか、リトライ不可なエラーが発生するまで継続
        // eslint-disable-next-line no-constant-condition
        while (true) {

            // キャプチャ画像の File オブジェクト (= Blob) を FormData に入れる
            // multipart/form-data で送るために必要
            // ref: https://r17n.page/2020/02/04/nodejs-axios-file-upload-api/
            const form_data = new FormData();
            form_data.append('image', blob, filename);

            // セマフォを取得し、アップロードを同時 5 件までに制限する
            await this.semaphore.acquire();
            let response: Awaited<ReturnType<typeof APIClient.post>>;
            try {
                // API リクエストを実行
                response = await APIClient.post('/captures', form_data, {
                    headers: {'Content-Type': 'multipart/form-data'},
                    // 回線状況によってはアップロードに時間がかかることがあるので、
                    // タイムアウトを 60 秒に伸ばす
                    timeout: 60 * 1000,
                });
            } finally {
                // セマフォを必ず解放する (アップロード試行 1 回分のみを占有)
                this.semaphore.release();
            }

            // 成功
            if (response.type !== 'error') {
                return;
            }

            // エラー処理
            switch (response.data.detail) {
                case 'Permission denied to save the file': {
                    Message.error('キャプチャのアップロードに失敗しました。保存先フォルダに書き込み権限がありません。');
                    return;
                }
                case 'No space left on the device': {
                    Message.error('キャプチャのアップロードに失敗しました。保存先フォルダに空き容量がありません。');
                    return;
                }
                case 'Unexpected error occurred while saving the file': {
                    Message.error('キャプチャのアップロードに失敗しました。保存中に予期しないエラーが発生しました。');
                    return;
                }
                default: {
                    if (Number.isNaN(response.status)) {
                        // HTTP リクエスト自体が失敗した場合はネットワークエラーの可能性が高い & 基本アップロードに失敗してはならないので、リトライする
                        // リトライする前に 1 ~ 15 秒程度ランダムに待機することで、
                        // リトライリクエストが同じタイミングで殺到するのを回避する
                        const sleep_time_seconds = 1 + Math.random() * 15;
                        if (response.error.code === AxiosError.ECONNABORTED) {
                            // ネットワーク接続エラーの場合
                            Message.warning(`キャプチャのアップロード中にサーバーへの接続が切断されました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        } else if (response.error.code === AxiosError.ETIMEDOUT) {
                            // タイムアウトの場合
                            Message.warning(`キャプチャのアップロード中にサーバーへの接続がタイムアウトしました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        } else if (response.error.code === AxiosError.ERR_NETWORK) {
                            // 予期しないネットワークエラーの場合
                            Message.warning(`キャプチャのアップロード中に予期しないネットワークエラーが発生しました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        } else {
                            // それ以外のエラーの場合
                            Message.warning(`キャプチャのアップロードに失敗しました。${sleep_time_seconds.toFixed(2)} 秒後にリトライします。`);
                        }
                        await Utils.sleep(sleep_time_seconds);  // 秒単位で指定
                        // ループ先頭に戻ってリトライ
                        continue;
                    } else {
                        APIClient.showGenericError(response, 'キャプチャのアップロードに失敗しました。');
                        return;
                    }
                }
            }
        }
    }

    /**
     * 手元の画像ファイルをキャプチャとしてアップロードし、登録されたキャプチャを返す
     * 視聴画面からのアップロードと違い、ファイルの更新日時を一緒に送り、メタデータのない画像の撮影日時として使わせる
     * @param file アップロードする画像ファイル
     * @returns 登録されたキャプチャ (失敗時は null)
     */
    static async uploadLocalFile(file: File): Promise<ICapture | null> {

        // ブラウザが読めるファイルの更新日時を一緒に送る
        // サーバー側で保存したファイルの更新日時に設定しないと、撮影日時がアップロードした日時になってしまう
        const form_data = new FormData();
        form_data.append('image', file, file.name);
        form_data.append('file_modified_at', String(file.lastModified));

        await this.semaphore.acquire();
        let response: Awaited<ReturnType<typeof APIClient.post<ICapture>>>;
        try {
            response = await APIClient.post<ICapture>('/captures', form_data, {
                headers: {'Content-Type': 'multipart/form-data'},
                timeout: 60 * 1000,
            });
        } finally {
            this.semaphore.release();
        }
        if (response.type === 'error') {
            APIClient.showGenericError(response, `${file.name} のアップロードに失敗しました。`);
            return null;
        }
        return response.data;
    }


    /**
     * 一覧や日付ごとの件数の API に渡す絞り込みを、クエリパラメータに変換する
     * 指定された絞り込みだけをパラメータに入れる
     * @param filter 絞り込みの条件
     * @returns クエリパラメータ
     */
    private static buildFilterParams(filter: ICaptureFilter): Record<string, string | number | boolean | string[]> {
        const params: Record<string, string | number | boolean | string[]> = {};
        for (const [key, value] of Object.entries(filter)) {
            // 空の配列 (検索語を探す範囲を1つも選んでいない) も、指定なしとして送らない
            if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
                continue;
            }
            params[key] = value as string | number | boolean | string[];
        }
        return params;
    }


    /**
     * キャプチャの一覧を取得する
     * @param options 並び順・カーソル・件数・日付・絞り込み
     * @returns キャプチャの一覧 (失敗時は null)
     */
    static async fetchCaptures(options: {
        order?: CaptureSortOrder;
        cursor?: string | null;
        limit?: number;
        date?: string | null;
        day_start_hour?: number;
        filter?: ICaptureFilter;
    } = {}): Promise<ICaptures | null> {

        const params: Record<string, string | number | boolean | string[]> = {
            ...this.buildFilterParams(options.filter ?? {}),
            order: options.order ?? 'CapturedAtDesc',
            limit: options.limit ?? 100,
        };
        if (options.cursor) {
            params.cursor = options.cursor;
        }
        if (options.date) {
            params.date = options.date;
            params.day_start_hour = options.day_start_hour ?? 0;
        }

        const response = await APIClient.get<ICaptures>('/captures', {
            params,
            // 検索語を探す範囲のリストを FastAPI が受け付ける &query_targets=A&query_targets=B の形式にエンコードする
            paramsSerializer: {
                indexes: null,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'キャプチャの一覧を取得できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * 条件に合うキャプチャを、カーソルをたどって最後まで取得する
     * 番組の中のキャプチャ (多くても数百件) のように、件数が限られる一覧のためのもの
     * @param options 並び順・日付・絞り込み
     * @returns キャプチャと、それらが参照する番組 (失敗時は null)
     */
    static async fetchAllCaptures(options: {
        order?: CaptureSortOrder;
        date?: string | null;
        day_start_hour?: number;
        filter?: ICaptureFilter;
    } = {}): Promise<ICaptures | null> {

        const captures: ICapture[] = [];
        const programs = new Map<number, ICaptureProgram>();
        let cursor: string | null = null;

        // 次のページが無くなるまで取得を繰り返す
        do {
            const page = await this.fetchCaptures({ ...options, cursor, limit: 200 });
            if (page === null) {
                return null;
            }
            captures.push(...page.captures);
            for (const program of page.programs) {
                programs.set(program.id, program);
            }
            cursor = page.next_cursor;
        } while (cursor !== null);

        return { captures, programs: [...programs.values()], next_cursor: null };
    }


    /**
     * 日付ごとのキャプチャの件数を取得する (タイムラインの高さとスクラバーの元になる)
     * @param options 時間の軸・日付の境目の時刻・絞り込み
     * @returns 日付ごとの件数 (失敗時は null)
     */
    static async fetchSections(options: {
        axis?: CaptureTimelineAxis;
        day_start_hour?: number;
        filter?: ICaptureFilter;
    } = {}): Promise<ICaptureSections | null> {

        const params: Record<string, string | number | boolean | string[]> = {
            ...this.buildFilterParams(options.filter ?? {}),
            axis: options.axis ?? 'CapturedAt',
            day_start_hour: options.day_start_hour ?? 0,
        };
        const response = await APIClient.get<ICaptureSections>('/captures/sections', {
            params,
            // 検索語を探す範囲のリストを FastAPI が受け付ける &query_targets=A&query_targets=B の形式にエンコードする
            paramsSerializer: {
                indexes: null,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'キャプチャの日付ごとの件数を取得できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * キャプチャの詳細を取得する
     * @param capture_id キャプチャの ID
     * @returns キャプチャの詳細 (失敗時は null)
     */
    static async fetchCapture(capture_id: number): Promise<ICaptureDetail | null> {
        const response = await APIClient.get<ICaptureDetail>(`/captures/${capture_id}`);
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'キャプチャの情報を取得できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * キャプチャの画像の URL を返す
     * 画像は長期間キャッシュされるので、内容が変わったら URL も変わるよう、内容のハッシュを URL に付加する
     * @param capture キャプチャ
     * @returns 画像の URL
     */
    static getImageURL(capture: ICapture): string {
        return `${Utils.api_base_url}/captures/${capture.id}/image?hash=${capture.file_hash}`;
    }


    /**
     * 番組ごとのキャプチャのまとまり (放送の回ごと) の一覧を取得する
     * @param options カーソル・件数・検索語・録画の有無での絞り込み・並び順
     * @returns 番組の一覧 (失敗時は null)
     */
    static async fetchPrograms(options: {
        cursor?: string | null;
        limit?: number;
        query?: string;
        has_recorded_program?: boolean | null;
        order?: CaptureProgramSortOrder;
    } = {}): Promise<ICapturePrograms | null> {

        const params: Record<string, string | number | boolean> = {
            order: options.order ?? 'BroadcastAtDesc',
            limit: options.limit ?? 60,
        };
        if (options.cursor) {
            params.cursor = options.cursor;
        }
        if (options.query) {
            params.query = options.query;
        }
        if (options.has_recorded_program !== null && options.has_recorded_program !== undefined) {
            params.has_recorded_program = options.has_recorded_program;
        }
        const response = await APIClient.get<ICapturePrograms>('/captures/programs', { params });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'キャプチャの番組の一覧を取得できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * 番組ごとのキャプチャのまとまりを1件取得する
     * @param capture_program_id キャプチャの番組の ID
     * @returns 番組 (失敗時は null)
     */
    static async fetchProgram(capture_program_id: number): Promise<ICaptureProgramAlbum | null> {
        const response = await APIClient.get<ICaptureProgramAlbum>(`/captures/programs/${capture_program_id}`);
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'キャプチャの番組の情報を取得できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * キャプチャをお気に入りに追加する・お気に入りから外す (ログイン必須)
     * @param capture_ids キャプチャの ID のリスト
     * @param is_favorite true ならお気に入りに追加し、false なら外す
     * @returns 成功したかどうか
     */
    static async updateFavorites(capture_ids: number[], is_favorite: boolean): Promise<boolean> {
        const response = is_favorite ?
            await APIClient.post('/captures/favorites', { capture_ids }) :
            await APIClient.delete('/captures/favorites', { data: { capture_ids } });
        if (response.type === 'error') {
            APIClient.showGenericError(response, is_favorite ? 'お気に入りに追加できませんでした。' : 'お気に入りから外せませんでした。');
            return false;
        }
        return true;
    }


    /**
     * 本人のタグの一覧を取得する (ログイン必須)
     * @returns タグの一覧 (失敗時は null)
     */
    static async fetchTags(): Promise<ICaptureTag[] | null> {
        const response = await APIClient.get<ICaptureTag[]>('/captures/tags');
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'タグの一覧を取得できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * タグを作成する (ログイン必須)
     * @param name タグの名前
     * @returns 作成したタグ (失敗時は null)
     */
    static async createTag(name: string): Promise<ICaptureTag | null> {
        const response = await APIClient.post<ICaptureTag>('/captures/tags', { name });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'タグを作成できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * タグの名前を変更する (ログイン必須)
     * @param tag_id タグの ID
     * @param name 新しい名前
     * @returns 変更後のタグ (失敗時は null)
     */
    static async renameTag(tag_id: number, name: string): Promise<ICaptureTag | null> {
        const response = await APIClient.put<ICaptureTag>(`/captures/tags/${tag_id}`, { name });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'タグの名前を変更できませんでした。');
            return null;
        }
        return response.data;
    }


    /**
     * タグを削除する (キャプチャ自体は消えない) (ログイン必須)
     * @param tag_id タグの ID
     * @returns 成功したかどうか
     */
    static async deleteTag(tag_id: number): Promise<boolean> {
        const response = await APIClient.delete(`/captures/tags/${tag_id}`);
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'タグを削除できませんでした。');
            return false;
        }
        return true;
    }


    /**
     * キャプチャにタグを付ける・外す (ログイン必須)
     * @param tag_id タグの ID
     * @param capture_ids キャプチャの ID のリスト
     * @param is_tagged true なら付け、false なら外す
     * @returns 成功したかどうか
     */
    static async updateTagItems(tag_id: number, capture_ids: number[], is_tagged: boolean): Promise<boolean> {
        const response = is_tagged ?
            await APIClient.post(`/captures/tags/${tag_id}/items`, { capture_ids }) :
            await APIClient.delete(`/captures/tags/${tag_id}/items`, { data: { capture_ids } });
        if (response.type === 'error') {
            APIClient.showGenericError(response, is_tagged ? 'タグを付けられませんでした。' : 'タグを外せませんでした。');
            return false;
        }
        return true;
    }


    /**
     * キャプチャを削除する (実ファイルも削除される) (管理者のみ)
     * @param capture_ids キャプチャの ID のリスト
     * @returns 削除の結果 (失敗時は null)
     */
    static async deleteCaptures(capture_ids: number[]): Promise<ICaptureDeleteResult | null> {
        const response = await APIClient.delete<ICaptureDeleteResult>('/captures', { data: { capture_ids } });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'キャプチャを削除できませんでした。');
            return null;
        }
        return response.data;
    }
}

export default Captures;
