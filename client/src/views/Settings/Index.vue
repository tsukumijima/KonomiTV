<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <v-card class="settings-container d-flex px-5 py-5 mx-auto background" elevation="0" width="100%" max-width="1000">
                <v-navigation-drawer permanent class="settings-navigation flex-shrink-0 background" width="100%" height="auto">
                    <v-list-item class="px-1">
                        <v-list-item-content>
                            <h1>設定</h1>
                        </v-list-item-content>
                    </v-list-item>
                    <v-list nav class="mt-2 px-0">
                        <v-list-item link color="primary" class="px-4" to="/settings/general">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fa-solid:sliders-h" width="26px" style="padding: 0 3px;" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>全般</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/quality">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:video-clip-multiple-16-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>画質</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/caption">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:subtitles-16-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>字幕</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/data-broadcasting">
                            <v-list-item-icon class="mr-4">
                                <svg width="26px" height="26px" viewBox="0 0 512 512">
                                    <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
                                </svg>
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>データ放送</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/capture">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:image-multiple-16-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>キャプチャ</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/account">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:person-20-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>アカウント</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/jikkyo">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="bi:chat-left-text-fill" width="26px" style="padding: 0 2px;" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>ニコニコ実況</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/twitter">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fa-brands:twitter" width="26px" style="padding: 0 1px;" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>Twitter</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/server">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:server-surface-16-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>サーバー設定</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4 settings-navigation-version" href="https://github.com/tsukumijima/KonomiTV"
                            :class="{'settings-navigation-version--highlight': versionStore.is_update_available}">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:info-16-regular" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>
                                    version {{versionStore.client_version}}{{versionStore.is_update_available ? ' (Update Available)' : ''}}
                                </v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                    </v-list>
                </v-navigation-drawer>
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
        transform: none !important;
        visibility: visible !important;

        .settings-navigation-version {
            display: none;
            @include smartphone-vertical {
                display: flex;
            }
            &--highlight {
                color: var(--v-secondary-lighten1);
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
            background: var(--v-background-lighten1);
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