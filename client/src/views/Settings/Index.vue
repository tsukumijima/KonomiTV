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
                        <v-list-item link color="primary" class="px-4" to="/settings/caption">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:subtitles-16-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>字幕</v-list-item-title>
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
import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import useVersionStore from '@/store/VersionStore';

export default Vue.extend({
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