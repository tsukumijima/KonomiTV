<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <v-card class="settings-container d-flex px-5 py-5 mx-auto background" elevation="0" width="100%" max-width="1000">
                <v-navigation-drawer permanent class="settings-navigation flex-shrink-0 background" width="100%" height="auto">
                    <v-list-item class="px-4">
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
                        <v-divider></v-divider>
                        <v-list-item link color="primary" class="px-4" to="/settings/account">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:person-20-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>アカウント</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider></v-divider>
                        <v-list-item link color="primary" class="px-4" to="/settings/jikkyo">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="bi:chat-left-text-fill" width="26px" style="padding: 0 2px;" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>ニコニコ実況</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider></v-divider>
                        <v-list-item link color="primary" class="px-4" to="/settings/twitter">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fa-brands:twitter" width="26px" style="padding: 0 1px;" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>Twitter</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-divider></v-divider>
                        <v-list-item link color="primary" class="px-4" to="/settings/environment">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:toolbox-20-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>環境設定</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                    </v-list>
                </v-navigation-drawer>
            </v-card>
        </main>
    </div>
</template>
<script lang="ts">

import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

export default Vue.extend({
    name: 'Settings-Index',
    components: {
        Header,
        Navigation,
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

    .settings-navigation {

        h1 {
            @include smartphone-horizontal {
                font-size: 22px !important;
            }
        }

        .v-navigation-drawer__content .v-list {
            @include smartphone-horizontal {
                margin-top: 4px !important;
                padding: 0 !important;
            }
            @include smartphone-horizontal-short {
                margin-top: 0 !important;
            }
        }

        .v-list-item--link, .v-list-item--link:before {
            border-radius: 11px !important;
            margin-bottom: 0px !important;
        }
    }
}

</style>