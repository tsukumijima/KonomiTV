
import Message from '@/message';
import APIClient from '@/services/APIClient';


/** Twitter アカウントと連携するための認証 URL を表すインターフェイス */
export interface ITwitterAuthURL {
    authorization_url: string;
}

/** ツイートの送信結果を表すインターフェイス */
export interface ITweetResult {
    is_success: boolean;
    tweet_url?: string;
    detail: string;
}

export interface ITwitterPasswordAuthRequest {
    screen_name: string;
    password: string;
}


class Twitter {

    /**
     * Twitter アカウントと連携するための認証 URL を取得する
     * @returns 認証 URL or 認証 URL の取得に失敗した場合は null
     */
    static async fetchAuthorizationURL(): Promise<string | null> {

        // API リクエストを実行
        const response = await APIClient.get<ITwitterAuthURL>('/twitter/auth');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Twitter アカウントとの連携用の認証 URL を取得できませんでした。');
            return null;
        }

        return response.data.authorization_url;
    }


    /**
     * Twitter アカウントとパスワード認証で連携する
     * @param twitter_password_auth_request スクリーンネームとパスワード
     * @returns ログインできた場合は true, 失敗した場合は false
     */
    static async authWithPassword(twitter_password_auth_request: ITwitterPasswordAuthRequest): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/twitter/password-auth', twitter_password_auth_request);

        // エラー処理
        if (response.type === 'error') {
            if (typeof response.data.detail === 'string') {
                if (response.data.detail.startsWith('Failed to authenticate with password')) {
                    const error = response.data.detail.match(/Message: (.+)\)/)![1];
                    Message.error(`ログインに失敗しました。${error}`);
                    return false;
                } else if (response.data.detail.startsWith('Unexpected error occurred while authenticate with password')) {
                    const error = response.data.detail.match(/Message: (.+)\)/)![1];
                    Message.error(`ログインフローの途中で予期せぬエラーが発生しました。${error}`);
                    return false;
                } else if (response.data.detail.startsWith('Failed to get user information')) {
                    Message.error('Twitter アカウントのユーザー情報の取得に失敗しました。');
                    return false;
                }
            }
            // 上記以外のエラー
            APIClient.showGenericError(response, 'Twitter アカウントとの連携に失敗しました。');
            return false;
        }

        return true;
    }


    /**
     * 現在ログイン中のユーザーアカウントに紐づく Twitter アカウントとの連携を解除する
     * @param screen_name Twitter のスクリーンネーム
     * @returns 連携解除に成功した場合は true, 失敗した場合は false
     */
    static async logoutAccount(screen_name: string): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.delete(`/twitter/accounts/${screen_name}`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'Twitter アカウントとの連携を解除できませんでした。');
            return false;
        }

        return true;
    }


    /**
     * ツイートを送信する
     * @param screen_name Twitter のスクリーンネーム
     * @param text ツイート本文
     * @param captures 添付するキャプチャ画像
     */
    static async sendTweet(screen_name: string, text: string, captures: Blob[]): Promise<{message: string; is_error: boolean;}> {

        // multipart/form-data でツイート本文と画像（選択されている場合）を送る
        const form_data = new FormData();
        form_data.append('tweet', text);
        for (const tweet_capture of captures) {
            form_data.append('images', tweet_capture);
        }

        // API リクエストを実行
        const response = await APIClient.post<ITweetResult>(`/twitter/accounts/${screen_name}/tweets`, form_data, {
            headers: {'Content-Type': 'multipart/form-data'},
            // 連投間隔によってはツイート送信に時間がかかるため、
            // タイムアウトを 10 分に設定
            timeout: 10 * 60 * 1000,
        });

        // エラー処理 (API リクエスト自体に失敗した場合)
        if (response.type === 'error') {
            if (typeof response.data.detail === 'string') {
                if (Number.isNaN(response.status)) {
                    // HTTP リクエスト自体が失敗し、HTTP ステータスコードが取得できなかった場合
                    return {message: `ツイートの送信に失敗しました。(${response.data.detail})`, is_error: true};
                } else {
                    // HTTP リクエスト自体は成功したが、API からエラーレスポンスが返ってきた場合
                    return {message: `ツイートの送信に失敗しました。(HTTP Error ${response.status} / ${response.data.detail})`, is_error: true};
                }
            } else {
                return {message: `ツイートの送信に失敗しました。(HTTP Error ${response.status})`, is_error: true};
            }
        }

        // 成功 or 失敗に関わらず detail の内容をそのまま通知する
        if (response.data.is_success === false) {
            // ツイート失敗
            return {message: response.data.detail, is_error: true};
        } else {
            // ツイート成功
            return {message: response.data.detail, is_error: false};
        }
    }
}

export default Twitter;
