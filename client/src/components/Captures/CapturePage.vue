<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <div class="capture-page" :class="{'capture-page--scrubber': withScrubber}">
                <Breadcrumbs :crumbs="crumbs" />
                <slot></slot>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';


withDefaults(defineProps<{
    crumbs: { name: string; path: string; disabled?: boolean }[];
    // 右端にスクラバーを出すページでは、その幅だけ右に余白を取る
    withScrubber?: boolean;
}>(), {
    withScrubber: false,
});

</script>
<style lang="scss" scoped>

.capture-page {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;  // サイドナビゲーション横のフレックス子要素を親幅内で縮め、はみ出しを防ぐ
    padding: 20px 28px 60px;
    // 日付の見出し・タブ・タイルなどの押して使う部品は、押したときに操作だけが働くよう、文字の選択を外す
    // 読んで写したくなる文 (番組概要など) だけ、それぞれの部品で選択できるように戻す
    user-select: none;
    @include smartphone-horizontal {
        padding: 16px 20px 60px !important;
    }
    // スマホの縦画面では、マイリストや視聴履歴と同じく上に 18px (10px + 8px)、左右に 8px を空ける
    @include smartphone-vertical {
        padding: 18px 8px 70px !important;
    }

    // PC ではスクラバーのレールの幅 (52px) だけ右に余白を取る (タッチの端末のつまみは画像の上に重ねる)
    &--scrubber {
        @media (pointer: fine) {
            padding-right: 60px;
        }
    }
}

</style>
<style lang="scss">

// キャプチャの画面で共通の、空の状態の表示
// どの画面から開いても当たるよう、すべてのキャプチャの画面が通るこの外枠に置く
.capture-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 16px;
    text-align: center;
    &__icon {
        color: rgb(var(--v-theme-text-darken-1));
    }
    &__message {
        margin-top: 16px;
        font-size: 19px;
        font-weight: 700;
        @include smartphone-vertical {
            font-size: 17px;
        }
    }
    &__sub {
        margin-top: 10px;
        font-size: 14px;
        line-height: 1.8;
        color: rgb(var(--v-theme-text-darken-1));
        @include smartphone-vertical {
            font-size: 13px;
        }
    }
}

</style>
