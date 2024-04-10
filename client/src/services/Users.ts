
import Message from '@/message';
import APIClient from '@/services/APIClient';


/** ユーザーアカウントの情報を表すインターフェイス */
export interface IUser {
    id: number;
    name: string;
    is_admin: boolean;
    niconico_user_id: number | null;
    niconico_user_name: string | null;
    niconico_user_premium: boolean | null;
    twitter_accounts: ITwitterAccount[];
    created_at: string;
    updated_at: string;
}

/** ユーザーアカウントに紐づく Twitter アカウントの情報を表すインターフェイス */
export interface ITwitterAccount {
    id: number;
    name: string;
    screen_name: string;
    icon_url: string;
    created_at: string;
    updated_at: string;
}

/** ユーザーアカウントのアクセストークンを表すインターフェイス */
export interface IUserAccessToken {
    access_token: string;
    token_type: string;
}

export interface IUserCreateRequest {
    username: string;
    password: string;
}
export interface IUserUpdateRequest {
    username?: string;
    password?: string;
}
export interface IUserUpdateRequestForAdmin {
    username?: string;
    password?: string;
    is_admin?: boolean;
}


class Users {

    /**
     * ユーザーアカウントを作成する
     * @param user_create_request ユーザー名とパスワード
     * @returns 作成したユーザーアカウントの情報 or アカウント作成に失敗した場合は null
     */
    static async createUser(user_create_request: IUserCreateRequest): Promise<IUser | null> {

        // API リクエストを実行
        const response = await APIClient.post<IUser>('/users', user_create_request);

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'Specified username is duplicated': {
                    Message.error('ユーザー名が重複しています。');
                    break;
                }
                case 'Specified username is not accepted due to system limitations': {
                    Message.error('ユーザー名に token と me は使えません。');
                    break;
                }
                default: {
                    APIClient.showGenericError(response, 'アカウントを作成できませんでした。');
                    break;
                }
            }
            return null;
        }

        return response.data;
    }


    /**
     * ユーザーアカウントのアクセストークンを発行する
     * @param username ユーザー名
     * @param password パスワード
     * @returns 発行したアクセストークン or ログインに失敗した場合は null
     */
    static async createUserAccessToken(username: string, password: string): Promise<IUserAccessToken | null> {

        // API リクエストを実行
        const response = await APIClient.post<IUserAccessToken>('/users/token', new URLSearchParams({username, password}));

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'Incorrect username': {
                    Message.error('ログインできませんでした。そのユーザー名のアカウントは存在しません。');
                    break;
                }
                case 'Incorrect password': {
                    Message.error('ログインできませんでした。パスワードを間違えていませんか？');
                    break;
                }
                default: {
                    APIClient.showGenericError(response, 'ログインできませんでした。');
                    break;
                }
            }
            return null;
        }

        return response.data;
    }


    /**
     * 現在ログイン中のユーザーアカウントの情報を取得する
     * @returns ログイン中のユーザーアカウントの情報 or ログインしていない場合は null
     */
    static async fetchUser(): Promise<IUser | null> {

        // API リクエストを実行
        const response = await APIClient.get<IUser>('/users/me');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'アカウント情報を取得できませんでした。');
            return null;
        }

        return response.data;
    }


    /**
     * 現在ログイン中のユーザーアカウントのアイコンを取得する
     * @returns ログイン中のユーザーアカウントのアイコンの Blob URL or ログインしていない場合は null
     */
    static async fetchUserIcon(): Promise<string | null> {

        // API リクエストを実行
        const response = await APIClient.get('/users/me/icon', {responseType: 'blob'});

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'アイコン画像を取得できませんでした。');
            return null;
        }

        return URL.createObjectURL(response.data);
    }


    /**
     * 現在ログイン中のユーザーアカウントの情報を更新する
     * @param user_update_request ユーザー名 or パスワード
     * @returns 更新に成功した場合は true
     */
    static async updateUser(user_update_request: IUserUpdateRequest): Promise<boolean> {

        // API リクエストを実行
        const response = await APIClient.put('/users/me', user_update_request);

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'Specified username is duplicated': {
                    Message.error('ユーザー名が重複しています。');
                    break;
                }
                case 'Specified username is not accepted due to system limitations': {
                    Message.error('ユーザー名に token と me は使えません。');
                    break;
                }
                default: {
                    APIClient.showGenericError(response, 'アカウント情報を更新できませんでした。');
                    break;
                }
            }
            return false;
        }

        return true;
    }


    /**
     * 現在ログイン中のユーザーアカウントのアイコン画像を更新する
     * @param icon アイコンの File オブジェクト
     */
    static async updateUserIcon(icon: File): Promise<void> {

        // アイコン画像の File オブジェクト (= Blob) を FormData に入れる
        // multipart/form-data で送るために必要
        // ref: https://r17n.page/2020/02/04/nodejs-axios-file-upload-api/
        const form_data = new FormData();
        form_data.append('image', icon);

        // API リクエストを実行
        const response = await APIClient.put('/users/me/icon', form_data, {headers: {'Content-Type': 'multipart/form-data'}});

        // エラー処理
        if (response.type === 'error') {
            switch (response.data.detail) {
                case 'Please upload JPEG or PNG image': {
                    Message.error('JPEG または PNG 画像をアップロードしてください。');
                    break;
                }
                default: {
                    APIClient.showGenericError(response, 'アイコン画像を更新できませんでした。');
                    break;
                }
            }
            return;
        }
    }


    /**
     * 現在ログイン中のユーザーアカウントを削除する
     */
    static async deleteUser(): Promise<void> {

        // API リクエストを実行
        const response = await APIClient.delete('/users/me');

        // エラー処理
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'アカウントを削除できませんでした。');
            return;
        }
    }
}

export default Users;
