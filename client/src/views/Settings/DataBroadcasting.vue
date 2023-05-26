<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <svg width="27px" height="27px" viewBox="0 0 512 512">
                <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
            </svg>
            <span class="ml-2">データ放送</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="tv_show_data_broadcasting">テレビをみるときにデータ放送を表示する</label>
                <label class="settings__item-label" for="tv_show_data_broadcasting">
                    この設定をオンにすると、テレビをみるときにデータ放送を表示できます。<br>
                    データ放送自体のオン/オフは、視聴画面右側のパネルからリモコンを表示した上で、リモコンの d ボタンから切り替えられます。<br>
                </label>
                <label class="settings__item-label" for="tv_show_data_broadcasting">
                    データ放送機能をオンにすると、視聴時の負荷が比較的高くなります。データ放送をまったく使わない場合や、スペックの低い Android 端末ではオフにすることをおすすめします。<br>
                </label>
                <v-switch class="settings__item-switch" id="tv_show_data_broadcasting" inset hide-details
                    v-model="settingsStore.settings.tv_show_data_broadcasting">
                </v-switch>
            </div>
            <v-divider class="mt-6"></v-divider>
            <!-- <div class="settings__item">
                <label class="settings__item-heading">字幕のフォント</label>
                <label class="settings__item-label">
                    プレイヤーで字幕表示をオンにしているときの、字幕のフォントを設定します。<br>
                </label>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="caption_font" v-model="settingsStore.settings.caption_font">
                </v-select>
            </div> -->
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
    name: 'Settings-DataBroadcasting',
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