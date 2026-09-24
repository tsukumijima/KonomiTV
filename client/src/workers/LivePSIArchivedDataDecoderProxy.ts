
import * as Comlink from 'comlink';

import type { ILivePSIArchivedDataDecoderConstructor } from '@/workers/LivePSIArchivedDataDecoder';


// LivePSIArchivedDataDecoder を Web Worker 上で動作させるためのラッパー
// Worker 側で Comlink.expose() により公開したクラスを、メインスレッドから Comlink.wrap() を通して操作する
// vite-plugin-comlink の ComlinkWorker はモジュール全体を自動公開するため、クラスを手動公開する構成では通常の Worker を使う
// Worker の生成処理を別ファイルに分け、実装からは型のみを import することで、メインスレッドと Worker の実行環境を分離する
const LivePSIArchivedDataDecoderProxy = Comlink.wrap<ILivePSIArchivedDataDecoderConstructor>(
    new Worker(new URL('./LivePSIArchivedDataDecoder.ts', import.meta.url), {type: 'module'}),
);
export default LivePSIArchivedDataDecoderProxy;
