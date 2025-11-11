
import { defineStore } from 'pinia';

import { ITwitterAccount } from '@/services/Users';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';


/**
 * アプリケーション全体で共有される Twitter 関連の状態を保存するストア
 */
const useTwitterStore = defineStore('twitter', {
    state: () => ({

        // Twitter アカウントを1つでも連携しているかどうか
        is_logged_in_twitter: false,

        // 現在ツイート対象として選択されている Twitter アカウント
        selected_twitter_account: null as ITwitterAccount | null,

        // 各アカウントごとに API 呼び出しが行われたかどうかを管理するオブジェクト
        // キーは Twitter アカウントのスクリーンネーム、値は API 呼び出しが行われたかどうかを表す真偽値
        account_api_activity: {} as Record<string, boolean>,
    }),
    actions: {

        /**
         * ストアが持つ状態を一括更新する
         */
        async update(): Promise<void> {
            const user_store = useUserStore();
            const settings_store = useSettingsStore();

            // まずはログイン中のユーザーの情報を取得する
            const user = await user_store.fetchUser();
            if (user === null) return;

            // ログイン時のみ
            if (user_store.is_logged_in === true) {

                // 連携している Twitter アカウントが一つでもあれば is_logged_in_twitter を true に設定
                if (user_store.user && user_store.user.twitter_accounts.length > 0) {
                    this.is_logged_in_twitter = true;

                    // 現在ツイート対象として選択されている Twitter アカウントの ID が設定されていない or ID に紐づく Twitter アカウントがないとき
                    // 連携している Twitter アカウントのうち、一番最初のものを自動選択する
                    // ここで言う Twitter アカウントの ID は DB 上で連番で振られるもので、Twitter アカウントそのものの固有 ID ではない
                    if (settings_store.settings.selected_twitter_account_id === null ||
                        !user_store.user.twitter_accounts.some((twitter_account) => {
                            return twitter_account.id === settings_store.settings.selected_twitter_account_id;
                        })) {
                        settings_store.settings.selected_twitter_account_id = user_store.user.twitter_accounts[0].id;
                    }

                    // 現在ツイート対象として選択されている Twitter アカウントを取得・設定
                    const twitter_account_index = user_store.user.twitter_accounts.findIndex((twitter_account) => {
                        // Twitter アカウントの ID が選択されているものと一致する
                        return twitter_account.id === settings_store.settings.selected_twitter_account_id;
                    });
                    this.selected_twitter_account = user_store.user.twitter_accounts[twitter_account_index];

                    // 選択されている Twitter アカウントがあればその API 活動フラグをリセット
                    if (this.selected_twitter_account) {
                        this.resetAccountAPIActivity(this.selected_twitter_account.screen_name);
                    }
                }
            } else {
                this.is_logged_in_twitter = false;
                this.selected_twitter_account = null;
                this.account_api_activity = {};
            }
        },

        /**
         * 指定したスクリーンネームのアカウントに紐づく API 呼び出しフラグを立てる
         * @param screen_name Twitter のスクリーンネーム
         */
        markAccountAPIActivity(screen_name: string): void {
            if (screen_name === '') {
                return;
            }
            this.account_api_activity = {
                ...this.account_api_activity,
                [screen_name]: true,
            };
        },

        /**
         * 指定したスクリーンネームのアカウントに紐づく API 呼び出しフラグをリセットする
         * @param screen_name Twitter のスクリーンネーム
         */
        resetAccountAPIActivity(screen_name: string): void {
            if (screen_name === '') {
                return;
            }
            this.account_api_activity = {
                ...this.account_api_activity,
                [screen_name]: false,
            };
        },
    }
});

export default useTwitterStore;
