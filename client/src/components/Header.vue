<template>
    <v-toolbar absolute
        color="background"
        elevation="8"
        width="100%"
        height="65px">
        <router-link v-ripple class="logo ml-6" to="/tv/">
            <img class="logo__image" src="/assets/img/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
        <v-btn icon class="mr-6">
            <v-icon>mdi-dots-vertical</v-icon>
        </v-btn>
    </v-toolbar>
</template>

<style lang="scss" scoped>
body .v-toolbar {
    position: fixed;
    z-index: 10;
}

.logo {
    padding: 12px 8px;
    border-radius: 8px;

    &__image {
        display: block;
    }
}
</style>
