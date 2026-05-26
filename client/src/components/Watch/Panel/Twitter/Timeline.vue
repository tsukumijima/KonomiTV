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

interface ISeenTweetTrackingState {
    pendingSeenTweetIds: string[];
    confirmedVisibleTweetIds: Set<string>;
}

const MAX_BLUESKY_CATCHUP_PAGES = 5;
const GAP_GROUP_ADJACENT_MILLISECONDS = 60 * 1000;

const tweetsByKey = ref<Map<string, ITweet>>(new Map());
const gaps = ref<IFeedGap[]>([]);
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

    // Vue の Map 監視は破壊的更新でも追従できるが、ここでは参照ごと差し替えて computed の再計算点を明確にする
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

// 内部ではサービスごとに gap を保持し、画面上では近接する未取得範囲を 1 つのボタンに束ねる
// Twitter と Bluesky ではカーソルの意味が違うため、内部 gap をマージせず表示層だけでまとめる
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
        // 直前グループの時刻範囲と重なる、または近接する gap は同じ未取得範囲として 1 ボタンへ束ねる
        // 画面上の分断を減らしつつ、クリック時には `gap_ids` から元のサービス別カーソルを引き直す
        const shouldJoinLastGroup = lastGroup !== undefined && (
            lastGroupLowerTime === null ||
            gapUpperTime >= lastGroupLowerTime - GAP_GROUP_ADJACENT_MILLISECONDS
        );

        if (shouldJoinLastGroup === true) {
            // 内部 gap はカーソル単位で保持しつつ、画面上は近接する未取得区間を 1 つのボタンに見せる
            // 同じ時系列リストの中でサービス別ボタンが並ぶ違和感を避けるため、押下時に gap_ids から元の gap 群を引き直す
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
    // フィルタリング更新中は空配列を返す
    if (isRefreshingFilter.value) {
        return [];
    }

    const items: (ITweet | ILoadMoreItem)[] = [];
    // `tweetsByKey` は順序を持たない正規化ストアなので、描画直前に必ず時刻降順へ並べ直す
    const sortedTweets = TweetUtils.sortTweetsByCreatedAt([...tweetsByKey.value.values()]);
    const filteredTweets = sortedTweets.filter(tweet => {
        if (!filterQuery.value) {
            return true;
        }
        // リツイートの場合は retweeted_tweet の text を使用する
        const targetText = tweet.retweeted_tweet ? tweet.retweeted_tweet.text : tweet.text;
        const hasText = targetText.toLowerCase().includes(filterQuery.value.toLowerCase());
        return isNotFilter.value ? !hasText : hasText;
    });
    const groupedLoadMoreItems = createGroupedLoadMoreItems();
    let tweetIndex = 0;

    for (const loadMoreItem of groupedLoadMoreItems) {
        const upperTime = getCreatedAtMilliseconds(loadMoreItem.upper_created_at);
        // gap の新しい側境界より新しいツイートを先に流し込み、ボタンを正しい時刻位置へ置く
        while (
            tweetIndex < filteredTweets.length &&
            getTweetCreatedAtMilliseconds(filteredTweets[tweetIndex]) >= upperTime
        ) {
            items.push(filteredTweets[tweetIndex]);
            tweetIndex++;
        }
        items.push(loadMoreItem);
    }

    // すべての gap より古いツイートは最後にそのまま流し込む
    while (tweetIndex < filteredTweets.length) {
        items.push(filteredTweets[tweetIndex]);
        tweetIndex++;
    }

    // フィルタリング中で、かつツイートが1件も含まれていない場合は空配列を返す
    if (filterQuery.value && !items.some(item => 'text' in item)) {
        return [];
    }

    return items;
});

// 選択中の Twitter アカウントに紐づく seenTweetIds 管理状態を取得する
// 本家と同様にアカウントごとに短期キューを分離し、アカウント切り替え後に戻った場合も未送信分を維持する
const getCurrentSeenTweetTrackingState = () => {
    const screenName = selected_twitter_account.value?.screen_name;
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

const restorePendingSeenTweetIds = (seenTweetIds: string[]) => {
    if (seenTweetIds.length === 0) {
        return;
    }

    const state = getCurrentSeenTweetTrackingState();
    if (!state) {
        return;
    }

    // Twitter 側の 30 秒制限で空応答になった場合、サーバーには seenTweetIds が届いていても Twitter には転送されない
    // ここで先頭へ戻しておくことで、次に実取得できたタイミングで同じ閲覧済み情報を再送できる
    state.pendingSeenTweetIds = [...seenTweetIds, ...state.pendingSeenTweetIds].slice(0, SEEN_TWEET_IDS_LIMIT);
};

const isCursorConsumed = (result: ITimelineTweetsResult | null) => {
    return result !== null && result.is_cursor_consumed === true;
};

const buildGapFromLoadMoreCursor = (
    source: 'Twitter' | 'Bluesky',
    loadMoreCursor: ITimelineLoadMoreCursor,
    pageTweets: ITweet[],
): IFeedGap | null => {
    // 表示位置はサーバー側が抽出したカーソル近傍の投稿時刻を優先する
    // Bluesky は古い方向カーソルだけなので、境界が空の場合は取得ページの最古投稿を上側境界にする
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
    // Twitter はレスポンス内の Gap / ShowMore / Older を、Bluesky は古い方向カーソルを同じ表示モデルへ変換する
    // どちらも取得結果の順序は信用せず、表示時に作成日時で再ソートする
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
    // Twitter のサーバー由来 gap はカーソル単位で安定しているため、ID で十分に重複を抑止できる
    const existingGapIds = new Set(gaps.value.map(gap => gap.id));
    gaps.value = [
        ...gaps.value,
        ...newGaps.filter(gap => existingGapIds.has(gap.id) === false),
    ];
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
        gaps.value = [];
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
    if (isCursorConsumed(twitter_result) === false) {
        restorePendingSeenTweetIds(seenTweetIds);
    }
    // 表示用フィルターとページ境界計算を分け、非表示対象だけのページでもカーソルを失わないようにする
    const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
    const twitterTweets = filterTimelineTweets(twitterPageTweets);
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
            const targetOldestTime = getCreatedAtMilliseconds(targetOldestCreatedAt);
            for (let pageIndex = 0; pageIndex < MAX_BLUESKY_CATCHUP_PAGES; pageIndex++) {
                const oldestTweet = getOldestTweet(collectedTweets);
                const hasReachedTarget = oldestTweet !== null && getTweetCreatedAtMilliseconds(oldestTweet) < targetOldestTime;
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
    const result = twitter_result ?? bluesky_result;
    if (result && result.tweets) {
        // フィルタと自分の RT 除外はサービス別に先に適用する
        // 統合後にまとめて判定すると、どちらのサービスに未取得区間が残ったかを判定しにくくなる
        const blueskyPageTweets = bluesky_result?.tweets ?? [];
        const blueskyTweets = filterTimelineTweets(blueskyPageTweets);
        // 既存表示との重複もサービス別に見る
        // Twitter と Bluesky の ID 空間は違うため、TweetUtils 側の `source` / URI ベースのキーで比較する
        const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
        const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
        // API ごとの戻り順に依存すると紐付け時にサービス単位で固まるため、作成日時で再ソートする
        const uniqueTweets = TweetUtils.sortTweetsByCreatedAt([
            ...twitterUniqueTweets,
            ...blueskyUniqueTweets,
        ]);

        // Twitter の新着方向カーソルは表示対象の有無に関係なく、実レスポンスが進んだときだけ更新する
        // 30 秒制限の空応答では既存カーソルを維持し、次回も同じ位置から更新できるようにする
        if (isCursorConsumed(twitter_result) === true && twitter_result?.newer_cursor_id) {
            twitterNewerCursorId.value = twitter_result.newer_cursor_id;
        }

        // サービスごとの新規投稿を正規化ストアへ追加し、表示順は `flattenedItems` 側に任せる
        if (uniqueTweets.length > 0) {
            addTweetsToMap(uniqueTweets);
        }

        // 更新取得でページ間に未取得範囲が残る場合、API レスポンス内の追加取得カーソルを gap として保存する
        // Twitter はサーバー由来の Gap / ShowMore を信用し、Bluesky は古い方向カーソルだけを控えめに扱う
        const newGaps = [
            ...buildGapsFromLoadMoreCursors('Twitter', twitter_result, twitterPageTweets),
            ...buildGapsFromLoadMoreCursors('Bluesky', bluesky_result, blueskyPageTweets),
        ];
        appendGaps(newGaps);

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
        // 近接 gap をまとめて描画しているだけなので、同じサービスへ複数リクエストを投げると Twitter 側の制限や順序管理が崩れる
        const shouldFetchTwitter = hasFetchedTwitter === false && twitterScreenName !== null && !!gap.twitter_cursor_id;
        const shouldFetchBluesky = hasFetchedBluesky === false && blueskyHandle !== null && !!gap.bluesky_cursor_id;
        if (shouldFetchTwitter === false && shouldFetchBluesky === false) {
            continue;
        }
        hasFetchedTwitter = hasFetchedTwitter || shouldFetchTwitter;
        hasFetchedBluesky = hasFetchedBluesky || shouldFetchBluesky;
        // Twitter にリクエストしない gap では seenTweetIds キューを触らない
        // Bluesky-only gap の押下で Twitter 側の閲覧済み情報が消えるのを防ぐ
        const seenTweetIds = shouldFetchTwitter === true ? dequeuePendingSeenTweetIds() : [];
        // 表示上は 1 つのボタンでも、内部 gap はカーソルの意味を壊さないよう 1 件ずつ処理する
        // 同じサービスの gap を無理に結合すると、Twitter の Bottom カーソルが指す範囲を失うためここで順に消化する
        const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
            shouldFetchTwitter === true ?
                Twitter.getHomeTimeline(twitterScreenName, gap.twitter_cursor_id, getTwitterTimelineCursorType(gap.twitter_cursor_type), seenTweetIds) :
                Promise.resolve(null),
            shouldFetchBluesky === true ?
                Bluesky.getHomeTimeline(blueskyHandle, gap.bluesky_cursor_id) :
                Promise.resolve(null),
        ]);
        const twitter_result = getTimelineFetchResult(twitter_settled_result);
        const bluesky_result = getTimelineFetchResult(bluesky_settled_result);
        // Twitter の空応答や通信失敗では `seenTweetIds` がサーバーへ反映されていない
        // 次回の実取得で同じ閲覧済み情報を再送するため、取り出した ID をキューへ戻す
        if (isCursorConsumed(twitter_result) === false || (shouldFetchTwitter === true && twitter_result === null)) {
            restorePendingSeenTweetIds(seenTweetIds);
        }

        // Twitter の空応答は投稿なしとして扱い、gap とカーソルは後段で温存する
        // gap 境界には取得ページそのものを使い、表示フィルターで全件落ちても次のカーソルを残す
        const twitterPageTweets = isCursorConsumed(twitter_result) === true ? [...(twitter_result?.tweets ?? [])] : [];
        const blueskyPageTweets = bluesky_result?.tweets ?? [];
        const twitterTweets = filterTimelineTweets(twitterPageTweets);
        const blueskyTweets = filterTimelineTweets(blueskyPageTweets);
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
        // ここで元の gap の Twitter 側だけを残し、後から同じ範囲を再取得できるようにする
        if (shouldFetchTwitter === true && (isCursorConsumed(twitter_result) === false || twitter_result === null)) {
            preservedGap.twitter_cursor_id = gap.twitter_cursor_id;
            preservedGap.twitter_cursor_type = gap.twitter_cursor_type;
            preservedGap.is_twitter_exhausted = false;
        }
        // Bluesky 側も API へ到達していない場合はカーソルを消費していない
        // Twitter の制限と同時に Bluesky が失敗したケースで、Bluesky のページング状態まで失わないようにする
        if (shouldFetchBluesky === true && bluesky_result === null) {
            preservedGap.bluesky_cursor_id = gap.bluesky_cursor_id;
            preservedGap.is_bluesky_exhausted = false;
        }

        // 実際にレスポンスが進んだサービスだけ、返却された追加取得カーソルから次の gap を作る
        // Twitter の gap カーソルはサーバー指示なので、投稿重複の有無で勝手に消さない
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
    gaps.value = [];
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
    gaps.value = [];
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
        if (lastItem && !('text' in lastItem) && lastItem.type === 'load_more') {
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
