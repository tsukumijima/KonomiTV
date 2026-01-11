<template>
    <!-- ベース画面の中にそれぞれの設定画面で異なる部分を記述する -->
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="fa-solid:sliders-h" width="19px" style="margin: 0 4px;" />
            <span class="ml-3">全般</span>
        </h2>
        <div class="settings__content">
            <div class="settings__item">
                <div class="settings__item-heading">ピン留め中チャンネルの並び替え</div>
                <div class="settings__item-label">
                    ピン留め中のチャンネルの表示順序を変更できます。よくみるチャンネルは先頭に配置しておくと便利です。<br>
                    ピン留め中のチャンネルの追加・削除は、別途 TV ホーム画面のチャンネルリストから行えます。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" variant="flat" @click="pinned_channel_settings_modal = !pinned_channel_settings_modal">
                <Icon icon="iconamoon:sorting-left-bold" height="19px" />
                <span class="ml-1">ピン留め中チャンネルの並び替え設定を開く</span>
            </v-btn>
            <div class="settings__item mt-6">
                <div class="settings__item-heading">番組表の表示設定</div>
                <div class="settings__item-label">
                    番組表のチャンネル名の表示幅、時間軸の表示密度、ジャンル別のハイライト色などを設定できます。<br>
                    番組表ページ上部の設定アイコンからも開くことができます。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" variant="flat" @click="timetable_settings_modal = !timetable_settings_modal">
                <Icon icon="fluent:calendar-ltr-16-regular" height="19px" />
                <span class="ml-1">番組表の表示設定を開く</span>
            </v-btn>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="show_player_background_image">プレイヤーの読み込み中に背景写真を表示する</label>
                <label class="settings__item-label" for="show_player_background_image">
                    プレイヤーの読み込み中にランダムで背景写真を表示できます。デフォルトはオンです。<br>
                    背景写真を表示したくない場合は、この設定をオフにできます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="show_player_background_image" hide-details
                    v-model="settingsStore.settings.show_player_background_image">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="use_pure_black_player_background">プレイヤー表示領域の背景色を完全な黒にする</label>
                <label class="settings__item-label" for="use_pure_black_player_background">
                    映像の上下 or 左右に表示される黒帯の色を、完全な黒に変更できます。デフォルトはオフです。<br>
                    特に有機 EL ディスプレイを搭載したデバイスで、映像の周囲に灰色がかった光が漏れて気になるときは、この設定をオンにすると改善されるかもしれません。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="use_pure_black_player_background" hide-details
                    v-model="settingsStore.settings.use_pure_black_player_background">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="tv_channel_selection_requires_alt_key">チャンネル選局のキーボードショートカットを {{Utils.AltOrOption()}} + 数字キー/テンキーに変更する</label>
                <label class="settings__item-label" for="tv_channel_selection_requires_alt_key">
                    オンにすると、数字キーまたはテンキーに対応するリモコン番号（1～12）のチャンネルに切り替えるとき、{{Utils.AltOrOption()}} キーを同時に押す必要があります。<br>
                    コメントやツイートを入力しようとして誤って数字キーを押してしまい、チャンネルが変わってしまう事態を避けたい方におすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="tv_channel_selection_requires_alt_key" hide-details
                    v-model="settingsStore.settings.tv_channel_selection_requires_alt_key">
                </v-switch>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="use_28hour_clock">時刻を 28 時間表記で表示する</label>
                <label class="settings__item-label" for="use_28hour_clock">
                    深夜番組でよく使われる 28 時間表記 (24 時 〜 27 時) で時刻を表示します。デフォルトはオフです。<br>
                    オンにすると、午前 0 時 〜 3 時が前日の 24 時 〜 27 時と表示され、深夜番組の放送時間がよりわかりやすくなります。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="use_28hour_clock" hide-details
                    v-model="settingsStore.settings.use_28hour_clock">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="show_original_broadcast_time_during_playback">録画番組の再生中に元の放送時刻を表示する</label>
                <label class="settings__item-label" for="show_original_broadcast_time_during_playback">
                    オンにすると、録画番組の再生中に現在時刻ではなく、元の放送時刻を再生位置に合わせて表示します。デフォルトはオフです。<br>
                    元の放送時刻が表示されているときは、タイムシフト再生中であることを示すアイコンが時刻の左側に表示されます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="show_original_broadcast_time_during_playback" hide-details
                    v-model="settingsStore.settings.show_original_broadcast_time_during_playback">
                </v-switch>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">デフォルトのパネルの表示状態</div>
                <div class="settings__item-label">
                    視聴画面を開いたときに、右側のパネルをどう表示するかを設定します。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="panel_display_state" v-model="settingsStore.settings.panel_display_state">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">テレビをみるときにデフォルトで表示されるパネルのタブ</div>
                <div class="settings__item-label">
                    テレビの視聴画面を開いたときに、右側のパネルで最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="tv_panel_active_tab" v-model="settingsStore.settings.tv_panel_active_tab">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">ビデオをみるときにデフォルトで表示されるパネルのタブ</div>
                <div class="settings__item-label">
                    ビデオの視聴画面を開いたときに、右側のパネルで最初に表示されるタブを設定します。<br>
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined" hide-details
                    :density="is_form_dense ? 'compact' : 'default'"
                    :items="video_panel_active_tab" v-model="settingsStore.settings.video_panel_active_tab">
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">視聴履歴の保持件数</div>
                <div class="settings__item-label">
                    録画番組の視聴履歴を何件まで保持するかを設定します。デフォルトは 50 件です。<br>
                    この値を超えると、最も古い視聴履歴から自動的に削除されます。<br>
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined" hide-details
                    type="number" min="1" suffix="件"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model.number="settingsStore.settings.video_watched_history_max_count">
                </v-text-field>
            </div>
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item">
                <div class="settings__item-heading">設定をエクスポート</div>
                <div class="settings__item-label">
                    このデバイス (ブラウザ) に保存されている設定データを、エクスポート (ダウンロード) できます。<br>
                    ダウンロードした設定データ (KonomiTV-Settings.json) は、[設定をインポート] からインポートできます。異なるサーバーの KonomiTV を同じ設定で使いたいときなどに使ってください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button mt-4" variant="flat" @click="exportSettings()">
                <Icon icon="fa6-solid:download" class="mr-3" height="19px" />設定をエクスポート
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading text-error-lighten-1">設定をインポート</div>
                <div class="settings__item-label">
                    [設定をエクスポート] でダウンロードした設定データを、このデバイス (ブラウザ) にインポートできます。<br>
                    <strong class="text-error-lighten-1">設定をインポートすると、現在のデバイス設定はすべて上書きされます。元に戻すことはできません。</strong><br>
                    <strong class="text-error-lighten-1">設定のデバイス間同期がオンのときは、同期が有効なすべてのデバイスに反映されます。</strong>十分ご注意ください。<br>
                </div>
                <v-file-input class="settings__item-form" color="primary" variant="outlined" hide-details
                label="設定データ (KonomiTV-Settings.json) を選択"
                    :density="is_form_dense ? 'compact' : 'default'"
                    accept="application/json"
                    prepend-icon=""
                    prepend-inner-icon="mdi-paperclip"
                    v-model="import_settings_file">
                </v-file-input>
            </div>
            <v-btn class="settings__save-button bg-error mt-5" variant="flat" @click="importSettings()">
                <Icon icon="fa6-solid:upload" class="mr-3" height="19px" />設定をインポート
            </v-btn>
            <div class="settings__item">
                <div class="settings__item-heading text-error-lighten-1">設定を初期状態にリセット</div>
                <div class="settings__item-label">
                    このデバイス (ブラウザ) に保存されている設定データを、初期状態のデフォルト値にリセットできます。<br>
                    <strong class="text-error-lighten-1">設定をリセットすると、元に戻すことはできません。</strong><br>
                    <strong class="text-error-lighten-1">設定のデバイス間同期がオンのときは、同期が有効なすべてのデバイスに反映されます。</strong>十分ご注意ください。<br>
                </div>
            </div>
            <v-btn class="settings__save-button bg-error mt-5" variant="flat" @click="resetSettings()">
                <Icon icon="material-symbols:device-reset-rounded" class="mr-2" height="23px" />設定をリセット
            </v-btn>
        </div>
        <PinnedChannelSettings :modelValue="pinned_channel_settings_modal" @update:modelValue="pinned_channel_settings_modal = $event" />
        <TimeTableSettingsDialog v-model:isOpen="timetable_settings_modal" />
    </SettingsBase>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import PinnedChannelSettings from '@/components/Settings/PinnedChannelSettings.vue';
import TimeTableSettingsDialog from '@/components/Settings/TimeTableSettings.vue';
import Message from '@/message';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';
import SettingsBase from '@/views/Settings/Base.vue';

export default defineComponent({
    name: 'Settings-General',
    components: {
        PinnedChannelSettings,
        TimeTableSettingsDialog,
        SettingsBase,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),

            // フォームを小さくするかどうか
            is_form_dense: Utils.isSmartphoneHorizontal(),

            // ピン留め中チャンネルの並び替え設定のモーダルを表示するか
            pinned_channel_settings_modal: false,

            // 番組表の表示設定のモーダルを表示するか
            timetable_settings_modal: false,

            // デフォルトのパネルの表示状態の選択肢
            panel_display_state: [
                {title: '前回の状態を復元する', value: 'RestorePreviousState'},
                {title: '常に表示する', value: 'AlwaysDisplay'},
                {title: '常に折りたたむ', value: 'AlwaysFold'},
            ],

            // テレビをみるときにデフォルトで表示されるパネルのタブの選択肢
            tv_panel_active_tab: [
                {title: '番組情報タブ', value: 'Program'},
                {title: 'チャンネルタブ', value: 'Channel'},
                {title: 'コメントタブ', value: 'Comment'},
                {title: 'Twitter タブ', value: 'Twitter'},
            ],

            // ビデオをみるときにデフォルトで表示されるパネルのタブの選択肢
            video_panel_active_tab: [
                {title: '番組情報タブ', value: 'RecordedProgram'},
                {title: 'シリーズタブ', value: 'Series'},
                {title: 'コメントタブ', value: 'Comment'},
                {title: 'Twitter タブ', value: 'Twitter'},
            ],

            // 選択された設定データ (KonomiTV-Settings.json) が入る
            import_settings_file: null as File | null,
        };
    },
    computed: {
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
            Message.success('設定をエクスポートしました。');
        },

        // 設定データをインポートする
        async importSettings() {

            // 設定データが選択されていないときは実行しない
            if (this.import_settings_file === null) {
                Message.error('インポートする設定データを選択してください！');
                return;
            }

            // 設定データのインポートを実行
            const result = await this.settingsStore.importClientSettings(this.import_settings_file);
            if (result === true) {
                Message.success('設定をインポートしました。');
                window.setTimeout(() => this.$router.go(0), 500);  // 念のためリロード
            } else {
                Message.error('設定データが不正なため、インポートできませんでした。');
            }
        },

        // 設定データをリセットする
        async resetSettings() {
            await this.settingsStore.resetClientSettings();
            Message.success('設定をリセットしました。');
            window.setTimeout(() => this.$router.go(0), 500);  // 念のためリロード
        },
    }
});

</script>