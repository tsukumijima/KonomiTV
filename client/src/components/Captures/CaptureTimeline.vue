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
                <span class="capture-timeline__header-date">{{ formatDate(section.date) }}</span>
                <span class="capture-timeline__header-count">{{ section.count.toLocaleString() }}枚</span>
            </div>
            <template v-for="tile in visibleTiles(section)" :key="tile.key">
                <div class="capture-timeline__tile" :style="tile.style">
                    <CaptureTile v-if="tile.capture" :capture="tile.capture"
                        :selected="selection.isSelected(tile.capture)"
                        :selecting="selection.isSelecting.value"
                        @open="$emit('open', tile.capture)"
                        @toggle="(shiftKey) => onToggle(tile.capture!, shiftKey)"
                        @updated="$emit('updated', $event)" />
                    <div v-else class="capture-timeline__placeholder"></div>
                </div>
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

import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';

import CaptureScrubber, { IScrubberMark } from '@/components/Captures/CaptureScrubber.vue';
import { CaptureSelection } from '@/components/Captures/CaptureSelection';
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
// ブラウザが扱える要素の高さには上限 (Chrome では約 3,355 万 px) があり、百万枚規模ではそれを超える
// そのため要素の高さはこの値までにとどめ、要素の上端に当たるタイムラインの位置 (baseOffset) をずらしながら、その範囲だけを描画する
const MAX_DOM_HEIGHT = 8_000_000;
const rootRef = ref<HTMLElement | null>(null);
const containerWidth = ref(0);
const viewportHeight = ref(window.innerHeight);
const scrollOffset = ref(0);  // タイムラインの先頭から見た、画面の上端の位置
const baseOffset = ref(0);  // 要素の上端に当たる、タイムラインの先頭からの位置

// 日付ごとの件数と、読み込んだ日のキャプチャ
const sections = shallowRef<ITimelineSection[]>([]);
const loadedDays = shallowRef(new Map<string, ICapture[]>());
// 日の読み込みの結果 (Queued は、同時に読み込める数の上限で順番待ちになったことを表す)
type DayLoadResult = 'Loaded' | 'Queued' | 'Failed';
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
watch(grid, layout);

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
watch(visibleSections, (list) => {
    for (const section of list) {
        const failedAt = failedDays.get(`${generation}:${section.date}`);
        if (failedAt !== undefined && performance.now() - failedAt < 10 * 1000) {
            continue;
        }
        void loadDay(section.date);
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
// 読み込めなかった日と、その時刻 (キーは `世代:日付`)
const failedDays = new Map<string, number>();
const pendingDays: string[] = [];
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
            const result = await Captures.fetchAllCaptures({
                order: props.axis === 'CapturedAt' ? 'CapturedAtDesc' : 'BroadcastAtDesc',
                date,
                day_start_hour: props.dayStartHour,
                filter: props.filter,
            });
            if (myGeneration !== generation || result === null) {
                if (result === null) {
                    failedDays.set(loadingKey, performance.now());
                }
                return 'Failed';
            }
            failedDays.delete(loadingKey);
            for (const program of result.programs) {
                programs.set(program.id, program);
            }
            const next = new Map(loadedDays.value);
            next.set(date, result.captures);
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

// 取り直している日付ごとの件数 (拡大表示の前後の移動で、取り直し終わるのを待つため)
let reloadingSections: Promise<unknown> | null = null;

// 日付ごとの件数を取り直して、読み込んだ日を捨てて描画し直す (要素の範囲をずらした位置は保つ)
const reload = async () => {
    generation++;
    const myGeneration = generation;
    loadedDays.value = new Map();
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
    // 描画する位置も同じ量だけずれるので見た目は動かず、そのままスクロールを続けられる (ずらすのは数百万 px スクロールするごとに1回だけ)
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
    window.scrollTo({ top: Math.max(0, rootTop + y - baseOffset.value - 72) });
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
const onToggle = (capture: ICapture, shiftKey: boolean) => {
    props.selection.toggle(capture, shiftKey ? orderedLoaded() : null);
};

const formatDate = (date: string) => {
    // 日付だけの文字列はブラウザのタイムゾーンの0時として解釈されるので、日本時間の0時として解釈させる
    const value = dayjs(`${date}T00:00:00+09:00`);
    return value.year() === dayjs().year() ? value.format('M月D日 (dd)') : value.format('YYYY年M月D日 (dd)');
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

    // 日の読み込みを始め、読み終わったその日のキャプチャを返す
    // 読み込みに時間がかかっても終わるまで待ち、読み込み中を0件と取り違えて端に着いたと判定するのを防ぐ
    const waitForDay = async (date: string) => {
        // 順番待ちになった日は、画面に見えていないと読み込まずに外されるので、空きができ次第この日の読み込みを始めるよう呼び直す
        let result = await loadDay(date);
        while (result === 'Queued') {
            await new Promise(resolve => setTimeout(resolve, 100));
            result = await loadDay(date);
        }
        // 読み込めなかった日は、端に着いたのではなく分からないだけなので、次に送るときに読み直せるよう undefined を返す
        if (result === 'Failed') {
            return undefined;
        }
        return loadedDays.value.get(date) ?? [];
    };

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
    if (time === null) {
        return null;
    }
    const date = dayjs(time).subtract(props.dayStartHour, 'hour').format('YYYY-MM-DD');

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

defineExpose({ reload, getNeighbor, replaceCapture, getProgram });

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
}

</style>
