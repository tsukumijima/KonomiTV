<template>
    <!-- 見出し・余白・閉じるボタンは、設定画面の一覧を扱うダイアログ (CommentMuteSettings.vue など) と同じ作りにする -->
    <v-dialog max-width="520" transition="slide-y-transition" :model-value="show" @update:model-value="$emit('update:show', $event)">
        <v-card class="capture-tag-dialog">
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="fluent:tag-20-filled" height="26px" />
                <span class="ml-3">タグを付ける</span>
                <span class="capture-tag-dialog__target">{{ captures.length.toLocaleString() }}枚</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="$emit('update:show', false)">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="capture-tag-dialog__body px-5 pb-6">
                <!-- 付けられるタグの一覧 (押すたびに付け外しする) -->
                <div class="capture-tag-dialog__list">
                    <div v-if="isLoading" class="capture-tag-dialog__empty">タグを読み込んでいます...</div>
                    <div v-else-if="isLoadFailed" class="capture-tag-dialog__empty">
                        タグの一覧を読み込めませんでした。<br>KonomiTV サーバーが起動しているか確認してから、もう一度お試しください。
                    </div>
                    <div v-else-if="tags.length === 0" class="capture-tag-dialog__empty">
                        タグはまだありません。<br>下の入力欄から、新しいタグを追加できます。
                    </div>
                    <div v-for="tag in tags" :key="tag.id" v-ripple class="capture-tag-dialog__item" @click="toggleTag(tag)">
                        <Icon class="capture-tag-dialog__item-check"
                            :icon="stateOf(tag) === 'All' ? 'fluent:checkbox-checked-24-filled' : stateOf(tag) === 'Some' ? 'fluent:checkbox-indeterminate-24-filled' : 'fluent:checkbox-unchecked-24-regular'"
                            :class="{'capture-tag-dialog__item-check--on': stateOf(tag) !== 'None'}"
                            width="22px" height="22px" />
                        <span class="capture-tag-dialog__item-name">{{ tag.name }}</span>
                        <span class="capture-tag-dialog__item-count">{{ tag.capture_count.toLocaleString() }}枚</span>
                    </div>
                </div>

                <!-- 新しいタグを追加する (追加したタグは、開いているキャプチャにそのまま付く) -->
                <div class="capture-tag-dialog__create">
                    <v-text-field v-model="newTagName" class="capture-tag-dialog__create-field"
                        color="primary" variant="outlined" density="compact" hide-details
                        placeholder="新しいタグの名前" maxlength="100" @keydown.enter.prevent="createTag" />
                    <v-btn class="capture-tag-dialog__create-button px-3" color="secondary" variant="flat" height="40"
                        :disabled="newTagName.trim() === '' || isBusy" @click="createTag">
                        <Icon icon="fluent:add-12-filled" width="18px" height="18px" />
                        <span class="ml-1">追加</span>
                    </v-btn>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { ref, watch } from 'vue';

import Captures, { ICapture, ICaptureTag } from '@/services/Captures';


const props = defineProps<{
    show: boolean;
    captures: ICapture[];
}>();

const emit = defineEmits<{
    (event: 'update:show', value: boolean): void;
    (event: 'updated', captures: ICapture[]): void;
}>();

const tags = ref<ICaptureTag[]>([]);
const isLoading = ref(false);
// タグの一覧を読み込めなかったか (0件と区別して、読み込めなかったことを伝えるため)
const isLoadFailed = ref(false);
const isBusy = ref(false);
const newTagName = ref('');

// 選んだキャプチャそれぞれの、今付いているタグ (付け外しのたびにここを書き換えて、親にも知らせる)
const workingCaptures = ref<ICapture[]>([]);

watch(() => props.show, async (show) => {
    if (!show) {
        return;
    }
    workingCaptures.value = props.captures.map(capture => ({ ...capture, tag_ids: [...(capture.tag_ids ?? [])] }));
    newTagName.value = '';
    isLoading.value = true;
    const result = await Captures.fetchTags();
    isLoadFailed.value = result === null;
    tags.value = result ?? [];
    isLoading.value = false;
});

// 選んだキャプチャのうち、そのタグが付いている数で、全部・一部・なしを返す
const stateOf = (tag: ICaptureTag): 'All' | 'Some' | 'None' => {
    const tagged = workingCaptures.value.filter(capture => capture.tag_ids?.includes(tag.id)).length;
    if (tagged === 0) {
        return 'None';
    }
    return tagged === workingCaptures.value.length ? 'All' : 'Some';
};

// 全部に付いていれば外し、それ以外 (一部・なし) なら全部に付ける
// 応答を待つ間にダイアログを閉じて別のキャプチャで開き直しても、押したときのキャプチャに結果を反映する
const toggleTag = async (tag: ICaptureTag, targets: ICapture[] = workingCaptures.value) => {
    if (isBusy.value) {
        return;
    }
    const isTagged = targets.filter(capture => capture.tag_ids?.includes(tag.id)).length !== targets.length;
    const ids = targets.map(capture => capture.id);
    isBusy.value = true;
    const success = await Captures.updateTagItems(tag.id, ids, isTagged);
    isBusy.value = false;
    if (!success) {
        return;
    }
    const before = targets.filter(capture => capture.tag_ids?.includes(tag.id)).length;
    const updated = targets.map(capture => {
        const tagIds = new Set(capture.tag_ids ?? []);
        if (isTagged) {
            tagIds.add(tag.id);
        } else {
            tagIds.delete(tag.id);
        }
        return { ...capture, tag_ids: [...tagIds] };
    });
    // 開いたままなら、ダイアログの状態と一覧に出す枚数を手元で合わせる (付けた・外した枚数だけ増減する)
    if (workingCaptures.value === targets) {
        workingCaptures.value = updated;
        const after = isTagged ? updated.length : 0;
        tag.capture_count = Math.max(0, tag.capture_count + after - before);
    }
    emit('updated', updated);
};

// 新しいタグを作り、開いているキャプチャにそのまま付ける
const createTag = async () => {
    const name = newTagName.value.trim();
    if (name === '' || isBusy.value) {
        return;
    }
    const targets = workingCaptures.value;
    isBusy.value = true;
    const tag = await Captures.createTag(name);
    isBusy.value = false;
    if (tag === null) {
        return;
    }
    tags.value = [...tags.value, tag].sort((a, b) => a.name.localeCompare(b.name, 'ja'));
    newTagName.value = '';
    await toggleTag(tags.value.find(item => item.id === tag.id)!, targets);
};

</script>
<style lang="scss" scoped>

.capture-tag-dialog {
    // スマホの縦画面では、設定画面のダイアログと同じく左右の余白を詰める
    .v-card-title, &__body {
        @include smartphone-vertical {
            padding-left: 12px !important;
            padding-right: 12px !important;
        }
    }
    .v-card-title span {
        font-size: 20px;
        @include smartphone-vertical {
            font-size: 19px;
        }
    }
    &__target {
        margin-left: 10px;
        font-size: 14px !important;
        font-weight: 500;
        color: rgb(var(--v-theme-text-darken-1));
    }

    // 一覧の行の区切りと余白は、コメントのミュート設定の一覧に合わせる
    &__list {
        max-height: min(380px, 50vh);
        margin-top: 4px;
        overflow-y: auto;
    }
    &__empty {
        padding: 24px 0px;
        text-align: center;
        font-size: 13.5px;
        line-height: 1.8;
        color: rgb(var(--v-theme-text-darken-1));
    }
    &__item {
        display: flex;
        align-items: center;
        gap: 12px;
        min-height: 48px;
        padding: 6px 8px;
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
        cursor: pointer;
        user-select: none;
        transition: background-color 0.15s ease;
        &:last-of-type {
            border-bottom: none;
        }
        &:hover {
            background: rgb(var(--v-theme-background-lighten-1));
        }
        @media (hover: none) {
            &:hover {
                background: transparent;
            }
        }
        &-check {
            flex-shrink: 0;
            color: rgb(var(--v-theme-text-darken-1));
            &--on {
                color: rgb(var(--v-theme-secondary));
            }
        }
        &-name {
            flex: 1;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 15px;
        }
        &-count {
            flex-shrink: 0;
            font-size: 13px;
            color: rgb(var(--v-theme-text-darken-1));
        }
    }

    &__create {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 16px;
        &-field {
            flex: 1;
            min-width: 0;
            font-size: 14px;
        }
        &-button {
            flex-shrink: 0;
        }
    }
}

</style>
