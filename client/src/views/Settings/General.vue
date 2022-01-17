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
                <div class="settings__item-label">視聴画面右側のパネルを既定でどう表示するかを設定します。</div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="panel_display_state" v-model="settings.panel_display_state"></v-select>
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
                {'text': '常に表示する', 'value': 'always_display'},
                {'text': '常に折りたたむ', 'value': 'always_fold'},
                {'text': '前回の状態を復元する', 'value': 'restore_previous_state'},
            ],

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: {
                panel_display_state: Utility.getSettingsItem('panel_display_state'),
            }
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