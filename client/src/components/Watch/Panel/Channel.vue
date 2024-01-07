<template>
    <div class="channels-container channels-container--watch">
        <v-tabs-fix centered show-arrows class="channels-tab" v-model="tab">
            <v-tab class="channels-tab__item"
                v-for="[channels_type,] in Array.from(channelsStore.channels_list_with_pinned_for_watch)" :key="channels_type">
                {{channels_type}}
            </v-tab>
        </v-tabs-fix>
        <div class="channels-list-container">
            <v-tabs-items-fix class="channels-list" v-model="tab">
                <v-tab-item-fix class="channels"
                    v-for="[channels_type, channels] in Array.from(channelsStore.channels_list_with_pinned_for_watch)" :key="channels_type">
                    <router-link v-ripple class="channel" v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.display_channel_id}`">
                        <!-- 以下では Icon コンポーネントを使うとチャンネルが多いときに高負荷になるため、意図的に SVG を直書きしている -->
                        <div class="channel__broadcaster">
                            <img class="channel__broadcaster-icon" :src="`${Utils.api_base_url}/channels/${channel.id}/logo`">
                            <div class="channel__broadcaster-content">
                                <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.name}}</span>
                                <div class="channel__broadcaster-force"
                                    :class="`channel__broadcaster-force--${ChannelUtils.getChannelForceType(channel.jikkyo_force)}`">
                                    <svg class="iconify iconify--fa-solid" width="9.63px" height="11px" viewBox="0 0 448 512">
                                        <path fill="currentColor" d="M323.56 51.2c-20.8 19.3-39.58 39.59-56.22 59.97C240.08 73.62 206.28 35.53 168 0C69.74 91.17 0 209.96 0 281.6C0 408.85 100.29 512 224 512s224-103.15 224-230.4c0-53.27-51.98-163.14-124.44-230.4zm-19.47 340.65C282.43 407.01 255.72 416 226.86 416C154.71 416 96 368.26 96 290.75c0-38.61 24.31-72.63 72.79-130.75c6.93 7.98 98.83 125.34 98.83 125.34l58.63-66.88c4.14 6.85 7.91 13.55 11.27 19.97c27.35 52.19 15.81 118.97-33.43 153.42z"></path>
                                    </svg>
                                    <span class="ml-1">{{channel.jikkyo_force ?? '--'}}</span>
                                </div>
                            </div>
                        </div>
                        <div class="channel__program-present">
                            <span class="channel__program-present-title"
                                v-html="ProgramUtils.decorateProgramInfo(channel.program_present, 'title')">
                            </span>
                            <span class="channel__program-present-time">{{ProgramUtils.getProgramTime(channel.program_present)}}</span>
                        </div>
                        <div class="channel__program-following">
                            <div class="channel__program-following-title">
                                <span class="channel__program-following-title-decorate">NEXT</span>
                                <svg class="channel__program-following-title-icon iconify iconify--fluent" width="16px" height="16px" viewBox="0 0 20 20">
                                    <path fill="currentColor" d="M10.018 5.486a1 1 0 0 1 1.592-.806l5.88 4.311a1.25 1.25 0 0 1 0 2.017l-5.88 4.311a1 1 0 0 1-1.592-.806v-3.16L4.61 15.319a1 1 0 0 1-1.592-.806V5.486A1 1 0 0 1 4.61 4.68l5.408 3.966v-3.16Z"></path>
                                </svg>
                                <span class="channel__program-following-title-text"
                                    v-html="ProgramUtils.decorateProgramInfo(channel.program_following, 'title')">
                                </span>
                            </div>
                            <span class="channel__program-following-time">{{ProgramUtils.getProgramTime(channel.program_following)}}</span>
                        </div>
                        <div class="channel__progressbar">
                            <div class="channel__progressbar-progress"
                                 :style="`width:${ProgramUtils.getProgramProgress(channel.program_present)}%;`"></div>
                        </div>
                    </router-link>
                </v-tab-item-fix>
            </v-tabs-items-fix>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import useChannelsStore from '@/stores/ChannelsStore';
import Utils, { ChannelUtils, ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'Panel-ChannelTab',
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            ChannelUtils: Object.freeze(ChannelUtils),
            ProgramUtils: Object.freeze(ProgramUtils),

            // タブの状態管理
            tab: null as number | null,
        };
    },
    computed: {
        ...mapStores(useChannelsStore),
    }
});

</script>
<style lang="scss">

// 上書きしたいスタイル
.channels-container.channels-container--watch {
    .v-tabs-bar {
        // スペースが少ないので高さを抑える
        height: 42px;
        // 下線を引く
        background: linear-gradient(to bottom, rgb(var(--v-theme-background)) calc(100% - 3px), rgb(var(--v-theme-background-lighten-1)) 3px);
        @include tablet-vertical {
            height: 50px;
        }
        @include smartphone-horizontal {
            height: 44px;
        }
        @include smartphone-vertical {
            height: 46px;
        }

        // 幅を縮める
        .v-slide-group__prev, .v-slide-group__next {
            flex: auto !important;
            min-width: 28px !important;
        }
    }
    .v-tabs-slider-wrapper {
        height: 3px !important;
        transition: left 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
    }
}

</style>
<style lang="scss" scoped>

.channels-container {
    display: flex;
    flex-direction: column;

    .channels-tab {
        position: sticky;
        flex: none;
        top: 0px;
        padding-left: 16px;
        padding-right: 16px;
        padding-bottom: 14px;
        background: rgb(var(--v-theme-background));
        z-index: 1;
        @include tablet-vertical {
            padding-left: 24px;
            padding-right: 24px;
            padding-bottom: 10px;
        }
        @include smartphone-horizontal {
            padding-bottom: 8px;
            margin-top: 0px;
        }
        @include smartphone-vertical {
            padding-bottom: 8px;
            margin-top: 0px;
        }

        .channels-tab__item {
            min-width: 72px !important;
            padding: 0 8px;
            color: rgb(var(--v-theme-text)) !important;
            font-size: 15px;
            text-transform: none;
            @include smartphone-horizontal {
                font-size: 14.5px;
            }
        }
    }

    .channels-list-container {
        overflow-y: auto;

        .channels-list {
            padding-left: 16px;
            padding-right: 10px;
            padding-bottom: 16px;
            background: transparent !important;
            overflow: visible !important;
            @include tablet-vertical {
                padding-left: 24px;
                padding-right: 24px;
            }
            @include smartphone-horizontal {
                padding-bottom: 12px;
            }

            .channels {
                display: flex;
                justify-content: center;
                flex-direction: column;
                // will-change を入れておく事で、アニメーションが GPU で処理される
                will-change: transform;

                // チャンネルリストでの content-visibility: auto; はちょっと描画上の副作用もあるので、
                // パフォーマンス向上が顕著なスマホ・タブレット (タッチデバイス) のみに適用する
                @media (hover: none) {
                    content-visibility: auto;
                    contain-intrinsic-size: 319.3px 2000px;  // だいたい 2000px 分の高さを確保
                    @include smartphone-horizontal {
                        contain-intrinsic-size: 277.3px 2000px;
                    }
                }

                // 1630px 以上で幅を 445px に固定
                @media (min-width: 1630px) {
                    grid-template-columns: repeat(auto-fit, 445px);
                }

                .channel {
                    display: flex;
                    flex-direction: column;
                    position: relative;
                    margin-top: 12px;
                    padding: 10px 12px 14px 12px;
                    border-radius: 10px;
                    color: rgb(var(--v-theme-text));
                    background: rgb(var(--v-theme-background-lighten-1));
                    transition: background-color 0.15s;
                    overflow: hidden;  // progressbar を切り抜くために必要
                    text-decoration: none;
                    user-select: none;
                    cursor: pointer;
                    // content-visibility: auto; を付与するだけでスマホでの描画パフォーマンスが大幅に向上する
                    content-visibility: auto;
                    contain-intrinsic-size: 295.3px 137.3px;

                    &:first-of-type {
                        margin-top: 0px;
                    }
                    @include smartphone-horizontal {
                        margin-top: 8px;
                        padding: 8px 12px 12px 12px;
                        border-radius: 8px;
                        contain-intrinsic-size: 253.3px 107.2px;
                    }
                    @include smartphone-vertical {
                        margin-top: 8px;
                        padding: 8px 12px 12px 12px;
                        border-radius: 8px;
                        contain-intrinsic-size: 253.3px 107.2px;
                    }

                    &:hover {
                        background: rgb(var(--v-theme-background-lighten-2));
                    }
                    // タッチデバイスで hover を無効にする
                    @media (hover: none) {
                        &:hover {
                            background: rgb(var(--v-theme-background-lighten-1));
                        }
                    }

                    .channel__broadcaster {
                        display: flex;
                        height: 28px;
                        @include smartphone-horizontal {
                            height: 24px;
                        }

                        &-icon {
                            display: inline-block;
                            flex-shrink: 0;
                            width: 48px;
                            height: 100%;
                            border-radius: 4px;
                            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                            object-fit: cover;
                            @include smartphone-horizontal {
                                width: 46px;
                            }
                        }

                        &-content {
                            display: flex;
                            align-items: center;
                            margin-left: 12px;
                            width: 100%;
                            min-width: 0;
                            @include smartphone-horizontal {
                                margin-left: 8px;
                            }
                        }

                        &-name {
                            font-size: 14.5px;
                            overflow: hidden;
                            white-space: nowrap;
                            text-overflow: ellipsis;
                            @include smartphone-horizontal {
                                font-size: 13.5px;
                            }
                            @include smartphone-vertical {
                                font-size: 13.5px;
                            }
                        }

                        &-force {
                            display: flex;
                            align-items: center;
                            flex-shrink: 0;
                            margin-top: 2px;
                            margin-left: auto;
                            padding-left: 6px;
                            font-size: 12px;
                            color: rgb(var(--v-theme-text-darken-1));

                            &--festival {
                                color: #E7556E;
                            }
                            &--so-many {
                                color: #E76B55;
                            }
                            &--many {
                                color: #E7A355;
                            }
                        }
                    }

                    .channel__program-present {
                        display: flex;
                        flex-direction: column;

                        &-title {
                            display: -webkit-box;
                            margin-top: 8px;
                            font-size: 13.5px;
                            font-weight: 700;
                            font-feature-settings: "palt" 1;  // 文字詰め
                            letter-spacing: 0.07em;  // 字間を少し空ける
                            overflow: hidden;
                            -webkit-line-clamp: 2;  // 2行までに制限
                            -webkit-box-orient: vertical;
                            @include smartphone-horizontal {
                                margin-top: 5px;
                                font-size: 12.5px;
                                -webkit-line-clamp: 1;  // 1行までに制限
                            }
                            @include smartphone-vertical {
                                margin-top: 5px;
                                font-size: 12.5px;
                                -webkit-line-clamp: 1;  // 1行までに制限
                            }
                        }

                        &-time {
                            margin-top: 4px;
                            color: rgb(var(--v-theme-text-darken-1));
                            font-size: 11.5px;
                            @include smartphone-horizontal {
                                margin-top: 1px;
                                font-size: 10px;
                            }
                            @include smartphone-vertical {
                                margin-top: 1px;
                                font-size: 10px;
                            }
                        }
                    }

                    .channel__program-following {
                        display: flex;
                        flex-direction: column;
                        margin-top: 4px;
                        color: rgb(var(--v-theme-text-darken-1));
                        font-size: 11.5px;
                        @include smartphone-horizontal {
                            margin-top: 2px;
                        }
                        @include smartphone-vertical {
                            margin-top: 2px;
                        }

                        &-title {
                            display: flex;
                            align-items: center;

                            &-decorate {
                                flex-shrink: 0;
                            }
                            &-icon {
                                flex-shrink: 0;
                                margin-left: 3px;
                            }
                            &-text {
                                margin-left: 2px;
                                overflow: hidden;
                                white-space: nowrap;
                                text-overflow: ellipsis;  // はみ出た部分を … で省略
                            }
                        }

                        &-time {
                            margin-top: 1px;
                            @include smartphone-horizontal {
                                font-size: 10px;
                            }
                            @include smartphone-vertical {
                                font-size: 10px;
                            }
                        }
                    }

                    .channel__progressbar {
                        position: absolute;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        height: 4px;
                        background: rgb(var(--v-theme-gray));

                        &-progress {
                            height: 4px;
                            background: rgb(var(--v-theme-primary));
                            transition: width 0.3s;
                        }
                    }
                }
            }
        }
    }
}

</style>