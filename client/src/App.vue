<template>
    <v-app id="app">
        <router-view v-slot="{ Component }">
            <component :is="Component" />
        </router-view>
        <Snackbars />
    </v-app>
</template>
<script lang="ts" setup>

import Snackbars from '@/components/Snackbars.vue';

</script>
<style lang="scss">

// ***** ブラウザのデフォルトスタイルの上書き *****

// スクロールバーのスタイル
// なるべく ::webkit-scrollbar を優先させるため、::webkit-scrollbar 未対応の Firefox でのみ scrollbar-color/width を有効化する
@supports (-moz-appearance: none) {
    * {
        scrollbar-color: rgb(var(--v-theme-gray)) rgb(var(--v-theme-background));
        scrollbar-width: thin;
    }
}
::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
::-webkit-scrollbar-track, ::-webkit-scrollbar-corner {
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

// ページ遷移アニメーション (View Transitions API)
// ref: https://developer.mozilla.org/ja/docs/Web/API/View_Transitions_API
::view-transition-old(root),
::view-transition-new(root) {
    animation-duration: 0.25s;  // 0.25 秒クロスフェード
}

// 全体のスタイル
html {
    overflow-y: auto !important;
    touch-action: manipulation;
    overscroll-behavior-x: none;

    // scrollbar-gutter: stable を指定すると、overflow: hidden 指定時にもスクロールバー分の領域が確保される
    // もっと早くに知りたかった…
    // ref: https://ics.media/entry/230206/
    scrollbar-gutter: stable;
    &:has(.watch-container), &:has(.timetable-container) {
        // 視聴画面・番組表では全体のスクロールバーが不要なため、スクロールバー分の領域を確保しない
        scrollbar-gutter: auto;
    }
    @media all and (display-mode: picture-in-picture) {
        // Document Picture-in-Picture モードでは全体のスクロールバーが不要なため、スクロールバー分の領域を確保しない
        scrollbar-gutter: auto;
    }

    // Vuetify 3 では position: fixed でモーダル表示時のスクロールを防止しようとしているが、これだとレイアウトがぶっ壊れるので使えない
    // そのため position を static に固定して、代わりに overflow: hidden でスクロールを防止する
    // iOS 16 から Safari でも overflow: hidden でスクロールを防止できるようになったため問題ない
    // ref: https://zenn.dev/lclco/articles/f5b20817a15b9a
    &.v-overlay-scroll-blocked {
        position: static !important;
        overflow: hidden !important;
    }

    // 番組表のジャンルハイライトカラー (REGZA 風)
    // TimeTable.vue と TimeTableSettings.vue 共通で使う
    --timetable-genre-highlight-white: #ffffff;
    --timetable-genre-background-white: #f8f8f8;
    --timetable-genre-highlight-pink: #f50094;
    --timetable-genre-background-pink: #f6eaef;
    --timetable-genre-highlight-red: #e1512d;
    --timetable-genre-background-red: #ffecec;
    --timetable-genre-highlight-orange: #ff9800;
    --timetable-genre-background-orange: #fff3e0;
    --timetable-genre-highlight-yellow: #ffeb3b;
    --timetable-genre-background-yellow: #fffde7;
    --timetable-genre-highlight-lime: #8bc34a;
    --timetable-genre-background-lime: #f1f8e9;
    --timetable-genre-highlight-teal: #009688;
    --timetable-genre-background-teal: #e0f2f1;
    --timetable-genre-highlight-cyan: #03a9f4;
    --timetable-genre-background-cyan: #e1f5fe;
    --timetable-genre-highlight-blue: #4e7ac1;
    --timetable-genre-background-blue: #eff3fb;
    --timetable-genre-highlight-ochre: #c59a2f;
    --timetable-genre-background-ochre: #fdf5e2;
    --timetable-genre-highlight-brown: #a3421f;
    --timetable-genre-background-brown: #fff2eb;
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

// ***** Vuetify 3 のスタイルの上書き *****

// font-weight を 400 から 500 に変更
.v-list-item-title {
    font-weight: 500 !important;
}
.v-input, .v-input__details {
    font-weight: 500 !important;
}

// カードテキストのテキストスタイルを Vuetify 2 に合わせる
.v-card-text {
    color: rgb(var(--v-theme-text-darken-1)) !important;
    font-size: .875rem !important;
    font-weight: inherit !important;
    line-height: 1.375rem !important;
    letter-spacing: .0071428571em !important;
}

// オーバーレイのスタイルを Vuetify 2 に合わせる (既定の --v-theme-on-surface では明るすぎる)
.v-overlay-container {
    font-family: 'Open Sans', 'YakuHanJPs', 'Twemoji', 'Hiragino Sans', 'Noto Sans JP', sans-serif;
    font-weight: 500;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    color: rgb(var(--v-theme-text)) !important;
}
.v-overlay__scrim {
    background: rgb(33, 33, 33) !important;
    opacity: 0.46 !important;
}

// スマホ縦画面でのダイヤログの表示幅を広げる
.v-dialog .v-overlay__content {
    @include smartphone-vertical {
        margin: 24px 6px !important;
        width: calc(100% - 12px) !important;
        max-width: calc(100% - 12px) !important;
        &--fullscreen {
            margin: 0 !important;
        }
    }
}

// ボタン内のテキストの字間をオフ
// 大文字への強制変換をオフ
.v-btn {
    letter-spacing: 0 !important;
    text-transform: none !important;
}

// ボタンに hover したときの transition が効かなくなっている Vuetify 3 のバグを打ち消す
// ref: https://github.com/vuetifyjs/vuetify/blob/v3.4.9/packages/vuetify/src/components/VBtn/VBtn.sass#L233
.v-btn__overlay {
    transition: opacity 0.2s ease-in-out;
}

// タッチデバイスでボタンへの hover を無効にする
@media (hover: none) {
    .v-btn:hover > .v-btn__overlay {
        opacity: 0 !important;
    }
}

// テキスト入力フォーム/セレクトボックスのボーダーの色を Vuetify 2 に合わせる
.v-field__outline {
    --v-field-border-opacity: 0.25 !important;
}
.v-field:hover .v-field__outline {
    --v-field-border-opacity: 0.5 !important;
}
.v-field.v-field--focused .v-field__outline {
    --v-field-border-opacity: 1 !important;
}

// テキスト入力フォーム/セレクトボックスの density が compact のときのフォントサイズを Vuetify 2 に合わせる
.v-input--density-compact {
    input, .v-field {
        font-size: 14px !important;
    }
}

// スライダーのつまみのラベルの色を Vuetify 2 に合わせる
.v-slider-thumb__label {
    background: rgb(var(--v-theme-primary)) !important;
    color: rgb(var(--v-theme-text)) !important;
    &:before {
        color: rgb(var(--v-theme-primary)) !important;
    }
}

// Progress Circular (indeterminate) のスタイルとアニメーション速度を Vuetify 2 に合わせる
.v-progress-circular--indeterminate {
    svg {
        .v-progress-circular__underlay {
            display: none !important;
        }
        .v-progress-circular__overlay {
            animation: progress-circular-dash 1.4s ease-in-out infinite !important;
        }
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

    // Safari でのみ display: inline に変更
    // Safari では -webkit-line-clamp と inline-flex/inline-block の組み合わせで
    // 省略が不要なテキストでも ... が表示されるレンダリングバグが発生するため
    @supports (hanging-punctuation: first) and (font: -apple-system-body) and (-webkit-appearance: none) {
        display: inline;
        padding-bottom: 0.045em;
    }
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