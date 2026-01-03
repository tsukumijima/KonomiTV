<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <div class="settings-container d-flex px-5 py-5 mx-auto" width="100%" max-width="1000">
                <nav class="settings-navigation">
                    <h1 class="mt-2 ml-4" style="font-size: 24px;">設定</h1>
                    <v-btn variant="flat" class="settings-navigation__button mt-6" to="/settings/general">
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
                </nav>
                <div class="settings ml-5 px-7 py-7" width="100%">
                    <!-- この slot にそれぞれの設定画面の内容が入る -->
                    <slot></slot>
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts">

import { defineComponent } from 'vue';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';

// 設定のベース画面なので、ロジックは基本置かない
export default defineComponent({
    name: 'Settings-Base',
    components: {
        HeaderBar,
        Navigation,
        SPHeaderBar,
    }
});

</script>
<style lang="scss" scoped>

.settings-container {
    background: rgb(var(--v-theme-background)) !important;
    width: 100%;
    min-width: 0;
    max-width: 1000px;
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
        display: flex;
        align-self: flex-start;
        flex-direction: column;
        flex-shrink: 0;
        width: 195px;
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

        .settings-navigation__button {
            justify-content: left !important;
            width: 100%;
            height: 58px;
            margin-bottom: 4px;
            border-radius: 11px;
            font-size: 16px;
            color: rgb(var(--v-theme-text)) !important;
            background: rgb(var(--v-theme-background)) !important;

            &.v-btn--active {
                color: rgb(var(--v-theme-primary)) !important;
            }
        }
    }

    // :deep() で子コンポーネント（それぞれの設定画面）にも CSS が効くようにする
    // ref: https://qiita.com/buntafujikawa/items/b1703a2a4344fd326fe0
    .settings :deep() {
        width: 100%;
        min-width: 0;
        border-radius: 11px !important;
        background-color: rgb(var(--v-theme-background-lighten-1)) !important;
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
            background-color: rgb(var(--v-theme-background)) !important;
        }

        .v-divider {
            opacity: 1 !important;
            border-top-width: 2px !important;
            border-color: rgb(var(--v-theme-background-lighten-2)) !important;
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
                background: rgb(var(--v-theme-background-lighten-1));
                box-shadow: 0px 3px 14px 2px rgb(0 0 0 / 12%);
                z-index: 5;
            }

            .settings__back-button {
                display: none;
                position: relative;
                left: -8px;
                padding: 6px;
                border-radius: 50%;
                color: rgb(var(--v-theme-text));
                cursor: pointer;
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
                    margin-left: -4px !important;
                }
                @include smartphone-horizontal {
                    margin-left: -4px !important;
                }
                @include smartphone-vertical {
                    margin-left: -4px !important;
                }
            }
        }

        .settings__description {
            margin-top: 16px;
            font-size: 13.5px;
            color: rgb(var(--v-theme-text-darken-1));
            line-height: 1.6;
            @include smartphone-horizontal {
                margin-top: 12px;
                font-size: 12px;
                line-height: 1.65;
            }
            @include smartphone-vertical {
                margin-top: 24px;
            }
        }

        .settings__content {
            margin-top: 24px;
            @include smartphone-horizontal {
                margin-top: 16px;
            }

            &--disabled {
                opacity: 0.65;
                pointer-events: none;
                cursor: default;
            }

            &-heading {
                display: flex;
                align-items: center;
                font-size: 18px;
                color: rgb(var(--v-theme-text-darken-1));
                padding-bottom: 10px;
                border-bottom: 2px solid rgb(var(--v-theme-background-lighten-2));
                @include smartphone-horizontal {
                    font-size: 16px;
                }
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
                            background: rgb(var(--v-theme-background-lighten-2));
                            font-size: 11px;
                        }
                    }
                }

                &--switch {
                    margin-right: 62px;
                    @include smartphone-vertical {
                        margin-right: 50px;
                    }

                    .settings__item-heading {
                        width: calc(100% + 62px);
                        @include smartphone-vertical {
                            width: calc(100% + 50px);
                        }
                    }

                    .settings__item-heading, .settings__item-label {
                        cursor: pointer;
                    }
                }

                &--disabled {
                    opacity: 0.5;
                }

                &-heading {
                    display: flex;
                    align-items: center;
                    color: rgb(var(--v-theme-text));
                    font-size: 16.5px;
                    @include smartphone-horizontal {
                        font-size: 15px;
                    }
                }
                &-label {
                    margin-top: 8px;
                    color: rgb(var(--v-theme-text-darken-1));
                    font-size: 13.5px;
                    line-height: 1.6;
                    @include smartphone-horizontal {
                        font-size: 12px;
                        line-height: 1.65;
                    }

                    // 設定項目の選択肢を箇条書きで表示するリスト
                    .settings__item-option-list {
                        margin: 0;
                        padding-left: 1.2em;
                        li {
                            margin-bottom: 4px;
                            &:last-child {
                                margin-bottom: 0;
                            }
                            strong {
                                color: rgb(var(--v-theme-text));
                            }
                        }
                    }

                    // 設定項目の補足情報を表示するノート
                    .settings__item-note {
                        margin-top: 6px;
                        margin-bottom: 0;
                        font-size: 12.5px;
                        opacity: 0.85;
                        @include smartphone-horizontal {
                            font-size: 11.5px;
                        }
                    }
                }
                &-form {
                    margin-top: 14px;
                    @include smartphone-horizontal {
                        font-size: 13.5px;
                    }
                }
                &-switch {
                    display: flex !important;
                    align-items: center;
                    position: absolute;
                    top: 0;
                    right: -60px;
                    bottom: 0px;
                    margin-top: 0;
                    @include smartphone-vertical {
                        right: -48px;
                    }
                }

                &-delete-button {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-shrink: 0;
                    width: 35px;
                    height: 40px;
                    margin-left: 4px;
                    border-radius: 5px;
                    outline: none;
                    cursor: pointer;
                }

                p {
                    margin-bottom: 8px;
                    &:last-of-type {
                        margin-bottom: 0px;
                    }
                }
            }

            .settings__save-button {
                max-width: 100%;
                height: 45px;
                background: rgb(var(--v-theme-background-lighten-2));
                font-size: 15.5px;
                letter-spacing: 0;
                @include smartphone-horizontal {
                    height: 40px;
                    padding: 0 12px;
                    font-size: 14px;
                }
                @include smartphone-vertical-short {
                    font-size: 14px;
                }
            }
        }

        .settings__quote {
            border-left: 3px solid rgb(var(--v-theme-text-darken-1));
            padding-left: 12px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 13.5px;
            line-height: 1.6;
        }
    }
}

</style>