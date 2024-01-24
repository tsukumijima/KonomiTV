
import { nanoid } from 'nanoid';
import { defineStore } from 'pinia';

import Utils from '@/utils';


export interface SnackbarState {
    id: string;
    level: 'success' | 'warning' | 'error' | 'info' | 'default';
    text: string;
    showing: boolean;
    destroying: boolean;
    show(): void;
    hide(): Promise<void>;
}


export const useSnackbarsStore = defineStore('snackbars', {
    state: () => ({
        snackbars: [] as SnackbarState[],
    }),
    actions: {

        /**
         * 指定されたレベルとテキストで Snackbar を表示する
         * @param level Snackbar のレベル
         * @param text Snackbar に表示するテキスト
         * @param timeout Snackbar を表示する秒数 (秒単位、デフォルトは 5 秒)
         */
        async show(level: 'success' | 'error' | 'warning' | 'info' | 'default', text: string, timeout: number = 5.0) {

            // Snackbar をスタックに追加
            // 一度 push() してからオブジェクトの参照を取得しないと何故かリアクティブにならない
            const _this = this;
            this.snackbars.push({
                id: nanoid(),
                level: level,
                text: text,
                showing: false,
                destroying: false,
                // Snackbar を表示させるときは必ずこのメソッドを使う
                show() {
                    // 表示する
                    this.showing = true;
                },
                // Snackbar を非表示にするときは必ずこのメソッドを使う
                async hide() {
                    // すでに非表示になっている場合は何もしない (重要)
                    if (!this.showing) {
                        return;
                    }
                    // 非表示にする
                    this.showing = false;
                    // 非表示時の CSS アニメーション (0.2 秒)
                    await Utils.sleep(0.2);
                    // 自身の height を 0px にしてなめらかにスタックの空白を詰める CSS アニメーション (0.3 秒)
                    this.destroying = true;  // これを true にすると .snackbar--destroying が適用されてアニメーションが開始される
                    await Utils.sleep(0.3);
                    // アニメーションが終わったら自身を配列から削除する
                    // 念のためさらに 0.1 秒待ってから実行
                    await Utils.sleep(0.1);
                    _this.snackbars.splice(_this.snackbars.indexOf(this), 1);
                },
            });
            const snackbar = this.snackbars[this.snackbars.length - 1];

            // 少し待ってからすぐに表示する
            await Utils.sleep(0.05);  // 少し待たないと表示時の CSS アニメーションが発生しない
            snackbar.show();

            // タイムアウト秒が終わったら非表示にする
            await Utils.sleep(timeout);
            await snackbar.hide();
        }
    },
});
