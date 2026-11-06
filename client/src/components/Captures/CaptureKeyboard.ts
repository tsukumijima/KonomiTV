import { onBeforeUnmount, onMounted, Ref } from 'vue';

import { CaptureSelection } from '@/components/Captures/CaptureSelection';
import { findTileImage, openWithTransition } from '@/components/Captures/CaptureTransition';
import { ICapture } from '@/services/Captures';


/** キーボードで選択を動かす向き */
export type CaptureKeyboardDirection = 'Left' | 'Right' | 'Up' | 'Down';


/**
 * キャプチャのタイルが並ぶ一覧 (タイムライン・番組別) で共通のキーボード操作を登録する
 * 何かを選んでいる間は、エクスプローラーや Finder のサムネイル表示と同じく、キーボードで選択を動かして操作できるようにする
 * 何も選んでいないときの矢印キーと Space は、ブラウザの既定の動作 (ページのスクロール) に任せる
 * 一覧によって並び方とスクロールの仕方が違うので、移動先の求め方と表示のさせ方は一覧側から渡す
 * @param options.selection キャプチャの選択の状態
 * @param options.selectionBar 選択中のバー (お気に入り・タグ・ダウンロード・削除の操作を行う)
 * @param options.isLightboxOpen 拡大表示を開いているかを返す関数 (開いている間のキーは拡大表示が扱う)
 * @param options.open キャプチャを拡大表示で開く関数
 * @param options.getTarget 矢印キーで移動する先のキャプチャを返す関数 (移動先がなければ null)
 * @param options.getOrdered 画面での並び順のキャプチャを返す関数 (Shift キーでの範囲選択に使う)
 * @param options.reveal キャプチャのタイルが画面に見える位置までスクロールさせる関数
 * @param options.getSelectAllTargets Ctrl (Command) + A キーで選ぶキャプチャを返す関数
 */
export function useCaptureKeyboard(options: {
    selection: CaptureSelection;
    selectionBar: Ref<{
        toggleFavorite: () => Promise<void>;
        openTagDialog: () => void;
        downloadSelected: () => Promise<void>;
        requestDelete: () => void;
    } | null>;
    isLightboxOpen: () => boolean;
    open: (capture: ICapture) => void;
    getTarget: (capture: ICapture, direction: CaptureKeyboardDirection) => Promise<ICapture | null | undefined>;
    getOrdered: () => ICapture[];
    reveal: (capture: ICapture) => Promise<void>;
    getSelectAllTargets: (cursor: ICapture) => ICapture[];
}): void {
    const { selection, selectionBar } = options;

    let isMoving = false;
    const move = async (direction: CaptureKeyboardDirection, mode: 'Select' | 'Extend' | 'Cursor') => {
        const cursor = selection.getCursor();
        // 隣の日を読み込んでいる間にキーが押し続けられても、移動を重ねずに1つずつ進める
        if (cursor === null || isMoving) {
            return;
        }
        isMoving = true;
        try {
            const target = await options.getTarget(cursor, direction);
            // 隣の日を読み込んでいる間に選択が解除・変更されたときは、押した時点の移動先を反映せずに終える
            if (target === null || target === undefined || selection.getCursor()?.id !== cursor.id) {
                return;
            }
            // Shift キーを押しているときは、範囲選択の起点から移動先までを選び、押していないときは移動先の1枚だけを選ぶ
            // Ctrl キーを押しているときは、エクスプローラーと同じく選択を変更せずにカーソルだけを動かす
            if (mode === 'Extend') {
                selection.selectRange(target, options.getOrdered());
            } else if (mode === 'Cursor') {
                selection.moveCursor(target);
            } else {
                selection.selectOnly(target);
            }
            await options.reveal(target);
        } finally {
            isMoving = false;
        }
    };

    const onKeyDown = (event: KeyboardEvent) => {
        // 拡大表示の中のキーは拡大表示 (CaptureLightbox.vue) が扱い、入力欄やメニュー・ダイアログを開いている間は何もしない
        if (options.isLightboxOpen() || selection.isSelecting.value === false) {
            return;
        }
        if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
            return;
        }
        if (document.querySelector('.v-overlay--active') !== null) {
            return;
        }
        const isCtrlOrCmd = event.ctrlKey || event.metaKey;
        const cursor = selection.getCursor();
        if (cursor === null) {
            return;
        }
        switch (event.key) {
            case 'ArrowLeft':
            case 'ArrowRight':
            case 'ArrowUp':
            case 'ArrowDown': {
                // カーソルだけを動かす操作は、エクスプローラーと同じく Mac でも Ctrl キーで行う
                if (event.altKey || event.metaKey || (event.ctrlKey && event.shiftKey)) {
                    return;
                }
                const direction = event.key.replace('Arrow', '') as CaptureKeyboardDirection;
                if (event.ctrlKey) {
                    void move(direction, 'Cursor');
                } else {
                    void move(direction, event.shiftKey ? 'Extend' : 'Select');
                }
                break;
            }
            // macOS のクイックルックと同じく、Space で選んでいるキャプチャを開く (もう一度 Space を押すと閉じる)
            // Ctrl キーと Space キーを一緒に押したときは、エクスプローラーと同じくカーソルの位置のキャプチャの選択を切り替える
            case ' ':
            case 'Enter': {
                if (event.ctrlKey && event.key === ' ' && event.altKey === false && event.shiftKey === false && event.metaKey === false) {
                    selection.toggleCursor();
                    break;
                }
                if (isCtrlOrCmd || event.altKey || event.shiftKey) {
                    return;
                }
                // タブやボタンなどの操作できる要素にフォーカスがあるときは、その要素を押す既定の動作に任せる
                if (event.target instanceof Element &&
                    event.target.closest('button, a[href], select, summary, [role="button"], [role="tab"], [role="link"], [role="menuitem"], [role="option"], [role="checkbox"], [role="switch"]') !== null) {
                    return;
                }
                openWithTransition(findTileImage(cursor.id), () => options.open(cursor));
                break;
            }
            // Mac のキーボードには Delete キーがないため、Finder と同じく Command+Backspace でも削除できるようにする
            case 'Delete': {
                selectionBar.value?.requestDelete();
                break;
            }
            case 'Backspace': {
                if (event.metaKey === false) {
                    return;
                }
                selectionBar.value?.requestDelete();
                break;
            }
            case 'a':
            case 'A': {
                if (isCtrlOrCmd === false) {
                    return;
                }
                selection.setMany(options.getSelectAllTargets(cursor), true);
                break;
            }
            // 拡大表示と同じく、F キーで選んでいるキャプチャをお気に入りに追加・お気に入りから外し、T キーでタグを付ける
            case 'f':
            case 'F': {
                if (isCtrlOrCmd || event.altKey) {
                    return;
                }
                void selectionBar.value?.toggleFavorite();
                break;
            }
            case 't':
            case 'T': {
                if (isCtrlOrCmd || event.altKey) {
                    return;
                }
                selectionBar.value?.openTagDialog();
                break;
            }
            // 拡大表示と同じく、D キーで選んでいるキャプチャをダウンロードする
            case 'd':
            case 'D': {
                if (isCtrlOrCmd || event.altKey) {
                    return;
                }
                void selectionBar.value?.downloadSelected();
                break;
            }
            case 'Escape': {
                selection.clear();
                break;
            }
            default:
                return;
        }
        event.preventDefault();
    };
    onMounted(() => window.addEventListener('keydown', onKeyDown));
    onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown));
}
