<template>
    <div class="route-container">
        <Header/>
        <v-main>
            <Navigation/>
            <div class="channels-container" :class="{'channels-container--loading': loading}">
                <v-tabs centered class="channels-tab" v-model="tab">
                    <v-tab class="channels-tab__item" v-for="(channels, channels_type) in channels_list" :key="channels_type">{{channels_type}}</v-tab>
                </v-tabs>
                <v-tabs-items class="channels-list" v-model="tab">
                    <v-tab-item class="channels" v-for="(channels, channels_type) in channels_list" :key="channels_type">
                        <router-link v-ripple class="channel" v-for="channel in channels" :key="channel.id" :to="`/tv/watch/${channel.channel_id}`">
                            <div class="channel__broadcaster">
                                <img class="channel__broadcaster-icon" :src="`http://192.168.1.36:7000/api/channels/${channel.channel_id}/logo`">
                                <div class="channel__broadcaster-content">
                                    <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.channel_name}}</span>
                                    <div class="channel__broadcaster-status">
                                        <Icon icon="fa-solid:eye" height="12px" />
                                        <span class="ml-1">{{channel.watching}}</span>
                                        <Icon class="ml-4" icon="fa-solid:fire-alt" height="12px" />
                                        <span class="ml-1">{{getAttribute(channel, 'channel_force', '-')}}</span>
                                        <Icon class="ml-4" icon="bi:chat-left-text-fill" height="12px" />
                                        <span class="ml-1">{{getAttribute(channel, 'channel_comment', '-')}}</span>
                                    </div>
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
                    </v-tab-item>
                </v-tabs-items>
            </div>
        </v-main>
    </div>
</template>

<script lang="ts">
import Vue from 'vue';
import mixins from 'vue-typed-mixins'
import mixin from '@/mixins';
import { Icon } from '@iconify/vue2';
import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

export default mixins(mixin).extend({
    name: 'Home',
    components: {
        Header,
        Navigation,
		Icon,
    },
    data() {
        return {

            // タブの状態管理
            tab: null,

            // ローディング中かどうか
            loading: true,

            // インターバル ID
            // ページ遷移時に setInterval(), setTimeout() の実行を止めるのに使う
            // setInterval(), setTimeout() の返り値を登録する
            interval_ids: [],

            // チャンネルリスト
            channels_list: null,
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
        this.interval_ids.push(setTimeout(() => {

            // チャンネル情報を更新
            this.update();

            // チャンネル情報を定期的に更新
            this.interval_ids.push(setInterval(() => {
                this.update();
            }, 60 * 1000));  // 1分おき

        }, residue_second * 1000));
    },
    // 終了時に実行
    destroyed() {

        // clearInterval() ですべての setInterval(), setTimeout() の実行を止める
        // clearInterval() と clearTimeout() は中身共通なので問題ない
        for (const interval_id in this.interval_ids) {
            clearInterval(parseInt(interval_id));  // 型推論がうまく効かないのでこうなる…つらい
        }
    },
    methods: {
        // チャンネル情報一覧を取得し、画面を更新する
        update() {

            // チャンネル情報一覧 API にアクセス
            Vue.axios.get('http://192.168.1.36:7000/api/channels').then((response) => {

                // is_display が true のチャンネルのみに絞り込むフィルタ関数
                // 放送していないサブチャンネルを表示から除外する
                function filter(channel: any) {
                    return channel.is_display;
                }

                // チャンネルリストを再構築
                // 1つでもチャンネルが存在するチャンネルタイプのみ表示するように
                // たとえば SKY (スカパー！プレミアムサービス) のタブは SKY に属すチャンネルが1つもない（=受信できない）なら表示されない
                this.channels_list = {};
                if (response.data.GR.length > 0) this.channels_list['地デジ'] = response.data.GR.filter(filter);
                if (response.data.BS.length > 0) this.channels_list['BS'] = response.data.BS.filter(filter);
                if (response.data.CS.length > 0) this.channels_list['CS'] = response.data.CS.filter(filter);
                if (response.data.SKY.length > 0) this.channels_list['SKY'] = response.data.SKY.filter(filter);

                // ローディング状態を解除
                this.loading = false;
            });
        }
    }
});
</script>

<style lang="scss">
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
        padding-top: 12px;
        padding-bottom: 26px;
        background:var(--v-background-base);
        z-index: 1;

        .v-tabs-bar {
            height: 58px;
            background: linear-gradient(to bottom, var(--v-background-base) calc(100% - 3px), var(--v-background-lighten1) 3px);  // 下線を引く

            .v-tabs-slider-wrapper {
                height: 3px !important;
                transition: left 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
            }

            .channels-tab__item {
                width: 98px;
                padding: 0;
                color: var(--v-text-base) !important;
                font-size: 16px;
            }
        }
    }

    .channels-list {
        padding-bottom: 32px;
        background: transparent !important;
        overflow: inherit;

        .v-window__container {
            min-height: calc(100vh - 65px);
        }
        .channels {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(370px, 1fr));
            grid-row-gap: 16px;
            grid-column-gap: 16px;
            justify-content: center;

            // 1630px 以上で幅を 445px に固定
            @media screen and (min-width: 1630px) {
                & {
                    grid-template-columns: repeat(auto-fit, 445px);
                }
            }

            .channel {
                display: flex;
                flex-direction: column;
                position: relative;
                height: 275px;
                padding: 18px 24px;
                border-radius: 11px;
                color: var(--v-text-base);
                background: var(--v-background-lighten1);
                transition: background-color 0.15s;
                overflow: hidden;  // progressbar を切り抜くために必要
                text-decoration: none;
                user-select: none;
                cursor: pointer;

                &:hover {
                    background: var(--v-background-lighten2);
                }

                .channel__broadcaster {
                    display: flex;
                    height: 44px;

                    &-icon {
                        display: inline-block;
                        flex-shrink: 0;
                        width: 80px;
                        height: 44px;
                        border-radius: 5px;
                        background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
                        object-fit: cover;
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
                    }

                    &-status {
                        display: flex;
                        align-items: center;
                        margin-top: 2px;
                        font-size: 12px;
                        color: var(--v-text-darken1);
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
                    }

                    &-time {
                        margin-top: 4px;
                        color: var(--v-text-darken1);
                        font-size: 13.5px;
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
                    }
                }

                .channel__program-following {
                    display: flex;
                    flex-direction: column;
                    color: var(--v-text-darken1);
                    font-size: 12.5px;

                    &-title {
                       display: flex;
                       align-items: center;
                       &-decorate {
                            flex-shrink: 0;
                       }
                       &-icon {
                            flex-shrink: 0;
                            margin-left: 3px;
                       }
                       &-text {
                            margin-left: 2px;
                            overflow: hidden;
                            white-space: nowrap;
                            text-overflow: ellipsis;  // はみ出た部分を … で省略
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
