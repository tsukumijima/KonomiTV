<template>
    <div class="route-container">
        <Header/>
        <main>
            <Navigation/>
            <div class="d-flex justify-center align-center w-100">
                <div class="d-flex justify-center align-center flex-column">
                    <h1>Not Found, or Under Development...</h1>
                    <span class="mt-4 text--text text--darken-1">お探しのページは存在しないか、鋭意開発中です。</span>
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts">

import Vue from 'vue';

import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

export default Vue.extend({
    name: 'NotFound',
    components: {
        Header,
        Navigation,
    },
});

</script>