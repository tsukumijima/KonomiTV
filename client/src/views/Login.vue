<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="login-container-wrapper d-flex align-center w-100 mb-13">
                <v-card class="login-container px-10 pt-8 pb-11 mx-auto background-lighten-1" elevation="10"
                    width="100%" max-width="450">
                    <v-card-title class="login__logo flex-column justify-center">
                        <v-img max-width="250" src="/assets/images/logo.svg"></v-img>
                        <h4 class="mt-10">ログイン</h4>
                    </v-card-title>
                    <v-divider></v-divider>
                    <v-form ref="login" @submit.prevent>
                        <v-text-field class="mt-12" variant="outlined" placeholder="ユーザー名" hide-details autofocus
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="username">
                        </v-text-field>
                        <v-text-field class="mt-8" variant="outlined" placeholder="パスワード" hide-details
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="password"
                            :type="password_showing ? 'text' : 'password'"
                            :append-icon="password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                            @click:append="password_showing = !password_showing">
                        </v-text-field>
                        <v-btn class="login-button mt-5" color="secondary" variant="flat" width="100%" height="56"
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

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import Message from '@/message';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

export default defineComponent({
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
        };
    },
    computed: {
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
        async login() {

            // ユーザー名またはパスワードが空
            if (this.username === '' || this.password === '') {
                Message.error('ユーザー名またはパスワードが空です。');
                return;
            }

            // ログイン処理 (エラーハンドリング含む) を実行
            const result = await this.userStore.login(this.username, this.password);
            if (result === false) {
                return;  // ログイン失敗
            }

            // アカウントページに遷移
            // ブラウザバックでログインページに戻れないようにする
            await this.$router.replace({path: '/settings/account'});
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