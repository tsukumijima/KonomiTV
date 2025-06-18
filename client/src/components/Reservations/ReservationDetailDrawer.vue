<template>
    <!-- 背景スクリム -->
    <div class="reservation-detail-drawer__scrim"
        :class="{ 'reservation-detail-drawer__scrim--visible': isVisible }"
        @click="handleClose"></div>

    <!-- ドロワー本体 -->
    <div class="reservation-detail-drawer" :class="{ 'reservation-detail-drawer--visible': isVisible }">
        <!-- ヘッダー -->
        <div class="reservation-detail-drawer__header">
            <div class="reservation-detail-drawer__tabs">
                <div v-ripple class="reservation-detail-drawer__tab"
                    :class="{ 'reservation-detail-drawer__tab--active': activeTab === 'info' }"
                    @click="activeTab = 'info'">
                    <Icon icon="fluent:info-12-regular" width="20px" height="20px" />
                    <span class="reservation-detail-drawer__tab-text">番組情報</span>
                </div>
                <div v-ripple class="reservation-detail-drawer__tab"
                    :class="{ 'reservation-detail-drawer__tab--active': activeTab === 'settings' }"
                    @click="activeTab = 'settings'">
                    <Icon icon="material-symbols:settings-video-camera-outline-rounded" width="20px" height="20px" />
                    <span class="reservation-detail-drawer__tab-text">録画設定</span>
                </div>
            </div>
            <div v-ripple class="reservation-detail-drawer__close" @click="handleClose">
                <Icon icon="fluent:dismiss-16-filled" width="22px" height="22px" />
            </div>
        </div>

        <!-- コンテンツ -->
        <div class="reservation-detail-drawer__content">
            <!-- 番組情報タブ -->
            <div v-if="activeTab === 'info' && reservation" class="reservation-detail-drawer__info">
                <ReservationProgramInfo :reservation="reservation" />
            </div>

            <!-- 録画設定タブ -->
            <div v-if="activeTab === 'settings' && reservation" class="reservation-detail-drawer__settings">
                <ReservationRecordingSettings
                    :reservation="reservation"
                    :has-changes="hasChanges"
                    @update-settings="handleUpdateSettings"
                    @changes-detected="hasChanges = $event" />
            </div>
        </div>

        <!-- フッター -->
        <div class="reservation-detail-drawer__footer">
            <div class="reservation-detail-drawer__actions">
                <v-btn
                    class="px-3"
                    variant="text"
                    @click="handleDelete">
                    <Icon icon="fluent:delete-16-regular" width="20px" height="20px" />
                    <span class="ml-1">予約を削除</span>
                </v-btn>
                <v-btn
                    v-if="activeTab === 'settings'"
                    class="px-3"
                    color="secondary"
                    variant="flat"
                    :disabled="!hasChanges"
                    :loading="isSaving"
                    @click="handleSave">
                    <Icon icon="fluent:save-16-regular" width="20px" height="20px" />
                    <span class="ml-1">変更を保存</span>
                </v-btn>
            </div>
        </div>
    </div>

    <!-- 削除確認ダイアログ -->
    <v-dialog v-model="showDeleteDialog" max-width="715">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                録画予約を削除しますか？
            </v-card-title>
            <v-card-text class="pt-2 pb-0">
                <div v-if="reservation" class="mb-4">
                    <div class="text-h6 text-text mb-2"
                        v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'title')"></div>
                    <div class="text-body-2 text-text-darken-1">
                        {{ ProgramUtils.getProgramTime(reservation.program) }}
                    </div>
                </div>
                <div v-if="isRecordingInProgress && reservation" class="warning-banner warning-banner--recording">
                    <Icon icon="fluent:warning-16-filled" class="warning-banner__icon" />
                    <span class="warning-banner__text">
                        この番組は現在録画中です。<br>
                        予約を削除すると、現在までの録画ファイルは残りますが、残りの期間の録画は中断されます。
                    </span>
                </div>
                <div v-else-if="reservation" class="warning-banner warning-banner--normal">
                    <Icon icon="fluent:info-16-regular" class="warning-banner__icon" />
                    <span class="warning-banner__text">
                        録画予約を削除すると、番組開始時刻までに再度予約を追加しない限り、この番組は録画されません。
                    </span>
                </div>
                <div v-if="isKeywordAutoReservation && reservation" class="warning-banner warning-banner--keyword mt-3">
                    <Icon icon="fluent:warning-16-filled" class="warning-banner__icon" />
                    <span class="warning-banner__text">
                        この予約はキーワード自動予約で追加されました。削除してもすぐに再追加される可能性があります。<br>
                        録画が不要な場合は削除ではなく「無効」にすることをおすすめします。
                    </span>
                </div>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer></v-spacer>
                <v-btn color="text" variant="text" @click="showDeleteDialog = false">
                    <Icon icon="fluent:dismiss-20-regular" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn class="px-3" color="error" variant="flat" @click="confirmDelete">
                    <Icon icon="fluent:delete-20-regular" width="18px" height="18px" />
                    <span class="ml-1">予約を削除</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script lang="ts" setup>
import { ref, computed, watch } from 'vue';

import ReservationProgramInfo from '@/components/Reservations/ReservationProgramInfo.vue';
import ReservationRecordingSettings from '@/components/Reservations/ReservationRecordingSettings.vue';
import Message from '@/message';
import Reservations, { type IReservation, type IRecordSettings } from '@/services/Reservations';
import { ProgramUtils } from '@/utils';

// Props
const props = defineProps<{
    reservation: IReservation | null;
    modelValue: boolean;
}>();

// Emits
const emit = defineEmits<{
    (e: 'update:modelValue', value: boolean): void;
    (e: 'updated', reservation: IReservation): void;
    (e: 'deleted', reservationId: number): void;
}>();

// ドロワーの表示状態
const isVisible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value),
});

// アクティブなタブ
const activeTab = ref<'info' | 'settings'>('info');

// 変更の検知
const hasChanges = ref(false);

// 保存中フラグ
const isSaving = ref(false);

// 現在の録画設定
const currentSettings = ref<IRecordSettings | null>(null);

// 削除確認ダイアログの表示状態
const showDeleteDialog = ref(false);

// キーワード自動予約かどうか
const isKeywordAutoReservation = computed(() => {
    return props.reservation?.comment.includes('EPG自動予約') ?? false;
});

// 録画中かどうか
const isRecordingInProgress = computed(() => {
    return props.reservation?.is_recording_in_progress ?? false;
});

// ドロワーが開かれた時の処理
watch(isVisible, (newValue) => {
    if (newValue) {
        // 開かれた時は番組情報タブを表示
        activeTab.value = 'info';
        hasChanges.value = false;
        // ページ全体のスクロールを無効にする
        document.documentElement.classList.add('v-overlay-scroll-blocked');
    } else {
        // ページ全体のスクロールを有効に戻す
        document.documentElement.classList.remove('v-overlay-scroll-blocked');
    }
});

// 閉じる処理
const handleClose = () => {
    if (hasChanges.value) {
        // 変更がある場合は確認
        const confirmed = confirm('変更が保存されていません。ドロワーを閉じますか？');
        if (!confirmed) return;
    }
    isVisible.value = false;
};

// 設定更新の処理
const handleUpdateSettings = (newSettings: IRecordSettings) => {
    currentSettings.value = newSettings;
};

// 保存処理
const handleSave = async () => {
    if (!hasChanges.value || isSaving.value || !currentSettings.value || !props.reservation) return;

    // バリデーションチェック
    const captionIsDefault = currentSettings.value.caption_recording_mode === 'Default';
    const dataBroadcastingIsDefault = currentSettings.value.data_broadcasting_recording_mode === 'Default';
    if (captionIsDefault !== dataBroadcastingIsDefault) {
        Message.warning('字幕データ録画設定・データ放送録画設定を明示的に設定する際は、両方とも「デフォルト設定を使う」以外に設定してください。');
        return;
    }

    isSaving.value = true;
    try {
        const result = await Reservations.updateReservation(props.reservation.id, currentSettings.value);
        if (result) {
            Message.success('録画設定の変更を保存しました。');
            const updatedReservation = { ...props.reservation, record_settings: currentSettings.value };
            emit('updated', updatedReservation);
            hasChanges.value = false;
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        Message.error('録画設定の保存に失敗しました。');
    } finally {
        isSaving.value = false;
    }
};

// 削除処理
const handleDelete = () => {
    showDeleteDialog.value = true;
};

// 削除確認
const confirmDelete = async () => {
    showDeleteDialog.value = false;
    if (!props.reservation) return;

    try {
        const success = await Reservations.deleteReservation(props.reservation.id);
        if (success) {
            Message.success('録画予約を削除しました。');
            emit('deleted', props.reservation.id);
            isVisible.value = false;
        }
    } catch (error) {
        console.error('Failed to delete reservation:', error);
    }
};
</script>

<style lang="scss" scoped>
// 背景スクリム
.reservation-detail-drawer__scrim {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1009;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.25s ease, visibility 0.25s ease;
    pointer-events: none;

    &--visible {
        opacity: 1;
        visibility: visible;
        pointer-events: auto;
    }
}

// ドロワー本体
.reservation-detail-drawer {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 370px;
    display: flex;
    flex-direction: column;
    background: rgb(var(--v-theme-background));
    border-top-left-radius: 16px;
    border-bottom-left-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16);
    z-index: 1010;
    transform: translateX(100%);
    transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);

    &--visible {
        transform: translateX(0);
    }

    // スマートフォンでは左側に少しスクリムが見えるように調整
    @media (max-width: 480px) {
        width: calc(100vw - 32px);
        border-top-left-radius: 16px;
        border-bottom-left-radius: 16px;
    }

    &__header {
        display: flex;
        position: relative;
        width: 100%;
        height: 48px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-top-left-radius: 16px;
        overflow: hidden;
    }

    &__tabs {
        display: flex;
        flex: 1;
        padding-left: 48px;
    }

    &__tab {
        display: flex;
        flex: 1;
        align-items: center;
        justify-content: center;
        gap: 8px;
        height: 100%;
        color: rgb(var(--v-theme-text));
        cursor: pointer;
        transition: background-color 0.15s;
        position: relative;

        &:hover {
            background: rgb(var(--v-theme-background-lighten-2));
        }
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                background: rgb(var(--v-theme-background-lighten-1));
            }
        }

        &::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: rgb(var(--v-theme-background-lighten-2));
        }

        &--active {
            color: rgb(var(--v-theme-text));

            &::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: rgb(var(--v-theme-secondary));
            }
        }
    }

    &__tab-text {
        font-size: 15.5px;
        font-weight: 700;
        letter-spacing: 0.04em;
    }

    &__close {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        color: rgb(var(--v-theme-text));
        cursor: pointer;
        transition: background-color 0.15s;

        &:hover {
            background: rgb(var(--v-theme-background-lighten-2));
        }
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                background: rgb(var(--v-theme-background-lighten-1));
            }
        }
    }

    &__content {
        display: flex;
        flex-direction: column;
        flex: 1;
        overflow-y: auto;
        background: rgb(var(--v-theme-background));
    }

    &__info,
    &__settings {
        padding: 16px;
    }

    &__footer {
        display: flex;
        position: relative;
        width: 100%;
        height: 52px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-top: 1px solid rgb(var(--v-theme-background-lighten-2));
        border-bottom-left-radius: 16px;
        overflow: hidden;
    }

    &__actions {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-left: auto;
        padding: 8px 16px;
    }
}

// 警告バナー
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

    // キーワード自動予約の警告（警告色）
    &--keyword {
        background-color: rgb(var(--v-theme-warning-darken-3), 0.5);

        .warning-banner__icon {
            color: rgb(var(--v-theme-warning));
        }

        .warning-banner__text {
            color: rgb(var(--v-theme-warning-lighten-1));
        }
    }

    // 録画中の警告（エラー色）
    &--recording {
        background-color: rgb(var(--v-theme-error-darken-3), 0.5);

        .warning-banner__icon {
            color: rgb(var(--v-theme-error));
        }

        .warning-banner__text {
            color: rgb(var(--v-theme-error-lighten-1));
        }
    }

    // 通常の警告（情報色）
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