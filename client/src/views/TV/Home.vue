<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="channels-container channels-container--home" :class="{'channels-container--loading': is_loading}">
                <v-tabs-fix centered class="channels-tab" v-model="tab">
                    <v-tab class="channels-tab__item" v-for="[channels_type,] in Array.from(channels_list)" :key="channels_type">{{channels_type}}</v-tab>
                </v-tabs-fix>
                <v-tabs-items-fix class="channels-list" v-model="tab">
                    <v-tab-item-fix class="channels-tabitem" v-for="[channels_type, channels] in Array.from(channels_list)" :key="channels_type">
                        <div class="channels" :class="`channels--length-${channels.length}`">
                            <router-link v-ripple class="channel" v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.channel_id}`">
                                <div class="channel__broadcaster">
                                    <img class="channel__broadcaster-icon" :src="`${api_base_url}/channels/${channel.channel_id}/logo`">
                                    <div class="channel__broadcaster-content">
                                        <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.channel_name}}</span>
                                        <div class="channel__broadcaster-status">
                                            <div class="channel__broadcaster-status-force"
                                                :class="`channel__broadcaster-status-force--${getChannelForceType(channel.channel_force)}`">
                                                <Icon icon="fa-solid:fire-alt" height="12px" />
                                                <span class="ml-1">勢い:</span>
                                                <span class="ml-1">{{getAttribute(channel, 'channel_force', '--')}} コメ/分</span>
                                            </div>
                                            <div class="channel__broadcaster-status-viewers ml-4">
                                                <Icon icon="fa-solid:eye" height="14px" />
                                                <span class="ml-1">視聴数:</span>
                                                <span class="ml-1">{{channel.viewers}}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div v-ripple class="channel__broadcaster-pin"
                                        v-tooltip="isPinnedChannel(channel.channel_id) ? 'ピン留めを外す' : 'ピン留めする'"
                                        :class="{'channel__broadcaster-pin--pinned': isPinnedChannel(channel.channel_id)}"
                                        @click.prevent.stop="isPinnedChannel(channel.channel_id) ? removePinnedChannel(channel.channel_id) : addPinnedChannel(channel.channel_id)"
                                        @mousedown.prevent.stop="/* 親要素の波紋が広がらないように */">
                                        <Icon icon="fluent:pin-20-filled" width="24px" />
                                    </div>
                                </div>
                                <div class="channel__program-present">
                                    <span class="channel__program-present-title" v-html="decorateProgramInfo(channel.program_present, 'title')"></span>
                                    <span class="channel__program-present-time">{{getProgramTime(channel.program_present)}}</span>
                                    <span class="channel__program-present-description" v-html="decorateProgramInfo(channel.program_present, 'description')"></span>
                                </div>
                                <v-spacer></v-spacer>
                                <div class="channel__program-following">
                                    <div class="channel__program-following-title">
                                        <span class="channel__program-following-title-decorate">NEXT</span>
                                        <Icon class="channel__program-following-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                                        <span class="channel__program-following-title-text" v-html="decorateProgramInfo(channel.program_following, 'title')"></span>
                                    </div>
                                    <span class="channel__program-following-time">{{getProgramTime(channel.program_following)}}</span>
                                </div>
                                <div class="channel__progressbar">
                                    <div class="channel__progressbar-progress" :style="`width:${getProgramProgress(channel.program_present)}%;`"></div>
                                </div>
                            </router-link>
                        </div>
                    </v-tab-item-fix>
                </v-tabs-items-fix>
            </div>
        </main>
    </div>
</template>
<script lang="ts">

import Vue from 'vue';

import { IChannel } from '@/interface';
import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import Mixin from '@/views/TV/Mixin.vue';
import Utility from '@/utility';

export default Mixin.extend({
    name: 'Home',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {

            // タブの状態管理
            tab: null,

            // ローディング中かどうか
            is_loading: true,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [] as number[],
        }
    },
    // 開始時に実行
    created() {

        // チャンネル情報を取得
        this.update();

        // 00秒までの残り秒数
        // 現在 16:01:34 なら 26 (秒) になる
        const residue_second = 60 - (Math.floor(new Date().getTime() / 1000) % 60);

        // 00秒になるまで待ってから
        // 番組は基本1分単位で組まれているため、20秒や45秒など中途半端な秒数で更新してしまうと反映が遅れてしまう
        this.interval_ids.push(window.setTimeout(() => {

            // チャンネル情報を更新
            this.update();

            // チャンネル情報を定期的に更新
            this.interval_ids.push(window.setInterval(() => {
                this.update();
            }, 60 * 1000));  // 1分おき

        }, residue_second * 1000));
    },
    // 終了前に実行
    beforeDestroy() {

        // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
        // clearInterval() と clearTimeout() は中身共通なので問題ない
        for (const interval_id of this.interval_ids) {
            window.clearInterval(interval_id);
        }
    },
    methods: {

        // チャンネル情報一覧を取得し、画面を更新する
        async update() {

            // チャンネル情報一覧 API にアクセス
            let channels_response;
            try {
                channels_response = await Vue.axios.get(`${this.api_base_url}/channels`);
            } catch (error) {
                console.error(error);   // エラー内容を表示
                return;
            }

            // is_display が true のチャンネルのみに絞り込むフィルタ関数
            // 放送していないサブチャンネルを表示から除外する
            const filter = (channel: IChannel) => {
                return channel.is_display;
            }

            // チャンネルリストを再構築
            // 1つでもチャンネルが存在するチャンネルタイプのみ表示するように
            // たとえば SKY (スカパー！プレミアムサービス) のタブは SKY に属すチャンネルが1つもない（=受信できない）なら表示されない
            this.channels_list = new Map();
            if (channels_response.data.GR.length > 0) this.channels_list.set('地デジ', channels_response.data.GR.filter(filter));
            if (channels_response.data.BS.length > 0) this.channels_list.set('BS', channels_response.data.BS.filter(filter));
            if (channels_response.data.CS.length > 0) this.channels_list.set('CS', channels_response.data.CS.filter(filter));
            if (channels_response.data.SKY.length > 0) this.channels_list.set('SKY', channels_response.data.SKY.filter(filter));

            // ピン留めされているチャンネルのリストを更新
            this.updatePinnedChannelList();

            // ローディング状態を解除
            this.is_loading = false;
        },

        // チャンネルをピン留めする
        addPinnedChannel(channel_id: string) {

            // 現在ピン留めされているチャンネルを取得
            this.pinned_channel_ids = Utility.getSettingsItem('pinned_channel_ids');

            // ピン留めするチャンネルの ID を追加
            this.pinned_channel_ids.push(channel_id);

            // 設定を保存
            Utility.setSettingsItem('pinned_channel_ids', this.pinned_channel_ids);

            // ピン留めされているチャンネルのリストを更新
            this.updatePinnedChannelList();
        },

        // チャンネルをピン留めから外す
        removePinnedChannel(channel_id: string) {

            // 現在ピン留めされているチャンネルを取得
            this.pinned_channel_ids = Utility.getSettingsItem('pinned_channel_ids');

            // ピン留めを外すチャンネルの ID を削除
            this.pinned_channel_ids.splice(this.pinned_channel_ids.indexOf(channel_id), 1);

            // 設定を保存
            Utility.setSettingsItem('pinned_channel_ids', this.pinned_channel_ids);

            // ピン留めされているチャンネルのリストを更新
            this.updatePinnedChannelList();
        },

        // チャンネルがピン留めされているか
        isPinnedChannel(channel_id: string): boolean {

            // 引数のチャンネルがピン留めリストに存在するかを返す
            return this.pinned_channel_ids.includes(channel_id);
        }
    }
});

</script>
<style lang="scss">

// 上書きしたいスタイル
.channels-container.channels-container--home {
    .v-tabs-bar {
        height: 54px;
        // 下線を引く
        background: linear-gradient(to bottom, var(--v-background-base) calc(100% - 3px), var(--v-background-lighten1) 3px);
        @media screen and (max-height: 450px) {
            height: 46px;
        }
    }
    .v-tabs-slider-wrapper {
        height: 3px !important;
        transition: left 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
    }

    .v-window__container {
        // 1px はスクロールバーを表示させるためのもの
        min-height: calc(100vh - 65px - 116px + 1px);
        // タッチデバイスではスクロールバーを気にする必要がないので無効化
        @media (hover: none) {
            min-height: auto;
        }
    }
}

// Safari のみ、チャンネルリストのスライドアニメーションを無効にする
// Safari は大量のチャンネルをレンダリングするのが非常に遅いようで、アニメーションがもはや機能していない上に重い
// アニメーションを無効化する事で、有効化時と比べてタブの切り替え速度が大幅に向上する（とはいえ、Chrome に比べると遅い）
// CSS ハックでは SCSS 記法が使えない
// ref: https://qiita.com/Butterthon/items/10e6b58d883236aa3838
_::-webkit-full-page-media, _:future, :root
.channels-container.channels-container--home .v-window__container {
    height: inherit !important;
    transition: none !important;
}
_::-webkit-full-page-media, _:future, :root
.channels-container.channels-container--home .v-window__container--is-active {
    display: none !important;
}
_::-webkit-full-page-media, _:future, :root
.channels-container.channels-container--home .v-window__container .v-window-item {
    display: none !important;
    position: static !important;
    transform: none !important;
    transition: none !important;
}
_::-webkit-full-page-media, _:future, :root
.channels-container.channels-container--home .v-window__container .v-window-item--active {
    display: block !important;
}

</style>
<style lang="scss" scoped>

.channels-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    margin-left: 21px;
    margin-right: 21px;
    opacity: 1;
    transition: opacity 0.4s;

    &--loading {
        opacity: 0;
    }

    .channels-tab {
        position: sticky;
        flex: none;
        top: 65px;  // ヘッダーの高さ分
        padding-top: 10px;
        padding-bottom: 20px;
        background:var(--v-background-base);
        z-index: 1;
        @media screen and (max-height: 450px) {
            top: 47.9px;
            padding-top: 2px;
            padding-bottom: 12px;
        }

        .channels-tab__item {
            width: 98px;
            padding: 0;
            color: var(--v-text-base) !important;
            font-size: 16px;
            @media screen and (max-height: 450px) {
                font-size: 15px;
            }
        }
    }

    .channels-list {
        padding-bottom: 32px;
        background: transparent !important;
        overflow: inherit;
        @media screen and (max-height: 450px) {
            padding-bottom: 22px;
        }

        .channels {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(365px, 1fr));
            grid-row-gap: 16px;
            grid-column-gap: 16px;
            justify-content: center;
            // 背後を通過する別のタブのアニメーションが写らないようにするのに必要
            background: var(--v-background-base);
            // will-change を入れておく事で、アニメーションが GPU で処理される
            will-change: transform;

            // 1630px 以上で幅を 445px に固定
            @media screen and (min-width: 1630px) {
                grid-template-columns: repeat(auto-fit, 445px);
            }

            // カードが横いっぱいに表示されてしまうのを回避する
            // チャンネルリストにチャンネルが1つしか表示されていないとき
            &.channels--length-1 {
                // 2列
                @media screen and (min-width: 1008px) {
                    // 16px は余白の幅のこと
                    margin-right: calc((((100% - (16px * 1)) / 2) * 1) + (16px * 1));  // もう1つ分のカード幅を埋める
                }
                // 3列でカード幅が自動
                @media screen and (min-width: 1389px) {
                    margin-right: calc((((100% - (16px * 2)) / 3) * 2) + (16px * 2));  // もう2つ分のカード幅を埋める
                }
                // 3列でカード幅が 445px
                @media screen and (min-width: 1630px) {
                    margin-right: calc((445px * 2) + (16px * 2));  // もう2つ分のカード幅を埋める
                }
                // 4列でカード幅が 445px
                @media screen and (min-width: 2090px) {
                    margin-right: calc((445px * 3) + (16px * 3));  // もう3つ分のカード幅を埋める
                }
            }
            // チャンネルリストにチャンネルが2つしか表示されていないとき
            &.channels--length-2 {
                // 3列でカード幅が自動
                @media screen and (min-width: 1389px) {
                    margin-right: calc((((100% - (16px * 2)) / 3) * 1) + (16px * 1));  // もう1つ分のカード幅を埋める
                }
                // 3列でカード幅が 445px
                @media screen and (min-width: 1630px) {
                    margin-right: calc(445px + 16px);  // もう1つ分のカード幅を埋める
                }
                // 4列でカード幅が 445px
                @media screen and (min-width: 2090px) {
                    margin-right: calc((445px * 2) + (16px * 2));  // もう2つ分のカード幅を埋める
                }
            }
            // チャンネルリストにチャンネルが3つしか表示されていないとき
            &.channels--length-3 {
                // 4列でカード幅が 445px
                @media screen and (min-width: 2090px) {
                    margin-right: calc(445px + 16px);  // もう1つ分のカード幅を埋める
                }
            }

            .channel {
                display: flex;
                flex-direction: column;
                position: relative;
                height: 275px;
                padding: 19px 22px;
                border-radius: 16px;
                color: var(--v-text-base);
                background: var(--v-background-lighten1);
                transition: background-color 0.15s;
                overflow: hidden;  // progressbar を切り抜くために必要
                text-decoration: none;
                user-select: none;
                cursor: pointer;

                // 1列表示
                @media screen and (max-width: 1007.9px) {
                    height: auto;
                }
                @media screen and (max-height: 450px) {
                    padding: 15px 18px;
                    height: auto;
                    border-radius: 15px;
                }

                &:hover {
                    background: var(--v-background-lighten2);
                }
                // タッチデバイスで hover を無効にする
                @media (hover: none) {
                    &:hover {
                        background: var(--v-background-lighten1);
                    }
                }

                .channel__broadcaster {
                    display: flex;
                    height: 44px;
                    @media screen and (max-height: 450px) {
                        height: 38px;
                    }

                    &-icon {
                        display: inline-block;
                        flex-shrink: 0;
                        width: 80px;
                        height: 44px;
                        border-radius: 5px;
                        background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                        object-fit: cover;
                        @media screen and (max-height: 450px) {
                            width: 64px;
                            height: 38px;
                        }
                    }

                    &-content {
                        display: flex;
                        flex-direction: column;
                        margin-left: 16px;
                        width: 100%;
                        min-width: 0;
                    }

                    &-name {
                        flex-shrink: 0;
                        font-size: 18px;
                        overflow: hidden;
                        white-space: nowrap;
                        text-overflow: ellipsis;
                        @media screen and (max-height: 450px) {
                            font-size: 15px;
                        }
                    }

                    &-status {
                        display: flex;
                        align-items: center;
                        margin-top: 2px;
                        font-size: 12px;
                        color: var(--v-text-darken1);
                        @media screen and (max-height: 450px) {
                            font-size: 10px;
                            margin-top: 3px;
                        }

                        &-force, &-viewers {
                            display: flex;
                            align-items: center;
                        }

                        &-force--festival {
                            color: #E7556E;
                        }
                        &-force--so-many {
                            color: #E76B55;
                        }
                        &-force--many {
                            color: #E7A355;
                        }
                    }

                    &-pin {
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-shrink: 0;
                        position: relative;
                        top: -5px;
                        right: -5px;
                        width: 34px;
                        height: 34px;
                        padding: 4px;
                        color: var(--v-text-darken1);
                        border-radius: 50%;
                        transition: color 0.15s ease, background-color 0.15s ease;
                        user-select: none;

                        &:before {
                            background-color: currentColor;
                            border-radius: inherit;
                            bottom: 0;
                            color: inherit;
                            content: "";
                            left: 0;
                            opacity: 0;
                            pointer-events: none;
                            position: absolute;
                            right: 0;
                            top: 0;
                            transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
                        }
                        &:hover{
                            color: var(--v-text-base);
                            &:before {
                                opacity: 0.15;
                            }
                        }
                        &--pinned {
                            color: var(--v-primary-base);
                            &:hover{
                                color: var(--v-primary-lighten1);
                            }
                        }
                    }
                }

                .channel__program-present {
                    display: flex;
                    flex-direction: column;

                    &-title {
                        display: -webkit-box;
                        margin-top: 14px;
                        font-size: 16px;
                        font-weight: 700;
                        font-feature-settings: "palt" 1;  // 文字詰め
                        letter-spacing: 0.07em;  // 字間を少し空ける
                        overflow: hidden;
                        -webkit-line-clamp: 2;  // 2行までに制限
                        -webkit-box-orient: vertical;
                        @media screen and (max-height: 450px) {
                            margin-top: 10px;
                            font-size: 14.5px;
                            -webkit-line-clamp: 1;  // 1行までに制限
                        }
                    }

                    &-time {
                        margin-top: 4px;
                        color: var(--v-text-darken1);
                        font-size: 13.5px;
                        @media screen and (max-height: 450px) {
                            font-size: 12px;
                        }
                    }

                    &-description {
                        display: -webkit-box;
                        margin-top: 8px;
                        color: var(--v-text-darken1);
                        font-size: 10.5px;
                        line-height: 175%;
                        overflow-wrap: break-word;
                        font-feature-settings: "palt" 1;  // 文字詰め
                        letter-spacing: 0.07em;  // 字間を少し空ける
                        overflow: hidden;
                        -webkit-line-clamp: 3;  // 3行までに制限
                        -webkit-box-orient: vertical;
                        @media screen and (max-height: 450px) {
                            margin-top: 8px;
                            font-size: 10px;
                            -webkit-line-clamp: 2;  // 3行までに制限
                        }
                    }
                }

                .channel__program-following {
                    display: flex;
                    flex-direction: column;
                    color: var(--v-text-base);
                    font-size: 12.5px;
                    // 1列表示
                    @media screen and (max-width: 1007.9px) {
                        margin-top: 6px;
                    }
                    @media screen and (max-height: 450px) {
                        margin-top: 6px;
                        font-size: 12px;
                    }

                    &-title {
                        display: flex;
                        align-items: center;
                        &-decorate {
                            flex-shrink: 0;
                            font-weight: bold;
                        }
                        &-icon {
                            flex-shrink: 0;
                            margin-left: 3px;
                        }
                        &-text {
                            margin-left: 2px;
                            white-space: nowrap;
                            text-overflow: ellipsis;  // はみ出た部分を … で省略
                            overflow: hidden;
                        }
                    }
                    &-time {
                        color: var(--v-text-darken1);
                        @media screen and (max-height: 450px) {
                            font-size: 11.5px;
                        }
                    }
                }

                .channel__progressbar {
                    position: absolute;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    height: 4px;
                    background: var(--v-gray-base);

                    &-progress {
                        height: 4px;
                        background: var(--v-primary-base);
                        transition: width 0.3s;
                    }
                }
            }
        }
    }
}

</style>