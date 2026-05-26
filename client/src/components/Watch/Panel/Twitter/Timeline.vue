<template>
    <div class="tab-content tab-content--timeline">
        <div class="timeline-header">
            <div class="search-input-wrapper" :class="{'search-input-wrapper--focused': isFilterFormFocused}">
                <Icon icon="fluent:filter-16-filled" height="18px" />
                <input
                    v-model="filterQuery"
                    class="search-input"
                    type="search"
                    enterkeyhint="search"
                    placeholder="タイムラインを絞り込む"
                    @focus="isFilterFormFocused = true"
                    @blur="isFilterFormFocused = false"
                />
            </div>
            <div class="d-flex align-center ml-auto h-100">
                <button v-ripple class="timeline-header__settings" @click="toggleSettings">
                    <Icon icon="fluent:settings-16-filled" width="20" />
                </button>
                <button v-ripple class="timeline-header__refresh" style="color: rgb(var(--v-theme-twitter-lighten-1))" @click="fetchTimelineTweets"
                    v-ftooltip.bottom="'タイムラインを更新'">
                    <Icon icon="ic:round-refresh" width="20" :class="isFetching ? 'animate-spin' : ''" />
                </button>
            </div>
        </div>
        <div v-if="showSettings" class="timeline-settings">
            <div class="timeline-settings__item">
                <v-switch id="show_retweets" color="primary" density="compact" hide-details v-model="showRetweets" />
                <label class="ml-4 cursor-pointer" for="show_retweets">リツイートを表示する</label>
            </div>
            <div class="timeline-settings__item">
                <v-switch id="is_not_filter" color="primary" density="compact" hide-details v-model="isNotFilter" />
                <label class="ml-4 cursor-pointer" for="is_not_filter">指定文字列を含まないツイートを表示</label>
            </div>
        </div>
        <VirtuaList ref="scroller" class="timeline-tweets" :data="flattenedItems" #default="{ item }"
            v-show="flattenedItems.length > 0">
            <div class="timeline-item">
                <Tweet v-if="'text' in item" :tweet="item" />
                <button v-else class="load-more-button" @click="handleLoadMore(item)" :disabled="isFetching">
                    <div class="load-more-button__content">
                        <Icon icon="ic:round-refresh" width="20" :class="isFetching ? 'animate-spin' : ''" class="mr-2" />
                        ツイートをさらに表示
                    </div>
                </button>
            </div>
        </VirtuaList>
        <div class="timeline-announce" v-show="flattenedItems.length === 0">
            <div class="timeline-announce__heading">{{ filterQuery ? '絞り込み条件に一致するツイートがありません。' : 'まだツイートがありません。' }}</div>
            <div class="timeline-announce__text">
                <p class="mt-0 mb-0" v-if="filterQuery">
                    絞り込み条件を変更するか、右上の更新ボタンを<br>押して、タイムラインを更新してください。
                </p>
                <p class="mt-0 mb-0" v-else>
                    右上の更新ボタンを押すと、最新の<br>ホームタイムラインを時系列で表示できます。
                </p>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { VList as VirtuaList } from 'virtua/vue';
import { computed, nextTick, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue';

import Tweet from '@/components/Watch/Panel/Twitter/Tweet.vue';
import {
    appendTwitterGaps,
    buildMergedTimelineItems,
    classifyTimelineCursors,
    createEmptyMergedFeedCoverage,
    decideLoadMoreTargets,
    getOldestTweet,
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
import Utils, { TweetUtils, dayjs } from '@/utils';

const twitterStore = useTwitterStore();
const { selected_account, selected_twitter_account } = storeToRefs(twitterStore);

const SEEN_TWEET_DWELL_MILLISECONDS = 500;
const SEEN_TWEET_IDS_LIMIT = 300;

const props = defineProps<{
    isTwitterPanelVisible: boolean;
    isTimelineTabActive: boolean;
}>();

interface ISeenTweetTrackingState {
    pendingSeenTweetIds: string[];
    confirmedVisibleTweetIds: Set<string>;
}

const MAX_BLUESKY_CATCHUP_PAGES = 5;

const tweetsByKey = ref<Map<string, ITweet>>(new Map());
const twitterGaps = ref<ITwitterGap[]>([]);
const feedCoverage = ref<IMergedFeedCoverage>(createEmptyMergedFeedCoverage());
const showSettings = ref(false);
const showRetweets = ref(true);
const isFetching = ref(false);
const scroller = useTemplateRef('scroller');
const isInitialFetchPending = ref(true);

// タイムラインタブが実際に表示されているかを判定
const shouldAutoFetchTimeline = computed(() => props.isTwitterPanelVisible === true && props.isTimelineTabActive === true);

// Twitter の新着方向カーソルは、本家 Web App と同じく直近レスポンスの Top 相当だけを保持する
// 2 回前のカーソルで重複範囲を作る方式は使わず、サーバーが返す gap カーソルを未取得範囲の正本にする
const twitterNewerCursorId = ref<string | null>(null);

// Twitter Web App の seenTweetIds に相当する、次回のタイムライン取得時に送信する短期キュー
// 本家の挙動に合わせ、同一キュー内で同じツイート ID が複数回入ることは許容する
const seenTweetTrackingByScreenName = new Map<string, ISeenTweetTrackingState>();
const visibleTweetTimers = new Map<string, number>();

// フィルタリング用の状態
const filterQuery = ref('');
const isFilterFormFocused = ref(false);
const isNotFilter = ref(false);
const isRefreshingFilter = ref(false);  // フィルタリング更新中かどうかのフラグ

// フィルタクエリまたは NOT フィルタの設定が変更された際に仮想スクローラーをリフレッシュ
watch([filterQuery, isNotFilter], async () => {
    isRefreshingFilter.value = true;  // 更新中フラグを立てる
    await nextTick();  // DOM の更新を待つ
    isRefreshingFilter.value = false;  // フラグを下ろす
});

const createExistingTweetIds = () => {
    return new Set([...tweetsByKey.value.keys()]);
};

const addTweetsToMap = (tweets: ITweet[]) => {
    if (tweets.length === 0) {
        return;
    }

    // Vue の Map 監視は破壊的更新でも追従できるが、ここでは参照ごと差し替えて computed の再計算点を明確にする
    const nextTweetsByKey = new Map(tweetsByKey.value);
    for (const tweet of tweets) {
        nextTweetsByKey.set(TweetUtils.getTweetIdentityKey(tweet), tweet);
    }
    tweetsByKey.value = nextTweetsByKey;
};

const getTimelineAccountKind = (): TimelineAccountKind => {
    const account = selected_account.value;
    if (account?.kind === 'Bluesky') {
        return 'Bluesky';
    }
    if (account?.kind === 'Linked') {
        return 'Linked';
    }
    return 'Twitter';
};

const getTimelineAccountIdentity = (account: typeof selected_account.value) => {
    // 取得中にアカウントが切り替わった場合、古いレスポンスを現在の表示状態へ混ぜない
    // 画面上の種別だけでは紐付け先変更を検知できないため、実アカウント ID まで含めて比較する
    if (account?.kind === 'Twitter') {
        return `Twitter:${account.twitter_account.id}`;
    }
    if (account?.kind === 'Bluesky') {
        return `Bluesky:${account.bluesky_account.id}`;
    }
    if (account?.kind === 'Linked') {
        return `Linked:${account.account_link.twitter_account.id}:${account.account_link.bluesky_account.id}`;
    }
    return null;
};

// フラットな構造の配列を生成する computed プロパティ
const flattenedItems = computed(() => {
    // フィルタリング更新中は空配列を返す
    if (isRefreshingFilter.value) {
        return [];
    }

    // `tweetsByKey` は順序を持たない正規化ストアなので、描画直前に必ず時刻降順へ並べ直す
    const sortedTweets = TweetUtils.sortTweetsByCreatedAtInPlace([...tweetsByKey.value.values()]);
    const filteredTweets = sortedTweets.filter(tweet => {
        if (!filterQuery.value) {
            return true;
        }
        // リツイートの場合は retweeted_tweet の text を使用する
        const targetText = tweet.retweeted_tweet ? tweet.retweeted_tweet.text : tweet.text;
        const hasText = targetText.toLowerCase().includes(filterQuery.value.toLowerCase());
        return isNotFilter.value ? !hasText : hasText;
    });
    const items = buildMergedTimelineItems(
        filteredTweets,
        twitterGaps.value,
        feedCoverage.value,
        getTimelineAccountKind(),
    );

    // フィルタリング中で、かつツイートが1件も含まれていない場合は空配列を返す
    if (filterQuery.value && !items.some(item => 'text' in item)) {
        return [];
    }

    return items;
});

const getSeenTweetTrackingState = (screenName: string | null | undefined) => {
    if (!screenName) {
        return null;
    }
    if (!seenTweetTrackingByScreenName.has(screenName)) {
        seenTweetTrackingByScreenName.set(screenName, {
            pendingSeenTweetIds: [],
            confirmedVisibleTweetIds: new Set<string>(),
        });
    }
    return seenTweetTrackingByScreenName.get(screenName)!;
};

// 選択中の Twitter アカウントに紐づく seenTweetIds 管理状態を取得する
// 本家と同様にアカウントごとに短期キューを分離し、アカウント切り替え後に戻った場合も未送信分を維持する
const getCurrentSeenTweetTrackingState = () => {
    return getSeenTweetTrackingState(selected_twitter_account.value?.screen_name);
};

// seenTweetIds の送信キューにツイート ID を追加する
// キューが伸びすぎると KonomiTV API への GET クエリが長くなるため、古い ID から破棄する
const enqueueSeenTweetId = (screenName: string, tweetId: string) => {
    const state = seenTweetTrackingByScreenName.get(screenName);
    if (!state) {
        return;
    }

    state.pendingSeenTweetIds.push(tweetId);
    if (state.pendingSeenTweetIds.length > SEEN_TWEET_IDS_LIMIT) {
        state.pendingSeenTweetIds.splice(0, state.pendingSeenTweetIds.length - SEEN_TWEET_IDS_LIMIT);
    }
};

// 次回のタイムライン取得で送信する seenTweetIds を取り出し、本家の clearTweets() 相当に合わせてキューを空にする
const dequeuePendingSeenTweetIds = () => {
    const state = getCurrentSeenTweetTrackingState();
    if (!state) {
        return [];
    }

    const seenTweetIds = [...state.pendingSeenTweetIds];
    state.pendingSeenTweetIds = [];
    return seenTweetIds;
};

// 現在 VirtuaList 上で実表示範囲に入っているツイート ID を取得する
// findStartIndex() / findEndIndex() は overscan を含まない実表示範囲を返すため、描画済みだが見えていないツイートを除外できる
const getVisibleTweetIds = () => {
    const visibleTweetIds = new Set<string>();
    if (!scroller.value) {
        return visibleTweetIds;
    }

    const startIndex = scroller.value.findStartIndex();
    const endIndex = scroller.value.findEndIndex();
    for (let itemIndex = startIndex; itemIndex <= endIndex; itemIndex++) {
        const item = flattenedItems.value[itemIndex];
        if (item && 'text' in item && item.source === 'Twitter') {
            visibleTweetIds.add(item.id);
        }
    }
    return visibleTweetIds;
};

// 実表示範囲に 0.5 秒以上入り続けたツイートを seenTweetIds の送信キューに追加する
// 一瞬だけ高速スクロールで通過したツイートは、タイマー完了時に表示範囲外になっていれば seen 扱いにしない
const updateSeenTweetTracking = () => {
    const screenName = selected_twitter_account.value?.screen_name;
    const state = getCurrentSeenTweetTrackingState();
    if (!screenName || !state) {
        return;
    }

    const visibleTweetIds = getVisibleTweetIds();

    for (const [tweetId, timerId] of visibleTweetTimers.entries()) {
        if (visibleTweetIds.has(tweetId) === false) {
            window.clearTimeout(timerId);
            visibleTweetTimers.delete(tweetId);
        }
    }

    for (const tweetId of state.confirmedVisibleTweetIds) {
        if (visibleTweetIds.has(tweetId) === false) {
            state.confirmedVisibleTweetIds.delete(tweetId);
        }
    }

    for (const tweetId of visibleTweetIds) {
        if (visibleTweetTimers.has(tweetId) || state.confirmedVisibleTweetIds.has(tweetId)) {
            continue;
        }

        const timerId = window.setTimeout(() => {
            // タイマー開始後にアカウントが切り替わった場合、異なるアカウントの seenTweetIds に混ぜない
            if (selected_twitter_account.value?.screen_name !== screenName) {
                visibleTweetTimers.delete(tweetId);
                return;
            }

            const currentVisibleTweetIds = getVisibleTweetIds();
            if (currentVisibleTweetIds.has(tweetId)) {
                enqueueSeenTweetId(screenName, tweetId);
                state.confirmedVisibleTweetIds.add(tweetId);
            }
            visibleTweetTimers.delete(tweetId);
        }, SEEN_TWEET_DWELL_MILLISECONDS);
        visibleTweetTimers.set(tweetId, timerId);
    }
};

// アカウント切り替えやタイムライン再初期化時に、現在表示中のツイートに紐づく判定タイマーだけを破棄する
// pendingSeenTweetIds はアカウントごとの短期キューとして保持し、ブラウザリロードまでは維持する
const clearVisibleTweetTimers = () => {
    for (const timerId of visibleTweetTimers.values()) {
        window.clearTimeout(timerId);
    }
    visibleTweetTimers.clear();
};

// タイムラインが表示されなくなったアカウントでは、現在表示中として扱っていたツイート ID だけを破棄する
// pendingSeenTweetIds は未送信の短期キューなので、ここでは破棄しない
const clearConfirmedVisibleTweetIds = (screenName: string | undefined) => {
    if (!screenName) {
        return;
    }
    seenTweetTrackingByScreenName.get(screenName)?.confirmedVisibleTweetIds.clear();
};

watch(flattenedItems, async () => {
    await nextTick();
    updateSeenTweetTracking();
});

// タイムラインの自動取得を必要に応じて実行
const tryAutoFetchTimeline = () => {
    if (isInitialFetchPending.value === true && shouldAutoFetchTimeline.value === true) {
        void fetchTimelineTweets();
    }
};

watch(shouldAutoFetchTimeline, () => {
    tryAutoFetchTimeline();
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

const getTimelineFetchResult = (result: PromiseSettledResult<ITimelineTweetsResult | null>) => {
    // ホームタイムラインは Twitter / Bluesky を独立して取得するため、片方の例外は null に正規化する
    if (result.status === 'fulfilled') {
        return result.value;
    }
    console.error('Timeline API request failed unexpectedly.', result.reason);
    return null;
};

const getTwitterTimelineCursorType = (cursorType: ITimelineLoadMoreCursor['cursor_type'] | undefined) => {
    // Twitter のホームタイムラインでは、Top 相当だけ 40 件、それ以外の追加取得は 20 件でリクエストする
    // KonomiTV の Older は Twitter Web App の Bottom 相当なので、API パラメータへ変換する
    if (cursorType === 'Gap' || cursorType === 'ShowMore') {
        return cursorType;
    }
    return 'Bottom';
};

const filterTimelineTweets = (tweets: ITweet[]) => {
    return tweets.filter(tweet => {
        let result = true;
        // 「リツイートを表示する」がオフの場合はリツイートのツイートを除外
        if (showRetweets.value === false) {
            result = !tweet.retweeted_tweet;
        }
        // 自分の RT を除外
        if (tweet.source === 'Twitter' && tweet.retweeted_tweet !== null && tweet.user.screen_name === selected_twitter_account.value?.screen_name) {
            result = false;
        }
        return result;
    });
};

const addFetchedTweetsToTimeline = (
    twitterPageTweets: ITweet[],
    blueskyPageTweets: ITweet[],
    existingIds: Set<string>,
) => {
    // 表示フィルターは投稿追加前にサービス別で適用し、取得範囲の計算にはフィルター前のページを使う
    // ここで混ぜてしまうと、非表示投稿だけのページで古い方向カーソルやクランプ下端を誤って失う
    const twitterTweets = filterTimelineTweets(twitterPageTweets);
    const blueskyTweets = filterTimelineTweets(blueskyPageTweets);
    const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
    const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
    const uniqueTweets = TweetUtils.sortTweetsByCreatedAtInPlace([
        ...twitterUniqueTweets,
        ...blueskyUniqueTweets,
    ]);

    if (uniqueTweets.length > 0) {
        addTweetsToMap(uniqueTweets);
    }
};

const restorePendingSeenTweetIds = (
    seenTweetIds: string[],
    screenName: string | null | undefined = selected_twitter_account.value?.screen_name,
) => {
    if (seenTweetIds.length === 0) {
        return;
    }

    const state = getSeenTweetTrackingState(screenName);
    if (!state) {
        return;
    }

    // Twitter 側の 30 秒制限で空応答になった場合、サーバーには seenTweetIds が届いていても Twitter には転送されない
    // 新しく溜まった閲覧済み情報を優先して残すため、上限超過時は古い側から切り落とす
    state.pendingSeenTweetIds = [...seenTweetIds, ...state.pendingSeenTweetIds].slice(-SEEN_TWEET_IDS_LIMIT);
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

    // 取得結果はまず取得範囲と Twitter 中央 gap に分類する
    // Bluesky の古い方向カーソルは取得範囲の境界であり、中央 gap には絶対に混ぜない
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

    // 混合表示では Twitter の表示下端を満たす分だけ Bluesky を補充する
    // Bluesky の古い方向カーソルはユーザー操作の中央 gap ではなく、表示範囲を埋めるための内部境界として扱う
    for (let pageIndex = 0; pageIndex < MAX_BLUESKY_CATCHUP_PAGES; pageIndex++) {
        if (shouldContinue() === false) {
            break;
        }
        if (shouldFetchBlueskyForDisplayLowerBound(feedCoverage.value, getTimelineAccountKind()) === false) {
            break;
        }
        const blueskyCursorId = feedCoverage.value.bluesky.older_cursor;
        if (blueskyCursorId === null) {
            break;
        }
        const existingIds = createExistingTweetIds();
        const nextResult = await Bluesky.getHomeTimeline(blueskyHandle, blueskyCursorId);
        if (nextResult === null) {
            break;
        }
        if (shouldContinue() === false) {
            break;
        }
        const blueskyPageTweets = nextResult.tweets;
        addFetchedTweetsToTimeline([], blueskyPageTweets, existingIds);
        applyFetchedPageState('Bluesky', nextResult, blueskyPageTweets);
    }
};

const toggleSettings = () => {
    showSettings.value = !showSettings.value;
};

let isFirstFetchCompleted = false;
const fetchTimelineTweets = async () => {
    isInitialFetchPending.value = false;
    // 更新ボタン連打や自動取得の重複でブロック配列が壊れないよう、取得中は後続の実行を止める
    if (isFetching.value) return;
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_account.value) {
        // 初回自動取得では未連携の警告を出さず、ユーザー操作後だけ通知する
        if (isFirstFetchCompleted) {
            Message.warning('タイムラインを更新するには、Twitter または Bluesky アカウントと連携してください。');
        }
        tweetsByKey.value = new Map();
        twitterGaps.value = [];
        feedCoverage.value = createEmptyMergedFeedCoverage();
        clearVisibleTweetTimers();
        isFetching.value = false;
        isFirstFetchCompleted = true;
        return;
    }
    isFirstFetchCompleted = true;

    // Twitter の通常更新では、直近レスポンスで返された新着方向カーソルだけを送る
    // 未取得範囲はサーバー由来の gap カーソルで表現するため、重複取得用の古いカーソル履歴は持たない
    const cursor_id = twitterNewerCursorId.value ?? undefined;

    const seenTweetIds = dequeuePendingSeenTweetIds();

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    const account = selected_account.value;
    const existingIds = createExistingTweetIds();
    const isLinkedAccount = account.kind === 'Linked';
    const requestAccountIdentity = getTimelineAccountIdentity(account);
    const twitterScreenName = account.kind === 'Twitter' ? account.twitter_account.screen_name :
        account.kind === 'Linked' ? account.account_link.twitter_account.screen_name : null;
    const blueskyHandle = account.kind === 'Bluesky' ? account.bluesky_account.handle :
        account.kind === 'Linked' ? account.account_link.bluesky_account.handle : null;
    // 紐付けアカウントでも最初の 1 ページは並列取得し、Twitter の結果が取れた後だけ Bluesky の追加取得を検討する
    const [twitter_settled_result, bluesky_first_settled_result] = await Promise.allSettled([
        // Twitter は Web App の HomeLatestTimeline と同じく、更新履歴の新着方向カーソルと `seenTweetIds` を渡す
        // 時間を空けた更新では Twitter 側が最新数十件だけを返すため、後段で gap ボタンを残して中間を埋められるようにする
        twitterScreenName !== null ?
            Twitter.getHomeTimeline(twitterScreenName, cursor_id, 'Top', seenTweetIds) :
            Promise.resolve(null),
        blueskyHandle !== null ?
            // Bluesky のカーソルは「次の古いページ」専用なので、通常更新では必ず最新ページを取り直す
            // 古いカーソルを更新に使うと、時間を置いた後に最新投稿へ戻れず Twitter 側との時系列マージが壊れる
            Bluesky.getHomeTimeline(blueskyHandle) :
            Promise.resolve(null),
    ]);
    const twitter_result = getTimelineFetchResult(twitter_settled_result);

    // 取得中にアカウントが切り替わった場合、旧アカウントのレスポンスは現在の状態へ反映しない
    // 監視処理側の初期化だけでは進行中の非同期処理までは止められないため、ここで明示的に捨てる
    if (getTimelineAccountIdentity(selected_account.value) !== requestAccountIdentity) {
        if (isCursorConsumed(twitter_result) === false || (twitterScreenName !== null && twitter_result === null)) {
            restorePendingSeenTweetIds(seenTweetIds, twitterScreenName);
        }
        isFetching.value = false;
        isInitialFetchPending.value = true;
        tryAutoFetchTimeline();
        return;
    }

    if (isCursorConsumed(twitter_result) === false) {
        restorePendingSeenTweetIds(seenTweetIds);
    }
    // 表示用フィルターとページ境界計算を分け、非表示対象だけのページでもカーソルを失わないようにする
    const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
    const targetOldestTweet = getOldestTweet(twitterPageTweets);
    const targetOldestCreatedAt = targetOldestTweet !== null ? String(targetOldestTweet.created_at) : null;
    let bluesky_result = getTimelineFetchResult(bluesky_first_settled_result);
    if (isLinkedAccount === true && blueskyHandle !== null && bluesky_result !== null) {
        // 初回ページの結果を使った上で、Twitter の取得範囲に届いていない場合だけ追加ページを取得する
        // Promise.allSettled の結果を直接再利用できないため、同じ条件を満たすまで明示的に追加取得する
        const collectedTweets = [...bluesky_result.tweets];
        let loadMoreCursorId = bluesky_result.load_more_cursors[0]?.cursor_id;
        let loadMoreCursors = bluesky_result.load_more_cursors;
        if (targetOldestCreatedAt !== null) {
            const targetOldestTime = dayjs(targetOldestCreatedAt).valueOf();
            for (let pageIndex = 0; pageIndex < MAX_BLUESKY_CATCHUP_PAGES; pageIndex++) {
                const oldestTweet = getOldestTweet(collectedTweets);
                const hasReachedTarget = oldestTweet !== null && dayjs(oldestTweet.created_at).valueOf() < targetOldestTime;
                const hasOverlap = collectedTweets.some(tweet => existingIds.has(TweetUtils.getTweetIdentityKey(tweet)));
                if (hasReachedTarget === true || hasOverlap === true || !loadMoreCursorId) {
                    break;
                }
                const nextResult = await Bluesky.getHomeTimeline(blueskyHandle, loadMoreCursorId);
                if (!nextResult) {
                    break;
                }
                collectedTweets.push(...nextResult.tweets);
                loadMoreCursorId = nextResult.load_more_cursors[0]?.cursor_id;
                loadMoreCursors = nextResult.load_more_cursors;
            }
        }
        bluesky_result = {
            ...bluesky_result,
            tweets: collectedTweets,
            load_more_cursors: loadMoreCursors,
        };
    }

    // Bluesky の補完中にもアカウントが切り替わる可能性がある
    // ここで再確認し、古い混合結果が新しいアカウントの `tweetsByKey` へ入るのを防ぐ
    if (getTimelineAccountIdentity(selected_account.value) !== requestAccountIdentity) {
        isFetching.value = false;
        isInitialFetchPending.value = true;
        tryAutoFetchTimeline();
        return;
    }

    const isSameRequestAccount = () => getTimelineAccountIdentity(selected_account.value) === requestAccountIdentity;
    const result = twitter_result ?? bluesky_result;
    if (result && result.tweets) {
        const blueskyPageTweets = bluesky_result?.tweets ?? [];

        // Twitter の新着方向カーソルは表示対象の有無に関係なく、実レスポンスが進んだときだけ更新する
        // 30 秒制限の空応答では既存カーソルを維持し、次回も同じ位置から更新できるようにする
        if (isCursorConsumed(twitter_result) === true && twitter_result?.newer_cursor_id) {
            twitterNewerCursorId.value = twitter_result.newer_cursor_id;
        }

        addFetchedTweetsToTimeline(twitterPageTweets, blueskyPageTweets, existingIds);
        // 通常更新は新着方向カーソルの取得であり、古い方向の終端確認ではない
        // 末尾状態が確立するまでは `Older` を採用し、確立後の通常更新では巻き戻りを防ぐ
        applyFetchedPageState('Twitter', twitter_result, twitterPageTweets, {
            should_preserve_older_state: feedCoverage.value.twitter.older_cursor !== null || feedCoverage.value.twitter.is_older_exhausted === true,
            should_keep_older_uninitialized_when_missing: true,
        });
        applyFetchedPageState('Bluesky', bluesky_result, blueskyPageTweets);
        await fetchBlueskyUntilDisplayLowerBound(blueskyHandle, isSameRequestAccount);

        // 仮想スクローラーの描画をリフレッシュ
        refreshScroller();
        await nextTick();
        updateSeenTweetTracking();
    }
    isFetching.value = false;
};

// 「さらに読み込む」ボタンが押されたら当該範囲のタイムラインを取得
const handleLoadMore = async (item: ILoadMoreItem) => {
    // 「さらに読み込む」ボタンは特定の歯抜け区間を埋めるので、別の取得処理とは同時に走らせない
    if (isFetching.value) {
        return;
    }
    isFetching.value = true;
    if (!selected_account.value) {
        console.warn('selected_account is null');
        isFetching.value = false;
        return;
    }

    const account = selected_account.value;
    const requestAccountIdentity = getTimelineAccountIdentity(account);
    const twitterScreenName = account.kind === 'Twitter' ? account.twitter_account.screen_name :
        account.kind === 'Linked' ? account.account_link.twitter_account.screen_name : null;
    const blueskyHandle = account.kind === 'Bluesky' ? account.bluesky_account.handle :
        account.kind === 'Linked' ? account.account_link.bluesky_account.handle : null;
    const loadMoreTargets = decideLoadMoreTargets(item, feedCoverage.value, getTimelineAccountKind());
    const shouldFetchTwitter = loadMoreTargets.should_fetch_twitter === true && twitterScreenName !== null && loadMoreTargets.twitter_cursor_id !== null;
    const shouldFetchBluesky = loadMoreTargets.should_fetch_bluesky === true && blueskyHandle !== null && loadMoreTargets.bluesky_cursor_id !== null;
    if (shouldFetchTwitter === false && shouldFetchBluesky === false) {
        isFetching.value = false;
        return;
    }

    const existingIds = createExistingTweetIds();
    // Twitter を実際に取得する場合だけ seenTweetIds キューを消費する
    // Bluesky の補充や Bluesky 単独の末尾取得で Twitter 側の閲覧済み情報が消えないようにする
    const seenTweetIds = shouldFetchTwitter === true ? dequeuePendingSeenTweetIds() : [];
    const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
        shouldFetchTwitter === true ?
            Twitter.getHomeTimeline(
                twitterScreenName,
                loadMoreTargets.twitter_cursor_id!,
                getTwitterTimelineCursorType(loadMoreTargets.twitter_cursor_type ?? undefined),
                seenTweetIds,
            ) :
            Promise.resolve(null),
        shouldFetchBluesky === true ?
            Bluesky.getHomeTimeline(blueskyHandle, loadMoreTargets.bluesky_cursor_id!) :
            Promise.resolve(null),
    ]);
    const twitter_result = getTimelineFetchResult(twitter_settled_result);
    const bluesky_result = getTimelineFetchResult(bluesky_settled_result);

    // 続き取得中にアカウントが切り替わった場合、旧アカウントのページを現在の表示へ差し込まない
    // Twitter 取得が空応答や失敗だった場合は、消費した seenTweetIds だけ元アカウントへ戻す
    if (getTimelineAccountIdentity(selected_account.value) !== requestAccountIdentity) {
        if (isCursorConsumed(twitter_result) === false || (shouldFetchTwitter === true && twitter_result === null)) {
            restorePendingSeenTweetIds(seenTweetIds, twitterScreenName);
        }
        isFetching.value = false;
        return;
    }

    // Twitter の空応答や通信失敗では seenTweetIds が Twitter に反映されない
    // 取得範囲も進めず同じカーソルを再利用するため、閲覧済み情報も次回へ戻す
    if (isCursorConsumed(twitter_result) === false || (shouldFetchTwitter === true && twitter_result === null)) {
        restorePendingSeenTweetIds(seenTweetIds);
    }

    const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
    const blueskyPageTweets = bluesky_result?.tweets ?? [];
    addFetchedTweetsToTimeline(twitterPageTweets, blueskyPageTweets, existingIds);

    // 中央 gap は Twitter のレスポンスが実際に進んだ場合だけ消費する
    // 30 秒制限や通信失敗で取り除くと、同じ未取得範囲を二度と埋められなくなる
    if (isCursorConsumed(twitter_result) === true) {
        removeTwitterGapById(loadMoreTargets.consumed_twitter_gap_id);
    }
    applyFetchedPageState('Twitter', twitter_result, twitterPageTweets, {
        should_preserve_older_state: item.type === 'twitter_gap',
    });
    applyFetchedPageState('Bluesky', bluesky_result, blueskyPageTweets);
    // 中央 gap は Twitter だけを埋める操作なので、Bluesky 補充は末尾取得の後だけ行う
    if (item.type === 'tail') {
        await fetchBlueskyUntilDisplayLowerBound(
            blueskyHandle,
            () => getTimelineAccountIdentity(selected_account.value) === requestAccountIdentity,
        );
    }

    // Bluesky 補充中にアカウントが切り替わった場合も、古い統合結果を現在の画面へ混ぜない
    if (getTimelineAccountIdentity(selected_account.value) !== requestAccountIdentity) {
        isFetching.value = false;
        return;
    }

    await nextTick();
    updateSeenTweetTracking();
    isFetching.value = false;
};

// 選択中の Twitter アカウントが変更されたらタイムラインの内容をまっさらにした上で再取得
// (Twitter パネルとタイムラインタブが表示状態のときのみ自動で再取得する)
// このイベントはコンポーネントのマウント時にも実行される (マウント時に selected_twitter_account が変更されるため)
watch(selected_account, (newAccount, oldAccount) => {
    // アカウント種別や紐付け先が変わったら、前アカウントのカーソルと表示ブロックを持ち越さない
    tweetsByKey.value = new Map();
    twitterGaps.value = [];
    feedCoverage.value = createEmptyMergedFeedCoverage();
    twitterNewerCursorId.value = null;  // 新着方向カーソルをリセット
    clearVisibleTweetTimers();
    // 離脱元アカウントの表示中判定を破棄し、移動先アカウントにも前回表示時の判定が残っていない状態で再取得する
    clearConfirmedVisibleTweetIds(oldAccount?.kind === 'Twitter' ? oldAccount.twitter_account.screen_name : oldAccount?.kind === 'Linked' ? oldAccount.account_link.twitter_account.screen_name : undefined);
    clearConfirmedVisibleTweetIds(newAccount?.kind === 'Twitter' ? newAccount.twitter_account.screen_name : newAccount?.kind === 'Linked' ? newAccount.account_link.twitter_account.screen_name : undefined);
    isInitialFetchPending.value = true;
    isFirstFetchCompleted = false;
    tryAutoFetchTimeline();
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにして再取得
watch(showRetweets, () => {
    // RT 表示設定は既存ブロックを後から完全に復元できないため、カーソルごと初期化して取り直す
    tweetsByKey.value = new Map();
    twitterGaps.value = [];
    feedCoverage.value = createEmptyMergedFeedCoverage();
    twitterNewerCursorId.value = null;  // 新着方向カーソルをリセット
    clearVisibleTweetTimers();
    clearConfirmedVisibleTweetIds(selected_twitter_account.value?.screen_name);
    fetchTimelineTweets();
});

const checkScrollPosition = () => {
    if (!scroller.value || !scroller.value.$el) return;
    // 現在他のタイミングでツイートを取得中なら常にイベントを無視
    if (isFetching.value) return;
    // 仮想スクローラーの描画リフレッシュ中なら常にイベントを無視
    if (isRefreshing.value) return;

    updateSeenTweetTracking();

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

// コンポーネントマウント時は、タイムラインタブが表示されている場合のみ自動取得する
onMounted(() => {
    tryAutoFetchTimeline();
    nextTick(() => {
        if (scroller.value && scroller.value.$el) {
            scroller.value.$el.addEventListener('scroll', checkScrollPosition);
            updateSeenTweetTracking();
        }
    });
});

onUnmounted(() => {
    if (scroller.value && scroller.value.$el) {
        scroller.value.$el.removeEventListener('scroll', checkScrollPosition);
    }
    clearVisibleTweetTimers();
});

</script>
<style lang="scss" scoped>

.tab-content--timeline {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: visible !important;
}

.timeline-header {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    height: 45px;
    padding: 6px 12px;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);

    .search-input-wrapper {
        display: flex;
        align-items: center;
        flex-grow: 1;
        height: 100%;
        margin-right: 6px;
        padding-left: 8px;
        padding-right: 8px;
        background-color: rgb(var(--v-theme-background-lighten-2));
        border-radius: 5px;
        transition: box-shadow 0.09s ease;

        &--focused {
            box-shadow: rgba(79, 130, 230, 60%) 0 0 0 3.5px;
        }

        .iconify {
            color: rgb(var(--v-theme-text-darken-2));
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

        &::placeholder {
            color: rgb(var(--v-theme-text-darken-2));
        }
    }

    &__settings,
    &__refresh {
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

    &__refresh {
        margin-left: 6px;
        background-color: rgb(var(--v-theme-twitter));
    }
}

.timeline-settings {
    display: flex;
    flex-direction: column;
    padding: 8px 12px;
    padding-left: 20px;
    font-size: 14px;
    color: rgb(var(--v-theme-text-darken-1));
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    @include smartphone-horizontal {
        font-size: 13.5px;
    }

    &__item {
        display: flex;
        align-items: center;
        height: 32px;
        user-select: none;
    }
}

.timeline-tweets {
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

.timeline-announce {
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
        text-align: center;
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
