<template>
    <CapturePage :crumbs="crumbs" :with-scrubber="true">
        <CaptureHeader :title="title" :total="total" :active-tab="activeTab" :show-timeline-controls="true" :show-back-button="mode === 'Tag'"
            :show-query-targets="mode === 'Search'" :axis="axis" :filter="viewFilter" :query-targets="queryTargets"
            :lock-favorite="mode === 'Favorites'" :excluded-tag-id="tagId"
            @update:axis="updateAxis" @update:filter="updateViewFilter" @update:query-targets="updateQueryTargets" @uploaded="timelineRef?.reload()" @scanned="timelineRef?.reload()" />

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
            <!-- 削除済みのタグの URL などで開いたときは、読み込みの失敗ではなく、タグが存在しないことを伝えてタグの一覧へ案内する -->
            <div v-if="isTagMissing" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:tag-dismiss-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">このタグは存在しません。</div>
                <div class="capture-empty__sub">タグが削除されたか、別のアカウントのタグです。<br class="d-sm-none">タグの一覧から、表示するタグを選び直してください。</div>
                <v-btn class="mt-6 px-4" color="secondary" variant="flat" height="40" to="/captures/tags/">
                    <Icon icon="fluent:tag-multiple-20-regular" width="18px" height="18px" />
                    <span class="ml-1">タグの一覧へ戻る</span>
                </v-btn>
            </div>
            <!-- 読み込み中は、ほかのキャプチャの画面と同じく見出しより下の領域の中央にスピナーを表示する -->
            <div v-else-if="!isLoaded || isTagLoading" class="capture-loading">
                <Icon icon="line-md:loading-twotone-loop" width="48px" height="48px" />
            </div>
            <div v-else-if="isLoadFailed" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">キャプチャを読み込めませんでした。</div>
                <div class="capture-empty__sub">KonomiTV サーバーが起動しているか確認してから、ページを再読み込みしてください。</div>
            </div>
            <div v-else-if="isLoaded && total === 0" class="capture-empty">
                <Icon class="capture-empty__icon" :icon="emptyIcon" width="54px" height="54px" />
                <div class="capture-empty__message" v-html="emptyMessage"></div>
                <div class="capture-empty__sub" v-html="emptySubMessage"></div>
                <!-- 条件で0件になったときは、その場で条件を外せるようにする -->
                <v-btn v-if="hasViewFilter" class="mt-6 px-4" color="secondary" variant="flat" height="40" @click="clearViewFilter">
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

        <CaptureSelectionBar ref="selectionBarRef" :selection="selection" @updated="onUpdated" @deleted="onDeleted" />
        <CaptureLightbox :capture="openedCapture" :program-hint="openedProgram" :navigate="navigate" :reveal="reveal"
            @update:capture="onLightboxCaptureChange" @updated="onUpdated([$event])" @deleted="onDeleted" />
    </CapturePage>
</template>
<script lang="ts" setup>

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import CaptureHeader from '@/components/Captures/CaptureHeader.vue';
import { useCaptureKeyboard } from '@/components/Captures/CaptureKeyboard';
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

// 時間の軸と絞り込みは、URL のクエリに持たせて戻る操作でも保つ
const axis = computed<CaptureTimelineAxis>(() => route.query.axis === 'BroadcastAt' ? 'BroadcastAt' : 'CapturedAt');
const parseBool = (value: unknown) => value === 'true' ? true : value === 'false' ? false : null;
const parseList = (value: unknown) => {
    const values = Array.isArray(value) ? value : [value];
    return values.filter((item): item is string => typeof item === 'string' && item !== '');
};
const parseDate = (value: unknown) => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
// ヘッダーの「並べ替えと絞り込み」で変更できる絞り込み
// お気に入りとタグの画面の前提の条件 (お気に入りであること・そのタグ) は含めず、その上に重ねる条件だけを持つ
const viewFilter = computed<ICaptureFilter>(() => ({
    is_favorite: mode.value !== 'Favorites' && route.query.is_favorite === 'true' ? true : null,
    tag_ids: parseList(route.query.tag_ids).map(Number).filter(id => Number.isInteger(id) && id !== tagId.value),
    channel_ids: parseList(route.query.channel_ids),
    start_date: parseDate(route.query.start_date),
    end_date: parseDate(route.query.end_date),
    is_caption_composited: parseBool(route.query.is_caption_composited),
    is_comment_composited: parseBool(route.query.is_comment_composited),
    has_caption_text: parseBool(route.query.has_caption_text),
    has_metadata: parseBool(route.query.has_metadata),
}));
const filter = computed<ICaptureFilter>(() => {
    const tagIds = [...(viewFilter.value.tag_ids ?? [])];
    if (tagId.value !== null) {
        tagIds.unshift(tagId.value);
    }
    return {
        ...viewFilter.value,
        is_favorite: mode.value === 'Favorites' ? true : viewFilter.value.is_favorite,
        tag_ids: tagIds,
        query: searchQuery.value || null,
        query_targets: queryTargets.value,
    };
});

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
const toQueryValue = (value: boolean | string | null | undefined) => value === null || value === undefined || value === '' ? null : String(value);
const updateViewFilter = (value: ICaptureFilter) => {
    const tagIds = (value.tag_ids ?? []).map(String);
    const channelIds = value.channel_ids ?? [];
    updateQuery({
        is_favorite: value.is_favorite === true ? 'true' : null,
        tag_ids: tagIds.length > 0 ? tagIds : null,
        channel_ids: channelIds.length > 0 ? channelIds : null,
        start_date: toQueryValue(value.start_date),
        end_date: toQueryValue(value.end_date),
        is_caption_composited: toQueryValue(value.is_caption_composited),
        is_comment_composited: toQueryValue(value.is_comment_composited),
        has_caption_text: toQueryValue(value.has_caption_text),
        has_metadata: toQueryValue(value.has_metadata),
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
// 絞り込みが1つでも掛かっているか (0件の理由が「まだ無い」のか「条件に合わない」のかを分けるため)
const hasViewFilter = computed(() => {
    for (const value of Object.values(viewFilter.value)) {
        if (Array.isArray(value) ? value.length > 0 : value !== null && value !== undefined) {
            return true;
        }
    }
    return false;
});

const emptyMessage = computed(() => {
    if (hasViewFilter.value) {
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
    if (hasViewFilter.value) {
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

const clearViewFilter = () => {
    updateViewFilter({});
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
const reveal = async (capture: ICapture) => timelineRef.value?.revealCapture(capture);

// 拡大表示で前後へ送ったときは、表示していた1枚だけを選んでいる状態なら、macOS のクイックルックと同じく選択も送った先へ移す
// 閉じたあとに矢印キーで続けて移動するときの起点を、最後に見ていたキャプチャにするため
// 表示していたキャプチャと別のキャプチャを選んでいるとき (拡大表示で削除して、選択に別の1枚だけが残ったときなど) は、選択を変更しない
const onLightboxCaptureChange = (capture: ICapture | null) => {
    const shown = openedCapture.value;
    if (capture !== null && shown !== null && selection.count.value === 1 && selection.isSelected(shown)) {
        selection.selectOnly(capture);
    }
    openedCapture.value = capture;
};


// ---------- キーボードでの操作 ----------

const selectionBarRef = ref<InstanceType<typeof CaptureSelectionBar> | null>(null);
useCaptureKeyboard({
    selection,
    selectionBar: selectionBarRef,
    isLightboxOpen: () => openedCapture.value !== null,
    open: openCapture,
    getTarget: async (capture, direction) => timelineRef.value?.getKeyboardTarget(capture, direction) ?? null,
    getOrdered: () => timelineRef.value?.orderedLoaded() ?? [],
    reveal: async (capture) => timelineRef.value?.revealCapture(capture),
    // 全選択は、選んでいるキャプチャがある日のキャプチャだけにする (日付の見出しのチェックと同じ範囲)
    // 絞り込みなしで十数万枚をまとめて選び、そのまま削除してしまう事故を防ぐため
    getSelectAllTargets: (cursor) => timelineRef.value?.getDayCaptures(cursor) ?? [],
});

// お気に入り・タグの変更は、表示中の一覧に反映する
// お気に入りやタグで絞り込んでいる一覧から外れたキャプチャがあれば、一覧を取り直す
const onUpdated = (captures: ICapture[]) => {
    for (const capture of captures) {
        timelineRef.value?.replaceCapture(capture);
        if (openedCapture.value?.id === capture.id) {
            openedCapture.value = capture;
        }
    }
    // 選択が持っている内容も、まだ選ばれているキャプチャの分だけ新しい状態に差し替える (Space で開き直したときに古い状態で開かないようにするため)
    selection.setMany(captures.filter(capture => selection.isSelected(capture)), true);
    const filterTagIds = filter.value.tag_ids ?? [];
    for (const capture of captures) {
        const isUnfavorited = filter.value.is_favorite === true && capture.is_favorite === false;
        const isUntagged = filterTagIds.some(id => capture.tag_ids?.includes(id) !== true);
        if (isUnfavorited || isUntagged) {
            void timelineRef.value?.reload();
            return;
        }
    }
};
// 削除したキャプチャは選択からも外す (拡大表示で削除したときも、選択に残ったまま一括の操作に送らないようにするため)
const onDeleted = (capture_ids: number[]) => {
    const deletedIds = new Set(capture_ids);
    selection.setMany([...selection.selected.value.values()].filter(capture => deletedIds.has(capture.id)), false);
    void timelineRef.value?.reload();
};

// タグの画面では、見出しに出すタグの名前を取り、タグが存在するかを確認する
// タグの一覧を読み込めなかったときは、存在しないとは判断せず、タイムラインの読み込みの結果を表示する
const isTagMissing = ref(false);
// タグが存在するかを確認している間は、存在しないタグで絞り込んだ読み込みの失敗を表示せずに、読み込み中にする
// (タグの画面を開いた直後は、ログイン状態を確認し終えて確認を始めるまでの間も読み込み中にする)
const isTagLoading = ref(mode.value === 'Tag');
const loadTagName = async () => {
    tagName.value = null;
    isTagMissing.value = false;
    isTagLoading.value = false;
    if (mode.value === 'Tag' && isLoggedIn.value) {
        const myTagId = tagId.value;
        isTagLoading.value = true;
        const tags = await Captures.fetchTags();
        // 確認している間に別のタグへ移ったときは、移った先のタグの確認の結果だけを反映する
        if (myTagId !== tagId.value) {
            return;
        }
        isTagLoading.value = false;
        if (tags !== null) {
            const tag = tags.find(item => item.id === myTagId);
            tagName.value = tag?.name ?? null;
            isTagMissing.value = tag === undefined;
        }
    }
};
watch(tagId, loadTagName);

// 別の種類のタイムラインへ移ったら、選択と拡大表示を閉じる
// 読み込み中の表示は、絞り込みが変わってタイムラインが読み込み直すとき (reloading) に切り替わる
// 「お気に入りのみ」で絞り込んだタイムラインからお気に入りのタブへ移ったときのように、絞り込みが同じなら読み込み直さずに今の一覧を表示し続ける
watch(() => route.path, () => {
    selection.clear();
    openedCapture.value = null;
});

onMounted(async () => {
    await userStore.fetchUser();
    isLoggedIn.value = userStore.is_logged_in;
    await loadTagName();
});

</script>
