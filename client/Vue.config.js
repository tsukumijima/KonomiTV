
process.env.VUE_APP_VERSION = process.env.npm_package_version
module.exports = {
    // 開発用サーバー
    devServer: {
        port: 7001,
        disableHostCheck: true,
    },
    // 出力フォルダ
    outputDir: 'dist/',
    assetsDir: 'assets/',
    publicPath: '/',
    // Vuetify
    transpileDependencies: ['vuetify'],
    // PWA 設定
    pwa: {
        name: 'Konomi',
        themeColor: '#2F221F',
        appleMobileWebAppCapable: 'yes',
        appleMobileWebAppStatusBarStyle: 'black',
        // アイコンのパス
        iconPaths: {
            favicon32: 'assets/img/icons/favicon-32x32.png',
            favicon16: 'assets/img/icons/favicon-16x16.png',
            appleTouchIcon: 'assets/img/icons/apple-touch-icon-152x152.png',
            maskIcon: 'assets/img/icons/safari-pinned-tab.svg',
            msTileImage: 'assets/img/icons/msapplication-icon-144x144.png',
        },
        // manifest.json の内容
        manifestOptions: {
            "name": "Konomi",
            "short_name": "Konomi",
            "start_url": ".",
            "display": "standalone",
            "theme_color": "#2F221F",
            "background_color": "#000000",
            "icons": [
                {
                    "src": "/assets/img/icons/android-chrome-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": "/assets/img/icons/android-chrome-512x512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                },
                {
                    "src": "/assets/img/icons/android-chrome-maskable-192x192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "maskable",
                },
                {
                    "src": "/assets/img/icons/android-chrome-maskable-512x512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                }
            ]
        }
    }
};
