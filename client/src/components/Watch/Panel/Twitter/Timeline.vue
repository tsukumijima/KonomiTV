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
import Twitter, { ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

const twitterStore = useTwitterStore();
const { selected_twitter_account } = storeToRefs(twitterStore);

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
    next_cursor_id?: string;  // より未来方向のツイートを取得するためのカーソル
    previous_cursor_id?: string;  // より過去方向のツイートを取得するためのカーソル
}

interface ILoadMoreItem {
    type: 'load_more';
    cursor_id: string;
    id: string;
}

type TimelineItem = ITweetBlock | ILoadMoreItem;

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
const cursorIdHistory = ref<string[]>([]);  // 更新履歴を保持

// Twitter Web App の seenTweetIds に相当する、次回のタイムライン取得時に送信する短期キュー
// 本家の挙動に合わせ、同一キュー内で同じツイート ID が複数回入ることは許容する
const pendingSeenTweetIds = ref<string[]>([]);
const visibleTweetTimers = new Map<string, number>();
const confirmedVisibleTweetIds = new Set<string>();

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

// seenTweetIds の送信キューにツイート ID を追加する
// キューが伸びすぎると KonomiTV API への GET クエリが長くなるため、古い ID から破棄する
const enqueueSeenTweetId = (tweetId: string) => {
    pendingSeenTweetIds.value.push(tweetId);
    if (pendingSeenTweetIds.value.length > SEEN_TWEET_IDS_LIMIT) {
        pendingSeenTweetIds.value.splice(0, pendingSeenTweetIds.value.length - SEEN_TWEET_IDS_LIMIT);
    }
};

// 次回のタイムライン取得で送信する seenTweetIds を取り出し、本家の clearTweets() 相当に合わせてキューを空にする
const dequeuePendingSeenTweetIds = () => {
    const seenTweetIds = [...pendingSeenTweetIds.value];
    pendingSeenTweetIds.value = [];
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
        if (item && 'text' in item) {
            visibleTweetIds.add(item.id);
        }
    }
    return visibleTweetIds;
};

// 実表示範囲に 0.5 秒以上入り続けたツイートを seenTweetIds の送信キューに追加する
// 一瞬だけ高速スクロールで通過したツイートは、タイマー完了時に表示範囲外になっていれば seen 扱いにしない
const updateSeenTweetTracking = () => {
    const visibleTweetIds = getVisibleTweetIds();

    for (const [tweetId, timerId] of visibleTweetTimers.entries()) {
        if (visibleTweetIds.has(tweetId) === false) {
            window.clearTimeout(timerId);
            visibleTweetTimers.delete(tweetId);
        }
    }

    for (const tweetId of confirmedVisibleTweetIds) {
        if (visibleTweetIds.has(tweetId) === false) {
            confirmedVisibleTweetIds.delete(tweetId);
        }
    }

    for (const tweetId of visibleTweetIds) {
        if (visibleTweetTimers.has(tweetId) || confirmedVisibleTweetIds.has(tweetId)) {
            continue;
        }

        const timerId = window.setTimeout(() => {
            const currentVisibleTweetIds = getVisibleTweetIds();
            if (currentVisibleTweetIds.has(tweetId)) {
                enqueueSeenTweetId(tweetId);
                confirmedVisibleTweetIds.add(tweetId);
            }
            visibleTweetTimers.delete(tweetId);
        }, SEEN_TWEET_DWELL_MILLISECONDS);
        visibleTweetTimers.set(tweetId, timerId);
    }
};

// タイムラインの再初期化時に、未送信キューと表示判定中のタイマーをすべて破棄する
const clearSeenTweetTracking = () => {
    for (const timerId of visibleTweetTimers.values()) {
        window.clearTimeout(timerId);
    }
    visibleTweetTimers.clear();
    confirmedVisibleTweetIds.clear();
    pendingSeenTweetIds.value = [];
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
                ids.add(tweet.id);
            }
        }
    }
    return ids;
};

// 新しいツイートから重複を除外
const filterDuplicateTweets = (tweets: ITweet[], existingIds: Set<string>) => {
    return tweets.filter(tweet => !existingIds.has(tweet.id));
};

const toggleSettings = () => {
    showSettings.value = !showSettings.value;
};

let isFirstFetchCompleted = false;
const fetchTimelineTweets = async () => {
    isInitialFetchPending.value = false;
    if (isFetching.value) return;
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_twitter_account.value) {
        if (isFirstFetchCompleted) {
            Message.warning('タイムラインを更新するには、Twitter アカウントと連携してください。');
        }
        timelineItems.value = [];
        clearSeenTweetTracking();
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
    const result = await Twitter.getHomeTimeline(selected_twitter_account.value.screen_name, cursor_id, seenTweetIds);
    if (result && result.tweets) {
        result.tweets = result.tweets.filter(tweet => {
            let result = true;
            // 「リツイートを表示する」がオフの場合はリツイートのツイートを除外
            if (showRetweets.value === false) {
                result = !tweet.retweeted_tweet;
            }
            // 自分の RT を除外
            if (tweet.retweeted_tweet !== null && tweet.user.screen_name === selected_twitter_account.value?.screen_name) {
                result = false;
            }
            return result;
        });

        // 既存のツイートとの重複を除外
        const existingIds = getExistingTweetIds();
        const uniqueTweets = filterDuplicateTweets(result.tweets, existingIds);

        // ユニークなツイートが得られた場合のみ next_cursor_id を履歴に追加
        if (uniqueTweets.length > 0 && result.next_cursor_id) {
            cursorIdHistory.value.push(result.next_cursor_id);
            // 履歴は最新の10件のみ保持
            if (cursorIdHistory.value.length > 10) {
                cursorIdHistory.value.shift();
            }
        }

        // 新しいツイートブロックを作成
        const newBlock: ITweetBlock = {
            type: 'tweet_block',
            tweets: uniqueTweets,
            id: `block_${Date.now()}`,
            next_cursor_id: result.next_cursor_id,  // より未来方向のカーソル
            previous_cursor_id: result.previous_cursor_id,  // より過去方向のカーソル
        };

        // 既存のタイムラインがある場合、新しいブロックと既存のブロックの間に「さらに読み込む」ボタンを挿入
        // ただし、重複するツイートがあった場合（＝歯抜けを埋め終わった場合）は挿入しない
        if (timelineItems.value.length > 0 && uniqueTweets.length === result.tweets.length) {
            timelineItems.value = [
                newBlock,
                {
                    type: 'load_more',
                    cursor_id: result.previous_cursor_id,
                    id: `load_more_${result.previous_cursor_id}`,
                },
                ...timelineItems.value,
            ];
        } else {
            timelineItems.value = [newBlock, ...timelineItems.value];
        }

        // 初回検索時、または最後のアイテムがツイートブロックの場合は、最下部に「さらに読み込む」ボタンを追加
        const lastItem = timelineItems.value[timelineItems.value.length - 1];
        if (result.previous_cursor_id && (!lastItem || lastItem.type === 'tweet_block')) {
            timelineItems.value.push({
                type: 'load_more',
                cursor_id: result.previous_cursor_id,
                id: `load_more_${result.previous_cursor_id}`,
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
    if (isFetching.value) {
        return;
    }
    isFetching.value = true;
    if (!selected_twitter_account.value) {
        console.warn('selected_twitter_account is null');
        isFetching.value = false;
        return;
    }

    const seenTweetIds = dequeuePendingSeenTweetIds();

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    const result = await Twitter.getHomeTimeline(selected_twitter_account.value.screen_name, item.cursor_id, seenTweetIds);
    if (result && result.tweets) {
        result.tweets = result.tweets.filter(tweet => {
            let result = true;
            // 「リツイートを表示する」がオフの場合はリツイートのツイートを除外
            if (showRetweets.value === false) {
                result = !tweet.retweeted_tweet;
            }
            // 自分の RT を除外
            if (tweet.retweeted_tweet !== null && tweet.user.screen_name === selected_twitter_account.value?.screen_name) {
                result = false;
            }
            return result;
        });

        // 既存のツイートとの重複を除外
        const existingIds = getExistingTweetIds();
        const uniqueTweets = filterDuplicateTweets(result.tweets, existingIds);

        // 「さらに読み込む」ボタンの位置を特定
        const loadMoreIndex = timelineItems.value.findIndex(i => i.type === 'load_more' && i === item);
        if (loadMoreIndex === -1) {
            isFetching.value = false;
            return;
        }

        // 新しいツイートブロックを作成
        const newBlock: ITweetBlock = {
            type: 'tweet_block',
            tweets: uniqueTweets,
            id: `block_${Date.now()}`,
            next_cursor_id: result.next_cursor_id,
            previous_cursor_id: result.previous_cursor_id,
        };

        // 新しいアイテムを配列に追加
        const newItems: TimelineItem[] = [newBlock];

        // 重複するツイートがなかった場合（＝まだ歯抜けがある場合）のみ「さらに読み込む」ボタンを追加
        if (result.previous_cursor_id && uniqueTweets.length === result.tweets.length) {
            newItems.push({
                type: 'load_more',
                cursor_id: result.previous_cursor_id,
                id: `load_more_${result.previous_cursor_id}`,
            });
        }

        // 既存の「さらに読み込む」ボタンを削除し、その位置に新しいアイテムを挿入
        timelineItems.value.splice(loadMoreIndex, 1, ...newItems);

        // 最後のアイテムがツイートブロックの場合は、最下部に「さらに読み込む」ボタンを追加
        const lastItem = timelineItems.value[timelineItems.value.length - 1];
        if (result.previous_cursor_id && lastItem.type === 'tweet_block') {
            timelineItems.value.push({
                type: 'load_more',
                cursor_id: result.previous_cursor_id,
                id: `load_more_${result.previous_cursor_id}`,
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
watch(selected_twitter_account, () => {
    timelineItems.value = [];
    cursorIdHistory.value = [];  // カーソル履歴をリセット
    clearSeenTweetTracking();
    isInitialFetchPending.value = true;
    isFirstFetchCompleted = false;
    tryAutoFetchTimeline();
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにして再取得
watch(showRetweets, () => {
    timelineItems.value = [];
    cursorIdHistory.value = [];  // カーソル履歴をリセット
    clearSeenTweetTracking();
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
    clearSeenTweetTracking();
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