<template>
    <v-toolbar absolute
        color="background"
        elevation="8"
        width="100%"
        height="65px">
        <v-toolbar-title class="ml-6">
            Konomi
        </v-toolbar-title>
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
</style>
