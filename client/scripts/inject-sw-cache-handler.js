/**
 * Service Worker に オフライン視聴用のキャッシュハンドラーを注入するスクリプト
 * generateSW で生成された sw.js に fetch イベントリスナーを追加する
 */

import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const swPath = join(process.cwd(), 'dist', 'sw.js');
const cacheHandlerPath = join(__dirname, 'sw-cache-handler.js');

try {
    let swContent = readFileSync(swPath, 'utf-8');

    // 既に注入済みの場合はスキップ
    if (swContent.includes('OFFLINE_CACHE_HANDLER_INJECTED')) {
        console.log('[inject-sw-cache-handler] Already injected, skipping...');
        process.exit(0);
    }

    // カスタムの fetch ハンドラーを外部ファイルから読み込み
    const customFetchHandler = readFileSync(cacheHandlerPath, 'utf-8');

    // ファイルの末尾に追加
    swContent += '\n' + customFetchHandler;

    // 書き込み
    writeFileSync(swPath, swContent, 'utf-8');
    console.log('[inject-sw-cache-handler] ✓ Successfully injected offline cache handler');
} catch (error) {
    console.error('[inject-sw-cache-handler] Error:', error);
    process.exit(1);
}