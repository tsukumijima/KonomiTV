<template>
    <div class="navigation-container elevation-8">
        <nav class="navigation">
            <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/tv/">
                <Icon class="navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
                <span class="navigation__link-text">テレビをみる</span>
            </router-link>
            <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/videos/">
                <Icon class="navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
                <span class="navigation__link-text">ビデオをみる</span>
            </router-link>
            <router-link v-ripple class="navigation__link" active-class="navigation__link--active" to="/schedules/">
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
            <a v-ripple class="navigation__link" active-class="navigation__link--active" href="https://github.com/tsukumijima/KonomiTV">
                <Icon class="navigation__link-icon" icon="fluent:info-16-regular" width="26px" />
                <span class="navigation__link-text">version {{version}}</span>
            </a>
        </nav>
    </div>
</template>

<script lang="ts">
import mixins from 'vue-typed-mixins'
import mixin from '@/mixins';
import { Icon } from '@iconify/vue2';

export default mixins(mixin).extend({
	components: {
		Icon,
	},
});
</script>

<style lang="scss" scoped>
.navigation-container {
    flex-shrink: 0;
    width: 220px;  // .navigation を fixed にするため、浮いた分の幅を確保する
    background: var(--v-background-lighten1);

    .navigation {
        display: flex;
        flex-direction: column;
        position: fixed;
        width: 220px;
        top: 65px;  // ヘッダーの高さ分
        left: 0px;
        // スマホ・タブレットのブラウザでアドレスバーが完全に引っ込むまでビューポートの高さが更新されず、
        // その間下に何も背景がない部分ができてしまうのを防ぐ
        bottom: -100px;
        padding: 22px 12px 122px;
        background: var(--v-background-lighten1);
        z-index: 1;

        .navigation__link {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            height: 52px;
            padding-left: 16px;
            padding-right: 16px;
            border-radius: 11px;
            font-size: 16px;
            color: var(--v-text-base);
            transition: background-color 0.15s;
            text-decoration: none;
            user-select: none;

            &:hover {
                background: var(--v-background-lighten2);
            }

            + .navigation__link {
                margin-top: 4px;
            }
            &--active {
                color: var(--v-primary-base);
                background: var(--v-background-lighten2);
            }

            .navigation__link-icon {
                margin-right: 14px;
            }
        }
    }
}
</style>
