<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="fluent:person-20-filled" width="24px" />
            <span class="ml-2">アカウント</span>
        </h2>
        <div class="settings__content">
            <div class="account">
                <img class="account__icon" src="/assets/images/account-icon-default.png">
                <div class="account__info">
                    <span class="account__info-name">ログインしていません</span>
                    <span class="account__info-id">Not Login</span>
                </div>
                <v-btn class="account__login ml-auto" color="secondary" width="140" height="60" depressed to="/login/">
                    <Icon icon="fa:sign-in" class="mr-2" />ログイン
                </v-btn>
            </div>
            <div class="account-register">
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

import Vue from 'vue';

import Base from '@/views/Settings/Base.vue';
import Utils from '@/utils';

export default Vue.extend({
    name: 'SettingsAccount',
    components: {
        Base,
    },
    data() {
        return {

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: (() => {
                // 設定の既定値を取得する
                const settings = {}
                for (const setting of []) {
                    settings[setting] = Utils.getSettingsItem(setting);
                }
                return settings;
            })(),
        }
    },
    watch: {
        // settings 内の値の変更を監視する
        settings: {
            deep: true,
            handler() {
                // settings 内の値を順に LocalStorage に保存する
                for (const [setting_key, setting_value] of Object.entries(this.settings)) {
                    Utils.setSettingsItem(setting_key, setting_value);
                }
            }
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
        height: 100%;
        border-radius: 50%;
    }

    &__info {
        display: flex;
        flex-direction: column;
        margin-left: 20px;

        &-name {
            display: inline-block;
            color: var(--v-text-base);
            font-size: 22px;
            font-weight: bold;
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