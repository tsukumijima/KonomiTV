<template>
    <div class="capture-header">
        <!-- スマホの縦画面の検索欄 (ほかのタブの上部の検索欄と同じ見た目で、見出しの行と入れ替えて出す) -->
        <div v-if="isSearchOpen" class="capture-header__search">
            <div class="capture-header__search-icon">
                <Icon icon="fluent:search-20-filled" height="20px" />
            </div>
            <input ref="searchInputRef" v-model="searchText" type="search" name="capture-search" enterkeyhint="search"
                placeholder="キャプチャを検索..." @keydown.enter.prevent="submitSearch" @keydown.esc="closeSearch">
            <div v-ripple class="capture-header__search-close" @click="closeSearch">
                <Icon icon="fluent:dismiss-20-filled" height="24px" />
            </div>
        </div>
        <div v-else class="capture-header__top">
            <!-- 1段入った画面 (タグごとのキャプチャなど) では、番組の画面と同じ戻るボタンを置く -->
            <div v-if="showBackButton" v-ripple class="capture-header__back" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </div>
            <h2 class="capture-header__title">
                <span class="capture-header__title-text">{{ title }}</span>
                <!-- 読み込み中は、録画番組の検索結果と同じく、枚数の代わりに読み込み中であることを出す -->
                <span v-if="loadingLabel !== null" class="capture-header__title-count capture-header__title-count--loading">
                    <Icon icon="line-md:loading-twotone-loop" width="18px" height="18px" />
                    <span>{{ loadingLabel }}</span>
                </span>
                <span v-else-if="total !== null" class="capture-header__title-count">{{ total.toLocaleString() }}枚</span>
            </h2>
            <div v-if="scanStatus !== null && scanStatus.is_running" class="capture-header__scan"
                v-ftooltip.bottom="'保存先フォルダのキャプチャをスキャンしています。解析が完了した画像から順次表示されます。'">
                <Icon icon="line-md:loading-twotone-loop" width="16px" />
                <span v-if="scanStatus.total_count === 0">保存先フォルダを確認しています...</span>
                <span v-else>キャプチャをスキャンしています... ({{ scanStatus.processed_count.toLocaleString() }} / {{ scanStatus.total_count.toLocaleString() }} 枚)</span>
            </div>
            <v-spacer></v-spacer>
            <!-- スマホの縦画面では、上部のヘッダーを隠しているので、ここに検索の入口を置く -->
            <div v-ripple class="capture-header__search-button" @click="openSearch">
                <Icon icon="fluent:search-20-filled" height="24px" />
            </div>
            <!-- 並べ替えと絞り込みは、一覧の見え方を変える操作としてまとめ、1つのボタンから開く -->
            <v-menu v-if="showTimelineControls" location="bottom end" :close-on-content-click="false">
                <template #activator="{ props: menuProps }">
                    <v-btn class="capture-header__view-button" variant="flat" color="background-lighten-1" height="34"
                        :class="{'capture-header__view-button--active': activeFilterCount > 0}" v-bind="menuProps">
                        <Icon icon="fluent:filter-20-regular" width="18px" height="18px" />
                        <span class="capture-header__view-button-text">並べ替えと絞り込み</span>
                        <span v-if="activeFilterCount > 0" class="capture-header__view-button-count">{{ activeFilterCount }}</span>
                    </v-btn>
                </template>
                <v-card class="capture-header__filter" color="background-lighten-1">
                    <div class="capture-header__filter-row">
                        <span class="capture-header__filter-label">並べ替えの基準</span>
                        <div class="capture-header__filter-choices">
                            <div v-for="choice in axisChoices" :key="choice.value" v-ripple
                                class="capture-header__filter-choice"
                                :class="{'capture-header__filter-choice--active': axis === choice.value}"
                                @click="$emit('update:axis', choice.value)">
                                {{ choice.label }}
                            </div>
                        </div>
                    </div>
                    <div class="capture-header__filter-divider"></div>
                    <div v-for="option in filterOptions" :key="option.key" class="capture-header__filter-row">
                        <span class="capture-header__filter-label">{{ option.label }}</span>
                        <div class="capture-header__filter-choices">
                            <div v-for="choice in option.choices" :key="String(choice.value)" v-ripple
                                class="capture-header__filter-choice"
                                :class="{'capture-header__filter-choice--active': filter[option.key] === choice.value}"
                                @click="updateFilter(option.key, choice.value)">
                                {{ choice.label }}
                            </div>
                        </div>
                    </div>
                    <div class="capture-header__filter-footer">
                        <v-btn variant="text" color="text" height="36" :disabled="activeFilterCount === 0" @click="clearFilters">
                            <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                            <span class="ml-1">絞り込みをすべて解除</span>
                        </v-btn>
                    </div>
                </v-card>
            </v-menu>
            <v-menu location="bottom end" :close-on-content-click="true">
                <template #activator="{ props: menuProps }">
                    <div v-ripple class="capture-header__menu" v-bind="menuProps">
                        <Icon icon="fluent:more-vertical-20-filled" width="22px" />
                    </div>
                </template>
                <v-list density="compact" bg-color="background-lighten-1" class="capture-header__menu-list">
                    <v-list-item @click="fileInputRef?.click()">
                        <template #prepend>
                            <Icon icon="fluent:arrow-upload-20-regular" width="20px" />
                        </template>
                        <v-list-item-title class="ml-3">画像をアップロード</v-list-item-title>
                    </v-list-item>
                </v-list>
            </v-menu>
            <input ref="fileInputRef" type="file" accept="image/jpeg,image/png" multiple hidden @change="onFilesSelected">
        </div>

        <!-- 検索結果では、別の画面へ移るタブの代わりに、検索語を探す範囲の絞り込みを出す -->
        <!-- 何も選ばなければすべての範囲から探し、選んだ範囲のどれかに含まれるキャプチャに絞り込む -->
        <div v-if="showQueryTargets" class="capture-header__targets">
            <div v-for="choice in queryTargetChoices" :key="choice.value" v-ripple class="capture-header__target"
                :class="{'capture-header__target--active': queryTargets.includes(choice.value)}"
                @click="toggleQueryTarget(choice.value)">
                <Icon :icon="queryTargets.includes(choice.value) ? 'fluent:checkmark-16-filled' : choice.icon" width="18px" />
                <span>{{ choice.label }}</span>
            </div>
        </div>
        <!-- タイムライン・番組別・タグ別・お気に入りの画面を切り替えるタブ -->
        <div v-else class="capture-header__tabs">
            <router-link v-for="tab in tabs" :key="tab.value" v-ripple class="capture-header__tab"
                :class="{'capture-header__tab--active': tab.value === activeTab}" :to="tab.to">
                <Icon :icon="tab.icon" width="18px" />
                <span>{{ tab.label }}</span>
            </router-link>
        </div>

        <!-- 画像のファイルを画面に持ってきている間に出す、ドロップしてアップロードするための枠 -->
        <Teleport to="body">
            <transition name="capture-drop-fade">
                <div v-if="isDraggingFiles" class="capture-drop-overlay">
                    <div class="capture-drop-overlay__frame">
                        <Icon icon="fluent:arrow-upload-24-regular" width="56px" height="56px" />
                        <div class="capture-drop-overlay__message">ドロップして画像をアップロード</div>
                        <div class="capture-drop-overlay__sub">JPEG・PNG の画像を、複数まとめてアップロードできます。</div>
                    </div>
                </div>
            </transition>
        </Teleport>
    </div>
</template>
<script lang="ts" setup>

import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import Message from '@/message';
import Captures, { CaptureQueryTarget, CaptureTimelineAxis, ICapture, ICaptureFilter } from '@/services/Captures';
import Maintenance, { IMaintenanceTaskStatus } from '@/services/Maintenance';


/** 絞り込みのうち、ヘッダーで切り替えるもの (キャプチャの種類と番組情報の有無) */
export type CaptureTypeFilterKey = 'is_caption_composited' | 'is_comment_composited' | 'has_caption_text' | 'has_metadata';

const props = withDefaults(defineProps<{
    title: string;
    total?: number | null;
    loadingLabel?: string | null;
    activeTab: 'Timeline' | 'Programs' | 'Favorites' | 'Tags' | null;
    showTimelineControls?: boolean;
    showBackButton?: boolean;
    showQueryTargets?: boolean;
    axis?: CaptureTimelineAxis;
    filter?: ICaptureFilter;
    queryTargets?: CaptureQueryTarget[];
}>(), {
    total: null,
    loadingLabel: null,
    showTimelineControls: false,
    showBackButton: false,
    showQueryTargets: false,
    axis: 'CapturedAt',
    filter: () => ({}),
    queryTargets: () => [],
});

const emit = defineEmits<{
    (event: 'update:axis', axis: CaptureTimelineAxis): void;
    (event: 'update:filter', filter: ICaptureFilter): void;
    (event: 'update:queryTargets', queryTargets: CaptureQueryTarget[]): void;
    (event: 'uploaded', captures: ICapture[]): void;
    (event: 'scanned'): void;
}>();

// 番組別とタグ別はどちらもキャプチャをまとめたアルバムの一覧なので、隣に並べる
const tabs = [
    { value: 'Timeline', label: 'タイムライン', icon: 'fluent:image-multiple-20-regular', to: '/captures/' },
    { value: 'Programs', label: '番組別', icon: 'fluent:video-clip-multiple-20-regular', to: '/captures/programs/' },
    { value: 'Tags', label: 'タグ別', icon: 'fluent:tag-multiple-20-regular', to: '/captures/tags/' },
    { value: 'Favorites', label: 'お気に入り', icon: 'fluent:heart-20-regular', to: '/captures/favorites/' },
];

// スマホの縦画面の検索欄 (検索結果の画面では、今の検索語を入れた状態で開く)
const route = useRoute();
const router = useRouter();
const isSearchOpen = ref(false);
const searchText = ref('');
const searchInputRef = ref<HTMLInputElement | null>(null);
const openSearch = async () => {
    searchText.value = typeof route.query.query === 'string' ? route.query.query : '';
    isSearchOpen.value = true;
    await nextTick();
    searchInputRef.value?.focus();
};
const closeSearch = () => {
    isSearchOpen.value = false;
};
const submitSearch = () => {
    const query = searchText.value.trim();
    if (query === '') {
        return;
    }
    isSearchOpen.value = false;
    void router.push({ path: '/captures/search', query: { query } });
};

// 検索語を探す範囲 (何も選ばないときは、字幕・番組名・番組概要に加えて、チャンネル名とファイル名からも探す)
const queryTargetChoices: { label: string; value: CaptureQueryTarget; icon: string }[] = [
    { label: '字幕テキスト', value: 'CaptionText', icon: 'fluent:closed-caption-20-regular' },
    { label: '番組名', value: 'ProgramTitle', icon: 'fluent:video-clip-20-regular' },
    { label: '番組概要', value: 'ProgramDescription', icon: 'fluent:text-description-20-regular' },
];
const toggleQueryTarget = (value: CaptureQueryTarget) => {
    // 範囲は選択肢の並びの順に保ち、同じ組み合わせが同じ URL になるようにする
    const next = queryTargetChoices
        .map(choice => choice.value)
        .filter(target => target === value ? !props.queryTargets.includes(target) : props.queryTargets.includes(target));
    emit('update:queryTargets', next);
};

// 並べ替えの基準 (撮影日時か、その場面が放送された日時か)
const axisChoices: { label: string; value: CaptureTimelineAxis }[] = [
    { label: '撮影日時', value: 'CapturedAt' },
    { label: '放送日時', value: 'BroadcastAt' },
];

// キャプチャの種類の絞り込み (どれも「指定なし」「あり」「なし」の3択)
const filterOptions: { key: CaptureTypeFilterKey; label: string; choices: { label: string; value: boolean | null }[] }[] = [
    { key: 'is_caption_composited', label: '字幕の合成', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
    { key: 'is_comment_composited', label: 'コメントの合成', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
    { key: 'has_caption_text', label: '字幕テキスト', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
    { key: 'has_metadata', label: '番組情報', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
];
const activeFilterCount = computed(() => filterOptions.filter(option => props.filter[option.key] !== null && props.filter[option.key] !== undefined).length);

const updateFilter = (key: CaptureTypeFilterKey, value: boolean | null) => {
    emit('update:filter', { ...props.filter, [key]: value });
};
const clearFilters = () => {
    const next = { ...props.filter };
    for (const option of filterOptions) {
        next[option.key] = null;
    }
    emit('update:filter', next);
};

// 手元の画像のアップロード (メタデータのない画像でも、ファイルの更新日時を撮影日時として扱う)
// メニューから選んだファイルと、画面にドロップしたファイルの両方をここで送る
const uploadFiles = async (files: File[]) => {
    if (files.length === 0) {
        return;
    }
    Message.info(`${files.length}枚の画像をアップロードしています...`);
    const results = await Promise.all(files.map(file => Captures.uploadLocalFile(file)));
    const uploaded = results.filter((capture): capture is ICapture => capture !== null);
    if (uploaded.length > 0) {
        Message.success(`${uploaded.length}枚の画像をアップロードしました。`);
        emit('uploaded', uploaded);
    }
};
const fileInputRef = ref<HTMLInputElement | null>(null);
const onFilesSelected = async () => {
    const files = [...(fileInputRef.value?.files ?? [])];
    if (fileInputRef.value !== null) {
        fileInputRef.value.value = '';
    }
    await uploadFiles(files);
};

// 画面へのドラッグ＆ドロップでのアップロード
// 子の要素を出入りするたびに dragenter と dragleave が届くので、入った回数と出た回数の差で、画面の上にあるかを判断する
const isDraggingFiles = ref(false);
let dragDepth = 0;
// ページの中の画像や文字のドラッグには反応せず、ほかのアプリから持ってきたファイルのときだけ枠を出す
const hasFiles = (event: DragEvent) => event.dataTransfer?.types.includes('Files') === true;
const onDragEnter = (event: DragEvent) => {
    if (hasFiles(event) === false) {
        return;
    }
    event.preventDefault();
    dragDepth++;
    isDraggingFiles.value = true;
};
const onDragOver = (event: DragEvent) => {
    if (hasFiles(event) === false) {
        return;
    }
    // 既定の動作 (ブラウザがファイルを開く) を止めて、ドロップを受け付ける
    event.preventDefault();
    if (event.dataTransfer !== null) {
        event.dataTransfer.dropEffect = 'copy';
    }
};
const onDragLeave = (event: DragEvent) => {
    if (hasFiles(event) === false) {
        return;
    }
    dragDepth = Math.max(dragDepth - 1, 0);
    if (dragDepth === 0) {
        isDraggingFiles.value = false;
    }
};
const onDrop = async (event: DragEvent) => {
    if (hasFiles(event) === false) {
        return;
    }
    event.preventDefault();
    dragDepth = 0;
    isDraggingFiles.value = false;

    // サーバーが受け付ける JPEG と PNG の画像だけを送り、それ以外のファイルは送らずに知らせる
    const files = [...(event.dataTransfer?.files ?? [])];
    const images = files.filter(file => file.type === 'image/jpeg' || file.type === 'image/png');
    if (images.length < files.length) {
        Message.warning(`JPEG・PNG 以外の${files.length - images.length}個のファイルは、アップロードしませんでした。`);
    }
    await uploadFiles(images);
};

// 索引作りの進み具合 (走っている間だけ表示する)
const scanStatus = ref<IMaintenanceTaskStatus | null>(null);
let scanTimer: number | null = null;
const refreshScanStatus = async () => {
    const wasRunning = scanStatus.value?.is_running === true;
    scanStatus.value = await Maintenance.fetchCaptureScanStatus();
    // 走っていた索引作りが終わったら、新しく登録されたキャプチャを一覧に読み直させる
    if (wasRunning === true && scanStatus.value !== null && scanStatus.value.is_running === false) {
        emit('scanned');
    }
    // 取得に失敗したら (エラーはサービス側で表示済み)、エラーを出し続けないよう取得を止める
    if (scanStatus.value === null && scanTimer !== null) {
        window.clearInterval(scanTimer);
        scanTimer = null;
    }
};
onMounted(() => {
    void refreshScanStatus();
    scanTimer = window.setInterval(refreshScanStatus, 10 * 1000);
    // ドロップは画面のどこで受けてもよいので、ウインドウ全体で受け取る
    window.addEventListener('dragenter', onDragEnter);
    window.addEventListener('dragover', onDragOver);
    window.addEventListener('dragleave', onDragLeave);
    window.addEventListener('drop', onDrop);
});
onBeforeUnmount(() => {
    if (scanTimer !== null) {
        window.clearInterval(scanTimer);
    }
    window.removeEventListener('dragenter', onDragEnter);
    window.removeEventListener('dragover', onDragOver);
    window.removeEventListener('dragleave', onDragLeave);
    window.removeEventListener('drop', onDrop);
});

</script>
<style lang="scss" scoped>

.capture-header {
    display: flex;
    flex-direction: column;
    padding-top: 8px;
    // スマホの縦画面では、マイリストの見出し (RecordedProgramList.vue) と同じく左右に 8px を加える
    // 見出しの行は右の 40px のボタンに合わせて文字より高くなるので、上の余白を減らして文字の位置をマイリストにそろえる
    @include smartphone-vertical {
        padding-top: 4px;
        padding-left: 8px;
        padding-right: 8px;
    }

    // 見出しの行は、置かれるボタン (戻る・並べ替えと絞り込み・その他) の有無にかかわらず同じ高さにし、タブで画面を移っても位置を変えない
    &__top {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
        height: 40px;
        min-width: 0;
    }
    // 番組の画面 (Program.vue) の戻るボタンと同じ寸法
    &__back {
        display: flex;
        flex-shrink: 0;
        margin-left: -8px;
        margin-right: -2px;
        padding: 6px;
        border-radius: 50%;
        cursor: pointer;
    }
    &__title {
        display: flex;
        align-items: baseline;
        min-width: 0;
        font-size: 24px;
        font-weight: 700;
        @include smartphone-vertical {
            font-size: 22px;
        }
        // iPhone SE などの小さいスマホでは、見出しと枚数が省略されずに収まるよう文字を小さくする
        @include smartphone-vertical-short {
            font-size: 19px;
        }
        // 幅が足りないときは、まず枚数を縮めて省略し、それでも足りないとき (長いタグの名前など) だけ見出しを省略する
        &-text {
            flex-shrink: 1;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        &-count {
            flex-shrink: 100;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            margin-left: 12px;
            font-size: 14px;
            font-weight: 400;
            color: rgb(var(--v-theme-text-darken-1));
            @include smartphone-vertical-short {
                margin-left: 8px;
                font-size: 12.5px;
            }
            &--loading {
                display: flex;
                align-items: center;
                align-self: center;
                gap: 4px;
                flex-shrink: 0;
            }
        }
    }
    &__scan {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
        padding: 0 10px;
        height: 28px;
        border-radius: 14px;
        background: rgb(var(--v-theme-background-lighten-1));
        font-size: 12px;
        color: rgb(var(--v-theme-text-darken-1));
        @include smartphone-vertical {
            display: none;
        }
    }
    // 並べ替えと絞り込みのボタン (スマホの縦画面ではアイコンだけにする)
    // 検索の入口 (スマホの縦画面だけ。PC とスマホの横画面では上部のヘッダーの検索欄を使う)
    &__search-button {
        display: none;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        width: 40px;
        height: 40px;
        border-radius: 8px;
        cursor: pointer;
        @include smartphone-vertical {
            display: flex;
        }
    }
    // 検索欄 (SPHeaderBar.vue の検索欄と同じ見た目)
    // 開いたときに下の一覧が跳ねないよう、見出しの行と同じ高さにする
    &__search {
        display: flex;
        align-items: center;
        height: 40px;
        &-icon {
            display: flex;
            align-items: center;
            margin-right: 8px;
            color: rgb(var(--v-theme-text-darken-1));
        }
        input {
            flex-grow: 1;
            min-width: 0;
            height: 100%;
            border: none;
            background: transparent;
            color: rgb(var(--v-theme-text));
            font-size: 16px;
            // type="search" のデフォルトスタイルを無効化
            -webkit-appearance: none;
            appearance: none;
            &:focus {
                outline: none;
            }
            &::placeholder {
                color: rgb(var(--v-theme-text-darken-2));
            }
            // type="search" のキャンセルボタンを非表示
            &::-webkit-search-cancel-button {
                display: none;
            }
        }
        &-close {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
        }
    }

    // 高さと文字の大きさは、録画番組の一覧の並べ替えの選択欄 (RecordedProgramList.vue) にそろえる
    &__view-button {
        flex-shrink: 0;
        padding: 0 10px !important;
        border-radius: 6px;
        letter-spacing: 0;
        font-size: 14px;
        // スマホの縦画面では、検索や「その他」と同じ背景のない四角いアイコンのボタンにする
        @include smartphone-vertical {
            position: relative;
            min-width: 40px !important;
            width: 40px;
            height: 40px !important;
            :deep(svg) {
                width: 20px;
                height: 20px;
            }
            padding: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        &-text {
            margin-left: 6px;
            @include smartphone-vertical {
                display: none;
            }
        }
        &-count {
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 20px;
            height: 20px;
            margin-left: 6px;
            padding: 0 6px;
            border-radius: 10px;
            background: rgb(var(--v-theme-secondary));
            color: rgb(var(--v-theme-text));
            font-size: 12px;
            font-weight: 700;
            // スマホの縦画面では、アイコンの右上に重ねる
            @include smartphone-vertical {
                position: absolute;
                top: 2px;
                right: 0px;
                min-width: 16px;
                height: 16px;
                margin-left: 0;
                padding: 0 4px;
                font-size: 10.5px;
            }
        }
        &--active {
            color: rgb(var(--v-theme-secondary-lighten-1)) !important;
        }
    }
    &__menu {
        display: flex;
        padding: 8px;
        border-radius: 50%;
        cursor: pointer;
        color: rgb(var(--v-theme-text));
    }
    // メニューの文字と項目の高さは、録画番組のメニュー (RecordedProgram.vue) にそろえる
    &__menu-list {
        :deep(.v-list-item-title) {
            text-autospace: normal;
            font-size: 14px !important;
        }
        :deep(.v-list-item) {
            min-height: 36px !important;
        }
    }

    // 画面を切り替えるタブと、検索結果の範囲の絞り込みは、同じ高さの行にして、画面を移っても下の一覧の位置を変えない
    &__tabs, &__targets {
        display: flex;
        flex-shrink: 0;
        height: 44px;
        margin-top: 10px;
        margin-bottom: 14px;
        overflow-x: auto;
        scrollbar-width: none;
        &::-webkit-scrollbar {
            display: none;
        }
    }
    // タブ (テレビをみるのチャンネルの種類のタブと同じく、下線で今の画面を示す)
    &__tabs {
        box-shadow: inset 0 -3px 0 rgb(var(--v-theme-background-lighten-1));
    }
    &__tab {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        flex-shrink: 0;
        min-width: 110px;
        height: 100%;
        padding: 0 16px;
        border-bottom: 3px solid transparent;
        border-radius: 2.5px 2.5px 0 0;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 15px;
        text-decoration: none;
        cursor: pointer;
        user-select: none;
        transition: color 0.15s ease, border-color 0.15s ease;
        white-space: nowrap;
        // スマホの縦画面では、4つのタブが画面の幅に収まるよう、アイコンを小さくして文字の長さに応じて幅を配る
        // iPhone SE などの小さいスマホでは、アイコンを並べる幅が足りないのでアイコンを外す
        @include smartphone-vertical {
            flex: 1 1 auto;
            min-width: 0;
            gap: 4px;
            padding: 0 4px;
            font-size: 14px;
            :deep(svg) {
                width: 16px;
                height: 16px;
                flex-shrink: 0;
            }
            @include smartphone-vertical-short {
                gap: 0;
                :deep(svg) {
                    display: none;
                }
            }
        }
        &:hover {
            color: rgb(var(--v-theme-text));
        }
        &--active {
            border-bottom-color: rgb(var(--v-theme-primary));
            color: rgb(var(--v-theme-text));
            font-weight: 700;
        }
    }
    // 検索語を探す範囲 (選んだ範囲はプライマリカラーで塗り、チェックを付ける)
    &__targets {
        align-items: center;
        gap: 8px;
    }
    &__target {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-shrink: 0;
        height: 34px;
        padding: 0 14px;
        border-radius: 17px;
        background: rgb(var(--v-theme-background-lighten-1));
        color: rgb(var(--v-theme-text));
        font-size: 13.5px;
        cursor: pointer;
        user-select: none;
        // スマホの縦画面では、3つの範囲が画面の幅に収まるよう詰める
        @include smartphone-vertical {
            gap: 4px;
            padding: 0 12px;
            font-size: 13px;
        }
        &--active {
            background: rgb(var(--v-theme-primary));
            color: rgb(var(--v-theme-text));
        }
    }

    &__filter {
        width: 340px;
        max-width: calc(100vw - 24px);
        padding: 14px 16px 8px;
        &-row {
            margin-bottom: 12px;
        }
        &-label {
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            color: rgb(var(--v-theme-text-darken-1));
        }
        &-choices {
            display: flex;
            gap: 6px;
        }
        &-choice {
            flex: 1;
            padding: 6px 0;
            border-radius: 6px;
            background: rgb(var(--v-theme-background-lighten-2));
            text-align: center;
            font-size: 13px;
            cursor: pointer;
            &--active {
                background: rgb(var(--v-theme-primary));
                color: rgb(var(--v-theme-text));
            }
        }
        &-divider {
            height: 1px;
            margin: 4px 0 14px;
            background: rgb(var(--v-theme-background-lighten-2));
        }
        &-footer {
            display: flex;
            justify-content: flex-end;
        }
    }
}

// ドロップしてアップロードするための枠 (画面全体を薄く覆い、その内側に点線の角丸の枠を出す)
// 1枚表示 (2300) より前に出し、タグのダイアログなど (2400) よりは後ろにする
.capture-drop-overlay {
    position: fixed;
    inset: 0;
    z-index: 2350;
    display: flex;
    padding: 24px;
    background: rgba(var(--v-theme-background), 0.82);
    backdrop-filter: blur(4px);
    // 枠の上でもドラッグのイベントが下の画面からウインドウへ届くよう、枠自体は操作を受けない
    pointer-events: none;
    @include smartphone-vertical {
        padding: 12px;
    }
    &__frame {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        flex: 1;
        border: 3px dashed rgb(var(--v-theme-primary));
        border-radius: 20px;
        background: rgba(var(--v-theme-primary), 0.06);
        color: rgb(var(--v-theme-primary-lighten-1));
        text-align: center;
    }
    &__message {
        margin-top: 16px;
        color: rgb(var(--v-theme-text));
        font-size: 22px;
        font-weight: 700;
        @include smartphone-vertical {
            font-size: 18px;
        }
    }
    &__sub {
        margin-top: 8px;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 14px;
    }
}
.capture-drop-fade-enter-active, .capture-drop-fade-leave-active {
    transition: opacity 0.15s ease;
}
.capture-drop-fade-enter-from, .capture-drop-fade-leave-to {
    opacity: 0;
}

</style>
