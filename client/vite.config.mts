
import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';
import { comlink } from 'vite-plugin-comlink';
import { VitePWA } from 'vite-plugin-pwa';
import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify';


// Vite の設定
// https://vitejs.dev/config/
export default defineConfig({
    // バージョン情報をビルド時に埋め込む
    // ref: https://stackoverflow.com/a/68093777/17124142
    define: {
        'process.env': {},  // これがないと assert がエラーになる
        'import.meta.env.KONOMITV_VERSION': JSON.stringify(process.env.npm_package_version),
    },
    // ビルドの設定
    build: {
        chunkSizeWarningLimit: 3 * 1024 * 1024,  // 3MB に緩和
        rollupOptions: {
            output: {
                assetFileNames: (assetInfo) => {
                    // フォントファイルのみ、ハッシュを付けずに assets/fonts/ に出力する
                    if (['.ttf', '.eot', '.woff', '.woff2'].some((ext) => assetInfo.name?.endsWith(ext))) {
                        return 'assets/fonts/[name][extname]';
                    }
                    return 'assets/[name].[hash][extname]';
                },
            },
        },
    },
    resolve: {
        alias: {'@': fileURLToPath(new URL('./src', import.meta.url))},
        extensions: ['.js', '.json', '.jsx', '.mjs', '.ts', '.tsx', '.vue'],
    },
    // SASS / SCSS の設定
    css: {
        preprocessorOptions: {
            scss: {
                // 共通の mixin を読み込む
                // ref: https://qiita.com/nanohanabuttobasu/items/f73ed978cc10d8bcaa59
                additionalData: '@import "./src/styles/mixin.scss";',
            },
        },
    },
    // 開発用サーバーの設定
    server: {
        host: '0.0.0.0',
        port: 7011,
        strictPort: true,
        allowedHosts: true,
    },
    preview: {
        host: '0.0.0.0',
        port: 7011,
        strictPort: true,
        allowedHosts: true,
    },
    // プラグインの設定
    plugins: [
        comlink(),
        vue({
            template: {
                transformAssetUrls: transformAssetUrls,
            },
        }),
        // https://github.com/vuetifyjs/vuetify-loader/tree/master/packages/vite-plugin#readme
        vuetify({
            autoImport: true,
            styles: {
                configFile: 'src/styles/settings.scss',
            }
        }),
        // ref: https://vite-pwa-org.netlify.app/guide/
        VitePWA({
            // Service Worker の登録方法
            strategies: 'generateSW',
            registerType: 'prompt',  // PWA の更新前にユーザーに確認する
            injectRegister: 'auto',
            // PWA のキャッシュに含めるファイル
            includeAssets: [
                'assets/**',
            ],
            // manifest.json の内容
            manifest: {
                name: 'KonomiTV',
                short_name: 'KonomiTV',
                start_url: '.',
                display: 'standalone',
                theme_color: '#0D0807',
                background_color: '#1E1310',
                lang: 'ja',
                icons: [
                    {
                        src: '/assets/images/icons/icon-192px.png',
                        sizes: '192x192',
                        type: 'image/png',
                    },
                    {
                        src: '/assets/images/icons/icon-512px.png',
                        sizes: '512x512',
                        type: 'image/png',
                    },
                    {
                        src: '/assets/images/icons/icon-maskable-192px.png',
                        sizes: '192x192',
                        type: 'image/png',
                        purpose: 'maskable',
                    },
                    {
                        src: '/assets/images/icons/icon-maskable-512px.png',
                        sizes: '512x512',
                        type: 'image/png',
                        purpose: 'maskable',
                    }
                ]
            },
            // Workbox の設定
            workbox: {
                // 古いキャッシュを自動削除する
                cleanupOutdatedCaches: true,
                // /api/, /cdn-cgi/(cloudflare) 以下のリクエストでは index.html を返さない
                navigateFallbackDenylist: [/^\/api/, /^\/cdn-cgi/],
                // キャッシュするファイルの最大サイズ
                maximumFileSizeToCacheInBytes: 1024 * 1024 * 15,  // 15MB
            }
        }),
    ],
    // Web Worker 上のプラグインの設定
    worker: {
        plugins: () => [
            comlink(),
        ]
    }
});
