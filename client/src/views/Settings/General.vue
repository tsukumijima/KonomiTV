<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="fa-solid:sliders-h" width="18px" />
            <span class="ml-3">全般</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">既定のパネルの表示状態</div>
                <div class="settings__item-label">視聴画面を開いたときに、右側のパネルをどう表示するかを設定します。</div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="panel_display_state" v-model="settings.panel_display_state"></v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">既定で表示されているパネルのタブ</div>
                <div class="settings__item-label">視聴画面を開いたときに、右側のパネルで最初に表示されているタブを設定します。</div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="panel_active_tab" v-model="settings.panel_active_tab"></v-select>
            </div>
        </div>
    </Base>
</template>
<script lang="ts">

import Vue from 'vue';

import Base from '@/views/Settings/Base.vue';
import Utility from '@/utility';

export default Vue.extend({
    name: 'Home',
    components: {
        Base,
    },
    data() {
        return {

            // 既定のパネルの表示状態
            panel_display_state: [
                {'text': '常に表示する', 'value': 'AlwaysDisplay'},
                {'text': '常に折りたたむ', 'value': 'AlwaysFold'},
                {'text': '前回の状態を復元する', 'value': 'RestorePreviousState'},
            ],

            // 既定で表示されているパネルのタブ
            panel_active_tab: [
                {'text': '番組情報タブ', 'value': 'Program'},
                {'text': 'チャンネルタブ', 'value': 'Channel'},
                {'text': 'コメントタブ', 'value': 'Comment'},
                {'text': 'Twitter タブ', 'value': 'Twitter'},
            ],

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: (() => {
                // 設定の既定値を取得する
                const settings = {}
                for (const setting of ['panel_display_state', 'panel_active_tab']) {
                    settings[setting] = Utility.getSettingsItem(setting);
                }
                return settings;
            })(),
        }
    },
    watch: {
        // settings 内の値の変更を監視する
        settings: {
            deep: true,
            handler() {
                // settings 内の値を順に LocalStorage に保存する
                for (const [setting_key, setting_value] of Object.entries(this.settings)) {
                    Utility.setSettingsItem(setting_key, setting_value);
                }
            }
        }
    }
});

</script>