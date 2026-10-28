<template>
    <CapturePage :crumbs="crumbs" :with-scrubber="true">
        <CaptureHeader :title="title" :total="total" :active-tab="activeTab" :show-timeline-controls="true" :show-back-button="mode === 'Tag'"
            :loading-label="isLoaded || needsLogin ? null : mode === 'Search' ? '検索中...' : '読み込み中...'"
            :show-query-targets="mode === 'Search'" :axis="axis" :filter="typeFilter" :query-targets="queryTargets"
            @update:axis="updateAxis" @update:filter="updateTypeFilter" @update:query-targets="updateQueryTargets" @uploaded="timelineRef?.reload()" @scanned="timelineRef?.reload()" />

        <!-- お気に入りとタグはログインが必要 -->
        <div v-if="needsLogin" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:person-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">お気に入りとタグを使うには、ログインが必要です。</div>
            <div class="capture-empty__sub">お気に入りやタグは、アカウントごとに分けて保存されます。</div>
            <v-btn class="mt-6 px-4" color="secondary" variant="flat" height="40" to="/login/">
                <Icon icon="fa:sign-in" class="mr-2" />ログイン
            </v-btn>
        </div>
        <template v-else>
            <div v-if="isLoaded && isLoadFailed" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">キャプチャを読み込めませんでした。</div>
                <div class="capture-empty__sub">KonomiTV サーバーが起動しているか確認してから、ページを再読み込みしてください。</div>
            </div>
            <div v-else-if="isLoaded && total === 0" class="capture-empty">
                <Icon class="capture-empty__icon" :icon="emptyIcon" width="54px" height="54px" />
                <div class="capture-empty__message" v-html="emptyMessage"></div>
                <div class="capture-empty__sub" v-html="emptySubMessage"></div>
                <!-- 条件で0件になったときは、その場で条件を外せるようにする -->
                <v-btn v-if="hasTypeFilter" class="mt-6 px-4" color="secondary" variant="flat" height="40" @click="clearTypeFilter">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                    <span class="ml-1">絞り込みをすべて解除</span>
                </v-btn>
                <v-btn v-else-if="queryTargets.length > 0" class="mt-6 px-4" color="secondary" variant="flat" height="40" @click="updateQueryTargets([])">
                    <Icon icon="fluent:search-16-regular" width="18px" height="18px" />
                    <span class="ml-1">すべての範囲から検索</span>
                </v-btn>
            </div>
            <CaptureTimeline ref="timelineRef" :filter="filter" :axis="axis" :day-start-hour="dayStartHour"
                :selection="selection" @open="openCapture" @reloading="onReloading" @loaded="onLoaded" @updated="onUpdated([$event])" />
        </template>

        <CaptureSelectionBar :selection="selection" @updated="onUpdated" @deleted="onDeleted" />
        <CaptureLightbox :capture="openedCapture" :program-hint="openedProgram" :navigate="navigate"
            @update:capture="openedCapture = $event" @updated="onUpdated([$event])" @deleted="onDeleted" />
    </CapturePage>
</template>
<script lang="ts" setup>

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import CaptureHeader from '@/components/Captures/CaptureHeader.vue';
import CaptureLightbox from '@/components/Captures/CaptureLightbox.vue';
import CapturePage from '@/components/Captures/CapturePage.vue';
import { useCaptureSelection } from '@/components/Captures/CaptureSelection';
import CaptureSelectionBar from '@/components/Captures/CaptureSelectionBar.vue';
import CaptureTimeline from '@/components/Captures/CaptureTimeline.vue';
import Captures, { CaptureQueryTarget, CaptureTimelineAxis, ICapture, ICaptureFilter } from '@/services/Captures';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';


/** このページで出すタイムラインの種類 (ルートの meta で決まる) */
type TimelineMode = 'Timeline' | 'Favorites' | 'Tag' | 'Search';

const route = useRoute();
const router = useRouter();
const settingsStore = useSettingsStore();
const userStore = useUserStore();

const mode = computed(() => (route.meta.captureMode ?? 'Timeline') as TimelineMode);
const tagId = computed(() => mode.value === 'Tag' ? Number(route.params.tag_id) : null);
const searchQuery = computed(() => mode.value === 'Search' ? String(route.query.query ?? '') : '');
// 検索語を探す範囲 (URL のクエリに持たせ、1つも選んでいなければすべての範囲から探す)
const QUERY_TARGETS: CaptureQueryTarget[] = ['CaptionText', 'ProgramTitle', 'ProgramDescription'];
const queryTargets = computed<CaptureQueryTarget[]>(() => {
    if (mode.value !== 'Search') {
        return [];
    }
    const value = route.query.query_targets;
    const values = Array.isArray(value) ? value : [value];
    return QUERY_TARGETS.filter(target => values.includes(target));
});
const tagName = ref<string | null>(null);

const timelineRef = ref<InstanceType<typeof CaptureTimeline> | null>(null);
const selection = useCaptureSelection();
const total = ref<number | null>(null);
const isLoaded = ref(false);
const isLoggedIn = ref(userStore.is_logged_in);

// 日付の境目は、28時間表記の設定に合わせる (深夜アニメのキャプチャが前の日にまとまるように)
const dayStartHour = computed(() => settingsStore.settings.use_28hour_clock ? 4 : 0);

// 時間の軸とキャプチャの種類の絞り込みは、URL のクエリに持たせて戻る操作でも保つ
const axis = computed<CaptureTimelineAxis>(() => route.query.axis === 'BroadcastAt' ? 'BroadcastAt' : 'CapturedAt');
const parseBool = (value: unknown) => value === 'true' ? true : value === 'false' ? false : null;
const typeFilter = computed<ICaptureFilter>(() => ({
    is_caption_composited: parseBool(route.query.is_caption_composited),
    is_comment_composited: parseBool(route.query.is_comment_composited),
    has_caption_text: parseBool(route.query.has_caption_text),
    has_metadata: parseBool(route.query.has_metadata),
}));
const filter = computed<ICaptureFilter>(() => ({
    ...typeFilter.value,
    is_favorite: mode.value === 'Favorites' ? true : null,
    tag_id: tagId.value,
    query: searchQuery.value || null,
    query_targets: queryTargets.value,
}));

const updateQuery = (patch: Record<string, string | string[] | null>) => {
    const query = { ...route.query, ...patch };
    for (const key of Object.keys(query)) {
        if (query[key] === null || query[key] === undefined) {
            delete query[key];
        }
    }
    void router.replace({ query });
};
const updateAxis = (value: CaptureTimelineAxis) => updateQuery({ axis: value === 'BroadcastAt' ? 'BroadcastAt' : null });
const updateQueryTargets = (value: CaptureQueryTarget[]) => updateQuery({ query_targets: value.length > 0 ? value : null });
const updateTypeFilter = (value: ICaptureFilter) => {
    updateQuery({
        is_caption_composited: value.is_caption_composited === null || value.is_caption_composited === undefined ? null : String(value.is_caption_composited),
        is_comment_composited: value.is_comment_composited === null || value.is_comment_composited === undefined ? null : String(value.is_comment_composited),
        has_caption_text: value.has_caption_text === null || value.has_caption_text === undefined ? null : String(value.has_caption_text),
        has_metadata: value.has_metadata === null || value.has_metadata === undefined ? null : String(value.has_metadata),
    });
};

const needsLogin = computed(() => (mode.value === 'Favorites' || mode.value === 'Tag') && !isLoggedIn.value);
const activeTab = computed(() => {
    switch (mode.value) {
        case 'Favorites': return 'Favorites';
        case 'Tag': return 'Tags';
        case 'Search': return null;
        default: return 'Timeline';
    }
});
const title = computed(() => {
    switch (mode.value) {
        case 'Favorites': return 'お気に入り';
        case 'Tag': return tagName.value ?? 'タグ';
        // スマホの縦画面では、録画番組の検索結果と同じく「検索結果」に短くする (検索語は検索欄に残っている)
        case 'Search': return Utils.isSmartphoneVertical() ? '検索結果' : `「${searchQuery.value}」の検索結果`;
        default: return 'キャプチャ';
    }
});
const crumbs = computed(() => {
    const base = [{ name: 'ホーム', path: '/' }, { name: 'キャプチャ', path: '/captures/' }];
    switch (mode.value) {
        case 'Favorites': return [...base, { name: 'お気に入り', path: '/captures/favorites/', disabled: true }];
        case 'Tag': return [...base, { name: 'タグ別', path: '/captures/tags/' }, { name: tagName.value ?? 'タグ', path: route.path, disabled: true }];
        case 'Search': return [...base, { name: '検索結果', path: route.fullPath, disabled: true }];
        default: return [{ name: 'ホーム', path: '/' }, { name: 'キャプチャ', path: '/captures/', disabled: true }];
    }
});
const emptyIcon = computed(() => mode.value === 'Favorites' ? 'fluent:heart-20-regular' : mode.value === 'Search' ? 'fluent:search-20-regular' : 'fluent:image-20-regular');
// 画像の種類の絞り込みが1つでも掛かっているか (0件の理由が「まだ無い」のか「条件に合わない」のかを分けるため)
const hasTypeFilter = computed(() => Object.values(typeFilter.value).some(value => value !== null && value !== undefined));

const emptyMessage = computed(() => {
    if (hasTypeFilter.value) {
        return '条件に一致するキャプチャはありません。';
    }
    if (mode.value === 'Favorites') {
        return 'お気に入りに追加したキャプチャはまだありません。';
    }
    if (mode.value === 'Tag') {
        return 'このタグが付与されたキャプチャはまだありません。';
    }
    if (mode.value === 'Search') {
        return '条件に一致するキャプチャは見つかりませんでした。';
    }
    return 'キャプチャはまだありません。';
});
const emptySubMessage = computed(() => {
    if (hasTypeFilter.value) {
        return '絞り込み条件を解除すると、<br class="d-sm-none">他のキャプチャも表示されます。';
    }
    if (mode.value === 'Favorites') {
        return 'キャプチャをお気に入りに追加すると、<br class="d-sm-none">ここに表示されます。';
    }
    if (mode.value === 'Search' && queryTargets.value.length > 0) {
        return '検索する範囲の選択をすべて外すと、<br class="d-sm-none">チャンネル名やファイル名も含めて検索します。';
    }
    if (mode.value === 'Search') {
        return '字幕テキスト・番組名・番組概要・チャンネル名・ファイル名から検索できます。<br>空白で区切ると、すべてを含むキャプチャを検索します。';
    }
    if (mode.value === 'Timeline') {
        return '視聴画面でキャプチャを撮影するか、保存先フォルダに画像が追加されると、<br class="d-none d-sm-inline">ここに表示されます。';
    }
    return '';
});

const clearTypeFilter = () => {
    updateTypeFilter({ is_caption_composited: null, is_comment_composited: null, has_caption_text: null, has_metadata: null });
};

const isLoadFailed = ref(false);
// 別の条件の一覧を読み込み始めたら、前の条件の件数を消して読み込み中にする
const onReloading = () => {
    total.value = null;
    isLoaded.value = false;
};
const onLoaded = (value: number | null) => {
    total.value = value;
    isLoadFailed.value = value === null;
    isLoaded.value = true;
};

// 拡大表示
const openedCapture = ref<ICapture | null>(null);
const openedProgram = computed(() => timelineRef.value?.getProgram(openedCapture.value?.capture_program_id ?? null) ?? null);
const openCapture = (capture: ICapture) => {
    openedCapture.value = capture;
};
const navigate = async (capture: ICapture, delta: 1 | -1) => timelineRef.value?.getNeighbor(capture, delta) ?? null;

// お気に入り・タグの変更は、表示中の一覧に反映する (お気に入りから外したものは、お気に入りの画面では一覧を取り直す)
const onUpdated = (captures: ICapture[]) => {
    for (const capture of captures) {
        timelineRef.value?.replaceCapture(capture);
        if (openedCapture.value?.id === capture.id) {
            openedCapture.value = capture;
        }
    }
    if ((mode.value === 'Favorites' && captures.some(capture => capture.is_favorite === false)) ||
        (mode.value === 'Tag' && captures.some(capture => !capture.tag_ids?.includes(tagId.value!)))) {
        void timelineRef.value?.reload();
    }
};
const onDeleted = () => {
    void timelineRef.value?.reload();
};

// タグの画面では、見出しに出すタグの名前を取る
const loadTagName = async () => {
    tagName.value = null;
    if (mode.value === 'Tag' && isLoggedIn.value) {
        const tags = await Captures.fetchTags();
        tagName.value = tags?.find(tag => tag.id === tagId.value)?.name ?? null;
    }
};
watch(tagId, loadTagName);

// 別の種類のタイムラインへ移ったら、選択と拡大表示を閉じる
watch(() => route.path, () => {
    selection.clear();
    openedCapture.value = null;
    isLoaded.value = false;
});

onMounted(async () => {
    await userStore.fetchUser();
    isLoggedIn.value = userStore.is_logged_in;
    await loadTagName();
});

</script>
