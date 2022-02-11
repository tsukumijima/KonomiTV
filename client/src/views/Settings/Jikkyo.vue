<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="bi:chat-left-text-fill" width="18px" />
            <span class="ml-3">ニコニコ実況</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">コメントの速さ</div>
                <div class="settings__item-label">
                    プレイヤーに流れるコメントの速さを設定します。<br>
                    たとえば 1.2 に設定すると、コメントが 1.2 倍速く流れます。<br>
                </div>
                <v-slider class="settings__item-form" ticks="always" thumb-label hide-details
                         :step="0.1" :min="0.5" :max="2" v-model="settings.comment_speed_rate"></v-slider>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">コメントの文字サイズ</div>
                <div class="settings__item-label">
                    プレイヤーに流れるコメントの文字サイズの基準値を設定します。<br>
                    実際の文字サイズは画面の大きさに合わせて調整されます。既定の文字サイズは 34px です。<br>
                </div>
                <v-slider class="settings__item-form" ticks="always" thumb-label hide-details
                          :min="20" :max="60" v-model="settings.comment_font_size"></v-slider>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">コメントの遅延時間</div>
                <div class="settings__item-label">
                    プレイヤーやコメントリストに表示されるコメントを何秒遅らせて反映するかを設定します。<br>
                    通常は 1 秒程度で大丈夫です。ネットワークが遅いなどでタイムラグが大きいときだけ、映像の遅延に合わせて調整してください。<br>
                </div>
                <v-slider class="settings__item-form" ticks="always" thumb-label hide-details
                          :step="0.5" :min="0" :max="5"  v-model="settings.comment_delay_time"></v-slider>
            </div>
        </div>
    </Base>
</template>
<script lang="ts">

import Vue from 'vue';

import Base from '@/views/Settings/Base.vue';
import Utils from '@/utils';

export default Vue.extend({
    name: 'SettingsJikkyo',
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
                for (const setting of ['comment_speed_rate', 'comment_font_size', 'comment_delay_time']) {
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