<template>
    <v-app id="app">
        <transition>
            <router-view/>
        </transition>
    </v-app>
</template>

<style lang="scss">
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

// スクロールバー
::-webkit-scrollbar {
    width: 12px;
}
::-webkit-scrollbar-track {
    background: var(--v-background-base);
}
::-webkit-scrollbar-thumb {
    background: var(--v-gray-base);
}
::-webkit-scrollbar-thumb:hover {
    background: var(--v-background-lighten2);
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
