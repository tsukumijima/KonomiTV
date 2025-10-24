<template>
    <v-dialog
        max-width="520"
        transition="slide-y-transition"
        :model-value="show"
        @update:model-value="emit('update:show', $event)">
        <v-card>
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="fluent:edit-20-filled" width="24px" height="24px" />
                <span class="ml-3">別タイトルを編集</span>
            </v-card-title>
            <v-card-text class="px-5 pt-2 pb-0">
                <div class="text-body-2 text-text-darken-1">
                    クリップ動画に表示する別タイトルを設定できます。空欄で保存すると別タイトルは解除されます。
                </div>
                <v-textarea
                    v-model="inputValue"
                    class="mt-4"
                    color="primary"
                    variant="outlined"
                    hide-details="auto"
                    rows="2"
                    auto-grow
                    :disabled="isSaving"
                    placeholder="例: 名シーンまとめ (後半)"
                />
            </v-card-text>
            <v-card-actions class="px-5 pt-4 pb-5">
                <v-spacer></v-spacer>
                <v-btn
                    variant="text"
                    color="text"
                    :disabled="isSaving"
                    @click="handleClear"
                >
                    クリア
                </v-btn>
                <v-btn
                    variant="text"
                    color="text"
                    :disabled="isSaving"
                    @click="emit('update:show', false)"
                >
                    キャンセル
                </v-btn>
                <v-btn
                    color="primary"
                    variant="flat"
                    :loading="isSaving"
                    :disabled="!hasChanges || isSaving"
                    @click="handleSave"
                >
                    保存
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed, ref, watch } from 'vue';

import Message from '@/message';
import ClipVideos, { IClipVideo } from '@/services/ClipVideos';

const props = defineProps<{
    clipVideo: IClipVideo;
    show: boolean;
}>();

const emit = defineEmits<{
    (e: 'update:show', value: boolean): void;
    (e: 'saved', clipVideo: IClipVideo): void;
}>();

const inputValue = ref('');
const isSaving = ref(false);

const normalize = (value: string | null | undefined): string => {
    return (value ?? '').trim();
};

const hasChanges = computed(() => {
    return normalize(inputValue.value) !== normalize(props.clipVideo.alternate_title);
});

watch(() => props.show, (show) => {
    if (show) {
        inputValue.value = props.clipVideo.alternate_title ?? '';
    }
});

watch(() => props.clipVideo.alternate_title, (value) => {
    if (!props.show) {
        inputValue.value = value ?? '';
    }
});

const handleClear = () => {
    inputValue.value = '';
};

const handleSave = async () => {
    if (isSaving.value) {
        return;
    }
    if (!hasChanges.value) {
        emit('update:show', false);
        return;
    }
    const normalized = normalize(inputValue.value);
    const payload = normalized === '' ? null : normalized;
    isSaving.value = true;
    emit('update:show', false);
    const updatedClipVideo = await ClipVideos.updateClipVideoAlternateTitle(props.clipVideo.id, payload);
    isSaving.value = false;
    if (updatedClipVideo !== null) {
        if (payload === null) {
            Message.success('別タイトルを削除しました。');
        } else {
            Message.success('別タイトルを更新しました。');
        }
        emit('saved', updatedClipVideo);
    } else {
        Message.error('別タイトルの更新に失敗しました。');
    }
};

</script>
