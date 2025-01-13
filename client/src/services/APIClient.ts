
/**
 * services/ 直下の各クラスは、KonomiTV サーバーへの API リクエストを抽象化し、
 * API レスポンスの受け取りと、エラーが発生した際のエラーハンドリング (エラーメッセージ表示) までを責務として負う
 */

import axios, { AxiosError, AxiosRequestConfig, AxiosResponse, AxiosResponseHeaders, RawAxiosResponseHeaders } from 'axios';

import Message from '@/message';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';
import useCFZTStore from '@/stores/CloudflareZerotrustStone';


/** API リクエスト成功時のレスポンスを表すインターフェイス */
export interface ISuccessResponse<T> {
    type: 'success';
    status: number;
    headers: RawAxiosResponseHeaders | AxiosResponseHeaders;
    data: T;
}

/** API リクエスト失敗時のレスポンスを表すインターフェイス */
export interface IErrorResponse {
    type: 'error';
    status: number;
    headers: RawAxiosResponseHeaders | AxiosResponseHeaders;
    data: IErrorResponseData;
    error: AxiosError<IErrorResponseData>;
}

/**
 * API リクエスト失敗時にサーバーから返されるエラーレスポンスを表すインターフェイス
 * HTTP リクエスト自体が失敗した場合は、detail に AxiosError のエラーメッセージが入る
 */
export interface IErrorResponseData {
    detail: string | [{
        type: string;
        loc: (string | number)[];
        msg: string;
        input?: any;
        url?: string;
    }]
}


/**
 * services/ 以下の各クラスから呼び出される、Axios の薄いラッパー
 * エラーハンドリングを容易にするために、レスポンスを ISuccessResponse と IErrorResponse に分けて返す
 * ref: https://zenn.dev/engineer_titan/articles/291c9fccb338e2
 */
class APIClient {

    /**
     * Axios で HTTP リクエストを送信し、レスポンスを受け取る
     * @param request AxiosRequestConfig
     * @returns 成功なら ISuccessResponse 、失敗なら IErrorResponse を返す
     */
    static async request<T>(request: AxiosRequestConfig): Promise<ISuccessResponse<T> | IErrorResponse> {

        // API のベース URL を設定 (config.baseURL が指定されていない場合のみ)
        if (request.baseURL === undefined) {
            request.baseURL = Utils.api_base_url;
        }

        // リクエストヘッダーが指定されていない場合は空のオブジェクトを設定
        if (request.headers === undefined) {
            request.headers = {};
        }

        // 外部サイトへの HTTP/HTTPS リクエストでは実行しない
        if (request.url?.startsWith('http') === false) {

            // アクセストークンが取得できたら (=ログインされていれば)
            // 取得したアクセストークンを Authorization ヘッダーに Bearer トークンとしてセット
            // これを忘れると当然ながらログインしていない扱いになる
            const access_token = Utils.getAccessToken();
            if (access_token !== null) {
                request.headers['Authorization'] = `Bearer ${access_token}`;
            }

            // KonomiTV クライアントのバージョンを設定
            // 今のところ使わないが、将来的にクライアントとサーバーを分離することを見据えて念のため
            request.headers['X-KonomiTV-Version'] = Utils.version;
        }

        // リクエストのタイムアウト時間を30秒に設定
        // 既にタイムアウト時間が設定されている場合は上書きしない
        if (request.timeout === undefined) {
            request.timeout = 30 * 1000;
        }

        // リクエストのタイムアウト時に、一般的な ECONNABORTED の代わりに ETIMEDOUT を送出する
        request.transitional = {
            clarifyTimeoutError: true,
        };

        // Axios で HTTP リクエストを送信し、レスポンスを受け取る
        const result: AxiosResponse<T> | AxiosError<IErrorResponseData> = await axios.request(request).catch((error) => error);

        // エラーが発生した場合は IErrorResponse を返す
        if (result instanceof AxiosError) {
            console.error(result);

            // エラーレスポンスがあれば、エラー内容と AxiosError を IErrorResponse に入れて返す
            if (result.response) {
                return {
                    type: 'error',
                    status: result.response.status,
                    headers: result.response.headers,
                    data: result.response.data,  // data には IErrorResponseData が入る
                    error: result,  // AxiosError をそのまま入れる
                };

            // エラーレスポンスがない場合は、AxiosError のみを IErrorResponse に入れて返す
            } else {
                return {
                    type: 'error',
                    status: NaN,  // ステータスコードは取得できないので NaN にする
                    headers: {},  // ヘッダーも取得できないので空のオブジェクトにする
                    data: {detail: result.message},  // data.detail に AxiosError のエラーメッセージを入れる
                    error: result,  // AxiosError をそのまま入れる
                };
            }

        // 正常にレスポンスが返ってきた場合は ISuccessResponse を返す
        } else {
            return {
                type: 'success',
                headers: result.headers,
                status: result.status,
                data: result.data,
            };
        }
    }


    /**
     * GET リクエストを送信する
     * @param url リクエスト先の URL
     * @param config AxiosRequestConfig
     * @returns 成功なら ISuccessResponse 、失敗なら IErrorResponse を返す
     */
    static async get<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<ISuccessResponse<T> | IErrorResponse> {
        const request: AxiosRequestConfig = {
            url: url,
            method: 'GET',
            ...config,
        };
        return await APIClient.request<T>(request);
    }


    /**
     * POST リクエストを送信する
     * @param url リクエスト先の URL
     * @param data 送信するデータ
     * @param config AxiosRequestConfig
     * @returns 成功なら ISuccessResponse 、失敗なら IErrorResponse を返す
     */
    static async post<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<ISuccessResponse<T> | IErrorResponse> {
        const request: AxiosRequestConfig = {
            url: url,
            method: 'POST',
            data: data,
            ...config,
        };
        return await APIClient.request<T>(request);
    }


    /**
     * PUT リクエストを送信する
     * @param url リクエスト先の URL
     * @param data 送信するデータ
     * @param config AxiosRequestConfig
     * @returns 成功なら ISuccessResponse 、失敗なら IErrorResponse を返す
     */
    static async put<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<ISuccessResponse<T> | IErrorResponse> {
        const request: AxiosRequestConfig = {
            url: url,
            method: 'PUT',
            data: data,
            ...config,
        };
        return await APIClient.request<T>(request);
    }


    /**
     * DELETE リクエストを送信する
     * @param url リクエスト先の URL
     * @param config AxiosRequestConfig
     * @returns 成功なら ISuccessResponse 、失敗なら IErrorResponse を返す
     */
    static async delete<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<ISuccessResponse<T> | IErrorResponse> {
        const request: AxiosRequestConfig = {
            url: url,
            method: 'DELETE',
            ...config,
        };
        return await APIClient.request<T>(request);
    }


    /**
     * 一般的なエラーメッセージの共通処理
     * エラーメッセージを SnackBar で表示する
     * @param error_response API から返されたエラーレスポンス
     * @param template エラーメッセージのテンプレート（「アカウント情報を取得できませんでした。」など)
     */
    static showGenericError(error_response: IErrorResponse, template: string): void {
        const user_store = useUserStore();
        switch (error_response.data.detail) {
            case 'Not authenticated': {
                user_store.logout(true);
                Message.error(`${template}\nログインし直してください。`);
                return;
            }
            case 'Access token data is invalid': {
                user_store.logout(true);
                Message.error(`${template}\nログインセッションが不正です。もう一度ログインし直してください。`);
                return;
            }
            case 'Access token is invalid': {
                user_store.logout(true);
                Message.error(`${template}\nログインセッションの有効期限が切れています。もう一度ログインし直してください。`);
                return;
            }
            case 'User associated with access token does not exist': {
                user_store.logout(true);
                Message.error(`${template}\nログインセッションに紐づくユーザーが存在しないか、削除されています。`);
                return;
            }
            case 'Don\'t have permission to access this resource': {
                Message.error(`${template}\nこのリソースにアクセスする権限がありません。`);
                return;
            }
            default: {
                if (Array.isArray(error_response.data.detail)) {
                    // バリデーションエラーが発生した場合
                    // error_response.data.detail が配列の場合は、バリデーションエラーが発生したとみなす
                    // FastAPI が返すバリデーションエラーのレスポンスを整形して、エラーメッセージを表示する
                    let message = '';
                    for (const error of error_response.data.detail) {
                        // いい感じに loc を整形して、コードっぽくする
                        const loc = error.loc.map(item => typeof item === 'number' ? `[${item}]` : item).join('.')
                            .replaceAll('.[', '[').replaceAll('body.', '').replaceAll('query.', '');
                        message += `⚠️ ${loc}: ${error.msg.replace('Value error, ', '')}\n`;
                    }
                    Message.error(`${template}\n${message}`);
                    return;
                } else if (Number.isNaN(error_response.status)) {
                    // HTTP リクエスト自体が失敗し、HTTP ステータスコードが取得できなかった場合
                    if (error_response.error.code === AxiosError.ECONNABORTED) {
                        // ネットワーク接続エラーの場合
                        Message.error(`${template}\nサーバーへの接続が切断されました。(${error_response.error.message})`);
                    } else if (error_response.error.code === AxiosError.ETIMEDOUT) {
                        // タイムアウトの場合
                        Message.error(`${template}\nサーバーへの接続がタイムアウトしました。(${error_response.error.message})`);
                    } else if (error_response.error.code === AxiosError.ERR_NETWORK) {
                        // 予期しないネットワークエラーの場合
                        Message.error(`${template}\n予期しないネットワークエラーが発生しました。(${error_response.error.message})`);
                        if (!error_response.error.config?.url?.startsWith('/cdn-cgi/')){
                            (async ()=>{
                                const CFZTStore = useCFZTStore();
                                await CFZTStore.fetchCFZTIdentity();
                                const u = new URL(location.href);
                                if (u.searchParams.get('pwa') !== 'false' && !u.searchParams.get('__cf_access_message') && CFZTStore.is_CFZT && !CFZTStore.is_login) {
                                    console.log('Cloudflare ZeroTrust Login need!!');
                                    u.searchParams.set('pwa','false');
                                    location.href = u.href;
                                }
                            })();
                        }
                    } else {
                        // それ以外のエラーの場合
                        Message.error(`${template}(${error_response.error.message})`);
                    }
                } else {
                    // HTTP リクエスト自体は成功したが、API からエラーレスポンスが返ってきた場合
                    if (error_response.status === 502) {
                        Message.error(`${template}\n現在サーバーを起動/再起動しています。もうしばらくお待ちください。(HTTP Error 502)`);
                    } else if (error_response.data.detail !== undefined) {
                        Message.error(`${template}(HTTP Error ${error_response.status} / ${error_response.data.detail})`);
                    } else {
                        Message.error(`${template}(HTTP Error ${error_response.status} / ${error_response.error.message})`);
                    }
                }
                return;
            }
        }
    }
}

export default APIClient;
