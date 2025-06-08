<template>
    <nav class="watch-navigation"
            @mousemove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})"
            @touchmove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})"
            @click="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})">
        <router-link v-ripple class="watch-navigation__icon" to="/tv/">
            <img class="watch-navigation__icon-image" src="/assets/images/icon.svg" width="23px">
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/tv')}"
            v-ftooltip.right="'テレビをみる'" to="/tv/">
            <Icon class="watch-navigation__link-icon" icon="fluent:tv-20-regular" width="26px" />
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/videos')}"
            v-ftooltip.right="'ビデオをみる'"  to="/videos/">
            <Icon class="watch-navigation__link-icon" icon="fluent:movies-and-tv-20-regular" width="26px" />
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/timetable')}"
            v-ftooltip.right="'番組表'" to="/timetable/">
            <Icon class="watch-navigation__link-icon" icon="fluent:calendar-ltr-20-regular" width="26px" />
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/reservations')}"
            v-ftooltip.right="'録画予約'" to="/reservations/">
            <Icon class="watch-navigation__link-icon" icon="fluent:timer-16-regular" width="26px" style="padding: 0.5px;"/>
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/captures')}"
            v-ftooltip.right="'キャプチャ'" to="/captures/">
            <Icon class="watch-navigation__link-icon" icon="fluent:image-multiple-24-regular" width="26px" />
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/mylist')}"
            v-ftooltip.right="'マイリスト'" to="/mylist/">
            <Icon class="watch-navigation__link-icon" icon="ic:round-playlist-play" width="26px" />
        </router-link>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/watched-history')}"
            v-ftooltip.right="'視聴履歴'" to="/watched-history/">
            <Icon class="watch-navigation__link-icon" icon="fluent:history-20-regular" width="26px" />
        </router-link>
        <v-spacer></v-spacer>
        <router-link v-ripple class="watch-navigation__link" active-class="watch-navigation__link--active"
            :class="{'watch-navigation__link--active': $route.path.startsWith('/settings')}"
            v-ftooltip.right="'設定'" to="/settings/">
            <Icon class="watch-navigation__link-icon" icon="fluent:settings-20-regular" width="26px" />
        </router-link>
    </nav>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import usePlayerStore from '@/stores/PlayerStore';

export default defineComponent({
    name: 'Watch-Navigation',
    computed: {
        ...mapStores(usePlayerStore),
    }
});

</script>
<style lang="scss" scoped>

.watch-navigation {
    display: flex;
    flex-direction: column;
    position: fixed;
    width: 68px;
    top: 0px;
    left: 0px;
    // スマホ・タブレットのブラウザでアドレスバーが完全に引っ込むまでビューポートの高さが更新されず、
    // その間下に何も背景がない部分ができてしまうのを防ぐ
    bottom: -100px;
    padding: 18px 8px 122px;
    background: #2F221F80;
    transition: opacity 0.3s, visibility 0.3s;
    opacity: 0;
    visibility: hidden;
    z-index: 10;
    @include tablet-vertical {
        display: none;
    }
    @include smartphone-horizontal {
        display: none;
    }
    @include smartphone-vertical {
        display: none;
    }

    .watch-navigation__icon {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 52px;
        margin-bottom: 17px;
        border-radius: 11px;
        font-size: 16px;
        color: rgb(var(--v-theme-text));
        transition: background-color 0.15s;
        text-decoration: none;
        user-select: none;
        @include smartphone-horizontal {
            height: 32px;
            border-radius: 10px;
        }
    }

    @include smartphone-horizontal {
        // スペースを確保するため、スペーサーを非表示に
        div.spacer {
            display: none;
        }
    }

    .watch-navigation__link {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 52px;
        border-radius: 11px;
        font-size: 16px;
        color: rgb(var(--v-theme-text));
        transition: background-color 0.15s;
        text-decoration: none;
        user-select: none;
        @include smartphone-horizontal {
            height: 44px;
            border-radius: 10px;
            // スペースを確保するため、設定・バージョン情報のアイコンを非表示に
            &:nth-last-child(1), &:nth-last-child(2) {
                display: none;
            }
        }

        &:hover {
            background: #433532A0;
        }

        @include smartphone-horizontal {
            &-icon {
                width: 26px;
                height: 26px;
            }
        }

        &--active {
            color: rgb(var(--v-theme-primary));
            background: #433532A0;
        }
        + .watch-navigation__link {
            margin-top: 4px;
            @include smartphone-horizontal {
                margin-top: auto;
            }
        }
    }
}

</style>