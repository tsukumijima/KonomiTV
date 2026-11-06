<template>
    <div ref="rootRef" class="capture-timeline" :style="{ height: `${domHeight}px` }">
        <!-- 見えている日の、見えている行のタイルだけを描画する -->
        <template v-for="section in visibleSections" :key="section.date">
            <div class="capture-timeline__header" :style="{ top: `${section.top - baseOffset}px` }">
                <div v-ripple class="capture-timeline__header-check"
                    :class="{'capture-timeline__header-check--visible': selection.isSelecting.value}"
                    @click="toggleDay(section)">
                    <Icon :icon="isDaySelected(section) ? 'fluent:checkmark-circle-24-filled' : 'fluent:circle-24-regular'"
                        width="22px" height="22px" />
                </div>
                <!-- 日付と枚数は文字の大きさが違うので、中央ではなく文字のベースラインでそろえる -->
                <span class="capture-timeline__header-label">
                    <span class="capture-timeline__header-date">{{ formatDate(section.date) }}</span>
                    <span class="capture-timeline__header-count">{{ section.count.toLocaleString() }}枚</span>
                </span>
            </div>
            <!-- 読み込めなかった日は、読み込み中の灰色の枠の代わりに、読み込めなかったことと再読み込みのボタンをタイルの領域に表示する -->
            <div v-if="failedDays.has(section.date)" class="capture-timeline__failed"
                :style="{ top: `${section.top + HEADER_HEIGHT - baseOffset}px`, height: `${section.height - HEADER_HEIGHT - SECTION_GAP}px` }">
                <div class="capture-timeline__failed-content">
                    <div class="capture-timeline__failed-message">この日のキャプチャを読み込めませんでした。</div>
                    <v-btn class="mt-3 px-4" color="secondary" variant="flat" height="40" @click="retryDay(section.date)">
                        <Icon icon="fluent:arrow-clockwise-16-filled" width="18px" height="18px" />
                        <span class="ml-1">再読み込み</span>
                    </v-btn>
                </div>
            </div>
            <template v-else>
                <template v-for="tile in visibleTiles(section)" :key="tile.key">
                    <div class="capture-timeline__tile" :style="tile.style">
                        <CaptureTile v-if="tile.capture" :capture="tile.capture"
                            :selected="selection.isSelected(tile.capture)"
                            :cursor="selection.isCursor(tile.capture)"
                            :previewed="selection.isPreviewed(tile.capture)"
                            :selecting="selection.isSelecting.value"
                            @open="$emit('open', tile.capture)"
                            @toggle="(shiftKey) => onToggle(tile.capture!, shiftKey)"
                            @updated="$emit('updated', $event)" />
                        <div v-else class="capture-timeline__placeholder"></div>
                    </div>
                </template>
            </template>
        </template>
    </div>
    <CaptureScrubber v-if="sections.length > 0"
        :marks="scrubberMarks"
        :content-height="totalHeight"
        :scroll-offset="scrollOffset"
        :viewport-height="viewportHeight"
        :label-at="labelAt"
        @scroll-to="scrollToContentY" />
</template>
<script lang="ts" setup>

import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';

import CaptureScrubber, { IScrubberMark } from '@/components/Captures/CaptureScrubber.vue';
import { CaptureSelection, useCaptureRangePreview } from '@/components/Captures/CaptureSelection';
import CaptureTile from '@/components/Captures/CaptureTile.vue';
import Captures, { CaptureTimelineAxis, ICapture, ICaptureFilter, ICaptureProgram } from '@/services/Captures';
import { dayjs } from '@/utils';


/** 日付ごとのまとまり (見出しとタイルの位置を含む) */
interface ITimelineSection {
    date: string;
    count: number;
    top: number;
    height: number;
}

const props = defineProps<{
    filter: ICaptureFilter;
    axis: CaptureTimelineAxis;
    dayStartHour: number;
    selection: CaptureSelection;
}>();

const emit = defineEmits<{
    (event: 'open', capture: ICapture): void;
    // 絞り込みや並べ方が変わり、別の条件の一覧を読み込み始めたとき
    (event: 'reloading'): void;
    // タイルのお気に入りのボタンで、キャプチャの状態が変わったとき
    (event: 'updated', capture: ICapture): void;
    // 読み込めなかったときは null を渡す (0件と区別して、読み込めなかったことを伝えるため)
    (event: 'loaded', total: number | null): void;
}>();

// 見出しの高さ・タイルの間隔・タイルの最小の幅 (px)
const HEADER_HEIGHT = 48;
const SECTION_GAP = 14;
// 画面の上端から、固定のヘッダーに隠れずに見え始める位置までの高さ (px)
const REVEAL_TOP_MARGIN = 72;
// 画面の下端から、複数選択中の下部のバーに隠れずに見える位置までの高さ (px)
const REVEAL_BOTTOM_MARGIN = 96;
// 読み込んだキャプチャを持っておく、画面の上下それぞれの画面数 (これより離れた日のキャプチャは手放し、近づいたら読み込み直す)
const KEEP_LOADED_SCREENS = 10;
// ブラウザが扱える要素の高さには上限 (Chrome では約 3,355 万 px) があり、百万枚規模ではそれを超える
// そのため要素の高さはこの値までにとどめ、要素の上端に当たるタイムラインの位置 (baseOffset) をずらしながら、その範囲だけを描画する
// macOS の Chrome では、画面の倍率が 2 のときに要素の上端から約 420 万 px (約 840 万デバイスピクセル) より下に置いたタイルが描画されないため、
// 倍率が 3 の端末でもその範囲に収まる 200 万 px までにとどめる
const MAX_DOM_HEIGHT = 2_000_000;
const rootRef = ref<HTMLElement | null>(null);
const containerWidth = ref(0);
const viewportHeight = ref(window.innerHeight);
const scrollOffset = ref(0);  // タイムラインの先頭から見た、画面の上端の位置
const baseOffset = ref(0);  // 要素の上端に当たる、タイムラインの先頭からの位置

// 日付ごとの件数と、読み込んだ日のキャプチャ
const sections = shallowRef<ITimelineSection[]>([]);
const loadedDays = shallowRef(new Map<string, ICapture[]>());
// 日の読み込みの結果 (Queued は、同時に読み込める数の上限で順番待ちになったことを、
// Canceled は、読み込みの途中でその日が見えなくなり、見えている日に順番を譲って打ち切ったことを表す)
type DayLoadResult = 'Loaded' | 'Queued' | 'Canceled' | 'Failed';
// 読み込み中の日と、その読み込みの完了 (同じ日を待つ呼び出しで完了を共有する)
// 絞り込みを変えたあとの読み込みを、変える前の読み込みと分けるため、世代と日付の組で持つ
const loadingDays = new Map<string, Promise<DayLoadResult>>();
const programs = new Map<number, ICaptureProgram>();
let generation = 0;  // 絞り込みが変わるたびに増やし、古い読み込みの結果を捨てる

// 画面の幅から、列の数とタイルの大きさを決める (キャプチャは 16:9 なので高さ合わせのレイアウトは要らない)
const grid = computed(() => {
    const width = Math.max(containerWidth.value, 200);
    const isNarrow = width < 600;
    const gap = isNarrow ? 3 : 5;
    const minTileWidth = isNarrow ? 150 : 200;
    const columns = Math.max(2, Math.floor((width + gap) / (minTileWidth + gap)));
    const tileWidth = (width - gap * (columns - 1)) / columns;
    const tileHeight = Math.round(tileWidth * 9 / 16);
    return { gap, columns, tileWidth, tileHeight, rowHeight: tileHeight + gap };
});

// 日付ごとの件数から、各日の見出しとタイルの位置を計算する
const layout = () => {
    const { columns, rowHeight } = grid.value;
    let top = 0;
    sections.value = sections.value.map((section) => {
        const rows = Math.ceil(section.count / columns);
        const laid = { ...section, top, height: HEADER_HEIGHT + rows * rowHeight + SECTION_GAP };
        top += laid.height;
        return laid;
    });
};
const totalHeight = computed(() => {
    const last = sections.value[sections.value.length - 1];
    return last ? last.top + last.height : 0;
});
const domHeight = computed(() => Math.min(totalHeight.value, MAX_DOM_HEIGHT));

// 日付から、日付ごとのまとまりの並びの中の位置を引く (範囲選択や、読み込んだ日を手放すときに使う)
const sectionIndexByDate = computed(() => {
    const result = new Map<string, number>();
    sections.value.forEach((section, index) => result.set(section.date, index));
    return result;
});

// 画面の回転やウインドウの幅の変更で列の数やタイルの大きさが変わったときは、レイアウトし直したあとも、
// 変更の前に画面の上端にあった日と、その日の中で上端にあったタイルの行を、画面の上端に保つ
// ページのスクロール位置を px のまま保つと、各日の高さが変わった分だけ、見ていた日付から大きくずれるため
watch(grid, async (next, previous) => {
    const root = rootRef.value;

    // 一覧が空のときや、戻る操作でスクロール位置を戻している間は、位置を合わせずにレイアウトだけをし直す
    if (root === null || sections.value.length === 0 || restoringScrollUntil !== null) {
        layout();
        return;
    }

    // タイムラインの先頭より上 (見出しの部分) を見ているときは、レイアウトし直しても上端の位置は変わらない
    const contentY = baseOffset.value - root.getBoundingClientRect().top;
    if (contentY <= 0) {
        layout();
        return;
    }

    // 画面の上端にある日と、その日の中の位置を覚えておく
    // タイルの部分を見ているときは、上端の行の最初のタイルの番号と、行の中のどこまで見えなくなっているかの割合で覚える
    const index = findSectionIndex(contentY);
    const offsetInSection = contentY - sections.value[index].top;
    const tileOffset = offsetInSection - HEADER_HEIGHT;
    const firstTileIndex = Math.floor(tileOffset / previous.rowHeight) * previous.columns;
    const rowFraction = (tileOffset % previous.rowHeight) / previous.rowHeight;

    // 新しい列の数でレイアウトし直し、覚えておいたタイルの行が今どこにあるかを求める
    layout();
    const section = sections.value[index];
    let nextOffsetInSection = offsetInSection;
    if (tileOffset > 0) {
        nextOffsetInSection = HEADER_HEIGHT + (Math.floor(firstTileIndex / next.columns) + rowFraction) * next.rowHeight;
    }
    const nextContentY = section.top + Math.min(nextOffsetInSection, section.height);

    // 移る先が要素の範囲の真ん中に来るよう要素の上端に当たる位置をずらし、新しい高さで描画されてからページをスクロールする
    // 描画される前にスクロールすると、ブラウザが変更前の要素の高さの範囲にスクロール位置を収めてしまうため
    baseOffset.value = centerBaseOffset(nextContentY);
    await nextTick();
    const rootTop = root.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: rootTop + nextContentY - baseOffset.value, behavior: 'instant' });
    onScroll();
});

// 全体の高さが変わったら (絞り込みや画面の幅の変更)、要素の範囲がタイムラインの外へはみ出さないようにずらす位置を収める
watch(totalHeight, (height) => {
    baseOffset.value = Math.min(baseOffset.value, Math.max(height - MAX_DOM_HEIGHT, 0));
});

// 要素の高さの上限を超える長いタイムラインでは、履歴に残るページのスクロール位置だけでは見ていた場所に戻れないので、ずらした位置も今の履歴に書いておく
// 戻る操作で戻ったときは、最初に読み込み終えたところでこの位置に戻し、Vue Router が戻すページのスクロール位置と合わせる
const savedBaseOffset: unknown = window.history.state?.capture_timeline_base_offset;
let restoringBaseOffset = typeof savedBaseOffset === 'number' ? savedBaseOffset : null;
// Vue Router がページのスクロール位置を戻し終えるまで、ずらす位置を保つ期限 (Vue Router は最大3秒待つので、少し長めにとる)
let restoringScrollUntil: number | null = null;
watch(baseOffset, (value) => {
    window.history.replaceState({ ...window.history.state, capture_timeline_base_offset: value }, '');
});

/**
 * タイムラインの位置が要素の範囲の真ん中に来るよう、要素の上端に当たる位置を決める
 * @param contentY タイムラインの先頭からの位置
 * @returns 要素の上端に当たる位置
 */
const centerBaseOffset = (contentY: number) => {
    return Math.min(Math.max(contentY - MAX_DOM_HEIGHT / 2, 0), Math.max(totalHeight.value - MAX_DOM_HEIGHT, 0));
};

// 位置から日を引く二分探索
const findSectionIndex = (y: number) => {
    const list = sections.value;
    let low = 0;
    let high = list.length - 1;
    while (low < high) {
        const mid = (low + high + 1) >> 1;
        if (list[mid].top <= y) {
            low = mid;
        } else {
            high = mid - 1;
        }
    }
    return low;
};

// 画面の上下に1画面ぶんの余裕を持たせた範囲を描画する
const visibleRange = computed(() => {
    const margin = viewportHeight.value;
    return { top: scrollOffset.value - margin, bottom: scrollOffset.value + viewportHeight.value + margin };
});
const visibleSections = computed(() => {
    if (sections.value.length === 0) {
        return [];
    }
    const { top, bottom } = visibleRange.value;
    const result: ITimelineSection[] = [];
    for (let index = findSectionIndex(Math.max(top, 0)); index < sections.value.length; index++) {
        const section = sections.value[index];
        if (section.top > bottom) {
            break;
        }
        result.push(section);
    }
    return result;
});

// 見えている日のうち、読み込んでいない日を読み込む
// 読み込めなかった日は、スクロールのたびに取り直してエラーを出し続けないよう、少し間を空けてから読み直す
// (すぐに読み直したいときは、その日の位置に表示する再読み込みのボタンから読み直せる)
watch(visibleSections, (list) => {
    for (const section of list) {
        const failedAt = failedDays.value.get(section.date);
        if (failedAt !== undefined && performance.now() - failedAt < 10 * 1000) {
            continue;
        }
        void loadDay(section.date);
    }

    // 範囲選択の起点の日から、キーボードで動かしているカーソルの日までは、Shift キーでの範囲選択に使うので持っておく
    let pinnedFrom = Infinity;
    let pinnedTo = -Infinity;
    for (const capture of [props.selection.anchor.value, props.selection.getCursor()]) {
        if (capture === null) {
            continue;
        }
        const date = dateOf(capture);
        const index = date === null ? undefined : sectionIndexByDate.value.get(date);
        if (index !== undefined) {
            pinnedFrom = Math.min(pinnedFrom, index);
            pinnedTo = Math.max(pinnedTo, index);
        }
    }

    // 画面から十分に離れた日のキャプチャは手放し、長くスクロールしても持っているキャプチャが一定の量に収まるようにする
    // 手放した日は、また近づいたときや、拡大表示やキーボードでその日へ移るときに読み込み直す
    const keepMargin = viewportHeight.value * KEEP_LOADED_SCREENS;
    const keepTop = scrollOffset.value - keepMargin;
    const keepBottom = scrollOffset.value + viewportHeight.value + keepMargin;
    let next: Map<string, ICapture[]> | null = null;
    for (const date of loadedDays.value.keys()) {
        const index = sectionIndexByDate.value.get(date);
        if (index !== undefined) {
            const section = sections.value[index];
            const isNear = section.top + section.height >= keepTop && section.top <= keepBottom;
            const isPinned = pinnedFrom <= index && index <= pinnedTo;
            if (isNear || isPinned) {
                continue;
            }
        }
        if (next === null) {
            next = new Map(loadedDays.value);
        }
        next.delete(date);
    }
    if (next === null) {
        return;
    }
    loadedDays.value = next;

    // 手放した日のキャプチャだけが参照していた番組の情報も手放す
    const usedProgramIds = new Set<number>();
    for (const captures of next.values()) {
        for (const capture of captures) {
            if (capture.capture_program_id !== null) {
                usedProgramIds.add(capture.capture_program_id);
            }
        }
    }
    for (const programId of programs.keys()) {
        if (usedProgramIds.has(programId) === false) {
            programs.delete(programId);
        }
    }
});

// 日の中で、見えている行のタイルだけを返す (1日に数百枚ある日でも、描画する要素を抑える)
const visibleTiles = (section: ITimelineSection) => {
    const { columns, tileWidth, tileHeight, rowHeight, gap } = grid.value;
    const { top, bottom } = visibleRange.value;
    const firstRow = Math.max(0, Math.floor((top - section.top - HEADER_HEIGHT) / rowHeight));
    const lastRow = Math.min(Math.ceil(section.count / columns) - 1, Math.floor((bottom - section.top - HEADER_HEIGHT) / rowHeight));
    const captures = loadedDays.value.get(section.date);
    const tiles: { key: string; capture: ICapture | null; style: Record<string, string> }[] = [];
    for (let row = firstRow; row <= lastRow; row++) {
        for (let column = 0; column < columns; column++) {
            const index = row * columns + column;
            if (index >= section.count) {
                break;
            }
            const capture = captures?.[index] ?? null;
            // 件数の集計と読み込んだ件数がずれた (読み込みの間に増減した) ときは、読み込めたキャプチャの枠だけを出す
            if (captures !== undefined && capture === null) {
                continue;
            }
            tiles.push({
                key: capture ? `c${capture.id}` : `${section.date}-${index}`,
                capture,
                style: {
                    top: `${section.top + HEADER_HEIGHT + row * rowHeight - baseOffset.value}px`,
                    left: `${column * (tileWidth + gap)}px`,
                    width: `${tileWidth}px`,
                    height: `${tileHeight}px`,
                },
            });
        }
    }
    return tiles;
};

// 1日分のキャプチャを読み込む (同時に読み込むのは2日まで)
let activeLoads = 0;
// 今の絞り込みで読み込めなかった日と、その時刻 (画面に読み込めなかったことを表示するため、変更を画面に反映する)
const failedDays = shallowRef(new Map<string, number>());
const pendingDays: string[] = [];
// 拡大表示の前後の移動やキーボードでの移動で、読み終わるのを待っている日
// 見えていなくても、読み込みを打ち切らずに最後のページまで読み込む
const requiredDays = new Set<string>();
const loadDay = (date: string): Promise<DayLoadResult> => {
    if (loadedDays.value.has(date)) {
        return Promise.resolve('Loaded');
    }
    const myGeneration = generation;
    const loadingKey = `${myGeneration}:${date}`;
    const loading = loadingDays.get(loadingKey);
    if (loading !== undefined) {
        return loading;
    }
    if (activeLoads >= 2) {
        if (!pendingDays.includes(date)) {
            pendingDays.push(date);
        }
        return Promise.resolve('Queued');
    }
    const promise = (async (): Promise<DayLoadResult> => {
        activeLoads++;
        try {
            // 1日分のキャプチャを、カーソルをたどって最後のページまで読み込む
            // 1日に数千枚ある日は何ページにも分かれるので、ページごとにその日がまだ必要かを確認し、
            // スクラバーで遠くへ移ったあとは、見えなくなった日の続きのページを読まずに、移った先の日に順番を譲る
            const captures: ICapture[] = [];
            const dayPrograms: ICaptureProgram[] = [];
            let cursor: string | null = null;
            do {
                const isVisible = visibleSections.value.some(section => section.date === date);
                if (isVisible === false && requiredDays.has(date) === false) {
                    return 'Canceled';
                }
                const page = await Captures.fetchCaptures({
                    order: props.axis === 'CapturedAt' ? 'CapturedAtDesc' : 'BroadcastAtDesc',
                    cursor,
                    limit: 200,
                    date,
                    day_start_hour: props.dayStartHour,
                    filter: props.filter,
                });
                if (myGeneration !== generation) {
                    return 'Failed';
                }
                // 読み込めなかった日は、画面に読み込めなかったことと再読み込みのボタンを表示する
                if (page === null) {
                    failedDays.value = new Map(failedDays.value).set(date, performance.now());
                    return 'Failed';
                }
                captures.push(...page.captures);
                dayPrograms.push(...page.programs);
                cursor = page.next_cursor;
            } while (cursor !== null);

            // 読み込めた日は、読み込めなかった記録を消し、キャプチャと番組の情報を画面に反映する
            if (failedDays.value.has(date)) {
                const nextFailedDays = new Map(failedDays.value);
                nextFailedDays.delete(date);
                failedDays.value = nextFailedDays;
            }
            for (const program of dayPrograms) {
                programs.set(program.id, program);
            }
            const next = new Map(loadedDays.value);
            next.set(date, captures);
            loadedDays.value = next;
            return 'Loaded';
        } finally {
            loadingDays.delete(loadingKey);
            activeLoads--;
            // 待っている日のうち、まだ見えている日から読み込む
            const visible = new Set(visibleSections.value.map(section => section.date));
            while (pendingDays.length > 0) {
                const nextDate = pendingDays.shift()!;
                if (visible.has(nextDate)) {
                    void loadDay(nextDate);
                    break;
                }
            }
        }
    })();
    loadingDays.set(loadingKey, promise);
    return promise;
};

/**
 * 読み込めなかった日を、すぐに読み込み直す (その日の位置に表示する再読み込みのボタン)
 * @param date 日付 (YYYY-MM-DD)
 */
const retryDay = (date: string) => {
    const next = new Map(failedDays.value);
    next.delete(date);
    failedDays.value = next;
    void loadDay(date);
};

// 取り直している日付ごとの件数 (拡大表示の前後の移動で、取り直し終わるのを待つため)
let reloadingSections: Promise<unknown> | null = null;

// 日付ごとの件数を取り直して、読み込んだ日を捨てて描画し直す (要素の範囲をずらした位置は保つ)
const reload = async () => {
    generation++;
    const myGeneration = generation;
    loadedDays.value = new Map();
    failedDays.value = new Map();
    pendingDays.length = 0;
    const request = Captures.fetchSections({ axis: props.axis, day_start_hour: props.dayStartHour, filter: props.filter });
    reloadingSections = request;
    const result = await request;
    if (myGeneration !== generation) {
        return;
    }
    reloadingSections = null;
    sections.value = (result?.sections ?? []).map(section => ({ ...section, top: 0, height: 0 }));
    layout();
    emit('loaded', result === null ? null : result.total);
    if (restoringBaseOffset !== null) {
        baseOffset.value = Math.min(restoringBaseOffset, Math.max(totalHeight.value - domHeight.value, 0));
        restoringBaseOffset = null;
        restoringScrollUntil = performance.now() + 4000;
    }
    updateViewport();
};
// 絞り込みや並べ方が変わったときは、先頭から見直す
// 削除やスキャンの完了で読み直すときは、見ている場所を保つよう、要素の範囲をずらした位置はそのまま使う
// 1枚表示を閉じて同じ URL へ戻ると、絞り込みは同じ値の新しいオブジェクトになるので、値を比べて変わったときだけ先頭へ戻す
// 前の条件の日付と件数は新しい条件の結果と食い違うので、日付ごとの件数が届くまで待たずにすぐ消す
watch(() => JSON.stringify([props.filter, props.axis, props.dayStartHour]), () => {
    baseOffset.value = 0;
    sections.value = [];
    layout();
    window.scrollTo({ top: 0 });
    emit('reloading');
    void reload();
});

// スクロールと画面の大きさの変化を追う
let frame: number | null = null;
const updateViewport = () => {
    frame = null;
    if (rootRef.value === null) {
        return;
    }
    const domScrollOffset = -rootRef.value.getBoundingClientRect().top;
    let contentY = baseOffset.value + domScrollOffset;

    // 戻る操作で戻ったばかりで、Vue Router がまだページのスクロール位置を戻していない間は、ずらす位置をそのまま保つ
    if (restoringScrollUntil !== null && (window.scrollY > 0 || performance.now() > restoringScrollUntil)) {
        restoringScrollUntil = null;
    }
    if (restoringScrollUntil !== null) {
        scrollOffset.value = contentY;
        viewportHeight.value = window.innerHeight;
        return;
    }

    // ページの先頭や末尾まで一気にスクロールしたとき (Home・End キーや、スマホで画面の上端をタップしたとき) は、タイムラインの先頭や末尾を出す
    const isAtPageTop = window.scrollY <= 0;
    const isAtPageBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1;
    // 要素の範囲の端の4分の1まで来たら、今の位置が範囲の真ん中に来るようにずらし、同じ量だけページのスクロールを戻す
    // 描画する位置も同じ量だけずれるので見た目は動かず、そのままスクロールを続けられる (ずらすのは数十万 px スクロールするごとに1回だけ)
    const edgeMargin = MAX_DOM_HEIGHT / 4;
    const isNearTop = domScrollOffset < edgeMargin && baseOffset.value > 0;
    const isNearBottom = domScrollOffset > domHeight.value - edgeMargin && baseOffset.value + domHeight.value < totalHeight.value;
    if (isAtPageTop && baseOffset.value > 0) {
        baseOffset.value = 0;
        contentY = domScrollOffset;
    } else if (isAtPageBottom && isNearBottom) {
        baseOffset.value = totalHeight.value - domHeight.value;
        contentY = baseOffset.value + domScrollOffset;
    } else if (isNearTop || isNearBottom) {
        const nextBaseOffset = centerBaseOffset(contentY);
        const delta = nextBaseOffset - baseOffset.value;
        if (delta !== 0) {
            baseOffset.value = nextBaseOffset;
            window.scrollBy({ top: -delta, behavior: 'instant' });
        }
    }

    scrollOffset.value = contentY;
    viewportHeight.value = window.innerHeight;
};
const onScroll = () => {
    if (frame === null) {
        frame = window.requestAnimationFrame(updateViewport);
    }
};
let resizeObserver: ResizeObserver | null = null;
onMounted(() => {
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    resizeObserver = new ResizeObserver((entries) => {
        containerWidth.value = entries[0].contentRect.width;
        onScroll();
    });
    if (rootRef.value !== null) {
        resizeObserver.observe(rootRef.value);
        containerWidth.value = rootRef.value.clientWidth;
    }
    // ログインが必要な画面との行き来で作り直されたときも、読み込み終えるまで前の一覧の件数を出さずに読み込み中にする
    emit('reloading');
    void reload();
});
onBeforeUnmount(() => {
    window.removeEventListener('scroll', onScroll);
    window.removeEventListener('resize', onScroll);
    resizeObserver?.disconnect();
});

// スクラバーの目盛り (年と月の始まり)
const scrubberMarks = computed<IScrubberMark[]>(() => {
    const marks: IScrubberMark[] = [];
    let lastMonth = '';
    for (const section of sections.value) {
        const month = section.date.slice(0, 7);
        if (month !== lastMonth) {
            marks.push({ y: section.top, year: Number(month.slice(0, 4)), month: Number(month.slice(5, 7)), isYearStart: month.slice(0, 4) !== lastMonth.slice(0, 4) });
            lastMonth = month;
        }
    }
    return marks;
});
const labelAt = (y: number) => {
    if (sections.value.length === 0) {
        return '';
    }
    // 日付だけの文字列はブラウザのタイムゾーンの0時として解釈されるので、日本時間の0時として解釈させる
    const date = dayjs(`${sections.value[findSectionIndex(y)].date}T00:00:00+09:00`);
    return date.format('YYYY年M月');
};
const scrollToContentY = (y: number) => {
    if (rootRef.value === null) {
        return;
    }
    const rootTop = rootRef.value.getBoundingClientRect().top + window.scrollY;
    // 移る先が要素の範囲の真ん中に来るよう、先に要素の上端に当たる位置をずらしてから、ページをスクロールする
    baseOffset.value = centerBaseOffset(y);
    // 固定ヘッダーの下に日の見出しが来るよう、少しだけ手前に合わせる
    window.scrollTo({ top: Math.max(0, rootTop + y - baseOffset.value - REVEAL_TOP_MARGIN) });
    // ずらしたあとのページのスクロール位置が前と同じでもスクロールのイベントは届かないので、描画する範囲を取り直す
    onScroll();
};

// 日の見出しの「この日をすべて選択」
const isDaySelected = (section: ITimelineSection) => {
    const captures = loadedDays.value.get(section.date);
    return captures !== undefined && captures.length > 0 && captures.every(capture => props.selection.isSelected(capture));
};
const toggleDay = (section: ITimelineSection) => {
    const captures = loadedDays.value.get(section.date);
    if (captures !== undefined) {
        props.selection.setMany(captures, !isDaySelected(section));
    }
};

// Shift キーを押しての範囲選択には、読み込んだ日を画面の並び順につないだものを渡す
const orderedLoaded = () => {
    const result: ICapture[] = [];
    for (const section of sections.value) {
        const captures = loadedDays.value.get(section.date);
        if (captures !== undefined) {
            result.push(...captures);
        }
    }
    return result;
};
useCaptureRangePreview(props.selection, orderedLoaded);

/**
 * タイルの選択を切り替える (Shift キーを押しているときは、範囲選択の起点からこのキャプチャまでをまとめて選ぶ)
 * スクラバーで遠くへ移ったあとのように、起点との間に読み込んでいない日があるときは、間の期間のキャプチャを取得してから選ぶ
 * 日ごとに読み込むと、数か月分の範囲では日の数だけリクエストを送ることになるので、一覧の API の期間の絞り込みとカーソルで、ページ単位にまとめて取得する
 * @param capture 選択を切り替えるキャプチャ
 * @param shiftKey Shift キーを押していたかどうか
 */
const onToggle = async (capture: ICapture, shiftKey: boolean) => {
    const anchor = props.selection.anchor.value;
    if (shiftKey === false || anchor === null) {
        props.selection.toggle(capture, shiftKey ? orderedLoaded() : null);
        return;
    }

    // 起点の日と、このキャプチャの日の並びの中の位置を求める
    const anchorDate = dateOf(anchor);
    const captureDate = dateOf(capture);
    const anchorIndex = anchorDate === null ? undefined : sectionIndexByDate.value.get(anchorDate);
    const captureIndex = captureDate === null ? undefined : sectionIndexByDate.value.get(captureDate);
    if (anchorIndex === undefined || captureIndex === undefined) {
        props.selection.toggle(capture, orderedLoaded());
        return;
    }

    // 間の日をすべて読み込んでいれば、読み込んだ日をつないだ並びでそのまま選ぶ
    const fromIndex = Math.min(anchorIndex, captureIndex);
    const toIndex = Math.max(anchorIndex, captureIndex);
    let hasUnloadedDay = false;
    for (let index = fromIndex; index <= toIndex; index++) {
        if (loadedDays.value.has(sections.value[index].date) === false) {
            hasUnloadedDay = true;
            break;
        }
    }
    if (hasUnloadedDay === false) {
        props.selection.toggle(capture, orderedLoaded());
        return;
    }

    // 読み込んでいない日があれば、起点の日からこのキャプチャの日までの期間のキャプチャを、日の読み込みと同じ並び順で取得する
    // 日は新しい順に並ぶので、並びの後ろの日が期間の開始日、前の日が終了日になる
    // 期間は今の絞り込みで表示している日の中にあるので、絞り込みの期間をこの期間で置き換えても、表示中の条件の中から選べる
    const myGeneration = generation;
    const result = await Captures.fetchAllCaptures({
        order: props.axis === 'CapturedAt' ? 'CapturedAtDesc' : 'BroadcastAtDesc',
        day_start_hour: props.dayStartHour,
        filter: { ...props.filter, start_date: sections.value[toIndex].date, end_date: sections.value[fromIndex].date },
    });

    // 取得している間に絞り込みが変わったり、選択を解除・変更したりしたときは、押した時点の範囲を選ばずに終える
    if (result === null || myGeneration !== generation || props.selection.anchor.value?.id !== anchor.id) {
        return;
    }
    props.selection.toggle(capture, result.captures);
};

const formatDate = (date: string) => {
    // 日付だけの文字列はブラウザのタイムゾーンの0時として解釈されるので、日本時間の0時として解釈させる
    const value = dayjs(`${date}T00:00:00+09:00`);
    return value.year() === dayjs().year() ? value.format('M月D日 (dd)') : value.format('YYYY年M月D日 (dd)');
};

/**
 * 日の読み込みを始め、読み終わったその日のキャプチャを返す
 * 読み込みに時間がかかっても終わるまで待ち、読み込み中を0件と取り違えて端に着いたと判定するのを防ぐ
 * @param date 日付 (YYYY-MM-DD)
 * @returns その日のキャプチャ (読み込めなかったときは undefined)
 */
const waitForDay = async (date: string) => {
    // 待っている間は、見えていない日でも読み込みを打ち切らずに最後まで読み込む
    // 順番待ちになった日は、画面に見えていないと読み込まずに外されるので、空きができ次第この日の読み込みを始めるよう呼び直す
    // 待ち始める前に見えなくなって打ち切られた読み込みも、同じように読み込み直す
    requiredDays.add(date);
    let result: DayLoadResult;
    try {
        result = await loadDay(date);
        while (result === 'Queued' || result === 'Canceled') {
            await new Promise(resolve => setTimeout(resolve, 100));
            // 同じ日を待っていたほかの呼び出しが先に待ち終えて外していても、この呼び出しが待っている間は読み込み続ける
            requiredDays.add(date);
            result = await loadDay(date);
        }
    } finally {
        requiredDays.delete(date);
    }
    // 読み込めなかった日は、端に着いたのではなく分からないだけなので、次に送るときに読み直せるよう undefined を返す
    if (result === 'Failed') {
        return undefined;
    }
    return loadedDays.value.get(date) ?? [];
};

/**
 * キャプチャが並んでいる日を、タイムラインの日付の軸の日時から求める
 * @param capture キャプチャ
 * @returns 日付 (YYYY-MM-DD 、日時がないときは null)
 */
const dateOf = (capture: ICapture) => {
    const time = props.axis === 'CapturedAt' ? capture.captured_at : capture.broadcast_at;
    if (time === null) {
        return null;
    }
    return dayjs(time).subtract(props.dayStartHour, 'hour').format('YYYY-MM-DD');
};

/**
 * 拡大表示の前後の移動に使う、隣のキャプチャを返す
 * 日の境目では隣の日を読み込んでから返すので、拡大表示のまま日をまたいで送れる
 * 削除やお気に入りから外したことで一覧から外れたキャプチャからも、並びの上で隣にあるキャプチャへ送れる
 * @param capture 今のキャプチャ
 * @param delta 1 なら次 (古い方)、-1 なら前 (新しい方)
 * @returns 隣のキャプチャ (端なら null、隣の日を読み込めず分からないときは undefined)
 */
const getNeighbor = async (capture: ICapture, delta: 1 | -1): Promise<ICapture | null | undefined> => {

    // 隣の日の、送る向きの端のキャプチャを返す
    const getEdgeOfDay = async (section: ITimelineSection | undefined) => {
        if (section === undefined) {
            return null;
        }
        const captures = await waitForDay(section.date);
        if (captures === undefined) {
            return undefined;
        }
        return (delta === 1 ? captures[0] : captures[captures.length - 1]) ?? null;
    };

    // 削除やお気に入りから外したことで一覧を取り直している間は、日付ごとの件数を取り直し終わるまで待つ
    if (reloadingSections !== null) {
        await reloadingSections;
    }

    // 今のキャプチャがある日を、タイムラインの日付の軸の日時から求める
    const timeOf = (item: ICapture) => props.axis === 'CapturedAt' ? item.captured_at : item.broadcast_at;
    const time = timeOf(capture);
    const date = dateOf(capture);
    if (time === null || date === null) {
        return null;
    }

    // その日ごと一覧から外れたときは、送る向きにある一番近い日の端から返す (日は新しい順に並ぶ)
    const index = sections.value.findIndex(section => section.date === date);
    if (index === -1) {
        if (delta === 1) {
            return getEdgeOfDay(sections.value.find(section => section.date < date));
        }
        return getEdgeOfDay(sections.value.findLast(section => section.date > date));
    }

    // 今のキャプチャの隣を返す
    const captures = await waitForDay(date);
    if (captures === undefined) {
        return undefined;
    }
    const position = captures.findIndex(item => item.id === capture.id);
    if (position !== -1) {
        if (captures[position + delta] !== undefined) {
            return captures[position + delta];
        }
        return getEdgeOfDay(sections.value[index + delta]);
    }

    // 今のキャプチャが一覧から外れたときは、並び (日時の新しい順、同じ日時は ID の大きい順) の上で隣にあるキャプチャを返す
    const isOlder = (item: ICapture) => {
        const itemTime = dayjs(timeOf(item)).valueOf();
        const currentTime = dayjs(time).valueOf();
        if (itemTime !== currentTime) {
            return itemTime < currentTime;
        }
        return item.id < capture.id;
    };
    const olderIndex = captures.findIndex(isOlder);
    const neighborIndex = delta === 1 ? olderIndex : (olderIndex === -1 ? captures.length : olderIndex) - 1;
    if (neighborIndex >= 0 && captures[neighborIndex] !== undefined) {
        return captures[neighborIndex];
    }
    return getEdgeOfDay(sections.value[index + delta]);
};

/**
 * 矢印キーで移動する先のキャプチャを返す (エクスプローラーや Finder のサムネイル表示と同じ動き)
 * 左右は並びの前後へ、上下は同じ列の上下の行へ移り、日の境目では隣の日の同じ列へ移る
 * @param capture 今のキャプチャ
 * @param direction 矢印キーの向き
 * @returns 移動先のキャプチャ (端なら null、隣の日を読み込めず分からないときは undefined)
 */
const getKeyboardTarget = async (capture: ICapture, direction: 'Left' | 'Right' | 'Up' | 'Down'): Promise<ICapture | null | undefined> => {

    // 左右は、拡大表示の前後の移動と同じく並びの前後へ移る
    if (direction === 'Left' || direction === 'Right') {
        return getNeighbor(capture, direction === 'Right' ? 1 : -1);
    }

    // 今のキャプチャがある日と、その日の中での位置を求める
    const date = dateOf(capture);
    const index = sections.value.findIndex(section => section.date === date);
    if (date === null || index === -1) {
        return null;
    }
    const captures = await waitForDay(date);
    if (captures === undefined) {
        return undefined;
    }
    const position = captures.findIndex(item => item.id === capture.id);
    if (position === -1) {
        return null;
    }
    const { columns } = grid.value;
    const column = position % columns;
    const lastRowStart = Math.floor((captures.length - 1) / columns) * columns;

    // 下へは同じ列の次の行へ移り、次の行がその列まで届いていなければその行の最後へ移る
    // 最後の行からは、次の日の最初の行の同じ列へ移る
    if (direction === 'Down') {
        if (position < lastRowStart) {
            return captures[Math.min(position + columns, captures.length - 1)];
        }
        const nextSection = sections.value[index + 1];
        if (nextSection === undefined) {
            return null;
        }
        const nextCaptures = await waitForDay(nextSection.date);
        if (nextCaptures === undefined) {
            return undefined;
        }
        return nextCaptures[Math.min(column, nextCaptures.length - 1)] ?? null;
    }

    // 上へは同じ列の前の行へ移り、最初の行からは前の日の最後の行の同じ列 (届いていなければその行の最後) へ移る
    if (position >= columns) {
        return captures[position - columns];
    }
    const previousSection = sections.value[index - 1];
    if (previousSection === undefined) {
        return null;
    }
    const previousCaptures = await waitForDay(previousSection.date);
    if (previousCaptures === undefined) {
        return undefined;
    }
    const previousLastRowStart = Math.floor((previousCaptures.length - 1) / columns) * columns;
    return previousCaptures[Math.min(previousLastRowStart + column, previousCaptures.length - 1)] ?? null;
};

/**
 * キャプチャのタイルが画面に見えるところまでスクロールする (矢印キーでの移動や、拡大表示を閉じたとき)
 * すでに見えているときはスクロールしない
 * @param capture キャプチャ
 */
const revealCapture = async (capture: ICapture) => {
    if (rootRef.value === null) {
        return;
    }

    // タイルのタイムラインの先頭からの位置を求める
    // 画面から離れて手放した日のキャプチャ (拡大表示で遠くの日まで送ったときなど) は、読み込み直してから位置を求める
    const date = dateOf(capture);
    const section = sections.value.find(item => item.date === date);
    if (date === null || section === undefined) {
        return;
    }
    const position = (await waitForDay(date))?.findIndex(item => item.id === capture.id) ?? -1;
    if (position === -1 || rootRef.value === null) {
        return;
    }
    const { columns, rowHeight, tileHeight } = grid.value;
    const tileTop = section.top + HEADER_HEIGHT + Math.floor(position / columns) * rowHeight;

    // 画面の上端 (固定のヘッダーの下) と下端に収まっていれば、そのままにする
    const rootTop = rootRef.value.getBoundingClientRect().top + window.scrollY;
    const pageTop = rootTop + tileTop - baseOffset.value;
    const visibleTop = window.scrollY + REVEAL_TOP_MARGIN;
    const visibleBottom = window.scrollY + window.innerHeight - REVEAL_BOTTOM_MARGIN;
    if (pageTop >= visibleTop && pageTop + tileHeight <= visibleBottom) {
        return;
    }

    // 上にはみ出していれば日の見出しごと上端に、下にはみ出していれば下端に合わせる
    if (pageTop < visibleTop) {
        scrollToContentY(tileTop - HEADER_HEIGHT);
    } else {
        scrollToContentY(tileTop + tileHeight - (window.innerHeight - REVEAL_TOP_MARGIN - REVEAL_BOTTOM_MARGIN));
    }
    await nextTick();
};

/**
 * キャプチャが並んでいる日の、読み込み済みのキャプチャを返す (Ctrl+A でその日をすべて選ぶとき)
 * @param capture キャプチャ
 * @returns その日のキャプチャ
 */
const getDayCaptures = (capture: ICapture) => {
    const date = dateOf(capture);
    return date === null ? [] : (loadedDays.value.get(date) ?? []);
};

/**
 * 読み込み済みのキャプチャを差し替える (お気に入りやタグを変えたとき)
 * @param updated 更新後のキャプチャ
 */
const replaceCapture = (updated: ICapture) => {
    const next = new Map(loadedDays.value);
    for (const [date, captures] of next) {
        const position = captures.findIndex(item => item.id === updated.id);
        if (position !== -1) {
            const copied = [...captures];
            copied[position] = updated;
            next.set(date, copied);
        }
    }
    loadedDays.value = next;
};

const getProgram = (capture_program_id: number | null) => capture_program_id === null ? null : programs.get(capture_program_id) ?? null;

defineExpose({ reload, getNeighbor, getKeyboardTarget, revealCapture, getDayCaptures, orderedLoaded, replaceCapture, getProgram });

</script>
<style lang="scss" scoped>

.capture-timeline {
    position: relative;
    width: 100%;
    // スクラバーの幅だけ右に余白を取る
    padding-right: 0;

    &__header {
        position: absolute;
        left: 0;
        right: 0;
        height: 48px;
        display: flex;
        align-items: center;
        padding-top: 6px;

        &-check {
            display: flex;
            margin-left: -4px;
            margin-right: 4px;
            padding: 3px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text-darken-1));
            cursor: pointer;
            width: 0;
            opacity: 0;
            overflow: hidden;
            transition: opacity 0.15s ease, width 0.15s ease;
            &--visible {
                width: 28px;
                opacity: 1;
            }
        }
        &:hover &-check {
            width: 28px;
            opacity: 1;
        }

        &-label {
            display: flex;
            align-items: baseline;
        }
        &-date {
            font-size: 15.5px;
            font-weight: 700;
            color: rgb(var(--v-theme-text));
            @include smartphone-vertical {
                font-size: 14.5px;
            }
        }
        &-count {
            margin-left: 10px;
            font-size: 12.5px;
            color: rgb(var(--v-theme-text-darken-1));
        }
    }

    &__tile {
        position: absolute;
    }
    &__placeholder {
        width: 100%;
        height: 100%;
        border-radius: 6px;
        background: rgb(var(--v-theme-background-lighten-1));
    }

    // 読み込めなかった日のタイルの領域 (1日に数百枚ある日でも、案内とボタンが固定のヘッダーの下に見え続けるよう、中身を上端に貼り付ける)
    &__failed {
        display: flex;
        justify-content: center;
        align-items: flex-start;
        position: absolute;
        left: 0;
        right: 0;
        border-radius: 6px;
        background: rgb(var(--v-theme-background-lighten-1));
        &-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: sticky;
            top: 72px;
            padding: 8px 12px;
            text-align: center;
        }
        &-message {
            font-size: 14px;
            color: rgb(var(--v-theme-text-darken-1));
        }
    }
}

</style>
