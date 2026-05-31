<template>
    <aside class="program-search-filters">
        <div class="program-search-filters__title">
            <span class="program-search-filters__title-label">
                <Icon icon="fluent:filter-20-filled" width="20px" height="20px" />
                検索条件
            </span>
            <button type="button" v-ripple class="program-search-filters__reset-button" @click="resetFilters">
                <Icon icon="fluent:arrow-reset-20-filled" width="14px" height="14px" />
                リセット
            </button>
        </div>
        <div class="program-search-filters__basic">
            <v-text-field
                v-model="keywordText"
                label="検索キーワード（空欄可）"
                name="program-search-keyword"
                color="primary"
                bg-color="background-lighten-1"
                variant="solo"
                density="comfortable"
                hide-details
                clearable
                @click:clear="keywordText = ''"
                @keydown.enter="handleSearchKeyDown">
                <template #append-inner>
                    <Icon class="program-search-filters__search-icon" icon="fluent:search-20-filled" width="22px" height="22px"
                        @click="emitSearch" />
                </template>
            </v-text-field>
            <v-text-field
                v-model="excludeKeywordText"
                label="除外キーワード"
                name="program-search-exclude-keyword"
                color="primary"
                bg-color="background-lighten-1"
                variant="solo"
                density="comfortable"
                hide-details
                clearable
                @click:clear="excludeKeywordText = ''"
                @keydown.enter="handleSearchKeyDown">
            </v-text-field>
            <div class="program-search-filters__toggle-grid">
                <button v-for="toggle in basicToggleOptions" :key="toggle.key"
                    type="button" v-ripple
                    class="program-search-filters__toggle-chip"
                    :class="{ 'program-search-filters__toggle-chip--active': localCondition[toggle.key] === true }"
                    :aria-pressed="localCondition[toggle.key]"
                    @click="toggleBasicCondition(toggle.key)">
                    <Icon :icon="toggle.icon" width="16px" height="16px" />
                    <span>{{ toggle.label }}</span>
                </button>
            </div>
        </div>
        <v-expansion-panels class="program-search-filters__panels" variant="accordion" multiple>
            <v-expansion-panel>
                <v-expansion-panel-title>
                    <span class="program-search-filters__panel-title-text">
                        <Icon icon="tabler:category-filled" width="16px" height="16px" />
                        ジャンル指定
                    </span>
                    <span class="program-search-filters__panel-status-badge"
                        :class="{ 'program-search-filters__panel-status-badge--modified': isGenreFilterModified }">
                        {{ genreFilterStatusLabel }}
                    </span>
                </v-expansion-panel-title>
                <v-expansion-panel-text class="program-search-filters__edge-panel">
                    <div class="program-search-filters__checkbox-list">
                        <div v-for="genre in genreOptions" :key="genre.major" class="program-search-filters__genre-group">
                            <button type="button" v-ripple
                                class="program-search-filters__check-row program-search-filters__check-row--major"
                                :class="{
                                    'program-search-filters__check-row--active': isGenreMajorSelected(genre.major),
                                    'program-search-filters__check-row--partial': isGenreMajorPartiallySelected(genre.major),
                                }"
                                :aria-pressed="isGenreMajorPartiallySelected(genre.major) ? 'mixed' : isGenreMajorFullySelected(genre.major)"
                                @click="toggleGenreAll(genre.major)">
                                <span class="program-search-filters__check-box">
                                    <Icon v-if="isGenreMajorFullySelected(genre.major)" icon="fluent:checkmark-16-filled"
                                        width="14px" height="14px" />
                                    <Icon v-else-if="isGenreMajorPartiallySelected(genre.major)" icon="fluent:subtract-16-filled"
                                        width="14px" height="14px" />
                                </span>
                                <span>{{ genre.major }} （すべて）</span>
                                <span class="program-search-filters__genre-expander"
                                    :class="{ 'program-search-filters__genre-expander--open': expandedGenreKeys.has(genre.major) }"
                                    @click.stop="toggleGenreExpanded(genre.major)">
                                    <Icon icon="fluent:chevron-down-16-filled" width="15px" height="15px" />
                                </span>
                            </button>
                            <div v-show="expandedGenreKeys.has(genre.major)" class="program-search-filters__genre-children">
                                <button v-for="middle in genre.middles" :key="middle"
                                    type="button" v-ripple
                                    class="program-search-filters__check-row program-search-filters__check-row--nested"
                                    :class="{ 'program-search-filters__check-row--active': isGenreSelected(genre.major, middle) }"
                                    :aria-pressed="isGenreSelected(genre.major, middle)"
                                    @click="toggleGenreMiddle(genre.major, middle)">
                                    <span class="program-search-filters__check-box">
                                        <Icon v-if="isGenreSelected(genre.major, middle)" icon="fluent:checkmark-16-filled"
                                            width="14px" height="14px" />
                                    </span>
                                    <span>{{ middle }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="program-search-filters__panel-section">
                        <button type="button" v-ripple
                            class="program-search-filters__inline-toggle"
                            :class="{ 'program-search-filters__inline-toggle--active': localCondition.is_exclude_genre_ranges === true }"
                            :aria-pressed="localCondition.is_exclude_genre_ranges"
                            @click="localCondition.is_exclude_genre_ranges = !localCondition.is_exclude_genre_ranges">
                            <Icon icon="fluent:subtract-circle-16-filled" width="16px" height="16px" />
                            選択したジャンルを除外
                        </button>
                    </div>
                </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel>
                <v-expansion-panel-title>
                    <span class="program-search-filters__panel-title-text">
                        <Icon icon="ic:round-cell-tower" width="16px" height="16px" />
                        検索対象チャンネル
                    </span>
                    <span class="program-search-filters__panel-status-badge"
                        :class="{
                            'program-search-filters__panel-status-badge--modified': isChannelFilterModified,
                            'program-search-filters__panel-status-badge--warning': selectedServiceKeys.size === 0,
                        }">
                        {{ channelFilterStatusLabel }}
                    </span>
                </v-expansion-panel-title>
                <v-expansion-panel-text class="program-search-filters__edge-panel">
                    <div class="program-search-filters__checkbox-list">
                        <button v-for="channel in selectableChannels" :key="channel.id"
                            type="button" v-ripple
                            class="program-search-filters__check-row"
                            :class="{ 'program-search-filters__check-row--active': selectedServiceKeys.has(getChannelServiceKey(channel)) }"
                            :aria-pressed="selectedServiceKeys.has(getChannelServiceKey(channel))"
                            @click="toggleChannel(channel)">
                            <span class="program-search-filters__check-box">
                                <Icon v-if="selectedServiceKeys.has(getChannelServiceKey(channel))" icon="fluent:checkmark-16-filled"
                                    width="14px" height="14px" />
                            </span>
                            <span class="program-search-filters__channel-logo">
                                <img :src="`${Utils.api_base_url}/channels/${channel.id}/logo`"
                                    loading="lazy"
                                    decoding="async"
                                    alt="">
                            </span>
                            <span class="program-search-filters__channel-name">
                                <span>{{ getChannelTypeLabel(channel.type) }}</span>
                                <span>Ch: {{ channel.channel_number }} {{ channel.name }}</span>
                            </span>
                        </button>
                    </div>
                    <div class="program-search-filters__quick-actions program-search-filters__panel-section">
                        <button v-for="channelType in channelTypeOptions" :key="channelType.value"
                            type="button" v-ripple
                            class="program-search-filters__mini-button"
                            @click="selectChannelType(channelType.value)">
                            {{ channelType.label }} 全選択
                        </button>
                        <button type="button" v-ripple class="program-search-filters__mini-button"
                            @click="clearChannels">
                            全解除
                        </button>
                    </div>
                </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel>
                <v-expansion-panel-title>
                    <span class="program-search-filters__panel-title-text">
                        <Icon icon="akar-icons:schedule" width="16px" height="16px" />
                        放送日時
                    </span>
                    <span class="program-search-filters__panel-status-badge"
                        :class="{ 'program-search-filters__panel-status-badge--modified': isDateFilterModified }">
                        {{ dateFilterStatusLabel }}
                    </span>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                    <div class="program-search-filters__date-range-list">
                        <div v-for="(dateRange, index) in dateRanges" :key="dateRange.id"
                            class="program-search-filters__date-range">
                            <div class="program-search-filters__date-range-header">
                                <span>条件 {{ index + 1 }}</span>
                                <div class="program-search-filters__date-range-actions">
                                    <button type="button" v-ripple class="program-search-filters__icon-button"
                                        aria-label="条件を複製"
                                        @click="copyDateRange(index)">
                                        <Icon icon="fluent:copy-16-regular" width="15px" height="15px" />
                                    </button>
                                    <button type="button" v-ripple class="program-search-filters__icon-button"
                                        aria-label="条件を削除"
                                        @click="removeDateRange(index)">
                                        <Icon icon="fluent:delete-16-filled" width="15px" height="15px" />
                                    </button>
                                </div>
                            </div>
                            <div class="program-search-filters__date-row">
                                <span class="program-search-filters__date-label">開始</span>
                                <select v-model.number="dateRange.start_day_of_week" class="program-search-filters__select"
                                    :name="`program-search-date-${dateRange.id}-start-day`">
                                    <option v-for="dayOfWeek in dayOfWeekOptions" :key="dayOfWeek.value"
                                        :value="dayOfWeek.value">
                                        {{ dayOfWeek.label }}
                                    </option>
                                </select>
                                <select v-model.number="dateRange.start_hour" class="program-search-filters__select"
                                    :name="`program-search-date-${dateRange.id}-start-hour`">
                                    <option v-for="hour in hourOptions" :key="hour" :value="hour">
                                        {{ hour.toString().padStart(2, '0') }}時
                                    </option>
                                </select>
                                <select v-model.number="dateRange.start_minute" class="program-search-filters__select"
                                    :name="`program-search-date-${dateRange.id}-start-minute`">
                                    <option v-for="minute in minuteOptions" :key="minute" :value="minute">
                                        {{ minute.toString().padStart(2, '0') }}分
                                    </option>
                                </select>
                            </div>
                            <div class="program-search-filters__date-row">
                                <span class="program-search-filters__date-label">終了</span>
                                <select v-model.number="dateRange.end_day_of_week" class="program-search-filters__select"
                                    :name="`program-search-date-${dateRange.id}-end-day`">
                                    <option v-for="dayOfWeek in dayOfWeekOptions" :key="dayOfWeek.value"
                                        :value="dayOfWeek.value">
                                        {{ dayOfWeek.label }}
                                    </option>
                                </select>
                                <select v-model.number="dateRange.end_hour" class="program-search-filters__select"
                                    :name="`program-search-date-${dateRange.id}-end-hour`">
                                    <option v-for="hour in hourOptions" :key="hour" :value="hour">
                                        {{ hour.toString().padStart(2, '0') }}時
                                    </option>
                                </select>
                                <select v-model.number="dateRange.end_minute" class="program-search-filters__select"
                                    :name="`program-search-date-${dateRange.id}-end-minute`">
                                    <option v-for="minute in minuteOptions" :key="minute" :value="minute">
                                        {{ minute.toString().padStart(2, '0') }}分
                                    </option>
                                </select>
                            </div>
                        </div>
                        <button type="button" v-ripple class="program-search-filters__mini-button program-search-filters__mini-button--wide"
                            @click="addDateRange">
                            <Icon icon="fluent:add-16-filled" width="15px" height="15px" />
                            日時条件を追加
                        </button>
                    </div>
                    <button type="button" v-ripple
                        class="program-search-filters__inline-toggle mt-3"
                        :class="{ 'program-search-filters__inline-toggle--active': localCondition.is_exclude_date_ranges === true }"
                        :aria-pressed="localCondition.is_exclude_date_ranges"
                        @click="localCondition.is_exclude_date_ranges = !localCondition.is_exclude_date_ranges">
                        <Icon icon="fluent:subtract-circle-16-filled" width="16px" height="16px" />
                        選択した日時を除外
                    </button>
                </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel>
                <v-expansion-panel-title>
                    <span class="program-search-filters__panel-title-text">
                        <Icon icon="fluent:clock-12-regular" width="16px" height="16px" />
                        番組長
                    </span>
                    <span class="program-search-filters__panel-status-badge"
                        :class="{ 'program-search-filters__panel-status-badge--modified': isDurationFilterModified }">
                        {{ durationFilterStatusLabel }}
                    </span>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                    <div class="program-search-filters__duration-grid">
                        <label class="program-search-filters__number-field">
                            <span>最小</span>
                            <input v-model="durationRangeMinText"
                                type="number"
                                name="program-search-duration-min"
                                min="0"
                                inputmode="numeric"
                                placeholder="指定なし">
                            <span>分</span>
                        </label>
                        <label class="program-search-filters__number-field">
                            <span>最大</span>
                            <input v-model="durationRangeMaxText"
                                type="number"
                                name="program-search-duration-max"
                                min="0"
                                inputmode="numeric"
                                placeholder="指定なし">
                            <span>分</span>
                        </label>
                    </div>
                </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel>
                <v-expansion-panel-title>
                    <span class="program-search-filters__panel-title-text">
                        <Icon icon="fluent:money-16-filled" width="16px" height="16px" />
                        無料放送/有料放送
                    </span>
                    <span class="program-search-filters__panel-status-badge"
                        :class="{ 'program-search-filters__panel-status-badge--modified': isBroadcastTypeFilterModified }">
                        {{ broadcastTypeFilterStatusLabel }}
                    </span>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                    <div class="program-search-filters__segmented">
                        <button v-for="broadcastType in broadcastTypeOptions" :key="broadcastType.value"
                            type="button" v-ripple
                            class="program-search-filters__segmented-button"
                            :class="{ 'program-search-filters__segmented-button--active': localCondition.broadcast_type === broadcastType.value }"
                            @click="localCondition.broadcast_type = broadcastType.value">
                            {{ broadcastType.label }}
                        </button>
                    </div>
                </v-expansion-panel-text>
            </v-expansion-panel>
        </v-expansion-panels>
        <div class="program-search-filters__actions">
            <v-btn class="program-search-filters__submit" color="secondary" variant="flat" block
                :loading="isSearching" @click="emitSearch">
                <Icon icon="fluent:search-20-filled" width="20px" height="20px" class="mr-1" />
                検索
            </v-btn>
        </div>
    </aside>
</template>
<script lang="ts" setup>

import { computed, nextTick, ref, toRaw, watch } from 'vue';

import type { ChannelType, ILiveChannel } from '@/services/Channels';
import type { IProgramSearchCondition, IProgramSearchConditionDate } from '@/services/Programs';

import Utils, { ProgramUtils } from '@/utils';

type GenreOption = {
    major: string;
    middles: string[];
};

type ChannelTypeOption = {
    label: string;
    value: ChannelType;
};

type DayOfWeekOption = {
    label: string;
    value: number;
};

type BasicToggleKey =
    'is_title_only' |
    'is_case_sensitive' |
    'is_fuzzy_search_enabled' |
    'is_regex_search_enabled';

type BasicToggleOption = {
    key: BasicToggleKey;
    label: string;
    icon: string;
};

type BroadcastTypeOption = {
    label: string;
    value: IProgramSearchCondition['broadcast_type'];
};

type DateRangeForm = IProgramSearchConditionDate & {
    id: number;
};

const props = defineProps<{
    condition: IProgramSearchCondition;
    channels: ILiveChannel[];
    isSearching: boolean;
}>();

const emit = defineEmits<{
    (e: 'update:condition', condition: IProgramSearchCondition): void;
    (e: 'search'): void;
}>();

// 入力途中の値を親に即時同期し、検索ボタン押下時には親側が最新条件を使えるようにする
const localCondition = ref<IProgramSearchCondition>(structuredClone(toRaw(props.condition)));

// チャンネル選択は API に送る3つの ID で保持し、種別別ボタンは単なる入力補助として扱う
const selectedServiceKeys = ref<Set<string>>(new Set());

// ジャンル選択は大分類すべてと中分類個別を同じ Set で扱い、同時選択の矛盾を避ける
const selectedGenreKeys = ref<Set<string>>(new Set());

// 大分類はチェック行を兼ねたアコーディオンとして扱い、長い中分類リストを必要な分だけ開く
const expandedGenreKeys = ref<Set<string>>(new Set());

// 放送日時範囲は複数件を扱うため、フォーム用 ID を付けて追加削除時の再利用を避ける
const dateRanges = ref<DateRangeForm[]>([]);

// PC 用とスマホ用の2つのフォームが同時に存在するため、親からの同期を再送信しないようにする
let isSyncingFromProps = false;

// 自分が親へ渡した条件がそのまま戻ってきた場合は、入力中のフォーム部品を再生成しない
let lastEmittedConditionJSON: string | null = null;

// 日時範囲のフォーム ID は画面内だけで一意なら十分なので、単純な連番で発行する
let dateRangeIdSequence = 1;

const allGenreMiddleLabel = 'すべて';
const genreKeySeparator = '\u0000';

const allChannelTypeOptions: ChannelTypeOption[] = [
    { label: '地デジ', value: 'GR' },
    { label: 'BS', value: 'BS' },
    { label: 'CS', value: 'CS' },
    { label: 'CATV', value: 'CATV' },
    { label: 'SKY', value: 'SKY' },
    { label: 'BS4K', value: 'BS4K' },
];

const basicToggleOptions: BasicToggleOption[] = [
    { key: 'is_title_only', label: '番組名のみ', icon: 'fluent:text-t-20-filled' },
    { key: 'is_case_sensitive', label: '大小文字区別', icon: 'fluent:text-change-case-20-filled' },
    { key: 'is_fuzzy_search_enabled', label: 'あいまい検索', icon: 'fluent:sparkle-20-filled' },
    { key: 'is_regex_search_enabled', label: '正規表現検索', icon: 'fluent:braces-20-filled' },
];

const dayOfWeekOptions: DayOfWeekOption[] = [
    { label: '日曜日', value: 0 },
    { label: '月曜日', value: 1 },
    { label: '火曜日', value: 2 },
    { label: '水曜日', value: 3 },
    { label: '木曜日', value: 4 },
    { label: '金曜日', value: 5 },
    { label: '土曜日', value: 6 },
];

const hourOptions = Array.from({ length: 24 }, (_, hour) => hour);
const minuteOptions = Array.from({ length: 60 }, (_, minute) => minute);

const broadcastTypeOptions: BroadcastTypeOption[] = [
    { label: 'すべて', value: 'All' },
    { label: '無料のみ', value: 'FreeOnly' },
    { label: '有料のみ', value: 'PaidOnly' },
];

const genreOptions = computed<GenreOption[]>(() => {
    return Object.entries(ProgramUtils.CONTENT_TYPE).map(([, contentType]) => {
        const [major, middles] = contentType as [string, Record<number, string>];
        return {
            major,
            middles: Object.values(middles),
        };
    });
});

const channelTypeOptions = computed<ChannelTypeOption[]>(() => {
    // チャンネルが存在しない種別の一括ボタンは出さず、押しても何も変わらない UI を避ける
    const availableChannelTypes = new Set(props.channels.map((channel) => channel.type));
    return allChannelTypeOptions.filter((channelType) => availableChannelTypes.has(channelType.value));
});

const selectableChannels = computed(() => {
    // EDCB の service_list にはトランスポートストリーム ID が必須なので、欠けているチャンネルは候補から外す
    return props.channels.filter((channel) => channel.transport_stream_id !== null);
});

const allSelectableServiceKeys = computed(() => {
    // 全チャンネル選択かどうかの判定を、UI に表示している候補だけで行う
    return new Set(selectableChannels.value.map((channel) => getChannelServiceKey(channel)));
});

const isGenreFilterModified = computed(() => {
    // ジャンル指定と除外指定のどちらかが初期値から変わっていれば、閉じた見出しにも印を出す
    return selectedGenreKeys.value.size > 0 || localCondition.value.is_exclude_genre_ranges === true;
});

const isChannelFilterModified = computed(() => {
    // 全チャンネル選択が初期状態なので、選択数や実際のキー集合が違う場合だけ変更扱いにする
    if (selectedServiceKeys.value.size !== allSelectableServiceKeys.value.size) {
        return true;
    }
    return [...allSelectableServiceKeys.value].some((serviceKey) => {
        return selectedServiceKeys.value.has(serviceKey) === false;
    });
});

const isDateFilterModified = computed(() => {
    // 日時範囲0件が初期状態なので、除外指定も含めて判定する
    return dateRanges.value.length > 0 || localCondition.value.is_exclude_date_ranges === true;
});

const isDurationFilterModified = computed(() => {
    // 放送時間は上下どちらかだけ指定した状態も検索条件として意味を持つ
    return localCondition.value.duration_range_min !== null || localCondition.value.duration_range_max !== null;
});

const isBroadcastTypeFilterModified = computed(() => {
    // 放送種別はすべてが初期状態なので、無料のみ・有料のみだけを変更扱いにする
    return localCondition.value.broadcast_type !== 'All';
});

const genreFilterStatusLabel = computed(() => {
    // ジャンルは未選択が指定なしなので、チェック数よりも検索条件としての意味を見出しに出す
    if (selectedGenreKeys.value.size === 0) {
        return localCondition.value.is_exclude_genre_ranges === true ? '除外オン' : '指定なし';
    }

    // 大分類すべてが選択されている場合、画面上は配下の中分類すべてが選択済みに見える
    // このため、見出しの件数は UI 上見えるチェック数に合わせ、増減が直感的に認知できるようにする
    let selectedGenreCount = 0;
    selectedGenreKeys.value.forEach((genreKey) => {
        const { major, middle } = splitGenreKey(genreKey);
        if (middle !== allGenreMiddleLabel) {
            selectedGenreCount += 1;
            return;
        }
        const genre = genreOptions.value.find((genreOption) => genreOption.major === major);
        selectedGenreCount += genre?.middles.length ?? 1;
    });

    return localCondition.value.is_exclude_genre_ranges === true
        ? `除外 ${selectedGenreCount}件`
        : `${selectedGenreCount}件選択`;
});

const channelFilterStatusLabel = computed(() => {
    // チャンネルは検索対象そのものなので、全件・0件・一部選択を明示してジャンルとの差を出す
    if (selectedServiceKeys.value.size === 0) {
        return '未選択';
    }
    if (isChannelFilterModified.value === false) {
        return 'すべて';
    }
    return `${selectedServiceKeys.value.size}件選択`;
});

const dateFilterStatusLabel = computed(() => {
    // 日時は0件が指定なしなので、除外だけが入っている状態も見落とさないよう短く示す
    if (dateRanges.value.length === 0) {
        return localCondition.value.is_exclude_date_ranges === true ? '除外オン' : '指定なし';
    }
    return localCondition.value.is_exclude_date_ranges === true
        ? `除外 ${dateRanges.value.length}件`
        : `${dateRanges.value.length}件指定`;
});

const durationFilterStatusLabel = computed(() => {
    // 片側だけの番組長指定も有効なので、上下限の入力に合わせて文言を分ける
    const min = localCondition.value.duration_range_min;
    const max = localCondition.value.duration_range_max;
    if (min === null && max === null) {
        return '指定なし';
    }
    if (min !== null && max !== null) {
        return `${min}〜${max}分`;
    }
    if (min !== null) {
        return `${min}分以上`;
    }
    return `${max}分以下`;
});

const broadcastTypeFilterStatusLabel = computed(() => {
    // 内部値ではなく、ユーザーが選んだラベルそのものを見出しに出す
    return broadcastTypeOptions.find((broadcastType) => {
        return broadcastType.value === localCondition.value.broadcast_type;
    })?.label ?? 'すべて';
});

const keywordText = computed({
    get: () => localCondition.value.keyword ?? '',
    set: (value: string | null) => {
        // Vuetify のクリア操作は null を入れるため、API に送る前にフォーム側で空文字へ戻す
        localCondition.value.keyword = value ?? '';
    },
});

const excludeKeywordText = computed({
    get: () => localCondition.value.exclude_keyword ?? '',
    set: (value: string | null) => {
        // 除外キーワードの空欄は null ではなく空文字として扱う
        localCondition.value.exclude_keyword = value ?? '';
    },
});

const durationRangeMinText = computed({
    get: () => localCondition.value.duration_range_min?.toString() ?? '',
    set: (value: string) => {
        // 空欄は最小番組長の指定なしとして API に渡す
        const parsedValue = Number(value);
        localCondition.value.duration_range_min = value === '' || Number.isFinite(parsedValue) === false
            ? null
            : Math.max(0, Math.floor(parsedValue));
    },
});

const durationRangeMaxText = computed({
    get: () => localCondition.value.duration_range_max?.toString() ?? '',
    set: (value: string) => {
        // 空欄は最大番組長の指定なしとして API に渡す
        const parsedValue = Number(value);
        localCondition.value.duration_range_max = value === '' || Number.isFinite(parsedValue) === false
            ? null
            : Math.max(0, Math.floor(parsedValue));
    },
});

const getChannelServiceKey = (channel: ILiveChannel): string => {
    // 選択状態と API 送信値の対応を崩さないため、EDCB が必要とする3つの ID をそのままキーにする
    return `${channel.network_id}:${channel.transport_stream_id ?? 0}:${channel.service_id}`;
};

const getChannelTypeLabel = (channelType: ChannelType): string => {
    // チャンネル種別は型として固定されているが、将来追加された場合でも表示が空にならないよう値を返す
    return allChannelTypeOptions.find((channelTypeOption) => {
        return channelTypeOption.value === channelType;
    })?.label ?? channelType;
};

const getGenreKey = (major: string, middle: string): string => {
    // ジャンル名自体に記号が含まれても分解できるよう、通常入力に出ない区切り文字を使う
    return `${major}${genreKeySeparator}${middle}`;
};

const splitGenreKey = (genreKey: string): { major: string; middle: string; } => {
    // 古い条件や手動編集の混入で中分類が欠けても、大分類すべてとして扱って検索条件を壊さない
    const [major, middle = allGenreMiddleLabel] = genreKey.split(genreKeySeparator);
    return { major, middle };
};

const isGenreSelected = (major: string, middle: string): boolean => {
    // 大分類すべてが選ばれている場合は、中分類も選択済みとして表示する
    return selectedGenreKeys.value.has(getGenreKey(major, allGenreMiddleLabel)) ||
        selectedGenreKeys.value.has(getGenreKey(major, middle));
};

const isGenreMajorFullySelected = (major: string): boolean => {
    // API へ送る大分類すべての指定と、親チェックボックスの見た目を同じ判定にする
    return selectedGenreKeys.value.has(getGenreKey(major, allGenreMiddleLabel));
};

const isGenreMajorPartiallySelected = (major: string): boolean => {
    // 中分類だけが選ばれている大分類は、折りたたみ時にも選択中だと分かるよう中間状態で表示する
    return selectedGenreKeys.value.has(getGenreKey(major, allGenreMiddleLabel)) === false &&
        [...selectedGenreKeys.value].some((genreKey) => {
            return splitGenreKey(genreKey).major === major;
        });
};

const isGenreMajorSelected = (major: string): boolean => {
    // 親行の色は全選択と一部選択のどちらでも付け、見出しとしての手掛かりを残す
    return isGenreMajorFullySelected(major) === true || isGenreMajorPartiallySelected(major) === true;
};

const createDateRangeForm = (dateRange?: IProgramSearchConditionDate): DateRangeForm => {
    // 追加直後から有効な範囲にしておくと、未入力の半端な条件を API に送る分岐が不要になる
    const nextDateRange = dateRange ?? {
        start_day_of_week: 0,
        start_hour: 22,
        start_minute: 0,
        end_day_of_week: 1,
        end_hour: 3,
        end_minute: 59,
    };
    return {
        id: dateRangeIdSequence++,
        ...nextDateRange,
    };
};

const stringifyCondition = (condition: IProgramSearchCondition): string => {
    // 検索条件は循環参照を持たないため、同一条件の往復判定には JSON 文字列を使える
    return JSON.stringify(toRaw(condition));
};

const syncLocalStateFromCondition = (condition: IProgramSearchCondition) => {
    const rawCondition = structuredClone(toRaw(condition));
    localCondition.value = {
        ...rawCondition,
        is_enabled: true,
        note: '',
    };

    // null は全チャンネル扱いなので、現在の KonomiTV チャンネル一覧をすべて選択済みに戻す
    if (condition.service_ranges !== null) {
        selectedServiceKeys.value = new Set(condition.service_ranges.map((service) => {
            return `${service.network_id}:${service.transport_stream_id}:${service.service_id}`;
        }));
    } else {
        selectedServiceKeys.value = new Set(allSelectableServiceKeys.value);
    }

    // 大分類すべてと中分類個別の両方を復元し、送信時も同じ粒度を保つ
    selectedGenreKeys.value = condition.genre_ranges !== null
        ? new Set(condition.genre_ranges.map((genre) => getGenreKey(genre.major, genre.middle)))
        : new Set();

    // 選択済みの大分類だけ開いておくと、復元後に何が選ばれているかをすぐ確認できる
    expandedGenreKeys.value = new Set([...selectedGenreKeys.value].map((genreKey) => splitGenreKey(genreKey).major));

    // null は日時指定なしとして扱い、UI では範囲0件に戻す
    dateRanges.value = condition.date_ranges !== null
        ? condition.date_ranges.map((dateRange) => createDateRangeForm(dateRange))
        : [];
};

const emitConditionUpdate = () => {
    const condition = buildCondition();
    lastEmittedConditionJSON = stringifyCondition(condition);
    emit('update:condition', condition);
};

watch(() => props.condition, (condition) => {
    // URL パラメータなど親側の条件が更新されたとき、フォーム側にも反映する
    const conditionJSON = stringifyCondition(condition);
    if (lastEmittedConditionJSON === conditionJSON) {
        lastEmittedConditionJSON = null;
        return;
    }
    isSyncingFromProps = true;
    syncLocalStateFromCondition(condition);
    nextTick(() => {
        isSyncingFromProps = false;
    });
}, { deep: true, immediate: true });

watch(() => props.channels, () => {
    // チャンネル一覧の取得後は、null だった全チャンネル指定を実際の候補全件へ展開する
    isSyncingFromProps = true;
    syncLocalStateFromCondition(props.condition);
    nextTick(() => {
        isSyncingFromProps = false;
    });
}, { deep: true });

watch([
    localCondition,
    selectedServiceKeys,
    selectedGenreKeys,
    dateRanges,
], () => {
    if (isSyncingFromProps === true) {
        return;
    }

    emitConditionUpdate();
}, { deep: true });

const toggleBasicCondition = (key: BasicToggleKey) => {
    // 検索方式の排他関係は API へ渡す前に UI で確定させる
    localCondition.value[key] = !localCondition.value[key];
    if (key === 'is_fuzzy_search_enabled' && localCondition.value.is_fuzzy_search_enabled === true) {
        localCondition.value.is_regex_search_enabled = false;
    }
    if (key === 'is_regex_search_enabled' && localCondition.value.is_regex_search_enabled === true) {
        localCondition.value.is_fuzzy_search_enabled = false;
    }
};

const toggleGenreAll = (major: string) => {
    // 大分類すべては同じ大分類の中分類と両立しないため、先に同じ大分類をすべて外す
    const nextGenreKeys = new Set(selectedGenreKeys.value);
    const allGenreKey = getGenreKey(major, allGenreMiddleLabel);
    const isAlreadySelected = nextGenreKeys.has(allGenreKey);
    [...nextGenreKeys].forEach((genreKey) => {
        if (splitGenreKey(genreKey).major === major) {
            nextGenreKeys.delete(genreKey);
        }
    });
    if (isAlreadySelected === false) {
        nextGenreKeys.add(allGenreKey);
    }
    selectedGenreKeys.value = nextGenreKeys;

    // すべて選択した直後は、中分類もチェック済みに見えることを確認できるよう展開する
    const nextExpandedGenreKeys = new Set(expandedGenreKeys.value);
    if (isAlreadySelected === false) {
        nextExpandedGenreKeys.add(major);
    }
    expandedGenreKeys.value = nextExpandedGenreKeys;
};

const toggleGenreMiddle = (major: string, middle: string) => {
    // すべて選択中の中分類を外した場合は、残りの中分類を個別選択へ展開する
    const nextGenreKeys = new Set(selectedGenreKeys.value);
    const middleGenreKey = getGenreKey(major, middle);
    const allGenreKey = getGenreKey(major, allGenreMiddleLabel);
    const genre = genreOptions.value.find((genreOption) => genreOption.major === major);
    if (nextGenreKeys.has(allGenreKey) === true && genre !== undefined) {
        nextGenreKeys.delete(allGenreKey);
        genre.middles
            .filter((middleGenre) => middleGenre !== middle)
            .forEach((middleGenre) => {
                nextGenreKeys.add(getGenreKey(major, middleGenre));
            });
        selectedGenreKeys.value = nextGenreKeys;
        return;
    }
    nextGenreKeys.delete(allGenreKey);
    if (nextGenreKeys.has(middleGenreKey) === true) {
        nextGenreKeys.delete(middleGenreKey);
    } else {
        nextGenreKeys.add(middleGenreKey);
    }

    // 中分類がすべて選ばれた場合は、大分類すべてに畳んで API 条件を短く保つ
    if (genre !== undefined && genre.middles.every((middleGenre) => {
        return nextGenreKeys.has(getGenreKey(major, middleGenre)) === true;
    })) {
        genre.middles.forEach((middleGenre) => {
            nextGenreKeys.delete(getGenreKey(major, middleGenre));
        });
        nextGenreKeys.add(allGenreKey);
    }
    selectedGenreKeys.value = nextGenreKeys;
};

const toggleGenreExpanded = (major: string) => {
    // チェック操作と展開操作を分け、親行を押しただけで中分類が開閉しないようにする
    const nextExpandedGenreKeys = new Set(expandedGenreKeys.value);
    if (nextExpandedGenreKeys.has(major) === true) {
        nextExpandedGenreKeys.delete(major);
    } else {
        nextExpandedGenreKeys.add(major);
    }
    expandedGenreKeys.value = nextExpandedGenreKeys;
};

const toggleChannel = (channel: ILiveChannel) => {
    // Set は同じ参照のままだと変更が追いにくいため、選択のたびに新しい Set へ差し替える
    const nextServiceKeys = new Set(selectedServiceKeys.value);
    const serviceKey = getChannelServiceKey(channel);
    if (nextServiceKeys.has(serviceKey) === true) {
        nextServiceKeys.delete(serviceKey);
    } else {
        nextServiceKeys.add(serviceKey);
    }
    selectedServiceKeys.value = nextServiceKeys;
};

const selectChannelType = (channelType: ChannelType) => {
    // 種別別全選択は既存選択を残し、該当種別のチャンネルだけを追加する
    const nextServiceKeys = new Set(selectedServiceKeys.value);
    selectableChannels.value
        .filter((channel) => channel.type === channelType)
        .forEach((channel) => {
            nextServiceKeys.add(getChannelServiceKey(channel));
        });
    selectedServiceKeys.value = nextServiceKeys;
};

const clearChannels = () => {
    // 0件選択は検索対象なしを明示する操作なので、全チャンネル指定の null とは分けて送る
    selectedServiceKeys.value = new Set();
};

const resetFilters = () => {
    // 検索語だけはヘッダーと共有しているため残し、絞り込みだけを初期状態へ戻す
    localCondition.value = {
        ...localCondition.value,
        exclude_keyword: '',
        is_title_only: false,
        is_case_sensitive: false,
        is_fuzzy_search_enabled: false,
        is_regex_search_enabled: false,
        service_ranges: null,
        genre_ranges: null,
        is_exclude_genre_ranges: false,
        date_ranges: null,
        is_exclude_date_ranges: false,
        duration_range_min: null,
        duration_range_max: null,
        broadcast_type: 'All',
    };
    selectedServiceKeys.value = new Set(allSelectableServiceKeys.value);
    selectedGenreKeys.value = new Set();
    expandedGenreKeys.value = new Set();
    dateRanges.value = [];
};

const addDateRange = () => {
    // 日時指定なしから明示的な条件へ切り替える操作なので、デフォルト範囲を1件追加する
    dateRanges.value = [...dateRanges.value, createDateRangeForm()];
};

const removeDateRange = (index: number) => {
    // 0件になった場合は buildCondition() 側で date_ranges: null へ戻す
    dateRanges.value = dateRanges.value.filter((_, dateRangeIndex) => dateRangeIndex !== index);
};

const copyDateRange = (index: number) => {
    const sourceDateRange = dateRanges.value[index];
    if (sourceDateRange === undefined) {
        return;
    }

    // フォーム ID だけ新規発行し、曜日・時刻の値はそのまま複製する
    const { id: _sourceId, ...dateRangeValues } = sourceDateRange;
    const copiedDateRange = createDateRangeForm(dateRangeValues);

    // 元の条件の直後へ挿入し、複製元を見ながら微調整しやすくする
    dateRanges.value = [
        ...dateRanges.value.slice(0, index + 1),
        copiedDateRange,
        ...dateRanges.value.slice(index + 1),
    ];
};

const buildCondition = (): IProgramSearchCondition => {
    const condition = structuredClone(toRaw(localCondition.value));
    condition.is_enabled = true;
    condition.note = '';
    condition.keyword = condition.keyword ?? '';
    condition.exclude_keyword = condition.exclude_keyword ?? '';

    // 表示候補がすべて選択されている場合は、サーバー側の全チャンネル指定として null を送る
    if (selectedServiceKeys.value.size === allSelectableServiceKeys.value.size) {
        condition.service_ranges = null;
    } else {
        condition.service_ranges = selectableChannels.value
            .filter((channel) => selectedServiceKeys.value.has(getChannelServiceKey(channel)) === true)
            .map((channel) => ({
                network_id: channel.network_id,
                transport_stream_id: channel.transport_stream_id ?? 0,
                service_id: channel.service_id,
            }));
    }

    // ジャンルは UI の選択粒度をそのまま送ることで、サーバー側の抽象化された変換処理へ委ねる
    const genreRanges = [...selectedGenreKeys.value].map((genreKey) => splitGenreKey(genreKey));
    condition.genre_ranges = genreRanges.length > 0 ? genreRanges : null;

    // 放送日時は複数範囲をそのまま送り、0件だけを日時指定なしとして扱う
    condition.date_ranges = dateRanges.value.length > 0
        ? dateRanges.value.map((dateRange) => ({
            start_day_of_week: dateRange.start_day_of_week,
            start_hour: dateRange.start_hour,
            start_minute: dateRange.start_minute,
            end_day_of_week: dateRange.end_day_of_week,
            end_hour: dateRange.end_hour,
            end_minute: dateRange.end_minute,
        }))
        : null;

    // 番組長は片側だけの指定も有効な検索条件なので、未入力のままなら null を維持する
    condition.duration_range_min = typeof condition.duration_range_min === 'number' &&
        Number.isFinite(condition.duration_range_min) === true
        ? Math.max(0, Math.floor(condition.duration_range_min))
        : null;
    condition.duration_range_max = typeof condition.duration_range_max === 'number' &&
        Number.isFinite(condition.duration_range_max) === true
        ? Math.max(0, Math.floor(condition.duration_range_max))
        : null;

    // 重複チェックはキーワード自動予約で予約を無効化するための条件なので、番組検索結果の絞り込みでは参照しない
    condition.duplicate_title_check_scope = 'None';
    condition.duplicate_title_check_period_days = 6;

    return condition;
};

const emitSearch = () => {
    emitConditionUpdate();
    emit('search');
};

const handleSearchKeyDown = (event: KeyboardEvent) => {
    // 日本語入力の変換確定 Enter では検索せず、確定後の通常 Enter だけを検索実行に使う
    if (event.isComposing === true) {
        return;
    }
    emitSearch();
};

</script>
<style lang="scss" scoped>

.program-search-filters {
    display: flex;
    flex-direction: column;
    width: 320px;
    flex-shrink: 0;
    gap: 16px;
    color: rgb(var(--v-theme-text));
    @include tablet-horizontal {
        width: 275px;
    }
    @include tablet-vertical {
        width: 100%;
        padding: 20px 16px;
    }
    @include smartphone-vertical {
        width: 100%;
        padding: 20px 16px;
    }
    @include smartphone-horizontal {
        width: 100%;
        padding: 20px 16px;
    }

    &__title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: 0.04em;
    }

    &__title-label {
        display: flex;
        align-items: center;
        min-width: 0;
        gap: 8px;
    }

    &__reset-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        height: 28px;
        gap: 4px;
        padding: 0px 10px;
        border: 1px solid rgba(var(--v-theme-text), 0.12);
        border-radius: 999px;
        color: rgb(var(--v-theme-text-darken-1));
        background: rgb(var(--v-theme-background-lighten-1));
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0em;
        transition: background-color 0.15s, border-color 0.15s, color 0.15s;
        cursor: pointer;

        &:hover {
            border-color: rgba(var(--v-theme-primary), 0.45);
            color: rgb(var(--v-theme-text));
            background: rgb(var(--v-theme-background-lighten-2));
        }
    }

    &__basic {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    &__toggle-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
    }

    &__toggle-chip {
        display: flex;
        align-items: center;
        min-width: 0;
        height: 34px;
        gap: 6px;
        padding: 0px 10px;
        border: 1px solid rgba(var(--v-theme-text), 0.16);
        border-radius: 7px;
        color: rgb(var(--v-theme-text-darken-1));
        background: rgb(var(--v-theme-background-lighten-1));
        font-size: 13px;
        font-weight: 700;
        line-height: 1;
        transition: background-color 0.15s, border-color 0.15s, color 0.15s;
        cursor: pointer;

        span {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        &:hover {
            border-color: rgba(var(--v-theme-primary), 0.55);
            color: rgb(var(--v-theme-text));
            background: rgb(var(--v-theme-background-lighten-2));
        }

        &--active {
            border-color: rgba(var(--v-theme-primary), 0.85);
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.16);
        }
    }

    &__search-icon {
        color: rgb(var(--v-theme-text-darken-1));
        cursor: pointer;
    }

    &__panels {
        :deep(.v-expansion-panel) {
            border-bottom: 1px solid rgba(var(--v-theme-text), 0.14);
            background: rgb(var(--v-theme-background-lighten-1));
            color: rgb(var(--v-theme-text));
            box-shadow: none;

            &:first-child {
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
            }

            &:last-child {
                border-bottom: 0px;
                border-bottom-right-radius: 7px;
                border-bottom-left-radius: 7px;
            }
        }
        :deep(.v-expansion-panel-title) {
            min-height: 44px;
            padding: 0px 14px;
            border-bottom: 1px solid transparent;
            font-size: 14px;
            font-weight: 600;
            transition: color 0.15s, background-color 0.15s, border-color 0.15s;
        }
        :deep(.v-expansion-panel--active > .v-expansion-panel-title:not(.v-expansion-panel-title--static)) {
            min-height: 44px;
        }
        :deep(.v-expansion-panel-title--active) {
            border-bottom-color: rgba(var(--v-theme-text), 0.14);
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.08);

            svg {
                color: rgb(var(--v-theme-primary));
            }
        }
        :deep(.v-expansion-panel-title__icon) {
            // Vuetify の矢印も自動余白を持つため、状態チップ側で右寄せを完結させる
            margin-inline-start: 12px;
            @include tablet-horizontal {
                margin-inline-start: 4px;
            }
        }
        :deep(.v-expansion-panel-text__wrapper) {
            padding: 12px 14px;
        }
        .program-search-filters__edge-panel {
            :deep(.v-expansion-panel-text__wrapper) {
                padding: 0px;
            }
        }
    }

    &__panel-title-text {
        display: inline-flex;
        align-items: center;
        flex: 0 1 auto;
        min-width: 0;
        gap: 6px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;

        svg {
            flex-shrink: 0;
            color: rgb(var(--v-theme-text-darken-1));
            transition: color 0.15s;
        }
    }

    &__panel-status-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        height: 20px;
        // 見出しの補足情報は閉じた状態でも視線が右端へ流れるよう、矢印の手前へ寄せる
        margin-left: auto;
        padding: 0px 7px;
        border: 1px solid rgba(var(--v-theme-text), 0.18);
        border-radius: 999px;
        color: rgb(var(--v-theme-text-darken-1));
        background: rgba(var(--v-theme-background), 0.18);
        font-size: 10.5px;
        font-weight: 700;
        line-height: 1;

        &--modified {
            border-color: rgba(var(--v-theme-primary), 0.55);
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.12);
        }

        &--warning {
            border-color: rgba(var(--v-theme-warning), 0.7);
            color: rgb(var(--v-theme-warning));
            background: rgba(var(--v-theme-warning), 0.16);
        }
    }

    &__panel-section {
        padding: 12px 14px;
    }

    &__checkbox-list {
        display: flex;
        flex-direction: column;
        max-height: 260px;
        gap: 4px;
        padding: 9px 7px;
        padding-bottom: 0px;
        overflow-y: auto;
    }

    &__genre-group {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    &__genre-children {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    &__genre-expander {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        flex-shrink: 0;
        margin-left: auto;
        border-radius: 50%;
        color: rgb(var(--v-theme-text-darken-1));
        transition: transform 0.15s, background-color 0.15s, color 0.15s;

        &:hover {
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.12);
        }

        &--open {
            transform: rotate(180deg);
        }
    }

    &__check-row {
        display: flex;
        align-items: center;
        width: 100%;
        min-height: 32px;
        gap: 9px;
        padding: 4px 8px;
        border: 0px;
        border-radius: 6px;
        color: rgb(var(--v-theme-text));
        background: transparent;
        font-size: 13.5px;
        font-weight: 600;
        line-height: 1.35;
        text-align: left;
        transition: background-color 0.15s, color 0.15s;
        cursor: pointer;

        &:hover {
            background: rgb(var(--v-theme-background-lighten-2));
        }

        &--active {
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.12);
        }

        &--major {
            font-weight: 700;
        }

        &--nested {
            padding-left: 28px;
            font-size: 13px;
        }
    }

    &__check-box {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        flex-shrink: 0;
        border: 2px solid rgba(var(--v-theme-text), 0.45);
        border-radius: 4px;
        color: rgb(var(--v-theme-background));
        background: transparent;
        transition: background-color 0.15s, border-color 0.15s;
    }

    &__check-row--active &__check-box {
        border-color: rgb(var(--v-theme-primary));
        background: rgb(var(--v-theme-primary));
    }

    &__check-row--partial &__check-box {
        border-color: rgb(var(--v-theme-primary));
        background: rgb(var(--v-theme-primary));
    }

    &__channel-logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        min-width: 38px;
        max-width: 38px;
        height: 28px;
        min-height: 28px;
        max-height: 28px;
        flex-shrink: 0;
        border-radius: 4px;
        background: rgba(var(--v-theme-background), 0.42);
        overflow: hidden;

        img {
            display: block;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
    }

    &__channel-name {
        display: flex;
        flex-direction: column;
        min-width: 0;
        gap: 1px;

        span {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        span:first-child {
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 10.5px;
            font-weight: 700;
            line-height: 1.1;
        }
    }

    &__quick-actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
    }

    &__mini-button {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 30px;
        gap: 5px;
        padding: 0px 9px;
        border: 1px solid rgba(var(--v-theme-text), 0.18);
        border-radius: 6px;
        color: rgb(var(--v-theme-text-darken-1));
        background: rgb(var(--v-theme-background-lighten-2));
        font-size: 12.5px;
        font-weight: 700;
        line-height: 1.2;
        transition: background-color 0.15s, border-color 0.15s, color 0.15s;
        cursor: pointer;

        &:hover {
            border-color: rgba(var(--v-theme-primary), 0.55);
            color: rgb(var(--v-theme-text));
        }

        &--wide {
            width: 100%;
        }
    }

    &__inline-toggle {
        display: inline-flex;
        align-items: center;
        min-height: 30px;
        gap: 6px;
        padding: 0px 10px;
        border: 1px solid rgba(var(--v-theme-text), 0.16);
        border-radius: 999px;
        color: rgb(var(--v-theme-text-darken-1));
        background: rgb(var(--v-theme-background-lighten-2));
        font-size: 13px;
        font-weight: 700;
        transition: background-color 0.15s, border-color 0.15s, color 0.15s;
        cursor: pointer;

        &:hover {
            border-color: rgba(var(--v-theme-primary), 0.55);
            color: rgb(var(--v-theme-text));
        }

        &--active {
            border-color: rgba(var(--v-theme-primary), 0.85);
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.16);
        }
    }

    &__date-range-list {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    &__date-range {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 8px;
        padding-top: 6px;
        border: 1px solid rgba(var(--v-theme-text), 0.12);
        border-radius: 7px;
        background: rgb(var(--v-theme-background-lighten-2));
    }

    &__date-range-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: rgb(var(--v-theme-text));
        font-size: 13px;
        font-weight: 700;
    }

    &__date-range-actions {
        display: flex;
        align-items: center;
        gap: 2px;
    }

    &__icon-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border: 0px;
        border-radius: 50%;
        color: rgb(var(--v-theme-text-darken-1));
        background: transparent;
        transition: background-color 0.15s, color 0.15s;
        cursor: pointer;

        &:hover {
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.12);
        }
    }

    &__date-row {
        display: grid;
        grid-template-columns: 28px minmax(0, 1fr) 62px 62px;
        align-items: center;
        gap: 6px;
    }

    &__date-label {
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 12px;
        font-weight: 700;
    }

    &__select {
        width: 100%;
        min-width: 0;
        height: 34px;
        padding: 0px 10px;
        border: 1px solid rgba(var(--v-theme-text), 0.16);
        border-radius: 6px;
        color: rgb(var(--v-theme-text));
        background: rgb(var(--v-theme-background-lighten-2));
        font-size: 13px;
        font-weight: 600;
        outline: none;
        cursor: pointer;

        &:focus {
            border-color: rgb(var(--v-theme-primary));
        }
    }

    &__segmented {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 6px;

        &--vertical {
            grid-template-columns: 1fr;
        }
    }

    &__segmented-button {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 34px;
        padding: 0px 8px;
        border: 1px solid rgba(var(--v-theme-text), 0.16);
        border-radius: 6px;
        color: rgb(var(--v-theme-text-darken-1));
        background: rgb(var(--v-theme-background-lighten-2));
        font-size: 13px;
        font-weight: 700;
        line-height: 1.2;
        text-align: center;
        transition: background-color 0.15s, border-color 0.15s, color 0.15s;
        cursor: pointer;

        &:hover {
            border-color: rgba(var(--v-theme-primary), 0.55);
            color: rgb(var(--v-theme-text));
        }

        &--active {
            border-color: rgba(var(--v-theme-primary), 0.85);
            color: rgb(var(--v-theme-primary));
            background: rgba(var(--v-theme-primary), 0.16);
        }
    }

    &__number-field {
        display: grid;
        grid-template-columns: auto minmax(0, 90px) 14px;
        align-items: center;
        gap: 8px;
        margin-top: 10px;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 13px;
        font-weight: 700;

        input {
            width: 100%;
            height: 34px;
            padding: 0px 8px;
            border: 1px solid rgba(var(--v-theme-text), 0.16);
            border-radius: 6px;
            color: rgb(var(--v-theme-text));
            background: rgb(var(--v-theme-background-lighten-2));
            font-size: 13px;
            font-weight: 700;
            outline: none;

            &:focus {
                border-color: rgb(var(--v-theme-primary));
            }
        }
    }

    &__duration-grid {
        display: flex;
        flex-direction: column;
        gap: 8px;

        .program-search-filters__number-field {
            margin-top: 0px;
        }
    }

    &__actions {
        background: rgb(var(--v-theme-background));
    }

    &__submit {
        height: 44px;
        font-weight: 700;
    }
}

</style>
