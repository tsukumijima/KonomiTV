
import { ITweet } from '@/services/Twitter';
import { dayjs } from '@/utils';


/**
 * ツイート (Twitter / Bluesky 投稿) を扱う共通ユーティリティ
 * Twitter タブ配下の Timeline / Search 双方で同じ重複検出・並び替えロジックを使うためにまとめている
 */
export class TweetUtils {

    /**
     * ツイートの同一性比較に使うキーを取得する
     * Bluesky 投稿の id は AT URI なので、source + ID だけで識別できる
     * @param tweet ツイート
     * @returns 同一性比較用のキー文字列
     */
    static getTweetIdentityKey(tweet: ITweet): string {
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
     * ツイート配列を投稿時刻の新しい順に並べ替える
     * 元の配列を破壊的にソートして返す (呼び出し側で配列を保護したい場合は事前にコピーすること)
     * @param tweets ソート対象のツイート配列
     * @returns ソート後のツイート配列
     */
    static sortTweetsByCreatedAt(tweets: ITweet[]): ITweet[] {
        return tweets.sort((a, b) => dayjs(b.created_at).valueOf() - dayjs(a.created_at).valueOf());
    }
}
