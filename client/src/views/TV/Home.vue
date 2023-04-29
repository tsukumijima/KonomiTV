<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="channels-container channels-container--home" :class="{'channels-container--loading': is_loading}">
                <v-tabs-fix centered class="channels-tab" v-model="tab">
                    <v-tab class="channels-tab__item"
                        v-for="[channels_type,] in Array.from(channelsStore.channels_list_with_pinned)" :key="channels_type">
                        {{channels_type}}
                    </v-tab>
                </v-tabs-fix>
                <v-tabs-items-fix class="channels-list" v-model="tab">
                    <v-tab-item-fix class="channels-tabitem"
                        v-for="[channels_type, channels] in Array.from(channelsStore.channels_list_with_pinned)" :key="channels_type">
                        <div class="channels" :class="`channels--tab-${channels_type} channels--length-${channels.length}`">
                            <router-link v-ripple class="channel"
                                v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.channel_id}`">
                                <div class="channel__broadcaster">
                                    <img class="channel__broadcaster-icon" :src="`${Utils.api_base_url}/channels/${channel.channel_id}/logo`">
                                    <div class="channel__broadcaster-content">
                                        <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.channel_name}}</span>
                                        <div class="channel__broadcaster-status">
                                            <div class="channel__broadcaster-status-force"
                                                :class="`channel__broadcaster-status-force--${ChannelUtils.getChannelForceType(channel.channel_force)}`">
                                                <Icon icon="fa-solid:fire-alt" height="12px" />
                                                <span class="ml-1">勢い:</span>
                                                <span class="ml-1">{{ProgramUtils.getAttribute(channel, 'channel_force', '--')}}</span>
                                                <span style="margin-left: 3px;"> コメ/分</span>
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
                                    <div class="channel__program-present-title-wrapper">
                                        <span class="channel__program-present-title"
                                            v-html="ProgramUtils.decorateProgramInfo(channel.program_present, 'title')"></span>
                                        <span class="channel__program-present-time">{{ProgramUtils.getProgramTime(channel.program_present)}}</span>
                                    </div>
                                    <span class="channel__program-present-description"
                                          v-html="ProgramUtils.decorateProgramInfo(channel.program_present, 'description')"></span>
                                </div>
                                <v-spacer></v-spacer>
                                <div class="channel__program-following">
                                    <div class="channel__program-following-title">
                                        <span class="channel__program-following-title-decorate">NEXT</span>
                                        <Icon class="channel__program-following-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                                        <span class="channel__program-following-title-text"
                                              v-html="ProgramUtils.decorateProgramInfo(channel.program_following, 'title')"></span>
                                    </div>
                                    <span class="channel__program-following-time">{{ProgramUtils.getProgramTime(channel.program_following)}}</span>
                                </div>
                                <div class="channel__progressbar">
                                    <div class="channel__progressbar-progress"
                                         :style="`width:${ProgramUtils.getProgramProgress(channel.program_present)}%;`"></div>
                                </div>
                            </router-link>
                            <div class="pinned-container d-flex justify-center align-center w-100"
                                v-if="channels_type === 'ピン留め' && channels.length === 0">
                                <div class="d-flex justify-center align-center flex-column">
                                    <h2>ピン留めされているチャンネルが<br>ありません。</h2>
                                    <div class="mt-4 text--text text--darken-1">各チャンネルの <Icon style="position:relative;bottom:-5px;" icon="fluent:pin-20-filled" width="22px" /> アイコンから、よくみる<br>チャンネルをこのタブにピン留めできます。</div>
                                    <div class="mt-2 text--text text--darken-1">チャンネルをピン留めすると、<br>このタブが最初に表示されます。</div>
                                </div>
                            </div>
                        </div>
                    </v-tab-item-fix>
                </v-tabs-items-fix>
            </div>
        </main>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';
import useChannelsStore from '@/store/ChannelsStore';
import useSettingsStore from '@/store/SettingsStore';
import Utils, { ChannelUtils, ProgramUtils } from '@/utils';

export default Vue.extend({
    name: 'TV-Home',
    components: {
        Header,
        Navigation,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ChannelUtils: ChannelUtils,
            ProgramUtils: ProgramUtils,

            // タブの状態管理
            tab: null as number | null,

            // ローディング中かどうか
            is_loading: true,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [] as number[],
        };
    },
    computed: {
        // ChannelsStore / SettingsStore に this.channelsStore / this.settingsStore でアクセスできるようにする
        // ref: https://pinia.vuejs.org/cookbook/options-api.html
        ...mapStores(useChannelsStore, useSettingsStore),
    },
    // 開始時に実行
    async created() {

        // ピン留めされているチャンネルの ID が空なら、タブを地デジタブに切り替える
        // ピン留めができる事を示唆するためにピン留めタブ自体は残す
        if (this.settingsStore.settings.pinned_channel_ids.length === 0) {
            this.tab = 1;
        }

        // 00秒までの残り秒数を取得
        // 現在 16:01:34 なら 26 (秒) になる
        const residue_second = 60 - new Date().getSeconds();

        // 00秒になるまで待ってから実行するタイマー
        // 番組は基本1分単位で組まれているため、20秒や45秒など中途半端な秒数で更新してしまうと番組情報の反映が遅れてしまう
        this.interval_ids.push(window.setTimeout(() => {

            // この時点で00秒なので、チャンネル情報を更新
            this.channelsStore.update(true);

            // 以降、30秒おきにチャンネル情報を更新
            this.interval_ids.push(window.setInterval(() => this.channelsStore.update(true), 30 * 1000));

        }, residue_second * 1000));

        // チャンネル情報を更新 (初回)
        await this.channelsStore.update();

        // 少しだけ待つ
        // v-tabs-slider-wrapper をアニメーションさせないために必要
        await Utils.sleep(0.01);

        // この時点でピン留めされているチャンネルがないなら、タブを地デジタブに切り替える
        // ピン留めされているチャンネル自体はあるが、現在放送されていないため表示できない場合に備える
        if (this.channelsStore.channels_list_with_pinned.get('ピン留め').length === 0) {
            this.tab = 1;
        }

        // チャンネル情報の更新が終わったタイミングでローディング状態を解除する
        this.is_loading = false;
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

        // チャンネルをピン留めする
        addPinnedChannel(channel_id: string) {

            // ピン留めするチャンネルの ID を追加 (保存は自動で行われる)
            this.settingsStore.settings.pinned_channel_ids.push(channel_id);

            const channel = this.channelsStore.getChannel(channel_id);
            this.$message.show(`${channel.channel_name}をピン留めしました。`);
        },

        // チャンネルをピン留めから外す
        removePinnedChannel(channel_id: string) {

            // ピン留めを外すチャンネルの ID を削除 (保存は自動で行われる)
            this.settingsStore.settings.pinned_channel_ids.splice(this.settingsStore.settings.pinned_channel_ids.indexOf(channel_id), 1);

            // この時点でピン留めされているチャンネルがないなら、タブを地デジタブに切り替える
            if (this.channelsStore.channels_list_with_pinned.get('ピン留め').length === 0) {
                this.tab = 1;
            }

            const channel = this.channelsStore.getChannel(channel_id);
            this.$message.show(`${channel.channel_name}のピン留めを外しました。`);
        },

        // チャンネルがピン留めされているか
        isPinnedChannel(channel_id: string): boolean {

            // 引数のチャンネルがピン留めリストに存在するかを返す
            return this.settingsStore.settings.pinned_channel_ids.includes(channel_id);
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
        @include smartphone-horizontal {
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
        min-height: calc(100dvh - 65px - 116px + 1px);
        // タッチデバイスではスクロールバーを気にする必要がないので無効化
        @media (hover: none) {
            min-height: auto;
        }
    }
}
.channels-container.channels-container--home.channels-container--loading {
    .v-tabs-slider-wrapper {
        transition: none !important;
    }
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
    transition: opacity 0.2s;
    @include smartphone-vertical {
        margin-left: 0px;
        margin-right: 0px;
    }

    &--loading {
        opacity: 0;
    }

    .channels-tab {
        position: sticky;
        flex: none;
        top: 65px;  // ヘッダーの高さ分
        padding-top: 2px;
        padding-bottom: 12px;
        background:var(--v-background-base);
        z-index: 1;
        @include smartphone-horizontal {
            top: 0px;
            padding-top: 0px;
            padding-bottom: 8px;
        }
        @include smartphone-vertical {
            top: 0px;
            padding-top: 0px;
            padding-bottom: 10px;
        }

        .channels-tab__item {
            width: 98px;
            padding: 0;
            color: var(--v-text-base) !important;
            font-size: 16px;
            text-transform: none;
            @include smartphone-horizontal {
                font-size: 15px;
            }
            @include smartphone-vertical {
                width: auto;
                font-size: 15px;
            }
        }
    }

    .channels-list {
        padding-bottom: 20px;
        background: transparent !important;
        overflow: inherit;
        @include smartphone-horizontal {
            padding-bottom: 12px;
        }
        @include smartphone-vertical {
            padding-left: 8px;
            padding-right: 8px;
            padding-bottom: 12px;
        }

        .channels {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(365px, 1fr));
            grid-row-gap: 12px;
            grid-column-gap: 16px;
            justify-content: center;
            // 背後を通過する別のタブのアニメーションが写らないようにするのに必要
            background: var(--v-background-base);
            // will-change を入れておく事で、アニメーションが GPU で処理される
            will-change: transform;
            @include tablet-vertical {
                grid-row-gap: 10px;
                grid-template-columns: 1fr;
            }
            @include smartphone-horizontal {
                grid-row-gap: 8px;
                grid-template-columns: 1fr;
            }
            @include smartphone-vertical {
                grid-row-gap: 10px;
                grid-template-columns: 1fr;
            }

            // チャンネルリストでの content-visibility: auto; はちょっと描画上の副作用もあるので、
            // パフォーマンス向上が顕著なスマホ・タブレット (タッチデバイス) のみに適用する
            @media (hover: none) {
                content-visibility: auto;
                contain-intrinsic-height: 2000px;  // だいたい 2000px 分の高さを確保
            }

            // 1630px 以上で幅を 445px に固定
            @media (min-width: 1630px) {
                grid-template-columns: repeat(auto-fit, 445px);
            }

            // ピン留めされているチャンネルがないとき
            &.channels--length-0.channels--tab-ピン留め {
                display: flex;
                min-height: calc(100vh - 65px - 116px + 1px);
                min-height: calc(100dvh - 65px - 116px + 1px);
                @include smartphone-horizontal {
                    min-height: calc(100vh - 54px - 12px);
                    min-height: calc(100dvh - 54px - 12px);
                }
            }

            // カードが横いっぱいに表示されてしまうのを回避する
            // チャンネルリストにチャンネルが1つしか表示されていないとき
            &.channels--length-1 {
                // 2列
                @media (min-width: 1008px) {
                    // 16px は余白の幅のこと
                    margin-right: calc((((100% - (16px * 1)) / 2) * 1) + (16px * 1));  // もう1つ分のカード幅を埋める
                }
                // 3列でカード幅が自動
                @media (min-width: 1389px) {
                    margin-right: calc((((100% - (16px * 2)) / 3) * 2) + (16px * 2));  // もう2つ分のカード幅を埋める
                }
                // 3列でカード幅が 445px
                @media (min-width: 1630px) {
                    margin-right: calc((445px * 2) + (16px * 2));  // もう2つ分のカード幅を埋める
                }
                // 4列でカード幅が 445px
                @media (min-width: 2090px) {
                    margin-right: calc((445px * 3) + (16px * 3));  // もう3つ分のカード幅を埋める
                }
            }
            // チャンネルリストにチャンネルが2つしか表示されていないとき
            &.channels--length-2 {
                // 3列でカード幅が自動
                @media (min-width: 1389px) {
                    margin-right: calc((((100% - (16px * 2)) / 3) * 1) + (16px * 1));  // もう1つ分のカード幅を埋める
                }
                // 3列でカード幅が 445px
                @media (min-width: 1630px) {
                    margin-right: calc(445px + 16px);  // もう1つ分のカード幅を埋める
                }
                // 4列でカード幅が 445px
                @media (min-width: 2090px) {
                    margin-right: calc((445px * 2) + (16px * 2));  // もう2つ分のカード幅を埋める
                }
            }
            // チャンネルリストにチャンネルが3つしか表示されていないとき
            &.channels--length-3 {
                // 4列でカード幅が 445px
                @media (min-width: 2090px) {
                    margin-right: calc(445px + 16px);  // もう1つ分のカード幅を埋める
                }
            }

            .channel {
                display: flex;
                flex-direction: column;
                position: relative;
                height: 270px;
                padding: 18px 20px;
                padding-bottom: 19px;
                border-radius: 14px;
                color: var(--v-text-base);
                background: var(--v-background-lighten1);
                transition: background-color 0.15s;
                overflow: hidden;  // progressbar を切り抜くために必要
                text-decoration: none;
                user-select: none;
                cursor: pointer;
                // content-visibility: auto; を付与するだけでスマホでの描画パフォーマンスが大幅に向上する
                content-visibility: auto;
                contain-intrinsic-height: 233px;

                // 1列表示
                @media (max-width: 1007.9px) {
                    height: auto;
                }
                @include tablet-vertical {
                    padding: 14px 16px;
                    padding-top: 12px;
                    height: auto;
                    border-radius: 11px;
                    contain-intrinsic-height: 162.25px;
                }
                @include smartphone-horizontal {
                    padding: 12px 14px;
                    padding-top: 10px;
                    height: auto;
                    border-radius: 11px;
                    contain-intrinsic-height: 125px;
                }
                @include smartphone-vertical {
                    padding: 12px 14px;
                    padding-top: 10px;
                    height: auto;
                    border-radius: 11px;
                    contain-intrinsic-height: 162.25px;
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
                    @include tablet-vertical {
                        height: 40px;
                    }
                    @include smartphone-horizontal {
                        height: 29px;
                    }
                    @include smartphone-vertical {
                        height: 40px;
                    }

                    &-icon {
                        display: inline-block;
                        flex-shrink: 0;
                        width: 80px;
                        height: 44px;
                        border-radius: 5px;
                        // 読み込まれるまでのアイコンの背景
                        background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                        object-fit: cover;
                        @include tablet-vertical {
                            width: 69px;
                            height: 40px;
                            border-radius: 4px;
                        }
                        @include smartphone-horizontal {
                            width: 54px;
                            height: 29px;
                            border-radius: 4px;
                        }
                        @include smartphone-vertical {
                            width: 69px;
                            height: 40px;
                            border-radius: 4px;
                        }
                    }

                    &-content {
                        display: flex;
                        flex-direction: column;
                        margin-left: 16px;
                        width: 100%;
                        min-width: 0;
                        @include tablet-vertical {
                            margin-left: 14px;
                        }
                        @include smartphone-horizontal {
                            align-items: center;
                            flex-direction: row;
                            margin-left: 12px;
                            margin-right: 6px;
                        }
                        @include smartphone-vertical {
                            margin-left: 14px;
                        }
                    }

                    &-name {
                        flex-shrink: 0;
                        font-size: 18px;
                        overflow: hidden;
                        white-space: nowrap;
                        text-overflow: ellipsis;
                        @include tablet-vertical {
                            font-size: 15.5px;
                        }
                        @include smartphone-horizontal {
                            font-size: 15px;
                        }
                        @include smartphone-vertical {
                            font-size: 15.5px;
                        }
                    }

                    &-status {
                        display: flex;
                        position: relative;
                        top: -1.5px;
                        flex-shrink: 0;
                        align-items: center;
                        margin-top: 2px;
                        font-size: 12px;
                        color: var(--v-text-darken1);
                        @include tablet-vertical {
                            margin-top: 2px;
                            font-size: 11px;
                        }
                        @include smartphone-horizontal {
                            margin-top: 3px;
                            margin-left: auto;
                            font-size: 12px;
                        }
                        @include smartphone-vertical {
                            margin-top: 2px;
                            font-size: 11px;
                        }

                        &-force, &-viewers {
                            display: flex;
                            align-items: center;
                            @include smartphone-horizontal-short {
                                span:nth-child(2), span:nth-child(4) {
                                    display: none;
                                }
                            }
                        }

                        @include smartphone-horizontal {
                            &-viewers {
                                margin-left: 8px !important;
                            }
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
                        @include smartphone-horizontal {
                            top: -1px;
                        }

                        &:before {
                            content: "";
                            position: absolute;
                            top: 0;
                            left: 0;
                            right: 0;
                            bottom: 0;
                            border-radius: inherit;
                            background-color: currentColor;
                            color: inherit;
                            opacity: 0;
                            transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
                            pointer-events: none;
                        }
                        &:hover {
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
                            @include smartphone-horizontal {
                                color: var(--v-secondary-lighten2);
                                &:hover{
                                    color: var(--v-secondary-lighten3);
                                }
                            }
                            @include smartphone-vertical {
                                color: var(--v-secondary-lighten2);
                                &:hover{
                                    color: var(--v-secondary-lighten3);
                                }
                            }
                        }
                    }
                }

                .channel__program-present {
                    display: flex;
                    flex-direction: column;

                    &-title-wrapper {
                        margin-top: 14px;

                        @include tablet-vertical {
                            display: flex;
                            flex-direction: column;
                            margin-top: 8px;
                        }
                        @include smartphone-horizontal {
                            display: flex;
                            align-items: center;
                            margin-top: 8px;
                        }
                        @include smartphone-vertical {
                            display: flex;
                            flex-direction: column;
                            margin-top: 8px;
                        }
                    }

                    &-title {
                        display: -webkit-box;
                        font-size: 16px;
                        font-weight: 700;
                        font-feature-settings: "palt" 1;  // 文字詰め
                        letter-spacing: 0.07em;  // 字間を少し空ける
                        overflow: hidden;
                        -webkit-line-clamp: 2;  // 2行までに制限
                        -webkit-box-orient: vertical;
                        @include tablet-vertical {
                            font-size: 14px;
                        }
                        @include smartphone-horizontal {
                            font-size: 14px;
                            -webkit-line-clamp: 1;  // 1行までに制限
                        }
                        @include smartphone-vertical {
                            font-size: 14px;
                            -webkit-line-clamp: 1;  // 1行までに制限
                        }
                    }

                    &-time {
                        margin-top: 4px;
                        color: var(--v-text-darken1);
                        font-size: 13.5px;
                        @include tablet-vertical {
                            flex-shrink: 0;
                            margin-top: 2px;
                            font-size: 13px;
                        }
                        @include smartphone-horizontal {
                            flex-shrink: 0;
                            margin-top: 0px;
                            margin-left: auto;
                            padding-left: 10px;
                            font-size: 12px;
                        }
                        @include smartphone-horizontal-short {
                            font-size: 11px;
                            padding-left: 6px;
                        }
                        @include smartphone-vertical {
                            flex-shrink: 0;
                            margin-top: 1px;
                            font-size: 12px;
                        }
                    }

                    &-description {
                        display: -webkit-box;
                        margin-top: 6px;
                        color: var(--v-text-darken1);
                        font-size: 10.5px;
                        line-height: 175%;
                        overflow-wrap: break-word;
                        font-feature-settings: "palt" 1;  // 文字詰め
                        letter-spacing: 0.07em;  // 字間を少し空ける
                        overflow: hidden;
                        -webkit-line-clamp: 3;  // 3行までに制限
                        -webkit-box-orient: vertical;
                        @include tablet-vertical {
                            margin-top: 4px;
                            font-size: 11px;
                            line-height: 155%;
                            -webkit-line-clamp: 2;  // 2行までに制限
                        }
                        @include smartphone-horizontal {
                            margin-top: 3px;
                            font-size: 10px;
                            line-height: 160%;
                            -webkit-line-clamp: 2;  // 2行までに制限
                        }
                        @include smartphone-vertical {
                            margin-top: 4px;
                            font-size: 10px;
                            line-height: 155%;
                            -webkit-line-clamp: 2;  // 2行までに制限
                        }
                    }
                }

                .channel__program-following {
                    display: flex;
                    flex-direction: column;
                    color: var(--v-text-base);
                    font-size: 12.5px;
                    // 1列表示
                    @media (max-width: 1007.9px) {
                        margin-top: 6px;
                    }
                    @include smartphone-horizontal {
                        flex-direction: row;
                        margin-top: 4px;
                        font-size: 12px;
                    }
                    @include smartphone-vertical {
                        margin-top: 4px;
                        font-size: 12px;
                    }

                    &-title {
                        display: flex;
                        align-items: center;
                        min-width: 0;  // magic!

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
                        @include smartphone-horizontal {
                            flex-shrink: 0;
                            margin-left: auto;
                            padding-left: 8px;
                            font-size: 11.5px;
                        }
                        @include smartphone-horizontal-short {
                            font-size: 11px;
                            padding-left: 6px;
                        }
                        @include smartphone-vertical {
                            flex-shrink: 0;
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

    .pinned-container {
        br {
            display: none;
        }
        @include tablet-vertical {
            h2 {
                font-size: 21px !important;
            }
            div {
                font-size: 12.5px !important;
                text-align: center;
            }
        }
        @include smartphone-horizontal {
            padding-top: 12px;
            h2 {
                font-size: 21px !important;
            }
            div {
                font-size: 13px !important;
                text-align: center;
                .mt-4 {
                    margin-top: 12px !important;
                }
                svg {
                    width: 16px;
                }
            }
        }
        @include smartphone-horizontal-short {
            h2 {
                font-size: 16px !important;
            }
            div {
                font-size: 10.5px !important;
                .mt-4 {
                    margin-top: 8px !important;
                }
            }
        }
        @include smartphone-vertical {
            min-height: calc(100vh - 56px - 64px - 12px);
            min-height: calc(100dvh - 56px - 64px - 12px);
            padding-top: 12px;
            br {
                display: inline;
            }
            h2 {
                font-size: 22px !important;
                text-align: center;
            }
            div {
                font-size: 15px !important;
                text-align: center;
                .mt-4 {
                    margin-top: 8px !important;
                }
                svg {
                    width: 20px;
                }
            }
        }
    }
}

</style>