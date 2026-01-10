<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="fluent:person-20-filled" width="25px" />
            <span class="ml-2">アカウント</span>
        </h2>
        <div class="settings__content" :class="{'settings__content--loading': is_loading}">
            <div class="account" v-if="userStore.user === null">
                <div class="account-wrapper">
                    <img class="account__icon" src="/assets/images/account-icon-default.png">
                    <div class="account__info">
                        <div class="account__info-name">
                            <span class="account__info-name-text">ログインしていません</span>
                        </div>
                        <span class="account__info-id">Not logged in</span>
                    </div>
                </div>
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="56" variant="flat" to="/login/">
                    <Icon icon="fa:sign-in" class="mr-2" />ログイン
                </v-btn>
            </div>
            <div class="account" v-if="userStore.user !== null">
                <div class="account-wrapper">
                    <img class="account__icon" :src="userStore.user_icon_url ?? ''">
                    <div class="account__info">
                        <div class="account__info-name">
                            <span class="account__info-name-text">{{userStore.user.name}}</span>
                            <span class="account__info-admin" v-if="userStore.user.is_admin">管理者</span>
                        </div>
                        <span class="account__info-id">User ID: {{userStore.user.id}}</span>
                    </div>
                </div>
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="56" variant="flat" @click="userStore.logout()">
                    <Icon icon="fa:sign-out" class="mr-2" />ログアウト
                </v-btn>
            </div>
            <div class="account-register" v-if="userStore.is_logged_in === false">
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
                            <span class="account-feature__info-heading">サーバー設定をブラウザから変更</span>
                            <span class="account-feature__info-text">管理者権限があれば、サーバー設定をブラウザから変更できます。一番最初に作成されたアカウントには、自動で管理者権限が付与されます。</span>
                        </div>
                    </div>
                </div>
                <div class="account-register__description">
                    KonomiTV アカウントの作成に必要なものは<br class="smartphone-vertical-only">ユーザー名とパスワードだけです。<br>
                    アカウントはローカルに導入した<br class="smartphone-vertical-only"> KonomiTV サーバーにのみ保存されます。<br>
                    外部のサービスには保存されませんので、ご安心ください。<br>
                </div>
                <v-btn class="account-register__button" color="secondary" width="100%" max-width="250" height="50" variant="flat" to="/register/">
                    <Icon icon="fluent:person-add-20-filled" class="mr-2" height="24" />アカウントを作成
                </v-btn>
            </div>
            <div v-if="userStore.is_logged_in === true">
                <div class="settings__item settings__item--switch">
                    <label class="settings__item-heading" for="sync_settings">設定をデバイス間で同期する</label>
                    <label class="settings__item-label" for="sync_settings">
                        KonomiTV では、設定を同じアカウントでログインしているデバイス間で同期できます！<br>
                        同期をオンにすると、同期をオンにしているすべてのデバイスで共通の設定が使えます。ピン留めしたチャンネル・マイリスト・視聴履歴・ハッシュタグリストなども一緒に同期されます。<br>
                        なお、デバイス固有の設定（画質設定など）は、同期後も各デバイスで個別に反映されます。<br>
                    </label>
                    <v-switch class="settings__item-switch" color="primary" id="sync_settings" hide-details
                        v-model="sync_settings">
                    </v-switch>
                </div>
                <v-dialog max-width="530" v-model="sync_settings_dialog">
                    <v-card>
                        <v-card-title class="d-flex justify-center font-weight-bold pt-6">設定データの競合</v-card-title>
                        <v-card-text class="pt-2 pb-5">
                            このデバイスの設定と、サーバーに保存されている設定が競合しています。<br>
                            一度上書きすると、元に戻すことはできません。慎重に選択してください。<br>
                        </v-card-text>
                        <div class="d-flex flex-column px-4 pb-6 settings__conflict-dialog">
                            <v-btn class="settings__save-button text-error-lighten-1" color="background-lighten-1" variant="flat"
                                @click="overrideServerSettingsFromClient()">
                                <Icon icon="fluent:document-arrow-up-16-filled" class="mr-2" height="22px" />
                                サーバーに保存されている設定を、<br class="smartphone-vertical-only">このデバイスの設定で上書きする
                            </v-btn>
                            <v-btn class="settings__save-button text-error-lighten-1 mt-3" color="background-lighten-1" variant="flat"
                                @click="overrideClientSettingsFromServer()">
                                <Icon icon="fluent:document-arrow-down-16-filled" class="mr-2" height="22px" />
                                このデバイスの設定を、<br class="smartphone-vertical-only">サーバーに保存されている設定で上書きする
                            </v-btn>
                            <v-btn class="settings__save-button mt-3" variant="flat" color="background-lighten-1"
                                @click="sync_settings_dialog = false">
                                <Icon icon="fluent:dismiss-16-filled" class="mr-2" height="22px" />
                                キャンセル
                            </v-btn>
                        </div>
                    </v-card>
                </v-dialog>
                <v-form class="settings__item" ref="settings_username" @submit.prevent>
                    <div class="settings__item-heading">ユーザー名</div>
                    <div class="settings__item-label">
                        KonomiTV アカウントのユーザー名を設定します。アルファベットだけでなく日本語や記号も使えます。<br>
                        同じ KonomiTV サーバー上の他のアカウントと同じユーザー名には変更できません。<br>
                    </div>
                    <v-text-field class="settings__item-form" color="primary" variant="outlined" placeholder="ユーザー名"
                        :density="is_form_dense ? 'compact' : 'default'"
                        v-model="settings_username"
                        :rules="[settings_username_validation]">
                    </v-text-field>
                </v-form>
                <v-btn class="settings__save-button mt-2" variant="flat" @click="updateAccountInfo('username')">
                    <Icon icon="fluent:save-16-filled" class="mr-2" height="24px" />ユーザー名を更新
                </v-btn>
                <v-form class="settings__item" @submit.prevent>
                    <div class="settings__item-heading">アイコン画像</div>
                    <div class="settings__item-label">
                        KonomiTV アカウントのアイコン画像を設定します。<br>
                        アップロードされた画像は自動で 400×400 の正方形にリサイズされます。<br>
                    </div>
                    <v-file-input class="settings__item-form" color="primary" variant="outlined" hide-details
                        label="アイコン画像を選択"
                        :density="is_form_dense ? 'compact' : 'default'"
                        accept="image/jpeg, image/png"
                        prepend-icon=""
                        prepend-inner-icon="mdi-paperclip"
                        v-model="settings_icon_file">
                    </v-file-input>
                </v-form>
                <v-btn class="settings__save-button mt-5" variant="flat" @click="updateAccountIcon()">
                    <Icon icon="fluent:save-16-filled" class="mr-2" height="24px" />アイコン画像を更新
                </v-btn>
                <v-form class="settings__item" ref="settings_password" @submit.prevent>
                    <div class="settings__item-heading">新しいパスワード</div>
                    <div class="settings__item-label">
                        KonomiTV アカウントの新しいパスワードを設定します。<br>
                    </div>
                    <v-text-field class="settings__item-form" color="primary" variant="outlined" placeholder="新しいパスワード"
                        :density="is_form_dense ? 'compact' : 'default'"
                        v-model="settings_password"
                        :type="settings_password_showing ? 'text' : 'password'"
                        :rules="[settings_password_validation]"
                        :append-inner-icon="settings_password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                        @click:appendInner="settings_password_showing = !settings_password_showing">
                    </v-text-field>
                </v-form>
                <v-btn class="settings__save-button mt-2" variant="flat" @click="updateAccountInfo('password')">
                    <Icon icon="fluent:save-16-filled" class="mr-2" height="24px" />パスワードを更新
                </v-btn>
                <v-divider class="mt-6"></v-divider>
                <div class="settings__item mt-6">
                    <div class="settings__item-heading text-error-lighten-1">アカウントを削除</div>
                    <div class="settings__item-label">
                        現在ログインしている KonomiTV アカウントを削除します。<br>
                        <strong class="text-error-lighten-1">アカウントに紐づくすべてのデータが削除されます。元に戻すことはできません。</strong><br>
                    </div>
                </div>
                <v-btn class="settings__save-button bg-error mt-5" variant="flat" @click="account_delete_confirm_dialog = true">
                    <Icon icon="fluent:delete-16-filled" class="mr-2" height="24px" />アカウントを削除
                </v-btn>
                <v-dialog max-width="385" v-model="account_delete_confirm_dialog">
                    <v-card>
                        <v-card-title class="d-flex justify-center pt-6 font-weight-bold">本当にアカウントを削除しますか？</v-card-title>
                        <v-card-text class="pt-2 pb-0">
                            アカウントに紐づくすべてのユーザーデータが削除されます。元に戻すことはできません。<br>
                            本当にアカウントを削除しますか？
                        </v-card-text>
                        <v-card-actions class="pt-4 px-6 pb-6">
                            <v-spacer></v-spacer>
                            <v-btn color="text" variant="text" @click="account_delete_confirm_dialog = false">キャンセル</v-btn>
                            <v-btn color="error" variant="flat" @click="deleteAccount()">削除</v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';
import { VForm } from 'vuetify/components';

import Message from '@/message';
import Settings from '@/services/Settings';
import useSettingsStore, { getSyncableClientSettings, hashClientSettings } from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default defineComponent({
    name: 'Settings-Account',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // ローディング中かどうか
            is_loading: true,

            // ユーザー名とパスワード
            // ログイン画面やアカウント作成画面の data と同一のもの
            settings_username: null as string | null,
            settings_username_validation: (value: string | null) => {
                if (value === '' || value === null) return 'ユーザー名を入力してください。';
                if (/^.{2,}$/.test(value) === false) return 'ユーザー名は2文字以上で入力してください。';
                return true;
            },
            settings_password: null as string | null,
            settings_password_showing: false,
            settings_password_validation: (value: string | null) => {
                if (value === '' || value === null) return 'パスワードを入力してください。';
                // 正規表現の参考: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },

            // アップロードするアイコン画像
            // 基本1ファイルしか入らない (Vuetify 側の都合で配列になっている)
            settings_icon_file: null as File | null,

            // アカウント削除確認ダイヤログ
            account_delete_confirm_dialog: false,

            // 設定を同期するかの設定値
            sync_settings: useSettingsStore().settings.sync_settings as boolean,

            // 設定を同期するときのダイヤログ
            sync_settings_dialog: false,
        };
    },
    computed: {
        ...mapStores(useSettingsStore, useUserStore),
    },
    watch: {
        // sync_settings の値の変更を監視する
        async sync_settings() {

            // 同期がオンになった & ダイヤログが表示されていない
            if (this.sync_settings === true && this.sync_settings_dialog === false) {

                // 同期対象の設定キーのみで設定データをまとめ直す
                const sync_settings = getSyncableClientSettings(this.settingsStore.settings);

                // 同期対象のこのクライアントの設定をハッシュ化する
                const sync_settings_hash = hashClientSettings(sync_settings);

                // サーバーから設定データをダウンロード
                // 一度オブジェクトに戻したものをハッシュ化する
                const server_sync_settings = await Settings.fetchClientSettings();
                if (server_sync_settings === null) {
                    Message.error('サーバーから設定データを取得できませんでした。');
                    return;
                }
                const server_sync_settings_hash = hashClientSettings(server_sync_settings);
                console.log('[Settings-Account] sync_settings_hash:', sync_settings_hash);
                console.log('[Settings-Account] server_sync_settings_hash:', server_sync_settings_hash);

                // このクライアントの設定とサーバーに保存されている設定が一致しない（=競合している）
                if (sync_settings_hash !== server_sync_settings_hash) {

                    // 一度同期のスイッチをオフにして、クライアントとサーバーどちらの設定を使うのかを選択させるダイヤログを表示
                    this.sync_settings_dialog = true;
                    this.sync_settings = false;

                // このクライアントの設定とサーバーに保存されている設定が一致する
                } else {

                    // 特に設定の同期をオンにしても問題ないので、そのまま有効にする
                    this.settingsStore.settings.sync_settings = true;
                }

            // 同期がオフになった & ダイヤログが表示されていない
            } else if (this.sync_settings === false && this.sync_settings_dialog === false) {
                this.settingsStore.settings.sync_settings = false;
            }
        }
    },
    async created() {

        // アカウント情報を更新
        await this.userStore.fetchUser();

        // ローディング状態を解除
        this.is_loading = false;
    },
    methods: {

        // このクライアントの設定でサーバー上の設定を上書きする
        async overrideServerSettingsFromClient() {

            // 強制的にこのクライアントの設定をサーバーに同期
            await this.settingsStore.syncClientSettingsToServer(true);

            // 設定の同期を有効化
            this.settingsStore.settings.sync_settings = true;
            this.sync_settings = true;

            // ダイヤログを閉じる
            this.sync_settings_dialog = false;
        },

        // サーバー上の設定でこのクライアントの設定を上書きする
        async overrideClientSettingsFromServer() {

            // 強制的にサーバーに保存されている設定データをこのクライアントに同期する
            // 設定の同期を有効化する前に実行しておくのが重要
            await this.settingsStore.syncClientSettingsFromServer(true);

            // 設定の同期を有効化
            // 値を変更した時点で設定データがサーバーにアップロードされてしまうので、
            // それよりも前に syncClientSettingsFromServer(true) でサーバー上の設定データを同期させておく必要がある
            // さもなければ、サーバー上の設定データがこのクライアントの設定で上書きされてしまい、overrideServerSettingsFromClient() と同じ挙動になってしまう
            this.settingsStore.settings.sync_settings = true;
            this.sync_settings = true;

            // ダイヤログを閉じる
            this.sync_settings_dialog = false;
        },

        async updateAccountInfo(update_type: 'username' | 'password') {

            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if (update_type === 'username') {
                if ((await (this.$refs.settings_username as VForm).validate()).valid === false) return;
            } else {
                if ((await (this.$refs.settings_password as VForm).validate()).valid === false) return;
            }

            // アカウント情報の更新処理 (エラーハンドリングを含む) を実行
            if (update_type === 'username') {
                if (this.settings_username === null) return;
                await this.userStore.updateUser({username: this.settings_username});
            } else {
                if (this.settings_password === null) return;
                await this.userStore.updateUser({password: this.settings_password});
            }
        },

        async updateAccountIcon() {

            // アイコン画像が選択されていないなら更新しない
            if (this.settings_icon_file === null) {
                Message.error('アップロードする画像を選択してください！');
                return;
            }

            // アイコン画像の更新処理 (エラーハンドリングを含む) を実行
            await this.userStore.updateUserIcon(this.settings_icon_file);
        },

        async deleteAccount() {

            // ダイヤログを閉じる
            this.account_delete_confirm_dialog = false;

            // アカウント削除処理 (エラーハンドリングを含む) を実行
            await this.userStore.deleteUser();
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

.settings__conflict-dialog {
    .v-btn {
        @include smartphone-vertical {
            height: 50px !important;
            text-align: left;
        }
        br.smartphone-vertical-only {
            display: none;
            @include smartphone-vertical {
                display: inline;
            }
        }
    }
}

.account {
    display: flex;
    align-items: center;
    height: 130px;
    padding: 18px 20px;
    border-radius: 15px;
    background: rgb(var(--v-theme-background-lighten-2));
    @include tablet-horizontal {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px;
    }
    @include tablet-vertical {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px;
    }
    @include smartphone-horizontal {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px;
        border-radius: 10px;
    }
    @include smartphone-vertical {
        align-items: normal;
        flex-direction: column;
        height: auto;
        padding: 16px 12px;
        border-radius: 10px;
    }

    &-wrapper {
        display: flex;
        align-items: center;
        min-width: 0;
        height: 94px;
        @include smartphone-horizontal {
            height: 80px;
        }
        @include smartphone-vertical {
            height: 70px;
        }
    }

    &__icon {
        flex-shrink: 0;
        min-width: 94px;
        height: 100%;
        border-radius: 50%;
        object-fit: cover;
        // 読み込まれるまでのアイコンの背景
        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
        // 低解像度で表示する画像がぼやけないようにする
        // ref: https://sho-log.com/chrome-image-blurred/
        image-rendering: -webkit-optimize-contrast;
        @include smartphone-horizontal {
            min-width: 80px;
        }
        @include smartphone-vertical {
            min-width: 70px;
        }
    }

    &__info {
        display: flex;
        flex-direction: column;
        min-width: 0;
        margin-left: 20px;
        margin-right: 12px;
        @include smartphone-vertical {
            margin-left: 12px !important;
            margin-right: 0 !important;
        }

        &-name {
            display: inline-flex;
            align-items: center;
            height: 33px;

            &-text {
                display: inline-block;
                font-size: 23px;
                color: rgb(var(--v-theme-text));
                font-weight: bold;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;  // はみ出た部分を … で省略
                @include smartphone-horizontal {
                    font-size: 21px;
                }
                @include smartphone-vertical {
                    font-size: 20px;
                }
            }
        }

        &-admin {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 52px;
            height: 28px;
            margin-left: 10px;
            border-radius: 5px;
            background: rgb(var(--v-theme-secondary));
            font-size: 14px;
            font-weight: 500;
            line-height: 2;
            @include smartphone-horizontal {
                width: 45px;
                height: 24px;
                border-radius: 4px;
                font-size: 11.5px;
            }
            @include smartphone-vertical {
                width: 45px;
                height: 24px;
                border-radius: 4px;
                font-size: 11.5px;
            }
        }

        &-id {
            display: inline-block;
            margin-top: 2px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 16px;
            @include smartphone-horizontal {
                font-size: 14.5px;
            }
            @include smartphone-vertical {
                font-size: 14.5px;
            }
        }
    }

    &__login {
        border-radius: 7px;
        font-size: 16px;
        letter-spacing: 0;
        @include tablet-horizontal {
            height: 50px !important;
            margin-top: 8px;
            margin-right: auto;
            font-size: 14.5px;
        }
        @include tablet-vertical {
            height: 42px !important;
            margin-top: 8px;
            margin-right: auto;
            font-size: 14.5px;
        }
        @include smartphone-horizontal {
            height: 42px !important;
            margin-top: 8px;
            margin-right: auto;
            font-size: 14.5px;
        }
        @include smartphone-vertical {
            height: 42px !important;
            margin-top: 16px;
            margin-right: auto;
            font-size: 14.5px;
        }
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
        @include smartphone-horizontal {
            font-size: 19px;
        }
        @include smartphone-vertical {
            font-size: 18px;
        }
    }

    &__feature {
        display: grid;
        grid-template-columns: 1fr 1fr;
        grid-row-gap: 18px;
        grid-column-gap: 16px;
        margin-top: 28px;
        @include tablet-horizontal {
            grid-template-columns: 1fr;
        }
        @include tablet-vertical {
            grid-template-columns: 1fr;
        }
        @include smartphone-horizontal {
            grid-template-columns: 1fr;
        }
        @include smartphone-vertical {
            grid-template-columns: 1fr;
        }

        .account-feature {
            display: flex;
            align-items: center;

            &__icon {
                width: 46px;
                height: 46px;
                flex-shrink: 0;
                margin-right: 16px;
                color: rgb(var(--v-theme-secondary-lighten-1));
            }

            &__info {
                display: flex;
                flex-direction: column;
                &-heading {
                    font-size: 15px;
                }
                &-text {
                    margin-top: 3px;
                    color: rgb(var(--v-theme-text-darken-1));
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
        br.smartphone-vertical-only {
            display: none;
        }
        @include tablet-horizontal {
            font-size: 12.5px;
        }
        @include tablet-vertical {
            font-size: 10.5px;
        }
        @include smartphone-horizontal {
            font-size: 12.5px;
        }
        @include smartphone-horizontal-short {
            font-size: 10.5px;
        }
        @include smartphone-vertical {
            font-size: 12.5px;
            br.smartphone-vertical-only {
                display: inline;
            }
        }
    }

    &__button {
        margin-top: 24px;
        margin-left: auto;
        margin-right: auto;
        border-radius: 7px;
        font-size: 16px;
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
            max-width: 210px !important;
            height: 42px !important;
            font-size: 15px;
        }
    }
}

</style>