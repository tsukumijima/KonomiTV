<template>
    <div class="remote-control-container" :class="{'remote-control-container--showing': modelValue}"
        @click="$emit('update:modelValue', false)">
        <div class="remote-control elevation-6" @click.stop>
            <div v-ripple class="remote-control__close d-flex align-center rounded-circle cursor-pointer px-2 py-2"
                @click="$emit('update:modelValue', false)">
                <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
            </div>
            <div class="remote-control-data-broadcasting remote-control-data-broadcasting--disabled">
                <v-progress-circular indeterminate size="60" width="6" class="remote-control__loading"></v-progress-circular>
                <div class="remote-control__directional-key">
                    <button v-ripple class="remote-control-button-up" data-arib-key-code="1">
                        <Icon icon="fluent:chevron-up-12-filled" width="26px" height="26px"></Icon>
                    </button>
                    <button v-ripple class="remote-control-button-left" data-arib-key-code="3">
                        <Icon icon="fluent:chevron-left-12-filled" width="26px" height="26px"></Icon>
                    </button>
                    <button v-ripple class="remote-control-button-select" data-arib-key-code="18">
                        決定
                    </button>
                    <button v-ripple class="remote-control-button-right" data-arib-key-code="4">
                        <Icon icon="fluent:chevron-right-12-filled" width="26px" height="26px"></Icon>
                    </button>
                    <button v-ripple class="remote-control-button-down" data-arib-key-code="2">
                        <Icon icon="fluent:chevron-down-12-filled" width="26px" height="26px"></Icon>
                    </button>
                </div>
                <div class="remote-control__control-key">
                    <button v-ripple class="remote-control-button-data" data-arib-key-code="20">
                        <svg width="20px" height="20px" viewBox="0 0 512 512">
                            <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
                        </svg>
                        <span class="ml-1">データ</span>
                    </button>
                    <button v-ripple class="remote-control-button-back" data-arib-key-code="19">
                        <Icon icon="fluent:chevron-left-12-filled" width="20px" />
                        <span class="ml-1">戻る</span>
                    </button>
                    <button v-ripple class="remote-control-button-blue bg-blue-darken-3" data-arib-key-code="21">青</button>
                    <button v-ripple class="remote-control-button-red bg-red-darken-3" data-arib-key-code="22">赤</button>
                    <button v-ripple class="remote-control-button-green bg-green-darken-3" data-arib-key-code="23">緑</button>
                    <button v-ripple class="remote-control-button-yellow bg-yellow-darken-3 text-text" data-arib-key-code="24">黄</button>
                </div>
            </div>
            <div class="remote-control__number-key">
                <button v-ripple data-remocon-id="1" data-arib-key-code="6">1</button>
                <button v-ripple data-remocon-id="2" data-arib-key-code="7">2</button>
                <button v-ripple data-remocon-id="3" data-arib-key-code="8">3</button>
                <button v-ripple data-remocon-id="4" data-arib-key-code="9">4</button>
                <button v-ripple data-remocon-id="5" data-arib-key-code="10">5</button>
                <button v-ripple data-remocon-id="6" data-arib-key-code="11">6</button>
                <button v-ripple data-remocon-id="7" data-arib-key-code="12">7</button>
                <button v-ripple data-remocon-id="8" data-arib-key-code="13">8</button>
                <button v-ripple data-remocon-id="9" data-arib-key-code="14">9</button>
                <button v-ripple data-remocon-id="10" data-arib-key-code="15">10</button>
                <button v-ripple data-remocon-id="11" data-arib-key-code="16">11</button>
                <button v-ripple data-remocon-id="12" data-arib-key-code="17">12</button>
            </div>
        </div>
    </div>
</template>
<script lang="ts">

import { defineComponent, PropType } from 'vue';

export default defineComponent({
    name: 'Panel-Remocon',
    props: {
        modelValue: {
            type: Boolean as PropType<boolean>,
            required: true,
        }
    },
    emits: {
        'update:modelValue': (value: boolean) => true,
    },
});

</script>
<style lang="scss" scoped>

.remote-control-container {
    display: grid;
    place-items: center;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(30, 19, 16, 50%);
    transition: opacity 0.2s, visibility 0.2s;
    overflow-y: scroll;
    opacity: 0;
    visibility: hidden;
    z-index: 20;
    &--showing {
        opacity: 1;
        visibility: visible;
    }

    .remote-control {
        position: relative;
        width: 234px;
        height: 514px;
        padding: 24px 16px;
        margin: 0 auto;
        border-radius: 8px;
        background: rgb(var(--v-theme-background));
        user-select: none;

        .remote-control__close {
            position: absolute !important;
            top: 10px;
            right: 10px;
            width: 36px;
            height: 36px;
            z-index: 2;
        }

        .remote-control-data-broadcasting {
            position: relative;
            opacity: 1;
            transition: opacity 0.2s ease;

            &--disabled {
                opacity: 0.4;
                pointer-events: none;
            }
            &--loading {
                opacity: 0.4;
                pointer-events: none;
                .remote-control__loading {
                    opacity: 1 !important;
                    visibility: visible !important;
                }
            }

            .remote-control__loading {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: rgb(var(--v-theme-gray));
                filter: drop-shadow(0px 0px 3px rgba(0, 0, 0, 0.3));
                opacity: 0;
                visibility: hidden;
                transition: opacity 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94), visibility 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94);
                will-change: opacity;
                z-index: 21;
            }

            .remote-control__directional-key {
                display: grid;
                grid-template-columns: 1fr 90px 1fr;
                grid-template-rows: 1fr 90px 1fr;
                width: 160px;
                height: 160px;
                margin-left: auto;
                margin-right: auto;
                border-radius: 50%;
                background: rgb(var(--v-theme-background-lighten-1));
                overflow: hidden;

                button {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 8px;
                    background: rgb(var(--v-theme-background-lighten-1));
                    color: rgb(var(--v-theme-text));
                    font-size: 14px;
                    font-weight: bold;
                    outline: none;
                    &.remote-control-button-up {
                        grid-column: 2;
                        grid-row: 1;
                        padding-top: 4px;
                    }
                    &.remote-control-button-left {
                        grid-column: 1;
                        grid-row: 2;
                        padding-left: 4px;
                    }
                    &.remote-control-button-select {
                        grid-column: 2;
                        grid-row: 2;
                        border-radius: 50%;
                        background: rgb(var(--v-theme-background));
                    }
                    &.remote-control-button-right {
                        grid-column: 3;
                        grid-row: 2;
                        padding-right: 4px;
                    }
                    &.remote-control-button-down {
                        grid-column: 2;
                        grid-row: 3;
                        padding-bottom: 4px;
                    }
                }
            }

            .remote-control__control-key {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr 1fr;
                grid-template-rows: 35px 35px;
                gap: 8px;
                width: 200px;
                margin-top: 12px;
                margin-left: auto;
                margin-right: auto;
                button {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 5px;
                    background: rgb(var(--v-theme-background-lighten-1));
                    color: rgb(var(--v-theme-text));
                    font-size: 15px;
                    font-weight: bold;
                    outline: none;
                    &.remote-control-button-data {
                        grid-column: 1 / 3;
                        grid-row: 1;
                    }
                    &.remote-control-button-back {
                        grid-column: 3 / 5;
                        grid-row: 1;
                    }
                }
            }
        }

        .remote-control__number-key {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-template-rows: 44px 44px 44px 44px;
            gap: 8px;
            width: 200px;
            margin-top: 16px;
            margin-left: auto;
            margin-right: auto;
            button {
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 5px;
                background: rgb(var(--v-theme-background-lighten-1));
                color: rgb(var(--v-theme-text));
                font-size: 26px;
                font-weight: bold;
                outline: none;
            }
        }
    }
}

</style>