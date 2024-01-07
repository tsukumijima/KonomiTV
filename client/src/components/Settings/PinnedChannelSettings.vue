<template>
    <v-dialog max-width="550" transition="slide-y-transition" v-model="pinned_channel_settings_modal">
        <v-card class="pinned-channels-settings">
            <v-card-title class="px-5 pt-5 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="iconamoon:sorting-left-bold" height="26px" />
                <span class="ml-3">ピン留め中チャンネルの並び替え</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="pinned_channel_settings_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-5">
                <div class="pinned-channels-settings__label"
                    v-if="(channelsStore.channels_list_with_pinned.get('ピン留め') ?? []).length > 0">
                    <div>各チャンネルのつまみをドラッグして並べ替えできます。</div>
                </div>
                <div class="pinned-channels-settings__label"
                    v-if="(channelsStore.channels_list_with_pinned.get('ピン留め') ?? []).length === 0">
                    <div><b>ピン留めされているチャンネルがありません。</b></div>
                    <div class="mt-1">TV ホーム画面のチャンネルリストの <Icon style="position: relative; bottom: -5px;" icon="fluent:pin-20-filled" width="18.5px" /> アイコンから、よくみるチャンネルをピン留めできます。</div>
                </div>
                <draggable class="pinned-channels" v-model="settingsStore.settings.pinned_channel_ids" handle=".pinned-channel__sort-handle"
                    v-if="(channelsStore.channels_list_with_pinned.get('ピン留め') ?? []).length > 0">
                    <!-- 以下では Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                    <div class="pinned-channel"
                        v-for="channel in channelsStore.channels_list_with_pinned.get('ピン留め') ?? []" :key="channel.id">
                        <img class="pinned-channel__icon" :src="`${Utils.api_base_url}/channels/${channel.id}/logo`">
                        <span class="pinned-channel__name">Ch: {{channel.channel_number}} {{channel.name}}</span>
                        <button class="pinned-channel__sort-handle">
                            <svg class="iconify iconify--material-symbols" width="20px" height="20px" viewBox="0 0 24 24">
                                <path fill="currentColor" d="M5 15q-.425 0-.713-.288T4 14q0-.425.288-.713T5 13h14q.425 0 .713.288T20 14q0 .425-.288.713T19 15H5Zm0-4q-.425 0-.713-.288T4 10q0-.425.288-.713T5 9h14q.425 0 .713.288T20 10q0 .425-.288.713T19 11H5Z"></path>
                            </svg>
                        </button>
                        <button v-ripple class="pinned-channel__delete-button"
                            @click="settingsStore.settings.pinned_channel_ids.splice(settingsStore.settings.pinned_channel_ids.indexOf(channel.id), 1)">
                            <svg class="iconify iconify--fluent" width="20px" height="20px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0ZM6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1h4Zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0v-5ZM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5Z"></path>
                            </svg>
                        </button>
                    </div>
                </draggable>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';
import draggable from 'vuedraggable';

import useChannelsStore from '@/stores/ChannelsStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';

export default defineComponent({
    name: 'PinnedChannelSettings',
    components: {
        draggable,
    },
    props: {
        modelValue: {
            type: Boolean as PropType<boolean>,
            required: true,
        }
    },
    emits: {
        'update:modelValue': (value: boolean) => true,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),

            // ピン留め中チャンネルの並び替え設定のモーダルを表示するか
            pinned_channel_settings_modal: false,
        };
    },
    computed: {
        ...mapStores(useChannelsStore, useSettingsStore),
    },
    watch: {

        // modelValue (親コンポーネント側: Props) の変更を監視し、変更されたら pinned_channel_settings_modal に反映する
        modelValue() {
            this.pinned_channel_settings_modal = this.modelValue;
        },

        // pinned_channel_settings_modal (子コンポーネント側) の変更を監視し、変更されたら this.$emit() で親コンポーネントに伝える
        pinned_channel_settings_modal() {
            this.$emit('update:modelValue', this.pinned_channel_settings_modal);
        }
    },
    async created() {

        // チャンネル情報を更新
        await this.channelsStore.update();
    }
});

</script>
<style lang="scss" scoped>

.pinned-channels-settings {
    .v-card-title, & > div {
        @include smartphone-vertical {
            padding-left: 12px !important;
            padding-right: 12px !important;
        }
    }
    .v-card-title span {
        font-size: 20px;
        @include smartphone-vertical {
            font-size: 15.5px;
        }
    }
}

.pinned-channels-settings__label {
    margin-top: 8px;
    color: rgb(var(--v-theme-text-darken-1));
    font-size: 13.5px;
    line-height: 1.6;
    @include smartphone-horizontal {
        font-size: 11px;
        line-height: 1.7;
    }
}

.pinned-channels {
    display: flex;
    flex-direction: column;
    margin-top: 12px;

    .pinned-channel {
        display: flex;
        align-items: center;
        padding: 6px 0px;
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        transition: background-color 0.15s ease;

        &:last-of-type {
            border-bottom: none;
        }

        &__icon {
            display: inline-block;
            flex-shrink: 0;
            width: 64px;
            height: 36px;
            border-radius: 4px;
            // 読み込まれるまでのアイコンの背景
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
            object-fit: cover;
        }

        &__name {
            margin-left: 16px;
            font-size: 16.5px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            @include smartphone-vertical {
                margin-left: 12px;
                font-size: 15.5px;
            }
        }

        &__sort-handle {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 35px;
            height: 40px;
            margin-left: auto;
            border-radius: 5px;
            outline: none;
            cursor: grab;
        }

        &__delete-button {
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
    }
}

</style>