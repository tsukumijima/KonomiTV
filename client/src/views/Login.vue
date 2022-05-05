<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="d-flex align-center w-100 mb-13">
                <v-card class="login-container px-10 pt-8 pb-11 mx-auto background lighten-1" elevation="10"
                    width="100%" max-width="450">
                    <v-card-title class="justify-center pb-7">
                        <v-img max-width="250" src="/assets/images/logo.svg"></v-img>
                    </v-card-title>
                    <v-divider></v-divider>
                    <v-form ref="login" @submit.prevent>
                        <v-text-field class="mt-12" autofocus outlined placeholder="ユーザー名"
                            v-model="username"
                            :rules="[username_validation]">
                        </v-text-field>
                        <v-text-field class="mt-2" outlined placeholder="パスワード"
                            v-model="password"
                            :type="password_showing ? 'text' : 'password'"
                            :append-icon="password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                            :rules="[password_validation]"
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
            username: null as string | null,
            username_validation: (value: string | null) => {
                if (value === '' || value === null) return 'ユーザー名を入力してください。';
                if (/^.{2,}$/.test(value) === false) return 'ユーザー名は2文字以上で入力してください。';
                return true;
            },
            password: null as string | null,
            password_showing: false,
            password_validation: (value: string | null) => {
                if (value === '' || value === null) return 'パスワードを入力してください。';
                // 正規表現の参考: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },
        }
    },
    methods: {
        async login() {

            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if ((this.$refs.login as any).validate() === false) return;

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
                this.$message.success('ログインしました。');
                await this.$router.replace({path: '/settings/account'});

            } catch (error) {

                // ログインに失敗
                if (axios.isAxiosError(error) && error.response && error.response.status === 401) {

                    console.log('Failed to login.');
                    console.log(error.response.data);

                    // エラーメッセージごとに Snackbar に表示
                    switch (error.response.data.detail) {
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

.login-container {
    border-radius: 11px;

    .login-button {
        border-radius: 7px;
        font-size: 18px;
        letter-spacing: 0px;
    }
}

</style>