<template>
    <!-- 並べ替えと絞り込みは、一覧の見え方を変える操作としてまとめ、1つのボタンから開く -->
    <v-menu location="bottom end" :close-on-content-click="false" @update:model-value="onFilterMenuToggle">
        <template #activator="{ props: menuProps }">
            <v-btn class="capture-filter-menu__button" variant="flat" color="background-lighten-1" height="34"
                :class="{'capture-filter-menu__button--active': activeFilterCount > 0}" v-bind="menuProps">
                <Icon icon="fluent:filter-20-regular" width="18px" height="18px" />
                <span class="capture-filter-menu__button-text">並べ替えと絞り込み</span>
                <span v-if="activeFilterCount > 0" class="capture-filter-menu__button-count">{{ activeFilterCount }}</span>
            </v-btn>
        </template>
        <v-card class="capture-filter-menu" color="background-lighten-1">
            <div class="capture-filter-menu__row">
                <span class="capture-filter-menu__label">{{ sortLabel }}</span>
                <div class="capture-filter-menu__choices">
                    <div v-for="choice in sortChoices" :key="choice.value" v-ripple
                        class="capture-filter-menu__choice"
                        :class="{'capture-filter-menu__choice--active': sort === choice.value}"
                        @click="$emit('update:sort', choice.value)">
                        {{ choice.label }}
                    </div>
                </div>
            </div>
            <div class="capture-filter-menu__divider"></div>
            <!-- タグ・お気に入りはアカウントごとのものなので、ログインしていないときは選ぼうとした時点でログインを案内する -->
            <div class="capture-filter-menu__row">
                <span class="capture-filter-menu__label">タグ (すべて付いているもの)</span>
                <v-autocomplete :model-value="filter.tag_ids ?? []" :items="tagChoices" item-title="name" item-value="id"
                    color="primary" variant="outlined" density="compact" multiple chips closable-chips hide-details
                    placeholder="タグを選択" :no-data-text="tags === null ? 'タグの一覧を読み込めませんでした' : 'タグがありません'" :readonly="!isLoggedIn"
                    @click="warnIfLoggedOut" @update:model-value="updateFilterValue('tag_ids', $event)" />
            </div>
            <div v-if="!lockFavorite" class="capture-filter-menu__row">
                <span class="capture-filter-menu__label">お気に入り</span>
                <div class="capture-filter-menu__choices">
                    <div v-for="choice in favoriteChoices" :key="String(choice.value)" v-ripple
                        class="capture-filter-menu__choice"
                        :class="{'capture-filter-menu__choice--active': (filter.is_favorite ?? null) === choice.value}"
                        @click="updateFavorite(choice.value)">
                        {{ choice.label }}
                    </div>
                </div>
            </div>
            <!-- 1つの放送回のキャプチャだけを並べる画面では、チャンネルと期間が決まっているので、その行を出さない -->
            <template v-if="!isSingleProgram">
                <div class="capture-filter-menu__row">
                    <span class="capture-filter-menu__label">チャンネル</span>
                    <v-autocomplete :model-value="filter.channel_ids ?? []" :items="channelChoices" item-title="label" item-value="id"
                        color="primary" variant="outlined" density="compact" multiple chips closable-chips hide-details
                        placeholder="チャンネルを選択" :no-data-text="channels === null ? 'チャンネルの一覧を読み込めませんでした' : 'チャンネルがありません'"
                        @update:model-value="updateFilterValue('channel_ids', $event)" />
                </div>
                <div class="capture-filter-menu__row">
                    <span class="capture-filter-menu__label">期間 ({{ periodLabel }})</span>
                    <div class="capture-filter-menu__period">
                        <v-text-field :model-value="filter.start_date ?? ''" type="date" color="primary" variant="outlined"
                            density="compact" hide-details :max="filter.end_date ?? undefined"
                            @update:model-value="updateFilterValue('start_date', $event || null)" />
                        <span>〜</span>
                        <v-text-field :model-value="filter.end_date ?? ''" type="date" color="primary" variant="outlined"
                            density="compact" hide-details :min="filter.start_date ?? undefined"
                            @update:model-value="updateFilterValue('end_date', $event || null)" />
                    </div>
                </div>
            </template>
            <div class="capture-filter-menu__divider"></div>
            <div v-for="option in filterOptions" :key="option.key" class="capture-filter-menu__row">
                <span class="capture-filter-menu__label">{{ option.label }}</span>
                <div class="capture-filter-menu__choices">
                    <div v-for="choice in option.choices" :key="String(choice.value)" v-ripple
                        class="capture-filter-menu__choice"
                        :class="{'capture-filter-menu__choice--active': filter[option.key] === choice.value}"
                        @click="updateFilter(option.key, choice.value)">
                        {{ choice.label }}
                    </div>
                </div>
            </div>
            <div class="capture-filter-menu__footer">
                <v-btn variant="text" color="text" height="36" :disabled="activeFilterCount === 0" @click="clearFilters">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                    <span class="ml-1">絞り込みをすべて解除</span>
                </v-btn>
            </div>
        </v-card>
    </v-menu>
</template>
<script lang="ts" setup>

import { computed, onMounted, ref, watch } from 'vue';

import Message from '@/message';
import Captures, { ICaptureChannel, ICaptureFilter, ICaptureTag } from '@/services/Captures';
import useUserStore from '@/stores/UserStore';
import { dayjs } from '@/utils';


/** 絞り込みのうち、ヘッダーで切り替えるもの (キャプチャの種類と番組情報の有無) */
export type CaptureTypeFilterKey = 'is_caption_composited' | 'is_comment_composited' | 'has_caption_text' | 'has_metadata';

/** 使っている絞り込みの条件のチップ (呼び出し元の画面が、一覧の上に並べて表示する) */
export interface ICaptureFilterChip {
    key: string;
    label: string;
    clear: () => void;
}

const props = withDefaults(defineProps<{
    // 並べ替えの選択肢は画面ごとに異なるので、行の見出しと選択肢を呼び出し元から受け取る
    sortLabel: string;
    sortChoices: { label: string; value: string }[];
    sort: string;
    filter: ICaptureFilter;
    // 期間の行の見出しに添える、期間を比べる日時の種類 (撮影日・放送日)
    periodLabel?: string;
    // お気に入りの画面では、お気に入りであることが画面の前提なので、お気に入りの絞り込みを出さない
    lockFavorite?: boolean;
    // タグの画面では、そのタグが画面の前提なので、重ねて選ぶタグの選択肢から外す
    excludedTagId?: number | null;
    // 1つの放送回のキャプチャだけを並べる画面 (番組の画面) では、チャンネルと期間の絞り込みを出さない
    isSingleProgram?: boolean;
}>(), {
    periodLabel: '撮影日',
    lockFavorite: false,
    excludedTagId: null,
    isSingleProgram: false,
});

const emit = defineEmits<{
    (event: 'update:sort', sort: string): void;
    (event: 'update:filter', filter: ICaptureFilter): void;
}>();

// キャプチャの種類の絞り込み (どれも「指定なし」「あり」「なし」の3択)
const filterOptions: { key: CaptureTypeFilterKey; label: string; choices: { label: string; value: boolean | null }[] }[] = [
    { key: 'is_caption_composited', label: '字幕の合成', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
    { key: 'is_comment_composited', label: 'コメントの合成', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
    { key: 'has_caption_text', label: '字幕テキスト', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
    { key: 'has_metadata', label: '番組情報', choices: [{ label: 'すべて', value: null }, { label: 'あり', value: true }, { label: 'なし', value: false }] },
];
const updateFilter = (key: CaptureTypeFilterKey, value: boolean | null) => {
    emit('update:filter', { ...props.filter, [key]: value });
};
const updateFilterValue = <K extends 'tag_ids' | 'channel_ids' | 'start_date' | 'end_date'>(key: K, value: ICaptureFilter[K]) => {
    emit('update:filter', { ...props.filter, [key]: value });
};

// お気に入りの絞り込み (お気に入りに追加したものだけに絞るか、絞らないかの2択)
const favoriteChoices: { label: string; value: boolean | null }[] = [
    { label: 'すべて', value: null },
    { label: 'お気に入りのみ', value: true },
];
const userStore = useUserStore();
const isLoggedIn = computed(() => userStore.is_logged_in);
const warnIfLoggedOut = () => {
    if (isLoggedIn.value === false) {
        Message.warning('お気に入りやタグで絞り込むには、ログインが必要です。\nアカウントにログインしてから、もう一度お試しください。');
    }
};
const updateFavorite = (value: boolean | null) => {
    if (value === true && isLoggedIn.value === false) {
        warnIfLoggedOut();
        return;
    }
    emit('update:filter', { ...props.filter, is_favorite: value });
};

// タグとチャンネルの選択肢 (チップに出す名前にも使う)
const tags = ref<ICaptureTag[] | null>(null);
const channels = ref<ICaptureChannel[] | null>(null);
const tagChoices = computed(() => (tags.value ?? []).filter(tag => tag.id !== props.excludedTagId));
// NHK BS のサブチャンネルのように同じ名前のチャンネルが複数あるときは、「NHK BS (Ch: 102)」のようにチャンネル番号を添えて見分けられるようにする
const channelChoices = computed(() => {
    const list = channels.value ?? [];
    return list.map((channel) => {
        const isDuplicated = list.some(other => other.id !== channel.id && other.name === channel.name);
        const number = Number(channel.display_channel_id.replace(/^[a-z]+/, ''));
        return { id: channel.id, label: isDuplicated ? `${channel.name} (Ch: ${number})` : channel.name };
    });
});
// 選択肢の取得に失敗していたら、絞り込みのメニューを開いたときに取得し直す
// タグはログインしていないと取得できないので、ログインしているときだけ取得し直す
// チャンネルの行を出さない画面では、チャンネルの一覧を使わないので取得しない
const onFilterMenuToggle = (isOpen: boolean) => {
    const isChannelsMissing = props.isSingleProgram === false && channels.value === null;
    if (isOpen && (isChannelsMissing || (isLoggedIn.value && tags.value === null))) {
        void loadFilterChoices();
    }
};

// 親の画面がログイン状態を確認し終えたら、アカウントごとのタグの選択肢を取得し直す
watch(isLoggedIn, () => {
    void loadFilterChoices();
});
const loadFilterChoices = async () => {
    const [tagResult, channelResult] = await Promise.all([
        isLoggedIn.value ? Captures.fetchTags() : Promise.resolve(null),
        props.isSingleProgram ? Promise.resolve(null) : Captures.fetchChannels(),
    ]);
    tags.value = tagResult;
    channels.value = channelResult;
};

// 使っている絞り込みの条件のチップ (並びは絞り込みのメニューの並びに合わせる)
const formatDate = (value: string) => dayjs(value).format('YYYY/MM/DD');
const activeFilterChips = computed(() => {
    const chips: ICaptureFilterChip[] = [];
    for (const tagId of props.filter.tag_ids ?? []) {
        const name = tags.value?.find(tag => tag.id === tagId)?.name ?? 'タグ';
        chips.push({
            key: `tag-${tagId}`,
            label: `タグ: ${name}`,
            clear: () => updateFilterValue('tag_ids', (props.filter.tag_ids ?? []).filter(id => id !== tagId)),
        });
    }
    if (props.lockFavorite === false && props.filter.is_favorite === true) {
        chips.push({ key: 'favorite', label: 'お気に入りのみ', clear: () => updateFavorite(null) });
    }
    for (const channelId of props.filter.channel_ids ?? []) {
        const name = channelChoices.value.find(channel => channel.id === channelId)?.label ?? channelId;
        chips.push({
            key: `channel-${channelId}`,
            label: `チャンネル: ${name}`,
            clear: () => updateFilterValue('channel_ids', (props.filter.channel_ids ?? []).filter(id => id !== channelId)),
        });
    }
    if (props.filter.start_date || props.filter.end_date) {
        const start = props.filter.start_date ? formatDate(props.filter.start_date) : '';
        const end = props.filter.end_date ? formatDate(props.filter.end_date) : '';
        chips.push({
            key: 'period',
            label: `期間: ${start} 〜 ${end}`,
            clear: () => emit('update:filter', { ...props.filter, start_date: null, end_date: null }),
        });
    }
    for (const option of filterOptions) {
        const value = props.filter[option.key];
        if (value === null || value === undefined) {
            continue;
        }
        const choice = option.choices.find(item => item.value === value);
        chips.push({ key: option.key, label: `${option.label}: ${choice?.label ?? ''}`, clear: () => updateFilter(option.key, null) });
    }
    return chips;
});
const activeFilterCount = computed(() => activeFilterChips.value.length);

const clearFilters = () => {
    const next: ICaptureFilter = { ...props.filter, tag_ids: [], channel_ids: [], start_date: null, end_date: null };
    if (props.lockFavorite === false) {
        next.is_favorite = null;
    }
    for (const option of filterOptions) {
        next[option.key] = null;
    }
    emit('update:filter', next);
};

// 絞り込みの選択肢と、URL から復元した条件のチップに出す名前を取得する
onMounted(() => {
    void loadFilterChoices();
});

// チップは一覧の上 (ボタンから離れた位置) に並べるので、呼び出し元の画面に渡して表示させる
defineExpose({ activeFilterChips });

</script>
<style lang="scss" scoped>

// 並べ替えと絞り込みのボタン (スマホの縦画面ではアイコンだけにする)
// 高さと文字の大きさは、録画番組の一覧の並べ替えの選択欄 (RecordedProgramList.vue) にそろえる
.capture-filter-menu__button {
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

.capture-filter-menu {
    width: 340px;
    max-width: calc(100vw - 24px);
    // 絞り込みの項目が画面の高さに収まらないときは、メニューの中をスクロールさせる
    max-height: calc(100vh - 120px);
    overflow-y: auto;
    padding: 14px 16px 8px;
    &__row {
        margin-bottom: 12px;
    }
    &__label {
        display: block;
        margin-bottom: 6px;
        font-size: 13px;
        color: rgb(var(--v-theme-text-darken-1));
    }
    &__choices {
        display: flex;
        gap: 6px;
    }
    &__choice {
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
    // 期間の開始日と終了日は、間に「〜」を挟んで横に並べる
    &__period {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
    }
    &__divider {
        height: 1px;
        margin: 4px 0 14px;
        background: rgb(var(--v-theme-background-lighten-2));
    }
    &__footer {
        display: flex;
        justify-content: flex-end;
    }
}

</style>
