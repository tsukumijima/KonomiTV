<template>
    <v-dialog max-width="1050" transition="slide-y-transition" v-model="playerStore.shortcut_key_modal">
        <v-card>
            <v-card-title class="px-5 pt-4 pb-3 d-flex align-center font-weight-bold">
                <Icon icon="fluent:keyboard-20-filled" height="28px" />
                <span class="ml-3">キーボードショートカット</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="playerStore.shortcut_key_modal = false">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-4">
                <v-row>
                    <v-col cols="6" v-for="(shortcut_key_column, shortcut_key_column_name) in shortcut_list" :key="shortcut_key_column_name">
                        <div class="mt-3" v-for="shortcut_keys in shortcut_key_column" :key="shortcut_keys.name">
                            <div class="text-subtitle-1 d-flex align-center font-weight-bold">
                                <Icon :icon="shortcut_keys.icon" :height="shortcut_keys.icon_height" />
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
                { name: 'キャプチャタブを表示する', keys: [{name: '＼(￥)', icon: false}] },
                { name: 'ツイート入力フォームにフォーカスを当てる/フォーカスを外す', keys: [{name: 'Tab', icon: false}] },
                { name: 'キャプチャにフォーカスする', keys: [{name: 'キャプチャタブを表示', icon: false}, {name: 'fluent:arrow-up-12-filled;fluent:arrow-down-12-filled;fluent:arrow-left-12-filled;fluent:arrow-right-12-filled', icon: true}] },
                { name: 'キャプチャを拡大表示する/<br>キャプチャの拡大表示を閉じる', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Enter', icon: false}] },
                { name: 'キャプチャを選択する/<br>キャプチャの選択を解除する', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Space', icon: false}] },
                { name: 'クリップボード内の画像を<br>キャプチャとして取り込む', keys: [{name: 'ツイート入力<br>フォームにフォーカス', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'V', icon: false}] },
                { name: 'ツイートを送信する', keys: [{name: 'Twitter タブを表示', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'Enter', icon: false}] },
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
                { name: 'キャプチャタブを表示する', keys: [{name: '＼(￥)', icon: false}] },
                { name: 'ツイート入力フォームにフォーカスを当てる/フォーカスを外す', keys: [{name: 'Tab', icon: false}] },
                { name: 'キャプチャにフォーカスする', keys: [{name: 'キャプチャタブを表示', icon: false}, {name: 'fluent:arrow-up-12-filled;fluent:arrow-down-12-filled;fluent:arrow-left-12-filled;fluent:arrow-right-12-filled', icon: true}] },
                { name: 'キャプチャを拡大表示する/<br>キャプチャの拡大表示を閉じる', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Enter', icon: false}] },
                { name: 'キャプチャを選択する/<br>キャプチャの選択を解除する', keys: [{name: 'キャプチャにフォーカス', icon: false}, {name: 'Space', icon: false}] },
                { name: 'クリップボード内の画像を<br>キャプチャとして取り込む', keys: [{name: 'ツイート入力<br>フォームにフォーカス', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'V', icon: false}] },
                { name: 'ツイートを送信する', keys: [{name: 'Twitter タブを表示', icon: false}, {name: Utils.CtrlOrCmd(), icon: false}, {name: 'Enter', icon: false}] },
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
            Utils: Utils,

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
    background-color: var(--v-background-lighten2);
    font-size: 14.5px;
    text-align: center;
}

.shortcut-key-plus {
    display: inline-block;
    margin: 0px 5px;
    flex-shrink: 0;
}

</style>