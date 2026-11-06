<template>
    <transition name="capture-selection-bar-slide">
        <div v-if="selection.isSelecting.value" class="capture-selection-bar">
            <div v-ripple class="capture-selection-bar__button" v-ftooltip.top="'選択を解除'" @click="selection.clear()">
                <Icon icon="fluent:dismiss-24-regular" width="22px" />
            </div>
            <span class="capture-selection-bar__count">{{ selection.count.value.toLocaleString() }}枚を選択中</span>
            <v-spacer></v-spacer>
            <div v-ripple class="capture-selection-bar__button" v-ftooltip.top="allFavorite ? 'お気に入りから外す' : 'お気に入りに追加'"
                @click="toggleFavorite">
                <Icon :icon="allFavorite ? 'fluent:heart-24-filled' : 'fluent:heart-24-regular'" width="22px"
                    :class="{'text-primary': allFavorite}" />
            </div>
            <div v-ripple class="capture-selection-bar__button" v-ftooltip.top="'タグを付ける'" @click="openTagDialog">
                <Icon icon="fluent:tag-24-regular" width="22px" />
            </div>
            <div v-ripple class="capture-selection-bar__button" v-ftooltip.top="'ダウンロード'" @click="downloadSelected">
                <Icon icon="fluent:arrow-download-24-regular" width="22px" />
            </div>
            <!-- 削除は右端に置き、誤って押したときは確認のダイアログでキャンセルできるようにする -->
            <div v-ripple class="capture-selection-bar__button capture-selection-bar__button--danger" v-ftooltip.top="'キャプチャを削除'"
                @click="requestDelete">
                <Icon icon="fluent:delete-24-regular" width="22px" />
            </div>
        </div>
    </transition>
    <CaptureTagDialog v-model:show="isTagDialogOpen" :captures="selectedList" @updated="onTagsUpdated" />
    <!-- キーボードだけでも続けて削除できるよう、確認のダイアログを開いたら削除のボタンにフォーカスを当て、Enter キーで確定できるようにする -->
    <!-- Tab キーでキャンセルのボタンへ移ってから Enter キーを押すと、キャンセルになる -->
    <v-dialog max-width="520" :model-value="isDeleteConfirmOpen" @update:model-value="isDeleteConfirmOpen = $event"
        @after-enter="deleteButtonRef?.$el.focus()">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">
                {{ selection.count.value.toLocaleString() }}枚のキャプチャを削除しますか？
            </v-card-title>
            <v-card-text class="pt-2 pb-0">
                <div class="text-error-lighten-1 font-weight-bold">
                    保存先にある画像ファイルも削除され、元に戻すことはできません。<br>
                    同じ画像が他のフォルダにもある場合は、それらも一緒に削除されます。
                </div>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer></v-spacer>
                <v-btn color="text" variant="text" height="40" @click="isDeleteConfirmOpen = false">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn ref="deleteButtonRef" color="error" variant="flat" height="40" class="px-3" :loading="isDeleting" @click="deleteSelected">
                    <Icon icon="fluent:delete-16-regular" width="18px" height="18px" />
                    <span class="ml-1">キャプチャを削除</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { ComponentPublicInstance, computed, ref } from 'vue';

import { CaptureSelection } from '@/components/Captures/CaptureSelection';
import CaptureTagDialog from '@/components/Captures/CaptureTagDialog.vue';
import Message from '@/message';
import Captures, { ICapture } from '@/services/Captures';
import useUserStore from '@/stores/UserStore';


const props = defineProps<{
    selection: CaptureSelection;
}>();

const emit = defineEmits<{
    (event: 'updated', captures: ICapture[]): void;
    (event: 'deleted', capture_ids: number[]): void;
}>();

const userStore = useUserStore();
const isAdmin = computed(() => userStore.user?.is_admin === true);
const isTagDialogOpen = ref(false);
const isDeleteConfirmOpen = ref(false);
const isDeleting = ref(false);
// 確認のダイアログの削除のボタン (開いたときにフォーカスを当てるため)
const deleteButtonRef = ref<ComponentPublicInstance | null>(null);

const selectedList = computed(() => [...props.selection.selected.value.values()]);
const allFavorite = computed(() => selectedList.value.length > 0 && selectedList.value.every(capture => capture.is_favorite === true));

const requireLogin = () => {
    if (!userStore.is_logged_in) {
        Message.warning('お気に入りとタグを使うには、KonomiTV アカウントにログインしてください。');
        return false;
    }
    return true;
};

// 選んだものがすべてお気に入りに追加済みなら外し、それ以外ならすべてお気に入りに追加する
const toggleFavorite = async () => {
    if (!requireLogin()) {
        return;
    }
    // 応答を待つ間に選択が変わっても、送ったキャプチャにだけ結果を反映する
    const targets = selectedList.value;
    const next = !allFavorite.value;
    const ids = targets.map(capture => capture.id);
    if (await Captures.updateFavorites(ids, next)) {
        const updated = targets.map(capture => ({ ...capture, is_favorite: next }));
        // 選択に持っている内容は、まだ選ばれているキャプチャの分だけ新しい状態に差し替える
        props.selection.setMany(updated.filter(capture => props.selection.isSelected(capture)), true);
        emit('updated', updated);
        Message.success(next ? `${ids.length}枚のキャプチャをお気に入りに追加しました。` : `${ids.length}枚のキャプチャをお気に入りから外しました。`);
    }
};

const openTagDialog = () => {
    if (requireLogin()) {
        isTagDialogOpen.value = true;
    }
};
const onTagsUpdated = (captures: ICapture[]) => {
    // 応答を待つ間に選択が変わっても、選択から外したキャプチャを選び直さないよう、まだ選ばれているキャプチャの分だけ差し替える
    props.selection.setMany(captures.filter(capture => props.selection.isSelected(capture)), true);
    emit('updated', captures);
};

// 選んだキャプチャを、ブラウザのダウンロードフォルダへ1枚ずつ保存する
// 1枚ずつ保存させるため、数百枚をまとめて選んだままダウンロードするとブラウザが固まるので、一度に保存できる枚数を制限する
const MAX_DOWNLOAD_COUNT = 50;
let isDownloading = false;
const downloadSelected = async () => {
    if (selectedList.value.length === 0 || isDownloading) {
        return;
    }
    if (selectedList.value.length > MAX_DOWNLOAD_COUNT) {
        Message.warning(`一度にダウンロードできるのは${MAX_DOWNLOAD_COUNT}枚までです。\n選択を${MAX_DOWNLOAD_COUNT}枚以下にしてからダウンロードしてください。`);
        return;
    }
    isDownloading = true;
    try {
        await Captures.downloadImages(selectedList.value);
    } finally {
        isDownloading = false;
    }
};

// 削除は管理者だけができるが、ボタンは誰にでも表示し、管理者でなければ押したときにログインし直す必要があることを伝える
const requestDelete = () => {
    if (selectedList.value.length === 0) {
        return;
    }
    if (!isAdmin.value) {
        Message.warning('キャプチャを削除するには管理者権限が必要です。\n管理者アカウントでログインし直してください。');
        return;
    }
    isDeleteConfirmOpen.value = true;
};

const deleteSelected = async () => {
    // 削除の途中で Enter キーが続けて押されたときは、最初の削除だけを送る
    if (isDeleting.value) {
        return;
    }
    isDeleting.value = true;
    const ids = selectedList.value.map(capture => capture.id);
    const result = await Captures.deleteCaptures(ids);
    isDeleting.value = false;
    isDeleteConfirmOpen.value = false;
    if (result === null) {
        return;
    }
    if (result.failed_capture_ids.length > 0) {
        Message.error(`${result.failed_capture_ids.length}枚のキャプチャを削除できませんでした。もう一度お試しください。`);
    } else {
        Message.success(`${result.deleted_capture_ids.length}枚のキャプチャを削除しました。`);
    }
    // 削除できたキャプチャだけを選択から外し、削除できなかったキャプチャは選んだまま残して、もう一度押せるようにする
    const deletedIds = new Set(result.deleted_capture_ids);
    props.selection.setMany(selectedList.value.filter(capture => deletedIds.has(capture.id)), false);
    emit('deleted', result.deleted_capture_ids);
};

// キーボードの F キー・T キー・Delete キーからも、ボタンを押したときと同じ操作ができるようにする
defineExpose({ toggleFavorite, openTagDialog, downloadSelected, requestDelete });

</script>
<style lang="scss" scoped>

.capture-selection-bar {
    position: fixed;
    left: 50%;
    bottom: 24px;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 2px;
    width: min(560px, calc(100vw - 24px));
    height: 56px;
    padding: 0 8px;
    border-radius: 28px;
    transform: translateX(-50%);
    background: rgb(var(--v-theme-background-lighten-2));
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.5);
    @include smartphone-vertical {
        bottom: calc(env(safe-area-inset-bottom) + 64px);
    }

    &__count {
        margin-left: 6px;
        font-size: 15px;
        font-weight: 700;
        white-space: nowrap;
    }
    &__button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        cursor: pointer;
        &:hover {
            background: rgba(var(--v-theme-text), 0.08);
        }
        // 取り消せない削除は、ほかの操作と見分けられるよう赤で表示する
        &--danger {
            color: rgb(var(--v-theme-error-lighten-1));
        }
    }
}

.capture-selection-bar-slide-enter-active, .capture-selection-bar-slide-leave-active {
    transition: opacity 0.18s ease, transform 0.18s ease;
}
.capture-selection-bar-slide-enter-from, .capture-selection-bar-slide-leave-to {
    opacity: 0;
    transform: translate(-50%, 16px);
}

</style>
