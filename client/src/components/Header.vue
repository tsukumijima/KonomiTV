<template>
    <v-toolbar absolute class="header"
        color="background"
        elevation="8"
        width="100%">
        <router-link v-ripple class="logo ml-3 ml-md-6" to="/tv/">
            <img class="logo__image" src="/assets/img/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
        <v-btn icon class="mr-3 mr-md-6">
            <v-icon>mdi-dots-vertical</v-icon>
        </v-btn>
    </v-toolbar>
</template>

<style lang="scss">
body .v-toolbar.header {
    position: fixed;
    height: 65px !important;
    z-index: 10;
    .v-toolbar__content {
        height: 65px !important;
    }
    @media screen and (max-height: 450px) {
        height: 48px !important;
        .v-toolbar__content {
            height: 48px !important;
        }
    }

    .logo {
        padding: 12px 8px;
        border-radius: 8px;

        &__image {
            display: block;
            @media screen and (max-height: 450px) {
                height: 19.5px;
            }
        }
    }
}
</style>
