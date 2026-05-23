
import { defineStore } from 'pinia';

import { IAccountLink, IBlueskyAccount, ISelectableAccount, ITwitterAccount } from '@/services/Users';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';


/**
 * アプリケーション全体で共有される Twitter 関連の状態を保存するストア
 */
const useTwitterStore = defineStore('twitter', {
    state: () => ({

        // Twitter アカウントを1つでも連携しているかどうか
        is_logged_in_twitter: false,

        // Twitter タブで利用できる Twitter / Bluesky / 紐付け済みアカウントの一覧
        selectable_accounts: [] as ISelectableAccount[],

        // 現在 Twitter タブで選択されているアカウント
        selected_account: null as ISelectableAccount | null,

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

            // まずはログイン中のユーザーの情報を取得する
            const user = await user_store.fetchUser();
            if (user === null) return;

            // ログイン時のみ
            if (user_store.is_logged_in === true) {

                // UserAPI で取得した個別アカウントと紐付けを、Twitter タブの選択単位に変換する
                const selectable_accounts = this.buildSelectableAccounts(
                    user_store.user?.twitter_accounts ?? [],
                    user_store.user?.bluesky_accounts ?? [],
                    user_store.user?.account_links ?? [],
                );
                this.selectable_accounts = selectable_accounts;

                // 連携している Twitter / Bluesky / 紐付け アカウントが一つでもあれば is_logged_in_twitter を true に設定
                if (selectable_accounts.length === 0) {
                    // ユーザー自体はログイン中でも、実況用アカウントをすべて解除した場合は Twitter タブを未連携状態に戻す
                    // 保存済みの選択アカウントも同時に消し、後から同じローカル ID が別アカウントに再利用される事故を避ける
                    this.is_logged_in_twitter = false;
                    this.selected_account = null;
                    this.selected_twitter_account = null;
                    this.account_api_activity = {};
                    useSettingsStore().settings.selected_twitter_panel_account = null;
                    return;
                }

                this.is_logged_in_twitter = true;
                // 永続化された選択中アカウントを復元 (該当が無ければ resolveSelectedAccount 側で先頭にフォールバックされる)
                // selectAccount() を経由することで、selected_account / selected_twitter_account / SettingsStore への書き戻しを一括で行う
                // フォールバック発動時に SettingsStore に書き戻すことで、無効な永続化値が残り続けるのを防ぐ
                const resolved_account = this.resolveSelectedAccount(selectable_accounts);
                if (resolved_account !== null) {
                    this.selectAccount(resolved_account);
                }

                // 選択されている Twitter アカウントがあればその API 活動フラグをリセット
                if (this.selected_twitter_account) {
                    this.resetAccountAPIActivity(this.selected_twitter_account.screen_name);
                }
            } else {
                this.is_logged_in_twitter = false;
                this.selectable_accounts = [];
                this.selected_account = null;
                this.selected_twitter_account = null;
                this.account_api_activity = {};
            }
        },

        /**
         * ユーザー情報から Twitter タブで選択可能なアカウント一覧を生成する
         * @param twitter_accounts Twitter アカウント一覧
         * @param bluesky_accounts Bluesky アカウント一覧
         * @param account_links Twitter / Bluesky 紐付け一覧
         * @returns 選択可能なアカウント一覧
         */
        buildSelectableAccounts(
            twitter_accounts: ITwitterAccount[],
            bluesky_accounts: IBlueskyAccount[],
            account_links: IAccountLink[],
        ): ISelectableAccount[] {
            // 紐付け済みの個別アカウントを単独候補にも出すと二重投稿や選択の混乱につながるため、先に ID 集合を作る
            const linked_twitter_account_ids = new Set(account_links.map(account_link => account_link.twitter_account.id));
            const linked_bluesky_account_ids = new Set(account_links.map(account_link => account_link.bluesky_account.id));
            // 紐付けアカウントを優先表示し、その後に未紐付けの Twitter / Bluesky 単独アカウントを並べる
            return [
                ...account_links.map(account_link => ({ kind: 'Linked' as const, account_link })),
                ...twitter_accounts
                    .filter(twitter_account => linked_twitter_account_ids.has(twitter_account.id) === false)
                    .map(twitter_account => ({ kind: 'Twitter' as const, twitter_account })),
                ...bluesky_accounts
                    .filter(bluesky_account => linked_bluesky_account_ids.has(bluesky_account.id) === false)
                    .map(bluesky_account => ({ kind: 'Bluesky' as const, bluesky_account })),
            ];
        },

        /**
         * SettingsStore の保存値から選択中アカウントを復元する
         * @param selectable_accounts 選択可能なアカウント一覧
         * @returns 選択中アカウント
         */
        resolveSelectedAccount(selectable_accounts: ISelectableAccount[]): ISelectableAccount | null {
            // 永続化は KonomiTV-Settings (SettingsStore) に集約しているため、localStorage への直接アクセスは行わない
            const saved_account = useSettingsStore().settings.selected_twitter_panel_account;
            const selected_account = selectable_accounts.find(account => {
                if (saved_account === null) {
                    return false;
                }
                if (account.kind === 'Twitter') {
                    return saved_account.kind === 'Twitter' && account.twitter_account.id === saved_account.id;
                }
                if (account.kind === 'Bluesky') {
                    return saved_account.kind === 'Bluesky' && account.bluesky_account.id === saved_account.id;
                }
                return saved_account.kind === 'Linked' && account.account_link.id === saved_account.id;
            });
            return selected_account ?? selectable_accounts[0] ?? null;
        },

        /**
         * Twitter タブで利用するアカウントを選択する
         * @param account 選択するアカウント
         */
        selectAccount(account: ISelectableAccount): void {
            this.selected_account = account;
            const settings_store = useSettingsStore();
            // TwitterScrapeBrowser の Keep-Alive や seenTweetIds は Twitter アカウントがある場合だけ使う
            // Bluesky 単独選択時は selected_twitter_account を明示的に空にして既存 Twitter API を止める
            if (account.kind === 'Twitter') {
                this.selected_twitter_account = account.twitter_account;
                settings_store.settings.selected_twitter_panel_account = {kind: 'Twitter', id: account.twitter_account.id};
            } else if (account.kind === 'Bluesky') {
                this.selected_twitter_account = null;
                settings_store.settings.selected_twitter_panel_account = {kind: 'Bluesky', id: account.bluesky_account.id};
            } else {
                this.selected_twitter_account = account.account_link.twitter_account;
                settings_store.settings.selected_twitter_panel_account = {kind: 'Linked', id: account.account_link.id};
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
