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
        contentInset: 'never',  // セーフエリアを手動で制御するため無効化
        scrollEnabled: true,  // スクロールを有効化
        // WKWebView のパフォーマンス設定
        limitsNavigationsToAppBoundDomains: false,
        // 最小デプロイメントターゲット (iOS 15以上)
        deploymentTarget: '15.0',
    },
};

export default config;
