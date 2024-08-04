<template>
    <div class="tab-content tab-content--search">
        <div class="search-header">
            <div class="search-input-wrapper">
                <Icon icon="fluent:search-16-filled" height="18px" />
                <input
                    v-model="searchQuery"
                    class="search-input"
                    type="text"
                    placeholder="検索キーワードを入力"
                    @keydown="onKeyDown($event)"
                />
            </div>
            <div class="d-flex align-center ml-auto h-100">
                <button v-ripple class="search-header__settings" @click="toggleSettings">
                    <Icon icon="fluent:settings-16-filled" width="20" />
                </button>
                <button v-ripple class="search-header__refresh" style="color: rgb(var(--v-theme-twitter-lighten-1))"
                    @click="performSearchTweets" v-tooltip.bottom="'検索結果を更新'">
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
        <DynamicScroller class="search-tweets" :direction="'vertical'" :items="tweets" :min-item-size="80">
            <template v-slot="{item, active}">
            <DynamicScrollerItem :item="item" :active="active" :size-dependencies="[item.text, item.image_urls, item.movie_url]">
                <Tweet :key="item.id" :tweet="item" />
                </DynamicScrollerItem>
            </template>
        </DynamicScroller>
    </div>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { ref, watch } from 'vue';

import Tweet from '@/components/Watch/Panel/Twitter/Tweet.vue';
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
const searchQuery = ref('');

// 表示する最大ツイート数
const MAX_TWEETS = 50;

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
    if (isFetching.value || !searchQuery.value.trim()) {
        return;
    }
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_twitter_account.value) {
        console.warn('selected_twitter_account is null');
        tweets.value = [];
        isFetching.value = false;
        return;
    }

    // 検索結果のツイートを「投稿時刻が新しい順」に取得
    // つまり後ろの要素になるほど古いツイートになる
    const result = await Twitter.searchTweets(selected_twitter_account.value.screen_name, searchQuery.value, nextCursorId.value);
    if (result && result.tweets) {
        // 「リツイートを表示しない」がチェックされている場合はリツイートのツイートを除外
        if (showRetweets.value === false) {
            result.tweets = result.tweets.filter(tweet => !tweet.retweeted_tweet);
        }
        // 新しいツイートを取得したら tweets の先頭に追加し、tweets.value を更新
        tweets.value = [ ...result.tweets, ...tweets.value];
        // 次の検索結果を取得するためのカーソル ID を更新
        nextCursorId.value = result.next_cursor_id;
    }
    isFetching.value = false;
};

// 検索クエリが変更された場合、同じ検索クエリではなくなるのでタイムラインの内容をまっさらにした上でカーソル ID も消す
// この時点では検索処理自体は実行しない
watch(searchQuery, () => {
    tweets.value = [];
    nextCursorId.value = undefined;
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにした上でカーソル ID も消して再取得
watch(showRetweets, () => {
    tweets.value = [];
    nextCursorId.value = undefined;
    performSearchTweets();
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

</style>