<template>
    <v-app id="app">
        <router-view/>
    </v-app>
</template>

<style lang="scss">
body .v-application {
    font-family: "Open Sans", "Noto Sans JP", sans-serif;
    font-weight: 500;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
body .v-main {
    height: 100%;
}
body .v-main__wrap {
    display: flex;
    height: 100%;
    padding-top: 65px !important;
}

// ユーティリティ
.w-25 {
    width: 25%;
}
.w-50 {
    width: 50%;
}
.w-75 {
    width: 75%;
}
.w-100 {
    width: 100%;
}
.h-25 {
    height: 25%;
}
.h-50 {
    height: 50%;
}
.h-75 {
    height: 75%;
}
.h-100 {
    height: 100%;
}
</style>
