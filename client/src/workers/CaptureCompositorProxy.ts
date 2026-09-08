
import * as Comlink from 'comlink';

import type { ICaptureCompositorConstructor } from '@/workers/CaptureCompositor';


// CaptureCompositor を Web Worker 上で動作させるためのラッパー
// CaptureCompositor.ts 側ですでにクラスを Comlink にエクスポートしている。
// ComlinkWorker を使うとエクスポート処理が重複するため、通常の Worker を Comlink.wrap() に渡す。
// ラップ元と同じファイルに定義すると Circular Dependency として警告されブラウザの挙動が不安定になるため、別ファイルに定義している
const CaptureCompositorProxy = Comlink.wrap<ICaptureCompositorConstructor>(
    new Worker(new URL('./CaptureCompositor.ts', import.meta.url), {type: 'module'}),
);
export default CaptureCompositorProxy;
