<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </a>
            <Icon icon="fluent:image-multiple-16-filled" width="26px" />
            <span class="ml-2">キャプチャ</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">キャプチャの保存先</div>
                <div class="settings__item-label">
                    <p>
                        [ブラウザでダウンロード] に設定すると、視聴中のデバイスのダウンロードフォルダに保存されます。<br>
                        視聴中のデバイスにそのまま保存されるためシンプルですが、保存先のフォルダを変更できないこと、iOS Safari (PWA モード) ではダウンロードするとファイル概要画面が表示されて視聴に支障することがデメリットです (将来的には、iOS / Android アプリ版や拡張機能などで解消される予定) 。<br>
                    </p>
                    <p>
                        [KonomiTV サーバーにアップロード] に設定すると、サーバー設定で指定されたキャプチャ保存フォルダに保存されます。視聴したデバイスにかかわらず、今までに撮ったキャプチャをひとつのフォルダにまとめて保存できます。<br>
                        他のデバイスでキャプチャを見るにはキャプチャ保存フォルダをネットワークに共有する必要があること、スマホ・タブレットではネットワーク上のフォルダへのアクセスがやや面倒なことがデメリットです。(将来的には、保存フォルダ内のキャプチャを Google フォトのように表示する機能を追加予定)<br>
                    </p>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="capture_save_mode" v-model="settingsStore.settings.capture_save_mode">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">字幕表示時のキャプチャの保存モード</div>
                <div class="settings__item-label">
                    字幕表示時、キャプチャした画像に字幕を合成するかを設定します。<br>
                    映像のみのキャプチャと、字幕を合成したキャプチャを両方同時に保存することもできます。<br>
                    なお、字幕非表示時は、常に映像のみ (+コメント付きキャプチャではコメントを合成して) 保存されます。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="capture_caption_mode" v-model="settingsStore.settings.capture_caption_mode">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">キャプチャの保存ファイル名パターン</div>
                <div class="settings__item-label">
                    キャプチャの保存ファイル名パターン（拡張子なし）を設定します。デフォルトは Capture_%date%-%time% です。<br>
                    字幕を合成したキャプチャのファイル名には、自動的に _caption のサフィックスが追加されます。<br>
                    ファイル名には、下記の TVTest 互換マクロ（一部）を使用できます。<br>
                    <ul class="ml-4 mt-1">
                        <li>%date%: 現在日時 - 年月日 (YYYYMMDD)</li>
                        <li>%time%: 現在日時 - 時分秒 (HHMMSS)</li>
                    </ul>
                </div>
                <v-text-field class="settings__item-form mt-5" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :label="capture_filename_pattern_preview"
                    v-model="settingsStore.settings.capture_filename_pattern">
                </v-text-field>
            </div>
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="capture_copy_to_clipboard">キャプチャをクリップボードにコピーする</label>
                <label class="settings__item-label" for="capture_copy_to_clipboard">
                    この設定をオンにすると、撮ったキャプチャ画像がクリップボードにもコピーされます。<br>
                    クリップボードの履歴をサポートしていない環境では、この設定をオンにしてキャプチャを撮ると、以前のクリップボードが上書きされます。注意してください。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="capture_copy_to_clipboard" hide-details
                    v-model="settingsStore.settings.capture_copy_to_clipboard">
                </v-switch>
            </div>
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import CaptureManager from '@/services/player/managers/CaptureManager';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default defineComponent({
    name: 'Settings-Capture',
    components: {
        SettingsBase,
    },
    data() {
        return {

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // キャプチャの保存先の選択肢
            capture_save_mode: [
                {title: 'ブラウザでダウンロード', value: 'Browser'},
                {title: 'KonomiTV サーバーにアップロード', value: 'UploadServer'},
                {title: 'ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う', value: 'Both'},
            ],

            // 字幕が表示されているときのキャプチャの保存モードの選択肢
            capture_caption_mode: [
                {title: '映像のみのキャプチャを保存する', value: 'VideoOnly'},
                {title: '字幕を合成したキャプチャを保存する', value: 'CompositingCaption'},
                {title: '映像のみのキャプチャと、字幕を合成したキャプチャを両方保存する', value: 'Both'},
            ],

            // キャプチャの保存ファイル名パターンのプレビュー
            capture_filename_pattern_preview: '',
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
    },
    watch: {
        'settingsStore.settings.capture_filename_pattern': {
            handler() {
                this.capture_filename_pattern_preview = `プレビュー: ${CaptureManager.generateCaptureFilename()}.jpg`;
            },
            immediate: true,
        },
    }
});

</script>