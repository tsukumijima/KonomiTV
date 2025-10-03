
import { defineStore } from 'pinia';

import Message from '@/message';
import Twitter, { ITwitterChallengeData } from '@/services/Twitter';
import { ITwitterAccount } from '@/services/Users';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';


// サーバー側でアクセスしている GraphQL API のエンドポイント名
// ref: server/app/utils/TwitterGraphQLAPI.py
type EndpointName =
    'CreateTweet' |
    'CreateRetweet' |
    'DeleteRetweet' |
    'FavoriteTweet' |
    'UnfavoriteTweet' |
    'HomeLatestTimeline' |
    'SearchTimeline';


/**
 * アプリケーション全体で共有される Twitter 関連の状態を保存するストア
 */
const useTwitterStore = defineStore('twitter', {
    state: () => ({

        // Twitter アカウントを1つでも連携しているかどうか
        is_logged_in_twitter: false,

        // 現在ツイート対象として選択されている Twitter アカウント
        selected_twitter_account: null as ITwitterAccount | null,

        // スクリーンネームごとの Challenge Solver 用 iframe と Challenge 情報を保存する
        challenge_solvers: {} as Record<string, {
            solver_iframe: HTMLIFrameElement,
            challenge_data: ITwitterChallengeData,
        }>,
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
                }
            }
        },

        /**
         * 指定されたスクリーンネームの Challenge Solver 用 iframe を初期化する
         * Challenge Solver 用 iframe とは、Twitter Web App の HTML などから取得した Challenge 情報に含まれる JavaScript コードを
         * 隔離された環境で eval() し、Twitter Web App のスクレイピング対策用ヘッダーである X-Client-Transaction-ID を解決するための iframe のこと
         * OldTweetDeck にて使われている手法がもっとも確実で変更にロバストだと考え、ロジックをほぼそのまま移植させて頂いた (感謝!!)
         * 性質上壊れやすいため、仮に失敗した場合でも他の機能の動作に影響を及ぼさないよう、ログを出力した上で敢えてエラーを送出しない設計としている
         * ref: https://github.com/dimdenGD/OldTweetDeck
         * ref: https://github.com/dimdenGD/OldTweetDeck/blob/main/src/challenge.js
         * @param screen_name スクリーンネーム
         */
        async initChallengeSolverIframe(screen_name: string): Promise<void> {

            // すでに Challenge Solver 用 iframe が初期化されている場合は何も行わない
            if (this.challenge_solvers[screen_name]) return;

            // 指定されたスクリーンネームの Challenge 情報を取得する
            const challenge_data = await Twitter.fetchChallengeData(screen_name);
            if (challenge_data === null) {
                console.error(`[TwitterStore] Failed to fetch challenge data for @${screen_name}.`);
                return;
            }

            // 指定されたスクリーンネームの Challenge Solver 用 iframe を初期化する
            // 開発維持コストの兼ね合いもあり、OldTweetDeck で使われている Challenge 解決用 iframe 用 HTML をそのまま移植して使っている
            const solver_iframe = document.createElement('iframe');
            solver_iframe.style.display = 'none';  // この iframe は Challenge の解決以外には使わないので表示する必要もない
            solver_iframe.src = '/solver.html';
            document.body.appendChild(solver_iframe);
            this.challenge_solvers[screen_name] = {
                solver_iframe: solver_iframe,
                challenge_data: challenge_data,
            };

            // Challenge Solver 用 iframe がロードされるまで待つ
            await new Promise((resolve) => {
                solver_iframe.onload = resolve;
            });

            // Challenge Solver 用 iframe に Challenge 情報を送る
            solver_iframe.contentWindow!.postMessage({
                action: 'init',
                challenge: challenge_data.challenge_js_code,
                vendor: challenge_data.vendor_js_code,
                anims: challenge_data.challenge_animation_svg_codes,
                verificationCode: challenge_data.verification_code,
            }, '*');

            // Challenge Solver 用 iframe からの応答を待つ
            await new Promise<void>((resolve, reject) => {
                const messageHandler = (event: MessageEvent) => {
                    // このイベントが Challenge Solver 用 iframe からのレスポンスであることを確認する
                    if (event.source !== solver_iframe.contentWindow) return;
                    const data = event.data;
                    // 初期化成功
                    if (data.action === 'ready') {
                        window.removeEventListener('message', messageHandler);
                        console.log(`[TwitterStore] Challenge Solver for @${screen_name} initialized successfully.`);
                        resolve();
                    // 初期化失敗
                    } else if (data.action === 'initError') {
                        window.removeEventListener('message', messageHandler);
                        console.error(`[TwitterStore] Challenge Solver for @${screen_name} failed to initialize.`);
                        Message.error(`Twitter @${screen_name} の Challenge Solver の初期化に失敗しました。`);
                        resolve();  // エラーにしないために成功扱い
                    }
                };
                window.addEventListener('message', messageHandler);
            });
        },

        /**
         * 指定されたエンドポイント名に対応する Challenge を解決し、94文字のランダム英数字である X-Client-Transaction-ID を返す
         * 性質上壊れやすいため、仮に失敗した場合でも他の機能の動作に影響を及ぼさないよう、ログを出力した上で敢えてエラーを送出しない設計としている
         * @param screen_name スクリーンネーム
         * @param endpoint_name エンドポイント名
         * @returns Twitter GraphQL API へのリクエストに必要な X-Client-Transaction-ID (成功した場合) または null (失敗した場合)
         */
        async solveChallenge(screen_name: string, endpoint_name: EndpointName): Promise<string | null> {

            // まだ当該スクリーンネームの Challenge Solver 用 iframe が初期化されていなければ初期化する
            if (!this.challenge_solvers[screen_name]) {
                await this.initChallengeSolverIframe(screen_name);
                // 何らかの理由で初期化に失敗している
                if (!this.challenge_solvers[screen_name]) {
                    console.error(`[TwitterStore] Failed to initialize challenge solver for @${screen_name}.`);
                    return null;
                }
            }
            const challenge_solver = this.challenge_solvers[screen_name];
            if (!challenge_solver.challenge_data.endpoint_infos[endpoint_name]) {
                console.error(`[TwitterStore] Endpoint info for ${endpoint_name} not found.`);
                return null;
            }

            // エンドポイント名に対応するエンドポイント情報を取得して Challenge Solver 用 iframe に送信する
            // この時、このリクエストに対応するレスポンスかを確認できるように一意な ID を付与する
            const endpoint_info = challenge_solver.challenge_data.endpoint_infos[endpoint_name];
            const request_id = Date.now();
            challenge_solver.solver_iframe.contentWindow!.postMessage({
                action: 'solve',
                path: endpoint_info.path,
                method: endpoint_info.method,
                id: request_id,
            }, '*');

            return new Promise<string | null>((resolve, reject) => {
                const messageHandler = (event: MessageEvent) => {
                    // このイベントが Challenge Solver 用 iframe からのレスポンスであることを確認する
                    if (event.source !== challenge_solver.solver_iframe.contentWindow) return;
                    const data = event.data;
                    // このレスポンスが対応するリクエストであることを確認する
                    if (data.id !== request_id) return;
                    // Challenge の解決成功
                    if (data.action === 'solved') {
                        window.removeEventListener('message', messageHandler);
                        console.log(`[TwitterStore] X-Client-Transaction-ID: ${data.result}`);
                        resolve(data.result);
                    // Challenge の解決失敗
                    } else if (data.action === 'error') {
                        window.removeEventListener('message', messageHandler);
                        console.error(`[TwitterStore] Challenge Solver for @${screen_name} failed to solve challenge. (${data.error})`);
                        Message.error(`Twitter @${screen_name} の Challenge Solver が Challenge を解決できませんでした。`);
                        resolve(null);  // エラーにしないために成功扱い
                    }
                };
                window.addEventListener('message', messageHandler);
            });
        }
    }
});

export default useTwitterStore;
