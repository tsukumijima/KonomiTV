
import { defineStore } from 'pinia';

import Message from '@/message';
import Users, { IUser, IUserUpdateRequest } from '@/services/Users';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';


/**
 * 現在ログイン中のユーザーアカウントの情報を共有するストア
 */
const useUserStore = defineStore('user', {
    state: () => ({

        // 現在ログイン中かどうか
        is_logged_in: false as boolean,

        // ログイン済みのユーザーの情報
        user: null as IUser | null,

        // ログイン済みのユーザーのアイコン画像の Blob URL
        user_icon_url: null as string | null,
    }),
    getters: {

        /**
         * ログイン済みのユーザーのニコニコアカウントのユーザーアイコンの URL (ニコニコアカウントと連携されている場合のみ)
         */
        user_niconico_icon_url(): string | null {
            if (this.user === null || this.user.niconico_user_id === null) {
                return null;
            }
            const user_id_slice = this.user.niconico_user_id.toString().slice(0, 4);
            return `https://secure-dcdn.cdn.nimg.jp/nicoaccount/usericon/${user_id_slice}/${this.user.niconico_user_id}.jpg`;
        }
    },
    actions: {

        /**
         * アカウントを作成する
         * @param username ユーザー名
         * @param password パスワード
         * @returns アカウント作成に成功した場合は true
         */
        async register(username: string, password: string): Promise<boolean> {

            // アカウントを作成
            const result = await Users.createUser({username, password});
            if (result === null) {
                console.log('Register failed.');
                return false;  // アカウント作成失敗 (エラーハンドリングは services 層で行われる)
            }

            // 作成したアカウントでログイン
            await this.login(username, password, true);
            console.log('Register successful.');
            Message.success('アカウントを作成しました。');
            return true;
        },

        /**
         * ログイン処理を行う
         * @param username ユーザー名
         * @param password パスワード
         * @param silent ログインしたことをメッセージで通知しない場合は true
         * @returns ログインに成功した場合は true
         */
        async login(username: string, password: string, silent: boolean = false): Promise<boolean> {

            // アクセストークンを発行
            const access_token = await Users.createUserAccessToken(username, password);
            if (access_token === null) {
                console.log('Login failed.');
                this.logout(true);
                return false;  // ログイン失敗 (エラーハンドリングは services 層で行われる)
            }

            // 取得したアクセストークンを保存
            console.log('Login successful.');
            Utils.saveAccessToken(access_token.access_token);
            this.is_logged_in = true;

            // ユーザーアカウントの情報を取得
            await this.fetchUser(true);

            if (silent === false) {
                Message.success('ログインしました。');
            }

            return true;
        },

        /**
         * ログアウト処理を行う
         * @param silent ログアウトしたことをメッセージで通知しない場合は true
         */
        logout(silent: boolean = false): void {

            // 設定の同期を無効化
            const settings_store = useSettingsStore();
            settings_store.settings.sync_settings = false;

            // ブラウザからアクセストークンを削除
            // これをもってログアウトしたことになる（それ以降の Axios のリクエストにはアクセストークンが含まれなくなる）
            Utils.deleteAccessToken();

            // 未ログイン状態に設定
            this.is_logged_in = false;
            this.user = null;
            this.user_icon_url = '';

            if (silent === false) {
                Message.success('ログアウトしました。');
            }
        },

        /**
         * 現在ログイン中のユーザーアカウントの情報を取得する
         * すでに取得済みの情報がある場合は API リクエストを行わずにそれを返す
         * @param force 強制的に API リクエストを行う場合は true
         * @returns ログイン中のユーザーアカウントの情報 or ログインしていない場合は null
         */
        async fetchUser(force: boolean = false): Promise<IUser | null> {

            // LocalStorage にアクセストークンが保存されていない場合 (= 非ログイン状態) は常に null を返す
            if (Utils.getAccessToken() === null) {
                return null;
            }

            // すでにログイン済みのユーザーアカウントの情報がある場合はそれを返す
            // force が true の場合は無視される
            if (this.user !== null && force === false) {
                return this.user;
            }

            // ユーザーアカウントの情報を取得する
            const user = await Users.fetchUser();
            if (user === null) {
                // この時点で無効などの理由でアクセストークンが削除されている場合、ログアウトする
                if (Utils.getAccessToken() === null) {
                    this.logout(true);
                }
                return null;
            }
            this.is_logged_in = true;
            this.user = user;

            // ユーザーアカウントのアイコン画像の Blob URL を取得する
            const user_icon_url = await Users.fetchUserIcon();
            if (user_icon_url === null) {
                return null;
            }
            this.user_icon_url = user_icon_url;

            return this.user;
        },

        /**
         * 現在ログイン中のユーザーアカウントの情報を更新する
         * @param user_update_request ユーザー名 or パスワード
         */
        async updateUser(user_update_request: IUserUpdateRequest): Promise<void> {

            // ユーザーアカウントの情報を更新する
            const result = await Users.updateUser(user_update_request);
            if (result === false) {
                console.log('Update user failed.');
                return;  // 更新失敗 (エラーハンドリングは services 層で行われる)
            }

            // ユーザーアカウントの情報を再取得する
            await this.fetchUser(true);

            if (user_update_request.username !== undefined) {
                Message.show('ユーザー名を更新しました。');
            } else if (user_update_request.password !== undefined) {
                Message.show('パスワードを更新しました。');
            }
        },

        /**
         * 現在ログイン中のユーザーアカウントのアイコン画像を更新する
         * @param icon アイコンの File オブジェクト
         */
        async updateUserIcon(icon: File): Promise<void> {

            // ユーザーアカウントのアイコン画像を更新する
            await Users.updateUserIcon(icon);

            // ユーザーアカウントの情報を再取得する
            await this.fetchUser(true);

            Message.show('アイコン画像を更新しました。');
        },

        /**
         * 現在ログイン中のユーザーアカウントを削除する
         */
        async deleteUser(): Promise<void> {

            // ユーザーアカウントを削除する
            await Users.deleteUser();

            // ログアウトする
            this.logout(true);

            Message.show('アカウントを削除しました。');
        }
    }
});

export default useUserStore;
