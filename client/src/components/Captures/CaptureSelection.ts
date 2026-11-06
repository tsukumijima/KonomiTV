
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { ICapture } from '@/services/Captures';


/**
 * キャプチャの複数選択の状態を扱う
 * 画面 (タイムライン・番組別・お気に入りなど) ごとに1つ作り、グリッドと選択中の操作バーで共有する
 * 選択したキャプチャそのものを持つのは、ページをまたいで選んだものも操作バーから扱えるようにするため
 */
export function useCaptureSelection() {

    // 選択中のキャプチャ (ID → キャプチャ)
    const selected = ref(new Map<number, ICapture>());

    // Shift キーでの範囲選択の起点にする、最後にクリックしたキャプチャ
    // タイムラインが起点のある日を求めて、起点から範囲の終わりまでの日を読み込めるよう、ID ではなくキャプチャそのものを持つ
    const anchor = ref<ICapture | null>(null);

    // キーボードで移動する起点にする、最後に選んだか矢印キーで移動したキャプチャ
    // Shift キーと矢印キーで範囲を広げている間は、範囲選択の起点は動かさずにこちらだけを動かす (エクスプローラーや Finder と同じ)
    // Ctrl キーと矢印キーで動かしたときは、選択に含まれないキャプチャを指すこともある
    const cursor = ref<ICapture | null>(null);

    // Ctrl キーと矢印キーで、選択とは別にカーソルを動かしている間だけ、カーソルの位置に枠を表示する
    // クリックや矢印キーだけでの移動では、カーソルは選んだキャプチャと同じ位置にあるため表示しない
    const isCursorVisible = ref(false);

    // Shift キーを押しながらマウスを乗せているときに、クリックすると選ばれる範囲のキャプチャの ID (Google フォトと同じ)
    const previewIds = ref(new Set<number>());

    // 選択中かどうか (1件でも選んでいれば選択モードとして扱う)
    const isSelecting = computed(() => selected.value.size > 0);
    const count = computed(() => selected.value.size);

    const isSelected = (capture: ICapture) => selected.value.has(capture.id);
    const isPreviewed = (capture: ICapture) => previewIds.value.has(capture.id);
    const isCursor = (capture: ICapture) => isCursorVisible.value && cursor.value?.id === capture.id;

    /**
     * キャプチャの選択を切り替える
     * @param capture キャプチャ
     * @param ordered 範囲選択に使う、画面での並び順のキャプチャ (Shift キーを押しているときだけ渡す)
     */
    const toggle = (capture: ICapture, ordered: ICapture[] | null = null) => {
        const next = new Map(selected.value);

        // Shift キーを押しての選択は、起点から今のキャプチャまでをまとめて選ぶ (Google フォトと同じ)
        if (ordered !== null && anchor.value !== null) {
            const from = ordered.findIndex(item => item.id === anchor.value?.id);
            const to = ordered.findIndex(item => item.id === capture.id);
            if (from !== -1 && to !== -1) {
                for (const item of ordered.slice(Math.min(from, to), Math.max(from, to) + 1)) {
                    next.set(item.id, item);
                }
                selected.value = next;
                anchor.value = capture;
                cursor.value = capture;
                isCursorVisible.value = false;
                return;
            }
        }

        if (next.has(capture.id)) {
            next.delete(capture.id);
        } else {
            next.set(capture.id, capture);
        }
        selected.value = next;
        anchor.value = capture;
        cursor.value = capture;
        isCursorVisible.value = false;
    };

    /**
     * 1枚のキャプチャだけを選んだ状態にする (矢印キーでの移動など)
     * @param capture キャプチャ
     */
    const selectOnly = (capture: ICapture) => {
        selected.value = new Map([[capture.id, capture]]);
        anchor.value = capture;
        cursor.value = capture;
        isCursorVisible.value = false;
    };

    /**
     * 範囲選択の起点から指定したキャプチャまでだけを選んだ状態にする (Shift キーと矢印キーでの範囲選択)
     * @param capture 範囲の終わりのキャプチャ
     * @param ordered 画面での並び順のキャプチャ
     */
    const selectRange = (capture: ICapture, ordered: ICapture[]) => {
        const from = ordered.findIndex(item => item.id === anchor.value?.id);
        const to = ordered.findIndex(item => item.id === capture.id);
        // 起点が並びの中に見つからないときは、移動先から範囲選択を始め直す
        if (from === -1 || to === -1) {
            selectOnly(capture);
            return;
        }
        const next = new Map<number, ICapture>();
        for (const item of ordered.slice(Math.min(from, to), Math.max(from, to) + 1)) {
            next.set(item.id, item);
        }
        selected.value = next;
        cursor.value = capture;
        isCursorVisible.value = false;
    };

    /**
     * Shift キーを押しながらクリックしたときに選ばれる範囲を、選ぶ前に示す
     * @param capture マウスを乗せているキャプチャ (Shift キーを離したときやタイルから外れたときは null)
     * @param ordered 画面での並び順のキャプチャ
     */
    const previewRange = (capture: ICapture | null, ordered: ICapture[]) => {
        const from = ordered.findIndex(item => item.id === anchor.value?.id);
        const to = capture === null ? -1 : ordered.findIndex(item => item.id === capture.id);
        if (selected.value.size === 0 || from === -1 || to === -1) {
            if (previewIds.value.size > 0) {
                previewIds.value = new Set();
            }
            return;
        }
        const next = new Set<number>();
        for (const item of ordered.slice(Math.min(from, to), Math.max(from, to) + 1)) {
            next.add(item.id);
        }
        previewIds.value = next;
    };

    /**
     * 選択を変更せずに、カーソルだけを指定したキャプチャへ動かす (Ctrl キーと矢印キーでの移動)
     * @param capture 移動先のキャプチャ
     */
    const moveCursor = (capture: ICapture) => {
        cursor.value = capture;
        isCursorVisible.value = true;
    };

    /**
     * カーソルの位置のキャプチャの選択を切り替える (Ctrl キーと Space キー)
     * エクスプローラーと同じく、切り替えたキャプチャを Shift キーでの範囲選択の起点にする
     * 最後の1枚の選択を外したときは、マウスで外したときと同じく選択モードを終える
     */
    const toggleCursor = () => {
        if (cursor.value === null) {
            return;
        }
        const next = new Map(selected.value);
        if (next.has(cursor.value.id)) {
            next.delete(cursor.value.id);
        } else {
            next.set(cursor.value.id, cursor.value);
        }
        if (next.size === 0) {
            clear();
            return;
        }
        selected.value = next;
        anchor.value = cursor.value;
        isCursorVisible.value = true;
    };

    /**
     * キーボードで移動する起点のキャプチャを返す
     * Ctrl キーと矢印キーで動かしたカーソルは、選択に含まれていなくてもそのまま返す
     * それ以外で起点のキャプチャが選択から外れているときは、最後に選んだキャプチャを返す
     * @returns キャプチャ (何も選んでいないときは null)
     */
    const getCursor = () => {
        if (cursor.value !== null) {
            // お気に入りなどの変更で選択が新しい内容に差し替わっていれば、そちらを返す
            const current = selected.value.get(cursor.value.id);
            if (current !== undefined) {
                return current;
            }
            if (isCursorVisible.value) {
                return cursor.value;
            }
        }
        return [...selected.value.values()].at(-1) ?? null;
    };

    /**
     * 複数のキャプチャをまとめて選ぶか外す (日付の見出しの「この日をすべて選択」など)
     * @param captures キャプチャのリスト
     * @param value true なら選び、false なら外す
     */
    const setMany = (captures: ICapture[], value: boolean) => {
        const next = new Map(selected.value);
        for (const capture of captures) {
            if (value) {
                next.set(capture.id, capture);
            } else {
                next.delete(capture.id);
                // 削除などで選択から外したキャプチャをカーソルが指していれば、カーソルも外す
                if (cursor.value?.id === capture.id) {
                    cursor.value = null;
                    isCursorVisible.value = false;
                }
            }
        }
        selected.value = next;
    };

    const clear = () => {
        selected.value = new Map();
        anchor.value = null;
        cursor.value = null;
        isCursorVisible.value = false;
    };

    return {
        selected,
        anchor,
        isSelecting,
        count,
        isSelected,
        isPreviewed,
        isCursor,
        toggle,
        selectOnly,
        selectRange,
        previewRange,
        moveCursor,
        toggleCursor,
        getCursor,
        setMany,
        clear,
    };
}

export type CaptureSelection = ReturnType<typeof useCaptureSelection>;


/**
 * 選択中に Shift キーを押しながらマウスを動かすと、クリックで選ばれる範囲をタイルに示す (Google フォトと同じ)
 * マウスを乗せているタイルは、タイルの data-capture-id 属性から探す
 * @param selection キャプチャの選択の状態
 * @param getOrdered 画面での並び順のキャプチャを返す関数
 */
export function useCaptureRangePreview(selection: CaptureSelection, getOrdered: () => ICapture[]) {

    // マウスを乗せているキャプチャの ID と Shift キーの状態は、変わったときだけ範囲を計算し直す
    let hoveredId: number | null = null;
    let isShiftPressed = false;

    const update = () => {
        if (hoveredId === null || isShiftPressed === false || selection.isSelecting.value === false) {
            selection.previewRange(null, []);
            return;
        }
        const ordered = getOrdered();
        selection.previewRange(ordered.find(capture => capture.id === hoveredId) ?? null, ordered);
    };

    const onMouseMove = (event: MouseEvent) => {
        if (selection.isSelecting.value === false) {
            return;
        }
        const tile = event.target instanceof Element ? event.target.closest<HTMLElement>('.capture-tile[data-capture-id]') : null;
        const id = tile !== null ? Number(tile.dataset.captureId) : null;
        if (id !== hoveredId || event.shiftKey !== isShiftPressed) {
            hoveredId = id;
            isShiftPressed = event.shiftKey;
            update();
        }
    };
    const onKey = (event: KeyboardEvent) => {
        if (event.key === 'Shift' && event.shiftKey !== isShiftPressed) {
            isShiftPressed = event.shiftKey;
            update();
        }
    };
    // Shift キーを押したまま別のウインドウへ移ると keyup が届かないので、フォーカスを失ったら範囲の表示を消す
    const onBlur = () => {
        isShiftPressed = false;
        update();
    };

    onMounted(() => {
        window.addEventListener('mousemove', onMouseMove, { passive: true });
        window.addEventListener('keydown', onKey);
        window.addEventListener('keyup', onKey);
        window.addEventListener('blur', onBlur);
    });
    onBeforeUnmount(() => {
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('keydown', onKey);
        window.removeEventListener('keyup', onKey);
        window.removeEventListener('blur', onBlur);
    });
}
