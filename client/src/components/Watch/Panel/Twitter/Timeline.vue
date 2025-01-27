<template>
    <div class="tab-content tab-content--timeline">
        <div class="timeline-header">
            <Icon icon="fluent:home-16-filled" height="18px" />
            <h2 class="timeline-header__title ml-2">タイムライン</h2>
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
            <v-switch
                v-model="showRetweets"
                color="primary"
                hide-details
                density="comfortable"
                label="リツイートを表示する"
            />
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
            <div class="timeline-announce__heading">まだツイートがありません。</div>
            <div class="timeline-announce__text">
                <p class="mt-0 mb-0">右上の更新ボタンを押すと、最新の<br>ホームタイムラインを時系列で表示できます。</p>
            </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import { VList as VirtuaList } from 'virtua/vue';
import { ref, onMounted, watch, nextTick, computed } from 'vue';

import Tweet from '@/components/Watch/Panel/Twitter/Tweet.vue';
import Message from '@/message';
import Twitter, { ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';

const twitterStore = useTwitterStore();
const { selected_twitter_account } = storeToRefs(twitterStore);

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
const scroller = ref<any>(null);

// 表示する最大ツイート数
const MAX_TWEETS = 1000;

// フラットな構造の配列を生成する computed プロパティ
const flattenedItems = computed(() => {
    const items: (ITweet | ILoadMoreItem)[] = [];
    for (const item of timelineItems.value) {
        if (item.type === 'tweet_block') {
            items.push(...item.tweets);
        } else {
            items.push(item);
        }
    }
    return items;
});

const getTotalTweetCount = () => {
    return timelineItems.value.reduce((count, item) => {
        if (item.type === 'tweet_block') {
            return count + item.tweets.length;
        }
        return count;
    }, 0);
};

// 既存のツイートIDのセットを取得
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
    if (isFetching.value) return;
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_twitter_account.value) {
        if (isFirstFetchCompleted) {
            Message.warning('タイムラインを更新するには、Twitter アカウントと連携してください。');
        }
        timelineItems.value = [];
        isFetching.value = false;
        isFirstFetchCompleted = true;
        return;
    }
    isFirstFetchCompleted = true;

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    const result = await Twitter.getHomeTimeline(selected_twitter_account.value.screen_name);
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
    }
    isFetching.value = false;
};

const handleLoadMore = async (item: ILoadMoreItem) => {
    if (isFetching.value || getTotalTweetCount() >= MAX_TWEETS) {
        return;
    }
    isFetching.value = true;
    if (!selected_twitter_account.value) {
        console.warn('selected_twitter_account is null');
        isFetching.value = false;
        return;
    }

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    const result = await Twitter.getHomeTimeline(selected_twitter_account.value.screen_name, item.cursor_id);
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
    }
    isFetching.value = false;
};

// 選択中の Twitter アカウントが変更されたらタイムラインの内容をまっさらにした上で再取得
// このイベントはコンポーネントのマウント時にも実行される (マウント時に selected_twitter_account が変更されるため)
watch(selected_twitter_account, () => {
    timelineItems.value = [];
    fetchTimelineTweets();
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにした上で再取得
watch(showRetweets, () => {
    timelineItems.value = [];
    fetchTimelineTweets();
});

const checkScrollPosition = () => {
    if (!scroller.value || !scroller.value.$el || isFetching.value) return;

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

// コンポーネントマウント時のみ自動取得
// これ以降は原則ボタンが押された時のみ手動取得となる
onMounted(() => {
    fetchTimelineTweets();
    nextTick(() => {
        if (scroller.value && scroller.value.$el) {
            scroller.value.$el.addEventListener('scroll', checkScrollPosition);
        }
    });
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

    &__title {
        font-size: 16px;
        font-weight: bold;
        margin: 0;
    }

    .timeline-header__settings,
    .timeline-header__refresh {
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

    .timeline-header__refresh {
        margin-left: 6px;
        background-color: rgb(var(--v-theme-twitter));
    }

}

.timeline-settings {
    padding: 0px 12px;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.timeline-tweets {
    flex-grow: 1;
    overflow-y: auto;
    will-change: transform;
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