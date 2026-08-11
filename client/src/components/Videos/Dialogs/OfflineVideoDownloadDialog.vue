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
                <v-alert v-if="savedVideo !== null" class="mt-4" color="primary" variant="tonal">
                    現在は {{OfflineVideos.formatQualityLabel(savedVideo.quality)}} / {{OfflineVideos.formatOfflineSize(savedVideo.size_bytes, false)}} で保存されています。<br>
                    新しい保存が完了するまで、現在のデータは削除されません。
                </v-alert>
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
                <v-btn class="px-3" color="secondary" variant="flat" :disabled="isPreparing" :loading="isStarting" @click="startDownload">
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
import OfflineVideos, { type IOfflineVideo } from '@/services/OfflineVideos';
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
const isHEVC10bitSupported = ref(false);
const isPreparing = ref(false);
const isStarting = ref(false);
const savedVideo = ref<IOfflineVideo | null>(null);
const showPersistenceWarning = ref(false);
const pendingAPIQuality = ref<string | null>(null);

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
    isStarting.value = true;
    try {
        const apiQuality = buildAPIQuality();

        // 永続化を拒否された環境では、専用ダイアログでブラウザによる削除可能性を伝える
        if (navigator.storage?.persist !== undefined && await navigator.storage.persist() === false) {
            pendingAPIQuality.value = apiQuality;
            showPersistenceWarning.value = true;
            return;
        }
        await OfflineVideos.start(props.program, apiQuality);
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
    if (pendingAPIQuality.value === null) return;
    isStarting.value = true;
    try {
        await OfflineVideos.start(props.program, pendingAPIQuality.value);
        Message.success('オフライン保存を開始しました。');
        showPersistenceWarning.value = false;
        pendingAPIQuality.value = null;
        isShown.value = false;
    } catch (error) {
        Message.error(error instanceof Error ? error.message : 'オフライン保存を開始できませんでした。');
    } finally {
        isStarting.value = false;
    }
};

// 永続ストレージの警告を閉じ、保留した画質を破棄
const cancelPersistenceWarning = (): void => {
    showPersistenceWarning.value = false;
    pendingAPIQuality.value = null;
};

watch(() => props.show, async (show) => {
    if (show === false) return;
    isPreparing.value = true;
    selectedQuality.value = '720p';
    isDataSaverMode.value = isHEVCSupported.value;
    is24fpsMode.value = true;
    try {
        savedVideo.value = await OfflineVideos.getVideo(props.program.id);
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

</style>
