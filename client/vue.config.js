
const path = require('path');

const webpack = require('webpack');

// Vue CLI に提供する環境変数
process.env.VUE_APP_VERSION = process.env.npm_package_version;

module.exports = {
    // 出力フォルダ
    outputDir: 'dist/',
    assetsDir: 'assets/',
    publicPath: '/',
    // Webpack の開発用サーバーの設定
    devServer: {
        host: '127.0.0.77',
        port: 7011,
        allowedHosts: 'all',
        client: {
            webSocketURL: 'wss://0.0.0.0:7001/ws',
        }
    },
    // Webpack の設定
    configureWebpack: {
        // web-bml の動作に必要
        // ref: https://github.com/tsukumijima/web-bml/blob/master/webpack.config.js
        resolve: {
            extensions: ['.ts', '.js'],
            fallback: {
                fs: false,
                path: false,
                url: false,
                vm: false,
                assert: require.resolve('assert'),
                Buffer: require.resolve('buffer'),
                process: require.resolve('process/browser'),
                stream: require.resolve('stream-browserify'),
                util: require.resolve('util'),
                zlib: require.resolve('browserify-zlib'),
            }
        }
    },
    chainWebpack: (config) => {
        // web-bml の動作に必要
        // ref: https://github.com/tsukumijima/web-bml/blob/master/webpack.config.js
        config.plugin('ProvidePlugin1').use(webpack.ProvidePlugin, [{
            Buffer: ['buffer', 'Buffer'],
            process: 'process/browser',
        }]);
        config.plugin('ProvidePlugin2').use(webpack.ProvidePlugin, [{
            acorn: path.resolve(__dirname, 'node_modules/web-bml/JS-Interpreter/acorn.js'),
        }]);
        if (process.env.NODE_ENV === 'development') {
            // 開発時は Minify を行わない
            config.optimization.minimize(false);
            // Safari で開発用サーバーのホットリロードが機能しない問題の回避策
            // ref: https://github.com/vuejs/vue-cli/issues/1132#issuecomment-409916879
            config.output.filename('[name].[contenthash].js').end();
        }
    },
    // PWA の設定
    pwa: {
        name: 'KonomiTV',
        themeColor: '#0D0807',
        appleMobileWebAppCapable: 'yes',
        appleMobileWebAppStatusBarStyle: 'black',
        // アイコンのパス
        iconPaths: {
            faviconSVG: 'assets/images/icons/favicon.svg',
            favicon32: 'assets/images/icons/favicon-32px.png',
            favicon16: 'assets/images/icons/favicon-16px.png',
            appleTouchIcon: 'assets/images/icons/apple-touch-icon.png',
            maskIcon: null,  // 設定しない
            msTileImage: null,  // 設定しない
        },
        // manifest.json の内容
        manifestOptions: {
            name: 'KonomiTV',
            short_name: 'KonomiTV',
            start_url: '.',
            display: 'standalone',
            theme_color: '#0D0807',
            background_color: '#1E1310',
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
        workboxOptions: {
            cleanupOutdatedCaches: true,
            maximumFileSizeToCacheInBytes: 1024 * 1024 * 3,  // 3MB
        }
    }
};
