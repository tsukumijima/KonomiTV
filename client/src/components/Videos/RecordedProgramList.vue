<template>
    <div class="recorded-program-list">
        <div class="recorded-program-list__header" v-if="!hideHeader">
            <h2 class="recorded-program-list__title">{{title}}</h2>
            <div class="recorded-program-list__actions">
                <v-select v-if="!hideSort"
                    v-model="sort_order"
                    :items="[
                        { title: '新しい順', value: 'desc' },
                        { title: '古い順', value: 'asc' },
                    ]"
                    item-title="title"
                    item-value="value"
                    density="compact"
                    hide-details
                    class="recorded-program-list__sort"
                    @update:model-value="$emit('update:sortOrder', $event)">
                </v-select>
                <v-btn v-if="showMoreButton"
                    variant="text"
                    class="recorded-program-list__more"
                    @click="$emit('more')">
                    もっと見る
                    <Icon icon="fluent:chevron-right-20-regular" width="20px" class="ml-1" />
                </v-btn>
            </div>
        </div>
        <div class="recorded-program-list__grid">
            <RecordedProgram v-for="program in programs" :key="program.id" :program="program" />
        </div>
        <div class="recorded-program-list__pagination" v-if="!hidePagination && total > 0">
            <v-pagination
                v-model="current_page"
                :length="Math.ceil(total / 30)"
                :total-visible="7"
                density="comfortable"
                @update:model-value="$emit('update:page', $event)">
            </v-pagination>
        </div>
        <div class="recorded-program-list__empty" v-if="total === 0">
            <div class="recorded-program-list__empty-content">
                <h2>{{emptyMessage}}</h2>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { ref } from 'vue';

import RecordedProgram from '@/components/Videos/RecordedProgram.vue';
import { IRecordedProgram } from '@/services/Videos';

// Props
const props = withDefaults(defineProps<{
    title: string;
    programs: IRecordedProgram[];
    total: number;
    page?: number;
    sortOrder?: 'desc' | 'asc';
    hideHeader?: boolean;
    hideSort?: boolean;
    hidePagination?: boolean;
    showMoreButton?: boolean;
    emptyMessage?: string;
}>(), {
    page: 1,
    sortOrder: 'desc',
    hideHeader: false,
    hideSort: false,
    hidePagination: false,
    showMoreButton: false,
    emptyMessage: '録画番組が見つかりませんでした。',
});

// Emits
defineEmits<{
    (e: 'update:page', page: number): void;
    (e: 'update:sortOrder', order: 'desc' | 'asc'): void;
    (e: 'more'): void;
}>();

// 現在のページ番号
const current_page = ref(props.page);

// 並び順
const sort_order = ref(props.sortOrder);

</script>
<style lang="scss" scoped>

.recorded-program-list {
    display: flex;
    flex-direction: column;
    width: 100%;

    &__header {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        @include smartphone-vertical {
            margin-bottom: 12px;
        }
    }

    &__title {
        font-size: 20px;
        font-weight: 700;
        @include smartphone-vertical {
            font-size: 18px;
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
    }

    &__sort {
        width: 120px;
        @include smartphone-vertical {
            width: 110px;
        }

        :deep(.v-field__input) {
            font-size: 14px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            min-height: unset !important;
        }
    }

    &__more {
        margin-left: 12px;
        font-size: 14px;
        letter-spacing: 0.05em;
        @include smartphone-vertical {
            margin-left: 8px;
            font-size: 13px;
        }
    }

    &__grid {
        display: flex;
        flex-direction: column;
        width: 100%;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 4px;
        overflow: hidden;

        :deep(.recorded-program) {
            // 最後の項目以外の下にボーダーを追加
            &:not(:last-child) {
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
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;

        &-content {
            text-align: center;
            h2 {
                font-size: 20px;
                @include smartphone-vertical {
                    font-size: 18px;
                }
            }
        }
    }
}

</style>