
import Message from '@/message';
import APIClient from '@/services/APIClient';
import { IPostTweetResult, ITimelineTweetsResult, ITwitterAPIResult } from '@/services/Twitter';


/** Bluesky アカウントと App Password 認証で連携するためのリクエストを表すインターフェイス */
export interface IBlueskyAuthRequest {
    handle: string;
    app_password: string;
}

/** Bluesky 投稿への操作リクエストを表すインターフェイス */
export interface IBlueskyPostActionRequest {
    bluesky_uri: string;
    bluesky_cid?: string | null;
}


class Bluesky {

    /**
     * Bluesky アカウントと App Password で連携する
     * @param bluesky_auth_request Bluesky の handle と App Password
     * @returns ログインできた場合は true, 失敗した場合は false
     */
    static async auth(bluesky_auth_request: IBlueskyAuthRequest): Promise<boolean> {

        const response = await APIClient.post('/bluesky/auth', bluesky_auth_request, {
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky アカウントとの連携に失敗しました。');
            return false;
        }

        return true;
    }


    /**
     * 現在ログイン中のユーザーアカウントに紐づく Bluesky アカウントとの連携を解除する
     * @param handle Bluesky の handle
     * @returns 連携解除に成功した場合は true, 失敗した場合は false
     */
    static async logoutAccount(handle: string): Promise<boolean> {

        const response = await APIClient.delete(`/bluesky/accounts/${handle}`);

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky アカウントとの連携を解除できませんでした。');
            return false;
        }

        return true;
    }


    /**
     * Bluesky に投稿を送信する
     * @param handle Bluesky の handle
     * @param text 投稿本文
     * @param captures 添付するキャプチャ画像
     */
    static async sendPost(handle: string, text: string, captures: Blob[]): Promise<{message: string; is_error: boolean;}> {

        // FastAPI 側は multipart/form-data で本文と画像を受け取るため、Twitter 投稿と同じ Blob 配列をそのまま詰め替える
        const form_data = new FormData();
        form_data.append('post', text);
        for (const tweet_capture of captures) {
            form_data.append('images', tweet_capture);
        }

        // 画像変換やアップロードに時間がかかる場合があるため、通常の API より長めのタイムアウトにする
        const response = await APIClient.post<IPostTweetResult>(`/bluesky/accounts/${handle}/posts`, form_data, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            timeout: 10 * 60 * 1000,
        });

        if (response.type === 'error') {
            // 送信 UI は Promise を reject させず結果通知を並列に扱うため、HTTP エラーも戻り値へ正規化する
            if (typeof response.data.detail === 'string') {
                return {message: `Bluesky への投稿に失敗しました。(HTTP Error ${response.status} / ${response.data.detail})`, is_error: true};
            }
            return {message: `Bluesky への投稿に失敗しました。(HTTP Error ${response.status})`, is_error: true};
        }

        return {message: response.data.detail, is_error: response.data.is_success === false};
    }


    /**
     * Bluesky 投稿をリポストする
     * @param handle Bluesky の handle
     * @param action_request Bluesky 投稿への操作リクエスト
     * @returns リポストの実行結果
     */
    static async repost(handle: string, action_request: IBlueskyPostActionRequest): Promise<ITwitterAPIResult | null> {

        // リポスト実行はサーバー側で StrongRef の存在を検証するため、クライアントは共通の操作リクエストをそのまま送る
        const response = await APIClient.put<ITwitterAPIResult>(`/bluesky/accounts/${handle}/posts/repost`, action_request, {
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky 投稿をリポストできませんでした。');
            return null;
        }
        // API としては 200 でも Bluesky 側の操作失敗は is_success=false で返るため、画面通知に変換する
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }
        return response.data;
    }


    /**
     * Bluesky 投稿のリポストを取り消す
     * @param handle Bluesky の handle
     * @param action_request Bluesky 投稿への操作リクエスト
     * @returns リポスト取り消しの実行結果
     */
    static async cancelRepost(handle: string, action_request: IBlueskyPostActionRequest): Promise<ITwitterAPIResult | null> {

        // DELETE でも操作対象の URI が必要なので、Axios の data 経由でリクエスト本文を渡す
        const response = await APIClient.delete<ITwitterAPIResult>(`/bluesky/accounts/${handle}/posts/repost`, {
            data: action_request,
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky 投稿のリポストを取り消せませんでした。');
            return null;
        }
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }
        return response.data;
    }


    /**
     * Bluesky 投稿をいいねする
     * @param handle Bluesky の handle
     * @param action_request Bluesky 投稿への操作リクエスト
     * @returns いいねの実行結果
     */
    static async favorite(handle: string, action_request: IBlueskyPostActionRequest): Promise<ITwitterAPIResult | null> {

        // いいね実行もリポストと同じ StrongRef を使うため、共通のリクエスト型で扱う
        const response = await APIClient.put<ITwitterAPIResult>(`/bluesky/accounts/${handle}/posts/like`, action_request, {
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky 投稿をいいねできませんでした。');
            return null;
        }
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }
        return response.data;
    }


    /**
     * Bluesky 投稿のいいねを取り消す
     * @param handle Bluesky の handle
     * @param action_request Bluesky 投稿への操作リクエスト
     * @returns いいね取り消しの実行結果
     */
    static async cancelFavorite(handle: string, action_request: IBlueskyPostActionRequest): Promise<ITwitterAPIResult | null> {

        // いいね取り消しはサーバー側で viewer.like を引き直してから削除するため、クライアントからは URI だけでも送れる
        const response = await APIClient.delete<ITwitterAPIResult>(`/bluesky/accounts/${handle}/posts/like`, {
            data: action_request,
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky 投稿のいいねを取り消せませんでした。');
            return null;
        }
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }
        return response.data;
    }


    /**
     * Bluesky のホームタイムラインを取得する
     * @param handle Bluesky の handle
     * @param cursor_id 前回のレスポンスから取得した cursor
     * @returns タイムラインの投稿リスト
     */
    static async getHomeTimeline(handle: string, cursor_id?: string): Promise<ITimelineTweetsResult | null> {

        // Bluesky の cursor は一方向のページング値なので、Twitter 側とは別の cursor_id として呼び出し元で保持する
        const response = await APIClient.get<ITimelineTweetsResult>(`/bluesky/accounts/${handle}/timeline`, {
            params: { cursor_id },
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky のホームタイムラインを取得できませんでした。');
            return null;
        }
        // タイムライン系 API は成功時に Tweet リスト、失敗時に TwitterAPIResult が返る Union なので is_success の有無で判定する
        if ('is_success' in response.data && response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }
        return response.data;
    }


    /**
     * Bluesky 投稿を検索する
     * @param handle Bluesky の handle
     * @param query 検索クエリ
     * @param cursor_id 前回のレスポンスから取得した cursor
     * @returns 検索結果の投稿リスト
     */
    static async searchPosts(handle: string, query: string, cursor_id?: string): Promise<ITimelineTweetsResult | null> {

        // 検索語は Twitter 検索用の include:nativeretweets などを付けず、Bluesky 側の検索構文へ素直に渡す
        const response = await APIClient.get<ITimelineTweetsResult>(`/bluesky/accounts/${handle}/search`, {
            params: { query, cursor_id },
            timeout: 60 * 1000,
        });

        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Bluesky 投稿の検索に失敗しました。');
            return null;
        }
        if ('is_success' in response.data && response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }
        return response.data;
    }
}

export default Bluesky;
