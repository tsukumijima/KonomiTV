import { ITimelineLoadMoreCursor, ITimelineTweetsResult, ITweet } from '@/services/Twitter';
import { TweetUtils, dayjs } from '@/utils';

export type TimelineAccountKind = 'Twitter' | 'Bluesky' | 'Linked';
export type TimelineSource = 'Twitter' | 'Bluesky';

/**
 * サービス単位の取得済み範囲と古い方向カーソルを保持する
 * `oldest_created_at` は保持済み投稿の最古時刻であり、そこまで連続取得済みであることは保証しない
 */
export interface IFeedCoverage {
    // 表示下端や Bluesky 補充判定に使う、保持済み投稿の最古時刻
    oldest_created_at: string | null;
    // 末尾の「さらに表示」で使う古い方向カーソル
    older_cursor: string | null;
    // サーバーが古い方向の終端を示した場合だけ true にする
    is_older_exhausted: boolean;
}

/**
 * Twitter と Bluesky の取得済み範囲を 1 つの表示モデルで扱うための状態
 */
export interface IMergedFeedCoverage {
    twitter: IFeedCoverage;
    bluesky: IFeedCoverage;
}

/**
 * Twitter サーバーが明示した中央の未取得範囲だけを表す
 * `Older` と Bluesky の古い方向カーソルは取得範囲側で扱う
 */
export interface ITwitterGap {
    id: string;
    cursor_id: string;
    cursor_type: 'Gap' | 'ShowMore';
    upper_created_at: string;
    lower_created_at: string | null;
}

/**
 * Twitter 中央 gap を埋めるための表示用ボタン
 * 押下時は Twitter だけを取得し、Bluesky の古い方向カーソルは消費しない
 */
export interface ITwitterGapLoadMoreItem {
    type: 'twitter_gap';
    id: string;
    gap_id: string;
    cursor_id: string;
    cursor_type: 'Gap' | 'ShowMore';
    upper_created_at: string;
    lower_created_at: string | null;
}

/**
 * 表示末尾から古い方向へ進むための表示用ボタン
 * 混合表示時は Twitter の取得範囲を優先し、Twitter 枯渇後だけ Bluesky を進める
 */
export interface ITailLoadMoreItem {
    type: 'tail';
    id: string;
    upper_created_at: string;
    lower_created_at: null;
}

export type ILoadMoreItem = ITwitterGapLoadMoreItem | ITailLoadMoreItem;
export type TimelineDisplayItem = ITweet | ILoadMoreItem;

export interface IClassifiedTimelineCursors {
    older_cursor: string | null;
    twitter_gaps: ITwitterGap[];
}

/**
 * 表示用ボタンから導いた、次の追加取得リクエストに必要な情報
 */
export interface ILoadMoreTargets {
    should_fetch_twitter: boolean;
    should_fetch_bluesky: boolean;
    twitter_cursor_id: string | null;
    twitter_cursor_type: ITimelineLoadMoreCursor['cursor_type'] | null;
    bluesky_cursor_id: string | null;
    consumed_twitter_gap_id: string | null;
}

/**
 * 空のサービス別取得範囲を作成する
 * @returns 未取得状態のサービス別取得範囲
 */
export const createEmptyFeedCoverage = (): IFeedCoverage => ({
    oldest_created_at: null,
    older_cursor: null,
    is_older_exhausted: false,
});

/**
 * 空の統合取得範囲を作成する
 * @returns Twitter / Bluesky の両方を未取得にした統合取得範囲
 */
export const createEmptyMergedFeedCoverage = (): IMergedFeedCoverage => ({
    twitter: createEmptyFeedCoverage(),
    bluesky: createEmptyFeedCoverage(),
});

const getCreatedAtMilliseconds = (createdAt: Date | string) => {
    return dayjs(createdAt).valueOf();
};

const getTweetCreatedAtMilliseconds = (tweet: ITweet) => {
    return getCreatedAtMilliseconds(tweet.created_at);
};

/**
 * 投稿配列から最も古い投稿を取得する
 * @param tweets 判定対象の投稿配列
 * @returns 最も古い投稿、配列が空の場合は null
 */
export const getOldestTweet = (tweets: ITweet[]) => {
    if (tweets.length === 0) {
        return null;
    }
    return tweets.reduce((oldestTweet, tweet) => (
        getTweetCreatedAtMilliseconds(tweet) < getTweetCreatedAtMilliseconds(oldestTweet) ? tweet : oldestTweet
    ));
};

const getOlderCursor = (loadMoreCursors: ITimelineLoadMoreCursor[]) => {
    return loadMoreCursors.find(loadMoreCursor => loadMoreCursor.cursor_type === 'Older') ?? null;
};

/**
 * API レスポンスが実際にカーソルを消費したかを判定する
 * @param result API レスポンス
 * @returns カーソルが消費された場合は true
 */
export const isCursorConsumed = (
    result: ITimelineTweetsResult | null,
): result is ITimelineTweetsResult & { is_cursor_consumed: true } => {
    return result !== null && result.is_cursor_consumed === true;
};

/**
 * API レスポンスの追加取得カーソルを取得範囲と Twitter 中央 gap に分類する
 * @param source レスポンス元サービス
 * @param result API レスポンス
 * @param pageTweets レスポンスに含まれる投稿配列
 * @returns 古い方向カーソルと Twitter 中央 gap の分類結果
 */
export const classifyTimelineCursors = (
    source: TimelineSource,
    result: ITimelineTweetsResult | null,
    pageTweets: ITweet[],
): IClassifiedTimelineCursors => {
    if (isCursorConsumed(result) === false) {
        return {
            older_cursor: null,
            twitter_gaps: [],
        };
    }

    const olderCursor = getOlderCursor(result.load_more_cursors);
    if (source === 'Bluesky') {
        return {
            older_cursor: olderCursor?.cursor_id ?? null,
            twitter_gaps: [],
        };
    }

    const oldestTweet = getOldestTweet(pageTweets);
    const fallbackUpperCreatedAt = oldestTweet !== null ? String(oldestTweet.created_at) : null;
    const twitterGaps = result.load_more_cursors
        .filter((loadMoreCursor): loadMoreCursor is ITimelineLoadMoreCursor & { cursor_type: 'Gap' | 'ShowMore' } => (
            loadMoreCursor.cursor_type === 'Gap' || loadMoreCursor.cursor_type === 'ShowMore'
        ))
        .map((loadMoreCursor) => {
            // Twitter が明示した中央 gap だけを表示用の未取得範囲として扱う
            // 古い方向の `Older` と Bluesky のカーソルは取得済み範囲の境界なので、この型には入れない
            const upperCreatedAt = loadMoreCursor.upper_created_at ?? fallbackUpperCreatedAt;
            if (upperCreatedAt === null) {
                return null;
            }
            return {
                id: `twitter_gap_${loadMoreCursor.cursor_id}_${upperCreatedAt}`,
                cursor_id: loadMoreCursor.cursor_id,
                cursor_type: loadMoreCursor.cursor_type,
                upper_created_at: upperCreatedAt,
                lower_created_at: loadMoreCursor.lower_created_at,
            };
        })
        .filter((gap): gap is ITwitterGap => gap !== null);

    return {
        older_cursor: olderCursor?.cursor_id ?? null,
        twitter_gaps: twitterGaps,
    };
};

/**
 * 取得済みページからサービス別取得範囲を更新する
 * @param previousCoverage 更新前のサービス別取得範囲
 * @param result API レスポンス
 * @param pageTweets レスポンスに含まれる投稿配列
 * @param options 新着方向取得や中央 gap 取得で古い方向状態を保護するためのオプション
 * @returns 更新後のサービス別取得範囲
 */
export const updateCoverageFromFetchedPage = (
    previousCoverage: IFeedCoverage,
    result: ITimelineTweetsResult | null,
    pageTweets: ITweet[],
    options: { should_preserve_older_state?: boolean; should_keep_older_uninitialized_when_missing?: boolean } = {},
): IFeedCoverage => {
    if (isCursorConsumed(result) === false) {
        return previousCoverage;
    }

    const oldestTweet = getOldestTweet(pageTweets);
    const pageOldestCreatedAt = oldestTweet !== null ? String(oldestTweet.created_at) : null;
    const olderCursor = getOlderCursor(result.load_more_cursors);

    // 取得済み最古時刻は過去方向にだけ広げる
    // 通常更新や中央 gap 取得で新しいページが返っても、混合表示の下端を新しい側へ巻き戻さない
    const oldestCreatedAt = (
        previousCoverage.oldest_created_at !== null &&
        (
            pageOldestCreatedAt === null ||
            getCreatedAtMilliseconds(previousCoverage.oldest_created_at) < getCreatedAtMilliseconds(pageOldestCreatedAt)
        )
    ) ? previousCoverage.oldest_created_at : pageOldestCreatedAt;

    // `oldest_created_at` は取得済み投稿の最古時刻であり、そこまで連続取得済みであることは保証しない
    // Twitter の中央 gap は別の表示項目として残るため、ここでは末尾表示下端の候補だけを更新する
    // 新着方向取得と中央 gap 取得は、末尾の古い方向カーソルを消費する操作ではない
    // レスポンスに `Older` が含まれていても中間位置の可能性があるため、既存の末尾状態を優先する
    const shouldPreserveOlderState = options.should_preserve_older_state === true;
    if (shouldPreserveOlderState === true) {
        return {
            oldest_created_at: oldestCreatedAt,
            older_cursor: previousCoverage.older_cursor,
            is_older_exhausted: previousCoverage.is_older_exhausted,
        };
    }

    // 初回や通常更新直後は、サーバーが `Older` を返すまで「未確立」として扱う
    // ここで枯渇扱いにすると、Twitter 単独でも末尾の「さらに表示」ボタンが二度と出なくなる
    const shouldKeepOlderUninitialized = (
        options.should_keep_older_uninitialized_when_missing === true &&
        previousCoverage.older_cursor === null &&
        previousCoverage.is_older_exhausted === false &&
        olderCursor === null
    );

    return {
        oldest_created_at: oldestCreatedAt,
        older_cursor: olderCursor?.cursor_id ?? null,
        is_older_exhausted: shouldKeepOlderUninitialized === true ? false : olderCursor === null,
    };
};

/**
 * 混合表示で画面に出してよい最古時刻を解決する
 * @param coverage Twitter / Bluesky の統合取得範囲
 * @param accountKind 表示中アカウント種別
 * @returns 表示下端に使う時刻、クランプしない場合は null
 */
export const resolveDisplayLowerBound = (
    coverage: IMergedFeedCoverage,
    accountKind: TimelineAccountKind,
) => {
    // 混合表示では Twitter が取得できている時刻範囲を下端にし、Bluesky だけ古く進む違和感を隠す
    // Twitter が古い方向で枯渇した場合は、Bluesky の保持済み投稿を隠す理由がなくなるため解除する
    if (
        accountKind === 'Linked' &&
        coverage.twitter.is_older_exhausted === false &&
        coverage.twitter.oldest_created_at !== null
    ) {
        return coverage.twitter.oldest_created_at;
    }
    return null;
};

const shouldShowTweet = (
    tweet: ITweet,
    displayLowerBound: string | null,
) => {
    if (displayLowerBound === null) {
        return true;
    }
    if (tweet.source !== 'Bluesky') {
        return true;
    }
    return getTweetCreatedAtMilliseconds(tweet) >= getCreatedAtMilliseconds(displayLowerBound);
};

const hasTailCursor = (
    coverage: IMergedFeedCoverage,
    accountKind: TimelineAccountKind,
) => {
    if (accountKind === 'Twitter') {
        return coverage.twitter.is_older_exhausted === false && coverage.twitter.older_cursor !== null;
    }
    if (accountKind === 'Bluesky') {
        return coverage.bluesky.is_older_exhausted === false && coverage.bluesky.older_cursor !== null;
    }
    if (coverage.twitter.is_older_exhausted === false) {
        return coverage.twitter.older_cursor !== null;
    }
    return coverage.bluesky.is_older_exhausted === false && coverage.bluesky.older_cursor !== null;
};

const getTailUpperCreatedAt = (
    sortedTweets: ITweet[],
    coverage: IMergedFeedCoverage,
    accountKind: TimelineAccountKind,
) => {
    const displayLowerBound = resolveDisplayLowerBound(coverage, accountKind);
    if (displayLowerBound !== null) {
        return displayLowerBound;
    }
    const oldestTweet = getOldestTweet(sortedTweets);
    return oldestTweet !== null ? String(oldestTweet.created_at) : null;
};

/**
 * 投稿・Twitter 中央 gap・取得範囲から表示用アイテム配列を構築する
 * @param tweets 表示候補の投稿配列
 * @param twitterGaps Twitter サーバー由来の中央 gap
 * @param coverage Twitter / Bluesky の統合取得範囲
 * @param accountKind 表示中アカウント種別
 * @returns 仮想スクローラーへ渡す表示用アイテム配列
 */
export const buildMergedTimelineItems = (
    tweets: ITweet[],
    twitterGaps: ITwitterGap[],
    coverage: IMergedFeedCoverage,
    accountKind: TimelineAccountKind,
): TimelineDisplayItem[] => {
    const displayLowerBound = resolveDisplayLowerBound(coverage, accountKind);
    const sortedTweets = TweetUtils.sortTweetsByCreatedAt([...tweets])
        .filter(tweet => shouldShowTweet(tweet, displayLowerBound));
    const sortedTwitterGaps = [...twitterGaps]
        .sort((a, b) => getCreatedAtMilliseconds(b.upper_created_at) - getCreatedAtMilliseconds(a.upper_created_at));
    const items: TimelineDisplayItem[] = [];
    let tweetIndex = 0;

    for (const twitterGap of sortedTwitterGaps) {
        const upperTime = getCreatedAtMilliseconds(twitterGap.upper_created_at);
        while (
            tweetIndex < sortedTweets.length &&
            getTweetCreatedAtMilliseconds(sortedTweets[tweetIndex]) >= upperTime
        ) {
            items.push(sortedTweets[tweetIndex]);
            tweetIndex++;
        }
        items.push({
            type: 'twitter_gap',
            id: `twitter_gap_load_more_${twitterGap.id}`,
            gap_id: twitterGap.id,
            cursor_id: twitterGap.cursor_id,
            cursor_type: twitterGap.cursor_type,
            upper_created_at: twitterGap.upper_created_at,
            lower_created_at: twitterGap.lower_created_at,
        });
    }

    while (tweetIndex < sortedTweets.length) {
        items.push(sortedTweets[tweetIndex]);
        tweetIndex++;
    }

    const tailUpperCreatedAt = getTailUpperCreatedAt(sortedTweets, coverage, accountKind);
    if (tailUpperCreatedAt !== null && hasTailCursor(coverage, accountKind) === true) {
        items.push({
            type: 'tail',
            id: 'tail_load_more',
            upper_created_at: tailUpperCreatedAt,
            lower_created_at: null,
        });
    }

    return items;
};

/**
 * 追加表示ボタンから次に取得すべきサービスとカーソルを決める
 * @param item 押下された追加表示ボタン
 * @param coverage Twitter / Bluesky の統合取得範囲
 * @param accountKind 表示中アカウント種別
 * @returns 次に取得するサービスとカーソル情報
 */
export const decideLoadMoreTargets = (
    item: ILoadMoreItem,
    coverage: IMergedFeedCoverage,
    accountKind: TimelineAccountKind,
): ILoadMoreTargets => {
    if (item.type === 'twitter_gap') {
        return {
            should_fetch_twitter: true,
            should_fetch_bluesky: false,
            twitter_cursor_id: item.cursor_id,
            twitter_cursor_type: item.cursor_type,
            bluesky_cursor_id: null,
            consumed_twitter_gap_id: item.gap_id,
        };
    }

    if (accountKind === 'Twitter') {
        return {
            should_fetch_twitter: coverage.twitter.older_cursor !== null,
            should_fetch_bluesky: false,
            twitter_cursor_id: coverage.twitter.older_cursor,
            twitter_cursor_type: 'Older',
            bluesky_cursor_id: null,
            consumed_twitter_gap_id: null,
        };
    }

    if (accountKind === 'Bluesky') {
        return {
            should_fetch_twitter: false,
            should_fetch_bluesky: coverage.bluesky.older_cursor !== null,
            twitter_cursor_id: null,
            twitter_cursor_type: null,
            bluesky_cursor_id: coverage.bluesky.older_cursor,
            consumed_twitter_gap_id: null,
        };
    }

    if (coverage.twitter.is_older_exhausted === false) {
        return {
            should_fetch_twitter: coverage.twitter.older_cursor !== null,
            should_fetch_bluesky: false,
            twitter_cursor_id: coverage.twitter.older_cursor,
            twitter_cursor_type: 'Older',
            bluesky_cursor_id: null,
            consumed_twitter_gap_id: null,
        };
    }

    return {
        should_fetch_twitter: false,
        should_fetch_bluesky: coverage.bluesky.older_cursor !== null,
        twitter_cursor_id: null,
        twitter_cursor_type: null,
        bluesky_cursor_id: coverage.bluesky.older_cursor,
        consumed_twitter_gap_id: null,
    };
};

/**
 * 混合表示の下端へ Bluesky の保持範囲が届いているかを判定する
 * @param coverage Twitter / Bluesky の統合取得範囲
 * @param accountKind 表示中アカウント種別
 * @returns Bluesky の追加取得が必要な場合は true
 */
export const shouldFetchBlueskyForDisplayLowerBound = (
    coverage: IMergedFeedCoverage,
    accountKind: TimelineAccountKind,
) => {
    const displayLowerBound = resolveDisplayLowerBound(coverage, accountKind);
    if (displayLowerBound === null || coverage.bluesky.older_cursor === null || coverage.bluesky.is_older_exhausted === true) {
        return false;
    }
    if (coverage.bluesky.oldest_created_at === null) {
        return true;
    }
    return getCreatedAtMilliseconds(coverage.bluesky.oldest_created_at) > getCreatedAtMilliseconds(displayLowerBound);
};

/**
 * Twitter 中央 gap を重複しないように追加する
 * @param currentGaps 現在保持している Twitter 中央 gap
 * @param newGaps 新しく追加する Twitter 中央 gap
 * @returns 重複を除いて結合した Twitter 中央 gap
 */
export const appendTwitterGaps = (
    currentGaps: ITwitterGap[],
    newGaps: ITwitterGap[],
) => {
    if (newGaps.length === 0) {
        return currentGaps;
    }
    const existingGapIds = new Set(currentGaps.map(gap => gap.id));
    return [
        ...currentGaps,
        ...newGaps.filter(gap => existingGapIds.has(gap.id) === false),
    ];
};
