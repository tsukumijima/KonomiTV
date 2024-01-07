<template>
    <v-bottom-navigation class="bottom-navigation-container elevation-12" color="primary" grow>
        <v-btn class="bottom-navigation-button" to="/tv/">
            <span class="mt-1">テレビをみる</span>
            <Icon icon="fluent:tv-20-regular" width="30px" />
        </v-btn>
        <v-btn class="bottom-navigation-button" to="/videos/">
            <span class="mt-1">ビデオをみる</span>
            <Icon icon="fluent:movies-and-tv-20-regular" width="30px" />
        </v-btn>
        <v-btn class="bottom-navigation-button" to="/settings/">
            <span class="mt-1">設定</span>
            <Icon icon="fluent:settings-20-regular" width="30px" />
        </v-btn>
    </v-bottom-navigation>
</template>
<style lang="scss" scoped>

.bottom-navigation-container {
    display: none;
    position: fixed;
    bottom: 0;
    z-index: 8;
    @include smartphone-vertical {
        display: flex;
        // iPhone X 以降の Home Indicator の高さ分
        padding-bottom: env(safe-area-inset-bottom);
        box-sizing: content-box;
    }
    .v-btn.bottom-navigation-button {
        color: rgb(var(--v-theme-text-darken-1)) !important;
        font-weight: bold;
        &.v-btn--active {
            color: rgb(var(--v-theme-primary)) !important;
        }
    }
}

</style>