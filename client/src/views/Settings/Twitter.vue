<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
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
                        <div class="text-text-darken-1 text-subtitle-2 mt-1">
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
                        <span class="twitter-account__info-screen-name">
                            @{{twitter_account.screen_name}}
                        </span>
                    </div>
                    <v-btn class="twitter-account__logout ml-auto" width="124" height="52" variant="flat"
                        @click="logoutTwitterAccount(twitter_account.screen_name)">
                        <Icon icon="fluent:plug-disconnected-20-filled" class="mr-2" height="24" />連携解除
                    </v-btn>
                </div>
                <v-btn class="twitter-account__login" color="secondary" max-width="250" height="50" variant="flat"
                    @click="loginTwitterAccountWithPasswordForm()">
                    <Icon icon="fluent:plug-connected-20-filled" class="mr-2" height="24" />連携するアカウントを追加
                </v-btn>
                <v-dialog max-width="700" v-model="twitter_password_auth_dialog">
                    <v-card>
                        <v-card-title class="d-flex justify-center pt-6 font-weight-bold">Twitter にログイン</v-card-title>
                        <!-- スクリーンネームとパスワードフォーム -->
                        <v-card-text class="pt-2 pb-0">
                            <p>2023/07 以降、Twitter のサードパーティー API の事実上の廃止により、従来のアプリ連携では Twitter にアクセスできなくなりました。</p>
                            <p class="mt-1">そこで KonomiTV では、代わりに <a class="link" href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc" target="_blank">Chrome 拡張機能</a> を使い <a class="link" href="https://x.com/TVRemotePlus/status/1821283471727493413" target="_blank">ブラウザからエクスポートした Cookie でログイン</a> または <a class="link" href="https://github.com/tsukumijima/tweepy-authlib" target="_blank">パスワードログイン</a> での Twitter 連携に対応しています。</p>
                            <p class="mt-2">ここで入力されたパスワードは一切保存されず、入力/取得した Cookie はローカルの KonomiTV サーバーにのみ保存されます。Cookie が Twitter API 以外の外部サービスに送信されることはありません。</p>
                            <p class="mt-1">万全は期していますが、非公式な方法のため、使い方次第ではアカウントにペナルティが適用される可能性もあります。自己の責任のもとでご利用ください。</p>
                            <blockquote class="mt-3">
                                <p>基本的には Cookie でのログインを推奨します。その方がスパム判定されづらいためです。</p>
                                <p class="mt-1">また、2要素認証 (2FA) が設定されているアカウントではパスワードログインを利用できません。</p>
                            </blockquote>
                            <v-tabs class="settings__tab mt-1" color="primary" bg-color="transparent" align-tabs="center" v-model="twitter_auth_tab">
                                <v-tab style="text-transform: none !important;" v-for="auth_type in ['Cookie でログイン', 'パスワードでログイン']" :key="auth_type">
                                    {{auth_type}}
                                </v-tab>
                            </v-tabs>
                            <v-window v-model="twitter_auth_tab">
                                <v-window-item class="settings__content mt-0">
                                    <v-form class="settings__item" ref="twitter_form" @submit.prevent>
                                        <v-textarea class="settings__item-form mt-4" color="primary" variant="outlined"
                                            label='Cookie (Netscape cookies.txt 形式)'
                                            placeholder='まず PC ブラウザ版 Twitter で連携したいアカウントに切り替えます。その後 PC ブラウザ版 Twitter の表示中に「Get cookies.txt LOCALLY」拡張機能を起動し、[Copy] ボタンを押してクリップボードにコピーした Cookie をここに貼り付けてください。'
                                            v-model="twitter_cookie"
                                            :density="is_form_dense ? 'compact' : 'default'"
                                            :rules="[(value) => {
                                                if (!value && twitter_auth_tab === 0) return 'Cookie を入力してください。';
                                                return true;
                                            }]">
                                        </v-textarea>
                                    </v-form>
                                </v-window-item>
                                <v-window-item class="settings__content mt-0">
                                    <v-form class="settings__item" ref="twitter_form" @submit.prevent>
                                        <v-text-field class="settings__item-form mt-4" color="primary" variant="outlined"
                                            label="ユーザー名 (@ から始まる ID)" placeholder="screen_name"
                                            ref="twitter_screen_name"
                                            v-model="twitter_screen_name"
                                            :density="is_form_dense ? 'compact' : 'default'"
                                            :rules="[(value) => {
                                                if (!value && twitter_auth_tab === 1) return 'ユーザー名を入力してください。';
                                                return true;
                                            }]">
                                        </v-text-field>
                                        <v-text-field class="settings__item-form mt-2" color="primary" variant="outlined"
                                            label="パスワード"
                                            v-model="twitter_password"
                                            :density="is_form_dense ? 'compact' : 'default'"
                                            :type="twitter_password_showing ? 'text' : 'password'"
                                            :rules="[(value) => {
                                                if (!value && twitter_auth_tab === 1) return 'パスワードを入力してください。';
                                                return true;
                                            }]"
                                            :append-inner-icon="twitter_password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                                            @click:appendInner="twitter_password_showing = !twitter_password_showing">
                                        </v-text-field>
                                    </v-form>
                                </v-window-item>
                            </v-window>
                        </v-card-text>
                        <v-card-actions class="pt-0 px-6 pb-6">
                            <v-spacer></v-spacer>
                            <v-btn color="text" variant="text" height="40" @click="twitter_password_auth_dialog = false">キャンセル</v-btn>
                            <v-btn color="secondary" variant="flat" height="40" class="px-4" @click="loginTwitterAccountWithPassword()">ログイン</v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="fold_panel_after_sending_tweet">ツイート送信後にパネルを折りたたむ</label>
                <label class="settings__item-label" for="fold_panel_after_sending_tweet">
                    この設定をオンにすると、ツイートを送信した後に、パネルが自動で折りたたまれます。<br>
                    ツイートするとき以外はできるだけ映像を大きくして見たい方におすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="fold_panel_after_sending_tweet" hide-details
                    v-model="settingsStore.settings.fold_panel_after_sending_tweet">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="reset_hashtag_when_program_switches">番組が切り替わったときにハッシュタグフォームをリセットする</label>
                <label class="settings__item-label" for="reset_hashtag_when_program_switches">
                    チャンネルを切り替えたときや、視聴中の番組が終了し次の番組の放送が開始されたときに、ハッシュタグフォームをリセットするかを設定します。<br>
                    この設定をオンにしておけば、「誤って前番組のハッシュタグをつけたまま次番組の実況ツイートをしてしまう」といったミスを回避できます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="reset_hashtag_when_program_switches" hide-details
                    v-model="settingsStore.settings.reset_hashtag_when_program_switches">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="auto_add_watching_channel_hashtag">視聴中のチャンネルに対応する局タグを自動で追加する</label>
                <label class="settings__item-label" for="auto_add_watching_channel_hashtag">
                    この設定をオンにすると、視聴中のチャンネルに対応する局タグ (#nhk, #tokyomx など) がハッシュタグフォームに自動で追加されます。<br>
                    なお、ビデオをみるときは視聴中のチャンネルに対応する局タグは追加されません。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="auto_add_watching_channel_hashtag" hide-details
                    v-model="settingsStore.settings.auto_add_watching_channel_hashtag">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">デフォルトで表示される Twitter タブ内のタブ</div>
                <div class="settings__item-label">
                    視聴画面を開いたときに、パネルの Twitter タブの中で最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="twitter_active_tab" v-model="settingsStore.settings.twitter_active_tab">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートにつけるハッシュタグの位置</div>
                <div class="settings__item-label">
                    ツイート本文から見て、ハッシュタグをどの位置につけてツイートするかを設定します。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="tweet_hashtag_position" v-model="settingsStore.settings.tweet_hashtag_position">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ツイートするキャプチャに番組タイトルの透かしを描画する</div>
                <div class="settings__item-label">
                    ツイートするキャプチャに、透かしとして視聴中の番組タイトルを描画するかを設定します。<br>
                    透かしの描画位置は 左上・右上・左下・右下 から選択できます。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="tweet_capture_watermark_position" v-model="settingsStore.settings.tweet_capture_watermark_position">
                </v-select>
            </div>
        </div>
        <v-overlay class="align-center justify-center" :persistent="true"
            :model-value="is_twitter_password_auth_sending" z-index="300">
            <v-progress-circular color="secondary" indeterminate size="64" />
        </v-overlay>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';
import { VForm } from 'vuetify/components';

import Message from '@/message';
import Twitter, { ITwitterPasswordAuthRequest, ITwitterCookieAuthRequest } from '@/services/Twitter';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default defineComponent({
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
                {title: 'ツイート検索タブ', value: 'Search'},
                {title: 'タイムラインタブ', value: 'Timeline'},
                {title: 'キャプチャタブ', value: 'Capture'},
            ],

            // ツイートにつけるハッシュタグの位置の選択肢
            tweet_hashtag_position: [
                {title: 'ツイート本文の前に追加する', value: 'Prepend'},
                {title: 'ツイート本文の後に追加する', value: 'Append'},
                {title: 'ツイート本文の前に追加してから改行する', value: 'PrependWithLineBreak'},
                {title: 'ツイート本文の後に改行してから追加する', value: 'AppendWithLineBreak'},
            ],

            // ツイートするキャプチャに番組タイトルの透かしを描画する位置の選択肢
            tweet_capture_watermark_position: [
                {title: '透かしを描画しない', value: 'None'},
                {title: '透かしをキャプチャの左上に描画する', value: 'TopLeft'},
                {title: '透かしをキャプチャの右上に描画する', value: 'TopRight'},
                {title: '透かしをキャプチャの左下に描画する', value: 'BottomLeft'},
                {title: '透かしをキャプチャの右下に描画する', value: 'BottomRight'},
            ],

            // ローディング中かどうか
            is_loading: true,

            // パスワード認証実行中かどうか
            is_twitter_password_auth_sending: false,

            // パスワード認証用ダイヤログ
            twitter_password_auth_dialog: false,

            // Twitter のスクリーンネームと (Cookie or パスワード)
            twitter_auth_tab: 0,
            twitter_screen_name: '',
            twitter_cookie: '',
            twitter_password: '',
            twitter_password_showing: false,
        };
    },
    computed: {
        ...mapStores(useSettingsStore, useUserStore),
    },
    async created() {

        // アカウント情報を更新
        await this.userStore.fetchUser();

        // ローディング状態を解除
        this.is_loading = false;
    },
    methods: {
        async loginTwitterAccountWithPasswordForm() {
            // ログインしていない場合はエラーにする
            if (this.userStore.is_logged_in === false) {
                Message.warning('連携をはじめるには、KonomiTV アカウントにログインしてください。');
                await Utils.sleep(0.01);
                this.twitter_password_auth_dialog = false;
                return;
            }
            this.twitter_password_auth_dialog = true;
        },

        async loginTwitterAccountWithPassword() {

            // バリデーションを実行
            if ((await (this.$refs.twitter_form as VForm).validate()).valid === false) {
                return;
            }

            let twitter_auth_request: ITwitterPasswordAuthRequest | ITwitterCookieAuthRequest;
            if (this.twitter_auth_tab === 1) {
                // パスワード認証
                twitter_auth_request = {
                    screen_name: this.twitter_screen_name,
                    password: this.twitter_password,
                };
            } else {
                // Cookie 認証
                // 空文字が入力されている場合は弾く
                if (this.twitter_cookie === null || this.twitter_cookie.trim() === '') {
                    Message.warning('Cookie を入力してください！');
                    return;
                }
                twitter_auth_request = {
                    cookies_txt: this.twitter_cookie,
                };
            }

            // Twitter 認証 API にリクエスト
            this.is_twitter_password_auth_sending = true;
            const result = await Twitter.auth(twitter_auth_request);
            this.is_twitter_password_auth_sending = false;
            if (result === false) {
                return;
            }

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);
            if (this.userStore.user === null) {
                Message.error('アカウント情報を取得できませんでした。');
                return;
            }

            // ログイン中のユーザーに紐づく Twitter アカウントのうち、一番 updated_at が新しいものを取得
            // ログインすると updated_at が更新されるため、この時点で一番 updated_at が新しいアカウントが今回連携したものだと判断できる
            // ref: https://stackoverflow.com/a/12192544/17124142 (ISO8601 のソートアルゴリズム)
            const current_twitter_account = [...this.userStore.user.twitter_accounts].sort((a, b) => {
                return (a.updated_at < b.updated_at) ? 1 : ((a.updated_at > b.updated_at) ? -1 : 0);
            })[0];

            Message.success(`Twitter @${current_twitter_account.screen_name} と連携しました。`);

            // フォームをリセットし、非表示にする
            (this.$refs.twitter_form as VForm).reset();
            this.twitter_password_auth_dialog = false;
        },

        async logoutTwitterAccount(screen_name: string) {

            // Twitter アカウント連携解除 API にリクエスト
            const result = await Twitter.logoutAccount(screen_name);
            if (result === false) {
                return;
            }

            // アカウント情報を強制的に更新
            await this.userStore.fetchUser(true);

            Message.success(`Twitter @${screen_name} との連携を解除しました。`);
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
    background: rgb(var(--v-theme-background-lighten-2));
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
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
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
                    color: rgb(var(--v-theme-text));
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
                color: rgb(var(--v-theme-text-darken-1));
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
            background: rgb(var(--v-theme-gray));
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

blockquote {
    border-left: 3px solid rgb(var(--v-theme-secondary));
    background-color: rgb(var(--v-theme-background-lighten-1));
    padding: 8px 12px;
    border-radius: 4px;
}

</style>