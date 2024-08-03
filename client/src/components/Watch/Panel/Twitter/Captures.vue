<template>
    <div class="tab-content tab-content--capture">
        <v-dialog content-class="zoom-capture-modal-container" max-width="980" transition="slide-y-transition"
            v-model="player_store.twitter_zoom_capture_modal">
            <div class="zoom-capture-modal">
                <img class="zoom-capture-modal__image"
                    :src="player_store.twitter_zoom_capture ? player_store.twitter_zoom_capture.image_url: ''">
                <a v-ripple class="zoom-capture-modal__download"
                    :href="player_store.twitter_zoom_capture ? player_store.twitter_zoom_capture.image_url : ''"
                    :download="player_store.twitter_zoom_capture ? player_store.twitter_zoom_capture.filename : ''">
                    <Icon icon="fa6-solid:download" width="45px" />
                </a>
            </div>
        </v-dialog>
        <div class="captures">
            <div class="capture" :class="{
                    'capture--selected': capture.selected,
                    'capture--focused': capture.focused,
                    'capture--disabled': !capture.selected && player_store.twitter_selected_capture_blobs.length >= 4,
                }"
                v-for="capture in player_store.twitter_captures" :key="capture.image_url"
                @click="clickCapture(capture)">
                <!-- 以下では Icon コンポーネントを使うと個数が多いときに高負荷になるため、意図的に SVG を直書きしている -->
                <img class="capture__image" :src="capture.image_url">
                <div class="capture__disabled-cover"></div>
                <div class="capture__selected-number">{{player_store.twitter_selected_capture_blobs.findIndex(blob => blob === capture.blob) + 1}}</div>
                <svg class="capture__selected-checkmark iconify iconify--fluent" width="1em" height="1em" viewBox="0 0 16 16">
                    <path fill="currentColor" d="M8 2a6 6 0 1 1 0 12A6 6 0 0 1 8 2Zm2.12 4.164L7.25 9.042L5.854 7.646a.5.5 0 1 0-.708.708l1.75 1.75a.5.5 0 0 0 .708 0l3.224-3.234a.5.5 0 0 0-.708-.706Z"></path>
                </svg>
                <div class="capture__selected-border"></div>
                <div class="capture__focused-border"></div>
                <div v-ripple class="capture__zoom"
                    @click.prevent.stop="player_store.twitter_zoom_capture_modal = true; player_store.twitter_zoom_capture = capture"
                    @mousedown.prevent.stop=""> <!-- ← 親要素の波紋が広がらないように -->
                    <svg class="iconify iconify--fluent" width="32px" height="32px" viewBox="0 0 16 16">
                        <path fill="currentColor" d="M7 4.5a.5.5 0 0 0-1 0V6H4.5a.5.5 0 0 0 0 1H6v1.5a.5.5 0 0 0 1 0V7h1.5a.5.5 0 0 0 0-1H7V4.5ZM6.5 11a4.481 4.481 0 0 0 2.809-.984l3.837 3.838a.5.5 0 0 0 .708-.708L10.016 9.31A4.5 4.5 0 1 0 6.5 11Zm0-8a3.5 3.5 0 1 1 0 7a3.5 3.5 0 0 1 0-7Z"></path>
                    </svg>
                </div>
            </div>
        </div>
        <div class="capture-announce" v-show="player_store.twitter_captures.length === 0">
            <div class="capture-announce__heading">まだキャプチャがありません。</div>
            <div class="capture-announce__text">
                <p class="mt-0 mb-0">プレイヤーのキャプチャボタンやショートカットキーでキャプチャを撮ると、ここに表示されます。</p>
                <p class="mt-2 mb-0">表示されたキャプチャを選択してからツイートすると、キャプチャを付けてツイートできます。</p>
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { ITweetCapture } from '@/components/Watch/Panel/Twitter.vue';
import usePlayerStore from '@/stores/PlayerStore';

const player_store = usePlayerStore();

// キャプチャリスト内のキャプチャがクリックされたときのイベント
function clickCapture(capture: ITweetCapture) {

    // 選択されたキャプチャが3枚まで & まだ選択されていないならキャプチャをツイート対象に追加する
    if (player_store.twitter_selected_capture_blobs.length < 4 && capture.selected === false) {
        capture.selected = true;
        player_store.twitter_selected_capture_blobs.push(capture.blob);
    } else {
        // ツイート対象のキャプチャになっていたら取り除く
        player_store.twitter_selected_capture_blobs = player_store.twitter_selected_capture_blobs.filter(blob => blob !== capture.blob);
        // キャプチャの選択を解除
        capture.selected = false;
    }
}

</script>
<style lang="scss">

// 上書きしたいスタイル
@include smartphone-horizontal {
    .zoom-capture-modal-container {
        width: auto !important;
        max-width: auto !important;
        aspect-ratio: 16 / 9;
    }
}

</style>
<style lang="scss" scoped>

.zoom-capture-modal {
    position: relative;

    &__image {
        display: block;
        width: 100%;
        border-radius: 11px;
    }

    &__download {
        display: flex;
        position: absolute;
        align-items: center;
        justify-content: center;
        right: 22px;
        bottom: 20px;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        color: rgb(var(--v-theme-text));
        filter: drop-shadow(0px 0px 4.5px rgba(0, 0, 0, 90%));
    }
}

.tab-content--capture {
    @include tablet-vertical {
        padding-top: 16px;
    }
    @include smartphone-horizontal {
        padding-top: 8px;
    }
    @include smartphone-vertical {
        padding-top: 8px;
    }
}

.captures {
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-row-gap: 12px;
    grid-column-gap: 12px;
    padding-left: 12px;
    padding-right: 6px;
    max-height: 100%;
    // iOS Safari のみ
    @supports (-webkit-touch-callout: none) {
        padding-right: 12px;
    }
    @include tablet-vertical {
        grid-template-columns: 1fr 1fr 1fr;
        padding-left: 24px;
        padding-right: 24px;
        grid-row-gap: 10px;
        grid-column-gap: 16px;
    }
    @include smartphone-horizontal {
        grid-row-gap: 8px;
        grid-column-gap: 8px;
    }
    @include smartphone-vertical {
        grid-template-columns: 1fr 1fr 1fr;
        grid-row-gap: 10px;
        grid-column-gap: 10px;
    }

    .capture {
        position: relative;
        height: 82px;
        border-radius: 11px;
        // 読み込まれるまでのキャプチャの背景
        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
        overflow: hidden;
        user-select: none;
        cursor: pointer;
        content-visibility: auto;
        @include tablet-vertical {
            height: 90px;
            border-radius: 9px;
            .capture__image {
                object-fit: cover;
            }
        }
        @include smartphone-horizontal {
            height: 74px;
            border-radius: 9px;
            .capture__image {
                object-fit: cover;
            }
        }
        @include smartphone-vertical {
            height: 82px;
            border-radius: 9px;
            .capture__image {
                object-fit: cover;
            }
        }

        &__image {
            display: block;
            width: 100%;
            height: 100%;
        }

        &__zoom {
            display: flex;
            align-items: center;
            justify-content: center;
            position: absolute;
            top: 1px;
            right: 3px;
            width: 38px;
            height: 38px;
            border-radius: 50%;
            filter: drop-shadow(0px 0px 2.5px rgba(0, 0, 0, 90%));
            cursor: pointer;
        }

        &__disabled-cover {
            display: none;
            align-items: center;
            justify-content: center;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(30, 19, 16, 50%);
        }

        &__selected-number {
            display: none;
            align-items: center;
            justify-content: center;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(30, 19, 16, 50%);
            font-size: 38px;
            text-shadow: 0px 0px 2.5px rgba(0, 0, 0, 90%)
        }

        &__selected-checkmark {
            display: none;
            position: absolute;
            top: 6px;
            left: 7px;
            width: 20px;
            height: 20px;
            color: rgb(var(--v-theme-primary));
        }

        &__selected-border {
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: 11px;
            border: 4px solid rgb(var(--v-theme-primary));
        }

        &__focused-border {
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: 11px;
            border: 4px solid rgb(var(--v-theme-secondary));
        }

        &--selected {
            .capture__selected-number, .capture__selected-checkmark, .capture__selected-border {
                display: flex;
            }
        }
        &--focused {
            .capture__focused-border {
                display: block;
            }
        }
        &--disabled {
            cursor: auto;
            .capture__disabled-cover {
                display: block;
            }
        }
    }
}

.capture-announce {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    height: 100%;
    padding-left: 12px;
    padding-right: 5px;
    @include tablet-vertical {
        padding-left: 24px;
        padding-right: 24px;
    }

    &__heading {
        font-size: 20px;
        font-weight: bold;
        @include smartphone-horizontal {
            font-size: 16px;
        }
    }
    &__text {
        margin-top: 12px;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 13.5px;
        text-align: center;
        @include smartphone-horizontal {
            font-size: 12px;
        }
    }
}

</style>