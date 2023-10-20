
import APIClient from '@/services/APIClient';


/** ニコニコアカウントと連携するための認証 URL を表すインターフェイス */
export interface INiconicoAuthURL {
    authorization_url: string;
}


class Niconico {

    /**
     * ニコニコアカウントと連携するための認証 URL を取得する
     * @returns 認証 URL or 認証 URL の取得に失敗した場合は null
     */
    static async fetchAuthorizationURL(): Promise<string | null> {

        // API リクエストを実行
        const response = await APIClient.get<INiconicoAuthURL>('/niconico/auth');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ニコニコアカウントとの連携用の認証 URL を取得できませんでした。');
            return null;
        }

        return response.data.authorization_url;
    }


    /**
     * 現在ログイン中のユーザーアカウントに紐づくニコニコアカウントとの連携を解除する
     * @returns 連携解除に成功した場合は true, 失敗した場合は false
     */
    static async logoutAccount(): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.delete('/niconico/logout');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'ニコニコアカウントとの連携を解除できませんでした。');
            return false;
        }

        return true;
    }
}

export default Niconico;
