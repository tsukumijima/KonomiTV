<template>
    <div>
        <div class="navigation-container elevation-8">
            <nav class="navigation">
                <div class="navigation-scroll">
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/tv/">
                        <Icon class="navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
                        <span class="navigation__link-text">テレビをみる</span>
                    </router-link>
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/videos/">
                        <Icon class="navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
                        <span class="navigation__link-text">ビデオをみる</span>
                    </router-link>
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/timetable/">
                        <Icon class="navigation__link-icon" icon="fluent:calendar-ltr-20-regular" width="26px" />
                        <span class="navigation__link-text">番組表</span>
                    </router-link>
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/captures/">
                        <Icon class="navigation__link-icon" icon="fluent:image-multiple-24-regular" width="26px" />
                        <span class="navigation__link-text">キャプチャ</span>
                    </router-link>
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/watchlists/">
                        <Icon class="navigation__link-icon" icon="ic:round-playlist-play" width="26px" />
                        <span class="navigation__link-text">ウォッチリスト</span>
                    </router-link>
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/histories/">
                        <Icon class="navigation__link-icon" icon="fluent:history-16-regular" width="26px" />
                        <span class="navigation__link-text">視聴履歴</span>
                    </router-link>
                    <v-spacer></v-spacer>
                    <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/settings/">
                        <Icon class="navigation__link-icon" icon="fluent:settings-20-regular" width="26px" />
                        <span class="navigation__link-text">設定</span>
                    </router-link>
                    <a v-ripple class="navigation__link" active-class="navigation__link--active" href="https://github.com/tsukumijima/KonomiTV"
                        :class="{
                            'navigation__link--version': Utils.version.includes('-dev'),
                            'navigation__link--highlight': is_update_available,
                        }"
                        v-tooltip.top="is_update_available ? `アップデートがあります (version ${latest_version})` : ''">
                        <Icon class="navigation__link-icon" icon="fluent:info-16-regular" width="26px" />
                        <span class="navigation__link-text">version {{Utils.version}}</span>
                    </a>
                </div>
            </nav>
        </div>
        <BottomNavigation />
    </div>
</template>
<script lang="ts">

import Vue from 'vue';

import BottomNavigation from '@/components/BottomNavigation.vue';
import Version from '@/services/Version';
import Utils from '@/utils';

export default Vue.extend({
    name: 'Navigation',
    components: {
        BottomNavigation,
    },
    data() {
        return {

            // ユーティリティをテンプレートで使えるように
            Utils: Utils,

            // 最新のバージョン
            latest_version: null as string | null,

            // アップデートが利用可能か
            is_update_available: false as boolean,
        }
    },
    async created() {
        try {

            // バージョン情報を取得
            const version_info = await Version.fetchServerVersion();
            if (version_info === null) {
                return;
            }

            this.latest_version = version_info.latest_version;

            // 最新のサーバーバージョンが取得できなかった場合は中断
            if (this.latest_version === null) {
                return;
            }

            // もし現在のサーバーバージョン (-dev を除く) と最新のサーバーバージョンが異なるなら、アップデートが利用できる旨を表示する
            // 現在のサーバーバージョンが -dev 付きで、かつ最新のサーバーバージョンが -dev なし の場合 (リリース版がリリースされたとき) も同様に表示する
            // つまり開発版だと同じバージョンのリリース版がリリースされたときにしかアップデート通知が表示されない事になるが、ひとまずこれで…
            if ((version_info.version.includes('-dev') === false && version_info.version !== version_info.latest_version) ||
                (version_info.version.includes('-dev') === true && version_info.version.replace('-dev', '') === version_info.latest_version)) {
                this.is_update_available = true;
            }

        } catch (error) {
            throw new Error(error);  // エラー内容をコンソールに表示して終了
        }
    }
});

</script>
<style lang="scss" scoped>

.navigation-container {
    flex-shrink: 0;
    width: 220px;  // .navigation を fixed にするため、浮いた分の幅を確保する
    background: var(--v-background-lighten1);
    @include smartphone-horizontal {
        width: 210px;
    }
    @include smartphone-horizontal-short {
        width: 190px;
    }
    @include smartphone-vertical {
        display: none;
    }

    .navigation {
        position: fixed;
        width: 220px;
        top: 65px;  // ヘッダーの高さ分
        left: 0px;
        // スマホ・タブレットのブラウザでアドレスバーが完全に引っ込むまでビューポートの高さが更新されず、
        // その間下に何も背景がない部分ができてしまうのを防ぐ
        bottom: -100px;
        padding-bottom: 100px;
        background: var(--v-background-lighten1);
        z-index: 1;
        @include smartphone-horizontal {
            top: 48px;
            width: 210px;
        }
        @include smartphone-horizontal-short {
            width: 190px;
        }

        .navigation-scroll {
            display: flex;
            flex-direction: column;
            height: 100%;
            padding: 22px 12px;
            overflow-y: auto;
            @include smartphone-horizontal {
                padding: 10px 12px;
            }
            @include smartphone-horizontal-short {
                padding: 10px 8px;
            }
            &::-webkit-scrollbar-track {
                background: var(--v-background-lighten1);
            }

            .navigation__link {
                display: flex;
                align-items: center;
                flex-shrink: 0;
                height: 52px;
                padding-left: 16px;
                margin-top: 4px;
                border-radius: 11px;
                font-size: 16px;
                color: var(--v-text-base);
                transition: background-color 0.15s;
                text-decoration: none;
                user-select: none;
                @include smartphone-horizontal {
                    height: 40px;
                    padding-left: 12px;
                    border-radius: 9px;
                    font-size: 15px;
                }

                &:hover {
                    background: var(--v-background-lighten2);
                }
                &:first-of-type {
                    margin-top: 0;
                }
                &--active {
                    color: var(--v-primary-base);
                    background: #5b2d3c;
                    &:hover {
                        background: #5b2d3c;
                    }
                }
                &--highlight {
                    color: var(--v-secondary-lighten1);
                }
                &--version {
                    font-size: 15px;
                    @include smartphone-horizontal {
                        font-size: 14.5px;
                    }
                }

                .navigation__link-icon {
                    margin-right: 14px;
                    @include smartphone-horizontal {
                        margin-right: 10px;
                    }
                }
            }
        }
    }
}

</style>