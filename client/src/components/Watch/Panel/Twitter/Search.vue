<template>
    <div class="tab-content tab-content--search">
        <div class="search-header">
            <div class="search-input-wrapper" :class="{'search-input-wrapper--focused': isSearchFormFocused}">
                <Icon icon="fluent:search-16-filled" height="18px" />
                <input
                    v-model="searchQuery"
                    class="search-input"
                    type="search"
                    enterkeyhint="search"
                    placeholder="検索キーワードを入力"
                    @keydown="onKeyDown($event)"
                    @focus="isSearchFormFocused = true"
                    @blur="isSearchFormFocused = false"
                />
            </div>
            <div class="d-flex align-center ml-auto h-100">
                <button v-ripple class="search-header__settings" @click="toggleSettings">
                    <Icon icon="fluent:settings-16-filled" width="20" />
                </button>
                <button v-ripple class="search-header__refresh" style="color: rgb(var(--v-theme-twitter-lighten-1))"
                    @click="performSearchTweets" v-ftooltip.bottom="'検索結果を更新'">
                    <Icon icon="ic:round-refresh" width="20" :class="isFetching ? 'animate-spin' : ''" />
                </button>
            </div>
        </div>
        <div v-if="showSettings" class="search-settings">
            <v-switch id="show_retweets" color="primary" density="compact" hide-details v-model="showRetweets" />
            <label class="ml-4 cursor-pointer" for="show_retweets">リツイートを表示する</label>
        </div>
        <VirtuaList ref="scroller" class="search-tweets" :data="flattenedItems" #default="{ item }"
            v-show="flattenedItems.length > 0">
            <div class="search-item">
                <Tweet v-if="'text' in item" :tweet="item" />
                <button v-else class="load-more-button" @click="handleLoadMore(item)" :disabled="isFetching">
                    <div class="load-more-button__content">
                        <Icon icon="ic:round-refresh" width="20" :class="isFetching ? 'animate-spin' : ''" class="mr-2" />
                        ツイートをさらに表示
                    </div>
                </button>
            </div>
        </VirtuaList>
        <div class="search-announce" v-show="flattenedItems.length === 0">
            <div class="search-announce__heading">まだツイートがありません。</div>
            <div class="search-announce__text">
                <p class="mt-0 mb-0">右上の更新ボタンを押すと、最新の<br>ツイート検索結果を時系列で表示できます。</p>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { VList as VirtuaList } from 'virtua/vue';
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue';

import Tweet from '@/components/Watch/Panel/Twitter/Tweet.vue';
import Message from '@/message';
import Bluesky from '@/services/Bluesky';
import Twitter, { ITimelineLoadMoreCursor, ITimelineTweetsResult, ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils, { TweetUtils, dayjs } from '@/utils';

const twitterStore = useTwitterStore();
const { selected_account } = storeToRefs(twitterStore);

interface ILoadMoreItem {
    type: 'load_more';
    gap_ids: string[];
    twitter_cursor_id?: string;
    twitter_cursor_type?: ITimelineLoadMoreCursor['cursor_type'];
    bluesky_cursor_id?: string;
    upper_created_at: string;
    lower_created_at: string | null;
    id: string;
}

interface IFeedGap {
    id: string;
    upper_created_at: string;
    lower_created_at: string | null;
    twitter_cursor_id?: string;
    twitter_cursor_type?: ITimelineLoadMoreCursor['cursor_type'];
    bluesky_cursor_id?: string;
    is_twitter_exhausted: boolean;
    is_bluesky_exhausted: boolean;
}

const tweetsByKey = ref<Map<string, ITweet>>(new Map());
const gaps = ref<IFeedGap[]>([]);
const showSettings = ref(false);
const showRetweets = ref(false);
const isFetching = ref(false);
const isSearchFormFocused = ref(false);
const searchQuery = ref('');
const scroller = useTemplateRef('scroller');

// Twitter 検索の新着方向カーソルは、直近レスポンスの Top 相当だけを保持する
// 中央の未取得範囲は Twitter サーバー由来の gap カーソルで表現する
const twitterNewerCursorId = ref<string | null>(null);

const getCreatedAtMilliseconds = (createdAt: Date | string) => {
    return dayjs(createdAt).valueOf();
};

const getTweetCreatedAtMilliseconds = (tweet: ITweet) => {
    return getCreatedAtMilliseconds(tweet.created_at);
};

const getOldestTweet = (tweets: ITweet[]) => {
    if (tweets.length === 0) {
        return null;
    }
    return tweets.reduce((oldestTweet, tweet) => (
        getTweetCreatedAtMilliseconds(tweet) < getTweetCreatedAtMilliseconds(oldestTweet) ? tweet : oldestTweet
    ));
};

const createExistingTweetIds = () => {
    return new Set([...tweetsByKey.value.keys()]);
};

const addTweetsToMap = (tweets: ITweet[]) => {
    if (tweets.length === 0) {
        return;
    }

    // 検索結果は Twitter / Bluesky のページ境界が揃わないため、表示順ではなく ID をキーにして保持する
    // Map ごと差し替えることで、仮想スクローラーに渡す computed が必ず再評価される状態にする
    const nextTweetsByKey = new Map(tweetsByKey.value);
    for (const tweet of tweets) {
        nextTweetsByKey.set(TweetUtils.getTweetIdentityKey(tweet), tweet);
    }
    tweetsByKey.value = nextTweetsByKey;
};

const isGapVisible = (gap: IFeedGap) => {
    return (
        (gap.is_twitter_exhausted === false && !!gap.twitter_cursor_id) ||
        (gap.is_bluesky_exhausted === false && !!gap.bluesky_cursor_id)
    );
};

// 内部ではサービスごとに gap を保持し、画面上では近接する gap を 1 つのボタンとして見せる
// カーソルの意味は壊さず、Twitter / Bluesky のボタンが時系列上に並ぶ違和感だけを描画層で吸収する
const createGroupedLoadMoreItems = () => {
    // 取得可能なカーソルが残っている gap だけを、新しい時刻境界から順に処理する
    const visibleGaps = gaps.value
        .filter(gap => isGapVisible(gap))
        .sort((a, b) => getCreatedAtMilliseconds(b.upper_created_at) - getCreatedAtMilliseconds(a.upper_created_at));
    const groupedItems: ILoadMoreItem[] = [];

    for (const gap of visibleGaps) {
        const gapUpperTime = getCreatedAtMilliseconds(gap.upper_created_at);
        const lastGroup = groupedItems[groupedItems.length - 1];
        const lastGroupLowerTime = lastGroup?.lower_created_at ? getCreatedAtMilliseconds(lastGroup.lower_created_at) : null;
        // 直前グループの時刻範囲と重なる gap は同じ未取得範囲として 1 ボタンへ束ねる
        // 検索はサービスごとにページ境界が揃わないため、表示だけ束ねて内部カーソルは個別に残す
        const shouldJoinLastGroup = lastGroup !== undefined && (
            lastGroupLowerTime === null ||
            gapUpperTime >= lastGroupLowerTime
        );

        if (shouldJoinLastGroup === true) {
            // 検索でも中央 gap を保持するが、近い範囲のサービス別カーソルは画面上 1 つのボタンへ束ねる
            // 内部 gap 自体はマージせず、クリック時に `gap_ids` から元のカーソルを引き直す
            lastGroup.gap_ids.push(gap.id);
            lastGroup.twitter_cursor_id ??= gap.twitter_cursor_id;
            lastGroup.twitter_cursor_type ??= gap.twitter_cursor_type;
            lastGroup.bluesky_cursor_id ??= gap.bluesky_cursor_id;
            if (
                lastGroup.lower_created_at !== null &&
                (gap.lower_created_at === null ||
                    getCreatedAtMilliseconds(gap.lower_created_at) < getCreatedAtMilliseconds(lastGroup.lower_created_at))
            ) {
                lastGroup.lower_created_at = gap.lower_created_at;
            }
            continue;
        }

        // 新しい未取得範囲は単独のボタンとして追加し、`flattenedItems` 側で時刻境界へ差し込む
        groupedItems.push({
            type: 'load_more',
            gap_ids: [gap.id],
            twitter_cursor_id: gap.twitter_cursor_id,
            twitter_cursor_type: gap.twitter_cursor_type,
            bluesky_cursor_id: gap.bluesky_cursor_id,
            upper_created_at: gap.upper_created_at,
            lower_created_at: gap.lower_created_at,
            id: `load_more_${gap.id}`,
        });
    }

    return groupedItems;
};

// フラットな構造の配列を生成する computed プロパティ
const flattenedItems = computed(() => {
    const items: (ITweet | ILoadMoreItem)[] = [];
    // `tweetsByKey` は順序を持たない正規化ストアなので、描画直前に必ず時刻降順へ並べ直す
    const sortedTweets = TweetUtils.sortTweetsByCreatedAt([...tweetsByKey.value.values()]);
    const groupedLoadMoreItems = createGroupedLoadMoreItems();
    let tweetIndex = 0;

    for (const loadMoreItem of groupedLoadMoreItems) {
        const upperTime = getCreatedAtMilliseconds(loadMoreItem.upper_created_at);
        // gap の新しい側境界より新しいツイートを先に流し込み、ボタンを正しい時刻位置へ置く
        while (
            tweetIndex < sortedTweets.length &&
            getTweetCreatedAtMilliseconds(sortedTweets[tweetIndex]) >= upperTime
        ) {
            items.push(sortedTweets[tweetIndex]);
            tweetIndex++;
        }
        items.push(loadMoreItem);
    }

    // すべての gap より古いツイートは最後にそのまま流し込む
    while (tweetIndex < sortedTweets.length) {
        items.push(sortedTweets[tweetIndex]);
        tweetIndex++;
    }
    return items;
});

// 仮想スクローラーの描画をリフレッシュする
// 2025/01 現在の Virtua の Vue バインディングは下方向への無限スクロールのみ考慮しているようで、
// 上方向の無限スクロールだと更新しても一見して更新内容が反映されていないように見える問題への回避策
// 一旦下方向にスクロールしてからすぐ元に戻すことで、表示状態の DOM を強制的に更新させる
const isRefreshing = ref(false);
const refreshScroller = async () => {
    if (scroller.value) {
        isRefreshing.value = true;
        const offset = scroller.value.scrollOffset;
        const viewportSize = scroller.value.viewportSize;
        // scrollOffset が 0 ~ (viewportSize * 2) 範囲に収まっていない (一番上にスクロールされていない) 場合はリフレッシュしない
        if (offset < 0 || offset > viewportSize * 2) {
            isRefreshing.value = false;
            return;
        }
        scroller.value.scrollToIndex(offset + (viewportSize * 2));  // 一旦 viewportSize * 2 分ずらしてスクロール
        await Utils.sleep(0.02);  // 0.02 秒待機
        scroller.value.scrollToIndex(offset);  // 元のスクロール位置に戻す
        isRefreshing.value = false;
    }
};

const getSearchFetchResult = (result: PromiseSettledResult<ITimelineTweetsResult | null>) => {
    // Twitter / Bluesky の片方が例外になっても、もう片方の結果を表示できるように null へ正規化する
    if (result.status === 'fulfilled') {
        return result.value;
    }
    console.error('Search API request failed unexpectedly.', result.reason);
    return null;
};

const getTwitterSearchCursorType = (cursorType: ITimelineLoadMoreCursor['cursor_type'] | undefined) => {
    // Twitter 検索 API へ渡すカーソル種別は、サーバー由来の gap 種別をできるだけ保持する
    // Older は Twitter Web App の Bottom 相当なので、既存の検索 API パラメータへ変換する
    if (cursorType === 'Gap' || cursorType === 'ShowMore') {
        return cursorType;
    }
    return 'Bottom';
};

// 検索条件が変わる場面では、投稿本体・gap・Twitter の新着方向カーソルをまとめて破棄する
// どれか 1 つだけ残すと、別クエリや別表示条件のカーソルを誤って再利用してしまう
const resetSearchState = () => {
    tweetsByKey.value = new Map();
    gaps.value = [];
    twitterNewerCursorId.value = null;
};

const filterTweetsByRetweetFlag = (tweets: ITweet[]) => {
    // 検索タブではリツイート非表示が既定なので、通常検索と続き取得で同じ条件を必ず通す
    if (showRetweets.value === true) {
        return tweets;
    }
    return tweets.filter(tweet => !tweet.retweeted_tweet);
};

// アカウント切替時に、現在の検索状態で消費できるサービス別カーソルが残るかを判定する
// Twitter 同士の切替では検索結果を維持しつつ、紐付けから単独へ移る場合の古い gap だけを破棄対象にする
const getAvailableSearchProviders = (account: typeof selected_account.value) => {
    return {
        hasTwitter: account?.kind === 'Twitter' || account?.kind === 'Linked',
        hasBluesky: account?.kind === 'Bluesky' || account?.kind === 'Linked',
    };
};

// 検索結果本体はアカウントをまたいで流用できるが、カーソルは各サービスの具体アカウントに紐づく
// 同じサービス内のアカウント切替を検知し、古いカーソルだけを安全に落とせるよう ID を分解しておく
const getSearchAccountIdentity = (account: typeof selected_account.value) => {
    return {
        twitterAccountId: account?.kind === 'Twitter' ? account.twitter_account.id :
            account?.kind === 'Linked' ? account.account_link.twitter_account.id : null,
        blueskyAccountId: account?.kind === 'Bluesky' ? account.bluesky_account.id :
            account?.kind === 'Linked' ? account.account_link.bluesky_account.id : null,
    };
};

const removeServiceCursorsFromGaps = (service: 'Twitter' | 'Bluesky') => {
    // gap 自体は複数サービスの未取得範囲を束ねるため、切替対象サービスのカーソルだけを無効化する
    // もう片方のサービスがまだ取得可能ならボタンを残し、どちらも消えた gap だけを画面から外す
    gaps.value = gaps.value
        .map((gap) => {
            if (service === 'Twitter') {
                return {
                    ...gap,
                    twitter_cursor_id: undefined,
                    twitter_cursor_type: undefined,
                    is_twitter_exhausted: true,
                };
            }
            return {
                ...gap,
                bluesky_cursor_id: undefined,
                is_bluesky_exhausted: true,
            };
        })
        .filter(gap => isGapVisible(gap));
};

const isCursorConsumed = (result: ITimelineTweetsResult | null) => {
    return result !== null && result.is_cursor_consumed === true;
};

const buildGapFromLoadMoreCursor = (
    source: 'Twitter' | 'Bluesky',
    loadMoreCursor: ITimelineLoadMoreCursor,
    pageTweets: ITweet[],
): IFeedGap | null => {
    // Twitter 検索の中央 gap はサーバー由来カーソルの時刻境界に従う
    // Bluesky 検索は sortAt と作成日時がずれるため、返却カーソルを末尾継続としてだけ扱う
    const oldestTweet = getOldestTweet(pageTweets);
    const upperCreatedAt = loadMoreCursor.upper_created_at ?? (oldestTweet !== null ? String(oldestTweet.created_at) : null);
    if (upperCreatedAt === null) {
        return null;
    }

    const baseGap: IFeedGap = {
        id: `${source.toLowerCase()}_${loadMoreCursor.cursor_id}_${upperCreatedAt}`,
        upper_created_at: upperCreatedAt,
        lower_created_at: loadMoreCursor.lower_created_at,
        is_twitter_exhausted: true,
        is_bluesky_exhausted: true,
    };

    if (source === 'Twitter') {
        return {
            ...baseGap,
            twitter_cursor_id: loadMoreCursor.cursor_id,
            twitter_cursor_type: loadMoreCursor.cursor_type,
            is_twitter_exhausted: false,
        };
    }

    return {
        ...baseGap,
        bluesky_cursor_id: loadMoreCursor.cursor_id,
        is_bluesky_exhausted: false,
    };
};

const buildGapsFromLoadMoreCursors = (
    source: 'Twitter' | 'Bluesky',
    result: ITimelineTweetsResult | null,
    pageTweets: ITweet[],
) => {
    // 実際にカーソルが消費されたレスポンスだけ、次の追加取得カーソルへ状態を進める
    // 30 秒制限の空応答では元の gap を残し、同じ範囲を後で再取得できるようにする
    if (result === null || isCursorConsumed(result) === false) {
        return [];
    }
    return result.load_more_cursors
        .map(loadMoreCursor => buildGapFromLoadMoreCursor(source, loadMoreCursor, pageTweets))
        .filter((gap): gap is IFeedGap => gap !== null);
};

const removeGapsById = (gapIds: string[]) => {
    const gapIdSet = new Set(gapIds);
    gaps.value = gaps.value.filter(gap => !gapIdSet.has(gap.id));
};

const appendGaps = (newGaps: IFeedGap[]) => {
    if (newGaps.length === 0) {
        return;
    }
    // 同じカーソルが再度返った場合は既存 gap を優先し、同じボタンが重複して並ばないようにする
    // 検索では更新ボタンと中央 gap の両方が同じ未取得範囲を指す可能性があるためここで抑止する
    const existingGapIds = new Set(gaps.value.map(gap => gap.id));
    gaps.value = [
        ...gaps.value,
        ...newGaps.filter(gap => existingGapIds.has(gap.id) === false),
    ];
};

const toggleSettings = () => {
    showSettings.value = !showSettings.value;
};

const onKeyDown = (event: KeyboardEvent) => {
    // 変換中でない場合のみ検索を実行
    if (event.key === 'Enter' && event.isComposing === false) {
        performSearchTweets();
    }
};

const performSearchTweets = async () => {
    // 検索 API の多重実行を防ぎ、カーソル履歴とタイムラインブロックの整合性を保つ
    if (isFetching.value) {
        return;
    }
    // 空検索はサーバーに投げず、既存の Twitter 検索 UI と同じくユーザー操作で解決させる
    if (!searchQuery.value.trim()) {
        Message.warning('検索キーワードを入力してください。');
        return;
    }
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_account.value) {
        Message.warning('ツイートを検索するには、Twitter または Bluesky アカウントと連携してください。');
        // 未連携状態に変わった場合は古い検索結果を残さず、現在のアカウント状態と画面表示を一致させる
        resetSearchState();
        isFetching.value = false;
        return;
    }

    // Twitter 検索の通常更新では、直近レスポンスで返された新着方向カーソルだけを送る
    // 中央の未取得範囲は Twitter サーバー由来の gap カーソルで表現し、重複取得用の古い履歴は持たない
    const cursor_id = twitterNewerCursorId.value ?? undefined;

    // 検索結果のツイートを「投稿時刻が新しい順」に取得
    // 初回取得は 20 件、より新しいツイートを取得する新着方向カーソル指定時は 40 件返ってくる
    const query = `${searchQuery.value}${showRetweets.value ? 'include:nativeretweets' : ''}`;
    const account = selected_account.value;
    // 重複判定は、取得結果を追加する前の状態を基準に固定する
    const existingIds = createExistingTweetIds();
    // 紐付けアカウントでは Twitter と Bluesky の検索を並列実行し、片方だけ連携している場合は不要な API を呼ばない
    const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
        account.kind === 'Twitter' || account.kind === 'Linked' ?
            Twitter.searchTweets(account.kind === 'Twitter' ? account.twitter_account.screen_name : account.account_link.twitter_account.screen_name, query, cursor_id, 'Top') :
            Promise.resolve(null),
        account.kind === 'Bluesky' || account.kind === 'Linked' ?
            // Bluesky の検索カーソルは古い方向の続きなので、検索更新では常にカーソルなしで最新検索結果を取り直す
            Bluesky.searchPosts(account.kind === 'Bluesky' ? account.bluesky_account.handle : account.account_link.bluesky_account.handle, searchQuery.value) :
            Promise.resolve(null),
    ]);
    const twitter_result = getSearchFetchResult(twitter_settled_result);
    const bluesky_result = getSearchFetchResult(bluesky_settled_result);
    const result = twitter_result ?? bluesky_result;
    if (result && result.tweets) {
        // KonomiTV の表示は単一リストなので、サービスごとの結果を作成日時で並べ直してから後続処理へ渡す
        // gap 境界には取得ページそのものを使い、表示フィルターで全件落ちても次のカーソルを残す
        const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
        const blueskyPageTweets = [...(bluesky_result?.tweets ?? [])];
        const twitterTweets = filterTweetsByRetweetFlag(twitterPageTweets);
        const blueskyTweets = filterTweetsByRetweetFlag(blueskyPageTweets);

        // 既存のツイートとの重複を除外
        const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
        const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
        const uniqueTweets = TweetUtils.sortTweetsByCreatedAt([
            ...twitterUniqueTweets,
            ...blueskyUniqueTweets,
        ]);

        // Twitter の新着方向カーソルは表示対象の有無に関係なく、実レスポンスが進んだときだけ更新する
        // 制限による空応答では既存カーソルを維持し、次回も同じ位置から検索更新できるようにする
        if (isCursorConsumed(twitter_result) === true && twitter_result?.newer_cursor_id) {
            twitterNewerCursorId.value = twitter_result.newer_cursor_id;
        }

        // サービスごとの新規投稿を正規化ストアへ追加し、表示順は `flattenedItems` 側に任せる
        if (uniqueTweets.length > 0) {
            addTweetsToMap(uniqueTweets);
        }

        // Twitter はサーバー由来の gap カーソル、Bluesky は末尾の古い方向カーソルだけを保存する
        // Bluesky 検索は sortAt と作成日時がずれるため、中央 gap は推定しない
        const newGaps = [
            ...buildGapsFromLoadMoreCursors('Twitter', twitter_result, twitterPageTweets),
            ...buildGapsFromLoadMoreCursors('Bluesky', bluesky_result, blueskyPageTweets),
        ];
        appendGaps(newGaps);

        // 仮想スクローラーの描画をリフレッシュ
        refreshScroller();
    }
    isFetching.value = false;
};

// 「さらに読み込む」ボタンが押されたら当該範囲の検索結果を取得
const handleLoadMore = async (item: ILoadMoreItem) => {
    // 既存ブロック間の歯抜けを埋める処理なので、通常検索の実行中は同時に進めない
    if (isFetching.value) {
        return;
    }
    isFetching.value = true;
    if (!selected_account.value) {
        console.warn('selected_account is null');
        isFetching.value = false;
        return;
    }

    // 検索結果のツイートを「投稿時刻が新しい順」に取得
    // より古いツイートを取得する Bottom カーソル指定時は 20 件返ってくる
    const query = `${searchQuery.value}${showRetweets.value ? 'include:nativeretweets' : ''}`;
    const account = selected_account.value;
    const twitterScreenName = account.kind === 'Twitter' ? account.twitter_account.screen_name :
        account.kind === 'Linked' ? account.account_link.twitter_account.screen_name : null;
    const blueskyHandle = account.kind === 'Bluesky' ? account.bluesky_account.handle :
        account.kind === 'Linked' ? account.account_link.bluesky_account.handle : null;
    // 表示用ボタンを作ったときの gap 順を保ち、最も新しい未取得範囲から 1 件ずつ消費する
    // `gaps.value` の追加順に戻すと、画面上のボタン位置と実際に取得するカーソルがずれる可能性がある
    const targetGaps = item.gap_ids
        .map(gapId => gaps.value.find(gap => gap.id === gapId))
        .filter((gap): gap is IFeedGap => gap !== undefined);
    const consumedGapIds: string[] = [];
    const replacementGaps: IFeedGap[] = [];
    let hasFetchedTwitter = false;
    let hasFetchedBluesky = false;

    for (const gap of targetGaps) {
        // この gap を消費する前の状態を基準に、取得済み投稿の重複だけを除外する
        // 次の gap は API レスポンス内の追加取得カーソルから作るため、境界はサーバー側の指示に従う
        const existingIds = createExistingTweetIds();
        // UI 上の 1 ボタンに複数 gap が束ねられていても、1 回の押下ではサービスごとに 1 カーソルだけ消費する
        // 検索の中央 gap は近接表示されやすいため、同じサービスの複数ページを一度に進めると未取得範囲の対応が読みにくくなる
        const shouldFetchTwitter = hasFetchedTwitter === false && twitterScreenName !== null && !!gap.twitter_cursor_id;
        const shouldFetchBluesky = hasFetchedBluesky === false && blueskyHandle !== null && !!gap.bluesky_cursor_id;
        if (shouldFetchTwitter === false && shouldFetchBluesky === false) {
            continue;
        }
        hasFetchedTwitter = hasFetchedTwitter || shouldFetchTwitter;
        hasFetchedBluesky = hasFetchedBluesky || shouldFetchBluesky;
        // 検索結果の続きはサービスごとのカーソルを 1 つのボタンから消化する
        // Twitter 側が空応答を返した場合は、同じカーソルで後から再取得できるよう gap を進めない
        const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
            shouldFetchTwitter === true ?
                Twitter.searchTweets(twitterScreenName, query, gap.twitter_cursor_id, getTwitterSearchCursorType(gap.twitter_cursor_type)) :
                Promise.resolve(null),
            shouldFetchBluesky === true ?
                Bluesky.searchPosts(blueskyHandle, searchQuery.value, gap.bluesky_cursor_id) :
                Promise.resolve(null),
        ]);
        const twitter_result = getSearchFetchResult(twitter_settled_result);
        const bluesky_result = getSearchFetchResult(bluesky_settled_result);
        // Twitter の空応答は投稿なしとして扱い、gap とカーソルは後段で温存する
        // gap 境界には取得ページそのものを使い、表示フィルターで全件落ちても次のカーソルを残す
        const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
        const blueskyPageTweets = [...(bluesky_result?.tweets ?? [])];
        const twitterTweets = filterTweetsByRetweetFlag(twitterPageTweets);
        const blueskyTweets = filterTweetsByRetweetFlag(blueskyPageTweets);
        const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
        const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
        const uniqueTweets = TweetUtils.sortTweetsByCreatedAt([
            ...twitterUniqueTweets,
            ...blueskyUniqueTweets,
        ]);

        // 取得できた投稿だけを先に Map へ反映し、ボタン位置は preserved / next gap の再構築で決め直す
        if (uniqueTweets.length > 0) {
            addTweetsToMap(uniqueTweets);
        }

        // 取得に成功したサービスのカーソルは消費し、失敗または制限されたサービスのカーソルだけを残す
        // 片側だけ成功した場合に、もう片側の未取得範囲まで誤って消さないための退避用 gap
        const preservedGap: IFeedGap = {
            ...gap,
            twitter_cursor_id: undefined,
            twitter_cursor_type: undefined,
            bluesky_cursor_id: undefined,
            is_twitter_exhausted: true,
            is_bluesky_exhausted: true,
        };
        // Twitter 側が空応答や通信失敗になった場合、そのカーソルは消費できていない
        // 元の gap の Twitter 側だけを残し、次回の「さらに読み込む」で同じ範囲を再取得できるようにする
        if (shouldFetchTwitter === true && (isCursorConsumed(twitter_result) === false || twitter_result === null)) {
            preservedGap.twitter_cursor_id = gap.twitter_cursor_id;
            preservedGap.twitter_cursor_type = gap.twitter_cursor_type;
            preservedGap.is_twitter_exhausted = false;
        }
        // Bluesky 側も API へ到達していない場合はカーソルを消費していない
        // 中央 gap に戻した後も、片側失敗時にもう片側のカーソルまで落とさないことが重要になる
        if (shouldFetchBluesky === true && bluesky_result === null) {
            preservedGap.bluesky_cursor_id = gap.bluesky_cursor_id;
            preservedGap.is_bluesky_exhausted = false;
        }

        // 実際にレスポンスが進んだサービスだけ、返却された追加取得カーソルから次の gap を作る
        // Twitter 検索の中央 gap はサーバー指示、Bluesky 検索の続きは末尾方向だけに限定する
        const nextTwitterGaps = buildGapsFromLoadMoreCursors('Twitter', twitter_result, twitterPageTweets);
        const nextBlueskyGaps = buildGapsFromLoadMoreCursors('Bluesky', bluesky_result, blueskyPageTweets);
        consumedGapIds.push(gap.id);
        if (isGapVisible(preservedGap)) {
            replacementGaps.push(preservedGap);
        }
        replacementGaps.push(...nextTwitterGaps, ...nextBlueskyGaps);
    }

    // 処理対象の gap は一度取り除き、未消費カーソルと新しいカーソルから作り直した gap へ差し替える
    removeGapsById(consumedGapIds);
    appendGaps(replacementGaps);
    isFetching.value = false;
};

// 検索クエリが変更された場合、同じ検索クエリではなくなるのでタイムラインの内容をまっさらにする
watch(searchQuery, () => {
    resetSearchState();
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにして再取得
watch(showRetweets, () => {
    resetSearchState();
    performSearchTweets();
});

// 検索結果はアカウントごとの差が小さいため、Twitter アカウント同士の切替では維持する
// 利用可能なサービスが減る切替だけ、消費不能な古いカーソルを残さないよう検索状態を破棄する
watch(selected_account, (newAccount, oldAccount) => {
    const oldProviders = getAvailableSearchProviders(oldAccount);
    const newProviders = getAvailableSearchProviders(newAccount);
    const oldIdentity = getSearchAccountIdentity(oldAccount);
    const newIdentity = getSearchAccountIdentity(newAccount);
    // Twitter アカウント同士の切替では検索結果を維持する
    // ただし利用可能なサービスが減る切替では、押しても消費できない古い gap が残るため状態を破棄する
    if (
        (oldProviders.hasTwitter === true && newProviders.hasTwitter === false) ||
        (oldProviders.hasBluesky === true && newProviders.hasBluesky === false)
    ) {
        resetSearchState();
        return;
    }

    // サービス自体は残っていても、具体アカウントが変わるとサーバー側カーソルの持ち主が変わる
    // 検索結果の表示は維持し、次の更新だけは新アカウントの初回検索として取り直す
    if (
        oldIdentity.twitterAccountId !== null &&
        oldIdentity.twitterAccountId !== newIdentity.twitterAccountId
    ) {
        twitterNewerCursorId.value = null;
        removeServiceCursorsFromGaps('Twitter');
    }

    // Bluesky 検索の続きカーソルもアカウント単位の状態なので、紐付け先変更時にだけ破棄する
    // 投稿本体まで消すと検索タブの見た目が大きく揺れるため、未取得範囲だけを現在のアカウントに合わせる
    if (
        oldIdentity.blueskyAccountId !== null &&
        oldIdentity.blueskyAccountId !== newIdentity.blueskyAccountId
    ) {
        removeServiceCursorsFromGaps('Bluesky');
    }
});

const checkScrollPosition = () => {
    if (!scroller.value || !scroller.value.$el) return;
    // 現在他のタイミングでツイートを取得中なら常にイベントを無視
    if (isFetching.value) return;
    // 仮想スクローラーの描画リフレッシュ中なら常にイベントを無視
    if (isRefreshing.value) return;

    const container = scroller.value.$el;
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;

    // スクロール位置が下部から 30px 以内に近づいたら追加のツイートを読み込む
    if (scrollHeight - scrollTop - clientHeight < 30) {
        // 最後のアイテムが「さらに読み込む」ボタンの場合、それをクリックする
        const lastItem = flattenedItems.value[flattenedItems.value.length - 1];
        if (lastItem && !('text' in lastItem) && lastItem.type === 'load_more') {
            handleLoadMore(lastItem);
        }
    }
};

onMounted(() => {
    nextTick(() => {
        if (scroller.value && scroller.value.$el) {
            scroller.value.$el.addEventListener('scroll', checkScrollPosition);
        }
    });
});

</script>
<style lang="scss" scoped>

.tab-content--search {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: visible !important;
}

.search-header {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    height: 45px;
    padding: 6px 12px;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.search-input-wrapper {
    display: flex;
    align-items: center;
    flex-grow: 1;
    height: 100%;
    padding-left: 8px;
    margin-right: 6px;
    background-color: rgb(var(--v-theme-background-lighten-2));
    border-radius: 5px;
    transition: box-shadow 0.09s ease;

    &--focused {
        box-shadow: rgba(79, 130, 230, 60%) 0 0 0 3.5px;
    }
}

.search-input {
    flex-grow: 1;
    margin-left: 8px;
    background: none;
    border: none;
    outline: none;
    font-size: 13px;
    color: rgb(var(--v-theme-text));
}

.search-header__settings,
.search-header__refresh {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 4px 8px;
    border-radius: 5px;
    background: none;
    border: none;
    cursor: pointer;
    color: rgb(var(--v-theme-text)) !important;
    background-color: rgb(var(--v-theme-background-lighten-2));
    transition: opacity 0.15s ease;
    opacity: 1;

    &:hover {
        opacity: 0.85;
    }
}

.search-header__refresh {
    margin-left: 6px;
    background-color: rgb(var(--v-theme-twitter));
}

.search-settings {
    display: flex;
    align-items: center;
    height: 45px;
    padding: 0px 12px;
    padding-left: 20px;
    font-size: 14px;
    color: rgb(var(--v-theme-text-darken-1));
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    user-select: none;
    @include smartphone-horizontal {
        font-size: 13.5px;
    }
}

.search-tweets {
    flex-grow: 1;
    overflow-x: hidden;
    overflow-y: auto;
}

@keyframes spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

.animate-spin {
    animation: spin 1s linear infinite;
}

.search-announce {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    height: 100%;
    padding-left: 12px;
    padding-right: 5px;
    @include tablet-vertical {
        padding-left: 24px;
        padding-right: 24px;
    }

    &__heading {
        font-size: 20px;
        font-weight: bold;
        @include smartphone-horizontal {
            font-size: 16px;
        }
    }
    &__text {
        margin-top: 12px;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 13.5px;
        text-align: center;
        @include smartphone-horizontal {
            font-size: 12px;
        }
    }
}

.load-more-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 8px;
    background-color: rgba(var(--v-theme-background-lighten-2), 0.5);
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    color: rgb(var(--v-theme-twitter));
    font-size: 13px;
    transition: background-color 0.15s ease;
    cursor: pointer;

    &:hover {
        background-color: rgba(var(--v-theme-background-lighten-2), 0.9);
    }
    // タッチデバイスで hover を無効にする
    @media (hover: none) {
        &:hover {
            background-color: transparent;
        }
    }

    &:disabled {
        cursor: not-allowed;

        .load-more-button__content {
            opacity: 0.5;
        }
    }

    &__content {
        display: flex;
        align-items: center;
        transition: opacity 0.15s ease;
    }
}

</style>
