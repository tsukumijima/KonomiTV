<template>
    <div class="tweet" @click="handleTweetClick">
        <div v-if="tweet.retweeted_tweet" class="tweet__retweet-info">
            <svg xmlns="http://www.w3.org/2000/svg" width="16.25px" height="13px" viewBox="0 0 640 512" style="color: rgb(var(--v-theme-success-lighten-1));">
                <path fill="currentColor" d="M629.657 343.598L528.971 444.284c-9.373 9.372-24.568 9.372-33.941 0L394.343 343.598c-9.373-9.373-9.373-24.569 0-33.941l10.823-10.823c9.562-9.562 25.133-9.34 34.419.492L480 342.118V160H292.451a24.005 24.005 0 0 1-16.971-7.029l-16-16C244.361 121.851 255.069 96 276.451 96H520c13.255 0 24 10.745 24 24v222.118l40.416-42.792c9.285-9.831 24.856-10.054 34.419-.492l10.823 10.823c9.372 9.372 9.372 24.569-.001 33.941m-265.138 15.431A23.999 23.999 0 0 0 347.548 352H160V169.881l40.416 42.792c9.286 9.831 24.856 10.054 34.419.491l10.822-10.822c9.373-9.373 9.373-24.569 0-33.941L144.971 67.716c-9.373-9.373-24.569-9.373-33.941 0L10.343 168.402c-9.373 9.373-9.373 24.569 0 33.941l10.822 10.822c9.562 9.562 25.133 9.34 34.419-.491L96 169.881V392c0 13.255 10.745 24 24 24h243.549c21.382 0 32.09-25.851 16.971-40.971z"></path>
            </svg>
            <span class="ml-2"><a class="tweet__retweet-info-link" :href="getUserUrl(tweet.user)" target="_blank" @click.stop>{{ tweet.user.name }}</a>さんがリツイートしました</span>
        </div>
        <div class="tweet__main-content">
            <a class="tweet__user-icon" :href="getUserUrl(displayedTweet.user)" target="_blank" @click.stop>
                <img :src="displayedTweet.user.icon_url" alt="User Icon" class="tweet__user-icon" loading="lazy" decoding="async">
            </a>
            <div class="tweet__content">
                <div class="tweet__user-info">
                    <div class="tweet__user-info-left">
                        <a class="tweet__user-name" :href="getUserUrl(displayedTweet.user)" target="_blank" @click.stop >{{ displayedTweet.user.name }}</a>
                        <span class="tweet__user-screen-name">@{{ displayedTweet.user.screen_name }}</span>
                    </div>
                    <span class="tweet__timestamp">{{ Utils.apply28HourClock(dayjs(displayedTweet.created_at).format('MM/DD HH:mm:ss')) }}</span>
                </div>
                <p class="tweet__text" v-html="formattedText"></p>
                <div class="tweet__images" v-if="displayedTweet.image_urls && displayedTweet.image_urls.length > 0">
                    <a v-for="(url, index) in displayedTweet.image_urls" :key="index" :href="url" target="_blank" @click.stop>
                        <img :src="url" alt="Tweet Image" class="tweet__image" loading="lazy" decoding="async">
                    </a>
                </div>
                <video class="tweet__movie" v-if="proxyMovieUrl" :src="proxyMovieUrl" controls @click.stop></video>
                <a v-if="displayedTweet.quoted_tweet"
                    :href="getTweetUrl(displayedTweet.quoted_tweet)"
                    target="_blank" class="tweet__quoted-tweet" @click.stop>
                    <div class="tweet__quoted-user-info">
                        <span class="tweet__quoted-user-name">{{ displayedTweet.quoted_tweet.user.name }}</span>
                        <span class="tweet__quoted-user-screen-name">@{{ displayedTweet.quoted_tweet.user.screen_name }}</span>
                    </div>
                    <p class="tweet__quoted-text" v-html="formattedQuotedText"></p>
                </a>
                <div class="tweet__actions">
                    <button v-ripple class="tweet__action tweet__action--retweet" :class="{ 'tweet__action--active': displayedTweet.retweeted }"
                        :disabled="isReactionDisabled"
                        @click.stop="handleRetweet">
                        <svg xmlns="http://www.w3.org/2000/svg" role="img" width="1.25em" height="1em" viewBox="0 0 640 512">
                            <path fill="currentColor" d="M629.657 343.598L528.971 444.284c-9.373 9.372-24.568 9.372-33.941 0L394.343 343.598c-9.373-9.373-9.373-24.569 0-33.941l10.823-10.823c9.562-9.562 25.133-9.34 34.419.492L480 342.118V160H292.451a24.005 24.005 0 0 1-16.971-7.029l-16-16C244.361 121.851 255.069 96 276.451 96H520c13.255 0 24 10.745 24 24v222.118l40.416-42.792c9.285-9.831 24.856-10.054 34.419-.492l10.823 10.823c9.372 9.372 9.372 24.569-.001 33.941m-265.138 15.431A23.999 23.999 0 0 0 347.548 352H160V169.881l40.416 42.792c9.286 9.831 24.856 10.054 34.419.491l10.822-10.822c9.373-9.373 9.373-24.569 0-33.941L144.971 67.716c-9.373-9.373-24.569-9.373-33.941 0L10.343 168.402c-9.373 9.373-9.373 24.569 0 33.941l10.822 10.822c9.562 9.562 25.133 9.34 34.419-.491L96 169.881V392c0 13.255 10.745 24 24 24h243.549c21.382 0 32.09-25.851 16.971-40.971z"></path>
                        </svg>
                        <span>{{ displayedTweet.retweet_count }}</span>
                    </button>
                    <button v-ripple class="tweet__action tweet__action--favorite" :class="{ 'tweet__action--active': displayedTweet.favorited }"
                        :disabled="isReactionDisabled"
                        @click.stop="handleFavorite">
                        <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 512 512">
                            <path fill="currentColor" d="M462.3 62.6C407.5 15.9 326 24.3 275.7 76.2L256 96.5l-19.7-20.3C186.1 24.3 104.5 15.9 49.7 62.6c-62.8 53.6-66.1 149.8-9.9 207.9l193.5 199.8c12.5 12.9 32.8 12.9 45.3 0l193.5-199.8c56.3-58.1 53-154.3-9.8-207.9"></path>
                        </svg>
                        <span>{{ displayedTweet.favorite_count }}</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { storeToRefs } from 'pinia';
import { computed, toRef } from 'vue';

import Message from '@/message';
import Bluesky from '@/services/Bluesky';
import Twitter, { ITweet } from '@/services/Twitter';
import { ITweetUser } from '@/services/Twitter';
import useTwitterStore from '@/stores/TwitterStore';
import Utils, { dayjs } from '@/utils';

const props = defineProps<{
    tweet: ITweet;
}>();

const twitterStore = useTwitterStore();
const { selected_twitter_account } = storeToRefs(twitterStore);

const tweet = toRef(props, 'tweet');

// RT / リポスト表示では外側の「誰が共有したか」と内側の原投稿を分け、本文や画像は原投稿側を表示する
const displayedTweet = computed(() => tweet.value.retweeted_tweet || tweet.value);

const formatText = (text: string, source: ITweet['source']) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const mentionRegex = source === 'Bluesky' ? /@([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z][a-zA-Z0-9.-]*)/g : /@(\w+)/g;
    const hashtagRegex = /[#＃]([\w\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}ー]+)/gu;

    // URLを先に処理し、プレースホルダーで置き換える
    const urls: string[] = [];
    let formattedText = text.replace(urlRegex, (url) => {
        urls.push(url);
        return `__URL_PLACEHOLDER_${urls.length - 1}__`;
    });

    // メンションとハッシュタグを処理
    // Bluesky 投稿は bsky.app のプロフィール・ハッシュタグページに飛ばし、Twitter 投稿の既存導線と混ざらないようにする
    formattedText = formattedText.replace(mentionRegex, (_match, screenName) => {
        const mentionUrl = source === 'Bluesky' ? `https://bsky.app/profile/${screenName}` : `https://x.com/${screenName}`;
        return `<a class="tweet-link" href="${mentionUrl}" target="_blank">@${screenName}</a>`;
    });
    formattedText = formattedText.replace(hashtagRegex, (_match, hashtag) => {
        const hashtagUrl = source === 'Bluesky' ?
            `https://bsky.app/hashtag/${encodeURIComponent(hashtag)}` :
            `https://x.com/hashtag/${encodeURIComponent(hashtag)}`;
        return `<a class="tweet-link" href="${hashtagUrl}" target="_blank">#${hashtag}</a>`;
    });

    // プレースホルダーを実際のURLリンクに置き換える
    formattedText = formattedText.replace(/__URL_PLACEHOLDER_(\d+)__/g, (_, index) => {
        const url = urls[parseInt(index)];
        return `<a class="tweet-link" href="${url}" target="_blank">${url}</a>`;
    });

    return formattedText;
};

const formattedText = computed(() => formatText(displayedTweet.value.text, displayedTweet.value.source));
const formattedQuotedText = computed(() => displayedTweet.value.quoted_tweet ?
    formatText(displayedTweet.value.quoted_tweet.text, displayedTweet.value.quoted_tweet.source) : '');

// Twitter 側の仕様変更により、許可されたオリジン以外からの動画 URL への直接アクセスが 403 になるため、
// KonomiTV サーバーの動画プロキシ API 経由で動画を配信する
const proxyMovieUrl = computed(() => {
    const movieUrl = displayedTweet.value.movie_url;
    if (!movieUrl) return null;
    if (displayedTweet.value.source === 'Bluesky') return movieUrl;
    return `${Utils.api_base_url}/twitter/video-proxy?url=${encodeURIComponent(movieUrl)}`;
});

const getUserUrl = (user: ITweetUser) => {
    // 投稿元サービスに合わせてプロフィール URL を生成し、Bluesky 投稿から X 側へ飛ばないようにする
    if (user.source === 'Bluesky') {
        return `https://bsky.app/profile/${user.screen_name}`;
    }
    return `https://x.com/${user.screen_name}`;
};

const getBlueskyRecordKey = (postId: string) => {
    // Bluesky の Tweet.id は AT URI そのものなので、bsky.app の URL には末尾の record key だけを使う
    return postId.split('/').at(-1) ?? postId;
};

const getTweetUrl = (targetTweet: ITweet) => {
    // Tweet スキーマは共通だが、投稿詳細 URL はサービスごとに組み立て方が異なる
    if (targetTweet.source === 'Bluesky') {
        return `https://bsky.app/profile/${targetTweet.user.screen_name}/post/${getBlueskyRecordKey(targetTweet.id)}`;
    }
    return `https://x.com/${targetTweet.user.screen_name}/status/${targetTweet.id}`;
};

const getSelectedBlueskyHandle = () => {
    const selectedAccount = twitterStore.selected_account;
    // Bluesky 投稿への操作は現在選択中の Bluesky セッションで行う
    // 紐付けアカウントでは Bluesky 側だけを取り出し、Twitter 側の選択状態と混ぜない
    if (selectedAccount?.kind === 'Bluesky') {
        return selectedAccount.bluesky_account.handle;
    }
    if (selectedAccount?.kind === 'Linked') {
        return selectedAccount.account_link.bluesky_account.handle;
    }
    return null;
};

const isReactionDisabled = computed(() => {
    // 表示中の投稿元サービスを操作できるアカウントが選択されていない場合は、誤操作に見える無反応を避ける
    if (displayedTweet.value.source === 'Bluesky') {
        return getSelectedBlueskyHandle() === null;
    }
    return selected_twitter_account.value === null;
});

const handleTweetClick = (event: MouseEvent) => {
    // テキストが選択されている場合は、クリックイベントを無視する
    if (window.getSelection()?.toString()) {
        return;
    }
    // Check if the clicked element or its parent is a link or a button
    const isClickableElement = (event.target as HTMLElement).closest('a, button, video');
    if (!isClickableElement) {
        window.open(getTweetUrl(displayedTweet.value), '_blank');
    }
};

const handleRetweet = async () => {
    if (displayedTweet.value.source === 'Bluesky') {
        const handle = getSelectedBlueskyHandle();
        // Bluesky の ID は AT URI で、CID はサーバー側で直前取得する
        if (handle === null) {
            Message.warning('Bluesky 投稿を操作するには、Bluesky アカウントまたは紐付けアカウントを選択してください。');
            return;
        }
        if (displayedTweet.value.retweeted) {
            const result = await Bluesky.cancelRepost(handle, displayedTweet.value.id);
            if (result && result.is_success) {
                displayedTweet.value.retweeted = false;
                displayedTweet.value.retweet_count--;
            }
        } else {
            const result = await Bluesky.repost(handle, displayedTweet.value.id);
            if (result && result.is_success) {
                displayedTweet.value.retweeted = true;
                displayedTweet.value.retweet_count++;
            }
        }
        return;
    }

    // Twitter 投稿への操作は TwitterScrapeBrowser の選択アカウントが必要
    // Bluesky 単独アカウント選択中に Twitter 投稿が残っていても操作 API を呼ばない
    if (selected_twitter_account.value === null) {
        Message.warning('Twitter 投稿を操作するには、Twitter アカウントまたは紐付けアカウントを選択してください。');
        return;
    }

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
    if (displayedTweet.value.source === 'Bluesky') {
        const handle = getSelectedBlueskyHandle();
        // いいねも AT URI だけを渡し、作成時の CID と取り消し時の viewer.like はサーバー側で引き直す
        if (handle === null) {
            Message.warning('Bluesky 投稿を操作するには、Bluesky アカウントまたは紐付けアカウントを選択してください。');
            return;
        }
        if (displayedTweet.value.favorited) {
            const result = await Bluesky.cancelFavorite(handle, displayedTweet.value.id);
            if (result && result.is_success) {
                displayedTweet.value.favorited = false;
                displayedTweet.value.favorite_count--;
            }
        } else {
            const result = await Bluesky.favorite(handle, displayedTweet.value.id);
            if (result && result.is_success) {
                displayedTweet.value.favorited = true;
                displayedTweet.value.favorite_count++;
            }
        }
        return;
    }

    // Twitter のいいね操作は現在の Twitter アカウントに紐づけて実行する
    if (selected_twitter_account.value === null) {
        Message.warning('Twitter 投稿を操作するには、Twitter アカウントまたは紐付けアカウントを選択してください。');
        return;
    }

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
    @include smartphone-horizontal {
        font-size: 11.5px;
    }
    @include smartphone-vertical {
        font-size: 12px;
    }

    &:hover {
        background-color: rgba(var(--v-theme-on-surface), 0.04);
    }
    // タッチデバイスで hover を無効にする
    @media (hover: none) {
        &:hover {
            background-color: transparent;
        }
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
        display: block;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        margin-right: 8px;
        transition: opacity 0.15s ease;

        &:hover {
            opacity: 0.9;
        }
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                opacity: 1;
            }
        }
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
        word-break: break-word;
        user-select: text;
    }

    &__images {
        display: flex;
        flex-wrap: wrap;
        margin-bottom: 8px;
    }

    &__image {
        display: block;
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

    &__movie {
        display: block;
        max-width: 100%;
        max-height: 300px;
        object-fit: cover;
        margin-top: 8px;
        margin-right: 6px;
        border-radius: 8px;
        margin-bottom: 8px;
        cursor: auto;
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
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                background-color: transparent;
            }
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
        word-break: break-word;
    }

    &__actions {
        display: flex;
        position: relative;
        margin-top: -2px;
    }

    &__action {
        display: flex;
        align-items: center;
        margin-right: 20px;
        padding: 3px 4px;
        border-radius: 4px;
        color: rgba(var(--v-theme-on-surface), 0.6);
        font-size: 12px;
        background: none;
        border: none;
        transition: color 0.15s ease, background-color 0.15s ease;
        user-select: none;
        outline: none;
        cursor: pointer;

        &:hover {
            background-color: rgba(var(--v-theme-on-surface), 0.1);
        }
        &:disabled {
            color: rgba(var(--v-theme-on-surface), 0.3);
            background: none;
            cursor: not-allowed;
        }
        &:disabled:hover {
            background: none;
        }
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                background-color: transparent;
            }
        }

        &--retweet {
            &.tweet__action--active {
                color: rgb(var(--v-theme-success));
            }
        }

        &--favorite {
            &.tweet__action--active {
                color: rgb(var(--v-theme-primary-darken-1));
            }
        }

        span {
            margin-left: 6px;
        }
    }
}

</style>
