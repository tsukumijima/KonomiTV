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
            <v-divider class="mt-6"></v-divider>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="tv_channel_sort_by_jikkyo_force">チャンネル一覧を実況勢いが強い順に並び替える</label>
                <label class="settings__item-label" for="tv_channel_sort_by_jikkyo_force">
                    オンにすると、チャンネル一覧を実況勢い (ニコニコ実況に1分間に投稿されたコメント数) が強い順に並べ替えます。デフォルトはオフです。<br>
                    実況勢いが同じ場合や、ニコニコ実況が存在しないチャンネル、実況勢いの取得に失敗したチャンネルは、通常通りチャンネル番号順で表示されます。<br>
                </label>
                <label class="settings__item-label" for="tv_channel_sort_by_jikkyo_force">
                    この設定がオンのときは、ピン留め中チャンネルの並び替え設定は無視されます。この設定をオフにすれば、再び並び替え設定が反映されます。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="tv_channel_sort_by_jikkyo_force" hide-details
                    v-model="settingsStore.settings.tv_channel_sort_by_jikkyo_force">
                </v-switch>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="tv_channel_up_down_buttons_reverse">チャンネル切り替えボタンとショートカットキーの上下方向をテレビリモコン準拠にする</label>
                <label class="settings__item-label" for="tv_channel_up_down_buttons_reverse">
                    オンにすると、視聴画面のチャンネル切り替えボタン <Icon icon="fluent:ios-arrow-left-24-filled" style="transform: rotate(90deg); margin-bottom: -4px;" /> <Icon icon="fluent:ios-arrow-right-24-filled" style="transform: rotate(90deg); margin-top: -4px;" /> とショートカットキーの上下キーの動作が反転します。デフォルトはオフです。<br>
                    一般的なテレビリモコンと同じように、<Icon icon="fluent:ios-arrow-left-24-filled" style="transform: rotate(90deg); margin-bottom: -4px;" /> ボタン/キーでチャンネル番号を上げ、<Icon icon="fluent:ios-arrow-right-24-filled" style="transform: rotate(90deg); margin-top: -4px;" /> ボタン/キーでチャンネル番号を下げたい方におすすめです。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="tv_channel_up_down_buttons_reverse" hide-details
                    v-model="settingsStore.settings.tv_channel_up_down_buttons_reverse">
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
                    マイリスト・視聴履歴を含めてインポートするかは、ボタンを押した後の確認ダイヤログで選択できます。<br>
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
            <v-btn class="settings__save-button bg-error mt-5" variant="flat" @click="openImportSettingsDialog()">
                <Icon icon="fa6-solid:upload" class="mr-3" height="19px" />設定をインポート
            </v-btn>
            <v-dialog max-width="560" v-model="import_settings_dialog">
                <v-card>
                    <v-card-title class="import-settings-dialog__title d-flex justify-center font-weight-bold pt-6">マイリスト・視聴履歴もインポートしますか？</v-card-title>
                    <v-card-text class="pt-2 pb-5">
                        マイリストと視聴履歴は、このサーバーの録画番組と紐づいています。<br>
                        別の KonomiTV サーバーの設定をインポートすると、保存されている録画番組が異なるため、身に覚えのない番組が表示されてしまいます。<br>
                        <p class="mt-2">
                            <strong>同じサーバーのバックアップから復元する際は「上書き」、別のサーバーへ設定を移行する際は「維持」を選択してください。</strong><br>
                        </p>
                        <div class="d-flex justify-center align-center mt-3">
                            <div class="mx-auto pr-md-4">
                                <div class="d-flex align-center flex-column flex-md-row">
                                    <div class="d-inline-block text-center text-md-right mr-md-2" style="min-width: 150px;">インポートするデータ:</div> <strong>マイリスト {{import_settings_mylist_count}}件 / 視聴履歴 {{import_settings_watched_history_count}}件</strong>
                                </div>
                                <div class="d-flex align-center flex-column flex-md-row">
                                    <div class="d-inline-block text-center text-md-right mr-md-2" style="min-width: 150px;">このデバイス:</div> <strong>マイリスト {{settingsStore.settings.mylist.length}}件 / 視聴履歴 {{settingsStore.settings.watched_history.length}}件</strong>
                                </div>
                            </div>
                    </div>
                    </v-card-text>
                    <div class="d-flex flex-column px-4 pb-6 import-settings-dialog">
                        <v-btn class="settings__save-button text-error-lighten-1" color="background-lighten-1" variant="flat"
                            @click="executeImport(true)">
                            <Icon icon="fluent:document-arrow-down-16-filled" class="mr-2" height="22px" />
                            マイリスト・視聴履歴を<br class="smartphone-vertical-only">上書きしてインポート
                        </v-btn>
                        <v-btn class="settings__save-button text-error-lighten-1 mt-3" color="background-lighten-1" variant="flat"
                            @click="executeImport(false)">
                            <Icon icon="fluent:document-checkmark-16-filled" class="mr-2" height="22px" />
                            マイリスト・視聴履歴は<br class="smartphone-vertical-only">維持してインポート
                        </v-btn>
                        <v-btn class="settings__save-button mt-3" color="background-lighten-1" variant="flat"
                            @click="import_settings_dialog = false">
                            <Icon icon="fluent:dismiss-16-filled" class="mr-2" height="22px" />
                            キャンセル
                        </v-btn>
                    </div>
                </v-card>
            </v-dialog>
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

            // 設定インポートの確認ダイヤログを表示するか
            import_settings_dialog: false,

            // インポートする設定データに含まれるマイリスト・視聴履歴の件数 (確認ダイヤログでの表示用)
            import_settings_mylist_count: 0,
            import_settings_watched_history_count: 0,
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

        // 設定インポートの確認ダイヤログを開く
        // インポート実行前に、マイリスト・視聴履歴を上書きするか維持するかをユーザーに選択させる
        async openImportSettingsDialog() {

            // 設定データが選択されていないときは実行しない
            if (this.import_settings_file === null) {
                Message.error('インポートする設定データを選択してください！');
                return;
            }

            // ダイヤログにマイリスト・視聴履歴の件数を表示するため、選択されたファイルを先読みしてパースする
            let parsed_settings: {[key: string]: any} = {};
            try {
                parsed_settings = JSON.parse(await this.import_settings_file.text());
            } catch (error) {
                Message.error('設定データが不正なため、インポートできませんでした。');
                return;
            }

            // 取り込むデータに含まれるマイリスト・視聴履歴の件数を取得する
            // 生の設定データなので、念のため配列かどうか確認してから件数を数える
            this.import_settings_mylist_count = Array.isArray(parsed_settings.mylist) ? parsed_settings.mylist.length : 0;
            this.import_settings_watched_history_count = Array.isArray(parsed_settings.watched_history) ? parsed_settings.watched_history.length : 0;

            // 確認ダイヤログを表示
            this.import_settings_dialog = true;
        },

        // 設定データをインポートする
        // include_environment_specific: マイリスト・視聴履歴などの環境固有値も上書きするか (false なら現在のデバイスの値を維持する)
        async executeImport(include_environment_specific: boolean) {

            // ダイヤログを閉じる
            this.import_settings_dialog = false;

            // ダイヤログを開いた時点でファイルは選択済みだが、念のため再確認する
            if (this.import_settings_file === null) {
                return;
            }

            // 設定データのインポートを実行
            const result = await this.settingsStore.importClientSettings(this.import_settings_file, include_environment_specific);
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
<style lang="scss" scoped>

// 設定インポートの確認ダイヤログのタイトル
.import-settings-dialog__title {
    // タイトルが長くスマホ縦では 1 行に収まらないため、折り返しを許可して中央寄せする
    // (Vuetify の v-card-title はデフォルトで white-space: nowrap のため、明示的に上書きする)
    white-space: normal;
    text-align: center;
    line-height: 1.5;
}

// 設定インポートの確認ダイヤログ内のアクションボタン (Account.vue の設定競合ダイヤログと同じ見た目に揃える)
.import-settings-dialog {
    .v-btn {
        @include smartphone-vertical {
            height: 50px !important;
            text-align: left;
        }
        // スマホ縦のときだけボタン文言を 2 行に折り返す
        br.smartphone-vertical-only {
            display: none;
            @include smartphone-vertical {
                display: inline;
            }
        }
    }
}

</style>