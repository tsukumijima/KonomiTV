<template>
    <div class="reservation-list" :class="{'reservation-list--show-sort': !hideSort}">
        <div class="reservation-list__header" v-if="!hideHeader">
            <h2 class="reservation-list__title">
                <div v-if="showBackButton" v-ripple class="reservation-list__title-back" @click="$router.back()">
                    <Icon icon="fluent:chevron-left-12-filled" width="27px" />
                </div>
                <span class="reservation-list__title-text">{{ title }}</span>
                <div class="reservation-list__title-count" v-if="!showMoreButton">
                    <template v-if="isLoading">
                        <Icon icon="line-md:loading-twotone-loop" class="mr-1 spin" width="20px" height="20px" />
                    </template>
                    <template v-else>{{ displayTotal }}件</template>
                </div>
            </h2>
            <div class="reservation-list__actions">
                <v-select v-if="!hideSort"
                    v-model="sortOrder"
                    :items="[
                        { title: '放送が近い順', value: 'asc' },
                        { title: '放送が遠い順', value: 'desc' },
                    ]"
                    item-title="title"
                    item-value="value"
                    class="reservation-list__sort"
                    color="primary"
                    bg-color="background-lighten-1"
                    variant="solo"
                    density="comfortable"
                    hide-details
                    @update:model-value="$emit('update:sortOrder', $event)">
                </v-select>
                <v-btn v-if="showMoreButton"
                    variant="text"
                    class="reservation-list__more"
                    @click="$emit('more')">
                    <span class="text-primary">もっと見る</span>
                    <Icon icon="fluent:chevron-right-12-regular" width="18px" class="ml-1 text-text-darken-1" style="margin: 0px -4px;" />
                </v-btn>
            </div>
        </div>
        <div class="reservation-list__grid"
            :class="{
                'reservation-list__grid--loading': isLoading,
                'reservation-list__grid--empty': displayTotal === 0 && showEmptyMessage,
            }">
            <div class="reservation-list__empty"
                :class="{
                    'reservation-list__empty--show': displayTotal === 0 && showEmptyMessage && !isLoading,
                }">
                <div class="reservation-list__empty-content">
                    <Icon class="reservation-list__empty-icon" :icon="emptyIcon" width="54px" height="54px" />
                    <h2 v-html="emptyMessage"></h2>
                    <div class="reservation-list__empty-submessage"
                        v-if="emptySubMessage" v-html="emptySubMessage"></div>
                </div>
            </div>
            <div class="reservation-list__grid-content">
                <Reservation v-for="reservation in displayReservations" :key="reservation.id" :reservation="reservation"
                    @deleted="handleReservationDeleted" @click="handleReservationClick" />
            </div>
        </div>
        <div class="reservation-list__pagination" v-if="!hidePagination && displayTotal > 0">
            <v-pagination
                v-model="currentPage"
                active-color="primary"
                density="comfortable"
                :length="Math.ceil(displayTotal / 30)"
                :total-visible="Utils.isSmartphoneVertical() ? 5 : 7"
                @update:model-value="$emit('update:page', $event)">
            </v-pagination>
        </div>

        <!-- 録画予約詳細ドロワー -->
        <ReservationDetailDrawer
            v-model="drawerOpen"
            :reservation="selectedReservation"
            @deleted="handleReservationDeleted"
            @updated="handleReservationSave" />
    </div>
</template>
<script lang="ts" setup>

import { ref, watch } from 'vue';

import Reservation from '@/components/Reservations/Reservation.vue';
import ReservationDetailDrawer from '@/components/Reservations/ReservationDetailDrawer.vue';
import { IReservation } from '@/services/Reservations';
import Utils from '@/utils';

// Props
const props = withDefaults(defineProps<{
    title: string;
    reservations: IReservation[];
    total: number;
    page?: number;
    sortOrder?: 'desc' | 'asc';
    hideHeader?: boolean;
    hideSort?: boolean;
    hidePagination?: boolean;
    showMoreButton?: boolean;
    showBackButton?: boolean;
    showEmptyMessage?: boolean;
    emptyIcon?: string;
    emptyMessage?: string;
    emptySubMessage?: string;
    isLoading?: boolean;
}>(), {
    page: 1,
    sortOrder: 'desc',
    hideHeader: false,
    hideSort: false,
    hidePagination: false,
    showMoreButton: false,
    showBackButton: false,
    showEmptyMessage: true,
    emptyIcon: 'fluent:timer-20-regular',
    emptyMessage: 'まだ録画予約がありません。',
    emptySubMessage: '番組表から録画予約を追加できます。',
    isLoading: false,
});

// 現在のページ番号
const currentPage = ref(props.page);

// 並び順
const sortOrder = ref<'desc' | 'asc'>(props.sortOrder);

// 内部で管理する予約リスト
const displayReservations = ref<IReservation[]>([...props.reservations]);
// 内部で管理する合計数
const displayTotal = ref<number>(props.total);

// ドロワーの状態管理
const drawerOpen = ref(false);
const selectedReservation = ref<IReservation | null>(null);

// props の page が変更されたら currentPage を更新
watch(() => props.page, (newPage) => {
    currentPage.value = newPage;
});

// props の sortOrder が変更されたら sortOrder を更新
watch(() => props.sortOrder, (newOrder) => {
    sortOrder.value = newOrder;
});

// props の reservations が変更されたら displayReservations を更新
watch(() => props.reservations, (newReservations) => {
    displayReservations.value = [...newReservations];
});

// props の total が変更されたら displayTotal を更新
watch(() => props.total, (newTotal) => {
    displayTotal.value = newTotal;
});

// Emits
const emit = defineEmits<{
    (e: 'update:page', page: number): void;
    (e: 'update:sortOrder', order: 'desc' | 'asc'): void;
    (e: 'more'): void;
    (e: 'delete', reservation_id: number): void;
}>();

// 予約がクリックされた時の処理
const handleReservationClick = (reservation: IReservation) => {
    selectedReservation.value = reservation;
    drawerOpen.value = true;
};

// 予約が削除された時の処理
const handleReservationDeleted = (id: number) => {
    // 内部の予約リストから削除された予約を除外
    displayReservations.value = displayReservations.value.filter(reservation => reservation.id !== id);
    // 合計数を1減らす
    displayTotal.value = Math.max(0, displayTotal.value - 1);
    // ドロワーを閉じる
    drawerOpen.value = false;
    // 親コンポーネントに削除イベントを発行
    emit('delete', id);
};

// 予約設定が保存された時の処理
const handleReservationSave = (updatedReservation: IReservation) => {
    // 内部の予約リストで該当する予約を更新
    const index = displayReservations.value.findIndex(r => r.id === updatedReservation.id);
    if (index !== -1) {
        displayReservations.value[index] = updatedReservation;
    }
    // 選択中の予約も更新
    selectedReservation.value = updatedReservation;
};

</script>
<style lang="scss" scoped>

.reservation-list {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;

    &--show-sort {
        .reservation-list__grid {
            @include smartphone-vertical {
                margin-top: 3px;
            }
        }
    }

    &__header {
        display: flex;
        align-items: center;
        @include smartphone-vertical {
            padding: 0px 8px;
        }
    }

    &__title {
        display: flex;
        align-items: center;
        position: relative;
        font-size: 24px;
        font-weight: 700;
        padding-top: 8px;
        padding-bottom: 20px;
        @include smartphone-vertical {
            font-size: 22px;
            padding-bottom: 16px;
        }

        &-back {
            display: none;
            position: absolute;
            left: -8px;
            padding: 6px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
            cursor: pointer;
            @include smartphone-vertical {
                display: flex;
            }

            & + .reservation-list__title-text {
                @include smartphone-vertical {
                    margin-left: 32px;
                }
            }
        }

        &-count {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            padding-top: 8px;
            margin-left: 12px;
            font-size: 14px;
            font-weight: 400;
            color: rgb(var(--v-theme-text-darken-1));

            .spin {
                animation: spin 1.15s linear infinite;
            }

            @keyframes spin {
                from {
                    transform: rotate(0deg);
                }
                to {
                    transform: rotate(360deg);
                }
            }
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
        :deep(.v-field) {
            padding-right: 4px !important;
        }
        :deep(.v-field__input) {
            padding-left: 12px !important;
            padding-right: 0px !important;
        }

        .v-select {
            width: 129px;
        }
    }

    &__sort {
        :deep(.v-field__input) {
            font-size: 14px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            min-height: unset !important;
        }
    }

    &__more {
        margin-bottom: 12px;
        padding: 0px 10px;
        font-size: 15px;
        letter-spacing: 0.05em;
        @include smartphone-vertical {
            margin-bottom: 6px;
        }
    }

    &__grid {
        display: flex;
        flex-direction: column;
        position: relative;
        width: 100%;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
        overflow: hidden;

        &--loading {
            .reservation-list__grid-content {
                visibility: hidden;
                opacity: 0;
            }
        }
        &--empty {
            height: 100%;
            min-height: 200px;
        }

        .reservation-list__grid-content {
            height: 100%;
            transition: visibility 0.2s ease, opacity 0.2s ease;
        }

        :deep(.reservation) {
            // 最後の項目以外の下にボーダーを追加
            &:not(:last-child) > .reservation__container {
                border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
            }
        }
    }

    &__pagination {
        display: flex;
        justify-content: center;
        margin-top: 24px;
        @include smartphone-vertical {
            margin-top: 20px;
        }
    }

    &__empty {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        padding-top: 28px;
        padding-bottom: 40px;
        flex-grow: 1;
        visibility: hidden;
        opacity: 0;
        transition: visibility 0.2s ease, opacity 0.2s ease;

        &--show {
            visibility: visible;
            opacity: 1;
        }

        &-content {
            text-align: center;

            .reservation-list__empty-icon {
                color: rgb(var(--v-theme-text-darken-1));
            }

            h2 {
                font-size: 21px;
                @include tablet-vertical {
                    font-size: 19px !important;
                }
                @include smartphone-horizontal {
                    font-size: 19px !important;
                }
                @include smartphone-horizontal-short {
                    font-size: 19px !important;
                }
                @include smartphone-vertical {
                    font-size: 19px !important;
                    text-align: center;
                }
            }

            .reservation-list__empty-submessage {
                margin-top: 8px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 15px;
                @include tablet-vertical {
                    font-size: 13px !important;
                    text-align: center;
                }
                @include smartphone-horizontal {
                    font-size: 13px !important;
                    text-align: center;
                }
                @include smartphone-vertical {
                    font-size: 13px !important;
                    text-align: center;
                    margin-top: 7px !important;
                    line-height: 1.65;
                }
            }
        }
    }
}

</style>