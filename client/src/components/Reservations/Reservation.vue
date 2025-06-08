<template>
    <div class="reservation" :class="{ 'reservation--conflict': reservation.recording_availability !== 'Full' }">
        <div class="reservation__container">
            <div class="reservation__thumbnail">
                <img class="reservation__thumbnail-image" loading="lazy" decoding="async"
                    :src="`${Utils.api_base_url}/channels/${reservation.channel.id}/logo`"
                    @error="onLogoError">
                <div class="reservation__thumbnail-duration">{{ ProgramUtils.getProgramDuration(reservation.program) }}</div>
                <div v-if="reservation.is_recording_in_progress" class="reservation__thumbnail-status reservation__thumbnail-status--recording">
                    <div class="reservation__thumbnail-status-dot"></div>
                    録画中
                </div>
                <div v-else-if="reservation.recording_availability !== 'Full'" class="reservation__thumbnail-status reservation__thumbnail-status--conflict">
                    ⚠️ 競合
                </div>
            </div>
            <div class="reservation__content">
                <div class="reservation__content-title"
                    v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'title')"></div>
                <div class="reservation__content-meta">
                    <div class="reservation__content-meta-broadcaster">
                        <img class="reservation__content-meta-broadcaster-icon" loading="lazy" decoding="async"
                            :src="`${Utils.api_base_url}/channels/${reservation.channel.id}/logo`"
                            @error="onLogoError">
                        <span class="reservation__content-meta-broadcaster-name">Ch: {{ reservation.channel.channel_number }} {{ reservation.channel.name }}</span>
                    </div>
                    <div class="reservation__content-meta-time">{{ ProgramUtils.getProgramTime(reservation.program) }}</div>
                </div>
                <div class="reservation__content-description"
                    v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'description')"></div>
            </div>
            <div class="reservation__status">
                <v-chip
                    :color="getReservationStatusColor(reservation)"
                    size="small"
                >
                    {{ getReservationStatusLabel(reservation) }}
                </v-chip>
            </div>
            <div class="reservation__menu">
                <v-menu location="bottom end" :close-on-content-click="true">
                    <template v-slot:activator="{ props }">
                        <div v-ripple class="reservation__menu-button"
                            v-bind="props"
                            @click.prevent.stop=""
                            @mousedown.prevent.stop="">
                            <svg width="19px" height="19px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M9.5 13a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0"/>
                            </svg>
                        </div>
                    </template>
                    <v-list density="compact" bg-color="background-lighten-1" class="reservation__menu-list">
                        <v-list-item @click="showDeleteConfirmation">
                            <template v-slot:prepend>
                                <Icon icon="fluent:delete-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">予約を削除</v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </div>
        </div>
    </div>

    <!-- 予約削除確認ダイアログ -->
    <v-dialog max-width="450" v-model="show_delete_confirmation">
        <v-card>
            <v-card-title class="text-h6">予約の削除</v-card-title>
            <v-card-text>
                「{{ reservation.program.title }}」を削除しますか？<br>
                この操作は取り消せません。
            </v-card-text>
            <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn color="secondary" @click="show_delete_confirmation = false">キャンセル</v-btn>
                <v-btn color="error" @click="deleteReservation" :loading="is_deleting">削除</v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { ref } from 'vue';

import Reservations, { IReservation } from '@/services/Reservations';
import { useSnackbarsStore } from '@/stores/SnackbarsStore';
import Utils, { ProgramUtils, dayjs } from '@/utils';

// Props
const props = defineProps<{
    reservation: IReservation;
}>();

// Emits
const emit = defineEmits<{
    (e: 'deleted', reservation_id: number): void;
}>();

const snackbarsStore = useSnackbarsStore();

// 削除確認ダイアログの表示状態
const show_delete_confirmation = ref(false);
const is_deleting = ref(false);

// ロゴ画像エラー時のフォールバック
const onLogoError = (event: Event) => {
    const target = event.target as HTMLImageElement;
    target.src = `${Utils.api_base_url}/channels/gr001/logo`;
};

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

// 予約削除確認ダイアログを表示
const showDeleteConfirmation = () => {
    show_delete_confirmation.value = true;
};

// 予約削除
const deleteReservation = async () => {
    is_deleting.value = true;
    try {
        const result = await Reservations.deleteReservation(props.reservation.id);
        if (result) {
            snackbarsStore.show('success', '予約を削除しました。');
            emit('deleted', props.reservation.id);
        }
        // エラー時のメッセージ表示は Reservations.deleteReservation() 内で処理済み
    } catch (error) {
        console.error('Failed to delete reservation:', error);
        // エラー時のメッセージ表示は Reservations.deleteReservation() 内で処理済み
    } finally {
        is_deleting.value = false;
        show_delete_confirmation.value = false;
    }
};

</script>
<style lang="scss" scoped>

.reservation {
    display: flex;
    position: relative;
    width: 100%;
    height: 125px;
    padding: 0px 16px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s;
    text-decoration: none;
    user-select: none;
    box-sizing: border-box;
    content-visibility: auto;
    contain-intrinsic-height: auto 125px;
    @include smartphone-vertical {
        height: auto;
        padding: 0px 9px;
        contain-intrinsic-height: auto 115px;
    }

    &--conflict {
        border-left: 3px solid rgb(var(--v-theme-error));
    }

    &__container {
        display: flex;
        align-items: center;
        width: 100%;
        height: 100%;
        padding: 12px 0px;
        @include smartphone-vertical {
            padding: 8px 0px;
        }
    }

    &__thumbnail {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        aspect-ratio: 16 / 9;
        height: 100%;
        border-radius: 4px;
        overflow: hidden;
        position: relative;
        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
        @include smartphone-vertical {
            width: 120px;
            height: auto;
            aspect-ratio: 3 / 2;
        }

        &-image {
            width: 100%;
            border-radius: 4px;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            @include smartphone-vertical {
                aspect-ratio: 3 / 2;
            }
        }

        &-duration {
            position: absolute;
            right: 4px;
            bottom: 4px;
            padding: 3px 4px;
            border-radius: 2px;
            background: rgba(0, 0, 0, 0.7);
            color: #fff;
            font-size: 11px;
            line-height: 1;
            @include smartphone-vertical {
                font-size: 10.5px;
            }
        }

        &-status {
            display: flex;
            align-items: center;
            gap: 4px;
            position: absolute;
            top: 4px;
            right: 4px;
            padding: 4px 6px;
            border-radius: 2px;
            font-size: 10.5px;
            font-weight: 700;
            line-height: 1;
            background: rgba(var(--v-theme-background-lighten-1), 0.9);
            color: rgba(255, 255, 255, 0.85);

            &--conflict {
                background: rgba(var(--v-theme-error), 0.9);
            }

            &-dot {
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #ff4444;
                animation: blink 1.5s infinite;
            }
        }
    }

    &__content {
        display: flex;
        flex-direction: column;
        justify-content: center;
        flex-grow: 1;
        min-width: 0;  // magic!
        margin-left: 16px;
        margin-right: 40px;
        @include tablet-vertical {
            margin-right: 16px;
        }
        @include smartphone-horizontal {
            margin-right: 20px;
        }
        @include smartphone-vertical {
            margin-left: 12px;
            margin-right: 0px;
        }

        &-title {
            display: -webkit-box;
            font-size: 17px;
            font-weight: 600;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 1;  // 1行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                font-size: 15px;
            }
            @include smartphone-horizontal {
                font-size: 14px;
            }
            @include smartphone-vertical {
                margin-right: 24px;
                font-size: 13px;
                line-height: 1.45;
                -webkit-line-clamp: 2;  // 2行までに制限
            }
        }

        &-meta {
            display: flex;
            align-items: center;
            margin-top: 4px;
            font-size: 13.8px;
            @include tablet-vertical {
                flex-wrap: wrap;
            }
            @include smartphone-horizontal {
                margin-top: 6px;
                flex-wrap: wrap;
            }
            @include smartphone-vertical {
                flex-wrap: wrap;
                margin-top: 4px;
                font-size: 12px;
            }

            &-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;  // magic!

                &-icon {
                    flex-shrink: 0;
                    width: 28px;
                    height: 16px;
                    margin-right: 10px;
                    border-radius: 2px;
                    // 読み込まれるまでのアイコンの背景
                    background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                    object-fit: cover;
                    @include smartphone-vertical {
                        margin-right: 4px;
                        width: 24px;
                        height: 14px;
                    }
                }

                &-name {
                    color: rgb(var(--v-theme-text-darken-1));
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include tablet-vertical {
                        font-size: 13px;
                    }
                    @include smartphone-horizontal {
                        font-size: 13px;
                    }
                    @include smartphone-vertical {
                        margin-left: 4px;
                        font-size: 12px;
                    }
                }
            }

            &-time {
                display: inline-block;
                flex-shrink: 0;
                margin-left: 10px;
                color: rgb(var(--v-theme-text-darken-1));
                border-left: 1px solid rgb(var(--v-theme-text-darken-1));
                padding-left: 10px;
                height: 16px;
                line-height: 15.5px;
                @include tablet-vertical {
                    margin-top: 2px;
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    margin-top: 2px;
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-vertical {
                    margin-top: 1px;
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 11.4px;
                }
            }
        }

        &-description {
            display: -webkit-box;
            margin-top: 6px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 11.5px;
            line-height: 1.55;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                margin-top: 3.5px;
                font-size: 11px;
            }
            @include smartphone-horizontal {
                margin-top: 3.5px;
                font-size: 11px;
            }
            @include smartphone-vertical {
                margin-top: 1.5px;
                font-size: 11px;
                line-height: 1.45;
                -webkit-line-clamp: 1;  // 1行までに制限
            }
        }
    }

    &__status {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        position: absolute;
        top: 38%;
        right: 12px;
        transform: translateY(-50%);
        @include tablet-vertical {
            right: 6px;
        }
        @include smartphone-horizontal {
            right: 6px;
        }
        @include smartphone-vertical {
            right: 4px;
        }
    }

    &__menu {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        position: absolute;
        top: 65%;
        right: 12px;
        transform: translateY(-50%);
        cursor: pointer;
        @include tablet-vertical {
            right: 6px;
        }
        @include smartphone-horizontal {
            right: 6px;
        }
        @include smartphone-vertical {
            right: 4px;
        }

        &-button {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            color: rgb(var(--v-theme-text-darken-1));
            border-radius: 50%;
            transition: color 0.15s ease, background-color 0.15s ease;
            user-select: none;
            @include tablet-vertical {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }
            @include smartphone-horizontal {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }
            @include smartphone-vertical {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }

            &:before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                border-radius: inherit;
                background-color: currentColor;
                color: inherit;
                opacity: 0;
                transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
                pointer-events: none;
            }
            &:hover {
                color: rgb(var(--v-theme-text));
                &:before {
                    opacity: 0.15;
                }
            }
            // タッチデバイスで hover を無効にする
            @media (hover: none) {
                &:hover {
                    &:before {
                        opacity: 0;
                    }
                }
            }
        }

        &-list {
            :deep(.v-list-item-title) {
                font-size: 14px !important;
            }

            :deep(.v-list-item) {
                min-height: 36px !important;
            }
        }
    }
}

@keyframes blink {
    0% { opacity: 0; }
    50% { opacity: 1; }
    100% { opacity: 0; }
}

</style>