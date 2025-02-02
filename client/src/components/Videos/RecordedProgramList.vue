<template>
    <div class="recorded-program-list">
        <div class="recorded-program-list__header" v-if="!hideHeader">
            <h2 class="recorded-program-list__title">
                {{title}}
                <div class="recorded-program-list__title-count" v-if="!showMoreButton">{{total}}件</div>
                <v-btn v-if="showMoreButton && Utils.isSmartphoneVertical()"
                    variant="text"
                    class="px-2"
                    style="min-width: 24px; border-radius: 50%;"
                    @click="$emit('more')">
                    <Icon icon="fluent:chevron-right-12-regular" width="24px" class="text-text-darken-1" style="margin: 0px 0px;" />
                </v-btn>
            </h2>
            <div class="recorded-program-list__actions">
                <v-select v-if="!hideSort"
                    v-model="sort_order"
                    :items="[
                        { title: '新しい順', value: 'desc' },
                        { title: '古い順', value: 'asc' },
                    ]"
                    item-title="title"
                    item-value="value"
                    class="recorded-program-list__sort"
                    color="primary"
                    bg-color="background-lighten-1"
                    variant="solo"
                    density="comfortable"
                    hide-details
                    @update:model-value="$emit('update:sortOrder', $event)">
                </v-select>
                <v-btn v-if="showMoreButton && !Utils.isSmartphoneVertical()"
                    variant="text"
                    class="recorded-program-list__more"
                    @click="$emit('more')">
                    <span class="text-primary">もっと見る</span>
                    <Icon icon="fluent:chevron-right-12-regular" width="18px" class="ml-1 text-text-darken-1" style="margin: 0px -4px;" />
                </v-btn>
            </div>
        </div>
        <div class="recorded-program-list__grid">
            <RecordedProgram v-for="program in programs" :key="program.id" :program="program" />
        </div>
        <div class="recorded-program-list__pagination" v-if="!hidePagination && total > 0">
            <v-pagination
                v-model="current_page"
                active-color="primary"
                density="comfortable"
                :length="Math.ceil(total / 30)"
                :total-visible="7"
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
import Utils from '@/utils';

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
        @include smartphone-vertical {
            padding: 0px 8px;
        }
    }

    &__title {
        display: flex;
        align-items: end;
        font-size: 24px;
        font-weight: 700;
        margin-top: 8px;
        margin-bottom: 20px;

        &-count {
            margin-left: 10px;
            margin-bottom: 4px;
            font-size: 14px;
            font-weight: 400;
            color: rgb(var(--v-theme-text-darken-1));
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
        @include smartphone-vertical {
            :deep(.v-field) {
                padding-right: 4px !important;
            }
            :deep(.v-field__input) {
                padding-left: 12px !important;
                padding-right: 0px !important;
            }
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
        margin-left: 8px;
        margin-bottom: 8px;
        padding: 0px 12px;
        font-size: 15px;
        letter-spacing: 0.05em;
    }

    &__grid {
        display: flex;
        flex-direction: column;
        width: 100%;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
        overflow: hidden;

        :deep(.recorded-program) {
            // 最後の項目以外の下にボーダーを追加
            &:not(:last-child) > .recorded-program__container {
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