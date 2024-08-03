<template>
    <v-dialog max-width="1050" transition="slide-y-transition" v-model="playerStore.shortcut_key_modal">
        <v-card>
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="fluent:keyboard-20-filled" height="28px" />
                <span class="ml-3">キーボードショートカット</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="playerStore.shortcut_key_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <v-row>
                    <v-col cols="6" v-for="(shortcut_key_column, shortcut_key_column_name) in shortcut_list" :key="shortcut_key_column_name">
                        <div class="mt-3" v-for="shortcut_keys in shortcut_key_column" :key="shortcut_keys.name">
                            <div class="text-subtitle-1 d-flex align-center font-weight-bold">
                                <Icon v-if="shortcut_keys.name !== 'データ放送'" :icon="shortcut_keys.icon" :height="shortcut_keys.icon_height" />
                                <svg v-else width="24px" height="24px" viewBox="0 0 512 512">
                                    <path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" />
                                </svg>
                                <span class="ml-2">{{shortcut_keys.name}}</span>
                            </div>
                            <div class="mt-3" v-for="shortcut in shortcut_keys.shortcuts" :key="shortcut.name">
                                <div class="text-subtitle-2 mt-2 d-flex align-center font-weight-medium">
                                    <span class="mr-2" v-html="shortcut.name"></span>
                                    <div class="ml-auto d-flex align-center flex-shrink-0">
                                        <div class="ml-auto d-flex align-center" v-for="(key, index) in shortcut.keys" :key="key.name">
                                            <span class="shortcut-key">
                                                <Icon v-show="key.icon === true" :icon="key_name" height="18px"
                                                    v-for="key_name in key.name.split(';')" :key="key_name" />
                                                <span v-if="key.icon === false" v-html="key.name"></span>
                                            </span>
                                            <span class="shortcut-key-plus" v-if="index < (shortcut.keys.length - 1)">+</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </v-col>
                </v-row>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils from '@/utils';

interface IShortcutList {
    left_column: IShortcutGroup[];
    right_column: IShortcutGroup[];
}

interface IShortcutGroup {
    name: string;
    icon: string;
    icon_height: string;
    shortcuts: IShortcut[];
}

interface IShortcut {
    name: string;
    keys: {
        name: string;
        icon: boolean;
    }[];
}

// キーボードショートカットの一覧に表示するショートカットキーのリスト (ライブ視聴)
const LIVE_SHORTCUT_LIST: IShortcutList = {
    left_column: [
        {
            name: '全般',
            icon: 'fluent:home-20-filled',
            icon_height: '22px',
            shortcuts: [
                { name: '数字キー/テンキーに対応するリモコン番号 (1~12) の地デジチャンネルに切り替える', keys: [{name: '1~9, 0, -(=), ^(~)', icon: false}] },
                { name: '数字キー/テンキーに対応するリモコン番号 (1~12) の BS チャンネルに切り替える', keys: [{name: 'Shift', icon: false}, {name: '1~9, 0, -(=), ^(~)', icon: false}] },
                { name: '前のチャンネルに切り替える', keys: [{name: 'fluent:arrow-up-12-filled', icon: true}] },
                { name: '次のチャンネルに切り替える', keys: [{name: 'fluent:arrow-down-12-filled', icon: true}] },
                { name: 'キーボードショートカットの一覧を表示する', keys: [{name: '／(？)', icon: false}] },
            ]
        },
        {
            name: 'プレイヤー',
            icon: 'fluent:play-20-filled',
            icon_height: '20px',
            shortcuts: [
                { name: '再生 / 一時停止の切り替え', keys: [{name: 'Space', icon: false}] },
                { name: '再生 / 一時停止の切り替え (キャプチャタブ表示時)', keys: [{name: 'Shift', icon: false}, {name: 'Space', icon: false}] },
                { name: '停止して0.5秒早戻し', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-left-12-filled', icon: true}] },
                { name: '停止して0.5秒早送り', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-right-12-filled', icon: true}] },
                { name: 'プレイヤーの音量を上げる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-up-12-filled', icon: true}] },
                { name: 'プレイヤーの音量を下げる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-down-12-filled', icon: true}] },
                { name: 'プレイヤーの音量をミュートする', keys: [{name: 'Q', icon: false}] },
                { name: 'ライブストリームを同期する', keys: [{name: 'W', icon: false}] },
                { name: 'プレイヤーを再起動する', keys: [{name: 'R', icon: false}] },
                { name: 'フルスクリーンの切り替え', keys: [{name: 'F', icon: false}] },
                { name: 'Picture-in-Picture の表示切り替え', keys: [{name: 'E', icon: false}] },
                { name: '字幕の表示切り替え', keys: [{name: 'S', icon: false}] },
                { name: 'コメントの表示切り替え', keys: [{name: 'D', icon: false}] },
                { name: '映像をキャプチャする', keys: [{name: 'C', icon: false}] },
                { name: '映像をコメントを付けてキャプチャする', keys: [{name: 'V', icon: false}] },
                { name: 'コメント入力フォームにフォーカスする', keys: [{name: 'M', icon: false}] },
                { name: 'コメント入力フォームを閉じる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'M', icon: false}] },
                { name: 'コメントを送信する', keys: [{name: 'コメント入力フォームを表示', icon: false}, {name: 'Enter', icon: false}] },
            ]
        },
    ],
    right_column: [
        {
            name: 'パネル',
            icon: 'fluent:panel-right-20-filled',
            icon_height: '24px',
            shortcuts: [
                { name: 'パネルの表示切り替え', keys: [{name: 'P', icon: false}] },
                { name: '番組情報タブを表示する', keys: [{name: 'K', icon: false}] },
                { name: 'チャンネルタブを表示する', keys: [{name: 'L', icon: false}] },
                { name: 'コメントタブを表示する', keys: [{name: '；(＋)', icon: false}] },
                { name: 'Twitter タブを表示する', keys: [{name: '：(＊)', icon: false}] },
            ]
        },
        {
            name: 'Twitter',
            icon: 'fa-brands:twitter',
            icon_height: '22px',
            shortcuts: [
                { name: 'ツイート検索タブを表示する', keys: [{name: '［ (「)', icon: false}] },
                { name: 'タイムラインタブを表示する', keys: [{name: '］ (」)', icon: false}] },
                { name: 'キャプチャタブを表示する', keys: [{name: '_', icon: false}] },
                { name: '検索結果を更新する', keys: [{name: 'ツイート検索タブを表示', icon: false}, {name: '＼(｜)', icon: false}] },
                { name: 'タイムラインを更新する', keys: [{name: 'タイムラインタブを表示', icon: false}, {name: '＼(｜)', icon: false}] },
                { name: 'キャプチャにフォーカスする', keys: [{name: 'キャプチャタブを表示', icon: false}, {name: 'fluent:arrow-up-12-filled;fluent:arrow-down-12-filled;fluent:arrow-left-12-filled;fluent:arrow-right-12-filled', icon: true}] },
                { name: 'キャプチャを拡大表示する/<br>キャプチャの拡大表示を閉じる', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Enter', icon: false}] },
                { name: 'キャプチャを選択する/<br>キャプチャの選択を解除する', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Space', icon: false}] },
                { name: 'ツイート入力フォームにフォーカスを当てる/フォーカスを外す', keys: [{name: 'Tab', icon: false}] },
                { name: 'ツイートを送信する', keys: [{name: 'Twitter タブを表示', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'Enter', icon: false}] },
                { name: 'クリップボード内の画像を<br>キャプチャとして取り込む', keys: [{name: 'ツイート入力<br>フォームにフォーカス', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'V', icon: false}] },
            ]
        },
        {
            name: 'データ放送',
            icon: '',  // これだけアイコンが独自なので空にする
            icon_height: '',
            shortcuts: [
                { name: 'リモコンの <svg v-else width="17px" height="17px" style="margin-bottom: -2.5px;" viewBox="0 0 512 512"><path fill="currentColor" d="M248.039 381.326L355.039 67.8258C367.539 28.3257 395.039 34.3258 406.539 34.3258C431.039 34.3258 453.376 61.3258 441.039 96.8258C362.639 322.426 343.539 375.326 340.539 384.826C338.486 391.326 342.039 391.326 345.539 391.326C377.039 391.326 386.539 418.326 386.539 435.326C386.539 458.826 371.539 477.326 350.039 477.326H214.539C179.039 477.326 85.8269 431.3 88.0387 335.826C91.0387 206.326 192.039 183.326 243.539 183.326H296.539L265.539 272.326H243.539C185.539 272.326 174.113 314.826 176.039 334.326C180.039 374.826 215.039 389.814 237.039 390.326C244.539 390.5 246.039 386.826 248.039 381.326Z" /></svg> ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'D', icon: false}] },
                { name: 'リモコンの戻るボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'Backspace', icon: false}] },
                { name: 'リモコンの決定ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'Enter', icon: false}] },
                { name: 'リモコンの ⬆ ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'fluent:arrow-up-12-filled', icon: true}] },
                { name: 'リモコンの ⬅️ ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'fluent:arrow-left-12-filled', icon: true}] },
                { name: 'リモコンの ➡ ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'fluent:arrow-right-12-filled', icon: true}] },
                { name: 'リモコンの ⬇ ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'fluent:arrow-down-12-filled', icon: true}] },
                { name: 'リモコンの 🟦 ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'F9', icon: false}] },
                { name: 'リモコンの 🟥 ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'F10', icon: false}] },
                { name: 'リモコンの 🟩 ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'F11', icon: false}] },
                { name: 'リモコンの 🟨 ボタンを押す', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'F12', icon: false}] },
            ]
        },
    ],
};

// キーボードショートカットの一覧に表示するショートカットキーのリスト (ビデオ視聴)
const VIDEO_SHORTCUT_LIST: IShortcutList = {
    left_column: [
        {
            name: '全般',
            icon: 'fluent:home-20-filled',
            icon_height: '22px',
            shortcuts: [
                { name: 'キーボードショートカットの一覧を表示する', keys: [{name: '／(？)', icon: false}] },
            ]
        },
        {
            name: 'プレイヤー',
            icon: 'fluent:play-20-filled',
            icon_height: '20px',
            shortcuts: [
                { name: '再生 / 一時停止の切り替え', keys: [{name: 'Space', icon: false}] },
                { name: '再生 / 一時停止の切り替え (キャプチャタブ表示時)', keys: [{name: 'Shift', icon: false}, {name: 'Space', icon: false}] },
                { name: '5秒早戻し', keys: [{name: 'fluent:arrow-left-12-filled', icon: true}] },
                { name: '5秒早送り', keys: [{name: 'fluent:arrow-right-12-filled', icon: true}] },
                { name: '15秒早戻し', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-left-12-filled', icon: true}] },
                { name: '15秒早送り', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-right-12-filled', icon: true}] },
                { name: '30秒早戻し', keys: [{name: 'Shift', icon: false}, {name: 'fluent:arrow-left-12-filled', icon: true}] },
                { name: '30秒早送り', keys: [{name: 'Shift', icon: false}, {name: 'fluent:arrow-right-12-filled', icon: true}] },
                { name: '60秒早戻し', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'fluent:arrow-left-12-filled', icon: true}] },
                { name: '60秒早送り', keys: [{name: Utils.AltOrOption(), icon: false}, {name: 'fluent:arrow-right-12-filled', icon: true}] },
                { name: 'プレイヤーの音量を上げる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-up-12-filled', icon: true}] },
                { name: 'プレイヤーの音量を下げる', keys: [{name: Utils.CtrlOrCmd(), icon: false}, {name: 'fluent:arrow-down-12-filled', icon: true}] },
                { name: 'プレイヤーの音量をミュートする', keys: [{name: 'Q', icon: false}] },
                { name: 'プレイヤーを再起動する', keys: [{name: 'R', icon: false}] },
                { name: 'フルスクリーンの切り替え', keys: [{name: 'F', icon: false}] },
                { name: 'Picture-in-Picture の表示切り替え', keys: [{name: 'E', icon: false}] },
                { name: '字幕の表示切り替え', keys: [{name: 'S', icon: false}] },
                { name: 'コメントの表示切り替え', keys: [{name: 'D', icon: false}] },
                { name: '映像をキャプチャする', keys: [{name: 'C', icon: false}] },
                { name: '映像をコメントを付けてキャプチャする', keys: [{name: 'V', icon: false}] },
            ]
        },
    ],
    right_column: [
        {
            name: 'パネル',
            icon: 'fluent:panel-right-20-filled',
            icon_height: '24px',
            shortcuts: [
                { name: 'パネルの表示切り替え', keys: [{name: 'P', icon: false}] },
                { name: '番組情報タブを表示する', keys: [{name: 'K', icon: false}] },
                { name: 'シリーズタブを表示する', keys: [{name: 'L', icon: false}] },
                { name: 'コメントタブを表示する', keys: [{name: '；(＋)', icon: false}] },
                { name: 'Twitter タブを表示する', keys: [{name: '：(＊)', icon: false}] },
            ]
        },
        {
            name: 'Twitter',
            icon: 'fa-brands:twitter',
            icon_height: '22px',
            shortcuts: [
                { name: 'ツイート検索タブを表示する', keys: [{name: '［ (「)', icon: false}] },
                { name: 'タイムラインタブを表示する', keys: [{name: '］ (」)', icon: false}] },
                { name: 'キャプチャタブを表示する', keys: [{name: '_', icon: false}] },
                { name: '検索結果を更新する', keys: [{name: 'ツイート検索タブを表示', icon: false}, {name: '＼(｜)', icon: false}] },
                { name: 'タイムラインを更新する', keys: [{name: 'タイムラインタブを表示', icon: false}, {name: '＼(｜)', icon: false}] },
                { name: 'キャプチャにフォーカスする', keys: [{name: 'キャプチャタブを表示', icon: false}, {name: 'fluent:arrow-up-12-filled;fluent:arrow-down-12-filled;fluent:arrow-left-12-filled;fluent:arrow-right-12-filled', icon: true}] },
                { name: 'キャプチャを拡大表示する/<br>キャプチャの拡大表示を閉じる', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Enter', icon: false}] },
                { name: 'キャプチャを選択する/<br>キャプチャの選択を解除する', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Space', icon: false}] },
                { name: 'ツイート入力フォームにフォーカスを当てる/フォーカスを外す', keys: [{name: 'Tab', icon: false}] },
                { name: 'ツイートを送信する', keys: [{name: 'Twitter タブを表示', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'Enter', icon: false}] },
                { name: 'クリップボード内の画像を<br>キャプチャとして取り込む', keys: [{name: 'ツイート入力<br>フォームにフォーカス', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'V', icon: false}] },
            ]
        },
    ],
};

export default defineComponent({
    name: 'KeyboardShortcutList',
    props: {
        playback_mode: {
            type: String as PropType<'Live' | 'Video'>,
            required: true,
        },
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),

            // キーボードショートカットの一覧に表示するショートカットキーのリスト (ライブ視聴)
            // created() で設定を反映するため、コンポーネントの破棄後に変更が残らないよう structuredClone() でクローンする
            live_shortcut_list: structuredClone(LIVE_SHORTCUT_LIST),

            // キーボードショートカットの一覧に表示するショートカットキーのリスト (ビデオ視聴)
            // created() で設定を反映するため、コンポーネントの破棄後に変更が残らないよう structuredClone() でクローンする
            video_shortcut_list: structuredClone(VIDEO_SHORTCUT_LIST),
        };
    },
    computed: {
        ...mapStores(usePlayerStore, useSettingsStore),

        // キーボードショートカットの一覧に表示するショートカットキーのリスト
        // ライブ視聴の場合は live_shortcut_key_list を、ビデオ視聴の場合は video_shortcut_key_list を返す
        shortcut_list() {
            if (this.playback_mode === 'Live') {
                return this.live_shortcut_list;
            } else {
                return this.video_shortcut_list;
            }
        },
    },
    created() {
        // チャンネル選局のキーボードショートカットを Alt or Option + 数字キー/テンキーに変更する設定が有効なら、
        // キーボードショートカット一覧に反映する
        if (this.settingsStore.settings.tv_channel_selection_requires_alt_key === true) {
            this.live_shortcut_list.left_column[0].shortcuts[0].keys.unshift({name: Utils.AltOrOption(), icon: false});
            this.live_shortcut_list.left_column[0].shortcuts[1].keys.unshift({name: Utils.AltOrOption(), icon: false});
        }
    },
});

</script>
<style lang="scss" scoped>

.shortcut-key {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    min-width: 32px;
    min-height: 28px;
    padding: 3px 8px;
    border-radius: 5px;
    background-color: rgb(var(--v-theme-background-lighten-2));
    font-size: 14.5px;
    text-align: center;
}

.shortcut-key-plus {
    display: inline-block;
    margin: 0px 5px;
    flex-shrink: 0;
}

</style>