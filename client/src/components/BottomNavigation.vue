<template>
    <v-bottom-navigation class="bottom-navigation-container elevation-12" color="primary" grow>
        <v-btn to="/tv/">
            <span class="mt-1">テレビをみる</span>
            <Icon icon="fluent:tv-20-regular" width="30px" />
        </v-btn>
        <v-btn to="/videos/">
            <span class="mt-1">ビデオをみる</span>
            <Icon icon="fluent:movies-and-tv-20-regular" width="30px" />
        </v-btn>
        <v-btn to="/settings/">
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
    z-index: 10;
    @include smartphone-vertical {
        display: flex;
    }
    .v-btn span {
        font-weight: bold;
    }
}

</style>