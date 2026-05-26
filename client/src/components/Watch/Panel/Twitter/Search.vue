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
import {
    appendTwitterGaps,
    buildMergedTimelineItems,
    classifyTimelineCursors,
    createEmptyMergedFeedCoverage,
    decideLoadMoreTargets,
    ILoadMoreItem,
    IMergedFeedCoverage,
    isCursorConsumed,
    ITwitterGap,
    shouldFetchBlueskyForDisplayLowerBound,
    TimelineAccountKind,
    TimelineSource,
    updateCoverageFromFetchedPage,
} from '@/components/Watch/Panel/Twitter/TweetTimelineMergeUtils';
import Message from '@/message';
import Bluesky from '@/services/Bluesky';
import Twitter, { ITimelineLoadMoreCursor, ITimelineTweetsResult, ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils, { TweetUtils } from '@/utils';

const twitterStore = useTwitterStore();
const { selected_account } = storeToRefs(twitterStore);

const tweetsByKey = ref<Map<string, ITweet>>(new Map());
const twitterGaps = ref<ITwitterGap[]>([]);
const feedCoverage = ref<IMergedFeedCoverage>(createEmptyMergedFeedCoverage());
const showSettings = ref(false);
const showRetweets = ref(false);
const isFetching = ref(false);
const isSearchFormFocused = ref(false);
const searchQuery = ref('');
const scroller = useTemplateRef('scroller');

// Twitter 検索の新着方向カーソルは、直近レスポンスの Top 相当だけを保持する
// 中央の未取得範囲は Twitter サーバー由来の gap カーソルで表現する
const twitterNewerCursorId = ref<string | null>(null);
const MAX_BLUESKY_CATCHUP_PAGES = 5;

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

const getSearchAccountKind = (): TimelineAccountKind => {
    const account = selected_account.value;
    if (account?.kind === 'Bluesky') {
        return 'Bluesky';
    }
    if (account?.kind === 'Linked') {
        return 'Linked';
    }
    return 'Twitter';
};

// フラットな構造の配列を生成する computed プロパティ
const flattenedItems = computed(() => {
    // `tweetsByKey` は順序を持たない正規化ストアなので、描画直前に必ず時刻降順へ並べ直す
    return buildMergedTimelineItems(
        [...tweetsByKey.value.values()],
        twitterGaps.value,
        feedCoverage.value,
        getSearchAccountKind(),
    );
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
    twitterGaps.value = [];
    feedCoverage.value = createEmptyMergedFeedCoverage();
    twitterNewerCursorId.value = null;
};

const filterTweetsByRetweetFlag = (tweets: ITweet[]) => {
    // 検索タブではリツイート非表示が既定なので、通常検索と続き取得で同じ条件を必ず通す
    if (showRetweets.value === true) {
        return tweets;
    }
    return tweets.filter(tweet => !tweet.retweeted_tweet);
};

const addFetchedTweetsToSearch = (
    twitterPageTweets: ITweet[],
    blueskyPageTweets: ITweet[],
    existingIds: Set<string>,
) => {
    // 検索結果の表示条件は取得結果を保存する前に適用する
    // 取得範囲はフィルター前ページで更新し、非表示投稿だけのページでも古い方向カーソルを失わない
    const twitterTweets = filterTweetsByRetweetFlag(twitterPageTweets);
    const blueskyTweets = filterTweetsByRetweetFlag(blueskyPageTweets);
    const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
    const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
    const uniqueTweets = TweetUtils.sortTweetsByCreatedAt([
        ...twitterUniqueTweets,
        ...blueskyUniqueTweets,
    ]);

    if (uniqueTweets.length > 0) {
        addTweetsToMap(uniqueTweets);
    }
};

const applyFetchedPageState = (
    source: TimelineSource,
    result: ITimelineTweetsResult | null,
    pageTweets: ITweet[],
    options: { should_preserve_older_state?: boolean; should_keep_older_uninitialized_when_missing?: boolean } = {},
) => {
    if (isCursorConsumed(result) === false) {
        return;
    }

    // 検索でも Bluesky の古い方向カーソルは取得範囲の境界として扱う
    // Twitter が返した中央 gap だけを表示用の未取得範囲として追加する
    const coverageKey = source === 'Twitter' ? 'twitter' : 'bluesky';
    const nextCoverage = updateCoverageFromFetchedPage(feedCoverage.value[coverageKey], result, pageTweets, options);
    feedCoverage.value = {
        ...feedCoverage.value,
        [coverageKey]: nextCoverage,
    };

    const classifiedCursors = classifyTimelineCursors(source, result, pageTweets);
    if (classifiedCursors.twitter_gaps.length > 0) {
        twitterGaps.value = appendTwitterGaps(twitterGaps.value, classifiedCursors.twitter_gaps);
    }
};

const removeTwitterGapById = (gapId: string | null) => {
    if (gapId === null) {
        return;
    }
    twitterGaps.value = twitterGaps.value.filter(gap => gap.id !== gapId);
};

const fetchBlueskyUntilDisplayLowerBound = async (
    blueskyHandle: string | null,
    shouldContinue: () => boolean = () => true,
) => {
    if (blueskyHandle === null) {
        return;
    }

    // 混合検索でも表示下端は Twitter の取得範囲に合わせる
    // Bluesky の追加検索は画面の末尾を埋める分だけ行い、Twitter の中央 gap には混ぜない
    for (let pageIndex = 0; pageIndex < MAX_BLUESKY_CATCHUP_PAGES; pageIndex++) {
        if (shouldContinue() === false) {
            break;
        }
        if (shouldFetchBlueskyForDisplayLowerBound(feedCoverage.value, getSearchAccountKind()) === false) {
            break;
        }
        const blueskyCursorId = feedCoverage.value.bluesky.older_cursor;
        if (blueskyCursorId === null) {
            break;
        }
        const existingIds = createExistingTweetIds();
        const nextResult = await Bluesky.searchPosts(blueskyHandle, searchQuery.value, blueskyCursorId);
        if (nextResult === null) {
            break;
        }
        if (shouldContinue() === false) {
            break;
        }
        const blueskyPageTweets = nextResult.tweets;
        addFetchedTweetsToSearch([], blueskyPageTweets, existingIds);
        applyFetchedPageState('Bluesky', nextResult, blueskyPageTweets);
    }
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

const isSameSearchAccountIdentity = (
    first: ReturnType<typeof getSearchAccountIdentity>,
    second: ReturnType<typeof getSearchAccountIdentity>,
) => {
    return (
        first.twitterAccountId === second.twitterAccountId &&
        first.blueskyAccountId === second.blueskyAccountId
    );
};

const removeServicePagingState = (service: 'Twitter' | 'Bluesky') => {
    // 検索結果本体は維持し、切替先で使えないカーソルだけを落とす
    // Twitter の中央 gap は Twitter アカウントに紐づくため、Twitter 切替時は安全側で破棄する
    if (service === 'Twitter') {
        twitterGaps.value = [];
        feedCoverage.value = {
            ...feedCoverage.value,
            twitter: createEmptyMergedFeedCoverage().twitter,
        };
        twitterNewerCursorId.value = null;
        return;
    }
    feedCoverage.value = {
        ...feedCoverage.value,
        bluesky: createEmptyMergedFeedCoverage().bluesky,
    };
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
    const requestSearchQuery = searchQuery.value;
    const requestShowRetweets = showRetweets.value;
    const account = selected_account.value;
    const requestAccountIdentity = getSearchAccountIdentity(account);
    // 重複判定は、取得結果を追加する前の状態を基準に固定する
    const existingIds = createExistingTweetIds();
    // 紐付けアカウントでは Twitter と Bluesky の検索を並列実行し、片方だけ連携している場合は不要な API を呼ばない
    const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
        account.kind === 'Twitter' || account.kind === 'Linked' ?
            Twitter.searchTweets(account.kind === 'Twitter' ? account.twitter_account.screen_name : account.account_link.twitter_account.screen_name, query, cursor_id, 'Top') :
            Promise.resolve(null),
        account.kind === 'Bluesky' || account.kind === 'Linked' ?
            // Bluesky の検索カーソルは古い方向の続きなので、検索更新では常にカーソルなしで最新検索結果を取り直す
            Bluesky.searchPosts(account.kind === 'Bluesky' ? account.bluesky_account.handle : account.account_link.bluesky_account.handle, requestSearchQuery) :
            Promise.resolve(null),
    ]);

    // 検索語・表示条件・アカウントが変わった後に古いレスポンスを書き込むと、別条件のカーソルが混ざる
    // 監視処理側で状態を初期化しても進行中の非同期処理は止まらないため、反映直前に再確認する
    if (
        requestSearchQuery !== searchQuery.value ||
        requestShowRetweets !== showRetweets.value ||
        isSameSearchAccountIdentity(requestAccountIdentity, getSearchAccountIdentity(selected_account.value)) === false
    ) {
        isFetching.value = false;
        return;
    }

    const isSameSearchRequest = () => (
        requestSearchQuery === searchQuery.value &&
        requestShowRetweets === showRetweets.value &&
        isSameSearchAccountIdentity(requestAccountIdentity, getSearchAccountIdentity(selected_account.value)) === true
    );

    const twitter_result = getSearchFetchResult(twitter_settled_result);
    const bluesky_result = getSearchFetchResult(bluesky_settled_result);
    const result = twitter_result ?? bluesky_result;
    if (result && result.tweets) {
        const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
        const blueskyPageTweets = [...(bluesky_result?.tweets ?? [])];

        // Twitter の新着方向カーソルは表示対象の有無に関係なく、実レスポンスが進んだときだけ更新する
        // 制限による空応答では既存カーソルを維持し、次回も同じ位置から検索更新できるようにする
        if (isCursorConsumed(twitter_result) === true && twitter_result?.newer_cursor_id) {
            twitterNewerCursorId.value = twitter_result.newer_cursor_id;
        }

        addFetchedTweetsToSearch(twitterPageTweets, blueskyPageTweets, existingIds);
        // 通常検索は新着方向カーソルの取得であり、古い方向の終端確認ではない
        // 末尾状態が確立するまでは `Older` を採用し、確立後の通常検索では巻き戻りを防ぐ
        applyFetchedPageState('Twitter', twitter_result, twitterPageTweets, {
            should_preserve_older_state: feedCoverage.value.twitter.older_cursor !== null || feedCoverage.value.twitter.is_older_exhausted === true,
            should_keep_older_uninitialized_when_missing: true,
        });
        applyFetchedPageState('Bluesky', bluesky_result, blueskyPageTweets);
        await fetchBlueskyUntilDisplayLowerBound(
            account.kind === 'Bluesky' ? account.bluesky_account.handle :
                account.kind === 'Linked' ? account.account_link.bluesky_account.handle : null,
            isSameSearchRequest,
        );

        // Bluesky の補完検索中に条件が変わった場合も、旧条件の統合結果を画面へ混ぜない
        if (
            requestSearchQuery !== searchQuery.value ||
            requestShowRetweets !== showRetweets.value ||
            isSameSearchAccountIdentity(requestAccountIdentity, getSearchAccountIdentity(selected_account.value)) === false
        ) {
            isFetching.value = false;
            return;
        }

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

    const query = `${searchQuery.value}${showRetweets.value ? 'include:nativeretweets' : ''}`;
    const requestSearchQuery = searchQuery.value;
    const requestShowRetweets = showRetweets.value;
    const account = selected_account.value;
    const requestAccountIdentity = getSearchAccountIdentity(account);
    const twitterScreenName = account.kind === 'Twitter' ? account.twitter_account.screen_name :
        account.kind === 'Linked' ? account.account_link.twitter_account.screen_name : null;
    const blueskyHandle = account.kind === 'Bluesky' ? account.bluesky_account.handle :
        account.kind === 'Linked' ? account.account_link.bluesky_account.handle : null;
    const loadMoreTargets = decideLoadMoreTargets(item, feedCoverage.value, getSearchAccountKind());
    const shouldFetchTwitter = loadMoreTargets.should_fetch_twitter === true && twitterScreenName !== null && loadMoreTargets.twitter_cursor_id !== null;
    const shouldFetchBluesky = loadMoreTargets.should_fetch_bluesky === true && blueskyHandle !== null && loadMoreTargets.bluesky_cursor_id !== null;
    if (shouldFetchTwitter === false && shouldFetchBluesky === false) {
        isFetching.value = false;
        return;
    }

    const existingIds = createExistingTweetIds();
    const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
        shouldFetchTwitter === true ?
            Twitter.searchTweets(
                twitterScreenName,
                query,
                loadMoreTargets.twitter_cursor_id!,
                getTwitterSearchCursorType(loadMoreTargets.twitter_cursor_type ?? undefined),
            ) :
            Promise.resolve(null),
        shouldFetchBluesky === true ?
            Bluesky.searchPosts(blueskyHandle, requestSearchQuery, loadMoreTargets.bluesky_cursor_id!) :
            Promise.resolve(null),
    ]);

    // 続き取得中に検索条件が変わった場合、取得済みの古い範囲を新しい検索結果へ差し込まない
    // 特に中央 gap は Twitter アカウントと検索語に紐づくため、反映直前の確認が必要になる
    if (
        requestSearchQuery !== searchQuery.value ||
        requestShowRetweets !== showRetweets.value ||
        isSameSearchAccountIdentity(requestAccountIdentity, getSearchAccountIdentity(selected_account.value)) === false
    ) {
        isFetching.value = false;
        return;
    }

    const isSameSearchRequest = () => (
        requestSearchQuery === searchQuery.value &&
        requestShowRetweets === showRetweets.value &&
        isSameSearchAccountIdentity(requestAccountIdentity, getSearchAccountIdentity(selected_account.value)) === true
    );

    const twitter_result = getSearchFetchResult(twitter_settled_result);
    const bluesky_result = getSearchFetchResult(bluesky_settled_result);
    const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
    const blueskyPageTweets = [...(bluesky_result?.tweets ?? [])];
    addFetchedTweetsToSearch(twitterPageTweets, blueskyPageTweets, existingIds);

    // Twitter の中央 gap は Twitter 側が実際に進んだ場合だけ消費する
    // 空応答や通信失敗では同じ検索範囲を後から再取得できるように残す
    if (isCursorConsumed(twitter_result) === true) {
        removeTwitterGapById(loadMoreTargets.consumed_twitter_gap_id);
    }
    applyFetchedPageState('Twitter', twitter_result, twitterPageTweets, {
        should_preserve_older_state: item.type === 'twitter_gap',
    });
    applyFetchedPageState('Bluesky', bluesky_result, blueskyPageTweets);
    // 中央 gap は Twitter だけを埋める操作なので、Bluesky 補充は末尾取得の後だけ行う
    if (item.type === 'tail') {
        await fetchBlueskyUntilDisplayLowerBound(blueskyHandle, isSameSearchRequest);
    }

    // Bluesky 補充中の条件変更でも、古い検索結果を現在の画面へ混ぜない
    if (
        requestSearchQuery !== searchQuery.value ||
        requestShowRetweets !== showRetweets.value ||
        isSameSearchAccountIdentity(requestAccountIdentity, getSearchAccountIdentity(selected_account.value)) === false
    ) {
        isFetching.value = false;
        return;
    }

    await nextTick();
    refreshScroller();
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
        removeServicePagingState('Twitter');
    }

    // Bluesky 検索の続きカーソルもアカウント単位の状態なので、紐付け先変更時にだけ破棄する
    // 投稿本体まで消すと検索タブの見た目が大きく揺れるため、未取得範囲だけを現在のアカウントに合わせる
    if (
        oldIdentity.blueskyAccountId !== null &&
        oldIdentity.blueskyAccountId !== newIdentity.blueskyAccountId
    ) {
        removeServicePagingState('Bluesky');
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
        if (lastItem && !('text' in lastItem)) {
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
