
import { ICaptureCompositorConstructor } from '@/workers/CaptureCompositor';


// CaptureCompositor を Web Worker 上で動作させるためのラッパー
// Comlink を経由し、Web Worker とメインスレッド間でオブジェクトをやり取りする
// ラップ元と同じファイルに定義すると Webpack から Circler Dependency として警告されブラウザの挙動が不安定になるため、別ファイルに定義している
const CaptureCompositorProxy =
    new ComlinkWorker<ICaptureCompositorConstructor>(new URL('./CaptureCompositor', import.meta.url));
export default CaptureCompositorProxy;
