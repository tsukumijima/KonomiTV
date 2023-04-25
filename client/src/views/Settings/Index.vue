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
                                <Icon icon="fluent:subtitles-16-regular" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>字幕</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4" to="/settings/capture">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:image-multiple-16-regular" width="26px" />
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
                        <v-list-item link color="primary" class="px-4" to="/settings/environment">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:toolbox-20-filled" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>環境設定</v-list-item-title>
                            </v-list-item-content>
                        </v-list-item>
                        <v-list-item link color="primary" class="px-4 settings-navigation-version" href="https://github.com/tsukumijima/KonomiTV"
                            :class="{'settings-navigation-version--highlight': is_update_available}">
                            <v-list-item-icon class="mr-4">
                                <Icon icon="fluent:info-16-regular" width="26px" />
                            </v-list-item-icon>
                            <v-list-item-content>
                                <v-list-item-title>
                                    version {{Utils.version}}{{is_update_available ? ' (Update Available)' : ''}}
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

import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import Version from '@/services/Version';
import Utils from '@/utils';

export default Vue.extend({
    name: 'Settings-Index',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,

            // 最新のバージョン
            latest_version: null as string | null,

            // アップデートが利用可能か
            is_update_available: false as boolean,
        };
    },
    async created() {
        try {

            // バージョン情報を取得
            const version_info = await Version.fetchServerVersion();
            if (version_info === null) {
                return;
            }

            this.latest_version = version_info.latest_version;

            // 最新のサーバーバージョンが取得できなかった場合は中断
            if (this.latest_version === null) {
                return;
            }

            // もし現在のサーバーバージョン (-dev を除く) と最新のサーバーバージョンが異なるなら、アップデートが利用できる旨を表示する
            // 現在のサーバーバージョンが -dev 付きで、かつ最新のサーバーバージョンが -dev なし の場合 (リリース版がリリースされたとき) も同様に表示する
            // つまり開発版だと同じバージョンのリリース版がリリースされたときにしかアップデート通知が表示されない事になるが、ひとまずこれで…
            if ((version_info.version.includes('-dev') === false && version_info.version !== version_info.latest_version) ||
                (version_info.version.includes('-dev') === true && version_info.version.replace('-dev', '') === version_info.latest_version)) {
                this.is_update_available = true;
            }

        } catch (error) {
            throw new Error(error);  // エラー内容をコンソールに表示して終了
        }
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