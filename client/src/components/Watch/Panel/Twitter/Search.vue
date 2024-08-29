<template>
    <div class="tab-content tab-content--search">
        <div class="search-header">
            <div class="search-input-wrapper" :class="{'search-input-wrapper--focused': isSearchFormFocused}">
                <Icon icon="fluent:search-16-filled" height="18px" />
                <input
                    v-model="searchQuery"
                    class="search-input"
                    type="text"
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
            <v-switch
                v-model="showRetweets"
                color="primary"
                hide-details
                density="comfortable"
                label="リツイートを表示する"
            />
        </div>
        <DynamicScroller ref="scroller" class="search-tweets" :direction="'vertical'" :items="tweets"
            :min-item-size="80" :buffer="400" v-show="tweets.length > 0">
            <template v-slot="{item, active}">
                <DynamicScrollerItem
                    :item="item"
                    :active="active"
                    :size-dependencies="[item.text, item.image_urls, item.movie_url]">
                    <Tweet :key="item.id" :tweet="item" />
                </DynamicScrollerItem>
            </template>
        </DynamicScroller>
        <div class="search-announce" v-show="tweets.length === 0">
            <div class="search-announce__heading">まだツイートがありません。</div>
            <div class="search-announce__text">
                <p class="mt-0 mb-0">右上の更新ボタンを押すと、最新の<br>ツイート検索結果を時系列で表示できます。</p>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { ref, watch, onMounted, nextTick } from 'vue';

import Tweet from '@/components/Watch/Panel/Twitter/Tweet.vue';
import Message from '@/message';
import Twitter, { ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';

const twitterStore = useTwitterStore();
const { selected_twitter_account } = storeToRefs(twitterStore);

const tweets = ref<ITweet[]>([]);
const showSettings = ref(false);
const showRetweets = ref(true);
const isFetching = ref(false);
const nextCursorId = ref<string | undefined>(undefined);
const previousCursorId = ref<string | undefined>(undefined);
const isSearchFormFocused = ref(false);
const searchQuery = ref('');
const scroller = ref<any>(null);

// 表示する最大ツイート数
const MAX_TWEETS = 1000;

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
        tweets.value = [];
        isFetching.value = false;
        return;
    }

    // 検索結果のツイートを「投稿時刻が新しい順」に取得
    // つまり後ろの要素になるほど古いツイートになる
    // タイムラインと異なり、検索結果は一度に 20 件しか返ってこない
    const result = await Twitter.searchTweets(selected_twitter_account.value.screen_name, searchQuery.value, nextCursorId.value);
    if (result && result.tweets) {
        // 「リツイートを表示する」がオフの場合はリツイートのツイートを除外
        if (showRetweets.value === false) {
            result.tweets = result.tweets.filter(tweet => !tweet.retweeted_tweet);
        }
        // 新しいツイートを取得したら tweets の先頭に追加
        // これで新しいツイートが上部に表示される
        tweets.value = [...result.tweets, ...tweets.value];
        // 次の検索結果を取得するためのカーソル ID を更新
        nextCursorId.value = result.next_cursor_id;
        // 初回実行時のみ、previousCursorId を更新
        // 2回目以降更新してしまうと previousCursorId がより新しいスナップショットに紐づいてしまうので更新しない
        // これ以降 previousCursorId が更新されるのは過去のツイートを遡って取得した際のみ
        if (previousCursorId.value === undefined) {
            previousCursorId.value = result.previous_cursor_id;
        }
    }
    isFetching.value = false;
};

const fetchOlderTweets = async () => {
    if (isFetching.value || !previousCursorId.value || tweets.value.length >= MAX_TWEETS) {
        return;
    }
    isFetching.value = true;
    if (!selected_twitter_account.value) {
        console.warn('selected_twitter_account is null');
        isFetching.value = false;
        return;
    }

    const result = await Twitter.searchTweets(selected_twitter_account.value.screen_name, searchQuery.value, previousCursorId.value);
    if (result && result.tweets) {
        if (showRetweets.value === false) {
            result.tweets = result.tweets.filter(tweet => !tweet.retweeted_tweet);
        }
        // 古いツイートを取得したら tweets の末尾に追加
        // これで古いツイートが下部に表示される
        tweets.value = [...tweets.value, ...result.tweets];
        // さらに過去の検索結果を取得するためのカーソル ID を更新
        previousCursorId.value = result.previous_cursor_id;
    }
    isFetching.value = false;
};

// 検索クエリが変更された場合、同じ検索クエリではなくなるのでタイムラインの内容をまっさらにした上でカーソル ID も消す
// この時点では検索処理自体は実行しない
watch(searchQuery, () => {
    tweets.value = [];
    nextCursorId.value = undefined;
    previousCursorId.value = undefined;
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにした上でカーソル ID も消して再取得
watch(showRetweets, () => {
    tweets.value = [];
    nextCursorId.value = undefined;
    previousCursorId.value = undefined;
    performSearchTweets();
});

const checkScrollPosition = () => {
    if (!scroller.value || !scroller.value.$el) return;

    const container = scroller.value.$el;
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;

    // スクロール位置が下部から 30px 以内に近づいたら追加のツイートを読み込む
    if (scrollHeight - scrollTop - clientHeight < 30) {
        fetchOlderTweets();
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
    padding: 0px 12px;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.search-tweets {
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

</style>