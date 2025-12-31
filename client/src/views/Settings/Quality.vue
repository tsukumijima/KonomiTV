<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="fluent:video-clip-multiple-16-filled" width="26px" />
            <span class="ml-3">画質</span>
        </h2>
        <div class="settings__quote mt-5 pb-2">
            視聴開始時の画質プロファイルは、デバイスの回線状況に応じて自動的に選択されます (Android のみ) 。<br>
            画質プロファイルは、プレイヤー下にある設定アイコン ⚙️ から変更できます。<br>
        </div>
        <v-tabs class="settings__tab" color="primary" bg-color="transparent" align-tabs="center" v-model="tab">
            <v-tab style="text-transform: none !important;" v-for="network_circuit in network_circuits" :key="network_circuit">
                {{network_circuit}}
            </v-tab>
        </v-tabs>
        <div v-show="tab === index" class="settings__content mt-0" v-for="(network_circuit, index) in network_circuits" :key="network_circuit">
            <div class="settings__content-heading mt-6">
                <Icon icon="fluent:tv-20-filled" width="22px" />
                <span class="ml-2">テレビのライブストリーミング</span>
            </div>
            <div class="settings__item settings__item--sync-disabled">
                <div class="settings__item-heading">テレビのデフォルトのストリーミング画質</div>
                <div class="settings__item-label">
                    ライブ視聴時に最初に適用される、デフォルトの画質を設定します。<br>
                    視聴中はプレイヤーの設定からいつでも変更できますが、次回視聴時はここで設定した画質に戻ります。<br>
                </div>
                <div class="settings__item-label mt-1">
                    画質を [1080p (60fps)] に設定すると、<b>通常 30fps (60i) の映像を補間し、より滑らか（ぬるぬる）な映像で視聴できます！</b>ドラマやバラエティなどを視聴するときに特におすすめです。<br>
                </div>
                <div class="settings__item-label mt-1" v-if="Utils.isAndroid()">
                    Fire HD 10 (2021) などの一部のローエンド Android (特に MediaTek SoC 搭載) デバイスでは、1080p 以上の映像描画が不安定なことが確認されています。その場合は 720p 以下の画質を選択することをおすすめします。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'" v-if="network_circuit !== 'モバイル回線時'"
                    :items="tv_streaming_quality" v-model="settingsStore.settings.tv_streaming_quality">
                </v-select>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'" v-if="network_circuit === 'モバイル回線時'"
                    :items="tv_streaming_quality_cellular" v-model="settingsStore.settings.tv_streaming_quality_cellular">
                </v-select>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled"
                :class="{'settings__item--disabled': PlayerUtils.isHEVCVideoSupported() === false}">
                <label class="settings__item-heading" :for="`tv_data_saver_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    テレビを通信節約モードで視聴する
                </label>
                <label class="settings__item-label" :for="`tv_data_saver_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    通信節約モードでは、圧縮率の高い H.265 / HEVC を使い、<b>画質はほぼそのまま、通信量を通常より 50% 〜 70% 削減して視聴できます！</b> サーバー PC によっては高負荷になることがあります。<br>
                </label>
                <div class="settings__item-label mt-1">
                    通信が不安定になりがちなモバイル回線 (4G/5G)・通信速度の遅いフリー Wi-Fi から視聴するときに特におすすめです。<br>
                    <p class="mt-1 mb-0 text-error-lighten-1" v-if="PlayerUtils.isHEVCVideoSupported() === false && Utils.isFirefox() === false">
                        このデバイスでは通信節約モードがサポートされていません。
                    </p>
                    <p class="mt-1 mb-0 text-error-lighten-1" v-if="PlayerUtils.isHEVCVideoSupported() === false && Utils.isFirefox() === true">
                        お使いの Firefox ブラウザでは通信節約モードがサポートされていません。
                    </p>
                </div>
                <v-switch class="settings__item-switch" color="primary" id="tv_data_saver_mode" hide-details v-if="network_circuit !== 'モバイル回線時'"
                    v-model="settingsStore.settings.tv_data_saver_mode" :disabled="PlayerUtils.isHEVCVideoSupported() === false">
                </v-switch>
                <v-switch class="settings__item-switch" color="primary" id="tv_data_saver_mode_cellular" hide-details v-if="network_circuit === 'モバイル回線時'"
                    v-model="settingsStore.settings.tv_data_saver_mode_cellular" :disabled="PlayerUtils.isHEVCVideoSupported() === false">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" :for="`tv_low_latency_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    テレビを低遅延で視聴する
                </label>
                <label class="settings__item-label" :for="`tv_low_latency_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    低遅延ストリーミングをオンにすると、<b>放送波との遅延を最短 0.9 秒に抑えて視聴できます！</b><br>
                    また、約 3 秒以上遅延したときに少しだけ再生速度を早める (1.1x) ことで、滑らかにストリーミングの遅延を取り戻します。<br>
                </label>
                <div class="settings__item-label mt-1">
                    映像がカクつきやすくなるため、<b>通信が不安定になりがちなモバイル回線やフリー Wi-Fi から視聴するときは、オフにすることをおすすめします。</b><br>
                </div>
                <v-switch class="settings__item-switch" color="primary" id="tv_low_latency_mode" hide-details v-if="network_circuit !== 'モバイル回線時'"
                    v-model="settingsStore.settings.tv_low_latency_mode">
                </v-switch>
                <v-switch class="settings__item-switch" color="primary" id="tv_low_latency_mode_cellular" hide-details v-if="network_circuit === 'モバイル回線時'"
                    v-model="settingsStore.settings.tv_low_latency_mode_cellular">
                </v-switch>
            </div>
            <div class="settings__content-heading mt-6">
                <Icon icon="fluent:movies-and-tv-20-filled" width="22px" />
                <span class="ml-2">ビデオのオンデマンドストリーミング</span>
            </div>
            <div class="settings__item settings__item--sync-disabled">
                <div class="settings__item-heading">ビデオのデフォルトのストリーミング画質</div>
                <div class="settings__item-label">
                    録画再生時に最初に適用される、デフォルトの画質を設定します。<br>
                    再生中はプレイヤーの設定からいつでも変更できますが、次回再生時はここで設定した画質に戻ります。<br>
                </div>
                <div class="settings__item-label mt-1">
                    画質を [1080p (60fps)] に設定すると、<b>通常 30fps (60i) の映像を補間し、より滑らか（ぬるぬる）な映像で再生できます！</b>ドラマやバラエティなどを再生するときに特におすすめです。<br>
                </div>
                <div class="settings__item-label mt-1" v-if="Utils.isAndroid()">
                    Fire HD 10 (2021) などの一部のローエンド Android (特に MediaTek SoC 搭載) デバイスでは、1080p 以上の映像描画が不安定なことが確認されています。その場合は 720p 以下の画質を選択することをおすすめします。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'" v-if="network_circuit !== 'モバイル回線時'"
                    :items="video_streaming_quality" v-model="settingsStore.settings.video_streaming_quality">
                </v-select>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'" v-if="network_circuit === 'モバイル回線時'"
                    :items="video_streaming_quality_cellular" v-model="settingsStore.settings.video_streaming_quality_cellular">
                </v-select>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled"
                :class="{'settings__item--disabled': PlayerUtils.isHEVCVideoSupported() === false}">
                <label class="settings__item-heading" :for="`video_data_saver_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    ビデオを通信節約モードで再生する
                </label>
                <label class="settings__item-label" :for="`video_data_saver_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    通信節約モードでは、圧縮率の高い H.265 / HEVC を使い、<b>画質はほぼそのまま、通信量を通常より 50% 〜 70% 削減して再生できます！</b> サーバー PC によっては高負荷になることがあります。<br>
                </label>
                <div class="settings__item-label mt-1">
                    通信が不安定になりがちなモバイル回線 (4G/5G)・通信速度の遅いフリー Wi-Fi から再生するときに特におすすめです。<br>
                    <p class="mt-1 mb-0 text-error-lighten-1" v-if="PlayerUtils.isHEVCVideoSupported() === false && Utils.isFirefox() === false">
                        このデバイスでは通信節約モードがサポートされていません。
                    </p>
                    <p class="mt-1 mb-0 text-error-lighten-1" v-if="PlayerUtils.isHEVCVideoSupported() === false && Utils.isFirefox() === true">
                        お使いの Firefox ブラウザでは通信節約モードがサポートされていません。
                    </p>
                </div>
                <v-switch class="settings__item-switch" color="primary" id="video_data_saver_mode" hide-details v-if="network_circuit !== 'モバイル回線時'"
                    v-model="settingsStore.settings.video_data_saver_mode" :disabled="PlayerUtils.isHEVCVideoSupported() === false">
                </v-switch>
                <v-switch class="settings__item-switch" color="primary" id="video_data_saver_mode_cellular" hide-details v-if="network_circuit === 'モバイル回線時'"
                    v-model="settingsStore.settings.video_data_saver_mode_cellular" :disabled="PlayerUtils.isHEVCVideoSupported() === false">
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
    {title: '1080p (60fps) (約4.50GB/h / 平均10.0Mbps)', value: '1080p-60fps'},
    {title: '1080p (約4.50GB/h / 平均10.0Mbps)', value: '1080p'},
    {title: '810p (約2.62GB/h / 平均5.8Mbps)', value: '810p'},
    {title: '720p (約2.18GB/h / 平均4.9Mbps)', value: '720p'},
    {title: '540p (約1.52GB/h / 平均3.4Mbps)', value: '540p'},
    {title: '480p (約1.06GB/h / 平均2.3Mbps)', value: '480p'},
    {title: '360p (約0.60GB/h / 平均1.3Mbps)', value: '360p'},
    {title: '240p (約0.35GB/h / 平均0.8Mbps)', value: '240p'},
];

const QUALITY_H265 = [
    {title: '1080p (60fps) (約1.80GB/h / 平均4.0Mbps)', value: '1080p-60fps'},
    {title: '1080p (約1.37GB/h / 平均3.0Mbps)', value: '1080p'},
    {title: '810p (約1.05GB/h / 平均2.3Mbps)', value: '810p'},
    {title: '720p (約0.82GB/h / 平均1.8Mbps)', value: '720p'},
    {title: '540p (約0.53GB/h / 平均1.2Mbps)', value: '540p'},
    {title: '480p (約0.46GB/h / 平均1.0Mbps)', value: '480p'},
    {title: '360p (約0.30GB/h / 平均0.7Mbps)', value: '360p'},
    {title: '240p (約0.20GB/h / 平均0.4Mbps)', value: '240p'},
];

export default defineComponent({
    name: 'Settings-Quality',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            PlayerUtils: Object.freeze(PlayerUtils),

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // タブの状態管理
            tab: null as number | null,

            // ネットワーク回線の種類
            network_circuits: ['Wi-Fi 回線時', 'モバイル回線時'],

            // テレビのデフォルトのストリーミング画質の選択肢
            tv_streaming_quality: QUALITY_H264,
            tv_streaming_quality_cellular: QUALITY_H264,

            // ビデオのデフォルトのストリーミング画質の選択肢
            video_streaming_quality: QUALITY_H264,
            video_streaming_quality_cellular: QUALITY_H264,
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
    },
    watch: {
        'settingsStore.settings.tv_data_saver_mode': {
            immediate: true,
            handler(value: boolean) {
                if (value === true) {
                    this.tv_streaming_quality = QUALITY_H265;
                } else {
                    this.tv_streaming_quality = QUALITY_H264;
                }
            },
        },
        'settingsStore.settings.tv_data_saver_mode_cellular': {
            immediate: true,
            handler(value: boolean) {
                if (value === true) {
                    this.tv_streaming_quality_cellular = QUALITY_H265;
                } else {
                    this.tv_streaming_quality_cellular = QUALITY_H264;
                }
            },
        },
        'settingsStore.settings.video_data_saver_mode': {
            immediate: true,
            handler(value: boolean) {
                if (value === true) {
                    this.video_streaming_quality = QUALITY_H265;
                } else {
                    this.video_streaming_quality = QUALITY_H264;
                }
            },
        },
        'settingsStore.settings.video_data_saver_mode_cellular': {
            immediate: true,
            handler(value: boolean) {
                if (value === true) {
                    this.video_streaming_quality_cellular = QUALITY_H265;
                } else {
                    this.video_streaming_quality_cellular = QUALITY_H264;
                }
            },
        },
    },
    created() {
        // 通信節約モードならストリーミング画質の選択肢を H.265 にする
        if (this.settingsStore.settings.tv_data_saver_mode === true) {
            this.tv_streaming_quality = QUALITY_H265;
        }
        if (this.settingsStore.settings.tv_data_saver_mode_cellular === true) {
            this.tv_streaming_quality_cellular = QUALITY_H265;
        }
        if (this.settingsStore.settings.video_data_saver_mode === true) {
            this.video_streaming_quality = QUALITY_H265;
        }
        if (this.settingsStore.settings.video_data_saver_mode_cellular === true) {
            this.video_streaming_quality_cellular = QUALITY_H265;
        }
    }
});

</script>
<style lang="scss" scoped>

.settings__tab {
    position: sticky;
    top: 65px;
    z-index: 4;
    background-color: rgb(var(--v-theme-background-lighten-1)) !important;
    @include smartphone-horizontal {
        top: 0px;
    }
    @include smartphone-vertical {
        top: 60px;
        background-color: rgb(var(--v-theme-background)) !important;
    }

    .v-tab {
        letter-spacing: 0.0892857143em !important;
    }
}

</style>