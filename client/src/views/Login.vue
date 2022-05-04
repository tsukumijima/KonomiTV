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
                    <v-form ref="login">
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

import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

export default Vue.extend({
    name: 'Login',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {
            username: null,
            username_validation: (value: string | null) => {
                if (value === '') return 'ユーザー名を入力してください。';
                return true;
            },
            password: null,
            password_showing: false,
            password_validation: (value: string | null) => {
                if (value === '') return 'パスワードを入力してください。';
                // 正規表現の参考: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },
        }
    },
    methods: {
        login() {
            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if ((this.$refs.login as any).validate()) {
                console.log(this.username, this.password);
                // TODO
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