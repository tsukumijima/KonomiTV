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
body .v-application {
    min-height: 100vh;
    font-family: "Open Sans", "Noto Sans JP", sans-serif;
    font-weight: 500;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
body .v-main__wrap {
    display: flex;
    min-height: 100vh;
    padding-top: 65px !important;
}

// ツールチップのスタイル
.v-tooltip__content {
    padding: 4px 10px !important;
    background: #2F221FC0 !important;
    font-size: 12px !important;
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
    width: 10px;
    height: 10px;
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
