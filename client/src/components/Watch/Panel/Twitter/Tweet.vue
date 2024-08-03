<template>
    <a :href="`https://x.com/${displayedTweet.user.screen_name}/status/${displayedTweet.id}`" target="_blank" class="tweet">
        <object v-if="tweet.retweeted_tweet" class="tweet__retweet-info">
            <Icon icon="fa-solid:retweet" height="13px" style="color: rgb(var(--v-theme-success-lighten-1))" />
            <span class="ml-2"><a class="tweet__retweet-info-link" :href="`https://x.com/${tweet.user.screen_name}`" target="_blank">{{ tweet.user.name }}</a>さんがリツイートしました</span>
        </object>
        <object class="tweet__main-content">
            <a :href="`https://x.com/${displayedTweet.user.screen_name}`" target="_blank">
                <img :src="displayedTweet.user.icon_url" alt="User Icon" class="tweet__user-icon" loading="lazy" decoding="async">
            </a>
            <div class="tweet__content">
                <div class="tweet__user-info">
                    <a :href="`https://x.com/${displayedTweet.user.screen_name}`" target="_blank" class="tweet__user-info-left">
                        <span class="tweet__user-name">{{ displayedTweet.user.name }}</span>
                        <span class="tweet__user-screen-name">@{{ displayedTweet.user.screen_name }}</span>
                    </a>
                    <span class="tweet__timestamp">{{ dayjs(displayedTweet.created_at).format('MM/DD HH:mm') }}</span>
                </div>
                <p class="tweet__text" v-html="formattedText"></p>
                <div v-if="displayedTweet.image_urls && displayedTweet.image_urls.length > 0" class="tweet__images">
                    <img v-for="(url, index) in displayedTweet.image_urls" :key="index" :src="url" alt="Tweet Image" class="tweet__image" loading="lazy" decoding="async">
                </div>
                <a v-if="displayedTweet.quoted_tweet"
                    :href="`https://x.com/${displayedTweet.quoted_tweet.user.screen_name}/status/${displayedTweet.quoted_tweet.id}`"
                    target="_blank" class="tweet__quoted-tweet">
                    <div class="tweet__quoted-user-info">
                        <span class="tweet__quoted-user-name">{{ displayedTweet.quoted_tweet.user.name }}</span>
                        <span class="tweet__quoted-user-screen-name">@{{ displayedTweet.quoted_tweet.user.screen_name }}</span>
                    </div>
                    <p class="tweet__quoted-text" v-html="formattedQuotedText"></p>
                </a>
                <div class="tweet__actions">
                    <button v-ripple class="tweet__action tweet__action--retweet" :class="{ 'tweet__action--active': displayedTweet.retweeted }"
                        @click.stop.prevent="handleRetweet">
                        <Icon icon="fa-solid:retweet" />
                        <span>{{ displayedTweet.retweet_count }}</span>
                    </button>
                    <button v-ripple class="tweet__action tweet__action--favorite" :class="{ 'tweet__action--active': displayedTweet.favorited }"
                        @click.stop.prevent="handleFavorite">
                        <Icon icon="fa-solid:heart" />
                        <span>{{ displayedTweet.favorite_count }}</span>
                    </button>
                </div>
            </div>
        </object>
    </a>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { ref, computed } from 'vue';

import Twitter, { ITweet } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import { dayjs } from '@/utils';

const props = defineProps<{
    tweet: ITweet;
}>();

const twitterStore = useTwitterStore();
const { selected_twitter_account } = storeToRefs(twitterStore);

const tweet = ref(props.tweet);

const displayedTweet = computed(() => tweet.value.retweeted_tweet || tweet.value);

const formatText = (text: string) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const mentionRegex = /@(\w+)/g;
    const hashtagRegex = /#([\w\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}ー]+)/gu;

    return text
        .replace(urlRegex, '<a class="tweet-link" href="$1" target="_blank">$1</a>')
        .replace(mentionRegex, '<a class="tweet-link" href="https://x.com/$1" target="_blank">@$1</a>')
        .replace(hashtagRegex, '<a class="tweet-link" href="https://x.com/hashtag/$1" target="_blank">#$1</a>');
};

const formattedText = computed(() => formatText(displayedTweet.value.text));
const formattedQuotedText = computed(() => displayedTweet.value.quoted_tweet ? formatText(displayedTweet.value.quoted_tweet.text) : '');

const handleRetweet = async () => {
    if (!selected_twitter_account.value) return;

    if (displayedTweet.value.retweeted) {
        const result = await Twitter.cancelRetweet(selected_twitter_account.value.screen_name, displayedTweet.value.id);
        if (result && result.is_success) {
            displayedTweet.value.retweeted = false;
            displayedTweet.value.retweet_count--;
        }
    } else {
        const result = await Twitter.retweet(selected_twitter_account.value.screen_name, displayedTweet.value.id);
        if (result && result.is_success) {
            displayedTweet.value.retweeted = true;
            displayedTweet.value.retweet_count++;
        }
    }
};

const handleFavorite = async () => {
    if (!selected_twitter_account.value) return;

    if (displayedTweet.value.favorited) {
        const result = await Twitter.cancelFavorite(selected_twitter_account.value.screen_name, displayedTweet.value.id);
        if (result && result.is_success) {
            displayedTweet.value.favorited = false;
            displayedTweet.value.favorite_count--;
        }
    } else {
        const result = await Twitter.favorite(selected_twitter_account.value.screen_name, displayedTweet.value.id);
        if (result && result.is_success) {
            displayedTweet.value.favorited = true;
            displayedTweet.value.favorite_count++;
        }
    }
};

</script>
<style lang="scss" scoped>
.tweet {
    display: flex;
    flex-direction: column;
    max-width: 100%;
    padding: 6px 12px;
    border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
    color: rgb(var(--v-theme-text));
    font-size: 13px;
    line-height: 1.45;
    transition: background-color 0.15s ease;
    cursor: pointer;

    &:hover {
        background-color: rgba(var(--v-theme-on-surface), 0.04);
    }

    :deep(.tweet-link) {
        color: rgb(var(--v-theme-twitter));
        text-decoration: none;

        &:hover {
            text-decoration: underline;
        }
    }

    &__retweet-info {
        display: flex;
        align-items: center;
        color: rgba(var(--v-theme-on-surface), 0.6);
        font-size: 11px;
        margin-bottom: 6px;

        .icon {
            margin-right: 4px;
        }

        &-link {
            text-decoration: none;

            &:hover {
                text-decoration: underline;
            }
        }
    }

    &__main-content {
        display: flex;
    }

    &__user-icon {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        margin-right: 8px;
    }

    &__content {
        flex-grow: 1;
    }

    &__user-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
        line-height: 1.3;
    }

    &__user-info-left {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
    }

    &__user-name {
        font-weight: bold;
        margin-right: 4px;
        text-decoration: none;

        &:hover {
            text-decoration: underline;
        }
    }

    &__user-screen-name {
        flex-shrink: 0;
        font-size: 12px;
        color: rgb(var(--v-theme-text-darken-1));
    }

    &__timestamp {
        margin-left: 8px;
        flex-shrink: 0;
        font-size: 11.5px;
        color: rgb(var(--v-theme-text-darken-1));
    }

    &__text {
        margin-bottom: 6px;
        white-space: pre-wrap;
        word-break: break-all;
    }

    &__images {
        display: flex;
        flex-wrap: wrap;
        margin-bottom: 8px;
    }

    &__image {
        max-width: 100%;
        max-height: 175px;
        object-fit: cover;
        margin-top: 8px;
        margin-right: 6px;
        border-radius: 8px;

        &:first-of-type {
            margin-top: 4px;
        }
    }

    &__quoted-tweet {
        display: block;
        border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
        border-radius: 8px;
        padding: 8px;
        margin-bottom: 8px;
        transition: background-color 0.15s ease;
        cursor: pointer;

        &:hover {
            background-color: rgba(var(--v-theme-on-surface), 0.04);
        }
    }

    &__quoted-user-info {
        margin-bottom: 4px;
    }

    &__quoted-user-name {
        font-weight: bold;
        margin-right: 4px;
    }

    &__quoted-user-screen-name {
        color: rgb(var(--v-theme-text-darken-1));
    }

    &__quoted-text {
        display: -webkit-box;
        -webkit-line-clamp: 3;  // 3行までに制限
        -webkit-box-orient: vertical;
        overflow: hidden;
        word-break: break-all;
    }

    &__actions {
        display: flex;
    }

    &__action {
        display: flex;
        align-items: center;
        padding: 2px 3px;
        border-radius: 4px;
        margin-right: 20px;
        color: rgba(var(--v-theme-on-surface), 0.6);
        font-size: 12px;
        background: none;
        border: none;
        transition: color 0.15s ease;
        cursor: pointer;

        &--retweet {
            &:hover {
                color: rgb(var(--v-theme-success-darken-1));
            }
            &.tweet__action--active {
                color: rgb(var(--v-theme-success));
                &:hover {
                    color: rgb(var(--v-theme-success-darken-1));
                }
            }
        }

        &--favorite {
            &:hover {
                color: rgb(var(--v-theme-primary-darken-2));
            }
            &.tweet__action--active {
                color: rgb(var(--v-theme-primary-darken-1));
                &:hover {
                    color: rgb(var(--v-theme-primary-darken-2));
                }
            }
        }


        span {
            margin-left: 6px;
        }
    }
}

</style>