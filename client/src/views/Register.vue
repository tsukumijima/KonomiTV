<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="register-container-wrapper d-flex align-center w-100 mb-13">
                <v-card class="register-container px-10 pt-8 pb-11 mx-auto background lighten-1" elevation="10"
                    width="100%" max-width="450">
                    <v-card-title class="register__logo flex-column justify-center">
                        <v-img max-width="250" src="/assets/images/logo.svg"></v-img>
                        <h4 class="mt-10">アカウントを作成</h4>
                    </v-card-title>
                    <v-divider></v-divider>
                    <v-form ref="register" @submit.prevent>
                        <v-text-field class="mt-12" outlined placeholder="ユーザー名" autofocus
                            :dense="is_form_dense"
                            v-model="username"
                            :rules="[username_validation]">
                        </v-text-field>
                        <v-text-field style="margin-top: 2px;" outlined placeholder="パスワード"
                            :dense="is_form_dense"
                            v-model="password"
                            :type="password_showing ? 'text' : 'password'"
                            :append-icon="password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                            :rules="[password_validation]"
                            @click:append="password_showing = !password_showing">
                        </v-text-field>
                        <v-btn class="register-button mt-5" color="secondary" depressed width="100%" height="56"
                            @click="register()">
                            <Icon icon="fluent:person-add-20-filled" class="mr-2" height="24" />アカウントを作成
                        </v-btn>
                    </v-form>
            </v-card>
            </div>
        </main>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

export default Vue.extend({
    name: 'Register',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            username: null as string | null,
            username_validation: (value: string | null) => {
                if (value === '' || value === null) return 'ユーザー名を入力してください。';
                if (/^.{2,}$/.test(value) === false) return 'ユーザー名は2文字以上で入力してください。';
                return true;
            },
            password: null as string | null,
            password_showing: true,  // アカウント作成時はデフォルトでパスワードを表示する
            password_validation: (value: string | null) => {
                if (value === '' || value === null) return 'パスワードを入力してください。';
                // 正規表現の参考: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },
        };
    },
    computed: {
        // UserStore に this.userStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useUserStore),
    },
    async created() {

        // アカウント情報を更新
        await this.userStore.fetchUser();

        // 現在ログイン中の場合はアカウントページに遷移
        if (this.userStore.is_logged_in) {
            await this.$router.replace({path: '/settings/account'});
        }
    },
    methods: {
        async register() {

            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if ((this.$refs.register as any).validate() === false) return;
            if (this.username === null || this.password === null) return;

            // アカウント作成 & ログイン処理 (エラーハンドリング含む) を実行
            const result = await this.userStore.register(this.username, this.password);
            if (result === false) {
                return;  // ログイン失敗
            }

            // アカウントページに遷移
            // ブラウザバックでアカウント作成画面に戻れないようにする
            await this.$router.replace({path: '/settings/account'});
        }
    }
});

</script>
<style lang="scss" scoped>

.register-container-wrapper {
    @include smartphone-horizontal {
        padding: 20px !important;
        margin-bottom: 0px !important;
    }
    @include smartphone-vertical {
        margin-bottom: 0px !important;
    }

    .register-container {
        border-radius: 11px;
        @include smartphone-horizontal {
            padding: 24px !important;
        }
        @include smartphone-vertical {
            padding: 32px 20px !important;
            margin-left: 12px !important;
            margin-right: 12px !important;
        }

        .register__logo {
            @include smartphone-horizontal {
                padding-top: 4px !important;
                padding-bottom: 8px !important;
                .v-image {
                    max-width: 200px !important;
                }
                h4 {
                    margin-top: 16px !important;
                    font-size: 19px !important;
                }
            }
            @include smartphone-vertical {
                padding-top: 4px !important;
                padding-bottom: 12px !important;
                .v-image {
                    max-width: 200px !important;
                }
                h4 {
                    margin-top: 24px !important;
                    font-size: 19px !important;
                }
            }
        }

        .v-input {
            @include smartphone-horizontal {
                margin-top: 0px !important;
                font-size: 14px !important;
            }
            @include smartphone-vertical {
                margin-top: 2px !important;
                font-size: 16px !important;
            }
        }
        .v-input:nth-child(1) {
            @include smartphone-horizontal {
                margin-top: 24px !important;
            }
            @include smartphone-vertical {
                margin-top: 32px !important;
            }
        }

        .register-button {
            border-radius: 7px;
            margin-top: 18px !important;
            font-size: 18px;
            letter-spacing: 0px;
            @include smartphone-horizontal {
                height: 44px !important;
                margin-top: 0px !important;
                font-size: 16px;
            }
            @include smartphone-vertical {
                height: 50px !important;
                margin-top: 2px !important;
                font-size: 15.5px;
            }
        }
    }
}


</style>