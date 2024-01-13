<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="register-container-wrapper d-flex align-center w-100 mb-13">
                <v-card class="register-container px-10 pt-8 pb-11 mx-auto" elevation="10"
                    width="100%" max-width="450">
                    <v-card-title class="register__logo py-4 d-flex flex-column justify-center align-center">
                        <img class="d-block" src="/assets/images/logo.svg" style="max-width: 250px;" />
                        <h4 class="mt-10">アカウントを作成</h4>
                    </v-card-title>
                    <v-divider></v-divider>
                    <v-form ref="register" @submit.prevent>
                        <v-text-field class="mt-12" color="primary" variant="outlined"
                            placeholder="ユーザー名" autofocus
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="username"
                            :rules="[username_validation]">
                        </v-text-field>
                        <v-text-field style="margin-top: 10px;" color="primary" variant="outlined"
                            placeholder="パスワード"
                            :density="is_form_dense ? 'compact' : 'default'"
                            v-model="password"
                            :type="password_showing ? 'text' : 'password'"
                            :rules="[password_validation]"
                            :append-inner-icon="password_showing ? 'mdi-eye' : 'mdi-eye-off'"
                            @click:appendInner="password_showing = !password_showing">
                        </v-text-field>
                        <v-btn class="register-button mt-5" color="secondary" variant="flat" width="100%" height="56"
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
import { defineComponent } from 'vue';
import { VForm } from 'vuetify/components';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';

export default defineComponent({
    name: 'Register',
    components: {
        HeaderBar,
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
                // ref: https://qiita.com/grrrr/items/0b35b5c1c98eebfa5128
                if (/^[a-zA-Z0-9!-/:-@¥[-`{-~]{4,}$/.test(value) === false) return 'パスワードは4文字以上の半角英数記号を入力してください。';
                return true;
            },
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
        async register() {

            // すべてのバリデーションが通過したときのみ
            // ref: https://qiita.com/Hijiri_Ishi/items/56cac99c8f3806a6fa24
            if ((await (this.$refs.register as VForm).validate()).valid === false) return;
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
        background: rgb(var(--v-theme-background-lighten-1)) !important;
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
                img {
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
                img {
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
                margin-top: 8px !important;
                font-size: 14px !important;
            }
            @include smartphone-vertical {
                margin-top: 10px !important;
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
            margin-top: 26px !important;
            font-size: 18px;
            letter-spacing: 0px;
            @include smartphone-horizontal {
                height: 44px !important;
                margin-top: 8px !important;
                font-size: 16px;
            }
            @include smartphone-vertical {
                height: 50px !important;
                margin-top: 10px !important;
                font-size: 15.5px;
            }
        }
    }
}


</style>