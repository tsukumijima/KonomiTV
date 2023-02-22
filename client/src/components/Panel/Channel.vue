<template>
    <div class="channels-container channels-container--watch">
        <v-tabs-fix centered show-arrows class="channels-tab" v-model="tab">
            <v-tab class="channels-tab__item" v-for="[channels_type,] in Array.from(channels_list)" :key="channels_type">
                {{channels_type}}
            </v-tab>
        </v-tabs-fix>
        <div class="channels-list-container">
            <v-tabs-items-fix class="channels-list" v-model="tab">
                <v-tab-item-fix class="channels" v-for="[channels_type, channels] in Array.from(channels_list)" :key="channels_type">
                    <router-link v-ripple class="channel" v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.channel_id}`">
                        <div class="channel__broadcaster">
                            <img class="channel__broadcaster-icon" :src="`${Utils.api_base_url}/channels/${channel.channel_id}/logo`">
                            <div class="channel__broadcaster-content">
                                <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.channel_name}}</span>
                                <div class="channel__broadcaster-force"
                                    :class="`channel__broadcaster-force--${ChannelUtils.getChannelForceType(channel.channel_force)}`">
                                    <Icon icon="fa-solid:fire-alt" height="11px" />
                                    <span class="ml-1">{{ProgramUtils.getAttribute(channel, 'channel_force', '-')}}</span>
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
                                <Icon class="channel__program-following-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
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

import Vue, { PropType } from 'vue';

import { ChannelTypePretty, IChannel } from '@/interface';
import Utils, { ChannelUtils, ProgramUtils } from '@/utils';

export default Vue.extend({
    name: 'Panel-ChannelTab',
    props: {
        // チャンネル情報リスト
        channels_list: {
            type: Map as PropType<Map<ChannelTypePretty, IChannel[]>>,
            required: true,
        }
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ChannelUtils: ChannelUtils,
            ProgramUtils: ProgramUtils,

            // タブの状態管理
            tab: null,
        }
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
        background: linear-gradient(to bottom, var(--v-background-base) calc(100% - 3px), var(--v-background-lighten1) 3px);
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
        background:var(--v-background-base);
        z-index: 1;
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
            color: var(--v-text-base) !important;
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
                    color: var(--v-text-base);
                    background: var(--v-background-lighten1);
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
                        background: var(--v-background-lighten2);
                    }
                    // タッチデバイスで hover を無効にする
                    @media (hover: none) {
                        &:hover {
                            background: var(--v-background-lighten1);
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
                            background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
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
                            color: var(--v-text-darken1);

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
                                -webkit-line-clamp: 1;  // 2行までに制限
                            }
                            @include smartphone-vertical {
                                margin-top: 5px;
                                font-size: 12.5px;
                                -webkit-line-clamp: 1;  // 2行までに制限
                            }
                        }

                        &-time {
                            margin-top: 4px;
                            color: var(--v-text-darken1);
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
                        color: var(--v-text-darken1);
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
                        background: var(--v-gray-base);

                        &-progress {
                            height: 4px;
                            background: var(--v-primary-base);
                            transition: width 0.3s;
                        }
                    }
                }
            }
        }
    }
}

</style>