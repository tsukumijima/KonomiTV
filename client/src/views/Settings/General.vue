<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <Icon icon="fa-solid:sliders-h" width="19px" />
            <span class="ml-3">全般</span>
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
                    [1080p (60fps)] で視聴するときは、環境設定の [利用するエンコーダー] をハードウェアエンコーダーに設定してください。FFmpeg (ソフトウェアエンコーダー) では、再生に支障が出ることがあります。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tv_streaming_quality" v-model="settingsStore.settings.tv_streaming_quality">
                </v-select>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled"
                :class="{'settings__item--disabled': PlayerUtils.isHEVCVideoSupported() === false}">
                <label class="settings__item-heading" for="tv_data_saver_mode">テレビを通信節約モードで視聴する</label>
                <label class="settings__item-label" for="tv_data_saver_mode">
                    通信節約モードでは、H.265 / HEVC という圧縮率の高いコーデックを使い、画質はほぼそのまま、通信量を通常の 2/3 程度に抑えながら視聴できます！<br>
                    通信節約モードで視聴するときは、環境設定の [利用するエンコーダー] をハードウェアエンコーダーに設定してください。FFmpeg (ソフトウェアエンコーダー) では、再生に支障が出る可能性が高いです。<br>
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
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">デフォルトのパネルの表示状態</div>
                <div class="settings__item-label">
                    視聴画面を開いたときに、右側のパネルをどう表示するかを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="panel_display_state" v-model="settingsStore.settings.panel_display_state">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">テレビをみるときにデフォルトで表示されるパネルのタブ</div>
                <div class="settings__item-label">
                    テレビの視聴画面を開いたときに、右側のパネルで最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details :dense="is_form_dense"
                    :items="tv_panel_active_tab" v-model="settingsStore.settings.tv_panel_active_tab">
                </v-select>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="tv_show_superimpose">チャンネル選局のキーボードショートカットを {{Utils.AltOrOption()}} + 数字キー/テンキーに変更する</label>
                <label class="settings__item-label" for="tv_show_superimpose">
                    この設定をオンにすると、数字キーまたはテンキーに対応するリモコン番号（1～12）のチャンネルに切り替える際、{{Utils.AltOrOption()}} キーを同時に押す必要があります。<br>
                    コメントやツイートを入力しようとして誤って数字キーを押してしまい、チャンネルが変わってしまう事態を避けたい方におすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" id="tv_show_superimpose" inset hide-details
                    v-model="settingsStore.settings.tv_channel_selection_requires_alt_key">
                </v-switch>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">設定をエクスポート</div>
                <div class="settings__item-label">
                    このデバイス（ブラウザ）に保存されている設定データを、エクスポート（ダウンロード）できます。<br>
                    ダウンロードした設定データ (KonomiTV-Settings.json) は、[設定をインポート] からインポートできます。異なるサーバーの KonomiTV を同じ設定で使いたいときなどに使ってください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" depressed @click="exportSettings()">
                <Icon icon="fa6-solid:download" class="mr-3" height="19px" />設定をエクスポート
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading error--text text--lighten-1">設定をインポート</div>
                <div class="settings__item-label">
                    [設定をエクスポート] でダウンロードした設定データを、このデバイス（ブラウザ）にインポートできます。<br>
                    設定をインポートすると、<b>現在のデバイス設定はすべて上書きされます。</b>元に戻すことはできません。<br>
                    設定のデバイス間同期がオンのときは、<b>同期が有効なすべてのデバイスに反映されます。</b>十分ご注意ください。<br>
                </div>
                <v-file-input class="settings__item-form" outlined hide-details placeholder="設定データ (KonomiTV-Settings.json) を選択"
                    :dense="is_form_dense"
                    accept="application/json"
                    prepend-icon=""
                    prepend-inner-icon="mdi-paperclip"
                    v-model="import_settings_file">
                </v-file-input>
            </div>
            <v-btn class="settings__save-button error mt-5" depressed @click="importSettings()">
                <Icon icon="fa6-solid:upload" class="mr-3" height="19px" />設定をインポート
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading error--text text--lighten-1">設定を初期状態にリセット</div>
                <div class="settings__item-label">
                    このデバイス（ブラウザ）に保存されている設定データを、初期状態のデフォルト値にリセットできます。<br>
                    設定をリセットすると、元に戻すことはできません。<br>
                    設定のデバイス間同期がオンのときは、<b>同期が有効なすべてのデバイスに反映されます。</b>十分ご注意ください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button error mt-5" depressed @click="resetSettings()">
                <Icon icon="material-symbols:device-reset-rounded" class="mr-2" height="23px" />設定をリセット
            </v-btn>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import useSettingsStore from '@/store/SettingsStore';
import Utils, { PlayerUtils } from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default Vue.extend({
    name: 'Settings-General',
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
            tv_streaming_quality: [
                {'text': '1080p (60fps) （約3.24GB/h / 平均7.2Mbps）', 'value': '1080p-60fps'},
                {'text': '1080p （約2.31GB/h / 平均5.1Mbps）', 'value': '1080p'},
                {'text': '810p （約1.92GB/h / 平均4.2Mbps）', 'value': '810p'},
                {'text': '720p （約1.33GB/h / 平均3.0Mbps）', 'value': '720p'},
                {'text': '540p （約1.00GB/h / 平均2.2Mbps）', 'value': '540p'},
                {'text': '480p （約0.74GB/h / 平均1.6Mbps）', 'value': '480p'},
                {'text': '360p （約0.40GB/h / 平均0.9Mbps）', 'value': '360p'},
                {'text': '240p （約0.23GB/h / 平均0.5Mbps）', 'value': '240p'},
            ],

            // デフォルトのパネルの表示状態の選択肢
            panel_display_state: [
                {'text': '前回の状態を復元する', 'value': 'RestorePreviousState'},
                {'text': '常に表示する', 'value': 'AlwaysDisplay'},
                {'text': '常に折りたたむ', 'value': 'AlwaysFold'},
            ],

            // テレビをみるときにデフォルトで表示されるパネルのタブの選択肢
            tv_panel_active_tab: [
                {'text': '番組情報タブ', 'value': 'Program'},
                {'text': 'チャンネルタブ', 'value': 'Channel'},
                {'text': 'コメントタブ', 'value': 'Comment'},
                {'text': 'Twitter タブ', 'value': 'Twitter'},
            ],

            // 選択された設定データ (KonomiTV-Settings.json) が入る
            import_settings_file: null as File | null,
        };
    },
    computed: {
        // SettingsStore に this.settingsStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useSettingsStore),
    },
    methods: {

        // 設定データをエクスポートする
        exportSettings() {

            // 設定データを JSON 化して取得
            const settings_json = JSON.stringify(this.settingsStore.settings, null, 4);

            // ダウンロードさせるために一旦 Blob にしてから、KonomiTV-Settings.json としてダウンロード
            const settings_json_blob = new Blob([settings_json], {type: 'application/json'});
            Utils.downloadBlobData(settings_json_blob, 'KonomiTV-Settings.json');
            this.$message.success('設定をエクスポートしました。');
        },

        // 設定データをインポートする
        async importSettings() {

            // 設定データが選択されていないときは実行しない
            if (this.import_settings_file === null) {
                this.$message.error('インポートする設定データを選択してください！');
                return;
            }

            // 設定データのインポートを実行
            const result = await this.settingsStore.importClientSettings(this.import_settings_file);
            if (result === true) {
                this.$message.success('設定をインポートしました。');
                window.setTimeout(() => this.$router.go(0), 300);
            } else {
                this.$message.error('設定データが不正なため、インポートできませんでした。');
            }
        },

        // 設定データをリセットする
        async resetSettings() {
            await this.settingsStore.resetClientSettings();
            this.$message.success('設定をリセットしました。');
            window.setTimeout(() => this.$router.go(0), 300);
        },
    }
});

</script>