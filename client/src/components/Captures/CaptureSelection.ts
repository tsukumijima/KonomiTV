
import { computed, ref } from 'vue';

import { ICapture } from '@/services/Captures';


/**
 * キャプチャの複数選択の状態を扱う
 * 画面 (タイムライン・番組別・お気に入りなど) ごとに1つ作り、グリッドと選択中の操作バーで共有する
 * 選択したキャプチャそのものを持つのは、ページをまたいで選んだものも操作バーから扱えるようにするため
 */
export function useCaptureSelection() {

    // 選択中のキャプチャ (ID → キャプチャ)
    const selected = ref(new Map<number, ICapture>());

    // Shift キーでの範囲選択の起点にする、最後にクリックしたキャプチャの ID
    const anchorId = ref<number | null>(null);

    // キーボードで移動する起点にする、最後に選んだか矢印キーで移動したキャプチャの ID
    // Shift キーと矢印キーで範囲を広げている間は、範囲選択の起点は動かさずにこちらだけを動かす (エクスプローラーや Finder と同じ)
    const cursorId = ref<number | null>(null);

    // 選択中かどうか (1件でも選んでいれば選択モードとして扱う)
    const isSelecting = computed(() => selected.value.size > 0);
    const count = computed(() => selected.value.size);

    const isSelected = (capture: ICapture) => selected.value.has(capture.id);

    /**
     * キャプチャの選択を切り替える
     * @param capture キャプチャ
     * @param ordered 範囲選択に使う、画面での並び順のキャプチャ (Shift キーを押しているときだけ渡す)
     */
    const toggle = (capture: ICapture, ordered: ICapture[] | null = null) => {
        const next = new Map(selected.value);

        // Shift キーを押しての選択は、起点から今のキャプチャまでをまとめて選ぶ (Google フォトと同じ)
        if (ordered !== null && anchorId.value !== null) {
            const from = ordered.findIndex(item => item.id === anchorId.value);
            const to = ordered.findIndex(item => item.id === capture.id);
            if (from !== -1 && to !== -1) {
                for (const item of ordered.slice(Math.min(from, to), Math.max(from, to) + 1)) {
                    next.set(item.id, item);
                }
                selected.value = next;
                anchorId.value = capture.id;
                cursorId.value = capture.id;
                return;
            }
        }

        if (next.has(capture.id)) {
            next.delete(capture.id);
        } else {
            next.set(capture.id, capture);
        }
        selected.value = next;
        anchorId.value = capture.id;
        cursorId.value = capture.id;
    };

    /**
     * 1枚のキャプチャだけを選んだ状態にする (矢印キーでの移動など)
     * @param capture キャプチャ
     */
    const selectOnly = (capture: ICapture) => {
        selected.value = new Map([[capture.id, capture]]);
        anchorId.value = capture.id;
        cursorId.value = capture.id;
    };

    /**
     * 範囲選択の起点から指定したキャプチャまでだけを選んだ状態にする (Shift キーと矢印キーでの範囲選択)
     * @param capture 範囲の終わりのキャプチャ
     * @param ordered 画面での並び順のキャプチャ
     */
    const selectRange = (capture: ICapture, ordered: ICapture[]) => {
        const from = ordered.findIndex(item => item.id === anchorId.value);
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
        cursorId.value = capture.id;
    };

    /**
     * キーボードで移動する起点のキャプチャを返す
     * 起点のキャプチャが選択から外れているときは、最後に選んだキャプチャを返す
     * @returns キャプチャ (何も選んでいないときは null)
     */
    const getCursor = () => {
        if (cursorId.value !== null && selected.value.has(cursorId.value)) {
            return selected.value.get(cursorId.value)!;
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
            }
        }
        selected.value = next;
    };

    const clear = () => {
        selected.value = new Map();
        anchorId.value = null;
        cursorId.value = null;
    };

    return { selected, isSelecting, count, isSelected, toggle, selectOnly, selectRange, getCursor, setMany, clear };
}

export type CaptureSelection = ReturnType<typeof useCaptureSelection>;
