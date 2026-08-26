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
                <div class="settings__item-label mt-2">
                    画質を [Original (MPEG-2)] に設定すると、<b>放送波の MPEG-2 を再エンコードせず直接 60fps で再生できます！</b><br>
                    <b>再生遅延・選局待ち時間・サーバー負荷を大幅に削減できるため、家の Wi-Fi で観るときにおすすめです。</b><br>
                    （ ⚠️ 最大 20Mbps の TS を直接ストリーミングするため、屋外で使うとパケ代が大変なことになります）<br>
                    実験的機能のため、微妙にカクついたり、低スペックな端末では再生が重くなる可能性があります。<br>
                </div>
                <div class="settings__item-label mt-2">
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
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" :for="`tv_24fps_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    テレビを 24fps モードで視聴する
                </label>
                <label class="settings__item-label" :for="`tv_24fps_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    映画やアニメなど 24fps で制作された映像を検出し、本来の動きに近づけます。<br>
                    画質で [1080p (60fps)] を選択している場合は、常に 60fps が優先されます。<br>
                </label>
                <div class="settings__item-label mt-1">
                    CM やニュースなど 30fps の区間は基本的にそのまま再生されます。テロップなど一部の映像では効果が安定しないことがあります。サーバーのエンコード設定によっては利用できません。<br>
                </div>
                <div class="settings__item-label mt-1">
                    画質で [Original (MPEG-2)] を選択している場合は、若干描画が不安定になる可能性があります。<br>
                </div>
                <v-switch class="settings__item-switch" color="primary" id="tv_24fps_mode" hide-details v-if="network_circuit !== 'モバイル回線時'"
                    v-model="settingsStore.settings.tv_24fps_mode">
                </v-switch>
                <v-switch class="settings__item-switch" color="primary" id="tv_24fps_mode_cellular" hide-details v-if="network_circuit === 'モバイル回線時'"
                    v-model="settingsStore.settings.tv_24fps_mode_cellular">
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
                <div class="settings__item-label mt-2">
                    画質を [Original (MPEG-2)] に設定すると、<b>録画 TS の MPEG-2 を再エンコードせず直接 60fps で再生できます！</b><br>
                    <b>シーク待ち時間とサーバー負荷を大幅に削減できるため、家の Wi-Fi で観るときにおすすめです。</b><br>
                    （ ⚠️ 数 GB ある録画ファイルを直接ストリーミングするため、屋外で使うとパケ代が大変なことになります）<br>
                </div>
                <div class="settings__item-label mt-1">
                    現時点では H.264 / HEVC 録画の直接再生には対応していません。デフォルト画質を [Original (MPEG-2)] にしていても、該当録画では自動的に 1080p (60fps) / 1080p (24fps モード有効時) が選択されます。<br>
                    実験的機能のため、微妙にカクついたり、低スペックな端末では再生が重くなる可能性があります。<br>
                </div>
                <div class="settings__item-label mt-2">
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
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" :for="`video_24fps_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    ビデオを 24fps モードで再生する
                </label>
                <label class="settings__item-label" :for="`video_24fps_mode${network_circuit === 'モバイル回線時' ? '_cellular' : ''}`">
                    映画やアニメなど 24fps で制作された映像を検出し、本来の動きに近づけます。<br>
                    画質で [1080p (60fps)] を選択している場合は、常に 60fps が優先されます。<br>
                </label>
                <div class="settings__item-label mt-1">
                    CM やニュースなど 30fps の区間は基本的にそのまま再生されます。テロップなど一部の映像では効果が安定しないことがあります。サーバーのエンコード設定によっては利用できません。<br>
                </div>
                <div class="settings__item-label mt-1">
                    画質で [Original (MPEG-2)] を選択している場合は、若干描画が不安定になる可能性があります。<br>
                </div>
                <v-switch class="settings__item-switch" color="primary" id="video_24fps_mode" hide-details v-if="network_circuit !== 'モバイル回線時'"
                    v-model="settingsStore.settings.video_24fps_mode">
                </v-switch>
                <v-switch class="settings__item-switch" color="primary" id="video_24fps_mode_cellular" hide-details v-if="network_circuit === 'モバイル回線時'"
                    v-model="settingsStore.settings.video_24fps_mode_cellular">
                </v-switch>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import Message from '@/message';
import useSettingsStore, { LiveStreamingQuality, VideoStreamingQuality } from '@/stores/SettingsStore';
import Utils, { PlayerUtils } from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

type QualitySelectItem = {
    title: string;
    value: LiveStreamingQuality | VideoStreamingQuality;
    props?: { disabled: boolean };
};

const QUALITY_H264: QualitySelectItem[] = [
    {title: 'Original (MPEG-2) (約7.65GB/h / 平均17.0Mbps)', value: 'original'},
    {title: '1080p (60fps) (約4.50GB/h / 平均10.0Mbps)', value: '1080p-60fps'},
    {title: '1080p (約4.50GB/h / 平均10.0Mbps)', value: '1080p'},
    {title: '810p (約2.62GB/h / 平均5.8Mbps)', value: '810p'},
    {title: '720p (約2.18GB/h / 平均4.9Mbps)', value: '720p'},
    {title: '540p (約1.52GB/h / 平均3.4Mbps)', value: '540p'},
    {title: '480p (約1.06GB/h / 平均2.3Mbps)', value: '480p'},
    {title: '360p (約0.60GB/h / 平均1.3Mbps)', value: '360p'},
    {title: '240p (約0.35GB/h / 平均0.8Mbps)', value: '240p'},
];

// 通信節約モード (H.265 / HEVC) 時のビットレート表示用
const QUALITY_H265_TITLES: Record<Exclude<LiveStreamingQuality | VideoStreamingQuality, 'original'>, string> = {
    '1080p-60fps': '1080p (60fps) (約1.80GB/h / 平均4.0Mbps)',
    '1080p': '1080p (約1.37GB/h / 平均3.0Mbps)',
    '810p': '810p (約1.05GB/h / 平均2.3Mbps)',
    '720p': '720p (約0.82GB/h / 平均1.8Mbps)',
    '540p': '540p (約0.53GB/h / 平均1.2Mbps)',
    '480p': '480p (約0.46GB/h / 平均1.0Mbps)',
    '360p': '360p (約0.30GB/h / 平均0.7Mbps)',
    '240p': '240p (約0.20GB/h / 平均0.4Mbps)',
};

// 通信節約モードオン時に Original 画質と矛盾しないよう、1080p (60fps) へ自動切り替えした際の告知文
const DATA_SAVER_ORIGINAL_AUTO_SWITCH_MESSAGE =
    '通信節約モードは Original (MPEG-2) 画質に対応していません。\n画質を 1080p (60fps) に自動で切り替えました。';

// モバイル回線プロファイルで Original 画質を選択した際の警告文
const MOBILE_ORIGINAL_QUALITY_WARNING_MESSAGE =
    'Original (MPEG-2) 画質は再エンコードなしでそのまま配信するため、通信量が非常に多くなります。\nモバイル回線で屋外から視聴する際は、通信量に十分ご注意ください。';

/**
 * 通信節約モードの状態に応じた画質選択肢を生成する
 * 通信節約モードオン時は H.265 のビットレート表記を使い、Original (MPEG-2) は disabled 状態で表示する
 */
function buildQualityItems(data_saver_mode: boolean): QualitySelectItem[] {
    if (data_saver_mode === false) {
        return QUALITY_H264;
    }

    return QUALITY_H264.map((item) => {
        if (item.value === 'original') {
            return {
                ...item,
                props: { disabled: true },
            };
        }

        return {
            title: QUALITY_H265_TITLES[item.value],
            value: item.value,
        };
    });
}

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
        };
    },
    computed: {
        ...mapStores(useSettingsStore),

        // テレビのデフォルトのストリーミング画質の選択肢
        tv_streaming_quality(): QualitySelectItem[] {
            return buildQualityItems(this.settingsStore.settings.tv_data_saver_mode);
        },
        tv_streaming_quality_cellular(): QualitySelectItem[] {
            return buildQualityItems(this.settingsStore.settings.tv_data_saver_mode_cellular);
        },

        // ビデオのデフォルトのストリーミング画質の選択肢
        video_streaming_quality(): QualitySelectItem[] {
            return buildQualityItems(this.settingsStore.settings.video_data_saver_mode);
        },
        video_streaming_quality_cellular(): QualitySelectItem[] {
            return buildQualityItems(this.settingsStore.settings.video_data_saver_mode_cellular);
        },
    },
    watch: {
        'settingsStore.settings.tv_data_saver_mode': {
            immediate: true,
            handler(value: boolean) {
                this.ensureQualityCompatibleWithDataSaverMode('tv', value);
            },
        },
        'settingsStore.settings.tv_data_saver_mode_cellular': {
            immediate: true,
            handler(value: boolean) {
                this.ensureQualityCompatibleWithDataSaverMode('tv_cellular', value);
            },
        },
        'settingsStore.settings.video_data_saver_mode': {
            immediate: true,
            handler(value: boolean) {
                this.ensureQualityCompatibleWithDataSaverMode('video', value);
            },
        },
        'settingsStore.settings.video_data_saver_mode_cellular': {
            immediate: true,
            handler(value: boolean) {
                this.ensureQualityCompatibleWithDataSaverMode('video_cellular', value);
            },
        },
        'settingsStore.settings.tv_streaming_quality_cellular'(value: LiveStreamingQuality, old_value: LiveStreamingQuality | undefined) {
            this.notifyMobileOriginalQualityWarning(value, old_value, this.settingsStore.settings.tv_data_saver_mode_cellular);
        },
        'settingsStore.settings.video_streaming_quality_cellular'(value: VideoStreamingQuality, old_value: VideoStreamingQuality | undefined) {
            this.notifyMobileOriginalQualityWarning(value, old_value, this.settingsStore.settings.video_data_saver_mode_cellular);
        },
    },
    methods: {

        /**
         * 通信節約モードオン時に Original 画質が選択されていた場合、1080p (60fps) へ自動切り替えする
         * @param target 画質設定の対象
         * @param data_saver_mode 通信節約モードがオンかどうか
         */
        ensureQualityCompatibleWithDataSaverMode(
            target: 'tv' | 'tv_cellular' | 'video' | 'video_cellular',
            data_saver_mode: boolean,
        ): void {
            if (data_saver_mode === false) {
                return;
            }

            const setting_key_map = {
                tv: 'tv_streaming_quality',
                tv_cellular: 'tv_streaming_quality_cellular',
                video: 'video_streaming_quality',
                video_cellular: 'video_streaming_quality_cellular',
            } as const;
            const setting_key = setting_key_map[target];

            if (this.settingsStore.settings[setting_key] !== 'original') {
                return;
            }

            this.settingsStore.settings[setting_key] = '1080p-60fps';
            Message.warning(DATA_SAVER_ORIGINAL_AUTO_SWITCH_MESSAGE, 10);  // 10秒表示
        },

        /**
         * モバイル回線プロファイルで通信節約モードオフの状態から Original 画質が選ばれた際に警告を表示する
         * @param value 新しい画質
         * @param old_value 以前の画質
         * @param data_saver_mode 通信節約モードがオンかどうか
         */
        notifyMobileOriginalQualityWarning(
            value: LiveStreamingQuality | VideoStreamingQuality,
            old_value: LiveStreamingQuality | VideoStreamingQuality | undefined,
            data_saver_mode: boolean,
        ): void {
            if (data_saver_mode === true) {
                return;
            }
            if (value !== 'original') {
                return;
            }
            // 通信節約モードオン時の自動切り替え (original → 1080p-60fps) では警告しない
            if (old_value === undefined || old_value === 'original') {
                return;
            }

            Message.warning(MOBILE_ORIGINAL_QUALITY_WARNING_MESSAGE, 10);  // 10秒表示
        },
    },
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