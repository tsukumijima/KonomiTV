<template>
    <CapturePage :crumbs="[
        { name: 'ホーム', path: '/' },
        { name: 'キャプチャ', path: '/captures/' },
        { name: 'タグ別', path: '/captures/tags/', disabled: true },
    ]">
        <CaptureHeader title="タグ別" :total="null" active-tab="Tags" />

        <div v-if="!isLoggedIn && !isLoading" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:person-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">タグを使うには、ログインが必要です。</div>
            <div class="capture-empty__sub">お気に入りやタグは、アカウントごとに分けて保存されます。</div>
            <v-btn class="mt-6 px-4" color="secondary" variant="flat" height="40" to="/login/">
                <Icon icon="fa:sign-in" class="mr-2" />ログイン
            </v-btn>
        </div>
        <template v-else-if="isLoggedIn">
            <div class="capture-tags__create">
                <v-text-field v-model="newTagName" color="primary" bg-color="background-lighten-1" variant="solo" density="comfortable"
                    hide-details flat placeholder="新しいタグの名前 (例: 作品名、キャラクター名、名シーン)" maxlength="100"
                    @keydown.enter.prevent="createTag" />
                <v-btn color="primary" variant="flat" height="48" class="capture-tags__create-button"
                    :disabled="newTagName.trim() === ''" @click="createTag">
                    <Icon icon="fluent:add-12-filled" width="18px" />
                    <span class="ml-1">タグを作成</span>
                </v-btn>
            </div>

            <div v-if="isLoadFailed" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">タグの一覧を読み込めませんでした。</div>
                <div class="capture-empty__sub">KonomiTV サーバーが起動しているか確認してから、ページを再読み込みしてください。</div>
            </div>
            <div v-else-if="!isLoading && tags.length === 0" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:tag-multiple-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">タグはまだありません。</div>
                <div class="capture-empty__sub">キャプチャの詳細や上の入力欄から、タグを作成して付与できます。<br>1枚のキャプチャに複数のタグを付与することもできます。</div>
            </div>
            <div class="capture-tags__list">
                <router-link v-for="tag in tags" :key="tag.id" v-ripple class="capture-tag-card" :to="`/captures/tags/${tag.id}`">
                    <Icon class="capture-tag-card__icon" icon="fluent:tag-20-filled" width="22px" />
                    <div class="capture-tag-card__body">
                        <div class="capture-tag-card__name">{{ tag.name }}</div>
                        <div class="capture-tag-card__count">{{ tag.capture_count.toLocaleString() }}枚</div>
                    </div>
                    <v-menu location="bottom end">
                        <template #activator="{ props: menuProps }">
                            <div v-ripple class="capture-tag-card__menu" v-bind="menuProps" @click.prevent.stop>
                                <Icon icon="fluent:more-vertical-20-filled" width="20px" />
                            </div>
                        </template>
                        <v-list density="compact" bg-color="background-lighten-1">
                            <v-list-item @click="startRename(tag)">
                                <template #prepend><Icon icon="fluent:rename-20-regular" width="20px" /></template>
                                <v-list-item-title class="ml-3">名前を変更</v-list-item-title>
                            </v-list-item>
                            <v-divider></v-divider>
                            <v-list-item class="text-error" @click="deletingTag = tag">
                                <template #prepend><Icon icon="fluent:delete-20-regular" width="20px" /></template>
                                <v-list-item-title class="ml-3">タグを削除</v-list-item-title>
                            </v-list-item>
                        </v-list>
                    </v-menu>
                </router-link>
            </div>
        </template>

        <!-- 見出し・余白・ボタンの並びは、ほかの画面の入力欄のあるダイアログ (Twitter.vue のアカウント連携など) と同じ作りにする -->
        <v-dialog max-width="480" :model-value="renamingTag !== null" @update:model-value="renamingTag = null">
            <v-card>
                <v-card-title class="d-flex justify-center pt-6 font-weight-bold">タグの名前を変更</v-card-title>
                <v-card-text class="pt-2 pb-0">
                    <v-text-field v-model="renameInput" class="mt-4" color="primary" variant="outlined" hide-details
                        label="タグの名前" maxlength="100" autofocus @keydown.enter.prevent="renameTag" />
                </v-card-text>
                <v-card-actions class="pt-6 px-6 pb-6">
                    <v-spacer></v-spacer>
                    <v-btn color="text" variant="text" height="40" @click="renamingTag = null">
                        <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                        <span class="ml-1">キャンセル</span>
                    </v-btn>
                    <v-btn color="secondary" variant="flat" height="40" class="px-3" :disabled="renameInput.trim() === ''" @click="renameTag">
                        <Icon icon="fluent:rename-16-regular" width="18px" height="18px" />
                        <span class="ml-1">名前を変更</span>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
        <v-dialog max-width="480" :model-value="deletingTag !== null" @update:model-value="deletingTag = null">
            <v-card>
                <v-card-title class="d-flex justify-center pt-6 font-weight-bold">タグ「{{ deletingTag?.name }}」を削除しますか？</v-card-title>
                <v-card-text class="pt-2 pb-0">
                    このタグは、付与されているすべてのキャプチャから解除されます。<br>
                    キャプチャ画像自体は削除されません。
                </v-card-text>
                <v-card-actions class="pt-4 px-6 pb-6">
                    <v-spacer></v-spacer>
                    <v-btn color="text" variant="text" height="40" @click="deletingTag = null">
                        <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                        <span class="ml-1">キャンセル</span>
                    </v-btn>
                    <v-btn color="error" variant="flat" height="40" class="px-3" @click="deleteTag">
                        <Icon icon="fluent:delete-16-regular" width="18px" height="18px" />
                        <span class="ml-1">タグを削除</span>
                    </v-btn>
                </v-card-actions>
            </v-card>
        </v-dialog>
    </CapturePage>
</template>
<script lang="ts" setup>

import { onMounted, ref } from 'vue';

import CaptureHeader from '@/components/Captures/CaptureHeader.vue';
import CapturePage from '@/components/Captures/CapturePage.vue';
import Message from '@/message';
import Captures, { ICaptureTag } from '@/services/Captures';
import useUserStore from '@/stores/UserStore';


const userStore = useUserStore();
const tags = ref<ICaptureTag[]>([]);
const isLoading = ref(true);
// 読み込みに失敗したか (0件と区別して、読み込めなかったことを伝えるため)
const isLoadFailed = ref(false);
const isLoggedIn = ref(false);
const newTagName = ref('');
const renamingTag = ref<ICaptureTag | null>(null);
const renameInput = ref('');
const deletingTag = ref<ICaptureTag | null>(null);

const load = async () => {
    const result = await Captures.fetchTags();
    isLoadFailed.value = result === null;
    tags.value = result ?? [];
};

const createTag = async () => {
    const name = newTagName.value.trim();
    if (name === '') {
        return;
    }
    const tag = await Captures.createTag(name);
    if (tag !== null) {
        newTagName.value = '';
        Message.success(`タグ「${tag.name}」を作成しました。`);
        await load();
    }
};

const startRename = (tag: ICaptureTag) => {
    renamingTag.value = tag;
    renameInput.value = tag.name;
};
const renameTag = async () => {
    if (renamingTag.value === null || renameInput.value.trim() === '') {
        return;
    }
    // 名前を変えられなかったとき (同じ名前のタグがあるときなど) は、入力した名前を直せるよう、ダイアログを開いたままにする
    const target = renamingTag.value;
    const tag = await Captures.renameTag(target.id, renameInput.value.trim());
    if (tag === null) {
        return;
    }
    if (renamingTag.value?.id === target.id) {
        renamingTag.value = null;
    }
    await load();
};
const deleteTag = async () => {
    if (deletingTag.value === null) {
        return;
    }
    const name = deletingTag.value.name;
    const success = await Captures.deleteTag(deletingTag.value.id);
    deletingTag.value = null;
    if (success) {
        Message.success(`タグ「${name}」を削除しました。`);
        await load();
    }
};

onMounted(async () => {
    await userStore.fetchUser();
    isLoggedIn.value = userStore.is_logged_in;
    if (isLoggedIn.value) {
        await load();
    }
    isLoading.value = false;
});

</script>
<style lang="scss" scoped>

.capture-tags {
    &__create {
        display: flex;
        gap: 10px;
        max-width: 640px;
        margin-bottom: 20px;
        &-button {
            border-radius: 7px;
            letter-spacing: 0;
        }
    }
    &__list {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 12px;
        @include smartphone-vertical {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
        }
    }
}

.capture-tag-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 8px 14px 16px;
    border-radius: 10px;
    background: rgb(var(--v-theme-background-lighten-1));
    color: rgb(var(--v-theme-text));
    text-decoration: none;
    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }
    &__icon {
        flex-shrink: 0;
        color: rgb(var(--v-theme-primary));
    }
    &__body {
        flex: 1;
        min-width: 0;
    }
    &__name {
        font-size: 15px;
        font-weight: 700;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    &__count {
        margin-top: 2px;
        font-size: 12.5px;
        color: rgb(var(--v-theme-text-darken-1));
    }
    &__menu {
        display: flex;
        flex-shrink: 0;
        padding: 6px;
        border-radius: 50%;
    }
}

</style>
