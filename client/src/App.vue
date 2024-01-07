<template>
    <v-app id="app">
        <transition>
            <router-view/>
        </transition>
        <Snackbars />
    </v-app>
</template>
<script lang="ts" setup>

import Snackbars from '@/components/Snackbars.vue';

</script>
<style lang="scss">

// ***** ブラウザのデフォルトスタイルの上書き *****

// スクロールバーのスタイル
* {
    scrollbar-color: rgb(var(--v-theme-gray)) rgb(var(--v-theme-background));
    scrollbar-width: thin;
}
::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
::-webkit-scrollbar-track {
    background: rgb(var(--v-theme-background));
}
::-webkit-scrollbar-thumb {
    background: rgb(var(--v-theme-background-lighten-2));
    &:hover {
        background: rgb(var(--v-theme-gray));
    }
}

// Android でタップしたときのハイライトが出ないようにする
* {
    -webkit-tap-highlight-color: transparent;
}

// タッチデバイスで hover を無効にする
@media (hover: none) {
    :hover:before {
        background-color: transparent !important;
    }
}

// 選択時の色
*::selection {
	background-color: #E64F9780;
}

// リンクの既定の CSS をリセット
a, a:link, a:visited, a:hover, a:active {
    color: inherit;
    text-decoration: none;
}

// ***** SPA 全体に適用されるスタイル *****

// ページ遷移アニメーション
.v-enter-active, .v-leave-active {
    transition: opacity 0.25s;
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

// 全体のスタイル
html {
    position: static !important;  // Vuetify による fixed への書き換えを防止する
    overflow-y: auto !important;
    touch-action: manipulation;
}

// アプリケーションのルート
.v-application {
    min-height: 100vh;
    min-height: 100dvh;
    font-family: 'Open Sans', 'YakuHanJPs', 'Twemoji', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
    font-weight: 500;
    overflow-x: clip;  // clip なら position: sticky; が効く
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background: rgb(var(--v-theme-background)) !important;
    color: rgb(var(--v-theme-text)) !important;

    // Safari は Twemoji COLR をうまく描画できない？ので当面無効にする
    @supports (-webkit-touch-callout: none) {
        font-family: 'Open Sans', 'YakuHanJPs', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
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
        padding-bottom: calc(env(safe-area-inset-bottom) + 56px) !important;
    }
}

// ルートコンテナ
body .route-container {
    height: 100%;
    background: rgb(var(--v-theme-background));
}

// ***** Vuetify 3 のスタイルの上書き *****

// ツールチップのスタイル
.v-popper--theme-tooltip {
    .v-popper__inner {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        background: rgb(var(--v-theme-background-lighten-1));
        color: rgb(var(--v-theme-text));
        font-size: 12px;
        font-family: 'Open Sans', 'YakuHanJPs', 'Twemoji', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
        font-weight: 500;
        opacity: 0.9;
        line-height: 22px;
    }
    .v-popper__arrow-container {
        display: none;
    }
}

// ボタン内のテキストの字間をオフ
// 大文字への強制変換をオフ
.v-btn {
    letter-spacing: 0 !important;
    text-transform: none !important;
}

// v-btn に hover したときの transition が効かなくなっている Vuetify 3 のバグを打ち消す
// ref: https://github.com/vuetifyjs/vuetify/blob/v3.4.9/packages/vuetify/src/components/VBtn/VBtn.sass#L233
.v-btn__overlay {
    transition: opacity 0.2s ease-in-out;
}

// オーバーレイのスタイルを Vuetify 2 に合わせる (既定の --v-theme-on-surface では明るすぎる)
.v-overlay__content {
    @include smartphone-vertical {
        margin: 24px 6px !important;
        width: calc(100% - 12px) !important;
        max-width: calc(100% - 12px) !important;
        &--fullscreen {
            margin: 0 !important;
        }
    }
}
.v-overlay__scrim {
    background: rgb(33, 33, 33) !important;
    opacity: 0.46 !important;
}

// スライダーのつまみのラベルの色を Vuetify 2 に合わせる
.v-slider-thumb__label {
    background: rgb(var(--v-theme-primary)) !important;
    color: rgb(var(--v-theme-text)) !important;
}

// カードテキストのテキストスタイルを Vuetify 2 に合わせる
.v-card-text {
    color: rgb(var(--v-theme-text-darken-1)) !important;
    font-size: .875rem !important;
    font-weight: inherit !important;
    line-height: 1.375rem !important;
    letter-spacing: .0071428571em !important;
}

// density が compact のときのフォントサイズを Vuetify 2 に合わせる
.v-input--density-compact input {
    font-size: 14px !important;
}

// TODO: 以下は Vuetify 3 向けに改修が必要

.v-menu__content {
    @include smartphone-vertical {
        .v-list {
            background-color: rgb(var(--v-theme-background-lighten-1)) !important;
        }
    }
    &::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    &::-webkit-scrollbar-thumb {
        border: solid 3.5px rgb(var(--v-theme-background));
    }
}

// ***** ユーティリティクラス *****

// リンク用のスタイル
.link {
    color: rgb(var(--v-theme-primary)) !important;
    text-decoration: underline !important;
    cursor: pointer;

    &:visited {
        color: rgb(var(--v-theme-primary-darken-1)) !important;
    }
}

// 番組情報内の囲み文字の装飾
.decorate-symbol {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    position: relative;
    padding: 0px 3px;
    margin-left: 2.5px;
    margin-right: 2.5px;
    border-radius: 4px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-primary));
    font-size: 0.94em;
}

// スマホ縦画面 (幅が 600px 以下の端末) のみ表示する <br> タグ
.br-smartphone-only {
    display: none;
    @include smartphone-vertical {
        display: inline;
    }
}

// カーソルをポインターにする
.cursor-pointer {
    cursor: pointer;
}

</style>