
import type { ITweet } from '@/services/Twitter';

import { dayjs } from '@/utils';



// リプライツリー実況のモード
export type ReplyThreadMode = 'PerHashtag' | 'PerDay' | 'Disabled';

// Twitter のリプライツリー状態
export interface ITwitterReplyThreadState {
    last_tweet_id: string;
    started_at: string;
    hashtag_key: string;
}

// Bluesky のリプライツリー状態
export interface IBlueskyReplyThreadState {
    root_uri: string;
    root_cid: string;
    parent_uri: string;
    parent_cid: string;
    started_at: string;
    hashtag_key: string;
}

export interface IReplyThreadDecision {
    send_as_reply: boolean;
    reset_state_after: boolean;
    clear_state: boolean;
}

/**
 * ツイート (Twitter / Bluesky 投稿) を扱う共通ユーティリティ
 * Twitter タブ配下の Timeline / Search 双方で同じ重複検出・並び替えロジックを使うためにまとめている
 */
export class TweetUtils {

    /**
     * ツイートの同一性比較に使うキーを取得する
     * Bluesky 投稿の id は AT URI なので、source + ID だけで識別できる
     * Bluesky のリポストは元投稿と同じ AT URI を持つため、リポストしたユーザーも含める
     * @param tweet ツイート
     * @returns 同一性比較用のキー文字列
     */
    static getTweetIdentityKey(tweet: ITweet): string {
        // Bluesky のリポスト通知は元投稿と同じ AT URI を共有する
        // 投稿本体とリポスト行を同じキーで畳むと、タイムライン上のリポスト表示が消えてしまう
        if (tweet.source === 'Bluesky' && tweet.retweeted_tweet !== null) {
            return `${tweet.source}:${tweet.id}:repost:${tweet.user.id}`;
        }
        return `${tweet.source}:${tweet.id}`;
    }

    /**
     * 既出ツイートのキーセットと突き合わせ、重複しないツイートだけを返す
     * @param tweets フィルタ対象のツイート配列
     * @param existingIds 既出のキーを格納した Set
     * @returns 重複を除いたツイート配列
     */
    static filterDuplicateTweets(tweets: ITweet[], existingIds: Set<string>): ITweet[] {
        return tweets.filter(tweet => !existingIds.has(TweetUtils.getTweetIdentityKey(tweet)));
    }

    /**
     * ツイート配列を投稿時刻の新しい順に破壊的に並べ替える
     * 元の配列を破壊的にソートして返す (呼び出し側で配列を保護したい場合は事前にコピーすること)
     * @param tweets ソート対象のツイート配列
     * @returns ソート後のツイート配列
     */
    static sortTweetsByCreatedAtInPlace(tweets: ITweet[]): ITweet[] {
        return tweets.sort((a, b) => dayjs(b.created_at).valueOf() - dayjs(a.created_at).valueOf());
    }

    /**
     * ハッシュタグセットを正規化してリプライツリー判定用キーへ変換する
     * @param hashtags 実際に投稿本文へ付与するハッシュタグ一覧
     * @returns 大文字小文字と順序を無視した正規化キー
     */
    static normalizeHashtagKey(hashtags: string[]): string {
        return [...new Set(hashtags
            .map(hashtag => hashtag.replace(/^#/, '').toLowerCase()))]
            .sort()
            .join(',');
    }

    /**
     * 朝 4 時を境界にした実況日キーを返す
     * @param value 判定対象の日時
     * @returns 朝 4 時境界に丸めた Unix epoch (ミリ秒)
     */
    static floorTo4amBoundary(value: string | ReturnType<typeof dayjs>): number {
        const date = dayjs(value);
        // 深夜帯の実況は前日の番組枠として扱い、深夜アニメの途中で日付だけが変わってもツリーを分断しない
        const adjusted = date.hour() < 4 ? date.subtract(1, 'day') : date;
        return adjusted.hour(4).minute(0).second(0).millisecond(0).valueOf();
    }

    /**
     * 現在の設定と保存済み状態からリプライツリーとして送信するかを判定する
     * @param args.mode リプライツリー実況モード
     * @param args.state アカウントごとの保存済みリプライツリー状態
     * @param args.current_hashtag_key 現在投稿するハッシュタグセットの正規化キー
     * @param args.now 判定に使う現在時刻
     * @returns 送信方法と送信成功後の状態更新方針
     */
    static decideReplyThread(args: {
        mode: ReplyThreadMode;
        state: {started_at: string; hashtag_key: string;} | undefined;
        current_hashtag_key: string;
        now: ReturnType<typeof dayjs>;
    }): IReplyThreadDecision {

        if (args.mode === 'Disabled') {
            return {
                send_as_reply: false,
                reset_state_after: false,
                clear_state: false,
            };
        }

        if (args.mode === 'PerHashtag') {
            // ハッシュタグ単位のツリーでは、タグなし投稿を文脈のない単独投稿として扱い、前回ツリーも明示的に切る
            if (args.current_hashtag_key === '') {
                return {
                    send_as_reply: false,
                    reset_state_after: false,
                    clear_state: true,
                };
            }
            if (args.state === undefined || args.state.hashtag_key !== args.current_hashtag_key) {
                return {
                    send_as_reply: false,
                    reset_state_after: true,
                    clear_state: false,
                };
            }
            return {
                send_as_reply: true,
                reset_state_after: false,
                clear_state: false,
            };
        }

        if (args.mode === 'PerDay') {
            if (args.state === undefined) {
                return {
                    send_as_reply: false,
                    reset_state_after: true,
                    clear_state: false,
                };
            }

            // 1 日 1 ツリーでは朝 4 時境界だけを見るため、番組タグの有無や変更はツリー切替条件に含めない
            if (TweetUtils.floorTo4amBoundary(args.state.started_at) !== TweetUtils.floorTo4amBoundary(args.now)) {
                return {
                    send_as_reply: false,
                    reset_state_after: true,
                    clear_state: false,
                };
            }
            return {
                send_as_reply: true,
                reset_state_after: false,
                clear_state: false,
            };
        }

        const unknown_mode: never = args.mode;
        throw new Error(`Unknown reply thread mode: ${unknown_mode}`);
    }
}
