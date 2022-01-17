<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <v-card class="settings-container d-flex px-5 mx-auto background" elevation="0" width="100%" max-width="1000">
                <v-navigation-drawer permanent class="settings-navigation flex-shrink-0 py-5 background" width="195" height="100%">
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
                <v-card class="settings my-5 ml-5 px-7 py-7 background lighten-1" width="100%">
                    <h2 class="settings__heading">
                        <Icon icon="fa-solid:sliders-h" width="18px" />
                        <span class="ml-3">全般</span>
                    </h2>
                    <div class="settings__content">
                        <div class="settings__item">
                            <div class="settings__item-heading">既定のパネルの表示状態</div>
                            <div class="settings__item-label">視聴画面右側のパネルを既定でどう表示するかを設定します。</div>
                            <v-select class="settings__item-form" outlined hide-details
                                :items="panel_display_state" v-model="settings.panel_display_state"></v-select>
                        </div>
                    </div>
                </v-card>
            </v-card>
        </main>
    </div>
</template>
<script lang="ts">

import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import Utility from '@/utility';

export default Vue.extend({
    name: 'Home',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {

            // 既定のパネルの表示状態
            panel_display_state: [
                {'text': '常に表示する', 'value': 'always_display'},
                {'text': '常に折りたたむ', 'value': 'always_fold'},
                {'text': '前回の状態を復元する', 'value': 'restore_previous_state'},
            ],

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: {
                panel_display_state: Utility.getSettingsItem('panel_display_state'),
            }
        }
    },
    watch: {
        // settings オブジェクトのすべての変更を監視し、変更された際に保存する
        settings: {
            deep: true,
            handler() {
                for (const [setting_key, setting_value] of Object.entries(this.settings)) {
                    Utility.setSettingsItem(setting_key, setting_value);
                }
            }
        }
    }
});

</script>
<style lang="scss" scoped>

.settings-container {
    width: 100%;

    .settings-navigation {
        .v-list-item--link:before {
            border-radius: 11px !important;
        }
    }

    .settings {
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
                margin-top: 20px;

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