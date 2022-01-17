<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <v-card class="settings-container d-flex px-5 py-5 mx-auto background" elevation="0" width="100%" max-width="1000">
                <div><!-- ← position: sticky; を効かせるためのボックス -->
                    <v-navigation-drawer permanent class="settings-navigation flex-shrink-0 background" width="195" height="auto">
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
                        </v-list>
                    </v-navigation-drawer>
                </div>
                <v-card class="settings ml-5 px-7 py-7 background lighten-1" width="100%">
                    <!-- この slot にそれぞれの設定画面の内容が入る -->
                    <slot></slot>
                </v-card>
            </v-card>
        </main>
    </div>
</template>
<script lang="ts">

import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

// 設定のベース画面なので、ロジックは基本置かない
export default Vue.extend({
    name: 'Home',
    components: {
        Header,
        Navigation,
    }
});

</script>
<style lang="scss" scoped>

.settings-container {
    width: 100%;

    .settings-navigation {
        position: sticky;
        top: calc(65px + 20px) !important;  // ヘッダー+余白の高さ

        .v-list-item--link:before {
            border-radius: 11px !important;
        }
    }

    // ::v-deep で子コンポーネント（それぞれの設定画面）にも CSS が効くようにする
    // ref: https://qiita.com/buntafujikawa/items/b1703a2a4344fd326fe0
    .settings ::v-deep {
        width: 100%;
        border-radius: 11px !important;

        .settings__heading {
            display: flex;
            align-items: center;
            font-size: 22px;
        }

        .settings__content {
            margin-top: 24px;

            .settings__item {
                display: flex;
                flex-direction: column;
                margin-top: 24px;

                &-heading {
                    color: var(--v-text-base);
                    font-size: 16.5px;
                }
                &-label {
                    margin-top: 4px;
                    color: var(--v-text-darken1);
                    font-size: 13.5px;
                }
                &-form {
                    margin-top: 12px;
                }
            }
        }
    }
}

</style>