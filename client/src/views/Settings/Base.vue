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
                        <v-list nav class="mt-3 px-0 py-0">
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/general">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="fa-solid:sliders-h" width="26px" style="padding: 0 3px;" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>全般</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/caption">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="fluent:subtitles-16-filled" width="26px" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>字幕</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/data-broadcasting">
                                <v-list-item-icon class="mr-4">
                                    <svg width="26px" height="26px" viewBox="0 0 512 512">
                                        <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
                                    </svg>
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>データ放送</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/capture">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="fluent:image-multiple-16-filled" width="26px" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>キャプチャ</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/account">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="fluent:person-20-filled" width="26px" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>アカウント</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/jikkyo">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="bi:chat-left-text-fill" width="26px" style="padding: 0 2px;" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>ニコニコ実況</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/twitter">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="fa-brands:twitter" width="26px" style="padding: 0 1px;" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>Twitter</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                            <v-list-item link color="primary" class="px-4 mb-1" to="/settings/server">
                                <v-list-item-icon class="mr-4">
                                    <Icon icon="fluent:server-surface-16-filled" width="26px" />
                                </v-list-item-icon>
                                <v-list-item-content>
                                    <v-list-item-title>サーバー設定</v-list-item-title>
                                </v-list-item-content>
                            </v-list-item>
                        </v-list>
                    </v-navigation-drawer>
                </div>
                <v-card class="settings ml-5 px-7 py-7 lighten-1" width="100%">
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
    name: 'Settings-Base',
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
    @include smartphone-vertical {
        padding: 0px 0px !important;
    }

    .settings-navigation {
        position: sticky;
        top: calc(65px + 20px) !important;  // ヘッダー+余白の高さ

        // タブレット縦画面・スマホ横画面・スマホ縦画面では表示しない
        @include tablet-vertical {
            display: none;
        }
        @include smartphone-horizontal {
            display: none;
        }
        @include smartphone-vertical {
            display: none;
        }

        .v-list-item--link, .v-list-item--link:before {
            border-radius: 11px !important;
        }
    }

    // ::deep() で子コンポーネント（それぞれの設定画面）にも CSS が効くようにする
    // ref: https://qiita.com/buntafujikawa/items/b1703a2a4344fd326fe0
    .settings :deep() {
        width: 100%;
        min-width: 0;
        border-radius: 11px !important;
        background-color: var(--v-background-lighten1);
        @include tablet-vertical {
            margin-left: 0 !important;
            padding-top: 20px !important;
            padding-left: 20px !important;
            padding-right: 20px !important;
        }
        @include smartphone-horizontal {
            padding: 20px !important;
            margin-left: 0 !important;
        }
        @include smartphone-vertical {
            margin-left: 0 !important;
        }
        @include smartphone-vertical {
            padding-top: 60px !important;
            padding-left: 16px !important;
            padding-right: 16px !important;
            border-radius: 0 !important;
            background-color: var(--v-background-base);
        }

        .settings__heading {
            display: flex;
            align-items: center;
            font-size: 22px;
            @include smartphone-horizontal {
                font-size: 20px;
            }
            @include smartphone-vertical {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 60px;
                padding: 16px;
                border-radius: 0;
                background: var(--v-background-lighten1);
                box-shadow: 0px 3px 14px 2px rgb(0 0 0 / 12%);
                z-index: 5;
            }

            .settings__back-button {
                display: none;
                position: relative;
                left: -6px;
                padding: 6px;
                border-radius: 50%;
                color: var(--v-text-base);
                @include tablet-vertical {
                    display: flex;
                }
                @include smartphone-horizontal {
                    display: flex;
                }
                @include smartphone-vertical {
                    display: flex;
                }
            }

            .settings__back-button + svg {
                @include tablet-vertical {
                    display: none;
                }
                @include smartphone-horizontal {
                    display: none;
                }
                @include smartphone-vertical {
                    display: none;
                }
            }

            .settings__back-button + svg + span {
                @include tablet-vertical {
                    margin-left: 0px !important;
                }
                @include smartphone-horizontal {
                    margin-left: 0px !important;
                }
                @include smartphone-vertical {
                    margin-left: 0px !important;
                }
            }
        }

        .settings__content {
            margin-top: 24px;
            @include smartphone-horizontal {
                margin-top: 16px;
            }

            .settings__item {
                display: flex;
                position: relative;
                flex-direction: column;
                margin-top: 24px;
                @include smartphone-horizontal {
                    margin-top: 16px;
                }

                &--sync-disabled {
                    .settings__item-heading {
                        padding-right: 8px;
                        &:after {
                            content: 'デバイス間同期無効';
                            display: flex;
                            align-items: center;
                            flex-shrink: 0;
                            position: relative;
                            right: -8px;
                            padding: 2px 4px;
                            margin-left: auto;
                            border-radius: 4px;
                            background: var(--v-background-lighten2);
                            font-size: 11px;
                        }
                    }
                }

                &--switch {
                    margin-right: 62px;

                    .settings__item-heading {
                        width: calc(100% + 62px);
                    }
                }

                &--disabled {
                    opacity: 0.5;
                }

                &-heading {
                    display: flex;
                    align-items: center;
                    color: var(--v-text-base);
                    font-size: 16.5px;
                    @include smartphone-horizontal {
                        font-size: 15px;
                    }
                }
                &-label {
                    margin-top: 8px;
                    color: var(--v-text-darken1);
                    font-size: 13.5px;
                    line-height: 1.6;
                    @include smartphone-horizontal {
                        font-size: 11px;
                        line-height: 1.7;
                    }
                }
                &-form {
                    margin-top: 14px;
                    @include smartphone-horizontal {
                        font-size: 13.5px;
                    }
                }
                &-switch {
                    align-items: center;
                    position: absolute;
                    top: 0;
                    right: -74px;
                    bottom: 0;
                    margin-top: 0;
                }

                p {
                    margin-bottom: 8px;
                    &:last-of-type {
                        margin-bottom: 0px;
                    }
                }
            }

            .settings__save-button {
                height: 45px;
                background: var(--v-background-lighten2);
                font-size: 15.5px;
                letter-spacing: 0;
                @include smartphone-horizontal {
                    height: 40px;
                    padding: 0 12px;
                    font-size: 14px;
                }
            }
        }
    }
}

</style>