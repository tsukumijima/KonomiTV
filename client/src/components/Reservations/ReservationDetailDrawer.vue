<template>
    <v-navigation-drawer
        v-model="isVisible"
        location="right"
        width="370"
        temporary
        class="reservation-detail-drawer"
        scrim="rgb(var(--v-theme-background))"
        @click:outside="handleClose">

        <!-- ヘッダー -->
        <div class="reservation-detail-drawer__header">
            <div class="reservation-detail-drawer__tabs">
                <div class="reservation-detail-drawer__tab"
                    :class="{ 'reservation-detail-drawer__tab--active': activeTab === 'info' }"
                    @click="activeTab = 'info'">
                    <Icon icon="fluent:info-16-regular" width="20px" height="20px" />
                    <span class="reservation-detail-drawer__tab-text">番組情報</span>
                </div>
                <div class="reservation-detail-drawer__tab"
                    :class="{ 'reservation-detail-drawer__tab--active': activeTab === 'settings' }"
                    @click="activeTab = 'settings'">
                    <Icon icon="material-symbols:settings-video-camera-outline-rounded" width="20px" height="20px" />
                    <span class="reservation-detail-drawer__tab-text">録画設定</span>
                </div>
            </div>
            <div class="reservation-detail-drawer__close" @click="handleClose">
                <Icon icon="fluent:dismiss-16-filled" width="22px" height="22px" />
            </div>
        </div>

        <!-- コンテンツ -->
        <div class="reservation-detail-drawer__content">
            <!-- 番組情報タブ -->
            <div v-if="activeTab === 'info'" class="reservation-detail-drawer__info">
                <ReservationProgramInfo :reservation="reservation" />
            </div>

            <!-- 録画設定タブ -->
            <div v-if="activeTab === 'settings'" class="reservation-detail-drawer__settings">
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
                    variant="text"
                    @click="handleDelete">
                    <Icon icon="fluent:delete-16-regular" width="20px" height="20px" />
                    <span class="ml-1">予約削除</span>
                </v-btn>
                <v-btn
                    v-if="activeTab === 'settings'"
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
    </v-navigation-drawer>

    <!-- 削除確認ダイアログ -->
    <v-dialog v-model="showDeleteDialog" max-width="700">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                録画予約を削除しますか？
            </v-card-title>
            <v-card-text class="pt-2 pb-0">
                <div class="mb-4">
                    <div class="text-h6 mb-2">{{ reservation.program.title }}</div>
                    <div class="text-body-2 text-text-darken-1">
                        {{ ProgramUtils.getProgramTime(reservation.program) }}
                    </div>
                </div>
                <div v-if="isKeywordAutoReservation" class="text-warning font-weight-bold">
                    ⚠️ この予約はキーワード自動予約で追加されました。<br>
                    削除してもすぐに再追加される可能性があります。<br>
                    不要な場合は削除ではなく「無効」にすることをおすすめします。
                </div>
                <div v-else class="text-error-lighten-1 font-weight-bold">
                    <template v-if="isPastProgram">
                        この録画予約を削除すると、録画は行われません。
                    </template>
                    <template v-else>
                        番組の放送開始前に削除すると、録画は行われません。
                    </template>
                </div>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer></v-spacer>
                <v-btn color="text" variant="text" @click="showDeleteDialog = false">
                    キャンセル
                </v-btn>
                <v-btn color="error" variant="flat" @click="confirmDelete">
                    削除
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
    reservation: IReservation;
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
    return props.reservation.comment.includes('EPG自動予約');
});

// 過去の番組かどうか
const isPastProgram = computed(() => {
    const now = new Date();
    const programEnd = new Date(props.reservation.program.end_time);
    return programEnd < now;
});

// ドロワーが開かれた時の処理
watch(isVisible, (newValue) => {
    if (newValue) {
        // 開かれた時は番組情報タブを表示
        activeTab.value = 'info';
        hasChanges.value = false;
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
    if (!hasChanges.value || isSaving.value || !currentSettings.value) return;

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
.reservation-detail-drawer {
    border-left: 1px solid rgb(var(--v-theme-background-lighten-2));

    &__header {
        display: flex;
        position: relative;
        width: 100%;
        height: 48px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
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

        &--active {
            color: rgb(var(--v-theme-text));

            &::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: rgb(var(--v-theme-primary));
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
    }

    &__content {
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        background: rgb(var(--v-theme-background));
    }

    &__info,
    &__settings {
        flex: 1;
        padding: 16px;
    }

    &__footer {
        display: flex;
        position: relative;
        width: 100%;
        height: 52px;
        background: rgb(var(--v-theme-background-lighten-1));
        border-top: 1px solid rgb(var(--v-theme-background-lighten-2));
    }

    &__actions {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-left: auto;
        padding: 8px 16px;
    }
}
</style>