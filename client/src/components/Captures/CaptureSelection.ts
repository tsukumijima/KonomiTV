
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
    };

    return { selected, isSelecting, count, isSelected, toggle, setMany, clear };
}

export type CaptureSelection = ReturnType<typeof useCaptureSelection>;
