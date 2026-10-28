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

// キャプチャの各画面で共通の、読み込み中と空の状態の表示
// すべてのキャプチャの画面に適用されるよう、各画面の共通の外枠であるこのコンポーネントに定義する
// どちらも見出しより下の残りの領域いっぱいに広げ、その中央に配置する
// 文字サイズは、録画番組の一覧 (RecordedProgramList.vue) の空の状態の表示に合わせる
.capture-loading, .capture-empty {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    // 外枠の下端には一覧の末尾用の余白 (60px) があるため、上側にも同程度の余白を確保し、表示領域の上下中央に配置する
    padding: 44px 12px 0px;
    text-align: center;
}
.capture-loading {
    color: rgb(var(--v-theme-text-darken-1));
}
.capture-empty {
    &__icon {
        color: rgb(var(--v-theme-text-darken-1));
    }
    &__message {
        margin-top: 8px;
        font-size: 21px;
        font-weight: 700;
        @include tablet-vertical {
            font-size: 19px;
        }
        @include smartphone-horizontal {
            font-size: 19px;
        }
        @include smartphone-vertical {
            font-size: 19px;
        }
    }
    &__sub {
        margin-top: 8px;
        font-size: 15px;
        color: rgb(var(--v-theme-text-darken-1));
        @include tablet-vertical {
            font-size: 13px;
        }
        @include smartphone-horizontal {
            font-size: 13px;
        }
        @include smartphone-vertical {
            margin-top: 7px;
            font-size: 13px;
            line-height: 1.65;
        }
    }
}

</style>
