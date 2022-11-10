<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
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
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="fold_panel_after_sending_tweet">ツイート送信後にパネルを閉じる</label>
                <label class="settings__item-label" for="fold_panel_after_sending_tweet">
                    ツイートを送信した後に、表示中のパネルを閉じる（折りたたむ）かを設定します。<br>
                </label>
                <v-switch class="settings__item-switch" id="fold_panel_after_sending_tweet" inset hide-details
                    v-model="settings.fold_panel_after_sending_tweet">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="reset_hashtag_when_program_switches">番組が切り替わったときにハッシュタグフォームをリセットする</label>
                <label class="settings__item-label" for="reset_hashtag_when_program_switches">
                    チャンネルを切り替えたときや、視聴中の番組が終了し次の番組の放送が開始されたときに、ハッシュタグフォームをリセットするかを設定します。<br>
                    この設定をオンにすると、「誤って前番組のハッシュタグをつけたまま次番組の実況ツイートをしてしまう」といったミスを回避できます。<br>
                </label>
                <v-switch class="settings__item-switch" id="reset_hashtag_when_program_switches" inset hide-details
                    v-model="settings.reset_hashtag_when_program_switches">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="auto_add_watching_channel_hashtag">視聴中のチャンネルに対応する局タグを自動的に追加する</label>
                <label class="settings__item-label" for="auto_add_watching_channel_hashtag">
                    ハッシュタグフォームに、常に視聴中のチャンネルに対応する局タグ (#nhk, #tokyomx など) を自動的に追加するかを設定します。<br>
                    なお、局タグは現時点で三大首都圏の地上波と BS の一部チャンネルと AT-X にのみ対応しています。<br>
                </label>
                <v-switch class="settings__item-switch" id="auto_add_watching_channel_hashtag" inset hide-details
                    v-model="settings.auto_add_watching_channel_hashtag">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">既定で表示される Twitter タブ内のタブ</div>
                <div class="settings__item-label">
                    視聴画面を開いたときに、パネルの Twitter タブの中で最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="twitter_active_tab" v-model="settings.twitter_active_tab">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートにつけるハッシュタグの位置</div>
                <div class="settings__item-label">
                    ツイート本文から見て、ハッシュタグをどの位置につけてツイートするかを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tweet_hashtag_position" v-model="settings.tweet_hashtag_position">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートするキャプチャに番組タイトルの透かしを描画する</div>
                <div class="settings__item-label">
                    ツイートするキャプチャに、視聴中の番組タイトルの透かしを描画するかを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tweet_capture_watermark_position" v-model="settings.tweet_capture_watermark_position">
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
    name: 'Settings-Twitter',
    components: {
        Base,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // 既定で表示されるパネルのタブの選択肢
            twitter_active_tab: [
                {'text': 'ツイート検索タブ', 'value': 'Search'},
                {'text': 'タイムラインタブ', 'value': 'Timeline'},
                {'text': 'キャプチャタブ', 'value': 'Capture'},
            ],

            // ツイートにつけるハッシュタグの位置の選択肢
            tweet_hashtag_position: [
                {'text': 'ツイート本文の前に追加する', 'value': 'Prepend'},
                {'text': 'ツイート本文の後に追加する', 'value': 'Append'},
                {'text': 'ツイート本文の前に追加してから改行する', 'value': 'PrependWithLineBreak'},
                {'text': 'ツイート本文の後に改行してから追加する', 'value': 'AppendWithLineBreak'},
            ],

            // ツイートするキャプチャに番組タイトルの透かしを描画する位置の選択肢
            tweet_capture_watermark_position: [
                {'text': '透かしを描画しない', 'value': 'None'},
                {'text': '透かしをキャプチャの左上に描画する', 'value': 'TopLeft'},
                {'text': '透かしをキャプチャの右上に描画する', 'value': 'TopRight'},
                {'text': '透かしをキャプチャの左下に描画する', 'value': 'BottomLeft'},
                {'text': '透かしをキャプチャの右下に描画する', 'value': 'BottomRight'},
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
                // 現在の設定値を取得する
                const settings = {};
                const setting_keys = [
                    'fold_panel_after_sending_tweet',
                    'reset_hashtag_when_program_switches',
                    'auto_add_watching_channel_hashtag',
                    'twitter_active_tab',
                    'tweet_hashtag_position',
                    'tweet_capture_watermark_position',
                ];
                for (const setting_key of setting_keys) {
                    settings[setting_key] = Utils.getSettingsItem(setting_key);
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
    @include smartphone-horizontal {
        padding: 16px 20px;
    }

    &__heading {
        display: flex;
        align-items: center;
        font-size: 18px;
        font-weight: bold;
    }

    &__guide {
        display: flex;
        align-items: center;

        .text-h6 {
            @include tablet-vertical {
                font-size: 19px !important;
            }
        }

        svg {
            @include smartphone-horizontal-short {
                display: none;
            }
        }
        svg + div {
            @include smartphone-horizontal-short {
                margin-left: 0px !important;
            }
        }
    }

    .twitter-account {
        display: flex;
        align-items: center;
        margin-top: 20px;
        @include smartphone-horizontal {
            margin-top: 16px;
        }

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
            @include smartphone-horizontal {
                width: 52px;
                height: 52px;
            }
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
                    @include smartphone-horizontal {
                        font-size: 18px;
                    }
                }
            }

            &-screen-name {
                display: inline-block;
                color: var(--v-text-darken1);
                font-size: 16px;
                @include smartphone-horizontal {
                    font-size: 14px;
                }
            }
        }

        &__login {
            margin-top: 20px;
            margin-left: auto;
            margin-right: auto;
            border-radius: 7px;
            font-size: 15px;
            letter-spacing: 0;
            @include tablet-vertical {
                height: 42px !important;
                font-size: 14.5px;
            }
            @include smartphone-horizontal {
                height: 42px !important;
                font-size: 14.5px;
            }
        }

        &__logout {
            background: var(--v-gray-base);
            border-radius: 7px;
            font-size: 15px;
            letter-spacing: 0;
            @include smartphone-horizontal {
                width: 116px !important;
            }
        }
    }
}

</style>