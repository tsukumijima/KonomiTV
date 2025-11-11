
import Message from '@/message';
import APIClient from '@/services/APIClient';
import useTwitterStore from '@/stores/TwitterStore';


/** Twitter アカウントと Cookie 認証で連携するためのリクエストを表すインターフェイス */
export interface ITwitterCookieAuthRequest {
    cookies_txt: string;
}

/** ツイートを表すインターフェイス */
export interface ITweet {
    id: string;
    created_at: Date;
    user: ITweetUser;
    text: string;
    lang: string;
    via: string;
    image_urls: string[] | null;
    movie_url: string | null;
    retweet_count: number;
    retweeted: boolean;
    favorite_count: number;
    favorited: boolean;
    retweeted_tweet: ITweet | null;
    quoted_tweet: ITweet | null;
}

/** ツイートのユーザーを表すインターフェイス */
export interface ITweetUser {
    id: string;
    name: string;
    screen_name: string;
    icon_url: string;
}

/** Twitter API の結果を表すインターフェイス */
export interface ITwitterAPIResult {
    is_success: boolean;
    detail: string;
}

/** ツイートの送信結果を表すインターフェイス */
export interface IPostTweetResult extends ITwitterAPIResult {
    tweet_url: string;
}

/** タイムラインのツイート取得結果を表すインターフェイス */
export interface ITimelineTweetsResult extends ITwitterAPIResult {
    next_cursor_id: string;
    previous_cursor_id: string;
    tweets: ITweet[];
}


class Twitter {

    /**
     * Twitter アカウントと Cookie ログインで連携する
     * @param twitter_auth_request Netscape 形式の Cookie ファイルの内容を格納した文字列
     * @returns ログインできた場合は true, 失敗した場合は false
     */
    static async auth(twitter_auth_request: ITwitterCookieAuthRequest): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/twitter/auth', twitter_auth_request);

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'No valid cookies found in the provided cookies.txt': {
                    Message.error('Cookie データのフォーマットが不正です。Netscape 形式の Cookie データを入力してください。');
                    break;
                }
                case 'Failed to get user information': {
                    Message.error('Twitter アカウント情報の取得に失敗しました。');
                    break;
                }
                default: {
                    APIClient.showGenericError(response, 'Twitter アカウントとの連携に失敗しました。');
                    break;
                }
            }
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
     * KonomiTV サーバー内部で起動しているヘッドレスブラウザのシャットダウンを遅らせる
     * @param screen_name Twitter のスクリーンネーム
     */
    static async keepAlive(screen_name: string): Promise<void> {

        // API リクエストを実行
        const response = await APIClient.post(`/twitter/accounts/${screen_name}/keep-alive`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ヘッドレスブラウザへの Keep-Alive 送信に失敗しました。');
            return;
        }

        Twitter.recordAccountActivity(screen_name);
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
        const response = await APIClient.post<IPostTweetResult>(`/twitter/accounts/${screen_name}/tweets`, form_data, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            // 連投間隔によってはツイート送信に時間がかかるため、
            // タイムアウトを 10 分に設定
            timeout: 10 * 60 * 1000,
        });

        // エラー処理 (API リクエスト自体に失敗した場合)
        // このエンドポイントのみ、Message (SnackBar) では通知せず、通知をプレイヤー側に委ねる必要がある
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
            Twitter.recordAccountActivity(screen_name);
            return {message: response.data.detail, is_error: false};
        }
    }


    /**
     * ツイートをリツイートする
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id リツイートするツイートの ID
     * @returns リツイートの実行結果
     */
    static async retweet(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // API リクエストを実行
        const response = await APIClient.put<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/retweet`, undefined);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ツイートをリツイートできませんでした。');
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        Twitter.recordAccountActivity(screen_name);
        return response.data;
    }


    /**
     * リツイートを取り消す
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id リツイートを取り消すツイートの ID
     * @returns リツイートの取り消し結果
     */
    static async cancelRetweet(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // API リクエストを実行
        const response = await APIClient.delete<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/retweet`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'リツイートを取り消せませんでした。');
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        Twitter.recordAccountActivity(screen_name);
        return response.data;
    }


    /**
     * ツイートをいいねする
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id いいねするツイートの ID
     * @returns いいねの実行結果
     */
    static async favorite(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // API リクエストを実行
        const response = await APIClient.put<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/favorite`, undefined);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ツイートをいいねできませんでした。');
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        Twitter.recordAccountActivity(screen_name);
        return response.data;
    }


    /**
     * いいねを取り消す
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id いいねを取り消すツイートの ID
     * @returns いいねの取り消し結果
     */
    static async cancelFavorite(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // API リクエストを実行
        const response = await APIClient.delete<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/favorite`);

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'いいねを取り消せませんでした。');
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        Twitter.recordAccountActivity(screen_name);
        return response.data;
    }


    /**
     * ホームタイムラインを取得する
     * @param screen_name Twitter のスクリーンネーム
     * @param cursor_id 前回のレスポンスから取得した、次のページを取得するためのカーソル ID
     * @returns タイムラインのツイートのリスト
     */
    static async getHomeTimeline(screen_name: string, cursor_id?: string): Promise<ITimelineTweetsResult | null> {

        // API リクエストを実行
        const response = await APIClient.get<ITimelineTweetsResult>(`/twitter/accounts/${screen_name}/timeline`, {
            params: { cursor_id },
        });

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ホームタイムラインを取得できませんでした。');
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if ('is_success' in response.data && response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        Twitter.recordAccountActivity(screen_name);
        return response.data;
    }


    /**
     * ツイートを検索する
     * @param screen_name Twitter のスクリーンネーム
     * @param query 検索クエリ
     * @param cursor_id 前回のレスポンスから取得した、次のページを取得するためのカーソル ID
     * @returns 検索結果のツイートのリスト
     */
    static async searchTweets(screen_name: string, query: string, cursor_id?: string): Promise<ITimelineTweetsResult | null> {

        // API リクエストを実行
        const response = await APIClient.get<ITimelineTweetsResult>(`/twitter/accounts/${screen_name}/search`, {
            params: { query, cursor_id },
        });

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ツイートの検索に失敗しました。');
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if ('is_success' in response.data && response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        Twitter.recordAccountActivity(screen_name);
        return response.data;
    }


    /**
     * 指定したスクリーンネームのアカウントで API 呼び出しが行われたことを記録する
     * @param screen_name Twitter のスクリーンネーム
     */
    private static recordAccountActivity(screen_name: string): void {
        if (screen_name === '') {
            return;
        }
        const twitterStore = useTwitterStore();
        twitterStore.markAccountAPIActivity(screen_name);
    }
}

export default Twitter;
