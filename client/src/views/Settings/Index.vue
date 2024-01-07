<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <v-card class="settings-container d-flex px-5 py-5 mx-auto bg-background" elevation="0" width="100%" max-width="1000">
                <nav class="settings-navigation">
                    <h1>設定</h1>
                    <v-btn variant="flat" class="settings-navigation__button mt-3" to="/settings/general">
                        <Icon icon="fa-solid:sliders-h" width="26px" style="padding: 0 3px;" />
                        <span class="ml-4">全般</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/quality">
                        <Icon icon="fluent:video-clip-multiple-16-filled" width="26px" />
                        <span class="ml-4">画質</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/caption">
                        <Icon icon="fluent:subtitles-16-filled" width="26px" />
                        <span class="ml-4">字幕</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/data-broadcasting">
                        <svg width="26px" height="26px" viewBox="0 0 512 512">
                            <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
                        </svg>
                        <span class="ml-4">データ放送</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/capture">
                        <Icon icon="fluent:image-multiple-16-filled" width="26px" />
                        <span class="ml-4">キャプチャ</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/account">
                        <Icon icon="fluent:person-20-filled" width="26px" />
                        <span class="ml-4">アカウント</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/jikkyo">
                        <Icon icon="bi:chat-left-text-fill" width="26px" style="padding: 0 2px;" />
                        <span class="ml-4">ニコニコ実況</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/twitter">
                        <Icon icon="fa-brands:twitter" width="26px" style="padding: 0 1px;" />
                        <span class="ml-4">Twitter</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button" to="/settings/server">
                        <Icon icon="fluent:server-surface-16-filled" width="26px" />
                        <span class="ml-4">サーバー設定</span>
                    </v-btn>
                    <v-btn variant="flat" class="settings-navigation__button settings-navigation__button--version"
                        :class="{'settings-navigation__button--version-highlight': versionStore.is_update_available}"
                        href="https://github.com/tsukumijima/KonomiTV">
                        <Icon icon="fluent:info-16-regular" width="26px" />
                        <span class="ml-4">
                            version {{versionStore.client_version}}{{versionStore.is_update_available ? ' (Update Available)' : ''}}
                        </span>
                    </v-btn>
                </nav>
            </v-card>
        </main>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import useVersionStore from '@/stores/VersionStore';

export default defineComponent({
    name: 'Settings-Index',
    components: {
        Header,
        Navigation,
    },
    computed: {
        ...mapStores(useVersionStore),
    },
    async created() {
        await this.versionStore.fetchServerVersion();
    }
});

</script>
<style lang="scss" scoped>

.settings-container {
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
                    color: rgb(var(--v-theme-secondary-lighten-1));
                }
            }
        }

        h1 {
            @include smartphone-horizontal {
                font-size: 22px !important;
            }
        }

        .v-navigation-drawer__content .v-list {
            @include smartphone-horizontal {
                margin-top: 12px !important;
                padding: 0 !important;
            }
        }

        .v-list-item--link, .v-list-item--link:before {
            background: rgb(var(--v-theme-background-lighten-1));
            border-radius: 6px !important;
            margin-top: 6px !important;
            margin-bottom: 0px !important;
        }
        .v-list-item--link {
            &:first-of-type {
                margin-top: 0 !important;
            }
        }
        .v-list-item__icon {
            margin: 14px 0 !important;
            margin-right: 16px !important;
        }
    }
}

</style>