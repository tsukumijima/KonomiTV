
import * as Comlink from 'comlink';

import { ILiveChannel } from '@/services/Channels';
import { ILivePSIArchivedDataDecoder } from '@/workers/LivePSIArchivedDataDecoder';


// LivePSIArchivedDataDecoder を Web Worker 上で動作させるためのラッパー
// Comlink を経由し、Web Worker とメインスレッド間でオブジェクトをやり取りする
// ラップ元と同じファイルに定義すると Webpack から Circler Dependency として警告されブラウザの挙動が不安定になるため、別ファイルに定義している
const worker = new Worker(new URL('@/workers/LivePSIArchivedDataDecoder', import.meta.url));
const LivePSIArchivedDataDecoderProxy = Comlink.wrap<new (channel: ILiveChannel, api_quality: string) => ILivePSIArchivedDataDecoder>(worker);
export default LivePSIArchivedDataDecoderProxy;
