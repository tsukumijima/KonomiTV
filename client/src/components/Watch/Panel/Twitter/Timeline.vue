<template>
    <div class="tab-content tab-content--timeline">
        <div class="timeline-header">
            <Icon icon="fluent:home-16-filled" height="18px" />
            <h2 class="timeline-header__title ml-2">タイムライン</h2>
            <div class="d-flex align-center ml-auto">
                <button v-ripple class="timeline-header__settings" @click="toggleSettings">
                    <Icon icon="fluent:settings-16-filled" width="20" />
                </button>
                <button v-ripple class="timeline-header__refresh" style="color: rgb(var(--v-theme-twitter-lighten-1))" @click="fetchTweets"
                    v-tooltip.bottom="'タイムラインを更新'">
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
        <div class="timeline-tweets" ref="tweetContainer">
            <div v-for="tweet in visibleTweets" :key="tweet.id" class="tweet-wrapper">
                <Tweet :tweet="tweet" />
            </div>
            <div ref="loadingTrigger" class="loading-trigger"></div>
        </div>
    </div>
</template>

<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import { ref, onMounted, watch } from 'vue';

import Tweet from '@/components/Watch/Panel/Twitter/Tweet.vue';
import Twitter, { ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import useUserStore from '@/stores/UserStore';

const twitterStore = useTwitterStore();
const { selected_twitter_account } = storeToRefs(twitterStore);

const tweets = ref<ITweet[]>([]);
const visibleTweets = ref<ITweet[]>([]);
const showSettings = ref(false);
const showRetweets = ref(true);
const isFetching = ref(false);
const tweetContainer = ref<HTMLElement | null>(null);
const loadingTrigger = ref<HTMLElement | null>(null);
const observer = ref<IntersectionObserver | null>(null);
const next_cursor_id = ref<string | undefined>(undefined);

const MAX_TWEETS = 100;  // データとして保持する最大ツイート数

const toggleSettings = () => {
    showSettings.value = !showSettings.value;
};

const fetchTweets = async () => {
    if (isFetching.value) return;
    isFetching.value = true;
    await useUserStore().fetchUser();
    if (!selected_twitter_account.value) {
        console.warn('selected_twitter_account is null');
        tweets.value = [];
        isFetching.value = false;
        return;
    }

    // タイムラインのツイートを「投稿時刻が新しい順」に取得
    // つまり新しいツイートを取得したら tweets の先頭に追加する必要がある
    const result = await Twitter.getHomeTimeline(selected_twitter_account.value.screen_name, next_cursor_id.value);
    if (result && result.tweets) {
        const newTweets = result.tweets.filter(tweet => showRetweets.value || !tweet.retweeted_tweet);
        tweets.value = next_cursor_id.value ? [ ...newTweets, ...tweets.value] : newTweets;
        tweets.value = tweets.value.slice(0, MAX_TWEETS);  // 最大100ツイートに制限
        next_cursor_id.value = result.next_cursor_id;
        updateVisibleTweets();
    }
    isFetching.value = false;
};

const updateVisibleTweets = () => {
    visibleTweets.value = tweets.value;
};

const loadMoreTweets = () => {
    if (tweets.value.length < MAX_TWEETS) {
        fetchTweets();
    }
};

onMounted(() => {
    observer.value = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && !isFetching.value) {
            loadMoreTweets();
        }
    }, { threshold: 0.5 });

    if (loadingTrigger.value) {
        observer.value.observe(loadingTrigger.value);
    }

    fetchTweets();
});

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにした上で再取得
watch(showRetweets, () => {
    tweets.value = tweets.value.filter(tweet => showRetweets.value || !tweet.retweeted_tweet);
    visibleTweets.value = [];
    loadMoreTweets();
});

// 選択中の Twitter アカウントが変更されたらタイムラインの内容をまっさらにした上で再取得
// このイベントはコンポーネントのマウント時にも実行される (マウント時に selected_twitter_account が変更されるため)
watch(selected_twitter_account, () => {
    tweets.value = [];
    visibleTweets.value = [];
    fetchTweets();
});

</script>
<style lang="scss" scoped>

.loading-trigger {
    height: 20px;
}

.tab-content--timeline {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: visible !important;
}

.timeline-header {
    display: flex;
    align-items: center;
    padding-top: 4px;
    padding: 8px 12px;
    border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);

    &__title {
        font-size: 16px;
        font-weight: bold;
        margin: 0;
    }

    &__settings {
        display: flex;
        align-items: center;
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
        display: flex;
        align-items: center;
        padding: 4px 8px;
        margin-left: 6px;
        border-radius: 4px;
        background: none;
        border: none;
        font-size: 13px;
        cursor: pointer;
        color: rgb(var(--v-theme-text)) !important;
        background-color: rgb(var(--v-theme-twitter));
        transition: opacity 0.15s ease;
        opacity: 1;

        &:hover {
            opacity: 0.85;
        }
    }
}

.timeline-settings {
    padding: 0px 12px;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    background-color: rgb(var(--v-theme-background-lighten-1));
}

.timeline-tweets {
    flex-grow: 1;
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

</style>