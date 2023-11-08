<template>
    <div class="watch-panel"
         @mousemove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})">
        <div class="watch-panel__header">
            <div v-ripple class="panel-close-button" @click="playerStore.is_panel_display = false">
                <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
                <span class="panel-close-button__text">閉じる</span>
            </div>
            <v-spacer></v-spacer>
            <div class="panel-broadcaster">
                <img class="panel-broadcaster__icon" :src="`${Utils.api_base_url}/channels/${(channelsStore.display_channel_id)}/logo`">
                <div class="panel-broadcaster__number">{{channelsStore.channel.current.channel_number}}</div>
                <div class="panel-broadcaster__name">{{channelsStore.channel.current.name}}</div>
            </div>
        </div>
        <div class="watch-panel__content-container">
            <Program class="watch-panel__content" v-if="playback_mode === 'Live'"
                :class="{'watch-panel__content--active': playerStore.tv_panel_active_tab === 'Program'}" />
            <Channel class="watch-panel__content" v-if="playback_mode === 'Live'"
                :class="{'watch-panel__content--active': playerStore.tv_panel_active_tab === 'Channel'}" />
            <Comment class="watch-panel__content" :playback_mode="playback_mode"
                :class="{'watch-panel__content--active': playerStore.tv_panel_active_tab === 'Comment'}" />
            <Twitter class="watch-panel__content" :playback_mode="playback_mode"
                :class="{'watch-panel__content--active': playerStore.tv_panel_active_tab === 'Twitter'}" />
            <button v-ripple class="watch-panel__content-remocon-button elevation-8" v-if="playback_mode === 'Live'"
                :class="{'watch-panel__content-remocon-button--active': playerStore.tv_panel_active_tab === 'Program' || playerStore.tv_panel_active_tab === 'Channel'}"
                @click="playerStore.is_remocon_display = !playerStore.is_remocon_display">
                <Icon class="panel-close-button__icon" icon="material-symbols:remote-gen" width="25px" />
            </button>
            <Remocon class="watch-panel__remocon" v-if="playback_mode === 'Live'"
                :modelValue="(playerStore.tv_panel_active_tab === 'Program' || playerStore.tv_panel_active_tab === 'Channel') && playerStore.is_remocon_display === true"
                @update:modelValue="playerStore.is_remocon_display = $event" />
        </div>
        <div class="watch-panel__navigation">
            <div v-ripple class="panel-navigation-button" v-if="playback_mode === 'Live'"
                 :class="{'panel-navigation-button--active': playerStore.tv_panel_active_tab === 'Program'}"
                 @click="playerStore.tv_panel_active_tab = 'Program'">
                <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                <span class="panel-navigation-button__text">番組情報</span>
            </div>
            <div v-ripple class="panel-navigation-button" v-if="playback_mode === 'Live'"
                 :class="{'panel-navigation-button--active': playerStore.tv_panel_active_tab === 'Channel'}"
                 @click="playerStore.tv_panel_active_tab = 'Channel'">
                <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                <span class="panel-navigation-button__text">チャンネル</span>
            </div>
            <div v-ripple class="panel-navigation-button"
                 :class="{'panel-navigation-button--active': playerStore.tv_panel_active_tab === 'Comment'}"
                 @click="playerStore.tv_panel_active_tab = 'Comment'">
                <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="29px" />
                <span class="panel-navigation-button__text">コメント</span>
            </div>
            <div v-ripple class="panel-navigation-button"
                 :class="{'panel-navigation-button--active': playerStore.tv_panel_active_tab === 'Twitter'}"
                 @click="playerStore.tv_panel_active_tab = 'Twitter'">
                <Icon class="panel-navigation-button__icon" icon="fa-brands:twitter" width="34px" />
                <span class="panel-navigation-button__text">Twitter</span>
            </div>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import Channel from '@/components/Watch/Panel/Channel.vue';
import Comment from '@/components/Watch/Panel/Comment.vue';
import Program from '@/components/Watch/Panel/Program.vue';
import Remocon from '@/components/Watch/Panel/Remocon.vue';
import Twitter from '@/components/Watch/Panel/Twitter.vue';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import Utils from '@/utils';

export default defineComponent({
    name: 'Watch-Panel',
    components: {
        Channel,
        Comment,
        Program,
        Remocon,
        Twitter,
    },
    props: {
        playback_mode: {
            type: String as PropType<'Live' | 'Video'>,
            required: true,
        },
    },
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore),
    }
});

</script>
<style lang="scss" scoped>

.watch-panel {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    width: 352px;
    height: 100%;
    background: var(--v-background-base);
    @include tablet-vertical {
        width: 100%;
        height: auto;
        flex-grow: 1;
    }
    @include smartphone-horizontal {
        width: 310px;
    }
    @include smartphone-vertical {
        width: 100%;
        height: auto;
        flex-grow: 1;
    }

    // タッチデバイスのみ、content-visibility: hidden でパネルを折り畳んでいるときの描画パフォーマンスを上げる
    @media (hover: none) {
        content-visibility: hidden;
    }

    .watch-panel__header {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        width: 100%;
        height: 70px;
        padding-left: 16px;
        padding-right: 16px;
        @include tablet-vertical {
            display: none;
        }
        @include smartphone-horizontal {
            display: none;
        }
        @include smartphone-vertical {
            display: none;
        }

        .panel-close-button {
            display: flex;
            position: relative;
            align-items: center;
            flex-shrink: 0;
            left: -4px;
            height: 35px;
            padding: 0 4px;
            border-radius: 5px;
            font-size: 16px;
            user-select: none;
            cursor: pointer;

            &__icon {
                position: relative;
                left: -4px;
            }
            &__text {
                font-weight: bold;
            }
        }

        .panel-broadcaster {
            display: flex;
            align-items: center;
            min-width: 0;
            margin-left: 16px;

            &__icon {
                display: inline-block;
                flex-shrink: 0;
                width: 43px;
                height: 24px;
                border-radius: 3px;
                background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                object-fit: cover;
                user-select: none;
            }

            &__number {
                flex-shrink: 0;
                margin-left: 8px;
                font-size: 16px;
            }

            &__name {
                margin-left: 5px;
                font-size: 16px;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
                @include smartphone-horizontal {
                    font-size: 14px;
                }
            }
        }
    }

    .watch-panel__content-container {
        position: relative;
        height: 100%;

        .watch-panel__content {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--v-background-base);
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;

            // スマホ・タブレット (タッチデバイス) ではアニメーションが重めなので、アニメーションを無効化
            // アクティブなタブ以外は明示的に描画しない
            @media (hover: none) {
                transition: none;
                content-visibility: hidden;
            }
            &--active {
                opacity: 1;
                visibility: visible;
                content-visibility: auto;
            }
        }

        .watch-panel__content-remocon-button {
            display: flex;
            align-items: center;
            justify-content: center;
            position: absolute;
            right: 16px;
            bottom: 16px;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: var(--v-background-lighten1);
            outline: none;
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;

            @media (hover: none) {
                transition: none;
            }
            &--active {
                opacity: 1;
                visibility: visible;
            }
        }
    }

    .watch-panel__navigation {
        display: flex;
        align-items: center;
        justify-content: space-evenly;
        flex-shrink: 0;
        height: 77px;
        background: var(--v-background-lighten1);
        @include tablet-vertical {
            height: 66px;
            background: var(--v-background-base);
        }
        @include smartphone-horizontal {
            height: 34px;
        }
        @include smartphone-vertical {
            height: 50px;
            background: var(--v-background-base);
        }

        .panel-navigation-button {
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            width: 77px;
            height: 56px;
            padding: 6px 0px;
            border-radius: 5px;
            color: var(--v-text-base);
            box-sizing: content-box;
            transition: color 0.3s;
            user-select: none;
            cursor: pointer;
            @include tablet-vertical {
                width: 100px;
                height: 56px;
                padding: 4px 0px;
                box-sizing: border-box;
            }
            @include smartphone-horizontal {
                height: 34px;
                padding: 5px 0px;
                box-sizing: border-box;
            }
            @include smartphone-vertical {
                height: 38px;
                padding: 6px 0px;
                box-sizing: border-box;
            }

            &--active {
                color: var(--v-primary-base);
                .panel-navigation-button__icon {
                    color: var(--v-primary-base);
                }
                @include tablet-vertical {
                    background: #5b2d3c;
                }
                @include smartphone-vertical {
                    background: #5b2d3c;
                }
            }

            &__icon {
                height: 34px;
                @include tablet-vertical {
                    color: var(--v-text-base);
                }
                @include smartphone-vertical {
                    color: var(--v-text-base);
                }
            }
            &__text {
                margin-top: 5px;
                font-size: 13px;
                @include tablet-vertical {
                    margin-top: 3px;
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    display: none;
                }
                @include smartphone-vertical {
                    display: none;
                }
            }
        }
    }
}

</style>