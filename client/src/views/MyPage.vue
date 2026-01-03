<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <v-card class="settings-container d-flex px-5 py-5 mx-auto" elevation="0" width="100%" max-width="1000">
                <nav class="settings-navigation">
                    <h1 class="mt-2" style="font-size: 24px;">マイページ</h1>
                    <router-link v-ripple to="/settings/account" class="account mt-6">
                        <div class="account-wrapper">
                            <img class="account__icon" :src="userStore.user ? (userStore.user_icon_url ?? '') : '/assets/images/account-icon-default.png'">
                            <div class="account__info">
                                <div class="account__info-name">
                                    <span class="account__info-name-text">{{ userStore.user ? userStore.user.name : 'ログインしていません' }}</span>
                                    <span class="account__info-admin" v-if="userStore.user?.is_admin">管理者</span>
                                </div>
                                <span class="account__info-id">{{ userStore.user ? `User ID: ${userStore.user.id}` : 'Not logged in' }}</span>
                            </div>
                        </div>
                    </router-link>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/">
                        <Icon icon="fluent:settings-20-regular" width="26px" />
                        <span class="ml-4">設定</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button mt-3" to="/mylist/">
                        <Icon icon="ic:round-playlist-play" width="26px" />
                        <span class="ml-4">マイリスト</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/watched-history/">
                        <Icon icon="fluent:history-20-regular" width="26px" />
                        <span class="ml-4">視聴履歴</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button settings-navigation__button--version mt-3"
                        :class="{'settings-navigation__button--version-highlight': versionStore.is_update_available}"
                        href="https://github.com/tsukumijima/KonomiTV" target="_blank">
                        <Icon icon="fluent:info-20-regular" width="26px" />
                        <span class="ml-4">
                            version {{versionStore.client_version}}{{versionStore.is_update_available ? ' (Update Available)' : ''}}
                        </span>
                    </v-btn>
                </nav>
            </v-card>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { onMounted } from 'vue';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import useUserStore from '@/stores/UserStore';
import useVersionStore from '@/stores/VersionStore';

const userStore = useUserStore();
const versionStore = useVersionStore();

onMounted(async () => {
    await userStore.fetchUser();
    await versionStore.fetchServerVersion();
});

</script>
<style lang="scss" scoped>

.settings-container {
    background: rgb(var(--v-theme-background)) !important;
    width: 100%;
    min-width: 0;
    @include smartphone-horizontal {
        padding: 16px 20px !important;
    }
    @include smartphone-horizontal-short {
        padding: 16px 16px !important;
    }
    @include smartphone-vertical {
        padding: 16px 16px !important;
    }

    .settings-navigation {
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        width: 100%;
        transform: none !important;
        visibility: visible !important;

        .settings-navigation__button {
            justify-content: left !important;
            width: 100%;
            height: 54px;
            margin-bottom: 6px;
            border-radius: 6px;
            font-size: 16px;
            color: rgb(var(--v-theme-text)) !important;
            background: rgb(var(--v-theme-background-lighten-1)) !important;

            &--version {
                display: none;
                @include smartphone-vertical {
                    display: flex;
                }
                &-highlight {
                    color: rgb(var(--v-theme-secondary-lighten-1)) !important;
                }
            }
        }

        h1 {
            @include smartphone-horizontal {
                font-size: 22px !important;
            }
        }
    }
}

.account {
    display: flex;
    align-items: center;
    height: 130px;
    align-items: normal;
    flex-direction: column;
    height: auto;
    padding: 16px 12px;
    margin-bottom: 6px;
    border-radius: 6px;
    background: rgb(var(--v-theme-background-lighten-1));

    &-wrapper {
        display: flex;
        align-items: center;
        min-width: 0;
        height: 70px;
    }

    &__icon {
        flex-shrink: 0;
        min-width: 70px;
        height: 100%;
        border-radius: 50%;
        object-fit: cover;
        // 読み込まれるまでのアイコンの背景
        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
        // 低解像度で表示する画像がぼやけないようにする
        // ref: https://sho-log.com/chrome-image-blurred/
        image-rendering: -webkit-optimize-contrast;
    }

    &__info {
        display: flex;
        flex-direction: column;
        min-width: 0;
        margin-left: 12px;
        margin-right: 0px;

        &-name {
            display: inline-flex;
            align-items: center;
            height: 33px;

            &-text {
                display: inline-block;
                font-size: 20px;
                color: rgb(var(--v-theme-text));
                font-weight: bold;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;  // はみ出た部分を … で省略
            }
        }

        &-admin {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
                width: 45px;
                height: 24px;
            margin-left: 10px;
            border-radius: 4px;
            background: rgb(var(--v-theme-secondary));
            font-size: 11.5px;
            font-weight: 500;
            line-height: 2;
        }

        &-id {
            display: inline-block;
            margin-top: 2px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 14.5px;
        }
    }
}

</style>