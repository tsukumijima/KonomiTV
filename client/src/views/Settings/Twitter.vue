<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="fa-brands:twitter" width="22px" />
            <span class="ml-3">Twitter</span>
        </h2>
        <div class="settings__content" :class="{'settings__content--loading': is_loading}">
            <div class="twitter-accounts">
                <div class="twitter-accounts__heading" v-if="user.twitter_accounts.length > 0">
                    <Icon icon="fluent:person-board-20-filled" class="mr-2" height="30" />連携中のアカウント
                </div>
                <div class="twitter-accounts__guide" v-if="user.twitter_accounts.length === 0">
                    <Icon class="flex-shrink-0" icon="fa-brands:twitter" width="45px" />
                    <div class="ml-4">
                        <div class="font-weight-bold text-h6">Twitter アカウントと連携していません</div>
                        <div class="text--text text--darken-1 text-subtitle-2 mt-1">
                            Twitter アカウントと連携すると、テレビを見ながら Twitter にツイートしたり、ほかの実況ツイートをリアルタイムで表示できるようになります。
                        </div>
                    </div>
                </div>
                <div class="twitter-account" v-for="twitter_account in user.twitter_accounts" :key="twitter_account.id">
                    <img class="twitter-account__icon" :src="twitter_account.icon_url">
                    <div class="twitter-account__info">
                        <div class="twitter-account__info-name">
                            <span class="twitter-account__info-name-text">{{twitter_account.name}}</span>
                        </div>
                        <span class="twitter-account__info-screen-name">@{{twitter_account.screen_name}}</span>
                    </div>
                    <v-btn class="twitter-account__logout ml-auto" width="124" height="52" depressed
                        @click="logoutTwitterAccount(twitter_account.screen_name)">
                        <Icon icon="fluent:plug-disconnected-20-filled" class="mr-2" height="24" />連携解除
                    </v-btn>
                </div>
                <v-btn class="twitter-account__login" color="secondary" max-width="250" height="50" depressed
                    @click="loginTwitterAccount()">
                    <Icon icon="fluent:plug-connected-20-filled" class="mr-2" height="24" />連携するアカウントを追加
                </v-btn>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートにつけるハッシュタグの位置</div>
                <div class="settings__item-label">
                    ツイート本文から見て、ハッシュタグをどの位置につけてツイートするかを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="tweet_hashtag_position" v-model="settings.tweet_hashtag_position">
                </v-select>
            </div>
        </div>
    </Base>
</template>
<script lang="ts">

import axios from 'axios';
import Vue from 'vue';

import { IUser } from '@/interface';
import Base from '@/views/Settings/Base.vue';
import Utils from '@/utils';

export default Vue.extend({
    name: 'SettingsTwitter',
    components: {
        Base,
    },
    data() {
        return {

            // ツイートにつけるハッシュタグの位置の選択肢
            tweet_hashtag_position: [
                {'text': 'ツイート本文の前に追加する', 'value': 'Prepend'},
                {'text': 'ツイート本文の後に追加する', 'value': 'Append'},
                {'text': 'ツイート本文の前に追加してから改行する', 'value': 'PrependWithLineBreak'},
                {'text': 'ツイート本文の後に改行してから追加する', 'value': 'AppendWithLineBreak'},
            ],

            // ローディング中かどうか
            is_loading: true,

            // ログイン中かどうか
            is_logged_in: Utils.getAccessToken() !== null,

            // ユーザーアカウントの情報
            // ログインしていない場合は null になる
            user: null as IUser | null,

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: (() => {
                // 設定の既定値を取得する
                const settings = {}
                for (const setting of ['tweet_hashtag_position']) {
                    settings[setting] = Utils.getSettingsItem(setting);
                }
                return settings;
            })(),
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
        }

        // ローディング状態を解除
        this.is_loading = false;
    },
    methods: {
        async syncAccountInfo() {

            try {

                // ユーザーアカウントの情報を取得する
                this.user = (await Vue.axios.get('/users/me')).data;

            } catch (error) {

                // ログインされていない
                if (axios.isAxiosError(error) && error.response && error.response.status === 401) {

                    // 未ログイン状態に設定
                    this.is_logged_in = false;
                    this.user = null;
                }
            }
        },

        async loginTwitterAccount() {

            // ログインしていない場合はエラーにする
            if (this.is_logged_in === false) {
                this.$message.warning('連携をはじめるには、KonomiTV アカウントにログインしてください。');
                return;
            }

            // Twitter アカウントと連携するための認証 URL を取得
            const authorization_url = (await Vue.axios.get('/twitter/auth')).data.authorization_url;

            // OAuth 連携のため、認証 URL をポップアップウインドウで開く
            // window.open() の第2引数はユニークなものにしておくと良いらしい
            // ref: https://qiita.com/catatsuy/items/babce8726ea78f5d25b1 (大変参考になりました)
            const popup_window = window.open(authorization_url, 'KonomiTV-OAuthPopup', Utils.getWindowFeatures());

            // 認証完了 or 失敗後、ポップアップウインドウから送信される文字列を受信
            const onMessage = async (event) => {

                // すでにウインドウが閉じている場合は実行しない
                if (popup_window.closed) return;

                // 受け取ったオブジェクトに KonomiTV-OAuthPopup キーがない or そもそもオブジェクトではない際は実行しない
                // ブラウザの拡張機能から結構余計な message が飛んでくるっぽい…。
                if (Utils.typeof(event.data) !== 'object') return;
                if (('KonomiTV-OAuthPopup' in event.data) === false) return;

                // 認証は完了したので、ポップアップウインドウを閉じ、リスナーを解除する
                if (popup_window) popup_window.close();
                window.removeEventListener('message', onMessage);

                // ステータスコードと詳細メッセージを取得
                const authorization_status = event.data['KonomiTV-OAuthPopup']['status'] as number;
                const authorization_detail = event.data['KonomiTV-OAuthPopup']['detail'] as string;
                console.log(`TwitterAuthCallbackAPI: Status: ${authorization_status} / Detail: ${authorization_detail}`);

                // OAuth 連携に失敗した
                if (authorization_status !== 200) {
                    if (authorization_detail.startsWith('Authorization was denied by user')) {
                        this.$message.error('Twitter アカウントとの連携がキャンセルされました。');
                    } else if (authorization_detail.startsWith('Failed to get access token')) {
                        this.$message.error('アクセストークンの取得に失敗しました。');
                    } else if (authorization_detail.startsWith('Failed to get user information')) {
                        this.$message.error('Twitter アカウントのユーザー情報の取得に失敗しました。');
                    } else {
                        this.$message.error(`Twitter アカウントとの連携に失敗しました。(${authorization_detail})`);
                    }
                    return;
                }

                // 表示されているアカウント情報を更新
                await this.syncAccountInfo();

                // ログイン中のユーザーに紐づく Twitter アカウントのうち、一番 updated_at が新しいものを取得
                // ログインすると updated_at が更新されるため、この時点で一番 updated_at が新しいアカウントが今回連携したものだと判断できる
                // ref: https://stackoverflow.com/a/12192544/17124142 (ISO8601 のソートアルゴリズム)
                const current_twitter_account = [...this.user.twitter_accounts].sort((a, b) => {
                    return (a.updated_at < b.updated_at) ? 1 : ((a.updated_at > b.updated_at) ? -1 : 0);
                })[0];

                this.$message.success(`Twitter @${current_twitter_account.screen_name} と連携しました。`);
            };

            // postMessage() を受信するリスナーを登録
            window.addEventListener('message', onMessage);
        },

        async logoutTwitterAccount(screen_name: string) {

            // Twitter アカウント連携解除 API にリクエスト
            await Vue.axios.delete(`/twitter/accounts/${screen_name}`);

            // 表示されているアカウント情報を更新
            await this.syncAccountInfo();

            this.$message.success(`Twitter @${screen_name} との連携を解除しました。`);
        },
    },
    watch: {
        // settings 内の値の変更を監視する
        settings: {
            deep: true,
            handler() {
                // settings 内の値を順に LocalStorage に保存する
                for (const [setting_key, setting_value] of Object.entries(this.settings)) {
                    Utils.setSettingsItem(setting_key, setting_value);
                }
            }
        }
    }
});

</script>
<style lang="scss" scoped>

.settings__content {
    opacity: 1;
    transition: opacity 0.4s;

    &--loading {
        opacity: 0;
    }
}

.twitter-accounts {
    display: flex;
    flex-direction: column;
    padding: 20px 20px;
    border-radius: 15px;
    background: var(--v-background-lighten2);

    &__heading {
        display: flex;
        align-items: center;
        font-size: 18px;
        font-weight: bold;
    }

    &__guide {
        display: flex;
        align-items: center;
    }

    .twitter-account {
        display: flex;
        align-items: center;
        margin-top: 20px;

        &__icon {
            flex-shrink: 0;
            width: 70px;
            height: 70px;
            margin-right: 16px;
            border-radius: 50%;
            object-fit: cover;
            // 読み込まれるまでのアイコンの背景
            background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
            // 低解像度で表示する画像がぼやけないようにする
            // ref: https://sho-log.com/chrome-image-blurred/
            image-rendering: -webkit-optimize-contrast;
        }

        &__info {
            display: flex;
            flex-direction: column;
            min-width: 0;
            margin-right: 16px;

            &-name {
                display: inline-flex;
                align-items: center;

                &-text {
                    display: inline-block;
                    color: var(--v-text-base);
                    font-size: 20px;
                    font-weight: bold;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;  // はみ出た部分を … で省略
                }
            }

            &-screen-name {
                display: inline-block;
                color: var(--v-text-darken1);
                font-size: 16px;
            }
        }

        &__login {
            margin-top: 20px;
            margin-left: auto;
            margin-right: auto;
            border-radius: 7px;
            font-size: 15px;
            letter-spacing: 0;
        }

        &__logout {
            background: var(--v-gray-base);
            border-radius: 7px;
            font-size: 15px;
            letter-spacing: 0;
        }
    }
}

</style>