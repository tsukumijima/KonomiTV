<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <Icon icon="fa-brands:twitter" width="22px" />
            <span class="ml-3">Twitter</span>
        </h2>
        <div class="settings__content" :class="{'settings__content--loading': is_loading}">
            <div class="twitter-accounts">
                <div class="twitter-accounts__heading" v-if="userStore.user !== null && userStore.user.twitter_accounts.length > 0">
                    <Icon icon="fluent:person-board-20-filled" class="mr-2" height="30" />連携中のアカウント
                </div>
                <div class="twitter-accounts__guide" v-if="userStore.user === null || userStore.user.twitter_accounts.length === 0">
                    <Icon class="flex-shrink-0" icon="fa-brands:twitter" width="45px" />
                    <div class="ml-4">
                        <div class="font-weight-bold text-h6">Twitter アカウントと連携していません</div>
                        <div class="text--text text--darken-1 text-subtitle-2 mt-1">
                            Twitter アカウントと連携すると、テレビを見ながら Twitter にツイートしたり、ほかの実況ツイートをリアルタイムで表示できるようになります。
                        </div>
                    </div>
                </div>
                <div class="twitter-account"
                    v-for="twitter_account in (userStore.user !== null ? userStore.user.twitter_accounts: [])"
                    :key="twitter_account.id">
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
                <v-dialog max-width="600" v-model="twitter_password_auth_dialog">
                    <template v-slot:activator="{ on }">
                    <v-btn class="twitter-account__login" color="secondary" max-width="250" height="50" depressed v-on="on"
                        @click="loginTwitterAccountWithPasswordForm()">
                        <Icon icon="fluent:plug-connected-20-filled" class="mr-2" height="24" />連携するアカウントを追加
                    </v-btn>
                    </template>
                    <v-card>
                        <v-card-title class="justify-center pt-6 font-weight-bold">Twitter にログイン</v-card-title>
                        <!-- スクリーンネームとパスワードフォーム -->
                        <v-card-text class="pt-2 pb-0">
                            <p class="mb-1">2023/4/30 以降、Twitter のサードパーティー API の事実上の廃止により、従来のアプリ連携では Twitter にアクセスできなくなりました。</p>
                            <p class="mb-1">そこで KonomiTV では、代わりにユーザー名とパスワードでログインすることで、これまで通り Twitter 連携ができるようにしています。</p>
                            <p class="mb-1">安全対策は講じていますが、非公式な手段のため、最悪の場合、アカウントにペナルティが適用される可能性もあります。自己の責任のもとでご利用ください。</p>
                            <v-form class="settings__item" ref="twitter_form" @submit.prevent>
                                <v-text-field class="settings__item-form mt-6" outlined label="ユーザー名 (@ から始まる ID)" placeholder="screen_name"
                                    ref="twitter_screen_name"
                                    :dense="is_form_dense"
                                    v-model="twitter_screen_name"
                                    :rules="[(value) => !!value || 'ユーザー名を入力してください。']">
                                </v-text-field>
                                <v-text-field class="settings__item-form" outlined label="パスワード"
                                    :dense="is_form_dense"
                                    v-model="twitter_password"
                                    :type="twitter_password_showing ? 'text' : 'password'"
                                    :append-icon="twitter_password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                                    :rules="[(value) => !!value || 'パスワードを入力してください。']"
                                    @click:append="twitter_password_showing = !twitter_password_showing">
                                </v-text-field>
                            </v-form>
                        </v-card-text>
                        <v-card-actions class="pt-0 px-6 pb-5">
                            <v-spacer></v-spacer>
                            <v-btn color="text" height="40" text @click="twitter_password_auth_dialog = false">キャンセル</v-btn>
                            <v-btn color="secondary" height="40" class="px-4" @click="loginTwitterAccountWithPassword()">ログイン</v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>
                <v-btn class="twitter-account__login" color="secondary" max-width="310" height="50" depressed
                    @click="loginTwitterAccountWithOAuth()">
                    <Icon icon="fluent:plug-connected-20-filled" class="mr-2" height="24" />連携するアカウントを追加 (Legacy)
                </v-btn>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="fold_panel_after_sending_tweet">ツイート送信後にパネルを折りたたむ</label>
                <label class="settings__item-label" for="fold_panel_after_sending_tweet">
                    この設定をオンにすると、ツイートを送信した後に、パネルが自動で折りたたまれます。<br>
                    ツイートするとき以外はできるだけ映像を大きくして見たい方におすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" id="fold_panel_after_sending_tweet" inset hide-details
                    v-model="settingsStore.settings.fold_panel_after_sending_tweet">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="reset_hashtag_when_program_switches">番組が切り替わったときにハッシュタグフォームをリセットする</label>
                <label class="settings__item-label" for="reset_hashtag_when_program_switches">
                    チャンネルを切り替えたときや、視聴中の番組が終了し次の番組の放送が開始されたときに、ハッシュタグフォームをリセットするかを設定します。<br>
                    この設定をオンにしておけば、「誤って前番組のハッシュタグをつけたまま次番組の実況ツイートをしてしまう」といったミスを回避できます。<br>
                </label>
                <v-switch class="settings__item-switch" id="reset_hashtag_when_program_switches" inset hide-details
                    v-model="settingsStore.settings.reset_hashtag_when_program_switches">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="auto_add_watching_channel_hashtag">視聴中のチャンネルに対応する局タグを自動で追加する</label>
                <label class="settings__item-label" for="auto_add_watching_channel_hashtag">
                    この設定をオンにすると、視聴中のチャンネルに対応する局タグ (#nhk, #tokyomx など) がハッシュタグフォームに自動で追加されます。<br>
                    現時点で、局タグは三大首都圏の地上波・BS の一部チャンネル・AT-X にのみ対応しています。<br>
                </label>
                <v-switch class="settings__item-switch" id="auto_add_watching_channel_hashtag" inset hide-details
                    v-model="settingsStore.settings.auto_add_watching_channel_hashtag">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">デフォルトで表示される Twitter タブ内のタブ</div>
                <div class="settings__item-label">
                    視聴画面を開いたときに、パネルの Twitter タブの中で最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="twitter_active_tab" v-model="settingsStore.settings.twitter_active_tab">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートにつけるハッシュタグの位置</div>
                <div class="settings__item-label">
                    ツイート本文から見て、ハッシュタグをどの位置につけてツイートするかを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tweet_hashtag_position" v-model="settingsStore.settings.tweet_hashtag_position">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートするキャプチャに番組タイトルの透かしを描画する</div>
                <div class="settings__item-label">
                    ツイートするキャプチャに、透かしとして視聴中の番組タイトルを描画するかを設定します。<br>
                    透かしの描画位置は 左上・右上・左下・右下 から選択できます。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tweet_capture_watermark_position" v-model="settingsStore.settings.tweet_capture_watermark_position">
                </v-select>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import Twitter from '@/services/Twitter';
import useSettingsStore from '@/store/SettingsStore';
import useUserStore from '@/store/UserStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default Vue.extend({
    name: 'Settings-Twitter',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // デフォルトで表示されるパネルのタブの選択肢
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

            // パスワード認証用ダイヤログ
            twitter_password_auth_dialog: false,

            // Twitter のスクリーンネームとパスワード
            twitter_screen_name: '',
            twitter_password: '',
            twitter_password_showing: false,
        };
    },
    computed: {
        // SettingsStore / UserStore に this.settingsStore / this.userStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useSettingsStore, useUserStore),
    },
    async created() {

        // アカウント情報を更新
        await this.userStore.fetchUser();

        // ローディング状態を解除
        this.is_loading = false;

        // もしハッシュ (# から始まるフラグメント) に何か指定されていたら、
        // OAuth 連携のコールバックの結果が入っている可能性が高いので、パースを試みる
        // アカウント情報更新より後にしないと Snackbar がうまく表示されない
        if (location.hash !== '') {
            const params = new URLSearchParams(location.hash.replace('#', ''));
            if (params.get('status') !== null && params.get('detail') !== null) {
                // コールバックの結果を取得できたので、OAuth 連携の結果を画面に通知する
                const authorization_status = parseInt(params.get('status')!);
                const authorization_detail = params.get('detail')!;
                this.onOAuthCallbackReceived(authorization_status, authorization_detail);
                // URL からフラグメントを削除
                // ref: https://stackoverflow.com/a/49373716/17124142
                history.replaceState(null, '', ' ');
            }
        }
    },
    methods: {
        async loginTwitterAccountWithPasswordForm() {
            // ログインしていない場合はエラーにする
            if (this.userStore.is_logged_in === false) {
                this.$message.warning('連携をはじめるには、KonomiTV アカウントにログインしてください。');
                await Utils.sleep(0.01);
                this.twitter_password_auth_dialog = false;
                return;
            }
        },

        async loginTwitterAccountWithPassword() {

            // バリデーションを実行
            if ((this.$refs.twitter_form as any).validate() === false) {
                return;
            }

            // Twitter パスワード認証 API にリクエスト
            const result = await Twitter.authWithPassword({
                screen_name: this.twitter_screen_name,
                password: this.twitter_password,
            });
            if (result === false) {
                return;
            }

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);
            if (this.userStore.user === null) {
                this.$message.error('アカウント情報を取得できませんでした。');
                return;
            }

            // ログイン中のユーザーに紐づく Twitter アカウントのうち、一番 updated_at が新しいものを取得
            // ログインすると updated_at が更新されるため、この時点で一番 updated_at が新しいアカウントが今回連携したものだと判断できる
            // ref: https://stackoverflow.com/a/12192544/17124142 (ISO8601 のソートアルゴリズム)
            const current_twitter_account = [...this.userStore.user.twitter_accounts].sort((a, b) => {
                return (a.updated_at < b.updated_at) ? 1 : ((a.updated_at > b.updated_at) ? -1 : 0);
            })[0];

            this.$message.success(`Twitter @${current_twitter_account.screen_name} と連携しました。`);

            // フォームをリセットし、非表示にする
            (this.$refs.twitter_form as any).reset();
            this.twitter_password_auth_dialog = false;
        },

        async loginTwitterAccountWithOAuth() {

            // ログインしていない場合はエラーにする
            if (this.userStore.is_logged_in === false) {
                this.$message.warning('連携をはじめるには、KonomiTV アカウントにログインしてください。');
                return;
            }

            // Twitter アカウントと連携するための認証 URL を取得
            const authorization_url = await Twitter.fetchAuthorizationURL();
            if (authorization_url === null) {
                return;
            }

            // モバイルデバイスではポップアップが事実上使えない (特に Safari ではブロックされてしまう) ので、素直にリダイレクトで実装する
            if (Utils.isMobileDevice() === true) {
                location.href = authorization_url;
                return;
            }

            // OAuth 連携のため、認証 URL をポップアップウインドウで開く
            // window.open() の第2引数はユニークなものにしておくと良いらしい
            // ref: https://qiita.com/catatsuy/items/babce8726ea78f5d25b1 (大変参考になりました)
            const popup_window = window.open(authorization_url, 'KonomiTV-OAuthPopup', Utils.getWindowFeatures());
            if (popup_window === null) {
                this.$message.error('ポップアップウインドウを開けませんでした。');
                return;
            }

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
                this.onOAuthCallbackReceived(authorization_status, authorization_detail);
            };

            // postMessage() を受信するリスナーを登録
            window.addEventListener('message', onMessage);
        },

        async onOAuthCallbackReceived(authorization_status: number, authorization_detail: string) {
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

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);
            if (this.userStore.user === null) {
                this.$message.error('アカウント情報を取得できませんでした。');
                return;
            }

            // ログイン中のユーザーに紐づく Twitter アカウントのうち、一番 updated_at が新しいものを取得
            // ログインすると updated_at が更新されるため、この時点で一番 updated_at が新しいアカウントが今回連携したものだと判断できる
            // ref: https://stackoverflow.com/a/12192544/17124142 (ISO8601 のソートアルゴリズム)
            const current_twitter_account = [...this.userStore.user.twitter_accounts].sort((a, b) => {
                return (a.updated_at < b.updated_at) ? 1 : ((a.updated_at > b.updated_at) ? -1 : 0);
            })[0];

            this.$message.success(`Twitter @${current_twitter_account.screen_name} と連携しました。`);
        },

        async logoutTwitterAccount(screen_name: string) {

            // Twitter アカウント連携解除 API にリクエスト
            const result = await Twitter.logoutAccount(screen_name);
            if (result === false) {
                return;
            }

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);

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
        border-radius: 10px;
    }
    @include smartphone-vertical {
        padding: 16px 12px;
        border-radius: 10px;
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
            @include smartphone-vertical {
                font-size: 17px !important;
            }
        }

        svg {
            @include smartphone-horizontal-short {
                display: none;
            }
            @include smartphone-vertical {
                display: none;
            }
        }
        svg + div {
            @include smartphone-horizontal-short {
                margin-left: 0px !important;
            }
            @include smartphone-vertical {
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
            @include smartphone-vertical {
                width: 48px;
                height: 48px;
                margin-right: 10px;
            }
        }

        &__info {
            display: flex;
            flex-direction: column;
            min-width: 0;
            margin-right: 16px;
            @include smartphone-vertical {
                margin-right: 10px;
            }

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
                    @include smartphone-vertical {
                        font-size: 16px;
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
                @include smartphone-vertical {
                    font-size: 13.5px;
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
            @include smartphone-vertical {
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
            @include smartphone-vertical {
                width: 100px !important;
                height: 48px !important;
                border-radius: 5px;
                font-size: 14px;
                svg {
                    width: 20px;
                    margin-right: 4px !important;
                }
            }
        }
    }
}

</style>