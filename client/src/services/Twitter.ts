
import Message from '@/message';
import APIClient from '@/services/APIClient';
import useTwitterStore from '@/stores/TwitterStore';


/** Twitter アカウントと連携するための認証 URL を表すインターフェイス */
export interface ITwitterAuthURL {
    authorization_url: string;
}

/** Twitter アカウントとパスワード認証で連携するためのリクエストを表すインターフェイス */
export interface ITwitterPasswordAuthRequest {
    screen_name: string;
    password: string;
}

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

/** Twitter チャレンジデータを表すインターフェイス */
export interface ITwitterChallengeData extends ITwitterAPIResult {
    endpoint_infos: { [key: string]: ITwitterGraphQLAPIEndpointInfo };
    verification_code: string;
    challenge_js_code: string;
    vendor_js_code: string;
    challenge_animation_svg_codes: string[];
}

/** Twitter GraphQL API のエンドポイント情報を表すインターフェイス */
export interface ITwitterGraphQLAPIEndpointInfo {
    method: 'GET' | 'POST';
    query_id: string;
    endpoint: string;
    features: { [key: string]: any } | null;
    path: string;
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
     * Twitter アカウントと Cookie or パスワードログインで連携する
     * @param twitter_auth_request cookies.txt または スクリーンネーム&パスワード
     * @returns ログインできた場合は true, 失敗した場合は false
     */
    static async auth(twitter_auth_request: ITwitterPasswordAuthRequest | ITwitterCookieAuthRequest): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.post('/twitter/auth', twitter_auth_request);

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
     * Twitter Web App の API リクエスト内の X-Client-Transaction-ID ヘッダーを算出するために必要な Challenge 情報を取得する
     * @param screen_name Twitter のスクリーンネーム
     * @returns Challenge 情報
     */
    static async fetchChallengeData(screen_name: string): Promise<ITwitterChallengeData | null> {

        // API リクエストを実行
        const response = await APIClient.get<ITwitterChallengeData>(`/twitter/accounts/${screen_name}/challenge-data`);

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'Twitter の Challenge 情報を取得できませんでした。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        return response.data;
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

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'CreateTweet');

        // API リクエストを実行
        const response = await APIClient.post<IPostTweetResult>(`/twitter/accounts/${screen_name}/tweets`, form_data, {
            headers: {
                'Content-Type': 'multipart/form-data',
                'X-Client-Transaction-ID': x_client_transaction_id,
            },
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


    /**
     * ツイートをリツイートする
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id リツイートするツイートの ID
     * @returns リツイートの実行結果
     */
    static async retweet(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'CreateRetweet');

        // API リクエストを実行
        const response = await APIClient.put<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/retweet`, undefined, {
            headers: {'X-Client-Transaction-ID': x_client_transaction_id},
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'ツイートをリツイートできませんでした。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        return response.data;
    }


    /**
     * リツイートを取り消す
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id リツイートを取り消すツイートの ID
     * @returns リツイートの取り消し結果
     */
    static async cancelRetweet(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'DeleteRetweet');

        // API リクエストを実行
        const response = await APIClient.delete<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/retweet`, {
            headers: {'X-Client-Transaction-ID': x_client_transaction_id},
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'リツイートを取り消せませんでした。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        return response.data;
    }


    /**
     * ツイートをいいねする
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id いいねするツイートの ID
     * @returns いいねの実行結果
     */
    static async favorite(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'FavoriteTweet');

        // API リクエストを実行
        const response = await APIClient.put<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/favorite`, undefined, {
            headers: {'X-Client-Transaction-ID': x_client_transaction_id},
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'ツイートをいいねできませんでした。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        return response.data;
    }


    /**
     * いいねを取り消す
     * @param screen_name Twitter のスクリーンネーム
     * @param tweet_id いいねを取り消すツイートの ID
     * @returns いいねの取り消し結果
     */
    static async cancelFavorite(screen_name: string, tweet_id: string): Promise<ITwitterAPIResult | null> {

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'UnfavoriteTweet');

        // API リクエストを実行
        const response = await APIClient.delete<ITwitterAPIResult>(`/twitter/accounts/${screen_name}/tweets/${tweet_id}/favorite`, {
            headers: {'X-Client-Transaction-ID': x_client_transaction_id},
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'いいねを取り消せませんでした。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if (response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        return response.data;
    }


    /**
     * ホームタイムラインを取得する
     * @param screen_name Twitter のスクリーンネーム
     * @param cursor_id 前回のレスポンスから取得した、次のページを取得するためのカーソル ID
     * @returns タイムラインのツイートのリスト
     */
    static async getHomeTimeline(screen_name: string, cursor_id?: string): Promise<ITimelineTweetsResult | null> {

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'HomeLatestTimeline');

        // API リクエストを実行
        const response = await APIClient.get<ITimelineTweetsResult>(`/twitter/accounts/${screen_name}/timeline`, {
            params: { cursor_id },
            headers: {'X-Client-Transaction-ID': x_client_transaction_id},
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'ホームタイムラインを取得できませんでした。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if ('is_success' in response.data && response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

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

        // Twitter の GraphQL API へのリクエストに必要な X-Client-Transaction-ID ヘッダーを Challenge を解決することで算出する
        // X-Client-Transaction-ID を設定せずとも API 操作は可能だが、垢ロックやツイート失敗の確率が上がる
        const x_client_transaction_id = await useTwitterStore().solveChallenge(screen_name, 'SearchTimeline');

        // API リクエストを実行
        const response = await APIClient.get<ITimelineTweetsResult>(`/twitter/accounts/${screen_name}/search`, {
            params: { query, cursor_id },
            headers: {'X-Client-Transaction-ID': x_client_transaction_id},
        });

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                default:
                    APIClient.showGenericError(response, 'ツイートの検索に失敗しました。');
                    break;
            }
            return null;
        }

        // HTTP エラーではないが、実際には処理が失敗した場合
        if ('is_success' in response.data && response.data.is_success === false) {
            Message.error(response.data.detail);
            return null;
        }

        return response.data;
    }
}

export default Twitter;
