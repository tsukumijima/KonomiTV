
import { ILivePSIArchivedDataDecoderConstructor } from '@/workers/LivePSIArchivedDataDecoder';


// LivePSIArchivedDataDecoder を Web Worker 上で動作させるためのラッパー
// Comlink を経由し、Web Worker とメインスレッド間でオブジェクトをやり取りする
// ラップ元と同じファイルに定義すると Webpack から Circler Dependency として警告されブラウザの挙動が不安定になるため、別ファイルに定義している
const LivePSIArchivedDataDecoderProxy =
    new ComlinkWorker<ILivePSIArchivedDataDecoderConstructor>(new URL('./LivePSIArchivedDataDecoder', import.meta.url));
export default LivePSIArchivedDataDecoderProxy;
