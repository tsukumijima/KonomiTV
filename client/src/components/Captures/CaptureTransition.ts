
import { nextTick } from 'vue';


/**
 * 一覧のタイルの画像を返す (読み込み済みの画像だけ)
 * 拡大表示を開閉するときに、タイルの画像と1枚表示の画像をつなぐために使う
 * @param capture_id キャプチャの ID
 * @returns タイルの画像 (画面に描画されていないか、まだ読み込めていなければ null)
 */
export function findTileImage(capture_id: number): HTMLImageElement | null {
    return document.querySelector<HTMLImageElement>(`.capture-tile[data-capture-id="${capture_id}"] .capture-tile__image--loaded`);
}


/**
 * 拡大表示を開くときに、View Transitions API でタイルの画像が1枚表示の画像の位置まで拡大していくように見せる
 * タイルの画像と1枚表示の画像に同じ名前を付けると、ブラウザが2つの位置と大きさをつないでアニメーションさせる
 * @param tileImage タイルの画像 (null ならアニメーションせずに開く)
 * @param open 拡大表示を開く処理
 */
export function openWithTransition(tileImage: HTMLImageElement | null, open: () => void): void {
    // 対応していないブラウザ、画像がまだ読み込めていないタイル、動きを減らす設定のときは、そのまま開く
    if (document.startViewTransition === undefined || tileImage === null ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches === true) {
        open();
        return;
    }
    tileImage.style.setProperty('view-transition-name', 'capture-lightbox-image');
    document.startViewTransition(async () => {
        // 開いた後の画面では、名前を1枚表示の画像 (CaptureLightbox.vue) へ渡す
        tileImage.style.removeProperty('view-transition-name');
        open();
        await nextTick();
        // 1枚表示の画像の描画が間に合うよう、デコードを待ってから開いた後の画面を撮らせる (同じ URL なのでキャッシュから読まれる)
        const target = document.querySelector<HTMLImageElement>('.capture-lightbox__image--current');
        if (target !== null) {
            await Promise.race([
                target.decode().catch(() => undefined),
                new Promise(resolve => window.setTimeout(resolve, 300)),
            ]);
        }
    });
}
