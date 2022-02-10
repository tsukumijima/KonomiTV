<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="fluent:person-20-filled" width="24px" />
            <span class="ml-2">アカウント</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">鋭意開発中…</div>
            </div>
        </div>
    </Base>
</template>
<script lang="ts">

import Vue from 'vue';

import Base from '@/views/Settings/Base.vue';
import Utils from '@/utils';

export default Vue.extend({
    name: 'SettingsAccount',
    components: {
        Base,
    },
    data() {
        return {

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: (() => {
                // 設定の既定値を取得する
                const settings = {}
                for (const setting of []) {
                    settings[setting] = Utils.getSettingsItem(setting);
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
                    Utils.setSettingsItem(setting_key, setting_value);
                }
            }
        }
    }
});

</script>