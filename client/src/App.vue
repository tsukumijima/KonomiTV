<template>
    <v-app id="app">
        <transition>
            <router-view/>
        </transition>
    </v-app>
</template>
<style lang="scss">

// 全体のスタイル
html {
    overflow-y: auto !important;
}

body .v-application {  // アプリケーションのルート
    min-height: 100vh;
    font-family: 'YakuHanJPs', 'Open Sans', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
    font-weight: 500;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    // iOS Safari で 100vh にアドレスバーが含まれてしまう問題を回避する
    @supports (-webkit-touch-callout: none) {
        min-height: -webkit-fill-available;
    }

    .v-application--wrap {
        min-height: 100% !important;
    }
}

body main {  // ヘッダー以外のメインコンテンツのルート
    display: flex;
    width: 100%;
    min-height: 100%;
}
body header + main {
    // ヘッダーの高さ分
    padding-top: 65px !important;
    @media screen and (max-height: 450px) {
        padding-top: 48px !important;
    }
}

body .route-container {  // ルートコンテナ
    height: 100%;
    background: var(--v-background-base);
}

// ツールチップのスタイル
.v-popper--theme-tooltip {
    .v-popper__inner {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        background: #2F221FC0;
        color: var(--v-text-base);
        font-size: 12px;
        font-family: "Open Sans", "Noto Sans JP", sans-serif;
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
    overflow: hidden;
    &::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    &::-webkit-scrollbar-track {
        background: #1E1E1E;
    }
    &::-webkit-scrollbar-thumb {
        border: solid 3.5px #1E1E1E;
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