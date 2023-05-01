<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <Icon icon="fluent:subtitles-16-filled" width="25px" />
            <span class="ml-3">字幕</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <label class="settings__item-heading">字幕のフォント</label>
                <label class="settings__item-label">
                    プレイヤーで字幕表示をオンにしているときの、字幕のフォントを設定します。<br>
                </label>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="caption_font" v-model="settingsStore.settings.caption_font">
                </v-select>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="always_border_caption_text">字幕の文字を常に縁取りする</label>
                <label class="settings__item-label" for="always_border_caption_text">
                    字幕表示時、縁取りをオンにすると、字幕が見やすくきれいになります。とくに理由がなければ、オンにしておくのがおすすめです。<br>
                    この設定がオフのときも、字幕データ側で縁取りが指定されていれば、オンのときと同様に縁取り付きで描画されます。<br>
                </label>
                <v-switch class="settings__item-switch" id="always_border_caption_text" inset hide-details
                    v-model="settingsStore.settings.always_border_caption_text">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="specify_caption_opacity">字幕の不透明度を指定する</label>
                <label class="settings__item-label" for="specify_caption_opacity">
                    字幕表示時、不透明度を自分で指定するか設定できます。<br>
                    この設定がオフのときは、字幕データ側で指定されている不透明度で描画します。とくに理由がなければ、オフにしておくのがおすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" id="specify_caption_opacity" inset hide-details
                    v-model="settingsStore.settings.specify_caption_opacity">
                </v-switch>
            </div>
            <div class="settings__item" :class="{'settings__item--disabled': settingsStore.settings.specify_caption_opacity === false}">
                <label class="settings__item-heading">字幕の不透明度</label>
                <label class="settings__item-label">
                    上の [字幕の不透明度を指定する] をオンに設定したときのみ有効です。不透明度を 0 に設定すれば、字幕の背景を非表示にできます。<br>
                </label>
                <div class="settings__item-label" ref="caption_opacity">
                    <v-slider class="settings__item-form" ticks="always" thumb-label hide-details
                        :min="0" :max="1" :step="0.05" v-model="settingsStore.settings.caption_opacity"
                        :disabled="settingsStore.settings.specify_caption_opacity === false">
                    </v-slider>
                </div>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="tv_show_superimpose">テレビをみるときに文字スーパーを表示する</label>
                <label class="settings__item-label" for="tv_show_superimpose">
                    文字スーパーは、緊急地震速報の赤テロップや、NHK BS のニュース速報のテロップなどで利用されています。とくに理由がなければ、オンにしておくのがおすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" id="tv_show_superimpose" inset hide-details
                    v-model="settingsStore.settings.tv_show_superimpose">
                </v-switch>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import useSettingsStore from '@/store/SettingsStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default Vue.extend({
    name: 'Settings-Caption',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // 字幕のフォントの選択肢
            caption_font: [
                {text: 'Windows TV ゴシック', value: 'Windows TV Gothic'},
                {text: 'Windows TV 丸ゴシック', value: 'Windows TV MaruGothic'},
                {text: 'Windows TV 太丸ゴシック', value: 'Windows TV FutoMaruGothic'},
                {text: 'ヒラギノTV丸ゴ', value: 'Hiragino TV Sans Rd S'},
                {text: '新丸ゴ ARIB', value: 'TT-ShinMGo-regular'},
                {text: 'Rounded M+ 1m for ARIB', value: 'Rounded M+ 1m for ARIB'},
                {text: 'Noto Sans JP', value: 'Noto Sans JP Caption'},
                {text: 'デフォルトのフォント', value: 'sans-serif'},
            ],
        };
    },
    computed: {
        // SettingsStore に this.settingsStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useSettingsStore),
    }
});

</script>