<template>
    <div class="reservation-list">
        <div v-if="title" class="reservation-list__header">
            <h2 class="reservation-list__title">{{ title }}</h2>
            <div class="reservation-list__actions">
                <v-btn
                    v-if="showMoreButton"
                    variant="text"
                    class="reservation-list__more"
                    @click="$emit('more')"
                >
                    <span class="text-primary">もっと見る</span>
                    <Icon icon="fluent:chevron-right-12-regular" width="18px" class="ml-1 text-text-darken-1" style="margin: 0px -4px;" />
                </v-btn>
            </div>
        </div>

        <div v-if="isLoading && reservations.length === 0" class="reservation-list__loading">
            <v-progress-circular indeterminate size="32"></v-progress-circular>
        </div>

        <div v-else-if="showEmptyMessage && reservations.length === 0" class="reservation-list__empty">
            <v-icon :size="48" color="grey">{{ emptyIcon || 'mdi-calendar-blank' }}</v-icon>
            <div class="reservation-list__empty-message">
                <p v-html="emptyMessage || '近日中の予約はありません。'" class="text-white"></p>
                <p v-html="emptySubMessage || '番組表から新しい予約を追加できます。'" class="reservation-list__empty-submessage text-white"></p>
            </div>
        </div>

        <div v-else class="reservation-list__table-container">
            <table class="reservation-list__table">
                <thead>
                    <tr>
                        <th class="reservation-list__table-channel">チャンネル</th>
                        <th class="reservation-list__table-program">番組名</th>
                        <th class="reservation-list__table-time">放送時間</th>
                        <th class="reservation-list__table-status">状態</th>
                        <th class="reservation-list__table-actions">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="reservation in reservations" :key="reservation.id" class="reservation-list__row"
                        :class="{ 'reservation-list__row--conflict': reservation.recording_availability !== 'Full' }">
                        <td class="reservation-list__channel">
                            {{ reservation.channel.name }}
                        </td>
                        <td class="reservation-list__program">
                            {{ reservation.program.title }}
                            <v-chip v-if="reservation.recording_availability !== 'Full'" color="error" size="x-small" class="ml-1">競合</v-chip>
                        </td>
                        <td class="reservation-list__time">
                            <div>{{ formatDateTime(reservation.program.start_time) }}</div>
                        </td>
                        <td class="reservation-list__status">
                            <v-chip
                                :color="getReservationStatusColor(reservation)"
                                size="small"
                            >
                                {{ getReservationStatusLabel(reservation) }}
                            </v-chip>
                        </td>
                        <td class="reservation-list__actions">
                            <v-btn icon="mdi-delete" variant="tonal" size="small" @click="onClickDelete(reservation)" :loading="deleting_reservation_id === reservation.id"></v-btn>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        <!-- 確認ダイアログ -->
        <v-dialog v-model="show_confirm_dialog" max-width="450">
            <v-card>
                <v-card-title class="text-h6">予約の削除</v-card-title>
                <v-card-text>
                    「{{ deleting_reservation_title }}」を削除しますか？<br>
                    この操作は取り消せません。
                </v-card-text>
                <v-card-actions>
                    <v-spacer></v-spacer>
                    <v-btn color="secondary" @click="show_confirm_dialog = false">キャンセル</v-btn>
                    <v-btn color="error" @click="confirmDeleteReservation" :loading="is_deleting">削除</v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </div>
</template>

<script lang="ts" setup>
import { ref, PropType } from 'vue';
import dayjs from 'dayjs';
import 'dayjs/locale/ja';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import relativeTime from 'dayjs/plugin/relativeTime';

import { IReservation } from '@/services/Reservations';
import Reservations from '@/services/Reservations';
import { useSnackbarsStore } from '@/stores/SnackbarsStore';

dayjs.extend(relativeTime);
dayjs.extend(customParseFormat);
dayjs.locale('ja');

const snackbarsStore = useSnackbarsStore();

const formatDateTime = (dateString: string): string => {
    return dayjs(dateString).format('YYYY年MM月DD日 HH:mm');
};

const props = defineProps({
    reservations: {
        type: Array as PropType<IReservation[]>,
        required: true,
    },
    total: {
        type: Number,
        required: true,
    },
    title: {
        type: String,
        default: '',
    },
    isLoading: {
        type: Boolean,
        default: false,
    },
    showEmptyMessage: {
        type: Boolean,
        default: true,
    },
    emptyIcon: {
        type: String,
        default: 'mdi-calendar-blank',
    },
    emptyMessage: {
        type: String,
        default: '現在、録画予約はありません。',
    },
    emptySubMessage: {
        type: String,
        default: '番組表から録画予約を追加できます。',
    },
    showMoreButton: {
        type: Boolean,
        default: false,
    },
});

const emit = defineEmits<{
    (e: 'more'): void;
    (e: 'delete', reservation_id: number): void;
}>();

// 予約状態のラベルを取得
const getReservationStatusLabel = (reservation: IReservation): string => {
    if (reservation.is_recording_in_progress) {
        return '録画中';
    }
    if (reservation.recording_availability !== 'Full') {
        return '競合';
    }
    return dayjs(reservation.program.end_time).isBefore(dayjs()) ? '終了' : '予約済み';
};

// 予約状態の色を取得
const getReservationStatusColor = (reservation: IReservation): string => {
    if (reservation.is_recording_in_progress) {
        return 'primary';
    }
    if (reservation.recording_availability !== 'Full') {
        return 'error';
    }
    return dayjs(reservation.program.end_time).isBefore(dayjs()) ? 'grey' : 'success';
};

// 削除関連
const show_confirm_dialog = ref(false);
const deleting_reservation_id = ref<number | null>(null);
const deleting_reservation_title = ref<string>('');
const is_deleting = ref(false);

const onClickDelete = (reservation: IReservation) => {
    deleting_reservation_id.value = reservation.id;
    deleting_reservation_title.value = reservation.program.title;
    show_confirm_dialog.value = true;
};

const confirmDeleteReservation = async () => {
    if (deleting_reservation_id.value === null) return;
    is_deleting.value = true;
    try {
        const result = await Reservations.deleteReservation(deleting_reservation_id.value);
        if (result === true) {
            snackbarsStore.show('success', '予約を削除しました。');
            emit('delete', deleting_reservation_id.value);
        } else if (typeof result === 'object' && result.detail) {
            snackbarsStore.show('error', `予約の削除に失敗しました。${result.detail}`);
        } else {
            snackbarsStore.show('error', '予約の削除に失敗しました。');
        }
    } catch (error) {
        console.error('Failed to delete reservation:', error);
        snackbarsStore.show('error', '予約の削除に失敗しました。');
    } finally {
        is_deleting.value = false;
        show_confirm_dialog.value = false;
    }
};

</script>

<style lang="scss" scoped>
.reservation-list {
    display: flex;
    flex-direction: column;
    width: 100%;

    &__header {
        display: flex;
        align-items: center;
        margin-bottom: 12px;
    }

    &__title {
        font-size: 24px;
        font-weight: 700;
        margin: 0;
        @include smartphone-vertical {
            font-size: 22px;
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
    }

    &__more {
        padding: 0px 10px;
        font-size: 15px;
        letter-spacing: 0.05em;
    }

    &__loading {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 32px;
        min-height: 150px;
    }

    &__empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 24px 16px;
        text-align: center;
        color: rgb(var(--v-theme-on-surface-variant));
        border: 1px dashed rgba(var(--v-theme-on-surface), 0.12);
        border-radius: 8px;
        min-height: 150px;
    }

    &__empty-message {
        margin-top: 16px;
        font-size: 1.1rem;
        font-weight: bold;
        p {
            margin-bottom: 4px;
        }
    }

    &__empty-submessage {
        margin-top: 8px;
        font-size: 0.9rem;
        color: rgb(var(--v-theme-on-surface-variant), 0.8);
    }

    &__table-container {
        overflow-x: auto;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
    }

    &__table {
        width: 100%;
        border-collapse: collapse;

        th {
            padding: 12px 16px;
            text-align: left;
            white-space: nowrap;
            font-weight: bold;
            color: rgb(var(--v-theme-on-surface));
            border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        }

        td {
            padding: 12px 16px;
            text-align: left;
            white-space: nowrap;
            color: rgb(var(--v-theme-on-surface));
            border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        }

        tr:last-child td {
            border-bottom: none;
        }
    }

    &__row {
        &--conflict {
            td:first-child {
                border-left: 3px solid rgb(var(--v-theme-error));
            }
        }
    }

    &__channel {
        min-width: 120px;
    }

    &__program {
        min-width: 200px;
        max-width: 250px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    &__time {
        min-width: 160px;
        font-size: 0.95em;
    }

    &__status {
        min-width: 100px;
    }

    &__actions {
        min-width: 80px;
        text-align: right;
    }
}
</style>
