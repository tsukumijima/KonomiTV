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
        <div class="timeline-tweets">
            <DynamicScroller
                :items="tweets"
                :min-item-size="80"
                class="scroller"
            >
                <template v-slot="{ item, index, active }">
                    <DynamicScrollerItem
                        :item="item"
                        :active="active"
                        :data-index="index"
                        :size-dependencies="[
                            item.text,
                            item.media,
                            item.quoted_tweet,
                            item.retweeted_tweet
                        ]"
                    >
                        <Tweet :tweet="item" />
                    </DynamicScrollerItem>
                </template>
            </DynamicScroller>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { ref, watch } from 'vue';
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller';

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

    const result = await Twitter.getHomeTimeline(selected_twitter_account.value.screen_name);
    if (result && result.tweets) {
        for (const tweet of result.tweets) {
            if (!showRetweets.value && tweet.retweeted_tweet) continue;
            tweets.value.unshift(tweet);
        }
        // 100件を超えたら古いツイートから削除
        if (tweets.value.length > 100) {
            tweets.value.splice(100);
        }
    }
    isFetching.value = false;
};

// 「リツイートを表示する」のスイッチが変更されたらタイムラインの内容をまっさらにした上で再取得
watch(showRetweets, () => {
    tweets.value = [];
    fetchTweets();
});

// 選択中の Twitter アカウントが変更されたらタイムラインの内容をまっさらにした上で再取得
// このイベントはコンポーネントのマウント時にも実行される
watch(selected_twitter_account, () => {
    tweets.value = [];
    fetchTweets();
});

</script>
<style lang="scss" scoped>
.timeline-tweets {
    flex: 1;
    overflow: hidden;
}

.scroller {
    height: 100%;
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