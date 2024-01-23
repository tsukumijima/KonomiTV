<template>
    <v-bottom-navigation class="bottom-navigation-container elevation-12" color="primary" grow active>
        <v-btn class="bottom-navigation-button" to="/tv/"
            :class="{'v-btn--active': $route.path.startsWith('/tv')}">
            <Icon icon="fluent:tv-20-regular" width="30px" />
            <span class="mt-1">テレビをみる</span>
        </v-btn>
        <v-btn class="bottom-navigation-button" to="/videos/"
            :class="{'v-btn--active': $route.path.startsWith('/videos')}">
            <Icon icon="fluent:movies-and-tv-20-regular" width="30px" />
            <span class="mt-1">ビデオをみる</span>
        </v-btn>
        <v-btn class="bottom-navigation-button" to="/settings/"
            :class="{'v-btn--active': $route.path.startsWith('/settings')}">
            <Icon icon="fluent:settings-20-regular" width="30px" />
            <span class="mt-1">設定</span>
        </v-btn>
    </v-bottom-navigation>
</template>
<style lang="scss">

.bottom-navigation-container .v-btn--active > .v-btn__overlay {
    opacity: 0 !important;
}

</style>
<style lang="scss" scoped>

.bottom-navigation-container {
    display: none;
    position: fixed;
    bottom: 0;
    background: rgb(var(--v-theme-background-lighten-1));
    z-index: 8;

    @include smartphone-vertical {
        display: flex;
        // iPhone X 以降の Home Indicator の高さ分
        padding-bottom: env(safe-area-inset-bottom);
        box-sizing: content-box;
    }

    .v-btn.bottom-navigation-button {
        flex-basis: 0;  // 均等に割り振る
        padding: 0 !important;
        color: rgb(var(--v-theme-text-darken-1)) !important;
        font-weight: bold;

        &.v-btn--active {
            color: rgb(var(--v-theme-primary)) !important;
        }
    }
}

</style>