<template>
    <div class="route-container">
        <Header/>
        <v-main>
            <Navigation/>
            <div class="channels-container">
                <v-tabs centered class="channels-tab" v-model="tab">
                    <v-tab class="channels-tab__item">地デジ</v-tab>
                    <v-tab class="channels-tab__item">BS</v-tab>
                    <v-tab class="channels-tab__item">CS</v-tab>
                </v-tabs>
                <v-tabs-items class="channels-list" v-model="tab">
                    <v-tab-item class="channels" v-for="channels in channels_list" :key="channels.id">
                        <div v-ripple class="channel" v-for="channel in channels" :key="channel.id">
                            <div class="channel__broadcaster">
                                <img class="channel__broadcaster-icon" :src="`http://192.168.1.36:7000/api/channels/${channel.channel_id}/logo`">
                                <div class="channel__broadcaster-content">
                                    <span class="channel__broadcaster-name">Ch: {{channel.channel_number}} {{channel.channel_name}}</span>
                                    <div class="channel__broadcaster-status">
                                        <Icon icon="fa-solid:eye" height="12px" />
                                        <span class="ml-1">{{channel.watching}}</span>
                                        <Icon class="ml-4" icon="fa-solid:fire-alt" height="12px" />
                                        <span class="ml-1">{{channel.channel_force}}</span>
                                        <Icon class="ml-4" icon="bi:chat-left-text-fill" height="12px" />
                                        <span class="ml-1">0</span>
                                    </div>
                                </div>
                            </div>
                            <div class="channel__program-present">
                                <span class="channel__program-present-title"></span>
                                <span class="channel__program-present-time">2021/06/21 (月) 08:15 ～ 09:55 (105分)</span>
                                <span class="channel__program-present-description"></span>
                            </div>
                            <v-spacer></v-spacer>
                            <div class="channel__program-following">
                                <div class="channel__program-following-title">
                                    <span class="channel__program-following-title-decorate">NEXT</span>
                                    <Icon class="channel__program-following-title-icon" icon="fluent:fast-forward-20-filled" width="16px" />
                                    <span class="channel__program-following-title-text">NHKニュース おはよう日本“潜在看護師”接種業務にああああああ</span>
                                </div>
                                <span class="channel__program-following-time">2021/06/21 (月) 06:30 ～ 07:00 (30分)</span>
                            </div>
                            <div class="channel__progressbar">
                                <div class="channel__progressbar-progress w-25"></div>
                            </div>
                        </div>
                    </v-tab-item>
                </v-tabs-items>
            </div>
        </v-main>
    </div>
</template>

<script lang="ts">
import Vue from 'vue';
import { Icon } from '@iconify/vue2';
import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

export default Vue.extend({
    name: 'Home',
    components: {
        Header,
        Navigation,
		Icon,
    },
    data() {
        return {
            tab: null,
            channels_list: null,
        }
    },
    created() {
        this.init();
    },
    methods: {
        init() {
            Vue.axios.get('http://192.168.1.36:7000/api/channels').then((response) => {
                this.channels_list = response.data;
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
        background: var(--v-background-base) !important;
        overflow: inherit;

        .channels {
            display: grid;
            grid-template-columns: repeat(auto-fit, 430px);
            grid-row-gap: 16px;
            grid-column-gap: 16px;
            justify-content: center;

            .channel {
                display: flex;
                flex-direction: column;
                position: relative;
                width: 430px;
                height: 275px;
                padding: 18px 24px;
                border-radius: 11px;
                background: var(--v-background-lighten1);
                overflow: hidden;  // progressbar を切り抜くために必要
                user-select: none;
                cursor: pointer;

                .channel__broadcaster {
                    display: flex;
                    height: 44px;

                    &-icon {
                        display: inline-block;
                        width: 80px;
                        height: 44px;
                        border-radius: 5px;
                        object-fit: cover;
                    }

                    &-content {
                        display: flex;
                        flex-direction: column;
                        margin-left: 16px;
                    }

                    &-name {
                        font-size: 18px;
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
                        font-feature-settings: "palt" 1;  // 文字詰め
                        letter-spacing: 0.06em;  // 字間を少し空ける
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
                           margin-left: 3px;
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
                        transition: 0.3s ease;
                    }
                }
            }
        }
    }
}
</style>
