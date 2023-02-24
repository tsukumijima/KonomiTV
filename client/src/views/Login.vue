<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="login-container-wrapper d-flex align-center w-100 mb-13">
                <v-card class="login-container px-10 pt-8 pb-11 mx-auto background lighten-1" elevation="10"
                    width="100%" max-width="450">
                    <v-card-title class="login__logo flex-column justify-center">
                        <v-img max-width="250" src="/assets/images/logo.svg"></v-img>
                        <h4 class="mt-10">ログイン</h4>
                    </v-card-title>
                    <v-divider></v-divider>
                    <v-form ref="login" @submit.prevent>
                        <v-text-field class="mt-12" outlined placeholder="ユーザー名" hide-details autofocus
                            :dense="is_form_dense"
                            v-model="username">
                        </v-text-field>
                        <v-text-field class="mt-8" outlined placeholder="パスワード" hide-details
                            :dense="is_form_dense"
                            v-model="password"
                            :type="password_showing ? 'text' : 'password'"
                            :append-icon="password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                            @click:append="password_showing = !password_showing">
                        </v-text-field>
                        <v-btn class="login-button mt-5" color="secondary" depressed width="100%" height="56"
                            @click="login()">
                            <Icon icon="fa:sign-in" class="mr-2" />ログイン
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
    name: 'Login',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            username: '' as string,
            password: '' as string,
            password_showing: false,
        }
    },
    methods: {
        async login() {

            // ユーザー名またはパスワードが空
            if (this.username === '' || this.password === '') return;

            try {

                // ログインしてアクセストークンを取得する
                const response = await Vue.axios.post('/users/token', new URLSearchParams({
                    username: this.username,
                    password: this.password,
                }));

                // 取得したアクセストークンを保存
                console.log('Login successful.');
                console.log(response.data);
                Utils.saveAccessToken(response.data.access_token);

                // アカウントページに遷移
                // ブラウザバックでログインページに戻れないようにする
                this.$message.success('ログインしました。');
                await this.$router.replace({path: '/settings/account'});

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

.login-container-wrapper {
    @include smartphone-horizontal {
        padding: 20px !important;
        margin-bottom: 0px !important;
    }
    @include smartphone-vertical {
        margin-bottom: 0px !important;
    }

    .login-container {
        border-radius: 11px;
        @include smartphone-horizontal {
            padding: 24px !important;
        }
        @include smartphone-vertical {
            padding: 32px 20px !important;
            margin-left: 12px !important;
            margin-right: 12px !important;
        }

        .login__logo {
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
                margin-top: 24px !important;
                font-size: 14px !important;
            }
            @include smartphone-vertical {
                margin-top: 32px !important;
                font-size: 16px !important;
            }
        }

        .login-button {
            border-radius: 7px;
            margin-top: 48px !important;
            font-size: 18px;
            letter-spacing: 0px;
            @include smartphone-horizontal {
                height: 44px !important;
                margin-top: 24px !important;
                font-size: 16px;
            }
            @include smartphone-vertical {
                height: 50px !important;
                margin-top: 32px !important;
                font-size: 15.5px;
            }
        }
    }
}

</style>