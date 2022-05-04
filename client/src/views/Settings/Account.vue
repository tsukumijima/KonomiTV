<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="fluent:person-20-filled" width="24px" />
            <span class="ml-2">アカウント</span>
        </h2>
        <div class="settings__content">
            <div class="account" v-if="user === null">
                <img class="account__icon" src="/assets/images/account-icon-default.png">
                <div class="account__info">
                    <span class="account__info-name">ログインしていません</span>
                    <span class="account__info-id">Not Login</span>
                </div>
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="60" depressed to="/login/">
                    <Icon icon="fa:sign-in" class="mr-2" />ログイン
                </v-btn>
            </div>
            <div class="account" v-if="user !== null">
                <img class="account__icon" :src="user_icon_blob">
                <div class="account__info">
                    <div class="account__info-name">
                        {{user.name}}
                        <span class="account__info-admin" v-if="user.is_admin">管理者</span>
                    </div>
                    <span class="account__info-id">User ID: {{user.id}}</span>
                </div>
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="60" depressed @click="logout()">
                    <Icon icon="fa:sign-out" class="mr-2" />ログアウト
                </v-btn>
            </div>
            <div class="account-register" v-if="is_logged_in === false">
                <div class="account-register__heading">
                    KonomiTV アカウントにログインすると、<br>より便利な機能が使えます！
                </div>
                <div class="account-register__feature">
                    <div class="account-feature">
                        <Icon class="account-feature__icon" icon="bi:chat-left-text-fill" />
                        <div class="account-feature__info">
                            <span class="account-feature__info-heading">ニコニコ実況にコメントする</span>
                            <span class="account-feature__info-text">テレビを見ながらニコニコ実況にコメントできます。別途、ニコニコアカウントとの連携が必要です。</span>
                        </div>
                    </div>
                    <div class="account-feature">
                        <Icon class="account-feature__icon" icon="fa-brands:twitter" />
                        <div class="account-feature__info">
                            <span class="account-feature__info-heading">Twitter 連携機能</span>
                            <span class="account-feature__info-text">テレビを見ながら Twitter にツイートしたり、検索したツイートをリアルタイムで表示できます。別途、Twitter アカウントとの連携が必要です。</span>
                        </div>
                    </div>
                    <div class="account-feature">
                        <Icon class="account-feature__icon" icon="fluent:arrow-sync-20-filled" />
                        <div class="account-feature__info">
                            <span class="account-feature__info-heading">設定をデバイス間で同期</span>
                            <span class="account-feature__info-text">ピン留めしたチャンネルなど、ブラウザに保存されている各種設定をブラウザやデバイスをまたいで同期できます。</span>
                        </div>
                    </div>
                    <div class="account-feature">
                        <Icon class="account-feature__icon" icon="fa-solid:sliders-h" />
                        <div class="account-feature__info">
                            <span class="account-feature__info-heading">環境設定をブラウザから変更</span>
                            <span class="account-feature__info-text">管理者権限があれば、環境設定をブラウザから変更できます。一番最初に作成されたアカウントには、自動で管理者権限が付与されます。</span>
                        </div>
                    </div>
                </div>
                <div class="account-register__description">
                    KonomiTV アカウントの作成に必要なものはユーザー名とパスワードだけです。<br>
                    アカウントはローカルにインストールした KonomiTV サーバーごとに保存されます。<br>
                    外部のサービスには保存されませんので、ご安心ください。<br>
                </div>
                <v-btn class="account-register__button" color="secondary" width="100%" max-width="250" height="50" depressed to="/register/">
                    <Icon icon="fluent:person-add-20-filled" class="mr-2" height="24" />アカウントを作成
                </v-btn>
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
    name: 'SettingsAccount',
    components: {
        Base,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,

            // ログイン中かどうか
            is_logged_in: Utils.getAccessToken() !== null,

            // ユーザーアカウントの情報
            // ログインしていない場合は null になる
            user: null as IUser | null,

            // ユーザーアカウントのアイコンの Blob URL
            user_icon_blob: '',
        }
    },
    async created() {

        // ロード時のちらつきを抑えるために、とりあえず値を入れておく
        this.user = {
            id: 0,
            name: '',
            is_admin: true,
            niconico_user_id: 0,
            niconico_user_name: '',
            twitter_accounts: [],
            created_at: '',
            updated_at: '',
        }

        try {

            // ユーザーアカウントの情報を取得する
            const response = await Vue.axios.get('/users/me');
            this.user = response.data;

            // ユーザーアカウントのアイコンを取得する
            // 認証が必要な URL は img タグからは直で読み込めないため
            const icon_response = await Vue.axios.get('/users/me/icon', {
                responseType: 'arraybuffer',
            });

            // Blob URL を生成
            this.user_icon_blob = URL.createObjectURL(new Blob([icon_response.data], {type: 'image/png'}));

        } catch (error) {

            // ログインされていない
            // user が null になったままなので、自動的に未ログイン時向けの画面が表示される
            if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
                console.log('Not logged in.');
            }
        }
    },
    methods: {
        logout() {

            // ブラウザからアクセストークンを削除
            // これをもってログアウトしたことになる（それ以降の Axios のリクエストにはアクセストークンが含まれなくなる）
            Utils.deleteAccessToken();

            // 未ログイン状態に設定
            this.is_logged_in = false;
            this.user = null;
            this.user_icon_blob = '';

            this.$message.success('ログアウトしました。');
        }
    }
});

</script>
<style lang="scss" scoped>

.account {
    display: flex;
    align-items: center;
    height: 130px;
    padding: 24px;
    border-radius: 15px;
    background: var(--v-background-lighten2);

    &__icon {
        min-width: 82px;
        height: 100%;
        border-radius: 50%;
        // 読み込まれるまでのアイコンの背景
        background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
        object-fit: cover;
    }

    &__info {
        display: flex;
        flex-direction: column;
        margin-left: 20px;

        &-name {
            display: inline-flex;
            align-items: center;
            height: 33px;
            color: var(--v-text-base);
            font-size: 23px;
            font-weight: bold;
        }

        &-admin {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 52px;
            height: 28px;
            margin-left: 12px;
            border-radius: 5px;
            background: var(--v-secondary-base);
            font-size: 14px;
            font-weight: 500;
        }

        &-id {
            display: inline-block;
            margin-top: 2px;
            color: var(--v-text-darken1);
            font-size: 16px;
        }
    }

    &__login {
        border-radius: 7px;
        font-size: 17px;
        letter-spacing: 0;
    }
}

.account-register {
    display: flex;
    flex-direction: column;
    margin-top: 28px;

    &__heading {
        font-size: 21px;
        font-weight: bold;
        text-align: center;
        font-feature-settings: "palt" 1;  // 文字詰め
        letter-spacing: 0.04em;  // 字間を少し空ける
    }

    &__feature {
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-row-gap: 18px;
        grid-column-gap: 16px;
        margin-top: 28px;

        .account-feature {
            display: flex;
            align-items: center;

            &__icon {
                width: 46px;
                height: 46px;
                flex-shrink: 0;
                margin-right: 16px;
                color: var(--v-secondary-lighten1);
            }

            &__info {
                display: flex;
                flex-direction: column;
                &-heading {
                    font-size: 15px;
                }
                &-text {
                    margin-top: 3px;
                    color: var(--v-text-darken1);
                    font-size: 12.5px;
                    line-height: 1.65;
                }
            }
        }
    }

    &__description {
        margin-top: 32px;
        font-size: 15px;
        line-height: 1.7;
        text-align: center;
    }

    &__button {
        margin-top: 24px;
        margin-left: auto;
        margin-right: auto;
        border-radius: 7px;
        font-size: 17px;
        letter-spacing: 0;
    }
}

</style>