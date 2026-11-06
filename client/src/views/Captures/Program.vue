<template>
    <CapturePage :crumbs="[
        { name: 'ホーム', path: '/' },
        { name: 'キャプチャ', path: '/captures/' },
        { name: '番組別', path: '/captures/programs/' },
        { name: program ? program.title : '番組', path: route.fullPath, disabled: true },
    ]">
        <div ref="rootRef" class="capture-program">
            <!-- 番組名から並べ替えまでの見出しの部分 (スマホの縦画面ではマイリストの見出しと同じく左右に 8px を加える) -->
            <div class="capture-program__intro">
                <!-- 戻るボタンと同じ行には番組名だけを置く -->
                <div class="capture-program__header" :class="{'capture-program__header--with-toolbar': isToolbarVisible}">
                    <div v-ripple class="capture-program__back" @click="$router.back()">
                        <Icon icon="fluent:chevron-left-12-filled" width="27px" />
                    </div>
                    <h2 class="capture-program__title" v-if="program" v-html="ProgramUtils.decorateProgramInfo(program, 'title')"></h2>
                    <h2 class="capture-program__title" v-else>{{ isLoading ? '読み込み中...' : 'この番組のキャプチャ' }}</h2>
                </div>
                <!-- PC では番組の情報の右に並べ替えと絞り込みを置き、そのためだけの段を作らない -->
                <!-- スマホの縦画面ではアイコンだけのボタンになるので、タイムラインの見出しの行と同じく、番組名の行の右端に置く -->
                <div class="capture-program__body">
                    <!-- 1枚表示の情報欄と同じ部品で、局ロゴ・局名・放送時間・枚数と番組概要を出し、録画の再生を続ける -->
                    <div v-if="program" class="capture-program__meta">
                        <CaptureProgramInfo :program="program" :capture-count="captures.length > 0 ? captures.length : null" />
                        <div v-if="program.recorded_program_ids.length > 0" class="capture-program__actions">
                            <v-btn color="primary" variant="flat" height="38" class="capture-program__action"
                                :to="`/videos/watch/${program.recorded_program_ids[0]}`">
                                <Icon icon="fluent:play-20-filled" width="18px" />
                                <span class="ml-2">録画を再生</span>
                            </v-btn>
                        </div>
                    </div>
                    <div v-if="isToolbarVisible" class="capture-program__toolbar">
                        <!-- 並べ替えと絞り込みは、タイムラインと同じく1つのボタンから開く (放送回が決まっているので、チャンネルと期間は出さない) -->
                        <CaptureFilterMenu ref="filterMenuRef" sort-label="並べ替え" :sort-choices="orderChoices" :sort="order"
                            :filter="viewFilter" :is-single-program="true" @update:sort="updateOrder" @update:filter="updateViewFilter" />
                    </div>
                </div>
            </div>

            <!-- 使っている絞り込みの条件だけをチップで並べ、× でその条件を解除できるようにする -->
            <div v-if="activeFilterChips.length > 0" class="capture-program__active-filters">
                <v-chip v-for="chip in activeFilterChips" :key="chip.key" class="capture-program__active-filter" color="primary"
                    variant="tonal" size="small" closable @click:close="chip.clear()">
                    {{ chip.label }}
                </v-chip>
            </div>

            <div v-if="isLoadFailed" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">キャプチャを読み込めませんでした。</div>
                <div class="capture-empty__sub">KonomiTV サーバーが起動しているか確認してから、ページを再読み込みしてください。</div>
            </div>
            <!-- 絞り込みで0件になったときは、まだ無いのではなく条件に合わないことを伝え、その場で条件を外せるようにする -->
            <div v-else-if="!isLoading && captures.length === 0 && hasViewFilter" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:image-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">条件に一致するキャプチャはありません。</div>
                <div class="capture-empty__sub">絞り込み条件を解除すると、<br class="d-sm-none">他のキャプチャも表示されます。</div>
                <v-btn class="mt-6 px-4" color="secondary" variant="flat" height="40" @click="clearViewFilter">
                    <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                    <span class="ml-1">絞り込みをすべて解除</span>
                </v-btn>
            </div>
            <div v-else-if="!isLoading && captures.length === 0" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:image-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">この番組のキャプチャはまだありません。</div>
                <div class="capture-empty__sub">この番組の視聴中にキャプチャを撮影すると、<br class="d-sm-none">ここに表示されます。</div>
            </div>

            <div class="capture-program__grid" :class="{'capture-program__grid--captions': hasCaptions}">
                <div v-for="capture in captures" :key="capture.id" class="capture-program__item">
                    <div class="capture-program__tile">
                        <CaptureTile :capture="capture" :show-position="order === 'PlaybackPosition'"
                            :selected="selection.isSelected(capture)" :cursor="selection.isCursor(capture)" :previewed="selection.isPreviewed(capture)"
                            :selecting="selection.isSelecting.value"
                            @open="openedCapture = capture"
                            @toggle="(shiftKey) => selection.toggle(capture, shiftKey ? captures : null)"
                            @updated="onUpdated([$event])" />
                    </div>
                    <!-- 字幕が出ていなかった場面は何も書かない (「字幕なし」と書くと、それ自体がセリフに見えるため) -->
                    <div v-if="hasCaptions" class="capture-program__caption">{{ capture.caption_text ?? '' }}</div>
                </div>
            </div>
        </div>

        <CaptureShortcutDialog v-model:show="isShortcutDialogOpen" select-all-scope="Program" />
        <CaptureSelectionBar ref="selectionBarRef" :selection="selection" @updated="onUpdated" @deleted="onDeleted" />
        <CaptureLightbox :capture="openedCapture" :program-hint="program" :navigate="navigate" :reveal="reveal"
            @update:capture="onLightboxCaptureChange" @updated="onUpdated([$event])" @deleted="onDeleted" />
    </CapturePage>
</template>
<script lang="ts" setup>

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import CaptureFilterMenu from '@/components/Captures/CaptureFilterMenu.vue';
import { CaptureKeyboardDirection, useCaptureKeyboard } from '@/components/Captures/CaptureKeyboard';
import CaptureLightbox from '@/components/Captures/CaptureLightbox.vue';
import CapturePage from '@/components/Captures/CapturePage.vue';
import CaptureProgramInfo from '@/components/Captures/CaptureProgramInfo.vue';
import { useCaptureRangePreview, useCaptureSelection } from '@/components/Captures/CaptureSelection';
import CaptureSelectionBar from '@/components/Captures/CaptureSelectionBar.vue';
import CaptureShortcutDialog from '@/components/Captures/CaptureShortcutDialog.vue';
import CaptureTile from '@/components/Captures/CaptureTile.vue';
import Captures, { CaptureSortOrder, ICapture, ICaptureFilter, ICaptureProgram } from '@/services/Captures';
import Videos from '@/services/Videos';
import useUserStore from '@/stores/UserStore';
import { ProgramUtils } from '@/utils';


const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const selection = useCaptureSelection();
// Shift キーを押しながらマウスを乗せたときに、クリックで選ばれる範囲を示す
useCaptureRangePreview(selection, () => captures.value);

const program = ref<ICaptureProgram | null>(null);
const captures = ref<ICapture[]>([]);
const isLoading = ref(true);
// 読み込みに失敗したか (0件と区別して、読み込めなかったことを伝えるため)
const isLoadFailed = ref(false);
// 並び順は番組別の一覧と同じく URL のクエリパラメータに保持し、録画の再生から戻ったときも同じ並びで表示する
// (並びが変わると、戻ったスクロール位置に別の場面のキャプチャが表示されるため)
const order = computed<CaptureSortOrder>({
    get: () => {
        if (route.query.order === 'CapturedAtDesc') {
            return 'CapturedAtDesc';
        }
        if (route.query.order === 'CapturedAtAsc') {
            return 'CapturedAtAsc';
        }
        return 'PlaybackPosition';
    },
    set: (value) => {
        void router.replace({ query: { ...route.query, order: value === 'PlaybackPosition' ? undefined : value } });
    },
});
// 並べ替えの選択肢 (メニューの3つ並びのボタンの幅に1行で収まるよう、「撮影日時」を「撮影」と短く書く)
const orderChoices: { label: string; value: CaptureSortOrder }[] = [
    { label: '再生位置順', value: 'PlaybackPosition' },
    { label: '撮影が新しい順', value: 'CapturedAtDesc' },
    { label: '撮影が古い順', value: 'CapturedAtAsc' },
];
const updateOrder = (value: string) => {
    const choice = orderChoices.find(item => item.value === value);
    if (choice !== undefined) {
        order.value = choice.value;
    }
};
const openedCapture = ref<ICapture | null>(null);

// どの入口から来たかで、絞り込みの条件を変える
// - /captures/programs/:capture_program_id: キャプチャの番組の ID
// - /captures/recorded/:video_id: 録画番組のメニューから (番組キーが同じキャプチャ)
// - /captures/broadcast?network_id=...: ライブ視聴から (番組キーそのもの)
const filter = computed<ICaptureFilter>(() => {
    if (route.params.capture_program_id !== undefined) {
        return { capture_program_id: Number(route.params.capture_program_id) };
    }
    if (route.params.video_id !== undefined) {
        return { recorded_program_id: Number(route.params.video_id) };
    }
    return {
        network_id: Number(route.query.network_id),
        service_id: Number(route.query.service_id),
        event_id: Number(route.query.event_id),
        start_time: String(route.query.start_time ?? ''),
    };
});

// 「並べ替えと絞り込み」で変更できる絞り込み (タイムラインと同じクエリパラメータの名前で URL に保持する)
// 放送回が決まっているので、チャンネルと期間の絞り込みは持たない
const parseBool = (value: unknown) => value === 'true' ? true : value === 'false' ? false : null;
const parseList = (value: unknown) => {
    const values = Array.isArray(value) ? value : [value];
    return values.filter((item): item is string => typeof item === 'string' && item !== '');
};
const viewFilter = computed<ICaptureFilter>(() => ({
    is_favorite: route.query.is_favorite === 'true' ? true : null,
    tag_ids: parseList(route.query.tag_ids).map(Number).filter(id => Number.isInteger(id)),
    is_caption_composited: parseBool(route.query.is_caption_composited),
    is_comment_composited: parseBool(route.query.is_comment_composited),
    has_caption_text: parseBool(route.query.has_caption_text),
    has_metadata: parseBool(route.query.has_metadata),
}));
const toQueryValue = (value: boolean | null | undefined) => value === null || value === undefined ? undefined : String(value);
const updateViewFilter = (value: ICaptureFilter) => {
    const tagIds = (value.tag_ids ?? []).map(String);
    void router.replace({
        query: {
            ...route.query,
            is_favorite: value.is_favorite === true ? 'true' : undefined,
            tag_ids: tagIds.length > 0 ? tagIds : undefined,
            is_caption_composited: toQueryValue(value.is_caption_composited),
            is_comment_composited: toQueryValue(value.is_comment_composited),
            has_caption_text: toQueryValue(value.has_caption_text),
            has_metadata: toQueryValue(value.has_metadata),
        },
    });
};
const clearViewFilter = () => {
    updateViewFilter({});
};
// 絞り込みが1つでも掛かっているか (0件の理由が「まだ無い」のか「条件に合わない」のかを分けるため)
const hasViewFilter = computed(() => {
    for (const value of Object.values(viewFilter.value)) {
        if (Array.isArray(value) ? value.length > 0 : value !== null && value !== undefined) {
            return true;
        }
    }
    return false;
});
// 並べ替えと絞り込みのボタンは、キャプチャがあるときと、絞り込みで0件になったとき (条件を変えたり解除したりするため) に出す
const isToolbarVisible = computed(() => captures.value.length > 0 || hasViewFilter.value);
// 使っている絞り込みの条件のチップ (条件と解除の処理は、並べ替えと絞り込みのメニューが持つ)
const filterMenuRef = ref<InstanceType<typeof CaptureFilterMenu> | null>(null);
const activeFilterChips = computed(() => filterMenuRef.value?.activeFilterChips ?? []);

// 字幕のあるキャプチャが1枚でもあれば、タイルの下にセリフを出す (絵コンテのように場面を追えるように)
const hasCaptions = computed(() => captures.value.some(capture => capture.caption_text));

// 読み込みごとに増やす番号 (並べ替えを続けて変えたときに、最新の読み込みの応答だけを反映するため)
let loadGeneration = 0;

const load = async () => {
    loadGeneration++;
    const myGeneration = loadGeneration;
    isLoading.value = true;
    // 放送回の条件に、絞り込みの条件を重ねてサーバーで絞り込む
    const result = await Captures.fetchAllCaptures({ order: order.value, filter: { ...filter.value, ...viewFilter.value } });
    if (myGeneration !== loadGeneration) {
        return;
    }
    isLoading.value = false;
    isLoadFailed.value = result === null;
    if (result === null) {
        captures.value = [];
        return;
    }
    captures.value = result.captures;
    // 番組の情報は、ID で来たときは番組の API から、それ以外はキャプチャが参照する番組から取る
    let nextProgram: ICaptureProgram | null = result.programs[0] ?? null;
    if (route.params.capture_program_id !== undefined) {
        nextProgram = (await Captures.fetchProgram(Number(route.params.capture_program_id))) ?? nextProgram;
    }
    // キャプチャがまだ無い番組でも見出しに番組名や局ロゴを出せるよう、入口に応じて番組の情報を補う
    if (nextProgram === null) {
        nextProgram = await fetchFallbackProgram();
    }
    if (myGeneration === loadGeneration) {
        program.value = nextProgram;
    }
};

/**
 * キャプチャがまだ無いときに、見出しに出す番組の情報を入口に応じて取る
 * - 録画番組から来たとき: 録画番組の API から取る
 * - ライブの番組パネルから来たとき: 画面の移動と一緒に渡された番組の情報を使う
 * @returns 番組の情報 (取れなければ null)
 */
const fetchFallbackProgram = async (): Promise<ICaptureProgram | null> => {
    if (route.params.video_id !== undefined) {
        const video = await Videos.fetchVideo(Number(route.params.video_id));
        if (video === null) {
            return null;
        }
        return {
            id: 0,
            network_id: video.network_id ?? 0,
            service_id: video.service_id ?? 0,
            event_id: video.event_id ?? 0,
            start_time: video.start_time,
            end_time: video.end_time,
            duration: video.duration,
            title: video.title,
            description: video.description,
            channel: video.channel === null ? null : {
                id: video.channel.id,
                display_channel_id: video.channel.display_channel_id,
                name: video.channel.name,
                type: video.channel.type,
            },
            recorded_program_ids: [video.id],
        };
    }
    const hint = (window.history.state as { capture_program_hint?: ICaptureProgram } | null)?.capture_program_hint;
    return hint ?? null;
};
watch([order, () => JSON.stringify(viewFilter.value)], load);
// 別の番組へ移ったときは、選択と拡大表示を閉じて読み込み直す
// 並び順や絞り込みだけを変えたときは URL のクエリも変わるが、同じ番組のキャプチャなので選択は保ち、読み込み直しは並び順と絞り込みの watch に任せる
watch(() => JSON.stringify(filter.value), () => {
    selection.clear();
    openedCapture.value = null;
    void load();
});

const navigate = async (capture: ICapture, delta: 1 | -1) => {
    const index = captures.value.findIndex(item => item.id === capture.id);
    return captures.value[index + delta] ?? null;
};
// 拡大表示を閉じるときに、閉じた先のタイルが画面に見える位置までスクロールさせる (タイルへ縮んでいくアニメーションの行き先にするため)
const rootRef = ref<HTMLElement | null>(null);
const findTile = (capture: ICapture) => rootRef.value?.querySelector<HTMLElement>(`.capture-tile[data-capture-id="${capture.id}"]`) ?? null;
const reveal = async (capture: ICapture) => {
    findTile(capture)?.scrollIntoView({ block: 'nearest' });
};

// 拡大表示で前後へ送ったときは、表示していた1枚だけを選んでいる状態なら、タイムラインと同じく選択も送った先へ移す
const onLightboxCaptureChange = (capture: ICapture | null) => {
    const shown = openedCapture.value;
    if (capture !== null && shown !== null && selection.count.value === 1 && selection.isSelected(shown)) {
        selection.selectOnly(capture);
    }
    openedCapture.value = capture;
};

// キーボードショートカットの一覧 (／(？) キーで開く)
const isShortcutDialogOpen = ref(false);

// タイムラインと同じキーボード操作
// 上下の矢印キーでは、画面に並んでいるタイルの位置から、すぐ上か下の行で左右の位置が最も近いタイルへ移る
// 選んだタイルは縮めて表示しているので、位置は縮める前のレイアウトの位置 (グリッドの項目の offsetTop・offsetLeft) で比べる
const selectionBarRef = ref<InstanceType<typeof CaptureSelectionBar> | null>(null);
const getKeyboardTarget = async (capture: ICapture, direction: CaptureKeyboardDirection) => {
    const index = captures.value.findIndex(item => item.id === capture.id);
    if (index === -1) {
        return null;
    }
    if (direction === 'Left' || direction === 'Right') {
        return captures.value[index + (direction === 'Right' ? 1 : -1)] ?? null;
    }
    const findItem = (target: ICapture) => findTile(target)?.closest<HTMLElement>('.capture-program__item') ?? null;
    const current = findItem(capture);
    if (current === null) {
        return null;
    }
    const step = direction === 'Down' ? 1 : -1;
    let rowTop: number | null = null;
    let best: { capture: ICapture; distance: number } | null = null;
    for (let i = index + step; i >= 0 && i < captures.value.length; i += step) {
        const item = findItem(captures.value[i]);
        if (item === null || item.offsetTop === current.offsetTop) {
            continue;
        }
        // 最初に見つかった別の行だけを対象にする
        if (rowTop === null) {
            rowTop = item.offsetTop;
        } else if (item.offsetTop !== rowTop) {
            break;
        }
        const distance = Math.abs(item.offsetLeft - current.offsetLeft);
        if (best === null || distance < best.distance) {
            best = { capture: captures.value[i], distance };
        }
    }
    return best?.capture ?? null;
};
useCaptureKeyboard({
    selection,
    selectionBar: selectionBarRef,
    isLightboxOpen: () => openedCapture.value !== null,
    open: (capture) => {
        openedCapture.value = capture;
    },
    getTarget: getKeyboardTarget,
    getOrdered: () => captures.value,
    reveal,
    // 番組別の一覧は1つの放送回のキャプチャだけなので、全選択はこの一覧のキャプチャすべてにする
    getSelectAllTargets: () => captures.value,
});

// 削除したキャプチャは、取り直しを待たずに一覧から外す (取り直しの間に1枚表示が削除したキャプチャを隣として拾わないため)
// 選択からも外し、拡大表示で削除したキャプチャも、その後の一括の操作の対象から除く (タイムラインと同じ)
const onDeleted = (deletedIds: number[]) => {
    const ids = new Set(deletedIds);
    captures.value = captures.value.filter(capture => !ids.has(capture.id));
    selection.setMany([...selection.selected.value.values()].filter(capture => ids.has(capture.id)), false);
    void load();
};
const onUpdated = (updated: ICapture[]) => {
    const byId = new Map(updated.map(capture => [capture.id, capture]));
    captures.value = captures.value.map(capture => byId.get(capture.id) ?? capture);
    if (openedCapture.value !== null && byId.has(openedCapture.value.id)) {
        openedCapture.value = byId.get(openedCapture.value.id)!;
    }
    // 選択が持っている内容も、まだ選ばれているキャプチャの分だけ新しい状態に差し替える (タイムラインと同じ)
    // 拡大表示でお気に入りを変えて閉じたあとに F キーを押したとき、変えたあとの状態から切り替えるため
    selection.setMany(updated.filter(capture => selection.isSelected(capture)), true);
    // お気に入りやタグで絞り込んでいる一覧から外れたキャプチャがあれば、一覧を取り直す (タイムラインと同じ)
    const filterTagIds = viewFilter.value.tag_ids ?? [];
    for (const capture of updated) {
        const isUnfavorited = viewFilter.value.is_favorite === true && capture.is_favorite === false;
        const isUntagged = filterTagIds.some(id => capture.tag_ids?.includes(id) !== true);
        if (isUnfavorited || isUntagged) {
            void load();
            return;
        }
    }
};

onMounted(async () => {
    await userStore.fetchUser();
    await load();
});

</script>
<style lang="scss" scoped>

.capture-program {
    display: flex;
    flex-direction: column;
    flex-grow: 1;  // 空の状態の表示を見出しより下の領域の中央に配置するため、外枠を残りの高さいっぱいに広げる
    min-width: 0;

    &__intro {
        @include smartphone-vertical {
            position: relative;
            padding: 0px 8px;
        }
    }
    &__header {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        padding-top: 8px;
        // スマホの縦画面では、右端に重ねる並べ替えと絞り込みのボタンの分だけ、番組名を手前で折り返す
        &--with-toolbar {
            @include smartphone-vertical {
                padding-right: 40px;
            }
        }
    }
    &__back {
        display: flex;
        flex-shrink: 0;
        margin-left: -8px;
        padding: 6px;
        border-radius: 50%;
        cursor: pointer;
    }
    &__title {
        min-width: 0;
        font-size: 22px;
        font-weight: 700;
        line-height: 1.45;
        margin-top: 2px;
        @include smartphone-vertical {
            font-size: 18px;
        }
    }
    &__actions {
        display: flex;
        margin-top: 16px;
    }
    &__action {
        border-radius: 7px;
        letter-spacing: 0;
    }
    // PC では、番組の情報と並べ替えを横に並べ、並べ替えの下端を番組の情報の下端にそろえる
    &__body {
        display: flex;
        align-items: flex-end;
        gap: 24px;
        @include smartphone-vertical {
            flex-direction: column;
            align-items: stretch;
            gap: 0;
        }
    }
    &__meta {
        flex: 1;
        min-width: 0;
    }
    &__toolbar {
        display: flex;
        flex-shrink: 0;
        justify-content: flex-end;
        // スマホの縦画面では、番組名の1行目の右端に、戻るボタンと高さをそろえて重ねる
        @include smartphone-vertical {
            position: absolute;
            top: 6px;
            right: 8px;
        }
    }
    // 使っている絞り込みの条件のチップ (番組の情報の下に、折り返して並べる)
    &__active-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
        @include smartphone-vertical {
            padding: 0px 8px;
        }
    }
    &__active-filter {
        user-select: none;
    }

    &__grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 8px;
        margin-top: 20px;
        @include smartphone-vertical {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 6px 4px;
        }
        &--captions {
            row-gap: 12px;
        }
    }
    &__item {
        min-width: 0;
    }
    &__tile {
        aspect-ratio: 16 / 9;
    }
    &__caption {
        margin-top: 5px;
        padding: 0 2px;
        font-size: 12.5px;
        line-height: 1.45;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        @include smartphone-vertical {
            font-size: 11.5px;
        }
    }
}

</style>
