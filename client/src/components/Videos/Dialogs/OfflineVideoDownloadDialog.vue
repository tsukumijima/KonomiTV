<template>
    <v-dialog max-width="620" v-model="isShown">
        <v-card class="offline-download-dialog__card">
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                オフライン再生用に保存
            </v-card-title>
            <v-card-text class="pt-4 px-6 pb-0">
                <div class="offline-download-dialog__title mb-4">
                    <div class="text-h6 text-text mb-2"
                        v-html="ProgramUtils.decorateProgramInfo(program, 'title')"></div>
                    <div class="text-body-2 text-text-darken-1">
                        {{ ProgramUtils.getProgramTime(program) }}
                    </div>
                </div>
                <div v-if="activeDownloadJob !== null" class="warning-banner warning-banner--normal mt-4">
                    <Icon icon="fluent:info-16-regular" class="warning-banner__icon" />
                    <span class="warning-banner__text">
                        現在オフライン保存中です ({{OfflineVideos.formatQualityLabel(activeDownloadJob.quality)}}) 。<br>
                        完了するまで新しい保存は開始できません。
                    </span>
                </div>
                <div v-if="savedVideo !== null" class="warning-banner warning-banner--keyword mt-4">
                    <Icon icon="fluent:warning-16-filled" class="warning-banner__icon" />
                    <span class="warning-banner__text">
                        現在は {{OfflineVideos.formatQualityLabel(savedVideo.quality)}} / {{OfflineVideos.formatOfflineSize(savedVideo.size_bytes, false)}} で保存されています。<br>
                        新しい保存が完了するまで、現在のデータは削除されません。
                    </span>
                </div>
                <v-select class="offline-download-dialog__select settings__item-form mt-7" v-model="selectedQuality" :items="qualityItems"
                    label="保存画質" color="primary" variant="outlined" hide-details :density="selectDensity" />
                <div class="offline-download-dialog__switch mt-6" :class="{'offline-download-dialog__switch--disabled': isHEVCSupported === false}">
                    <div>
                        <div class="font-weight-bold mb-1" style="font-size: 15px;">通信節約モード (H.265 / HEVC)</div>
                        <div class="text-text-darken-1">画質はほぼそのまま、保存容量を 50% ~ 70% 抑えて保存できます。</div>
                    </div>
                    <v-switch v-model="isDataSaverMode" color="primary" hide-details :disabled="isHEVCSupported === false" />
                </div>
                <div class="offline-download-dialog__switch mt-3">
                    <div>
                        <div class="font-weight-bold mb-1" style="font-size: 15px;">24fps モード</div>
                        <div class="text-text-darken-1">映画やアニメなど 24fps で制作された映像を検出し、本来の動きに近づけます。</div>
                    </div>
                    <v-switch v-model="is24fpsMode" color="primary" hide-details />
                </div>
                <div class="offline-download-dialog__switch mt-3"
                    :class="{'offline-download-dialog__switch--disabled': isBackgroundFetchSupported !== true}">
                    <div>
                        <div class="font-weight-bold mb-1" style="font-size: 15px;">バックグラウンドでダウンロードする</div>
                        <div class="text-text-darken-1">
                            オフのときは、完了まで KonomiTV のタブを開いたまま待つ必要があります。スマートフォンでは画面を閉じずに開き続けてください。<br>
                            オンにするとタブを閉じてもダウンロードを続行できますが、ブラウザの制限で同時に保存できるのは<b>1本まで</b>です。2本目以降は順番待ちになります。Android ではダウンロードが始まらず待機したままになることがあり、挙動が不安定です。<br>
                            急いで保存したいときや、複数本を同時に保存したいときは、<b>オフのまま使うことをおすすめします。</b>
                        </div>
                        <p class="mt-1 mb-0 text-error-lighten-1" v-if="isBackgroundFetchSupported === false">
                            このブラウザではバックグラウンドダウンロードに対応していません。
                        </p>
                    </div>
                    <v-switch v-model="isBackgroundDownload" color="primary" hide-details
                        :disabled="isBackgroundFetchSupported !== true" />
                </div>
                <v-alert v-if="isMeteredConnection" class="mt-4" color="warning" variant="tonal">
                    従量制通信の可能性があります。通信量に注意してください。
                </v-alert>
            </v-card-text>
            <v-card-actions class="pt-7 px-6 pb-6">
                <v-spacer />
                <v-btn color="text" variant="text" @click="isShown = false">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn class="px-3" color="secondary" variant="flat"
                    :disabled="isPreparing || activeDownloadJob !== null" :loading="isStarting" @click="startDownload">
                    <Icon icon="fluent:cloud-arrow-down-20-filled" width="18px" height="18px" />
                    <span class="ml-1">{{savedVideo === null ? 'ダウンロード開始' : '保存し直す'}}</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>

    <!-- 永続ストレージを利用できない場合の確認ダイアログ -->
    <v-dialog v-model="showPersistenceWarning" max-width="620" persistent>
        <v-card class="offline-download-dialog__card">
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                保存データが自動削除される可能性があります
            </v-card-title>
            <v-card-text class="pt-2 pb-0">
                <v-alert color="warning" variant="tonal">
                    ブラウザから永続ストレージの利用を許可されませんでした。空き容量が減った場合、ブラウザの判断でオフライン保存が削除されることがあります。
                </v-alert>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer />
                <v-btn color="text" variant="text" @click="cancelPersistenceWarning">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn class="px-3" color="secondary" variant="flat" :loading="isStarting" @click="continueAfterPersistenceWarning">
                    <Icon icon="fluent:arrow-download-16-filled" width="18px" height="18px" />
                    <span class="ml-1">そのまま保存</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed, ref, watch } from 'vue';

import type { IRecordedProgram } from '@/services/Videos';

import Message from '@/message';
import OfflineVideos, { type IOfflineDownloadJob, type IOfflineVideo } from '@/services/OfflineVideos';
import Utils, { PlayerUtils, ProgramUtils } from '@/utils';

const props = defineProps<{
    program: IRecordedProgram;
    show: boolean;
}>();

const emit = defineEmits<{
    (event: 'update:show', show: boolean): void;
}>();

// ダイアログを開くたびに容量優先の既定値へ戻し、前回の高画質設定を意図せず引き継がない
const selectedQuality = ref('720p');
const isDataSaverMode = ref(true);
const is24fpsMode = ref(true);
// Background Fetch は同時に1件までしか実行できず、Android では開始しないことがあるため、明示的に選ばれたときだけ使う
const isBackgroundDownload = ref(false);
const isBackgroundFetchSupported = ref<boolean | null>(null);
const isHEVC10bitSupported = ref(false);
const isPreparing = ref(false);
const isStarting = ref(false);
const savedVideo = ref<IOfflineVideo | null>(null);
const activeDownloadJob = ref<IOfflineDownloadJob | null>(null);
const showPersistenceWarning = ref(false);
const pendingAPIQuality = ref<string | null>(null);
const pendingUseBackgroundFetch = ref(false);

// ダイアログを開く前に対応可否を把握し、未対応ブラウザで一瞬有効に見えないようにする
void OfflineVideos.isBackgroundFetchSupported().then(supported => {
    isBackgroundFetchSupported.value = supported;
});

const isShown = computed({
    get: () => props.show,
    set: value => emit('update:show', value),
});
const isHEVCSupported = computed(() => PlayerUtils.isHEVCVideoSupported());
const isMeteredConnection = computed(() => {
    const connection = navigator.connection;
    return connection !== undefined && (connection.saveData === true || ['slow-2g', '2g', '3g'].includes(connection.effectiveType ?? ''));
});
const selectDensity = computed(() => Utils.isSmartphoneHorizontal() ? 'compact' : 'default');

/** 通信節約モードの状態に応じて、画質ごとの見積もり容量付き選択肢を組み立てる */
const qualityItems = computed(() => {
    const isHEVC = isDataSaverMode.value === true && isHEVCSupported.value === true;
    return OfflineVideos.BASE_QUALITY_VALUES.map(baseQuality => ({
        title: OfflineVideos.formatQualitySelectLabel(baseQuality, props.program.recorded_video.duration, isHEVC),
        value: baseQuality,
    }));
});

/** 現在の UI 設定から API 画質を組み立てる */
const buildAPIQuality = (): string => {
    return OfflineVideos.buildAPIQuality(selectedQuality.value, {
        isDataSaverMode: isDataSaverMode.value,
        isHEVCSupported: isHEVCSupported.value,
        isHEVC10bitSupported: isHEVC10bitSupported.value,
        is24fpsMode: is24fpsMode.value,
    });
};

/** 選択した画質でオフライン保存を開始する */
const startDownload = async (): Promise<void> => {
    if (isStarting.value === true || activeDownloadJob.value !== null) return;
    isStarting.value = true;
    try {
        const apiQuality = buildAPIQuality();

        // 永続化を拒否された環境では、専用ダイアログでブラウザによる削除可能性を伝える
        if (navigator.storage?.persist !== undefined && await navigator.storage.persist() === false) {
            pendingAPIQuality.value = apiQuality;
            pendingUseBackgroundFetch.value = isBackgroundDownload.value;
            showPersistenceWarning.value = true;
            return;
        }
        await OfflineVideos.start(props.program, apiQuality, isBackgroundDownload.value);
        Message.success('オフライン保存を開始しました。');
        isShown.value = false;
    } catch (error) {
        Message.error(error instanceof Error ? error.message : 'オフライン保存を開始できませんでした。');
    } finally {
        isStarting.value = false;
    }
};

/** 永続ストレージを利用できない条件を了承して保存を開始する */
const continueAfterPersistenceWarning = async (): Promise<void> => {
    if (pendingAPIQuality.value === null || isStarting.value === true || activeDownloadJob.value !== null) return;
    isStarting.value = true;
    try {
        await OfflineVideos.start(props.program, pendingAPIQuality.value, pendingUseBackgroundFetch.value);
        Message.success('オフライン保存を開始しました。');
        showPersistenceWarning.value = false;
        pendingAPIQuality.value = null;
        pendingUseBackgroundFetch.value = false;
        isShown.value = false;
    } catch (error) {
        Message.error(error instanceof Error ? error.message : 'オフライン保存を開始できませんでした。');
    } finally {
        isStarting.value = false;
    }
};

// 永続ストレージの警告を閉じ、保留した画質とバックグラウンド保存の選択を破棄
const cancelPersistenceWarning = (): void => {
    showPersistenceWarning.value = false;
    pendingAPIQuality.value = null;
    pendingUseBackgroundFetch.value = false;
};

watch(() => props.show, async (show) => {
    if (show === false) return;
    isPreparing.value = true;
    selectedQuality.value = '720p';
    isDataSaverMode.value = isHEVCSupported.value;
    is24fpsMode.value = true;
    isBackgroundDownload.value = false;
    try {
        const [savedVideoResult, activeJobResult, isBackgroundFetchSupportedResult] = await Promise.all([
            OfflineVideos.getVideo(props.program.id),
            OfflineVideos.getActiveJobForVideo(props.program.id),
            OfflineVideos.isBackgroundFetchSupported(),
        ]);
        savedVideo.value = savedVideoResult;
        activeDownloadJob.value = activeJobResult;
        isBackgroundFetchSupported.value = isBackgroundFetchSupportedResult;
        isHEVC10bitSupported.value = isHEVCSupported.value === true && await PlayerUtils.isHEVC10bitVideoSupported();
    } catch (error) {
        Message.error(error instanceof Error ? error.message : 'オフライン保存の準備に失敗しました。');
        isShown.value = false;
    } finally {
        isPreparing.value = false;
    }
});

</script>
<style lang="scss" scoped>

.offline-download-dialog {
    &__card {
        // スマホ縦画面ではダイアログ幅が狭いため、カード内の左右 padding を 4px だけ削る (24px → 20px)
        @include smartphone-vertical {
            :deep(.v-card-title),
            :deep(.v-card-text),
            :deep(.v-card-actions) {
                padding-left: 20px !important;
                padding-right: 20px !important;
            }
        }
    }

    &__title {
        font-size: 17px;
        font-weight: bold;
        line-height: 1.5;
    }

    &__select {
        // v-card-text の 14px / text-darken-1 指定を打ち消し、設定画面の outlined セレクトと同じサイズ感に揃える
        :deep(.v-field) {
            font-size: 16px !important;
            color: rgb(var(--v-theme-text)) !important;
            text-autospace: normal;
        }

        :deep(.v-field__input) {
            min-height: 56px;
            padding-top: 16px;
            padding-bottom: 16px;
            color: rgb(var(--v-theme-text)) !important;
            font-size: 16px !important;
            line-height: 1.5 !important;
            text-autospace: normal;
        }

        :deep(.v-select__selection-text) {
            color: rgb(var(--v-theme-text)) !important;
            text-autospace: normal;
        }

        @include smartphone-horizontal {
            :deep(.v-field),
            :deep(.v-field__input) {
                font-size: 13.5px !important;
            }

            :deep(.v-field__input) {
                min-height: 40px;
                padding-top: 8px;
                padding-bottom: 8px;
            }
        }
    }

    &__switch {
        // 説明文とスイッチを横並びにしつつ、v-switch の余白分を padding-right で確保してカード内に収める
        position: relative;
        padding-right: 56px;

        @include smartphone-vertical {
            padding-right: 52px;
        }

        > div:first-child {
            min-width: 0;
        }

        :deep(.v-switch) {
            position: absolute;
            top: 4px;
            right: 0;
            margin: 0;

            .v-selection-control {
                // flex 配置時のデフォルト margin が右端からはみ出すので打ち消す
                margin-inline-start: 0;
                min-height: 40px;
            }
        }

        &--disabled {
            opacity: 0.5;
        }
    }
}

// 既存保存の警告バナー (ReservationDetailDrawer.vue と同じスタイル)
.warning-banner {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-radius: 6px;

    &__icon {
        width: 22px;
        height: 22px;
        margin-right: 8px;
        flex-shrink: 0;
    }

    &__text {
        font-size: 13px;
        font-weight: 500;
        line-height: 1.55;
    }

    &--keyword {
        background-color: rgb(var(--v-theme-warning-darken-3), 0.5);

        .warning-banner__icon {
            color: rgb(var(--v-theme-warning));
        }

        .warning-banner__text {
            color: rgb(var(--v-theme-warning-lighten-1));
        }
    }

    &--normal {
        background-color: rgb(var(--v-theme-info-darken-3), 0.5);

        .warning-banner__icon {
            color: rgb(var(--v-theme-info));
        }

        .warning-banner__text {
            color: rgb(var(--v-theme-info-lighten-1));
        }
    }
}

</style>
