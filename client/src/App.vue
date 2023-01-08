<template>
    <v-app id="app">
        <transition>
            <router-view/>
        </transition>
    </v-app>
</template>
<style lang="scss">

@font-face {
    font-family: 'Noto Sans JP Caption';
    font-weight: normal;
    src: url('https://cdn.jsdelivr.net/npm/noto-sans-japanese@1.0.0/fonts/NotoSansJP-Medium.woff2') format('woff2');
}

@font-face {
  font-family: 'Open Sans (for iOS Safari)';
  font-style: normal;
  font-weight: 400;
  font-stretch: 100%;
  src: url(https://fonts.gstatic.com/s/opensans/v34/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4uaVIGxA.woff2) format('woff2');
  unicode-range: U+0100-024F, U+0259, U+1E00-1EFF, U+2020, U+20A0-20AB, U+20AD-20CF, U+2113, U+2C60-2C7F, U+A720-A7FF;
}
@font-face {
  font-family: 'Open Sans (for iOS Safari)';
  font-style: normal;
  font-weight: 400;
  font-stretch: 100%;
  src: url(https://fonts.gstatic.com/s/opensans/v34/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4gaVI.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
@font-face {
  font-family: 'Open Sans (for iOS Safari)';
  font-style: normal;
  font-weight: 600;
  font-stretch: 100%;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/opensans/v34/memvYaGs126MiZpBA-UvWbX2vVnXBbObj2OVTSGmu1aB.woff2) format('woff2');
  unicode-range: U+0100-024F, U+0259, U+1E00-1EFF, U+2020, U+20A0-20AB, U+20AD-20CF, U+2113, U+2C60-2C7F, U+A720-A7FF;
}
@font-face {
  font-family: 'Open Sans (for iOS Safari)';
  font-style: normal;
  font-weight: 600;
  font-stretch: 100%;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/opensans/v34/memvYaGs126MiZpBA-UvWbX2vVnXBbObj2OVTS-muw.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
@font-face {
  font-family: 'Open Sans (for iOS Safari)';
  font-style: normal;
  font-weight: 700;
  font-stretch: 100%;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/opensans/v34/memvYaGs126MiZpBA-UvWbX2vVnXBbObj2OVTSGmu1aB.woff2) format('woff2');
  unicode-range: U+0100-024F, U+0259, U+1E00-1EFF, U+2020, U+20A0-20AB, U+20AD-20CF, U+2113, U+2C60-2C7F, U+A720-A7FF;
}
@font-face {
  font-family: 'Open Sans (for iOS Safari)';
  font-style: normal;
  font-weight: 700;
  font-stretch: 100%;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/opensans/v34/memvYaGs126MiZpBA-UvWbX2vVnXBbObj2OVTS-muw.woff2) format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}

// 全体のスタイル
html {
    overflow-y: auto !important;
    touch-action: manipulation;
}

// アプリケーションのルート
body .v-application {
    min-height: 100vh;
    min-height: 100dvh;
    font-family: 'YakuHanJPs', 'Open Sans', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
    font-weight: 500;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    // iOS Safari で 100vh にアドレスバーが含まれてしまう問題を回避する
    // iOS のヒラギノには Medium が搭載されていないため、Open Sans の font-weight を薄めに調整
    @supports (-webkit-touch-callout: none) {
        min-height: -webkit-fill-available;
        font-family: 'YakuHanJPs', 'Open Sans (for iOS Safari)', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
        font-weight: 400;
    }

    .v-application--wrap {
        min-height: 100% !important;
    }
}

// ヘッダー以外のメインコンテンツのルート
body main {
    display: flex;
    width: 100%;
    min-height: 100%;
}
body header + main {
    // ヘッダーの高さ分
    padding-top: 65px !important;
    @include smartphone-horizontal {
        padding-top: 0px !important;
    }
    // ボトムナビゲーションバーの高さ分
    @include smartphone-vertical {
        padding-top: 0px !important;
        padding-bottom: 56px !important;
    }
}

// ルートコンテナ
body .route-container {
    height: 100%;
    background: var(--v-background-base);
}

// ボタン内のテキストの字間をオフ
.v-btn {
    letter-spacing: 0 !important;
}

// スナックバーの表示時にナビゲーションバーの分だけ表示位置をずらす
// 揃えないと見栄えが悪い
.v-snack {
    left: calc(220px / 2) !important;
    @include tablet-vertical {
        left: 0 !important;
    }
    @include smartphone-horizontal {
        left: 0 !important;
    }
    @include smartphone-vertical {
        left: 0 !important;
    }
    .v-btn__content {
        color: var(--v-primary-lighten1);
        letter-spacing: 0.3;
    }
    .success, .info, .warning, .error {
        .v-btn__content {
            color: var(--v-text-base);
            letter-spacing: 0.3;
        }
    }
    &:not(.v-snack--absolute) {
        height: 100dvh !important;
    }
}

// ダイヤログ
.v-dialog {
    @include smartphone-vertical {
        margin: 24px 6px !important;
        &--fullscreen {
            margin: 0 !important;
        }
    }
}

// ツールチップのスタイル
.v-popper--theme-tooltip {
    .v-popper__inner {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        background: var(--v-background-lighten1);
        color: var(--v-text-base);
        font-size: 12px;
        font-family: 'YakuHanJPs', 'Open Sans', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
        font-weight: 500;
        opacity: 0.9;
        line-height: 22px;
    }
    .v-popper__arrow-container {
        display: none;
    }
}

// タッチデバイスで hover を無効にする
// ref: https://github.com/vuetifyjs/vuetify/issues/2178
@media (hover: none) {
    :hover:before {
        background-color: transparent !important;
    }
}

// 選択時の色
*::selection {
	background-color: #E64F9780;
}

// 記号の装飾
.decorate-symbol {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    position: relative;
    padding: 0px 3px;
    margin-left: 2.5px;
    margin-right: 2.5px;
    border-radius: 4px;
    color: var(--v-text-base);
    background: var(--v-primary-base);
    font-size: 0.94em;
}

// スクロールバー
* {
    scrollbar-color: var(--v-gray-base) var(--v-background-base);
    scrollbar-width: thin;
}
::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
::-webkit-scrollbar-track {
    background: var(--v-background-base);
}
::-webkit-scrollbar-thumb {
    background: var(--v-background-lighten2);
    &:hover {
        background: var(--v-gray-base);
    }
}

.v-menu__content {
    &::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    &::-webkit-scrollbar-thumb {
        border: solid 3.5px var(--v-background-base);
    }
}

// ページ遷移アニメーション
.v-enter-active, .v-leave-active {
    transition: opacity 0.3s;
}
.v-enter, .v-leave-to {
    opacity: 0;
}
.v-enter-active.route-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
}

// カーソルをポインターにするやつ
.cursor-pointer {
    cursor: pointer;
}

// ユーティリティ
.w-25 {
    width: 25%;
}
.w-50 {
    width: 50%;
}
.w-75 {
    width: 75%;
}
.w-100 {
    width: 100%;
}
.h-25 {
    height: 25%;
}
.h-50 {
    height: 50%;
}
.h-75 {
    height: 75%;
}
.h-100 {
    height: 100%;
}

</style>