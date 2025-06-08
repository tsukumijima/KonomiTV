<template>
    <div class="reservation" :class="{ 'reservation--disabled': !reservation.record_settings.is_enabled }">
        <div class="reservation__container">
            <!-- 左側：優先度と有効・無効スイッチ -->
            <div class="reservation__controls">
                <div class="reservation__priority">
                    <div class="reservation__priority-badge">{{ reservation.record_settings.priority }}</div>
                    <div class="reservation__priority-label">優先度</div>
                </div>
                <div class="reservation__toggle">
                    <v-switch
                        v-model="is_enabled"
                        color="primary"
                        density="compact"
                        hide-details
                        @update:model-value="handleToggleEnabled"
                    ></v-switch>
                    <div class="reservation__toggle-label">{{ is_enabled ? '有効' : '無効' }}</div>
                </div>
            </div>

            <!-- 中央：番組情報 -->
            <div class="reservation__content">
                <div class="reservation__content-header">
                    <div class="reservation__content-title"
                        v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'title')"></div>
                    <div class="reservation__content-status">
                        <v-chip
                            :color="getReservationStatusColor(reservation)"
                            size="small"
                            variant="tonal"
                        >
                            <Icon :icon="getReservationStatusIcon(reservation)" width="12px" height="12px" class="mr-1" />
                            {{ getReservationStatusLabel(reservation) }}
                        </v-chip>
                    </div>
                </div>

                <div class="reservation__content-meta">
                    <div class="reservation__content-meta-broadcaster">
                        <img class="reservation__content-meta-broadcaster-icon" loading="lazy" decoding="async"
                            :src="`${Utils.api_base_url}/channels/${reservation.channel.id}/logo`"
                            @error="onLogoError">
                        <span class="reservation__content-meta-broadcaster-name">Ch: {{ reservation.channel.channel_number }} {{ reservation.channel.name }}</span>
                    </div>
                    <div class="reservation__content-meta-time">{{ ProgramUtils.getProgramTime(reservation.program) }}</div>
                    <div class="reservation__content-meta-size-comment">
                        <div class="reservation__content-meta-size">
                            <Icon icon="fluent:hard-drive-20-filled" width="14px" height="14px" class="mr-1" />
                            予想: {{ getDummyFileSize() }}
                        </div>
                        <div v-if="reservation.comment" class="reservation__content-meta-comment">
                            <Icon icon="fluent:note-20-filled" width="14px" height="14px" class="mr-1" />
                            {{ reservation.comment }}
                        </div>
                    </div>
                </div>

                <div class="reservation__content-description"
                    v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'description')"></div>
            </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
import { ref, watch } from 'vue';

import Reservations, { IReservation } from '@/services/Reservations';
import { useSnackbarsStore } from '@/stores/SnackbarsStore';
import Utils, { ProgramUtils } from '@/utils';

// Props
const props = defineProps<{
    reservation: IReservation;
}>();

// Emits
const emit = defineEmits<{
    (e: 'deleted', reservation_id: number): void;
}>();

const snackbarsStore = useSnackbarsStore();

// 有効・無効の状態を管理
const is_enabled = ref(props.reservation.record_settings.is_enabled);
const is_updating = ref(false);

// propsの変更を監視
watch(() => props.reservation.record_settings.is_enabled, (newValue) => {
    is_enabled.value = newValue;
});

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

    switch (reservation.recording_availability) {
        case 'Full':
            return '録画可能';
        case 'Partial':
            return '一部録画';
        case 'Unavailable':
            return '録画不可';
        default:
            return '不明';
    }
};

// 予約状態のアイコンを取得
const getReservationStatusIcon = (reservation: IReservation): string => {
    if (reservation.is_recording_in_progress) {
        return 'fluent:record-20-filled';
    }

    switch (reservation.recording_availability) {
        case 'Full':
            return 'fluent:checkmark-circle-20-regular';
        case 'Partial':
            return 'fluent:warning-20-regular';
        case 'Unavailable':
            return 'fluent:dismiss-circle-20-regular';
        default:
            return 'fluent:question-circle-20-regular';
    }
};

// 予約状態の色を取得
const getReservationStatusColor = (reservation: IReservation): string => {
    if (reservation.is_recording_in_progress) {
        return 'primary';
    }

    switch (reservation.recording_availability) {
        case 'Full':
            return 'success';
        case 'Partial':
            return 'warning';
        case 'Unavailable':
            return 'error';
        default:
            return 'grey';
    }
};

// ダミーファイルサイズを生成
const getDummyFileSize = (): string => {
    // 番組時間に基づいてダミーサイズを算出
    const duration = ProgramUtils.getProgramDuration(props.reservation.program);
    const durationMatch = duration.match(/(\d+)分/);
    const minutes = durationMatch ? parseInt(durationMatch[1]) : 30;

    // 1分あたり約60MBと仮定してサイズを計算
    const sizeInMB = Math.round(minutes * 60 / 10) * 10; // 10MB単位で四捨五入

    if (sizeInMB >= 1000) {
        return `${(sizeInMB / 1000).toFixed(1)}GB`;
    } else {
        return `${sizeInMB}MB`;
    }
};

// 有効・無効の切り替え処理
const handleToggleEnabled = async () => {
    if (is_updating.value) return;

    is_updating.value = true;
    try {
        // 録画設定を更新
        const updatedSettings = {
            ...props.reservation.record_settings,
            is_enabled: is_enabled.value,
        };

        const result = await Reservations.updateReservation(props.reservation.id, updatedSettings);
        if (result) {
            snackbarsStore.show('success', `予約を${is_enabled.value ? '有効' : '無効'}にしました。`);
        } else {
            // 失敗時は元の状態に戻す
            is_enabled.value = props.reservation.record_settings.is_enabled;
        }
    } catch (error) {
        console.error('Failed to update reservation:', error);
        // 失敗時は元の状態に戻す
        is_enabled.value = props.reservation.record_settings.is_enabled;
    } finally {
        is_updating.value = false;
    }
};

</script>

<style lang="scss" scoped>
.reservation {
    display: flex;
    position: relative;
    width: 100%;
    min-height: auto;
    padding: 0px 16px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s, opacity 0.15s;
    text-decoration: none;
    user-select: none;
    box-sizing: border-box;
    content-visibility: auto;
    @include smartphone-vertical {
        padding: 0px 9px;
    }

    &--disabled {
        opacity: 0.65;
    }

    &__container {
        display: flex;
        align-items: center;
        width: 100%;
        min-height: auto;
        padding: 12px 16px;
        @include smartphone-vertical {
            padding: 8px 0px;
        }
    }

    &__controls {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex-shrink: 0;
        margin-right: 16px;
        @include smartphone-vertical {
            margin-right: 8px;
        }
    }

    &__priority {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 0px 7px;  // 下のスイッチと揃えるため
        margin-bottom: 6px;
        @include smartphone-vertical {
            margin-bottom: 12px;
        }

        &-badge {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: rgb(var(--v-theme-primary));
            color: white;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 3px;
            @include smartphone-vertical {
                width: 24px;
                height: 24px;
                font-size: 12px;
                margin-bottom: 2px;
            }
        }

        &-label {
            font-size: 10px;
            color: rgb(var(--v-theme-text-darken-1));
            text-align: center;
            @include smartphone-vertical {
                font-size: 9px;
            }
        }
    }

    &__toggle {
        display: flex;
        flex-direction: column;
        align-items: center;

        :deep(.v-switch) {
            .v-selection-control {
                min-height: unset;
            }
            .v-selection-control__wrapper {
                height: 18px;
                @include smartphone-vertical {
                    height: 16px;
                }
            }
        }

        &-label {
            font-size: 10px;
            color: rgb(var(--v-theme-text-darken-1));
            text-align: center;
            margin-top: 2px;
            @include smartphone-vertical {
                font-size: 9px;
            }
        }
    }

    &__content {
        display: flex;
        flex-direction: column;
        justify-content: center;
        flex-grow: 1;
        min-width: 0;

        &-header {
            display: flex;
            align-items: center;
            margin-bottom: 2px;
        }

        &-title {
            flex-grow: 1;
            font-size: 17px;
            font-weight: 600;
            font-feature-settings: "palt" 1;
            letter-spacing: 0.07em;
            line-height: 1.35;
            margin-right: 12px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 1;
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                font-size: 15px;
            }
            @include smartphone-horizontal {
                font-size: 14px;
            }
            @include smartphone-vertical {
                font-size: 13px;
                line-height: 1.45;
                margin-right: 8px;
                -webkit-line-clamp: 2;
            }
        }

        &-status {
            flex-shrink: 0;

            :deep(.v-chip) {
                @include smartphone-vertical {
                    height: 22px !important;
                    font-size: 11px !important;
                    padding: 0 6px !important;
                }
            }
        }

        &-meta {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 2px;
            font-size: 13.8px;
            @include tablet-vertical {
                gap: 3px 6px;
            }
            @include smartphone-horizontal {
                gap: 3px 6px;
            }
            @include smartphone-vertical {
                row-gap: 1px;
                font-size: 12px;
            }

            &-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;
                @include smartphone-vertical {
                    margin-bottom: 2px;
                }

                &-icon {
                    flex-shrink: 0;
                    width: 28px;
                    height: 16px;
                    margin-right: 10px;
                    border-radius: 2px;
                    background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                    object-fit: cover;
                    @include smartphone-vertical {
                        width: 24px;
                        height: 14px;
                        margin-right: 4px;
                    }
                }

                &-name {
                    color: rgb(var(--v-theme-text-darken-1));
                    white-space: nowrap;
                    overflow: hidden;
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
                color: rgb(var(--v-theme-text-darken-1));
                border-left: 1px solid rgb(var(--v-theme-text-darken-1));
                padding-left: 10px;
                height: 16px;
                line-height: 15.5px;
                @include tablet-vertical {
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-vertical {
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 11.4px;
                }
            }

            &-size,
            &-comment {
                display: flex;
                align-items: center;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 12.5px;
                white-space: nowrap;
                @include tablet-vertical {
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    font-size: 12px;
                }
                @include smartphone-vertical {
                    font-size: 11px;
                }
            }
            &-size-comment {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
            }

            &-comment {
                border-left: 1px solid rgb(var(--v-theme-text-darken-1));
                padding-left: 8px;
                @include tablet-vertical {
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                }
                @include smartphone-horizontal {
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                }
                @include smartphone-vertical {
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                }
            }
        }

        &-description {
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 11.5px;
            line-height: 1.55;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;
            letter-spacing: 0.07em;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            @include tablet-vertical {
                font-size: 11px;
            }
            @include smartphone-horizontal {
                font-size: 11px;
            }
            @include smartphone-vertical {
                display: none;
            }
        }
    }
}
</style>