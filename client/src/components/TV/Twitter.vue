<template>
    <div class="twitter-container">
        <div class="tab-container"></div>
        <div class="tab-button-container">
            <div v-ripple class="tab-button" :class="{'tab-button--active': active_tab === 'Search'}"
                @click="active_tab = 'Search'">
                <Icon icon="fluent:search-16-filled" height="18px" />
                <span class="tab-button__text">ツイート検索</span>
            </div>
            <div v-ripple class="tab-button" :class="{'tab-button--active': active_tab === 'Timeline'}"
                @click="active_tab = 'Timeline'">
                <Icon icon="fluent:home-16-regular" height="18px" />
                <span class="tab-button__text">タイムライン</span>
            </div>
            <div v-ripple class="tab-button" :class="{'tab-button--active': active_tab === 'Capture'}"
                @click="active_tab = 'Capture'">
                <Icon icon="fluent:image-copy-20-regular" height="18px" />
                <span class="tab-button__text">キャプチャ</span>
            </div>
        </div>
        <div class="tweet-form">
            <div class="tweet-form__hashtag">
                <input class="tweet-form__hashtag-form" type="text" placeholder="#ハッシュタグ"
                    v-model="tweet_hashtag" @input="changeTweetLetterCount()">
                <div v-ripple class="tweet-form__hashtag-memory-button">
                    <Icon icon="fluent:clipboard-text-ltr-32-regular" height="22px" />
                </div>
            </div>
            <textarea class="tweet-form__textarea" placeholder="ツイート"
                v-model="tweet_text" @input="changeTweetLetterCount()">
            </textarea>
            <div class="tweet-form__control">
                <div v-ripple class="account-button" :class="{'account-button--no-login': !this.is_logged_in_twitter}"
                    @click="clickAccountButton()">
                    <img class="account-button__icon"
                        :src="this.is_logged_in_twitter ? this.selected_twitter_account.icon_url : '/assets/images/account-icon-default.png'">
                    <span class="account-button__screen-name">
                        {{this.is_logged_in_twitter ? `@${this.selected_twitter_account.screen_name}` : '連携されていません'}}
                    </span>
                    <Icon class="account-button__menu" icon="fluent:more-circle-20-regular" width="22px" />
                </div>
                <div class="limit-meter">
                    <div class="limit-meter__content" :class="{
                        'limit-meter__content--yellow': this.tweet_letter_count <= 20,
                        'limit-meter__content--red': this.tweet_letter_count <= 0,
                    }">
                        <Icon icon="fa-brands:twitter" width="12px" style="margin-right: -2px;" />
                        <span>{{tweet_letter_count}}</span>
                    </div>
                    <div class="limit-meter__content">
                        <Icon icon="fluent:image-16-filled" width="14px" />
                        <span>0/4</span>
                    </div>
                </div>
                <button v-ripple class="tweet-button"
                    :disabled="!this.is_logged_in_twitter || this.tweet_letter_count === 140 || this.tweet_letter_count < 0"
                    @click="sendTweet()">
                    <Icon icon="fa-brands:twitter" height="16px" />
                    <span class="ml-1">ツイート</span>
                </button>
            </div>
        </div>
        <div class="twitter-account-list" :class="{'twitter-account-list--display': is_twitter_account_list_display}">
            <div v-ripple class="twitter-account" v-for="twitter_account in user.twitter_accounts" :key="twitter_account.id"
                @click="updateSelectedTwitterAccount(twitter_account)">
                <img class="twitter-account__icon" :src="twitter_account.icon_url">
                <div class="twitter-account__info">
                    <div class="twitter-account__name">{{twitter_account.name}}</div>
                    <div class="twitter-account__screen-name">@{{twitter_account.screen_name}}</div>
                </div>
                <Icon class="twitter-account__check" icon="fluent:checkmark-16-filled" width="24px"
                    v-show="twitter_account.id === selected_twitter_account_id" />
            </div>
        </div>
    </div>
</template>
<script lang="ts">

import axios from 'axios';
import Vue, { PropType } from 'vue';

import { IChannel, ITwitterAccount, IUser } from '@/interface';
import Utils, { TVUtils } from '@/utils';

export default Vue.extend({
    name: 'Twitter',
    props: {
        // チャンネル情報
        channel: {
            type: Object as PropType<IChannel>,
            required: true,
        },
        // プレイヤーのインスタンス
        player: {
            type: null as PropType<any>,  // 代入当初は null になるため苦肉の策
            required: true,
        }
    },
    data() {
        return {

            // ログイン中かどうか
            is_logged_in: Utils.getAccessToken() !== null,

            // Twitter アカウントを1つでも連携しているかどうか
            is_logged_in_twitter: false,

            // ユーザーアカウントの情報
            // ログインしていない場合は null になる
            user: null as IUser | null,

            // 現在ツイート対象として選択されている Twitter アカウント
            selected_twitter_account: null as ITwitterAccount | null,

            // 現在ツイート対象として選択されている Twitter アカウントの ID
            selected_twitter_account_id: Utils.getSettingsItem('selected_twitter_account_id') as number | null,

            // 連携している Twitter アカウントリストを表示しているか
            is_twitter_account_list_display: false,

            // アクティブなタブ
            active_tab: 'Capture' as ('Search' | 'Timeline' | 'Capture'),

            // ツイートのハッシュタグ
            tweet_hashtag: '',

            // ツイート本文
            tweet_text: '',

            // 文字数カウント
            tweet_letter_count: 140,
        }
    },
    async created() {

        // ユーザーモデルの初期値
        this.user = {
            id: 0,
            name: '',
            is_admin: true,
            niconico_user_id: null,
            niconico_user_name: null,
            niconico_user_premium: null,
            twitter_accounts: [],
            created_at: '',
            updated_at: '',
        }

        // 表示されているアカウント情報を更新 (ログイン時のみ)
        if (this.is_logged_in === true) {
            await this.syncAccountInfo();

            // 連携している Twitter アカウントがあれば true に設定
            if (this.user.twitter_accounts.length > 0) {
                this.is_logged_in_twitter = true;

                // 現在ツイート対象として選択されている Twitter アカウントの ID が設定されていない or ID に紐づく Twitter アカウントがない
                // 連携している Twitter アカウントのうち、一番最初のものを自動選択する
                // ここで言う Twitter アカウントの ID は DB 上で連番で振られるもので、Twitter アカウントそのものの固有 ID ではない
                if (this.selected_twitter_account_id === null ||
                    !this.user.twitter_accounts.some((twitter_account) => twitter_account.id === this.selected_twitter_account_id)) {
                    this.selected_twitter_account_id = this.user.twitter_accounts[0].id;
                    Utils.setSettingsItem('selected_twitter_account_id', this.selected_twitter_account_id);
                }

                // 現在ツイート対象として選択されている Twitter アカウントを取得・設定
                const twitter_account_index = this.user.twitter_accounts.findIndex((twitter_account) => {
                    return twitter_account.id === this.selected_twitter_account_id;  // Twitter アカウントの ID が選択されているものと一致する
                });
                this.selected_twitter_account = this.user.twitter_accounts[twitter_account_index];
            }
        }
    },
    methods: {

        // ユーザーアカウントの情報を取得する
        async syncAccountInfo() {
            try {
                this.user = (await Vue.axios.get('/users/me')).data;
            } catch (error) {
                // ログインされていないので未ログイン状態に設定
                if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
                    this.is_logged_in = false;
                    this.user = null;
                }
            }
        },

        // 文字数カウントを変更するイベントハンドラー
        changeTweetLetterCount() {

            // サロゲートペアを考慮し、スプレッド演算子で一度配列化してから数えている
            // ref: https://qiita.com/suin/items/3da4fb016728c024eaca
            this.tweet_letter_count = 140 - [...this.tweet_hashtag].length - [...this.tweet_text].length;
        },

        // アカウントボタンが押されたときのイベントハンドラー
        clickAccountButton() {
            // Twitter アカウントが連携されていない場合は Twitter 設定画面に飛ばす
            if (!this.is_logged_in_twitter) {
                // 視聴ページ以外に遷移するため、フルスクリーンを解除しないと画面が崩れる
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                }
                this.$router.push({path: '/settings/twitter'});
                return;
            }
            this.is_twitter_account_list_display = !this.is_twitter_account_list_display;
        },

        // 選択されている Twitter アカウントを更新する
        updateSelectedTwitterAccount(twitter_account: ITwitterAccount) {
            this.selected_twitter_account_id = twitter_account.id;
            Utils.setSettingsItem('selected_twitter_account_id', this.selected_twitter_account_id);
            this.selected_twitter_account = twitter_account;

            // Twitter アカウントリストのオーバーレイを閉じる (少し待ってから閉じたほうが体感が良い)
            window.setTimeout(() => this.is_twitter_account_list_display = false, 150);
        },

        // ツイートを送信する
        async sendTweet() {

            // ハッシュタグを整形（余計なスペースなどを削り、全角ハッシュを半角ハッシュへ、全角スペースを半角スペースに置換）
            const tweet_hashtag_array = this.tweet_hashtag.trim()
                .replaceAll('♯', '#').replaceAll('＃', '#').replaceAll('　', '').replaceAll(/ +/g,' ').split(' ');
            for (let index in tweet_hashtag_array) {
                // ハッシュタグがついてない場合にハッシュタグを付与
                if (!tweet_hashtag_array[index].startsWith('#')) tweet_hashtag_array[index] = `#${tweet_hashtag_array[index]}`;
            }
            const tweet_hashtag = tweet_hashtag_array.join(' ');

            // 実際に送るツイート本文を作成
            let tweet_text;
            switch (Utils.getSettingsItem('tweet_hashtag_position')) {
                // ツイート本文の前に追加する
                case 'Prepend': {
                    tweet_text = `${tweet_hashtag} ${this.tweet_text}`;
                    break;
                }
                // ツイート本文の後に追加する
                case 'Append': {
                    tweet_text = `${this.tweet_text} ${tweet_hashtag}`;
                    break;
                }
                // ツイート本文の前に追加してから改行する
                case 'PrependWithLineBreak': {
                    tweet_text = `${tweet_hashtag}\n${this.tweet_text}`;
                    break;
                }
                // ツイート本文の後に改行してから追加する
                case 'AppendWithLineBreak': {
                    tweet_text = `${this.tweet_text}\n${tweet_hashtag}`;
                    break;
                }
            }

            // multipart/form-data でツイート本文と画像（選択されている場合）を送る
            const form_data = new FormData();
            form_data.append('tweet', tweet_text);

            // 連投防止のため、フォーム上のツイート本文を消去
            this.tweet_text = '';

            try {

                // ツイート送信 API にリクエスト
                const result = await Vue.axios.post(`/twitter/accounts/${this.selected_twitter_account.screen_name}/tweets`, form_data, {
                    headers: {'Content-Type': 'multipart/form-data'},
                });

                // 成功 or 失敗に関わらず detail の内容をそのまま通知する
                this.player.notice(result.data.detail);

            } catch (error) {
                console.error(error);
                this.player.notice('ツイートの送信に失敗しました。');
            }
        },
    }
});

</script>
<style lang="scss" scoped>

.twitter-container {
    display: flex;
    flex-direction: column;
    position: relative;
    padding-left: 12px;
    padding-right: 12px;
    padding-bottom: 8px;

    .tab-container {
        flex-grow: 1;
    }

    .tab-button-container {
        display: flex;
        column-gap: 7px;
        height: 40px;
        padding-top: 8px;
        padding-bottom: 6px;

        .tab-button {
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1;
            background: var(--v-background-lighten2);
            border-radius: 7px;
            font-size: 11px;
            transition: background-color 0.15s ease;
            user-select: none;
            cursor: pointer;
            &--active {
                background: var(--v-twitter-base);
            }

            &__text {
                margin-left: 4px;
                margin-right: 2px;
                line-height: 2;
            }
        }
    }

    .tweet-form {
        display: flex;
        flex-direction: column;
        height: 130px;
        border-radius: 12px;
        background: var(--v-background-lighten1);

        &__hashtag {
            display: flex;
            align-items: center;
            height: 19px;
            margin-top: 12px;
            margin-left: 12px;
            margin-right: 12px;

            &-form {
                display: block;
                height: 100%;
                flex-grow: 1;
                font-size: 12.5px;
                color: var(--v-twitter-lighten2);
                outline: none;
                &::placeholder {
                    color: rgba(65, 165, 241, 60%);
                }
            }
            &-memory-button {
                display: flex;
                position: relative;
                align-items: center;
                justify-content: center;
                right: -8px;
                width: 34px;
                height: 34px;
                padding: 6px;
                border-radius: 50%;
                color: var(--v-twitter-lighten2);
                cursor: pointer;
            }
        }

        &__textarea {
            display: block;
            flex-grow: 1;
            margin-top: 8px;
            margin-left: 12px;
            margin-right: 12px;
            font-size: 12.5px;
            color: var(--v-text-base);
            word-break: break-all;
            resize: none;
            outline: none;
            &::placeholder {
                color: var(--v-text-darken2);
            }
        }

        &__control {
            display: flex;
            align-items: center;
            height: 32px;
            margin-top: 6px;

            .account-button {
                display: flex;
                align-items: center;
                width: 183px;
                height: 100%;
                border-radius: 7px;
                font-size: 13px;
                color: var(--v-text-base);
                background: var(--v-background-lighten2);
                user-select: none;
                cursor: pointer;
                &--no-login {
                    .account-button__screen-name {
                        font-weight: 500;
                    }
                    .account-button__menu {
                        display: none;
                    }
                }

                &__icon {
                    display: block;
                    width: 32px;
                    height: 100%;
                    border-radius: 7px;
                    // 読み込まれるまでのアイコンの背景
                    background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                }
                &__screen-name {
                    flex-grow: 1;
                    line-height: 2;
                    text-align: center;
                    font-weight: bold;
                }
                &__menu {
                    margin-right: 4px;
                }
            }

            .limit-meter {
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                flex-grow: 1;
                row-gap: 0.5px;
                font-size: 10px;
                color: var(--v-text-darken1);
                user-select: none;

                &__content {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    svg {
                        width: 14px;
                    }
                    span {
                        width: 16px;
                        margin-left: 5px;
                        text-align: center;
                        font-weight: bold;
                    }
                    &--yellow {
                        color: var(--v-warning-base);
                    }
                    &--red {
                        color: var(--v-error-base);
                    }
                }
            }

            .tweet-button {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 94px;
                height: 100%;
                border-radius: 7px;
                font-size: 12.5px;
                line-height: 2;
                color: var(--v-text-base);
                background: var(--v-twitter-base);
                user-select: none;
                outline: none;
                cursor: pointer;

                &[disabled] {
                    opacity: 0.7;
                    cursor: auto;
                }
            }
        }
    }

    .twitter-account-list {
        position: absolute;
        left: 12px;
        right: 12px;
        bottom: 48px;
        border-radius: 7px;
        background: var(--v-background-lighten2);
        box-shadow: 0px 3px 4px rgba(0, 0, 0, 53%);
        transition: opacity 0.2s ease, visibility 0.2s ease;
        opacity: 0;
        visibility: hidden;
        &--display {
            opacity: 1;
            visibility: visible;
        }

        .twitter-account {
            display: flex;
            align-items: center;
            padding: 12px 12px;
            border-radius: 7px;
            user-select: none;
            cursor: pointer;

            &__icon {
                display: block;
                width: 50px;
                height: 50px;
                border-radius: 50%;
            }
            &__info {
                display: flex;
                flex-direction: column;
                flex-grow: 1;
                min-width: 0;
                margin-left: 12px;
            }
            &__name {
                font-size: 17px;
                font-weight: bold;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            &__screen-name {
                color: var(--v-text-darken1);
                font-size: 14px;
            }
            &__check {
                flex-shrink: 0;
                color: var(--v-twitter-lighten1);
            }
        }
    }
}

</style>