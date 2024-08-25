<template>
    <v-dialog max-width="700" transition="slide-y-transition" v-model="playerStore.lshaped_screen_crop_settings_modal">
        <v-card class="lshaped-screen-crop-settings-modal">
            <v-card-title class="px-5 pt-3 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="fluent:crop-20-filled" height="28px" />
                <span class="ml-3">Ｌ字画面のクロップ</span>
                <v-spacer></v-spacer>
                <v-switch class="mr-4" color="primary" hide-details v-model="settingsStore.settings.lshaped_screen_crop_enabled"></v-switch>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2"
                    @click="playerStore.lshaped_screen_crop_settings_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <v-slider color="primary" v-model="settingsStore.settings.lshaped_screen_crop_zoom_level" :min="100" :max="200" :step="1"
                    show-ticks="always" hide-details class="ml-0 mr-0 mb-4">
                    <template v-slot:prepend>
                        <div class="d-flex align-center" style="width: 85px;">
                            <Icon icon="mdi:magnify" width="20px" />
                            <span class="ml-2">拡大率</span>
                        </div>
                    </template>
                    <template v-slot:append>
                        <div class="text-right" style="width: 42px;">{{ settingsStore.settings.lshaped_screen_crop_zoom_level }}%</div>
                    </template>
                </v-slider>
                <v-slider color="primary" v-model="settingsStore.settings.lshaped_screen_crop_x_position" :min="0" :max="100" :step="1"
                    show-ticks="always" hide-details class="ml-0 mr-0 mb-4">
                    <template v-slot:prepend>
                        <div class="d-flex align-center" style="width: 85px;">
                            <Icon icon="mdi:arrow-left-right" width="20px" />
                            <span class="ml-2">Ｘ座標</span>
                        </div>
                    </template>
                    <template v-slot:append>
                        <div class="text-right" style="width: 42px;">{{ settingsStore.settings.lshaped_screen_crop_x_position }}%</div>
                    </template>
                </v-slider>
                <v-slider color="primary" v-model="settingsStore.settings.lshaped_screen_crop_y_position" :min="0" :max="100" :step="1"
                    show-ticks="always" hide-details class="ml-0 mr-0 mb-4">
                    <template v-slot:prepend>
                        <div class="d-flex align-center" style="width: 85px;">
                            <Icon icon="mdi:arrow-up-down" width="20px" />
                            <span class="ml-2">Ｙ座標</span>
                        </div>
                    </template>
                    <template v-slot:append>
                        <div class="text-right" style="width: 42px;">{{ settingsStore.settings.lshaped_screen_crop_y_position }}%</div>
                    </template>
                </v-slider>
                <div class="mt-5 ml-0">
                    <div class="d-flex align-center">
                        <span>拡大起点</span>
                    </div>
                    <div class="text-text-darken-1 mt-2" style="font-size: 13.5px;">
                        拡大率を変更したときに、どの位置を基準に拡大するかを設定します。
                    </div>
                </div>
                <v-radio-group class="zoom-origin-radio-group mt-3 ml-0" color="primary" inline hide-details
                    v-model="settingsStore.settings.lshaped_screen_crop_zoom_origin">
                    <v-radio label="左上" value="TopLeft"></v-radio>
                    <v-radio label="左下" value="BottomLeft"></v-radio>
                    <v-radio label="右上" value="TopRight"></v-radio>
                    <v-radio label="右下" value="BottomRight"></v-radio>
                </v-radio-group>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';

const settingsStore = useSettingsStore();
const playerStore = usePlayerStore();

</script>
<style lang="scss">

.zoom-origin-radio-group .v-selection-control-group {
    column-gap: 12px;
    .v-label {
        opacity: 1 !important;
    }
}

.lshaped-screen-crop-settings-modal > div {
    @include smartphone-vertical {
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
}

</style>
<style lang="scss" scoped>

.shortcut-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    min-width: 32px;
    min-height: 28px;
    padding: 3px 8px;
    border-radius: 5px;
    background-color: rgb(var(--v-theme-background-lighten-2));
    font-size: 14.5px;
    text-align: center;
}

.shortcut-key-plus {
    display: inline-block;
    margin: 0px 5px;
    flex-shrink: 0;
}

</style>