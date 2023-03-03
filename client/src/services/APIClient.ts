
/**
 * services/ 以下の各クラスは、KonomiTV サーバーへの API リクエストを抽象化し、
 * API レスポンスの受け取りと、エラーが発生した際のエラーハンドリング (エラーメッセージ表示) までを責務として負う
 */

import { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios';

import Message from '@/message';
import axios from '@/plugins/axios';


/** API のエラーレスポンスを表すインターフェイス */
export interface IError {
    detail: string;
}

/** API リクエスト成功時のレスポンスを表すインターフェイス */
export type SuccessResponse<T> = {
    status: number;
    data: T;
    error: null;
    is_success: true;
}

/** API リクエスト失敗時のレスポンスを表すインターフェイス */
export type ErrorResponse<T extends Error = Error> = {
    status: number;
    data: null;
    error: T;
    is_error: true;
}


/**
 * services/ 以下の各クラスから呼び出される、Axios の薄いラッパー
 * エラーハンドリングを容易にするために、レスポンスを SuccessResponse と ErrorResponse に分けて返す
 * ref: https://zenn.dev/engineer_titan/articles/291c9fccb338e2
 */
class APIClient {

    /**
     * Axios で HTTP リクエストを送信し、レスポンスを受け取る
     * @param request AxiosRequestConfig
     * @returns 成功なら SuccessResponse 、失敗なら ErrorResponse を返す
     */
    static async request<T>(request: AxiosRequestConfig): Promise<SuccessResponse<T> | ErrorResponse> {

        // Axios で HTTP リクエストを送信し、レスポンスを受け取る
        const result: AxiosResponse<T> | AxiosError<IError> = await axios.request(request).catch((error: AxiosError<IError>) => error);

        // エラーが発生した場合は ErrorResponse を返す
        if (result instanceof AxiosError<IError>) {
            console.error(result);

            // エラーレスポンスがあれば、エラー内容を取得して返す
            if (result.response) {
                return {
                    status: result.response.status,
                    data: null,
                    error: new Error(result.response.data.detail),
                    is_error: true,
                }

            // エラーレスポンスがない場合は、AxiosError をそのまま返す
            } else {
                return {
                    status: NaN,
                    data: null,
                    error: result,
                    is_error: true,
                };
            }

        // 正常にレスポンスが返ってきた場合は SuccessResponse を返す
        } else {
            return {
                status: result.status,
                data: result.data,
                error: null,
                is_success: true,
            };
        }
    }


    /**
     * GET リクエストを送信する
     * @param url リクエスト先の URL
     * @returns 成功なら SuccessResponse 、失敗なら ErrorResponse を返す
     */
    static async get<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<SuccessResponse<T> | ErrorResponse> {
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
     * @returns 成功なら SuccessResponse 、失敗なら ErrorResponse を返す
     */
    static async post<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<SuccessResponse<T> | ErrorResponse> {
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
     * @returns 成功なら SuccessResponse 、失敗なら ErrorResponse を返す
     */
    static async put<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<SuccessResponse<T> | ErrorResponse> {
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
     * @returns 成功なら SuccessResponse 、失敗なら ErrorResponse を返す
     */
    static async delete<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<SuccessResponse<T> | ErrorResponse> {
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
     * @param response API から返されたエラーレスポンス
     * @param template エラーメッセージのテンプレート（「アカウント情報を取得できませんでした。」など)
     */
    static showGenericError(response: ErrorResponse, template: string): void {
        switch (response.error.message) {
            case 'Access token data is invalid': {
                Message.error(`${template}\nログインセッションが不正です。もう一度ログインしてください。`);
                return;
            }
            case 'Access token is invalid': {
                Message.error(`${template}\nログインセッションの有効期限が切れています。もう一度ログインしてください。`);
                return;
            }
            case 'User associated with access token does not exist': {
                Message.error(`${template}\nログインセッションに紐づくユーザーが存在しないか、削除されています。`);
                return;
            }
            default: {
                if (response.error.message) {
                    Message.error(`${template}(HTTP Error ${response.status} / ${response.error.message})`);
                } else {
                    Message.error(`${template}(HTTP Error ${response.status})`);
                }
                return;
            }
        }
    }
}

export default APIClient;
