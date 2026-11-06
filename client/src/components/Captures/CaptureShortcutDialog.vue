<template>
    <!-- 見出し・閉じるボタン・キーの表示は、視聴画面のキーボードショートカットの一覧 (KeyboardShortcutList.vue) と同じ作りにする -->
    <v-dialog max-width="600" transition="slide-y-transition" :model-value="show" @update:model-value="emit('update:show', $event)">
        <v-card>
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="fluent:keyboard-20-filled" height="28px" />
                <span class="ml-3">キーボードショートカット</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="emit('update:show', false)">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <div class="mt-3" v-for="group in shortcutGroups" :key="group.name">
                    <div class="text-subtitle-1 d-flex align-center font-weight-bold">
                        <Icon :icon="group.icon" height="22px" />
                        <span class="ml-2">{{ group.name }}</span>
                    </div>
                    <div class="mt-3" v-for="shortcut in group.shortcuts" :key="shortcut.name">
                        <div class="text-subtitle-2 mt-2 d-flex align-center font-weight-medium">
                            <span class="mr-2">{{ shortcut.name }}</span>
                            <div class="ml-auto d-flex align-center flex-shrink-0">
                                <template v-for="(keys, alternativeIndex) in shortcut.alternatives" :key="alternativeIndex">
                                    <span v-if="alternativeIndex > 0" class="shortcut-key-or">/</span>
                                    <div class="d-flex align-center" v-for="(key, index) in keys" :key="key.name">
                                        <span class="shortcut-key">
                                            <Icon v-if="key.icon" :icon="key.name" height="18px" />
                                            <span v-else>{{ key.name }}</span>
                                        </span>
                                        <span class="shortcut-key-plus" v-if="index < keys.length - 1">+</span>
                                    </div>
                                </template>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed, onBeforeUnmount, onMounted } from 'vue';

import Utils from '@/utils';


/** ショートカットのキー (icon が true なら name はアイコンの名前) */
interface IShortcutKey {
    name: string;
    icon: boolean;
}

/** ショートカット (同じ操作に割り当てたキーの組み合わせが複数ある場合は、alternatives に並べる) */
interface IShortcut {
    name: string;
    alternatives: IShortcutKey[][];
}

const props = withDefaults(defineProps<{
    show: boolean;
    // Ctrl (Command) + A キーで選ぶ範囲 (タイムラインでは同じ日付のキャプチャ、番組別の一覧ではその番組のキャプチャすべて)
    selectAllScope?: 'Day' | 'Program';
}>(), {
    selectAllScope: 'Day',
});

const emit = defineEmits<{
    (event: 'update:show', show: boolean): void;
}>();

// キャプチャの一覧のどの画面でも、視聴画面と同じく ／(？) キーで一覧を開く
const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== '/' && event.key !== '?') {
        return;
    }
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
    }
    if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
    }
    event.preventDefault();
    emit('update:show', true);
};
onMounted(() => window.addEventListener('keydown', onKeyDown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown));

const ARROW_KEYS: IShortcutKey = {name: 'fluent:arrow-move-20-regular', icon: true};
const LEFT_KEY: IShortcutKey = {name: 'fluent:arrow-left-12-filled', icon: true};
const RIGHT_KEY: IShortcutKey = {name: 'fluent:arrow-right-12-filled', icon: true};
// Mac のキーボードには Delete キーがないため、Finder と同じく Command+Backspace でも削除できる
const DELETE_KEYS: IShortcutKey[][] = [[{name: 'Delete', icon: false}], [{name: 'Cmd', icon: false}, {name: 'Backspace', icon: false}]];

const shortcutGroups = computed<{ name: string; icon: string; shortcuts: IShortcut[] }[]>(() => [
    {
        name: 'キャプチャを選択しているとき',
        icon: 'fluent:checkmark-circle-20-filled',
        shortcuts: [
            { name: '選択を移動する', alternatives: [[ARROW_KEYS]] },
            { name: '選択する範囲を広げる', alternatives: [[{name: 'Shift', icon: false}, ARROW_KEYS]] },
            { name: '選択を変更せずにカーソルを移動する', alternatives: [[{name: 'Ctrl', icon: false}, ARROW_KEYS]] },
            { name: 'カーソルの位置のキャプチャを選択する / 外す', alternatives: [[{name: 'Ctrl', icon: false}, {name: 'Space', icon: false}]] },
            { name: '選択しているキャプチャを拡大表示する', alternatives: [[{name: 'Space', icon: false}], [{name: 'Enter', icon: false}]] },
            {
                name: props.selectAllScope === 'Program' ? 'この番組のキャプチャをすべて選択する' : '同じ日付のキャプチャをすべて選択する',
                alternatives: [[{name: Utils.CtrlOrCmd(), icon: false}, {name: 'A', icon: false}]],
            },
            { name: '選択しているキャプチャをお気に入りに追加する / 外す', alternatives: [[{name: 'F', icon: false}]] },
            { name: '選択しているキャプチャにタグを付ける', alternatives: [[{name: 'T', icon: false}]] },
            { name: '選択しているキャプチャをダウンロードする (50枚まで)', alternatives: [[{name: 'D', icon: false}]] },
            { name: '選択しているキャプチャを削除する', alternatives: DELETE_KEYS },
            { name: '選択を解除する', alternatives: [[{name: 'Esc', icon: false}]] },
        ],
    },
    {
        name: 'キャプチャを拡大表示しているとき',
        icon: 'fluent:image-20-filled',
        shortcuts: [
            { name: '前のキャプチャを表示する', alternatives: [[LEFT_KEY]] },
            { name: '次のキャプチャを表示する', alternatives: [[RIGHT_KEY]] },
            { name: 'お気に入りに追加する / 外す', alternatives: [[{name: 'F', icon: false}]] },
            { name: 'タグを付ける', alternatives: [[{name: 'T', icon: false}]] },
            { name: 'ダウンロードする', alternatives: [[{name: 'D', icon: false}]] },
            { name: '情報の表示を切り替える', alternatives: [[{name: 'I', icon: false}]] },
            { name: 'キャプチャを削除する', alternatives: DELETE_KEYS },
            { name: '拡大表示を閉じる', alternatives: [[{name: 'Space', icon: false}], [{name: 'Esc', icon: false}]] },
        ],
    },
    {
        name: '全般',
        icon: 'fluent:home-20-filled',
        shortcuts: [
            { name: 'キーボードショートカットの一覧を表示する', alternatives: [[{name: '／(？)', icon: false}]] },
        ],
    },
]);

</script>
<style lang="scss" scoped>

// キーの表示は、視聴画面のキーボードショートカットの一覧 (KeyboardShortcutList.vue) と同じ見た目にする
.shortcut-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    min-width: 32px;
    min-height: 28px;
    padding: 3px 8px;
    border-radius: 5px;
    background-color: rgb(var(--v-theme-background-lighten-2));
    font-size: 14.5px;
    text-align: center;
}

.shortcut-key-plus {
    display: inline-block;
    margin: 0px 5px;
    flex-shrink: 0;
}

// 同じ操作に割り当てた別のキーの組み合わせとの区切り
.shortcut-key-or {
    display: inline-block;
    margin: 0px 8px;
    flex-shrink: 0;
    color: rgb(var(--v-theme-text-darken-1));
}

</style>
