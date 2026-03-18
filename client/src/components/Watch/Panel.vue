<template>
    <div class="watch-panel" :style="panelWidthStyle"
         @mousemove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})">
        <div class="panel-resize-handle"
             @mousedown="startResize"></div>
        <div class="watch-panel__header">
            <div v-ripple class="panel-close-button" @click="playerStore.is_panel_display = false">
                <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
                <span class="panel-close-button__text">閉じる</span>
            </div>
            <v-spacer></v-spacer>
            <div class="panel-broadcaster" v-if="playback_mode === 'Live'">
                <img class="panel-broadcaster__icon" :src="`${Utils.api_base_url}/channels/${channelsStore.channel.current.id}/logo`">
                <div class="panel-broadcaster__number">{{channelsStore.channel.current.channel_number}}</div>
                <div class="panel-broadcaster__name">{{channelsStore.channel.current.name}}</div>
            </div>
        </div>
        <div class="watch-panel__content-container">
            <Program class="watch-panel__content" v-if="playback_mode === 'Live'"
                :class="{'watch-panel__content--active': panel_active_tab === 'Program'}" />
            <RecordedProgram class="watch-panel__content" v-if="playback_mode === 'Video'"
                :class="{'watch-panel__content--active': panel_active_tab === 'RecordedProgram'}" />
            <Channel class="watch-panel__content" v-if="playback_mode === 'Live'"
                :class="{'watch-panel__content--active': panel_active_tab === 'Channel'}" />
            <Series class="watch-panel__content" v-if="playback_mode === 'Video'"
                :class="{'watch-panel__content--active': panel_active_tab === 'Series'}" />
            <Comment class="watch-panel__content" :playback_mode="playback_mode"
                :class="{'watch-panel__content--active': panel_active_tab === 'Comment'}" />
            <Twitter class="watch-panel__content" :playback_mode="playback_mode"
                :class="{'watch-panel__content--active': panel_active_tab === 'Twitter'}" />
            <button v-ripple class="watch-panel__content-remocon-button elevation-8" v-if="playback_mode === 'Live'"
                :class="{'watch-panel__content-remocon-button--active': panel_active_tab === 'Program' || panel_active_tab === 'Channel'}"
                @click="playerStore.is_remocon_display = !playerStore.is_remocon_display">
                <Icon class="panel-close-button__icon" icon="material-symbols:remote-gen" width="25px" />
            </button>
            <Remocon class="watch-panel__remocon" v-if="playback_mode === 'Live'"
                :modelValue="(panel_active_tab === 'Program' || panel_active_tab === 'Channel') && playerStore.is_remocon_display === true"
                @update:modelValue="playerStore.is_remocon_display = $event" />
        </div>
        <section class="comment-input-bar" v-if="playback_mode === 'Live' && panel_active_tab === 'Comment' && settingsStore.settings.show_panel_comment_input">
            <div class="comment-input-bar__container">
                <v-text-field class="comment-input-bar__input" variant="outlined" density="compact" hide-details
                    placeholder="コメントを入力..." v-model="comment_text"
                    @keydown.enter="sendCommentFromPanel()" :disabled="is_sending_comment" />
                <v-menu v-model="comment_settings_menu" :close-on-content-click="false" location="top end">
                    <template v-slot:activator="{ props }">
                        <v-btn class="comment-input-bar__settings-button" v-bind="props"
                            icon variant="tonal" density="compact" size="small">
                            <Icon icon="fluent:settings-20-filled" height="16px" />
                        </v-btn>
                    </template>
                    <v-card class="comment-input-bar__settings-card" min-width="200">
                        <v-card-text class="pa-3">
                            <div class="comment-input-bar__settings-label">色</div>
                            <div class="comment-input-bar__color-list">
                                <button v-for="c in available_colors" :key="c.hex"
                                    class="comment-input-bar__color-button"
                                    :class="{'comment-input-bar__color-button--active': settingsStore.settings.panel_comment_color === c.hex}"
                                    :style="{background: c.hex}" :title="c.name"
                                    @click="settingsStore.settings.panel_comment_color = c.hex" />
                            </div>
                            <div class="comment-input-bar__settings-label mt-3">位置</div>
                            <v-btn-toggle v-model="settingsStore.settings.panel_comment_position" mandatory density="compact" color="primary" class="comment-input-bar__toggle">
                                <v-btn value="top" size="small">上</v-btn>
                                <v-btn value="right" size="small">中(流)</v-btn>
                                <v-btn value="bottom" size="small">下</v-btn>
                            </v-btn-toggle>
                            <div class="comment-input-bar__settings-label mt-3">サイズ</div>
                            <v-btn-toggle v-model="settingsStore.settings.panel_comment_size" mandatory density="compact" color="primary" class="comment-input-bar__toggle">
                                <v-btn value="small" size="small">小</v-btn>
                                <v-btn value="medium" size="small">中</v-btn>
                                <v-btn value="big" size="small">大</v-btn>
                            </v-btn-toggle>
                        </v-card-text>
                    </v-card>
                </v-menu>
                <v-btn class="comment-input-bar__send-button" icon variant="flat" density="compact" size="small"
                    color="primary" :disabled="is_sending_comment || comment_text.trim() === ''"
                    @click="sendCommentFromPanel()">
                    <Icon icon="fluent:send-20-filled" height="16px" />
                </v-btn>
            </div>
        </section>
        <div class="watch-panel__navigation">
            <div v-ripple class="panel-navigation-button" v-if="playback_mode === 'Live'"
                 :class="{'panel-navigation-button--active': panel_active_tab === 'Program'}"
                 @click="playerStore.tv_panel_active_tab = 'Program'">
                <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                <span class="panel-navigation-button__text">番組情報</span>
            </div>
            <div v-ripple class="panel-navigation-button" v-if="playback_mode === 'Video'"
                 :class="{'panel-navigation-button--active': panel_active_tab === 'RecordedProgram'}"
                 @click="playerStore.video_panel_active_tab = 'RecordedProgram'">
                <Icon class="panel-navigation-button__icon" icon="fa-solid:info-circle" width="33px" />
                <span class="panel-navigation-button__text">番組情報</span>
            </div>
            <div v-ripple class="panel-navigation-button" v-if="playback_mode === 'Live'"
                 :class="{'panel-navigation-button--active': panel_active_tab === 'Channel'}"
                 @click="playerStore.tv_panel_active_tab = 'Channel'">
                <Icon class="panel-navigation-button__icon" icon="fa-solid:broadcast-tower" width="34px" />
                <span class="panel-navigation-button__text">チャンネル</span>
            </div>
            <div v-ripple class="panel-navigation-button" v-if="playback_mode === 'Video'"
                 :class="{'panel-navigation-button--active': panel_active_tab === 'Series'}"
                 @click="playerStore.video_panel_active_tab = 'Series'">
                <Icon class="panel-navigation-button__icon" icon="fluent:video-clip-multiple-16-filled" width="34px"
                    style="width: 39px; height: 39px; margin-top: -4px; margin-bottom: -4px;" />
                <span class="panel-navigation-button__text">シリーズ</span>
            </div>
            <div v-ripple class="panel-navigation-button"
                 :class="{'panel-navigation-button--active': panel_active_tab === 'Comment'}"
                 @click="playback_mode === 'Live' ? playerStore.tv_panel_active_tab = 'Comment' : playerStore.video_panel_active_tab = 'Comment'">
                <Icon class="panel-navigation-button__icon" icon="bi:chat-left-text-fill" width="29px" />
                <span class="panel-navigation-button__text">コメント</span>
            </div>
            <div v-ripple class="panel-navigation-button"
                 :class="{'panel-navigation-button--active': panel_active_tab === 'Twitter'}"
                 @click="playback_mode === 'Live' ? playerStore.tv_panel_active_tab = 'Twitter' : playerStore.video_panel_active_tab = 'Twitter'">
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
import RecordedProgram from '@/components/Watch/Panel/RecordedProgram.vue';
import Remocon from '@/components/Watch/Panel/Remocon.vue';
import Series from '@/components/Watch/Panel/Series.vue';
import Twitter from '@/components/Watch/Panel/Twitter.vue';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';

export default defineComponent({
    name: 'Watch-Panel',
    components: {
        Channel,
        Comment,
        Program,
        RecordedProgram,
        Remocon,
        Series,
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
            Utils: Object.freeze(Utils),
            // リサイズ中かどうか
            is_resizing: false,
            // リサイズ開始時の X 座標
            resize_start_x: 0,
            // リサイズ開始時のパネル幅
            resize_start_width: 0,

            // コメント入力バー関連
            comment_text: '',
            comment_settings_menu: false,
            is_sending_comment: false,
            available_colors: [
                { hex: '#FFEAEA', name: '白' },
                { hex: '#F02840', name: '赤' },
                { hex: '#FD7E80', name: 'ピンク' },
                { hex: '#FDA708', name: 'オレンジ' },
                { hex: '#FFE133', name: '黄' },
                { hex: '#64DD17', name: '緑' },
                { hex: '#00D4F5', name: '水色' },
                { hex: '#4763FF', name: '青' },
            ],
        };
    },
    computed: {
        ...mapStores(useChannelsStore, usePlayerStore, useSettingsStore),

        // ライブ視聴なら tv_panel_active_tab を、ビデオ視聴なら video_panel_active_tab を返す
        panel_active_tab() {
            if (this.playback_mode === 'Live') {
                return this.playerStore.tv_panel_active_tab;
            } else {
                return this.playerStore.video_panel_active_tab;
            }
        },

        panelWidthStyle() {
            return { '--panel-width': `${this.settingsStore.settings.panel_width}px` };
        },
    },
    beforeUnmount() {
        // リサイズ中にコンポーネントが破棄された場合のリスナーのクリーンアップ
        document.removeEventListener('mousemove', this.onResize);
        document.removeEventListener('mouseup', this.stopResize);
        this.is_resizing = false;
    },
    methods: {
        // パネルのコメント入力バーからコメントを送信する
        sendCommentFromPanel(): void {
            const text = this.comment_text.trim();
            if (text === '' || this.is_sending_comment) return;

            this.is_sending_comment = true;

            // コールバックが呼ばれなかった場合のフォールバックタイマー (10秒)
            const fallback_timer = window.setTimeout(() => {
                this.is_sending_comment = false;
            }, 10000);

            try {
                this.playerStore.event_emitter.emit('SendComment', {
                    text: text,
                    color: this.settingsStore.settings.panel_comment_color,
                    type: this.settingsStore.settings.panel_comment_position,
                    size: this.settingsStore.settings.panel_comment_size,
                    onSuccess: () => {
                        window.clearTimeout(fallback_timer);
                        this.comment_text = '';
                        this.is_sending_comment = false;
                    },
                    onError: (message: string) => {
                        window.clearTimeout(fallback_timer);
                        this.is_sending_comment = false;
                        this.playerStore.event_emitter.emit('SendNotification', {
                            message: message,
                            duration: 4000,
                            color: '#FF6F6A',
                        });
                    },
                });
            } catch {
                window.clearTimeout(fallback_timer);
                this.is_sending_comment = false;
            }
        },
        startResize(event: MouseEvent) {
            event.preventDefault();
            this.is_resizing = true;
            this.resize_start_x = event.clientX;
            this.resize_start_width = this.settingsStore.settings.panel_width;
            document.addEventListener('mousemove', this.onResize);
            document.addEventListener('mouseup', this.stopResize);
        },
        onResize(event: MouseEvent) {
            // 左にドラッグ = 正の値 = 幅が増える
            const delta = this.resize_start_x - event.clientX;
            const new_width = Math.min(600, Math.max(352, this.resize_start_width + delta));
            this.settingsStore.settings.panel_width = new_width;
        },
        stopResize() {
            this.is_resizing = false;
            document.removeEventListener('mousemove', this.onResize);
            document.removeEventListener('mouseup', this.stopResize);
        },
    },
});

</script>
<style lang="scss" scoped>

.watch-panel {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    position: relative;
    width: var(--panel-width, 352px);
    height: 100%;
    background: rgb(var(--v-theme-background));
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

    .panel-resize-handle {
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        cursor: col-resize;
        z-index: 25;
        transition: background-color 0.15s;

        &:hover, &:active {
            background: rgb(var(--v-theme-primary));
        }

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
                background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
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
            background: rgb(var(--v-theme-background));
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
                z-index: 15;
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
            background: rgb(var(--v-theme-background-lighten-1));
            outline: none;
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;
            z-index: 20;

            @media (hover: none) {
                transition: none;
            }
            &--active {
                opacity: 1;
                visibility: visible;
            }
        }
    }

    .comment-input-bar {
        flex-shrink: 0;
        width: 100%;
        padding: 8px 16px;
        border-top: 1px solid rgb(var(--v-theme-background-lighten-2));
        @include tablet-vertical {
            padding: 8px 24px;
        }
        @include smartphone-horizontal {
            padding: 6px 16px;
        }
        @include smartphone-vertical {
            padding: 6px 16px;
        }

        &__container {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        &__input {
            flex: 1;
            min-width: 0;
            :deep(.v-field) {
                font-size: 13px;
                min-height: 32px;
            }
            :deep(.v-field__input) {
                padding-top: 4px;
                padding-bottom: 4px;
                min-height: 32px;
            }
        }

        &__settings-button, &__send-button {
            flex-shrink: 0;
        }

        &__settings-card {
            background: rgb(var(--v-theme-background-lighten-1)) !important;
        }

        &__settings-label {
            font-size: 12px;
            font-weight: bold;
            color: rgb(var(--v-theme-text-darken-1));
            margin-bottom: 6px;
        }

        &__color-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        &__color-button {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            border: 2px solid transparent;
            cursor: pointer;
            transition: border-color 0.15s;
            &:hover {
                opacity: 0.8;
            }
            &--active {
                border-color: rgb(var(--v-theme-primary));
            }
        }

        &__toggle {
            width: 100%;
            :deep(.v-btn) {
                flex: 1;
                font-size: 12px;
            }
        }
    }

    .watch-panel__navigation {
        display: flex;
        align-items: center;
        justify-content: space-evenly;
        flex-shrink: 0;
        height: 77px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-top: 1px solid rgb(var(--v-theme-background-lighten-2));
        @include tablet-vertical {
            height: 66px;
            background: rgb(var(--v-theme-background));
        }
        @include smartphone-horizontal {
            height: 34px;
        }
        @include smartphone-vertical {
            height: 50px;
            background: rgb(var(--v-theme-background));
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
            color: rgb(var(--v-theme-text));
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
                color: rgb(var(--v-theme-primary));
                .panel-navigation-button__icon {
                    color: rgb(var(--v-theme-primary));
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
                    color: rgb(var(--v-theme-text));
                }
                @include smartphone-vertical {
                    color: rgb(var(--v-theme-text));
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