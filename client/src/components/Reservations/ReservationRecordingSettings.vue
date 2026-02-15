<template>
    <div class="reservation-recording-settings">
        <!-- 録画中の警告バナー -->
        <div v-if="reservation.is_recording_in_progress" class="recording-warning-banner">
            <Icon icon="fluent:warning-16-filled" class="recording-warning-banner__icon" />
            <span class="recording-warning-banner__text">
                録画中の録画設定の変更はできません。
            </span>
        </div>

        <!-- 録画設定プリセット選択（プリセットが2つ以上ある場合のみ表示） -->
        <div v-if="presets !== null && presets.presets.length >= 2" class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画設定プリセット</div>
            <div class="reservation-recording-settings__description">
                EDCB の録画設定プリセットから設定値を読み込みます。プリセットの追加・変更・削除は EpgTimer から行ってください。
            </div>
            <v-select
                :disabled="reservation.is_recording_in_progress"
                v-model="selectedPresetId"
                :items="presetOptions"
                item-title="title"
                item-value="value"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                @update:model-value="handlePresetChange">
            </v-select>
        </div>

        <!-- 録画予約の有効/無効 -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__header">
                <div class="reservation-recording-settings__label">録画予約の有効/無効</div>
                <v-switch
                    :disabled="reservation.is_recording_in_progress"
                    style="height: 0; margin-top: -40px; margin-right: 6px;"
                    v-model="settings.is_enabled"
                    color="primary"
                    density="compact"
                    hide-details
                    @update:model-value="handleChange">
                </v-switch>
            </div>
            <div class="reservation-recording-settings__description mb-0">
                予約が無効なときは、この番組の録画動作を行いません。<br>
                キーワード自動予約条件により不必要な番組が予約されてしまっているときは、予約を無効にしてみてください。(予約削除ではすぐ再追加されてしまい意味がありません。)
            </div>
        </div>

        <!-- 録画予約の優先度 -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画予約の優先度</div>
            <div class="reservation-recording-settings__description mb-0">
                放送時間が重なりチューナーが足りないときは、より優先度が高い予約から優先的に録画します。
            </div>
            <div class="reservation-recording-settings__slider">
                <v-slider
                    :disabled="reservation.is_recording_in_progress"
                    v-model="settings.priority"
                    :min="1"
                    :max="5"
                    :step="1"
                    color="primary"
                    density="compact"
                    show-ticks="always"
                    thumb-label
                    hide-details
                    @update:model-value="handleChange">
                </v-slider>
            </div>
        </div>

        <!-- 録画フォルダのパス -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画フォルダのパス</div>
            <div class="reservation-recording-settings__description">
                空欄にすると、デフォルトの録画フォルダに保存されます。
            </div>
            <v-text-field
                :disabled="reservation.is_recording_in_progress"
                v-model="recordingFolderPath"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                :placeholder="versionStore.is_linux_environment ? '/mnt/hdd/Records/2025年春アニメ' : 'E:\\Records\\2025年春アニメ'"
                @update:model-value="handleChange">
            </v-text-field>
        </div>

        <!-- 録画ファイル名テンプレート -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画ファイル名テンプレート (マクロ)</div>
            <div class="reservation-recording-settings__description">
                空欄にすると、デフォルトの録画ファイル名テンプレート (マクロ) が録画ファイル名の変更に利用されます。<br>
                <div class="mt-1">
                    <a class="link" href="https://github.com/xtne6f/EDCB/blob/work-plus-s/Document/Readme_EpgTimer.txt#L929-L1008" target="_blank">テンプレート構文の一覧</a> / <a class="link" href="https://github.com/xtne6f/EDCB/blob/work-plus-s/Document/Readme_Mod.txt#%E3%83%9E%E3%82%AF%E3%83%AD" target="_blank">xtne6f 版での追加差分</a>
                </div>
            </div>
            <v-text-field
                :disabled="reservation.is_recording_in_progress"
                v-model="recordingFileNameTemplate"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                placeholder="$ZtoH(Title)$.ts"
                @update:model-value="handleChange">
            </v-text-field>
        </div>

        <!-- 録画マージン -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画マージン (秒)</div>
            <div class="reservation-recording-settings__description">
                番組開始時刻の何秒前から録画を開始し、番組終了時刻の何秒後に録画を終了するかの設定です。最低でも5秒以上をおすすめします。(0秒だと番組の冒頭/末尾が欠けてしまいます。)
            </div>
            <div class="reservation-recording-settings__margin-default">
                <v-checkbox
                    :disabled="reservation.is_recording_in_progress"
                    id="use-default-margin"
                    v-model="useDefaultMargin"
                    color="primary"
                    density="compact"
                    hide-details
                    @update:model-value="handleMarginDefaultChange">
                </v-checkbox>
                <label class="reservation-recording-settings__margin-default-text" for="use-default-margin"
                    style="user-select: none;">
                    {{ marginDefaultLabel }}
                </label>
            </div>
            <div class="reservation-recording-settings__margin-controls">
                <v-text-field
                    :disabled="reservation.is_recording_in_progress || useDefaultMargin"
                    v-model.number="settings.recording_start_margin"
                    color="primary"
                    variant="outlined"
                    density="compact"
                    type="number"
                    hide-details
                    prefix="番組開始"
                    suffix="秒前"
                    style="width: 160px;"
                    @update:model-value="handleChange">
                </v-text-field>
                <v-text-field
                    :disabled="reservation.is_recording_in_progress || useDefaultMargin"
                    v-model.number="settings.recording_end_margin"
                    color="primary"
                    variant="outlined"
                    density="compact"
                    type="number"
                    hide-details
                    prefix="番組終了"
                    suffix="秒後"
                    style="width: 166px;"
                    @update:model-value="handleChange">
                </v-text-field>
            </div>
        </div>

        <!-- 字幕データ録画設定 -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">字幕データ録画設定</div>
            <div class="reservation-recording-settings__description">
                字幕データはほとんど録画容量を消費しません。<br>
                [録画する] に設定しておくことを強くおすすめします。
            </div>
            <v-select
                :disabled="reservation.is_recording_in_progress"
                v-model="settings.caption_recording_mode"
                :items="captionRecordingOptions"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                @update:model-value="handleChange">
            </v-select>
        </div>

        <!-- データ放送録画設定 -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">データ放送録画設定</div>
            <div class="reservation-recording-settings__description">
                データ放送は30分で 500MB 以上録画容量を消費する上、KonomiTV は録画再生時のデータ放送表示に非対応です。<br>
                [録画しない] に設定しておくことを強くおすすめします。
            </div>
            <v-select
                :disabled="reservation.is_recording_in_progress"
                v-model="settings.data_broadcasting_recording_mode"
                :items="dataBroadcastingRecordingOptions"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                @update:model-value="handleChange">
            </v-select>
        </div>

        <!-- 録画後動作設定 -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画後動作設定</div>
            <div class="reservation-recording-settings__description">
                通常は [何もしない] のままで大丈夫です。録画後に録画 PC をスリープさせておきたい方のみ設定してください。環境によっては復帰できず以降の録画に失敗することがあります。
            </div>
            <v-select
                :disabled="reservation.is_recording_in_progress"
                v-model="settings.post_recording_mode"
                :items="postRecordingOptions"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                @update:model-value="handleChange">
            </v-select>
        </div>

        <!-- 録画後実行スクリプトのパス -->
        <div class="reservation-recording-settings__section">
            <div class="reservation-recording-settings__label">録画後実行スクリプトのパス</div>
            <div class="reservation-recording-settings__description">
                通常は空欄のままで大丈夫です。録画後に指定の {{ versionStore.is_linux_environment ? '.sh / .lua' : '.bat / .ps1 / .lua' }} スクリプトを実行させたい方のみ設定してください。
            </div>
            <v-text-field
                :disabled="reservation.is_recording_in_progress"
                v-model="settings.post_recording_bat_file_path"
                color="primary"
                variant="outlined"
                density="compact"
                hide-details
                :placeholder="versionStore.is_linux_environment ? '/var/local/edcb/transcode.sh' : 'C:\\DTV\\EDCB\\Transcode.bat'"
                @update:model-value="handleChange">
            </v-text-field>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { objectHash } from 'ohash';
import { ref, computed, watch, onMounted, toRaw } from 'vue';

import { type IReservation, type IRecordSettings, type IRecordSettingsPresets } from '@/services/Reservations';
import useVersionStore from '@/stores/VersionStore';

// Props
const props = defineProps<{
    reservation: IReservation;
    presets: IRecordSettingsPresets | null;
    hasChanges: boolean;
}>();

// Emits
const emit = defineEmits<{
    (e: 'updateSettings', settings: IRecordSettings): void;
    (e: 'changesDetected', hasChanges: boolean): void;
}>();

// ストア
const versionStore = useVersionStore();

// 設定のコピーを作成（元の設定を変更しないため）
const settings = ref<IRecordSettings>(structuredClone(toRaw(props.reservation.record_settings)));

// 初期設定を保存（変更検知用）
const initialSettings = ref<IRecordSettings>(structuredClone(toRaw(props.reservation.record_settings)));

// 録画フォルダパス・録画ファイル名テンプレートの computed（settings.value を単一の情報源とする）
// 録画フォルダは仕様上は複数指定できるが、複数指定はほとんど使われないので、KonomiTV では常に 0 番目の要素を使用する
// 録画フォルダが空の場合はデフォルトの録画フォルダに保存される（フォーム上は空欄としておく）
const recordingFolderPath = computed({
    get: () => settings.value.recording_folders.length > 0
        ? settings.value.recording_folders[0].recording_folder_path
        : '',
    set: (value: string) => {
        updateRecordingFolderSettings(value, recordingFileNameTemplate.value);
    },
});

const recordingFileNameTemplate = computed({
    get: () => settings.value.recording_folders.length > 0
        ? settings.value.recording_folders[0].recording_file_name_template || ''
        : '',
    set: (value: string) => {
        updateRecordingFolderSettings(recordingFolderPath.value, value);
    },
});

// 録画フォルダ設定を更新する関数
const updateRecordingFolderSettings = (folderPath: string, fileNameTemplate: string) => {
    const hasFolderPath = folderPath.trim() !== '';
    const hasFileNameTemplate = fileNameTemplate.trim() !== '';

    if (!hasFolderPath && !hasFileNameTemplate) {
        // 両方とも空の場合は空リストにしてデフォルト設定を使用
        settings.value.recording_folders = [];
    } else {
        // どちらか一方でも指定されている場合は新しい要素を追加
        if (settings.value.recording_folders.length === 0) {
            settings.value.recording_folders.push({
                recording_folder_path: '',
                recording_file_name_template: null,
                is_oneseg_separate_recording_folder: false,
            });
        }
        // 録画フォルダパスとマクロを更新
        // 録画フォルダは仕様上は複数指定できるが、複数指定はほとんど使われないので、KonomiTV では常に 0 番目の要素を使用する
        settings.value.recording_folders[0].recording_folder_path = folderPath;
        settings.value.recording_folders[0].recording_file_name_template = fileNameTemplate || null;
    }
};

// デフォルトマージン使用フラグ
const useDefaultMargin = ref(
    settings.value.recording_start_margin === null && settings.value.recording_end_margin === null
);

// プリセット一覧のプルダウン選択肢
// プリセットが2つ以上ある場合のみ表示される
const presetOptions = computed(() => {
    if (props.presets === null) return [];
    return props.presets.presets.map(preset => ({
        title: preset.name,
        value: preset.id,
    }));
});

// 現在選択中のプリセット ID
const selectedPresetId = ref<number | null>(null);

// プリセットの選択が変更された時の処理
// フォーム全体をプリセットの録画設定値でリセットする
const handlePresetChange = (presetId: number) => {
    if (props.presets === null) return;
    const preset = props.presets.presets.find(p => p.id === presetId);
    if (!preset) return;

    // プリセットの録画設定をフォームに反映
    settings.value = structuredClone(toRaw(preset.record_settings));
    // デフォルトマージン使用フラグも再計算
    useDefaultMargin.value = (
        settings.value.recording_start_margin === null && settings.value.recording_end_margin === null
    );
    handleChange();
};

// 録画後動作モードの日本語ラベルマッピング
const postRecordingModeLabels: Record<string, string> = {
    'Nothing': '何もしない',
    'Standby': 'スタンバイ',
    'StandbyAndReboot': 'スタンバイ(復帰後再起動)',
    'Suspend': 'サスペンド',
    'SuspendAndReboot': 'サスペンド(復帰後再起動)',
    'Shutdown': 'シャットダウン',
};

// 字幕録画のオプション
// グローバルデフォルト値が取得できている場合は括弧書きで実際の値を表示
const captionRecordingOptions = computed(() => {
    const globalDefaults = props.presets?.global_defaults;
    const defaultLabel = globalDefaults
        ? `デフォルト設定を使う (${globalDefaults.caption_recording_mode === 'Enable' ? '録画する' : '録画しない'})`
        : 'デフォルト設定を使う';
    return [
        { title: defaultLabel, value: 'Default' },
        { title: '録画する', value: 'Enable' },
        { title: '録画しない', value: 'Disable' },
    ];
});

// データ放送録画のオプション
// グローバルデフォルト値が取得できている場合は括弧書きで実際の値を表示
const dataBroadcastingRecordingOptions = computed(() => {
    const globalDefaults = props.presets?.global_defaults;
    const defaultLabel = globalDefaults
        ? `デフォルト設定を使う (${globalDefaults.data_broadcasting_recording_mode === 'Enable' ? '録画する' : '録画しない'})`
        : 'デフォルト設定を使う';
    return [
        { title: defaultLabel, value: 'Default' },
        { title: '録画する', value: 'Enable' },
        { title: '録画しない', value: 'Disable' },
    ];
});

// 録画後動作のオプション
// グローバルデフォルト値が取得できている場合は括弧書きで実際の値を表示
const postRecordingOptions = computed(() => {
    const globalDefaults = props.presets?.global_defaults;
    const defaultLabel = globalDefaults
        ? `デフォルト設定を使う (${postRecordingModeLabels[globalDefaults.post_recording_mode] ?? globalDefaults.post_recording_mode})`
        : 'デフォルト設定を使う';
    return [
        { title: defaultLabel, value: 'Default' },
        { title: '何もしない', value: 'Nothing' },
        { title: 'スタンバイ', value: 'Standby' },
        { title: 'スタンバイ(復帰後再起動)', value: 'StandbyAndReboot' },
        { title: 'サスペンド', value: 'Suspend' },
        { title: 'サスペンド(復帰後再起動)', value: 'SuspendAndReboot' },
        { title: 'シャットダウン', value: 'Shutdown' },
    ];
});

// 変更があるかどうかを計算
// ohash を使ってオブジェクトのハッシュ値を比較することで、より信頼性の高い変更検知を実現
const hasChangesComputed = computed(() => {
    return objectHash(settings.value) !== objectHash(initialSettings.value);
});

// 変更を監視
watch(hasChangesComputed, (newValue) => {
    emit('changesDetected', newValue);
});

// 保存後に initialSettings を更新（親から hasChanges が false になったことを監視）
// これにより、保存後は保存した状態が新しい基準となり、その状態からの差分で変更検知が行われる
watch(() => props.hasChanges, (newValue, oldValue) => {
    // hasChanges が true から false に変わったとき（保存完了時）
    if (oldValue === true && newValue === false) {
        // 現在の設定を新しい初期設定として保存
        initialSettings.value = structuredClone(toRaw(settings.value));
    }
});

// 変更時の処理（settings.value の変更を親に通知）
const handleChange = () => {
    emit('updateSettings', settings.value);
};

// マージンの「デフォルト設定を使う」ラベル
// グローバルデフォルト値が取得できている場合は括弧書きで実際の値を表示
const marginDefaultLabel = computed(() => {
    const globalDefaults = props.presets?.global_defaults;
    if (globalDefaults) {
        return `デフォルト設定を使う (開始 ${globalDefaults.recording_start_margin} 秒前 / 終了 ${globalDefaults.recording_end_margin} 秒後)`;
    }
    return 'デフォルト設定を使う';
});

// マージンデフォルト設定の変更
// デフォルト → カスタムに切り替えた際は、グローバルデフォルト値を初期値として設定する
const handleMarginDefaultChange = () => {
    if (useDefaultMargin.value) {
        settings.value.recording_start_margin = null;
        settings.value.recording_end_margin = null;
    } else {
        // グローバルデフォルト値が取得できている場合はその値を使い、取得できていない場合はフォールバック値を使う
        const globalDefaults = props.presets?.global_defaults;
        settings.value.recording_start_margin = globalDefaults?.recording_start_margin ?? 5;
        settings.value.recording_end_margin = globalDefaults?.recording_end_margin ?? 2;
    }
    handleChange();
};

// props の予約情報が変更された時の処理
watch(() => props.reservation, (newReservation) => {
    settings.value = structuredClone(toRaw(newReservation.record_settings));
    initialSettings.value = structuredClone(toRaw(newReservation.record_settings));
    // フォルダパス等は computed で自動的に更新される
    // プリセット選択状態とデフォルトマージン使用フラグもリセット
    selectedPresetId.value = null;
    useDefaultMargin.value = (
        newReservation.record_settings.recording_start_margin === null &&
        newReservation.record_settings.recording_end_margin === null
    );
}, { deep: true });

// コンポーネントマウント時にバージョン情報を取得
onMounted(async () => {
    await versionStore.fetchServerVersion();
});

</script>
<style lang="scss" scoped>

.reservation-recording-settings {
    display: flex;
    flex-direction: column;
    gap: 16px;

    &__section {
        display: flex;
        flex-direction: column;
    }

    &__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    &__label {
        font-size: 13.5px;
        font-weight: 700;
        line-height: 1.5;
        letter-spacing: 0.04em;
        color: rgb(var(--v-theme-text));
    }

    &__description {
        font-size: 12px;
        font-weight: 500;
        line-height: 1.55;
        color: rgb(var(--v-theme-text-darken-1));
        margin-top: 6px;
        margin-bottom: 10px;
    }

    &__description-small {
        font-size: 11.5px;
        font-weight: 500;
        line-height: 1.5;
        color: rgb(var(--v-theme-text-darken-1));
        margin-top: 6px;
    }

    &__slider {
        margin-top: 8px;
    }

    &__margin-controls {
        display: flex;
        gap: 6px;
    }

    &__margin-default {
        display: flex;
        align-items: center;
        gap: 4px;
        height: 20px;
        margin-left: -3px;
        margin-bottom: 10px;

        &-text {
            font-size: 12.5px;
        }
    }
}

// 録画中の警告バナー
.recording-warning-banner {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    margin-bottom: 4px;
    background-color: rgb(var(--v-theme-warning-darken-3), 0.5);
    border-radius: 6px;

    &__icon {
        color: rgb(var(--v-theme-warning));
        width: 22px;
        height: 22px;
        margin-right: 8px;
        flex-shrink: 0;
    }

    &__text {
        font-size: 13px;
        font-weight: 500;
        line-height: 1.5;
        color: rgb(var(--v-theme-warning-lighten-1));
    }
}

</style>