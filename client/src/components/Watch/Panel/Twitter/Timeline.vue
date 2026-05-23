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
import Twitter, { ITimelineTweetsResult, ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils, { TweetUtils } from '@/utils';

const twitterStore = useTwitterStore();
const { selected_account, selected_twitter_account } = storeToRefs(twitterStore);

const SEEN_TWEET_DWELL_MILLISECONDS = 500;
const SEEN_TWEET_IDS_LIMIT = 300;

const props = defineProps<{
    isTwitterPanelVisible: boolean;
    isTimelineTabActive: boolean;
}>();

// タイムラインのアイテムの型定義
interface ITweetBlock {
    type: 'tweet_block';
    tweets: ITweet[];
    id: string;
}

interface ILoadMoreItem {
    type: 'load_more';
    twitter_cursor_id?: string;
    bluesky_cursor_id?: string;
    id: string;
}

type TimelineItem = ITweetBlock | ILoadMoreItem;

interface ISeenTweetTrackingState {
    pendingSeenTweetIds: string[];
    confirmedVisibleTweetIds: Set<string>;
}

const timelineItems = ref<TimelineItem[]>([]);
const showSettings = ref(false);
const showRetweets = ref(true);
const isFetching = ref(false);
const scroller = useTemplateRef('scroller');
const isInitialFetchPending = ref(true);

// タイムラインタブが実際に表示されているかを判定
const shouldAutoFetchTimeline = computed(() => props.isTwitterPanelVisible === true && props.isTimelineTabActive === true);

// タイムライン更新履歴を管理するための変数
// ユニークなツイートが得られた更新時の next_cursor_id のみを保持
const cursorIdHistory = ref<string[]>([]);  // Twitter の更新履歴を保持

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

// フラットな構造の配列を生成する computed プロパティ
const flattenedItems = computed(() => {
    // フィルタリング更新中は空配列を返す
    if (isRefreshingFilter.value) {
        return [];
    }

    const items: (ITweet | ILoadMoreItem)[] = [];
    for (const item of timelineItems.value) {
        if (item.type === 'tweet_block') {
            // フィルタクエリが存在する場合、ツイート本文でフィルタリング
            const tweets = filterQuery.value
                ? item.tweets.filter(tweet => {
                    // リツイートの場合は retweeted_tweet の text を使用する
                    const targetText = tweet.retweeted_tweet ? tweet.retweeted_tweet.text : tweet.text;
                    const hasText = targetText.toLowerCase().includes(filterQuery.value.toLowerCase());
                    return isNotFilter.value ? !hasText : hasText;
                })
                : item.tweets;
            items.push(...tweets);
        } else {
            items.push(item);
        }
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

// 既存のツイート ID のセットを取得
const getExistingTweetIds = () => {
    const ids = new Set<string>();
    for (const item of timelineItems.value) {
        if (item.type === 'tweet_block') {
            for (const tweet of item.tweets) {
                ids.add(TweetUtils.getTweetIdentityKey(tweet));
            }
        }
    }
    return ids;
};

const getTimelineFetchResult = (result: PromiseSettledResult<ITimelineTweetsResult | null>) => {
    // ホームタイムラインは Twitter / Bluesky を独立して取得するため、片方の例外は null に正規化する
    if (result.status === 'fulfilled') {
        return result.value;
    }
    console.error('Timeline API request failed unexpectedly.', result.reason);
    return null;
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

const hasTimelineGap = (tweets: ITweet[], previousCursorId: string | undefined, existingIds: Set<string>) => {
    // 返ってきたページが既存表示と一つも重なっていない場合、そのページと旧表示の間にまだ未取得区間が残る
    // Twitter と Bluesky はカーソルの意味が違うため、サービス別にこの判定を行ってからボタンへ持たせる
    // 片方だけ重複が見つかった場合に、もう片方の未取得区間まで消さないための判定でもある
    if (!previousCursorId || tweets.length === 0) {
        return false;
    }
    return TweetUtils.filterDuplicateTweets(tweets, existingIds).length === tweets.length;
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
        timelineItems.value = [];
        clearVisibleTweetTimers();
        isFetching.value = false;
        isFirstFetchCompleted = true;
        return;
    }
    isFirstFetchCompleted = true;

    // 使用するカーソル ID を決定
    // 履歴が2件以上ある場合は末尾から2番目のカーソル ID を使用
    let cursor_id: string | undefined;
    if (cursorIdHistory.value.length >= 2) {
        cursor_id = cursorIdHistory.value[cursorIdHistory.value.length - 2];
    }

    const seenTweetIds = dequeuePendingSeenTweetIds();

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    const account = selected_account.value;
    // 紐付けアカウントでは Twitter と Bluesky のホームタイムラインを並列取得し、表示直前に一つのリストへ統合する
    const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
        // Twitter は Web App の HomeLatestTimeline と同じく、更新履歴の Top 側 cursor と seenTweetIds を渡す
        // 時間を空けた更新では Twitter 側が最新数十件だけを返すため、後段で gap ボタンを残して中間を埋められるようにする
        account.kind === 'Twitter' || account.kind === 'Linked' ?
            Twitter.getHomeTimeline(account.kind === 'Twitter' ? account.twitter_account.screen_name : account.account_link.twitter_account.screen_name, cursor_id, seenTweetIds) :
            Promise.resolve(null),
        account.kind === 'Bluesky' || account.kind === 'Linked' ?
            // Bluesky の cursor は「次の古いページ」専用なので、通常更新では必ず最新ページを取り直す
            // 古い cursor を更新に使うと、時間を置いた後に最新投稿へ戻れず Twitter 側との時系列マージが壊れる
            Bluesky.getHomeTimeline(account.kind === 'Bluesky' ? account.bluesky_account.handle : account.account_link.bluesky_account.handle) :
            Promise.resolve(null),
    ]);
    const twitter_result = getTimelineFetchResult(twitter_settled_result);
    const bluesky_result = getTimelineFetchResult(bluesky_settled_result);
    const result = twitter_result ?? bluesky_result;
    if (result && result.tweets) {
        const existingIds = getExistingTweetIds();
        // フィルタと自分の RT 除外はサービス別に先に適用する
        // 統合後にまとめて判定すると、どちらのサービスに未取得区間が残ったかを判定しにくくなる
        const twitterTweets = filterTimelineTweets(twitter_result?.tweets ?? []);
        const blueskyTweets = filterTimelineTweets(bluesky_result?.tweets ?? []);
        // 既存表示との重複もサービス別に見る
        // Twitter と Bluesky の ID 空間は違うため、TweetUtils 側の source / URI ベースのキーで比較する
        const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
        const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
        // gap ボタンに載せる cursor は、未取得区間が残っているサービスだけに限定する
        // 両サービスをまとめて判定すると、片方の重複で片方のページングまで消える
        const shouldLoadMoreTwitter = hasTimelineGap(twitterTweets, twitter_result?.previous_cursor_id, existingIds);
        const shouldLoadMoreBluesky = hasTimelineGap(blueskyTweets, bluesky_result?.previous_cursor_id, existingIds);
        // API ごとの戻り順に依存すると紐付け時にサービス単位で固まるため、作成日時で再ソートする
        const uniqueTweets = TweetUtils.sortTweetsByCreatedAt([
            ...twitterUniqueTweets,
            ...blueskyUniqueTweets,
        ]);

        // ユニークなツイートが得られた場合のみ next_cursor_id を履歴に追加
        // Twitter の更新用 cursor だけを履歴として残し、Bluesky の古いページング cursor は通常更新に持ち越さない
        if (twitterUniqueTweets.length > 0 && twitter_result?.next_cursor_id) {
            cursorIdHistory.value.push(twitter_result.next_cursor_id);
            // 履歴は最新の10件のみ保持
            if (cursorIdHistory.value.length > 10) {
                cursorIdHistory.value.shift();
            }
        }

        if (uniqueTweets.length > 0) {
            // 新しいツイートブロックを作成
            // 重複だけが返った場合は空ブロックを追加せず、既存タイムライン表示を保つ
            const newBlock: ITweetBlock = {
                type: 'tweet_block',
                tweets: uniqueTweets,
                id: `block_${Date.now()}`,
            };

            // 既存のタイムラインがある場合、新しいブロックと既存のブロックの間に「さらに読み込む」ボタンを挿入
            // ただし、サービス別に既存表示との重複があった場合（＝歯抜けを埋め終わった場合）は、そのサービスのカーソルを挿入しない
            if (timelineItems.value.length > 0 && (shouldLoadMoreTwitter === true || shouldLoadMoreBluesky === true)) {
                timelineItems.value = [
                    newBlock,
                    {
                        type: 'load_more',
                        twitter_cursor_id: shouldLoadMoreTwitter === true ? twitter_result?.previous_cursor_id : undefined,
                        bluesky_cursor_id: shouldLoadMoreBluesky === true ? bluesky_result?.previous_cursor_id : undefined,
                        id: `load_more_${twitter_result?.previous_cursor_id ?? ''}_${bluesky_result?.previous_cursor_id ?? ''}`,
                    },
                    ...timelineItems.value,
                ];
            } else {
                timelineItems.value = [newBlock, ...timelineItems.value];
            }
        }

        // 初回検索時、または最後のアイテムがツイートブロックの場合は、最下部に「さらに読み込む」ボタンを追加
        const lastItem = timelineItems.value[timelineItems.value.length - 1];
        if ((twitter_result?.previous_cursor_id || bluesky_result?.previous_cursor_id) && timelineItems.value.length > 0 && (!lastItem || lastItem.type === 'tweet_block')) {
            // 最下部のボタンは通常の古い方向へのページング用に両サービスの cursor を持たせる
            // ここは最新更新の gap ボタンと違い、現在表示の末尾からさらに古い投稿を読むための入口になる
            timelineItems.value.push({
                type: 'load_more',
                twitter_cursor_id: twitter_result?.previous_cursor_id,
                bluesky_cursor_id: bluesky_result?.previous_cursor_id,
                id: `load_more_${twitter_result?.previous_cursor_id ?? ''}_${bluesky_result?.previous_cursor_id ?? ''}`,
            });
        }

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
        console.warn('selected_twitter_account is null');
        isFetching.value = false;
        return;
    }

    const seenTweetIds = dequeuePendingSeenTweetIds();

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    const account = selected_account.value;
    // ボタンに保存されたサービス別カーソルだけを使い、カーソルがないサービスには追加取得を投げない
    const [twitter_settled_result, bluesky_settled_result] = await Promise.allSettled([
        // gap ボタンはサービスごとに cursor を持つ
        // Twitter 側の未取得区間だけを埋めるボタンなら Bluesky API には触らない
        (account.kind === 'Twitter' || account.kind === 'Linked') && item.twitter_cursor_id ?
            Twitter.getHomeTimeline(account.kind === 'Twitter' ? account.twitter_account.screen_name : account.account_link.twitter_account.screen_name, item.twitter_cursor_id, seenTweetIds) :
            Promise.resolve(null),
        // Bluesky 側も同様に、保存された古い方向の cursor がある場合だけ追加取得する
        // 通常更新では cursor なし、load more では cursor ありという呼び分けをここで明確に分ける
        (account.kind === 'Bluesky' || account.kind === 'Linked') && item.bluesky_cursor_id ?
            Bluesky.getHomeTimeline(account.kind === 'Bluesky' ? account.bluesky_account.handle : account.account_link.bluesky_account.handle, item.bluesky_cursor_id) :
            Promise.resolve(null),
    ]);
    const twitter_result = getTimelineFetchResult(twitter_settled_result);
    const bluesky_result = getTimelineFetchResult(bluesky_settled_result);
    const result = twitter_result ?? bluesky_result;
    if (result && result.tweets) {
        const existingIds = getExistingTweetIds();
        // 追加取得でもサービス別にフィルタしてから統合する
        // どちらの cursor を次の gap ボタンへ残すかを、各サービスの重複有無で判断するため
        const twitterTweets = filterTimelineTweets(twitter_result?.tweets ?? []);
        const blueskyTweets = filterTimelineTweets(bluesky_result?.tweets ?? []);
        const twitterUniqueTweets = TweetUtils.filterDuplicateTweets(twitterTweets, existingIds);
        const blueskyUniqueTweets = TweetUtils.filterDuplicateTweets(blueskyTweets, existingIds);
        // 取得ページが既存表示と重ならないサービスだけ、さらに深い cursor をボタンへ残す
        // これで Twitter の歯抜けと Bluesky の古いページングを互いに巻き込まずに進められる
        const shouldLoadMoreTwitter = hasTimelineGap(twitterTweets, twitter_result?.previous_cursor_id, existingIds);
        const shouldLoadMoreBluesky = hasTimelineGap(blueskyTweets, bluesky_result?.previous_cursor_id, existingIds);
        // 追加取得でもサービス間の時系列を保つため、結合後に KonomiTV 共通の比較関数で並べ替える
        const uniqueTweets = TweetUtils.sortTweetsByCreatedAt([
            ...twitterUniqueTweets,
            ...blueskyUniqueTweets,
        ]);

        // 「さらに読み込む」ボタンの位置を特定
        const loadMoreIndex = timelineItems.value.findIndex(i => i.type === 'load_more' && i === item);
        if (loadMoreIndex === -1) {
            isFetching.value = false;
            return;
        }

        // 新しいアイテムを配列に追加
        const newItems: TimelineItem[] = [];
        if (uniqueTweets.length > 0) {
            // 新しいツイートブロックを作成
            // 既存ツイートだけが返った場合はボタンの除去だけを行い、空のブロックは挿入しない
            newItems.push({
                type: 'tweet_block',
                tweets: uniqueTweets,
                id: `block_${Date.now()}`,
            });
        }

        // 重複するツイートがなかった場合（＝まだ歯抜けがある場合）のみ「さらに読み込む」ボタンを追加
        if (shouldLoadMoreTwitter === true || shouldLoadMoreBluesky === true) {
            // 次の gap ボタンにも、未取得区間が続いているサービスの cursor だけを載せる
            // 片側が既存表示へ到達したあとも、もう片側の未取得区間を引き続き埋められるようにする
            newItems.push({
                type: 'load_more',
                twitter_cursor_id: shouldLoadMoreTwitter === true ? twitter_result?.previous_cursor_id : undefined,
                bluesky_cursor_id: shouldLoadMoreBluesky === true ? bluesky_result?.previous_cursor_id : undefined,
                id: `load_more_${twitter_result?.previous_cursor_id ?? ''}_${bluesky_result?.previous_cursor_id ?? ''}`,
            });
        }

        // 既存の「さらに読み込む」ボタンを削除し、その位置に新しいアイテムを挿入
        timelineItems.value.splice(loadMoreIndex, 1, ...newItems);

        // 最後のアイテムがツイートブロックの場合は、最下部に「さらに読み込む」ボタンを追加
        const lastItem = timelineItems.value[timelineItems.value.length - 1];
        if ((shouldLoadMoreTwitter === true || shouldLoadMoreBluesky === true) && lastItem && lastItem.type === 'tweet_block') {
            // 差し替え位置が末尾だった場合は、引き続き最下部から古い投稿を読めるようにボタンを補う
            // 直前で挿入済みの gap ボタンと重ならないよう、末尾がツイートブロックの時だけ追加する
            timelineItems.value.push({
                type: 'load_more',
                twitter_cursor_id: shouldLoadMoreTwitter === true ? twitter_result?.previous_cursor_id : undefined,
                bluesky_cursor_id: shouldLoadMoreBluesky === true ? bluesky_result?.previous_cursor_id : undefined,
                id: `load_more_${twitter_result?.previous_cursor_id ?? ''}_${bluesky_result?.previous_cursor_id ?? ''}`,
            });
        }

        await nextTick();
        updateSeenTweetTracking();
    }
    isFetching.value = false;
};

// 選択中の Twitter アカウントが変更されたらタイムラインの内容をまっさらにした上で再取得
// (Twitter パネルとタイムラインタブが表示状態のときのみ自動で再取得する)
// このイベントはコンポーネントのマウント時にも実行される (マウント時に selected_twitter_account が変更されるため)
watch(selected_account, (newAccount, oldAccount) => {
    // アカウント種別や紐付け先が変わったら、前アカウントのカーソルと表示ブロックを持ち越さない
    timelineItems.value = [];
    cursorIdHistory.value = [];  // カーソル履歴をリセット
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
    timelineItems.value = [];
    cursorIdHistory.value = [];  // カーソル履歴をリセット
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
        const lastItem = timelineItems.value[timelineItems.value.length - 1];
        if (lastItem && lastItem.type === 'load_more') {
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
