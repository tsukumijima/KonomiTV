<template>
    <div class="remote-control-container" :class="{'remote-control-container--showing': showing}">
        <div class="remote-control elevation-6">
            <div v-ripple class="remote-control__close d-flex align-center rounded-circle cursor-pointer px-2 py-2"
                @click="$emit('close')">
                <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
            </div>
            <div class="remote-control-data-broadcasting"
                :class="{'remote-control-data-broadcasting--disabled': !settingsStore.settings.tv_show_data_broadcasting}">
                <div class="remote-control__directional-key">
                    <button v-ripple class="remote-control-button-up" id="key1">
                        <Icon icon="fluent:chevron-up-12-filled" width="26px" height="26px"></Icon>
                    </button>
                    <button v-ripple class="remote-control-button-left" id="key3">
                        <Icon icon="fluent:chevron-left-12-filled" width="26px" height="26px"></Icon>
                    </button>
                    <button v-ripple class="remote-control-button-select" id="key18">
                        決定
                    </button>
                    <button v-ripple class="remote-control-button-right" id="key4">
                        <Icon icon="fluent:chevron-right-12-filled" width="26px" height="26px"></Icon>
                    </button>
                    <button v-ripple class="remote-control-button-down" id="key2">
                        <Icon icon="fluent:chevron-down-12-filled" width="26px" height="26px"></Icon>
                    </button>
                </div>
                <div class="remote-control__control-key">
                    <button v-ripple class="remote-control-button-data" id="key20">
                        <svg width="20px" height="20px" viewBox="0 0 512 512">
                            <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
                        </svg>
                        <span class="ml-1">データ</span>
                    </button>
                    <button v-ripple class="remote-control-button-back" id="key19">
                        <Icon icon="fluent:arrow-left-12-filled" width="20px" />
                        <span class="ml-1">戻る</span>
                    </button>
                    <button v-ripple class="remote-control-button-blue blue darken-3" id="key21">青</button>
                    <button v-ripple class="remote-control-button-red red darken-3" id="key22">赤</button>
                    <button v-ripple class="remote-control-button-green green darken-3" id="key23">緑</button>
                    <button v-ripple class="remote-control-button-yellow yellow darken-3" id="key24">黄</button>
                </div>
            </div>
            <div class="remote-control__number-key">
                <button v-ripple type="button" id="key6">1</button>
                <button v-ripple type="button" id="key7">2</button>
                <button v-ripple type="button" id="key8">3</button>
                <button v-ripple type="button" id="key9">4</button>
                <button v-ripple type="button" id="key10">5</button>
                <button v-ripple type="button" id="key11">6</button>
                <button v-ripple type="button" id="key12">7</button>
                <button v-ripple type="button" id="key13">8</button>
                <button v-ripple type="button" id="key14">9</button>
                <button v-ripple type="button" id="key15">10</button>
                <button v-ripple type="button" id="key16">11</button>
                <button v-ripple type="button" id="key17">12</button>
            </div>
            <span class="remote-control-receiving-status" style="display: none;">Loading...</span>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue, { PropType } from 'vue';

import useSettingsStore from '@/store/SettingsStore';


export default Vue.extend({
    name: 'Panel-Remocon',
    props: {
        // リモコンのモーダルを表示するか
        showing: {
            type: Boolean as PropType<Boolean>,
            required: true,
        }
    },
    computed: {
        // SettingsStore に this.settingsStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useSettingsStore),
    }
});

</script>
<style lang="scss" scoped>

.remote-control-container {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    padding: 12px;
    background: rgba(30, 19, 16, 50%);
    transition: opacity 0.2s, visibility 0.2s;
    overflow-y: scroll;
    opacity: 0;
    visibility: hidden;
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
        background: var(--v-background-base);
        user-select: none;

        .remote-control__close {
            position: absolute !important;
            top: 10px;
            right: 10px;
            width: 36px;
            height: 36px;
        }

        .remote-control-data-broadcasting {
            &--disabled {
                opacity: 0.4;
                pointer-events: none;
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
                background: var(--v-background-lighten1);
                overflow: hidden;

                button {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 8px;
                    background: var(--v-background-lighten1);
                    color: var(--v-text-base);
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
                        background: var(--v-background-base);
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
                    background: var(--v-background-lighten1);
                    color: var(--v-text-base);
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
                background: var(--v-background-lighten1);
                color: var(--v-text-base);
                font-size: 26px;
                font-weight: bold;
                outline: none;
            }
        }
    }
}

</style>