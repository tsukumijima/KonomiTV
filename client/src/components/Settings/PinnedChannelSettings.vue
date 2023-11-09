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
                    <div>チャンネルをドラッグして並べ替えできます。</div>
                </div>
                <div class="pinned-channels-settings__label"
                    v-if="(channelsStore.channels_list_with_pinned.get('ピン留め') ?? []).length === 0">
                    <div><b>ピン留めされているチャンネルがありません。</b></div>
                    <div class="mt-1">TV ホーム画面のチャンネルリストの <Icon style="position: relative; bottom: -5px;" icon="fluent:pin-20-filled" width="18.5px" /> アイコンから、よくみるチャンネルをピン留めできます。</div>
                </div>
                <draggable class="pinned-channels" v-model="settingsStore.settings.pinned_channel_ids"
                    v-if="(channelsStore.channels_list_with_pinned.get('ピン留め') ?? []).length > 0">
                    <div class="pinned-channel"
                        v-for="channel in channelsStore.channels_list_with_pinned.get('ピン留め') ?? []" :key="channel.id">
                        <img class="pinned-channel__icon" :src="`${Utils.api_base_url}/channels/${channel.id}/logo`">
                        <span class="pinned-channel__name">Ch: {{channel.channel_number}} {{channel.name}}</span>
                        <button class="pinned-channel__sort-handle">
                            <Icon icon="material-symbols:drag-handle-rounded" width="20px" />
                        </button>
                        <button v-ripple class="pinned-channel__delete-button"
                            @click="settingsStore.settings.pinned_channel_ids.splice(settingsStore.settings.pinned_channel_ids.indexOf(channel.id), 1)">
                            <Icon icon="fluent:delete-16-filled" width="20px" />
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
            Utils: Utils,

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
    .v-card__title, & > div {
        @include smartphone-vertical {
            padding-left: 12px !important;
            padding-right: 12px !important;
        }
    }
    .v-card__title span {
        font-size: 20px;
        @include smartphone-vertical {
            font-size: 16px;
        }
    }
}

.pinned-channels-settings__label {
    margin-top: 8px;
    color: var(--v-text-darken1);
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
        border-bottom: 1px solid var(--v-background-lighten2);
        transition: background-color 0.15s ease;
        user-select: none;
        cursor: grab;

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
            background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
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
            height: 40px;
            margin-left: auto;
            border-radius: 5px;
            outline: none;
            cursor: inherit;
        }

        &__delete-button {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            margin-left: 4px;
            border-radius: 5px;
            outline: none;
            cursor: pointer;
        }
    }
}

</style>