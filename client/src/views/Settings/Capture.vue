<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <router-link v-ripple class="settings__back-button" to="/settings/">
                <Icon icon="fluent:arrow-left-12-filled" width="25px" />
            </router-link>
            <Icon icon="fluent:image-multiple-16-filled" width="26px" />
            <span class="ml-2">キャプチャ</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item settings__item--switch settings__item--sync-disabled">
                <label class="settings__item-heading" for="capture_copy_to_clipboard">キャプチャをクリップボードにコピーする</label>
                <label class="settings__item-label" for="capture_copy_to_clipboard">
                    この設定をオンにすると、撮ったキャプチャ画像がクリップボードにもコピーされます。<br>
                    クリップボードの履歴をサポートしていない OS では、この設定をオンにしてキャプチャを撮ると、以前のクリップボードが上書きされます。注意してください。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="capture_copy_to_clipboard" hide-details
                    v-model="settingsStore.settings.capture_copy_to_clipboard">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">キャプチャの保存先</div>
                <div class="settings__item-label">
                    <p>
                        キャプチャした画像をブラウザでダウンロードするか、KonomiTV サーバーにアップロードするかを設定します。<br>
                        ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方同時に行うこともできます。<br>
                    </p>
                    <p>
                        ブラウザでダウンロードすると、視聴中のデバイスのダウンロードフォルダに保存されます。<br>
                        視聴中のデバイスにそのまま保存されるためシンプルですが、保存先のフォルダを変更できないこと、iOS Safari (PWA モード) ではダウンロードするとファイル概要画面が表示されて視聴に支障することがデメリットです (将来的には、iOS / Android アプリ版や拡張機能などで解消される予定) 。<br>
                    </p>
                    <p>
                        KonomiTV サーバーにアップロードすると、サーバー設定で指定されたキャプチャ保存フォルダに保存されます。視聴したデバイスにかかわらず、今までに撮ったキャプチャをひとつのフォルダにまとめて保存できます。<br>
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
        </div>
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

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
                {text: 'ブラウザでダウンロード', value: 'Browser'},
                {text: 'KonomiTV サーバーにアップロード', value: 'UploadServer'},
                {text: 'ブラウザでのダウンロードと、KonomiTV サーバーへのアップロードを両方行う', value: 'Both'},
            ],

            // 字幕が表示されているときのキャプチャの保存モードの選択肢
            capture_caption_mode: [
                {text: '映像のみのキャプチャを保存する', value: 'VideoOnly'},
                {text: '字幕を合成したキャプチャを保存する', value: 'CompositingCaption'},
                {text: '映像のみのキャプチャと、字幕を合成したキャプチャを両方保存する', value: 'Both'},
            ],
        };
    },
    computed: {
        ...mapStores(useSettingsStore),
    }
});

</script>