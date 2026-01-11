<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="channels-container channels-container--home" :class="{'channels-container--loading': is_loading}">
                <SPHeaderBar />
                <div class="channels-tab">
                    <div class="channels-tab__buttons" :style="{
                        '--tab-length': Array.from(channelsStore.channels_list_with_pinned).length,
                        '--active-tab-index': active_tab_index,
                    }">
                        <v-btn variant="flat" class="channels-tab__button"
                            v-for="([channels_type,], index) in Array.from(channelsStore.channels_list_with_pinned)" :key="channels_type"
                            @click="active_tab_index = index">
                            {{channels_type}}
                        </v-btn>
                        <div class="channels-tab__highlight"></div>
                    </div>
                </div>
                <Swiper class="channels-list" :space-between="32" :auto-height="true" :touch-start-prevent-default="false"
                    :observer="true" :observe-parents="true"
                    @swiper="swiper_instance = $event"
                    @slide-change="active_tab_index = $event.activeIndex"
                    v-show="Array.from(channelsStore.channels_list_with_pinned).length > 0">
                    <SwiperSlide v-for="[channels_type, channels] in Array.from(channelsStore.channels_list_with_pinned)" :key="channels_type">
                        <div class="channels" :class="`channels--tab-${channels_type} channels--length-${channels.length}`">
                            <router-link v-ripple class="channel" draggable="false"
                                v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.display_channel_id}`">
                                <!-- 以下では Icon コンポーネントを使うとチャンネルが多いときに高負荷になるため、意図的に SVG を直書きしている -->
                                <div class="channel__broadcaster">
                                    <img class="channel__broadcaster-icon" loading="lazy" decoding="async"
                                        :src="`${Utils.api_base_url}/channels/${channel.id}/logo`">
                                    <div class="channel__broadcaster-content">
                                        <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.name}}</span>
                                        <div class="channel__broadcaster-status">
                                            <div class="channel__broadcaster-status-force"
                                                :class="`channel__broadcaster-status-force--${ChannelUtils.getChannelForceType(channel.jikkyo_force)}`">
                                                <svg class="iconify iconify--fa-solid" width="10.5px" height="12px" viewBox="0 0 448 512">
                                                    <path fill="currentColor" d="M323.56 51.2c-20.8 19.3-39.58 39.59-56.22 59.97C240.08 73.62 206.28 35.53 168 0C69.74 91.17 0 209.96 0 281.6C0 408.85 100.29 512 224 512s224-103.15 224-230.4c0-53.27-51.98-163.14-124.44-230.4zm-19.47 340.65C282.43 407.01 255.72 416 226.86 416C154.71 416 96 368.26 96 290.75c0-38.61 24.31-72.63 72.79-130.75c6.93 7.98 98.83 125.34 98.83 125.34l58.63-66.88c4.14 6.85 7.91 13.55 11.27 19.97c27.35 52.19 15.81 118.97-33.43 153.42z"></path>
                                                </svg>
                                                <span class="ml-1">勢い:</span>
                                                <span class="ml-1">{{channel.jikkyo_force ?? '--'}}</span>
                                                <span style="margin-left: 3px;"> コメ/分</span>
                                            </div>
                                            <div class="channel__broadcaster-status-viewers ml-4">
                                                <svg class="iconify iconify--fa-solid" width="15.75px" height="14px" viewBox="0 0 576 512">
                                                    <path fill="currentColor" d="M572.52 241.4C518.29 135.59 410.93 64 288 64S57.68 135.64 3.48 241.41a32.35 32.35 0 0 0 0 29.19C57.71 376.41 165.07 448 288 448s230.32-71.64 284.52-177.41a32.35 32.35 0 0 0 0-29.19zM288 400a144 144 0 1 1 144-144a143.93 143.93 0 0 1-144 144zm0-240a95.31 95.31 0 0 0-25.31 3.79a47.85 47.85 0 0 1-66.9 66.9A95.78 95.78 0 1 0 288 160z"></path>
                                                </svg>
                                                <span class="ml-1">視聴数:</span>
                                                <span class="ml-1">{{channel.viewer_count}}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div v-ripple class="channel__broadcaster-pin"
                                        v-ftooltip="isPinnedChannel(channel) ? 'ピン留めを外す' : 'ピン留めする'"
                                        :class="{'channel__broadcaster-pin--pinned': isPinnedChannel(channel)}"
                                        @click.prevent.stop="isPinnedChannel(channel) ? removePinnedChannel(channel) : addPinnedChannel(channel)"
                                        @mousedown.prevent.stop=""> <!-- ← 親要素の波紋が広がらないように -->
                                        <svg class="iconify iconify--fluent" width="24px" height="24px" viewBox="0 0 20 20">
                                            <path fill="currentColor" d="M13.325 2.617a2 2 0 0 0-3.203.52l-1.73 3.459a1.5 1.5 0 0 1-.784.721l-3.59 1.436a1 1 0 0 0-.335 1.636L6.293 13L3 16.292V17h.707L7 13.706l2.61 2.61a1 1 0 0 0 1.636-.335l1.436-3.59a1.5 1.5 0 0 1 .722-.784l3.458-1.73a2 2 0 0 0 .52-3.203l-4.057-4.057Z"></path>
                                        </svg>
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
                                        <svg class="channel__program-following-title-icon iconify iconify--fluent" width="16px" height="16px" viewBox="0 0 20 20">
                                            <path fill="currentColor" d="M10.018 5.486a1 1 0 0 1 1.592-.806l5.88 4.311a1.25 1.25 0 0 1 0 2.017l-5.88 4.311a1 1 0 0 1-1.592-.806v-3.16L4.61 15.319a1 1 0 0 1-1.592-.806V5.486A1 1 0 0 1 4.61 4.68l5.408 3.966v-3.16Z"></path>
                                        </svg>
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
                                    <div class="mt-4 text-text-darken-1">各チャンネルの <Icon style="position: relative; bottom: -5px;" icon="fluent:pin-20-filled" width="22px" /> アイコンから、よくみる<br>チャンネルをこのタブにピン留めできます。</div>
                                    <div class="mt-2 text-text-darken-1">チャンネルをピン留めすると、<br>このタブが最初に表示されます。</div>
                                </div>
                            </div>
                        </div>
                    </SwiperSlide>
                </Swiper>
                <div class="channels-list pinned-container d-flex justify-center align-center w-100" style="flex-grow: 1;"
                    v-if="Array.from(channelsStore.channels_list_with_pinned).length === 0">
                    <div class="d-flex justify-center align-center flex-column">
                        <h2>視聴可能なチャンネルが<br class="d-sm-none">ありません。</h2>
                        <div class="mt-4 text-text-darken-1">前回チャンネルスキャンしたときに<br class="d-sm-none">受信可能なチャンネルを見つけられませんでした。</div>
                        <div class="mt-1 text-text-darken-1">再度チャンネルスキャンを行ってください。</div>
                    </div>
                </div>
            </div>
        </main>
        <div v-ripple class="floating-button" @click="$router.push('/timetable/')">
            <div class="floating-button__content">
                <Icon class="floating-button__icon" icon="fluent:calendar-20-regular" width="26px" />
                <div class="floating-button__text">番組表</div>
            </div>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { Swiper as SwiperClass } from 'swiper';
import { Swiper, SwiperSlide } from 'swiper/vue';
import 'swiper/css';
import { defineComponent } from 'vue';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Message from '@/message';
import { ILiveChannel } from '@/services/Channels';
import useChannelsStore from '@/stores/ChannelsStore';
import useSettingsStore from '@/stores/SettingsStore';
import Utils, { ChannelUtils, ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'TV-Home',
    components: {
        SPHeaderBar,
        HeaderBar,
        Navigation,
        Swiper,
        SwiperSlide,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            ChannelUtils: Object.freeze(ChannelUtils),
            ProgramUtils: Object.freeze(ProgramUtils),
            Message: Object.freeze(Message),

            // 現在アクティブなタブ
            active_tab_index: 0 as number,

            // Swiper のインスタンス
            swiper_instance: null as SwiperClass | null,

            // スクロールイベントを解除するための AbortController
            scroll_abort_controller: new AbortController(),

            // ローディング中かどうか
            is_loading: true,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [] as number[],
        };
    },
    computed: {
        ...mapStores(useChannelsStore, useSettingsStore),
    },
    watch: {
        active_tab_index() {
            // content-visibility: auto の指定の関係でうまく計算されないことがある Swiper の autoHeight を強制的に再計算する
            this.swiper_instance?.updateAutoHeight();
            // 現在なアクティブなタブを Swiper 側に随時反映する
            // ローディング中のみスライドアニメーションを実行せずに即座に切り替える
            this.swiper_instance?.slideTo(this.active_tab_index, this.is_loading === true ? 0 : undefined);
        }
    },
    // 開始時に実行
    async mounted() {

        // ピン留めされているチャンネルがないなら、タブを地デジタブに切り替える
        // ピン留めができる事を示唆するためにピン留めタブ自体は残す
        if (this.settingsStore.settings.pinned_channel_ids.length === 0) {
            this.active_tab_index = 1;
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

        // この時点でピン留めされているチャンネルがないなら、タブを地デジタブに切り替える
        // ピン留めされているチャンネル自体はあるが、現在放送されていないため表示できない場合に備える
        if (this.channelsStore.channels_list_with_pinned.get('ピン留め')?.length === 0) {
            this.active_tab_index = 1;
        }

        // content-visibility: auto の指定の関係でうまく計算されないことがある Swiper の autoHeight を強制的に再計算する
        this.swiper_instance?.updateAutoHeight();

        // 画面がスクロールされたときに Swiper の autoHeight を再計算する
        window.addEventListener('scroll', () => {
            this.swiper_instance?.updateAutoHeight();
        }, { passive: true, signal: this.scroll_abort_controller.signal });

        // チャンネル情報の更新が終わったタイミングでローディング状態を解除する
        await Utils.sleep(0.01);  // 少し待たないとタブのハイライトがアニメーションされてしまう
        this.is_loading = false;
    },
    // 終了前に実行
    beforeUnmount() {

        // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
        // clearInterval() と clearTimeout() は中身共通なので問題ない
        for (const interval_id of this.interval_ids) {
            window.clearInterval(interval_id);
        }

        // スクロールイベントを解除する
        this.scroll_abort_controller.abort();
        this.scroll_abort_controller = new AbortController();
    },
    methods: {

        // チャンネルをピン留めする
        addPinnedChannel(channel: ILiveChannel) {

            // ピン留めするチャンネルの ID リストに追加 (保存は自動で行われる)
            // UI に変更を反映するため、意図的に指定チャンネルの ID が追加された配列を新しく作り再代入している
            this.settingsStore.settings.pinned_channel_ids = [...this.settingsStore.settings.pinned_channel_ids, channel.id];

            // ピン留めしたチャンネルを通知
            Message.show(`${channel.name}をピン留めしました。`);
        },

        // チャンネルをピン留めから外す
        removePinnedChannel(channel: ILiveChannel) {

            // ピン留めするチャンネルの ID リストから削除 (保存は自動で行われる)
            // UI に変更を反映するため、意図的に指定チャンネルの ID が削除された配列を新しく作り再代入している
            this.settingsStore.settings.pinned_channel_ids = this.settingsStore.settings.pinned_channel_ids.filter((id) => id !== channel.id);

            // この時点でピン留めされているチャンネルがないなら、タブを地デジタブに切り替える
            if (this.channelsStore.channels_list_with_pinned.get('ピン留め')?.length === 0) {
                this.active_tab_index = 1;
            }

            // ピン留めを外したチャンネルを通知
            Message.show(`${channel.name}のピン留めを外しました。`);
        },

        // チャンネルがピン留めされているか
        isPinnedChannel(channel: ILiveChannel): boolean {
            return this.settingsStore.settings.pinned_channel_ids.includes(channel.id);
        }
    }
});

</script>
<style lang="scss" scoped>

.channels-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    min-width: 0;  // magic!
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

        // ローディング中はタブのハイライトのアニメーションを無効にする
        .channels-tab__highlight {
            transition: none !important;
        }
    }

    // レスポンシブに変化する各要素の高さを定義
    // 実装上一部の要素の height を 100dvh から自分以外の要素の高さを引く形で実装しなければならないため、CSS 変数にまとめている
    --header-height: 65px;
    --channels-tab-height: 68px;
    --channels-list-padding-bottom: 20px;
    --bottom-navigation-height: 0px;
    @include smartphone-horizontal {
        --header-height: 0px;
        --channels-tab-height: 54px;
        --channels-list-padding-bottom: 12px;
        --bottom-navigation-height: 0px;
    }
    @include smartphone-vertical {
        --header-height: 0px;
        --channels-tab-height: 64px;
        --channels-list-padding-bottom: 12px;
        --bottom-navigation-height: 56px;
    }

    .channels-tab {
        --channels-tab-padding-bottom: 12px;
        display: flex;
        align-items: center;
        position: sticky;
        flex: none;
        top: 65px;
        height: var(--channels-tab-height);
        padding-top: 5px;
        padding-bottom: var(--channels-tab-padding-bottom);
        background: rgb(var(--v-theme-background));
        box-sizing: border-box;
        z-index: 5;

        // 下線を引く
        background: linear-gradient(
            to bottom,
            rgb(var(--v-theme-background)) calc(100% - calc(var(--channels-tab-padding-bottom) + 3px)),
            rgb(var(--v-theme-background-lighten-1))
                calc(100% - calc(var(--channels-tab-padding-bottom) + 3px))
                calc(100% - var(--channels-tab-padding-bottom)),
            rgb(var(--v-theme-background)) calc(100% - 12px)
        );

        @include smartphone-horizontal {
            top: 0px;
            padding-top: 0px;
            --channels-tab-padding-bottom: 8px;
        }
        @include smartphone-vertical {
            top: 0px;
            padding-top: 0px;
            --channels-tab-padding-bottom: 10px;
        }

        .channels-tab__buttons {
            display: flex;
            position: relative;
            align-items: center;
            max-width: 100%;
            height: 100%;
            margin-left: auto;
            margin-right: auto;
            overflow-x: auto;
            overflow-y: clip;

            .channels-tab__button {
                display: flex;
                align-items: center;
                justify-content: center;
                width: 98px;
                height: 100%;
                padding: 0;
                border-radius: 2.5px;
                color: rgb(var(--v-theme-text)) !important;
                background-color: transparent !important;
                font-size: 16px;
                letter-spacing: 0.0892857143em !important;
                text-transform: none;
                cursor: pointer;
                @include smartphone-horizontal {
                    font-size: 15px;
                }
                @include smartphone-vertical {
                    width: 90px;
                    font-size: 15px;
                }
            }

            .channels-tab__highlight {
                position: absolute;
                left: 0;
                bottom: 0;
                width: calc(100% / var(--tab-length, 0));
                height: 3px;
                background: rgb(var(--v-theme-primary));
                transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
                transform: translateX(calc(100% * var(--active-tab-index, 0)));
                will-change: transform;
            }
        }
    }

    .channels-list {
        width: 100%;
        // タブとボトムナビゲーション分の高さを引き、スクロールバーが出るよう 1px 足す
        min-height: calc(100% - var(--channels-tab-height) + var(--bottom-navigation-height) + 1px);
        padding-bottom: var(--channels-list-padding-bottom);
        background: transparent !important;
        overflow: hidden;

        @include smartphone-vertical {
            min-height: calc(100% - 54px - var(--channels-tab-height) + var(--bottom-navigation-height) + 1px);
            padding-left: 8px;
            padding-right: 8px;
        }

        .swiper-slide {
            display: flex;
            flex-direction: column;
            min-height: calc(100vh - var(--header-height) - var(--channels-tab-height) - var(--channels-list-padding-bottom) - var(--bottom-navigation-height));
            min-height: calc(100dvh - var(--header-height) - var(--channels-tab-height) - var(--channels-list-padding-bottom) - var(--bottom-navigation-height));
        }

        .channels {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(365px, 1fr));
            grid-row-gap: 12px;
            grid-column-gap: 16px;
            justify-content: center;
            // 背後を通過する別のタブのアニメーションが写らないようにするのに必要
            background: rgb(var(--v-theme-background));
            // will-change を入れておく事で、アニメーションが GPU で処理される
            will-change: transform;

            @include tablet-vertical {
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                grid-row-gap: 10px;
            }
            @include smartphone-horizontal {
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                grid-row-gap: 8px;
            }
            @include smartphone-vertical {
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                grid-row-gap: 10px;
            }

            // チャンネルリストでの content-visibility: auto; はちょっと描画上の副作用もあるので、
            // パフォーマンス向上が顕著なスマホ・タブレット (タッチデバイス) のみに適用する
            @media (hover: none) {
                content-visibility: auto;
            }

            // 1630px 以上で幅を 445px に固定
            @media (min-width: 1630px) {
                grid-template-columns: repeat(auto-fit, 445px);
            }

            // ピン留めされているチャンネルがないとき
            &.channels--length-0.channels--tab-ピン留め {
                display: flex;
                justify-content: center !important;
                flex-grow: 1;
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
                color: rgb(var(--v-theme-text));
                background: rgb(var(--v-theme-background-lighten-1));
                transition: background-color 0.15s;
                overflow: hidden;  // progressbar を切り抜くために必要
                text-decoration: none;
                user-select: none;
                box-sizing: border-box;
                cursor: pointer;
                // content-visibility: auto; を付与するだけでスマホでの描画パフォーマンスが大幅に向上する
                content-visibility: auto;
                contain-intrinsic-height: auto 233px;

                // 1列表示
                @media (max-width: 1007.9px) {
                    height: auto;
                }
                @include tablet-vertical {
                    padding: 14px 16px;
                    padding-top: 12px;
                    height: auto;
                    border-radius: 11px;
                    contain-intrinsic-height: auto 162.25px;
                }
                @include smartphone-horizontal {
                    padding: 12px 14px;
                    padding-top: 10px;
                    height: auto;
                    border-radius: 11px;
                    contain-intrinsic-height: auto 125px;
                }
                @include smartphone-vertical {
                    padding: 12px 14px;
                    padding-top: 10px;
                    height: auto;
                    border-radius: 11px;
                    contain-intrinsic-height: auto 162.25px;
                }

                &:hover {
                    background: rgb(var(--v-theme-background-lighten-2));
                }
                // タッチデバイスで hover を無効にする
                @media (hover: none) {
                    &:hover {
                        background: rgb(var(--v-theme-background-lighten-1));
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
                        background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
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
                            margin-right: 8px;
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
                        color: rgb(var(--v-theme-text-darken-1));
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
                            @include smartphone-horizontal {
                                span:nth-child(2), span:nth-child(4) {
                                    display: none;
                                }
                            }
                        }

                        @include smartphone-horizontal {
                            &-viewers {
                                margin-left: 12px !important;
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
                        color: rgb(var(--v-theme-text-darken-1));
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
                            color: rgb(var(--v-theme-text));
                            &:before {
                                opacity: 0.15;
                            }
                        }
                        &--pinned {
                            color: rgb(var(--v-theme-primary));
                            &:hover{
                                color: rgb(var(--v-theme-primary-lighten-1));
                            }
                            @include smartphone-horizontal {
                                color: rgb(var(--v-theme-secondary-lighten-2));
                                &:hover{
                                    color: rgb(var(--v-theme-secondary-lighten-3));
                                }
                            }
                            @include smartphone-vertical {
                                color: rgb(var(--v-theme-secondary-lighten-2));
                                &:hover{
                                    color: rgb(var(--v-theme-secondary-lighten-3));
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
                            display: block;
                            font-size: 14px;
                            white-space: nowrap;
                            text-overflow: ellipsis;
                        }
                        @include smartphone-vertical {
                            display: block;
                            font-size: 14px;
                            white-space: nowrap;
                            text-overflow: ellipsis;
                        }
                    }

                    &-time {
                        margin-top: 4px;
                        color: rgb(var(--v-theme-text-darken-1));
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
                        color: rgb(var(--v-theme-text-darken-1));
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
                    color: rgb(var(--v-theme-text));
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
                        color: rgb(var(--v-theme-text-darken-1));
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
                    background: rgb(var(--v-theme-gray));

                    &-progress {
                        height: 4px;
                        background: rgb(var(--v-theme-primary));
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

.floating-button {
    display: none;
    justify-content: center;
    align-items: center;
    position: fixed;
    // iPhone X 以降の Home Indicator の高さ分を考慮
    bottom: calc(72px + env(safe-area-inset-bottom));
    right: 20px;
    padding: 12px 16px;
    background: rgb(var(--v-theme-background-lighten-2));
    box-shadow: 0px 4px 7.5px rgba(0, 0, 0, 0.61);
    border-radius: 12px;
    user-select: none;
    cursor: pointer;
    z-index: 1005;
    @include smartphone-vertical {
        display: flex;
    }

    &__content {
        position: relative;
        display: flex;
        align-items: center;
    }

    &__text {
        margin-left: 8px;
        margin-right: 2px;
        color: #FFEAEA;
        font-size: 16px;
        font-weight: 500;
    }
}

</style>