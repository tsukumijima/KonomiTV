<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <Base>
        <h2 class="settings__heading">
            <Icon icon="fa-solid:sliders-h" width="19px" />
            <span class="ml-3">全般</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">テレビのストリーミング画質</div>
                <div class="settings__item-label">
                    テレビをライブストリーミングする際の既定の画質を設定します。<br>
                    ストリーミング画質はプレイヤーの設定からいつでも切り替えられます。<br>
                </div>
                <div class="settings__item-label">
                    [1080p (60fps)] は、通常 30fps (60i) の映像を補間することで、ほかの画質よりも滑らか（ぬるぬる）な映像で再生できます。ただし、再生負荷が少し高くなります。<br>
                    [1080p (60fps)] で視聴するときは、QSVEncC / NVEncC / VCEEncC エンコーダーの利用をおすすめします。FFmpeg エンコーダーでは CPU 使用率が高くなり、再生に支障が出ることがあります。br>
                </div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="tv_streaming_quality" v-model="settings.tv_streaming_quality">
                </v-select>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="low_latency_mode">テレビを低遅延で視聴する</label>
                <label class="settings__item-label" for="low_latency_mode">
                    テレビをライブストリーミングする際に、低遅延で視聴するかを設定します。<br>
                    低遅延ストリーミングがオンのときは、約 2 秒以上遅延したときに少しだけ再生速度を早める (1.15x) ことで、滑らかにストリーミングの遅れを取り戻します。<br>
                    宅外視聴などのネットワークが不安定になりがちな環境では、一度低遅延ストリーミングをオフにしてみると、映像のカクつきを改善できるかもしれません。<br>
                </label>
                <v-switch class="settings__item-switch" id="low_latency_mode" inset hide-details
                    v-model="settings.low_latency_mode">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="show_superimpose_tv">テレビをみるときに文字スーパーを表示する</label>
                <label class="settings__item-label" for="show_superimpose_tv">
                    テレビをライブストリーミングする際に、文字スーパーを表示するかを設定します。<br>
                    文字スーパーは、緊急地震速報の赤テロップや、NHK BS のニュース速報のテロップなどで利用されています。とくに理由がなければ、オンのままにしておくことをおすすめします。<br>
                </label>
                <v-switch class="settings__item-switch" id="show_superimpose_tv" inset hide-details
                    v-model="settings.show_superimpose_tv">
                </v-switch>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">既定のパネルの表示状態</div>
                <div class="settings__item-label">
                    視聴画面を開いたときに、右側のパネルをどう表示するかを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="panel_display_state" v-model="settings.panel_display_state">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">テレビをみるときに既定で表示されるパネルのタブ</div>
                <div class="settings__item-label">
                    テレビの視聴画面を開いたときに、右側のパネルで最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="tv_panel_active_tab" v-model="settings.tv_panel_active_tab">
                </v-select>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">キャプチャの保存先</div>
                <div class="settings__item-label">
                    <p>
                        キャプチャした画像をブラウザでダウンロードするか、KonomiTV サーバーにアップロードするかを設定します。<br>
                        ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方同時に行うこともできます。<br>
                    </p>
                    <p>
                        ブラウザでダウンロードすると、視聴中のデバイスのダウンロードフォルダに保存されます。<br>
                        視聴中のデバイスにそのまま保存されるためシンプルですが、保存先のフォルダを変更できないこと、PC 版 Chrome では毎回ダウンロードバーが表示されてしまうことがデメリットです。<br>
                    </p>
                    <p>
                        KonomiTV サーバーにアップロードすると、環境設定で指定されたキャプチャ保存フォルダに保存されます。視聴したデバイスにかかわらず、今までに撮ったキャプチャをひとつのフォルダにまとめて保存できます。<br>
                        他のデバイスでキャプチャを見るにはキャプチャ保存フォルダをネットワークに共有する必要があること、スマホ・タブレットではネットワーク上のフォルダへのアクセスがやや面倒なことがデメリットです。<br>
                    </p>
                </div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="capture_save_mode" v-model="settings.capture_save_mode">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">字幕が表示されているときのキャプチャの保存モード</div>
                <div class="settings__item-label">
                    字幕が表示されているときに、キャプチャした画像に字幕を合成するかを設定します。<br>
                    映像のみのキャプチャと、字幕を合成したキャプチャを両方同時に保存することもできます。<br>
                </div>
                <v-select class="settings__item-form" outlined hide-details
                    :items="capture_caption_mode" v-model="settings.capture_caption_mode">
                </v-select>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item mt-6">
                <div class="settings__item-heading">設定をエクスポート</div>
                <div class="settings__item-label">
                    このデバイス（ブラウザ）に保存されている設定データをエクスポート（ダウンロード）できます。<br>
                    ダウンロードした設定データ (KonomiTV-Settings.json) は、[設定をインポート] からインポートできます。異なるサーバーの KonomiTV を同じ設定で使いたいときなどに使ってください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" depressed @click="exportSettings()">
                <Icon icon="fa6-solid:download" class="mr-3" height="19px" />設定をエクスポート
            </v-btn>
            <div class="settings__item mt-6">
                <div class="settings__item-heading error--text text--lighten-1">設定をインポート</div>
                <div class="settings__item-label">
                    [設定をエクスポート] でダウンロードした設定データを、このデバイス（ブラウザ）にインポートできます。<br>
                    設定をインポートすると、それまでこのデバイス（ブラウザ）に保存されていた設定が、すべてインポート先の設定データで上書きされます。元に戻すことはできません。
                </div>
                <v-file-input class="settings__item-form" outlined hide-details placeholder="設定データ (KonomiTV-Settings.json) を選択"
                    accept="application/json"
                    prepend-icon=""
                    prepend-inner-icon="mdi-paperclip"
                    v-model="import_settings_file">
                </v-file-input>
            </div>
            <v-btn class="settings__save-button error mt-5" depressed @click="importSettings()">
                <Icon icon="fa6-solid:upload" class="mr-3" height="19px" />設定をインポート
            </v-btn>
        </div>
    </Base>
</template>
<script lang="ts">

import Vue from 'vue';

import Base from '@/views/Settings/Base.vue';
import Utils from '@/utils';

export default Vue.extend({
    name: 'Settings-General',
    components: {
        Base,
    },
    data() {
        return {

            // テレビのストリーミング画質の選択肢
            tv_streaming_quality: [
                {'text': '1080p (60fps) （1時間あたり約3.24GB / 7.2Mbps）', 'value': '1080p-60fps'},
                {'text': '1080p （1時間あたり約2.31GB / 5.1Mbps）', 'value': '1080p'},
                {'text': '810p （1時間あたり約1.92GB / 4.2Mbps）', 'value': '810p'},
                {'text': '720p （1時間あたり約1.33GB / 3.0Mbps）', 'value': '720p'},
                {'text': '540p （1時間あたり約1.00GB / 2.2Mbps）', 'value': '540p'},
                {'text': '480p （1時間あたり約0.74GB / 1.6Mbps）', 'value': '480p'},
                {'text': '360p （1時間あたり約0.40GB / 0.9Mbps）', 'value': '360p'},
                {'text': '240p （1時間あたり約0.23GB / 0.5Mbps）', 'value': '240p'},
            ],

            // 既定のパネルの表示状態の選択肢
            panel_display_state: [
                {'text': '前回の状態を復元する', 'value': 'RestorePreviousState'},
                {'text': '常に表示する', 'value': 'AlwaysDisplay'},
                {'text': '常に折りたたむ', 'value': 'AlwaysFold'},
            ],

            // テレビをみるときに既定で表示されるパネルのタブの選択肢
            tv_panel_active_tab: [
                {'text': '番組情報タブ', 'value': 'Program'},
                {'text': 'チャンネルタブ', 'value': 'Channel'},
                {'text': 'コメントタブ', 'value': 'Comment'},
                {'text': 'Twitter タブ', 'value': 'Twitter'},
            ],

            // キャプチャの保存先
            capture_save_mode: [
                {'text': 'ブラウザでダウンロード', 'value': 'Browser'},
                {'text': 'KonomiTV サーバーにアップロード', 'value': 'UploadServer'},
                {'text': 'ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う', 'value': 'Both'},
            ],

            // 字幕が表示されているときのキャプチャの保存モードの選択肢
            capture_caption_mode: [
                {'text': '映像のみのキャプチャを保存する', 'value': 'VideoOnly'},
                {'text': '字幕を合成したキャプチャを保存する', 'value': 'CompositingCaption'},
                {'text': '映像のみのキャプチャと、字幕を合成したキャプチャを両方保存する', 'value': 'Both'},
            ],

            // 選択された設定データ (KonomiTV-Settings.json) が入る
            import_settings_file: null as File | null,

            // 設定値が保存されるオブジェクト
            // ここの値とフォームを v-model で binding する
            settings: (() => {
                // 現在の設定値を取得する
                const settings = {}
                const settings_keys = [
                    'tv_streaming_quality',
                    'low_latency_mode',
                    'show_superimpose_tv',
                    'panel_display_state',
                    'tv_panel_active_tab',
                    'capture_save_mode',
                    'capture_caption_mode',
                ];
                for (const setting_key of settings_keys) {
                    settings[setting_key] = Utils.getSettingsItem(setting_key);
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
    },
    methods: {

        // 設定データをエクスポートする
        exportSettings() {

            // JSON のままの設定データを LocalStorage から直に取得
            // "KonomiTV-Settings" キーがないときはデフォルト設定を JSON 化したものを入れる
            const settings_json = localStorage.getItem('KonomiTV-Settings') || JSON.stringify(Utils.default_settings);

            // ダウンロードさせるために Blob にしてから、KonomiTV-Settings.json としてダウンロード
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

            try {

                // 選択された設定データの JSON を取得してデコード
                // そのまま突っ込んでもいいんだけど、念のため一度オブジェクトになおしておく
                const settings = JSON.parse(await this.import_settings_file.text());

                // LocalStorage に直に保存
                // このとき、既存の設定データはすべて上書きされる
                localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));

                // 設定データをサーバーに同期する
                await Utils.syncClientSettingsToServer();

                // 設定を適用するためリロード
                this.$message.success('設定をインポートしました。');
                window.setTimeout(() => this.$router.go(0), 300);

            } catch (error) {
                this.$message.error('設定データが不正なため、インポートできませんでした。');
                return;
            }
        },
    }
});

</script>