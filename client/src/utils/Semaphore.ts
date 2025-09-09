/**
 * 非同期処理の同時実行数を制御する軽量セマフォ
 * - acquire(): 同時実行スロットを取得するまで待機
 * - release(): スロットを解放し、待機中の処理があれば 1 件だけ起こす
 */
export class Semaphore {
    private readonly max: number;
    private current = 0;
    private queue: Array<() => void> = [];

    constructor(max: number) {
        // 1 未満が指定された場合でも最低 1 に矯正
        this.max = Math.max(1, Math.floor(max));
    }

    public async acquire(): Promise<void> {
        if (this.current < this.max) {
            this.current += 1;
            return;
        }
        await new Promise<void>(resolve => {
            this.queue.push(() => {
                this.current += 1;
                resolve();
            });
        });
    }

    public release(): void {
        // 先に 1 スロット分を解放してから待機者へ譲渡する
        this.current = Math.max(0, this.current - 1);
        const next = this.queue.shift();
        if (next !== undefined) {
            // 解放したスロットを待機者 1 件へ譲渡（acquire 側で current++ される）
            next();
        }
    }
}

export default Semaphore;
