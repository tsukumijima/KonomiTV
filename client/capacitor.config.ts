import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
    appId: 'tv.konomi.app',
    appName: 'KonomiTV',
    webDir: 'dist',
    server: {
        // iOS で Service Worker を有効にするため、https スキームを使用
        hostname: 'localhost',
        iosScheme: 'https',
        androidScheme: 'https',
    },
    ios: {
        // iOS 固有の設定
        contentInset: 'automatic',
        // WKWebView のパフォーマンス設定
        limitsNavigationsToAppBoundDomains: false,
    },
};

export default config;
