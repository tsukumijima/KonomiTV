<template>
    <header class="header">
        <router-link v-ripple class="konomitv-logo" to="/tv/">
            <img class="konomitv-logo__image" src="/assets/images/logo.svg" height="21">
        </router-link>
        <v-spacer></v-spacer>
        <div v-ripple class="search-button" @click="Message.warning('検索機能は現在開発中です。')">
            <Icon icon="fluent:search-20-filled" height="24px" />
        </div>
    </header>
</template>
<script lang="ts" setup>

import Message from '@/message';

</script>
<style lang="scss" scoped>

.header {
    display: none;
    justify-content: center;
    align-items: center;
    flex-shrink: 0;
    padding: 0px 16px;
    padding-top: 14px;
    height: 48px;
    background: rgb(var(--v-theme-background));
    @include smartphone-vertical {
        display: flex;
    }

    .konomitv-logo {
        display: block;
        padding: 12px 8px;
        border-radius: 8px;

        &__image {
            display: block;
        }
    }

    .search-button {
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        margin-right: -2px;
        padding: 2px;
        border-radius: 8px;
    }
}

</style>