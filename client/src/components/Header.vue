<template>
    <header class="header">
        <router-link v-ripple class="konomitv-logo ml-3 ml-md-6" to="/tv/">
            <img class="konomitv-logo__image" src="/assets/images/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
    </header>
</template>
<style lang="scss" scoped>

.header {
    position: fixed;
    display: flex;
    align-items: center;
    width: 100%;
    height: 65px;
    padding: 4px 16px;
    background: var(--v-background-base);
    box-shadow: 0px 5px 5px -3px rgb(0 0 0 / 20%),
                0px 8px 10px 1px rgb(0 0 0 / 14%),
                0px 3px 14px 2px rgb(0 0 0 / 12%);
    z-index: 10;

    @include smartphone-horizontal {
        width: 210px;
        height: 48px;
        justify-content: center;
    }
    @include smartphone-horizontal-short {
        width: 190px;
    }

    .spacer {
        @include smartphone-horizontal {
            display: none;
        }
    }

    .konomitv-logo {
        display: block;
        padding: 12px 8px;
        border-radius: 8px;
        @include smartphone-horizontal {
            margin: 0 !important;
        }

        &__image {
            display: block;
            @include smartphone-horizontal {
                height: 19.5px;
            }
        }
    }
}

</style>