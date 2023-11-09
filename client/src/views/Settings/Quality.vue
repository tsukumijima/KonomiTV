<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <Icon icon="fluent:video-clip-multiple-16-filled" width="26px" />
            <span class="ml-3">画質</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item settings__item--sync-disabled">
                <div class="settings__item-heading">テレビのデフォルトのストリーミング画質</div>
                <div class="settings__item-label">
                    テレビをライブストリーミングするときのデフォルトの画質を設定します。<br>
                    ストリーミング画質はプレイヤーの設定からいつでも切り替えられます。<br>
                </div>
                <div class="settings__item-label">
                    [1080p (60fps)] は、通常 30fps (60i) の映像を補間し、より滑らか（ぬるぬる）な映像で視聴できます！<br>
                    [1080p (60fps)] で視聴するときは、サーバー設定の [利用するエンコーダー] をハードウェアエンコーダーに設定してください。FFmpeg (ソフトウェアエンコーダー) では、視聴に支障が出ることがあります。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tv_streaming_quality" v-model="settingsStore.settings.tv_streaming_quality">
                </v-select>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled"
                :class="{'settings__item--disabled': PlayerUtils.isHEVCVideoSupported() === false}">
                <label class="settings__item-heading" for="tv_data_saver_mode">テレビを通信節約モードで視聴する</label>
                <label class="settings__item-label" for="tv_data_saver_mode">
                    通信節約モードでは、H.265 / HEVC という圧縮率の高いコーデックを使い、画質はほぼそのまま、通信量を通常の 1/2 程度に抑えながら視聴できます！<br>
                    通信節約モードで視聴するときは、サーバー設定の [利用するエンコーダー] をハードウェアエンコーダーに設定してください。FFmpeg (ソフトウェアエンコーダー) では、視聴に支障が出る可能性が高いです。<br>
                    <p class="mt-1 mb-0 error--text lighten-1" v-if="PlayerUtils.isHEVCVideoSupported() === false && Utils.isFirefox() === false">
                        このデバイスでは通信節約モードがサポートされていません。
                    </p>
                    <p class="mt-1 mb-0 error--text lighten-1" v-if="PlayerUtils.isHEVCVideoSupported() === false && Utils.isFirefox() === true">
                        お使いの Firefox ブラウザでは通信節約モードがサポートされていません。
                    </p>
                </label>
                <v-switch class="settings__item-switch" id="tv_data_saver_mode" inset hide-details
                    v-model="settingsStore.settings.tv_data_saver_mode" :disabled="PlayerUtils.isHEVCVideoSupported() === false">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="tv_low_latency_mode">テレビを低遅延で視聴する</label>
                <label class="settings__item-label" for="tv_low_latency_mode">
                    低遅延ストリーミングをオンにすると、<b>放送波との遅延を最短 0.9 秒に抑えて視聴できます！</b><br>
                    また、約 3 秒以上遅延したときに少しだけ再生速度を早める (1.1x) ことで、滑らかにストリーミングの遅延を取り戻します。<br>
                    宅外視聴などのネットワークが不安定になりがちな環境では、低遅延ストリーミングをオフにしてみると、映像のカクつきを改善できるかもしれません。<br>
                </label>
                <v-switch class="settings__item-switch" id="tv_low_latency_mode" inset hide-details
                    v-model="settingsStore.settings.tv_low_latency_mode">
                </v-switch>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import useSettingsStore from '@/stores/SettingsStore';
import Utils, { PlayerUtils } from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

const QUALITY_H264 = [
    {text: '1080p (60fps) (約4.50GB/h / 平均10.0Mbps)', value: '1080p-60fps'},
    {text: '1080p (約4.50GB/h / 平均10.0Mbps)', value: '1080p'},
    {text: '810p (約2.62GB/h / 平均5.8Mbps)', value: '810p'},
    {text: '720p (約2.18GB/h / 平均4.9Mbps)', value: '720p'},
    {text: '540p (約1.52GB/h / 平均3.4Mbps)', value: '540p'},
    {text: '480p (約1.06GB/h / 平均2.3Mbps)', value: '480p'},
    {text: '360p (約0.60GB/h / 平均1.3Mbps)', value: '360p'},
    {text: '240p (約0.35GB/h / 平均0.8Mbps)', value: '240p'},
];

const QUALITY_H265 = [
    {text: '1080p (60fps) (約1.80GB/h / 平均4.0Mbps)', value: '1080p-60fps'},
    {text: '1080p (約1.37GB/h / 平均3.0Mbps)', value: '1080p'},
    {text: '810p (約1.05GB/h / 平均2.3Mbps)', value: '810p'},
    {text: '720p (約0.82GB/h / 平均1.8Mbps)', value: '720p'},
    {text: '540p (約0.53GB/h / 平均1.2Mbps)', value: '540p'},
    {text: '480p (約0.46GB/h / 平均1.0Mbps)', value: '480p'},
    {text: '360p (約0.30GB/h / 平均0.7Mbps)', value: '360p'},
    {text: '240p (約0.20GB/h / 平均0.4Mbps)', value: '240p'},
];

export default defineComponent({
    name: 'Settings-Quality',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            PlayerUtils: PlayerUtils,

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // テレビのデフォルトのストリーミング画質の選択肢
            tv_streaming_quality: QUALITY_H264,
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
    },
    watch: {
        'settingsStore.settings.tv_data_saver_mode': {
            immediate: true,
            handler(val: boolean) {
                if (val === true) {
                    this.tv_streaming_quality = QUALITY_H265;
                } else {
                    this.tv_streaming_quality = QUALITY_H264;
                }
            },
        }
    },
    created() {
        // 通信節約モードならストリーミング画質の選択肢を H.265 にする
        if (this.settingsStore.settings.tv_data_saver_mode === true) {
            this.tv_streaming_quality = QUALITY_H265;
        }
    }
});

</script>