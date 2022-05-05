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
                    <span class="account__info-id">Not logged in</span>
                </div>
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="56" depressed to="/login/">
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
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="56" depressed @click="logout()">
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
            <div class="settings__content" v-if="is_logged_in === true">
                <v-form class="settings__item" ref="settings_username">
                    <div class="settings__item-heading">ユーザー名</div>
                    <div class="settings__item-label">
                        KonomiTV アカウントのユーザー名を設定します。アルファベットだけでなく日本語も使えます。<br>
                        同じ KonomiTV サーバー上の他のアカウントと同じユーザー名には変更できません。<br>
                    </div>
                    <v-text-field class="settings__item-form" outlined placeholder="ユーザー名"
                        v-model="settings_username"
                        :rules="[settings_username_validation]">
                    </v-text-field>
                </v-form>
                <v-btn class="settings__save-button" depressed @click="updateAccountInfo('username')">
                    <Icon icon="fluent:save-16-filled" class="mr-2" height="24px" />ユーザー名を更新
                </v-btn>
                <v-form class="settings__item" ref="settings_username">
                    <div class="settings__item-heading">アイコン画像</div>
                    <div class="settings__item-label">
                        KonomiTV アカウントのアイコン画像を設定します。<br>
                        アップロードされた画像は自動的に 400×400 の正方形にリサイズされます。<br>
                    </div>
                    <v-file-input class="settings__item-form" outlined hide-details placeholder="アイコン画像を選択"
                        accept="image/jpeg, image/png"
                        prepend-icon=""
                        prepend-inner-icon="mdi-paperclip"
                        v-model="settings_icon">
                    </v-file-input>
                </v-form>
                <v-btn class="settings__save-button mt-5" depressed @click="updateAccountIcon()">
                    <Icon icon="fluent:save-16-filled" class="mr-2" height="24px" />アイコン画像を更新
                </v-btn>
                <v-form class="settings__item" ref="settings_password">
                    <div class="settings__item-heading">新しいパスワード</div>
                    <div class="settings__item-label">
                        KonomiTV アカウントの新しいパスワードを設定します。<br>
                    </div>
                    <v-text-field class="settings__item-form" outlined placeholder="新しいパスワード"
                        v-model="settings_password"
                        :type="settings_password_showing ? 'text' : 'password'"
                        :append-icon="settings_password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                        :rules="[settings_password_validation]"
                        @click:append="settings_password_showing = !settings_password_showing">
                    </v-text-field>
                </v-form>
                <v-btn class="settings__save-button" depressed @click="updateAccountInfo('password')">
                    <Icon icon="fluent:save-16-filled" class="mr-2" height="24px" />パスワードを更新
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

            // ユーザー名とパスワード
            // ログイン画面やアカウント作成画面の data と同一のもの
            settings_username: null as string | null,
            settings_username_validation: (value: string | null) => {
                if (value === '' || value === null) return 'ユーザー名を入力してください。';
                if (/^.{2,}$/.test(value) === false) return 'ユーザー名は2文字以上で入力してください。';
                return true;
            },
            settings_password: null as string | null,
            settings_password_showing: true,  // アカウント情報変更時は既定でパスワードを表示する
            settings_password_validation: (value: string | null) => {
                if (value === '' || value === null) return 'パスワードを入力してください。';
                // 正規表現の参考: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },

            // アイコン画像
            settings_icon: null as File | null,
        }
    },
    async created() {

        // 未ログイン時は実行しない
        if (this.is_logged_in === false) return;

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

        // 表示されているアカウント情報を更新
        await this.syncAccountInfo();
    },
    methods: {
        async syncAccountInfo() {

            try {

                // ユーザーアカウントの情報を取得する
                const response = await Vue.axios.get('/users/me');
                this.user = response.data;
                this.settings_username = this.user.name;

                // 表示中のアイコン画像を更新
                await this.syncAccountIcon();

            } catch (error) {

                // ログインされていない
                if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
                    console.log('Not logged in.');

                    // 未ログイン状態に設定
                    this.is_logged_in = false;
                    this.user = null;
                    this.user_icon_blob = '';
                }
            }
        },

        async syncAccountIcon() {

            // ユーザーアカウントのアイコンを取得する
            // 認証が必要な URL は img タグからは直で読み込めないため
            const icon_response = await Vue.axios.get('/users/me/icon', {
                responseType: 'arraybuffer',
            });

            // Blob URL を生成
            this.user_icon_blob = URL.createObjectURL(new Blob([icon_response.data], {type: 'image/png'}));
        },

        async updateAccountInfo(update_type: 'username' | 'password') {

            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if (update_type === 'username') {
                if ((this.$refs.settings_username as any).validate() === false) return;
            } else {
                if ((this.$refs.settings_password as any).validate() === false) return;
            }

            try {

                // アカウント情報更新 API にリクエスト
                // レスポンスは 204 No Content なので不要
                if (update_type === 'username') {
                    await Vue.axios.put('/users/me', {username: this.settings_username});
                    this.$message.show('ユーザー名を更新しました。');
                } else {
                    await Vue.axios.put('/users/me', {password: this.settings_password});
                    this.$message.show('パスワードを更新しました。');
                }

                // 表示中のアカウント情報を更新
                await this.syncAccountInfo();

            } catch (error) {

                // アカウント情報の更新に失敗
                // ref: https://dev.classmethod.jp/articles/typescript-typing-exception-objects-in-axios-trycatch/
                if (axios.isAxiosError(error) && error.response && error.response.status === 422) {
                    // エラーメッセージごとに Snackbar に表示
                    switch (error.response.data.detail) {
                        case 'Specified username is duplicated': {
                            this.$message.error('ユーザー名が重複しています。');
                            break;
                        }
                        case 'Specified username is not accepted due to system limitations': {
                            this.$message.error('ユーザー名に token と me は使えません。');
                            break;
                        }
                        default: {
                            this.$message.error(`アカウント情報を更新できませんでした。(HTTP Error ${error.response.status})`);
                            break;
                        }
                    }
                }
            }
        },

        async updateAccountIcon() {

            // アイコン画像が選択されていないなら更新しない
            if (this.settings_icon === null) {
                this.$message.error('アップロードする画像を選択してください！');
                return;
            }

            // アイコン画像の File オブジェクト（=Blob）を FormData に入れる
            // multipart/form-data で送るために必要
            // ref: https://r17n.page/2020/02/04/nodejs-axios-file-upload-api/
            const form_data = new FormData();
            form_data.append('image', this.settings_icon);

            try {

                // アカウントアイコン画像更新 API にリクエスト
                await Vue.axios.put('/users/me/icon', form_data, {headers: {'Content-Type': 'multipart/form-data'}});

                // 表示中のアイコン画像を更新
                await this.syncAccountIcon();

            } catch (error) {

                // アカウント情報の更新に失敗
                // ref: https://dev.classmethod.jp/articles/typescript-typing-exception-objects-in-axios-trycatch/
                if (axios.isAxiosError(error) && error.response && error.response.status === 422) {
                    // エラーメッセージごとに Snackbar に表示
                    switch (error.response.data.detail) {
                        case 'Please upload JPEG or PNG image': {
                            this.$message.error('JPEG または PNG 画像をアップロードしてください。');
                            break;
                        }
                        default: {
                            this.$message.error(`アイコン画像を更新できませんでした。(HTTP Error ${error.response.status})`);
                            break;
                        }
                    }
                }
            }
        },

        logout() {

            // ブラウザからアクセストークンを削除
            // これをもってログアウトしたことになる（それ以降の Axios のリクエストにはアクセストークンが含まれなくなる）
            Utils.deleteAccessToken();

            // 未ログイン状態に設定
            this.is_logged_in = false;
            this.user = null;
            this.user_icon_blob = '';

            this.$message.success('ログアウトしました。');
        },
    }
});

</script>
<style lang="scss" scoped>

.account {
    display: flex;
    align-items: center;
    height: 130px;
    padding: 18px 20px;
    border-radius: 15px;
    background: var(--v-background-lighten2);

    &__icon {
        min-width: 94px;
        height: 100%;
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
        font-size: 16px;
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