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

import axios from 'axios';
import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
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
            password_showing: true,  // アカウント作成時は既定でパスワードを表示する
            password_validation: (value: string | null) => {
                if (value === '' || value === null) return 'パスワードを入力してください。';
                // 正規表現の参考: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },
        }
    },
    methods: {
        async register() {

            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if ((this.$refs.register as any).validate() === false) return;

            try {

                // アカウント作成 API にリクエスト
                const response = await Vue.axios.post('/users', {
                    username: this.username,
                    password: this.password,
                });

                console.log('Account created.')
                console.log(response.data);

            } catch (error) {

                // アカウントの作成に失敗
                // ref: https://dev.classmethod.jp/articles/typescript-typing-exception-objects-in-axios-trycatch/
                if (axios.isAxiosError(error) && error.response && error.response.status === 422) {

                    console.log('Failed to create account.');
                    console.log(error.response.data);

                    // エラーメッセージごとに Snackbar に表示
                    switch ((error.response.data as any).detail) {
                        case 'Specified username is duplicated': {
                            this.$message.error('ユーザー名が重複しています。');
                            break;
                        }
                        case 'Specified username is not accepted due to system limitations': {
                            this.$message.error('ユーザー名に token と me は使えません。');
                            break;
                        }
                        default: {
                            this.$message.error(`アカウントを作成できませんでした。(HTTP Error ${error.response.status})`);
                            break;
                        }
                    }
                }
                return;  // 処理を中断
            }

            // ここから先の処理はログイン画面とほぼ同じ
            try {

                // アカウントを作成できたので、ログインしてアクセストークンを取得する
                const response = await Vue.axios.post('/users/token', new URLSearchParams({
                    username: this.username,
                    password: this.password,
                }));

                // 取得したアクセストークンを保存
                console.log('Login successful.');
                console.log(response.data);
                Utils.saveAccessToken(response.data.access_token);

                // アカウントページに遷移
                this.$message.success('アカウントを作成しました。');
                await this.$router.push({path: '/settings/account'});

            } catch (error) {

                // ログインに失敗
                if (axios.isAxiosError(error) && error.response && error.response.status === 401) {

                    console.log('Failed to login.');
                    console.log(error.response.data);

                    // エラーメッセージごとに Snackbar に表示
                    switch ((error.response.data as any).detail) {
                        case 'Incorrect username': {
                            this.$message.error('ログインできませんでした。そのユーザー名のアカウントは存在しません。');
                            break;
                        }
                        case 'Incorrect password': {
                            this.$message.error('ログインできませんでした。パスワードを間違えていませんか？');
                            break;
                        }
                        default: {
                            this.$message.error(`ログインできませんでした。(HTTP Error ${error.response.status})`);
                            break;
                        }
                    }
                }
            }
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