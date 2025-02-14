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
import Twitter, { ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

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
const showRetweets = ref(false);
const isFetching = ref(false);
const isSearchFormFocused = ref(false);
const searchQuery = ref('');
const scroller = useTemplateRef('scroller');

// タイムライン更新履歴を管理するための変数
// ユニークなツイートが得られた更新時の next_cursor_id のみを保持
const cursorIdHistory = ref<string[]>([]);  // 更新履歴を保持

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

const onKeyDown = (event: KeyboardEvent) => {
    // 変換中でない場合のみ検索を実行
    if (event.key === 'Enter' && event.isComposing === false) {
        performSearchTweets();
    }
};

const performSearchTweets = async () => {
    if (isFetching.value) {
        return;
    }
    if (!searchQuery.value.trim()) {
        Message.warning('検索キーワードを入力してください。');
        return;
    }
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_twitter_account.value) {
        Message.warning('ツイートを検索するには、Twitter アカウントと連携してください。');
        timelineItems.value = [];
        isFetching.value = false;
        return;
    }

    // 使用するカーソル ID を決定
    // 履歴が2件以上ある場合は末尾から2番目のカーソル ID を使用
    let cursor_id: string | undefined;
    if (cursorIdHistory.value.length >= 2) {
        cursor_id = cursorIdHistory.value[cursorIdHistory.value.length - 2];
    }

    // 検索結果のツイートを「投稿時刻が新しい順」に取得
    // タイムラインと異なり、検索結果は一度に 20 件しか返ってこない
    const query = `${searchQuery.value}${showRetweets.value ? 'include:nativeretweets' : ''}`;
    const result = await Twitter.searchTweets(selected_twitter_account.value.screen_name, query, cursor_id);
    if (result && result.tweets) {
        // 「リツイートを表示する」がオフの場合はリツイートのツイートを除外
        if (showRetweets.value === false) {
            result.tweets = result.tweets.filter(tweet => !tweet.retweeted_tweet);
        }

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
    }
    isFetching.value = false;
};

// 「さらに読み込む」ボタンが押されたら当該範囲の検索結果を取得
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

    // 検索結果のツイートを「投稿時刻が新しい順」に取得
    // タイムラインと異なり、検索結果は一度に 20 件しか返ってこない
    const query = `${searchQuery.value}${showRetweets.value ? 'include:nativeretweets' : ''}`;
    const result = await Twitter.searchTweets(selected_twitter_account.value.screen_name, query, item.cursor_id);
    if (result && result.tweets) {
        // 「リツイートを表示する」がオフの場合はリツイートのツイートを除外
        if (showRetweets.value === false) {
            result.tweets = result.tweets.filter(tweet => !tweet.retweeted_tweet);
        }

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

// 検索クエリが変更された場合、同じ検索クエリではなくなるのでタイムラインの内容をまっさらにする
watch(searchQuery, () => {
    timelineItems.value = [];
    cursorIdHistory.value = [];  // カーソル履歴をリセット
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにして再取得
watch(showRetweets, () => {
    timelineItems.value = [];
    cursorIdHistory.value = [];  // カーソル履歴をリセット
    performSearchTweets();
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
        const lastItem = timelineItems.value[timelineItems.value.length - 1];
        if (lastItem && lastItem.type === 'load_more') {
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