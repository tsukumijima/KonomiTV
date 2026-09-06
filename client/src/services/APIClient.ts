
/**
 * services/ 直下の各クラスは、KonomiTV サーバーへの API リクエストを抽象化し、
 * API レスポンスの受け取りと、エラーが発生した際のエラーハンドリング (エラーメッセージ表示) までを責務として負う
 */

import axios, { AxiosError, AxiosRequestConfig, AxiosResponse, AxiosResponseHeaders, RawAxiosResponseHeaders } from 'axios';

import Message from '@/message';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';


// 前段の認証プロキシへトップレベルナビゲーションを到達させる間だけ付与するクエリパラメータ
// client/src/sw.ts 側でも同じ値を NavigationRoute の除外判定に使用している
const UPSTREAM_AUTHENTICATION_BYPASS_QUERY_PARAMETER = '__konomitv_auth_bypass';


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

    // 同時に失敗した複数の API リクエストが、それぞれ同じトップレベルナビゲーションを開始しないようにする
    private static is_upstream_authentication_redirecting = false;


    /**
     * レスポンス本文が KonomiTV API の標準エラー形式かどうかを判定する
     * @param data レスポンス本文
     * @returns KonomiTV API の標準エラー形式なら true
     */
    private static isKonomiTVErrorResponseData(data: unknown): data is IErrorResponseData {
        return typeof data === 'object' && data !== null && 'detail' in data;
    }


    /**
     * 前段の認証プロキシへ再認証を要求するため、現在の URL を一度だけ Service Worker の外へ送る
     */
    private static redirectToUpstreamAuthentication(): void {
        const current_url = new URL(window.location.href);

        // 最初の API リクエストですでに再認証のためのナビゲーションを開始していれば、後続の失敗では何もしない
        if (APIClient.is_upstream_authentication_redirecting) {
            return;
        }

        // すでに Service Worker を迂回しても認証できなかった場合は、無限リロードを避けて通常のエラー処理へ戻す
        if (current_url.searchParams.get(UPSTREAM_AUTHENTICATION_BYPASS_QUERY_PARAMETER) === '1') {
            return;
        }

        // 現在のパス・クエリ・ハッシュを維持したまま、一時パラメータを付けてトップレベルナビゲーションを行う
        // この URL だけは Service Worker の NavigationRoute から除外され、Cloudflare Access などの前段認証へ到達する
        APIClient.is_upstream_authentication_redirecting = true;
        current_url.searchParams.set(UPSTREAM_AUTHENTICATION_BYPASS_QUERY_PARAMETER, '1');
        window.location.replace(current_url.href);
    }


    /**
     * 前段認証から正常に復帰した後、アドレスバーから一時的な Service Worker 迂回パラメータを取り除く
     */
    private static clearUpstreamAuthenticationBypass(): void {
        const current_url = new URL(window.location.href);
        if (current_url.searchParams.get(UPSTREAM_AUTHENTICATION_BYPASS_QUERY_PARAMETER) !== '1') {
            return;
        }

        // ページを再読み込みせず URL だけを置き換え、以後の通常ナビゲーションでは従来どおり app shell を利用する
        current_url.searchParams.delete(UPSTREAM_AUTHENTICATION_BYPASS_QUERY_PARAMETER);
        window.history.replaceState(window.history.state, '', current_url.href);
    }

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
        const is_konomitv_api_request = request.url?.startsWith('http') === false;
        if (is_konomitv_api_request) {

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

            // Cloudflare Access などの前段認証が失効した際、ログイン HTML へのリダイレクトではなく
            // クライアント側で検知可能な 401 Unauthorized を返してもらう
            request.headers['X-Requested-With'] = 'XMLHttpRequest';
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

                // KonomiTV API の形式ではない 401 は Cloudflare Access など前段認証の失効とみなし、
                // Service Worker を一度だけ迂回するトップレベルナビゲーションで再認証を開始する
                if (is_konomitv_api_request && result.response.status === 401 &&
                    APIClient.isKonomiTVErrorResponseData(result.response.data) === false) {
                    APIClient.redirectToUpstreamAuthentication();
                }
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

            // 一時パラメータは、前段認証を通過して KonomiTV API から正常な応答を得られた時点でのみ削除する
            // それまでは残すことで、前段が 401 を返し続ける場合の無限リロードを防ぐ
            if (is_konomitv_api_request) {
                APIClient.clearUpstreamAuthenticationBypass();
            }
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

        // ブラウザが明確にオフラインと判定した通信失敗では、サーバーが応答したエラーだけを利用者通知の対象にする
        // navigator.onLine が true でもサーバーへ到達できる保証はないため、オンライン扱いのエラーは従来どおり表示する
        if (Number.isNaN(error_response.status) && navigator.onLine === false) {
            return;
        }
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
