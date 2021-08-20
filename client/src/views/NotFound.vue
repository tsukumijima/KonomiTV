<template>
    <div class="route-container">
        <Header/>
        <v-main>
            <Navigation/>
            <div class="d-flex justify-center align-center w-100">
                <div class="d-flex justify-center align-center flex-column">
                    <h1>404 Not Found</h1>
                    <span class="mt-2">お探しのページは存在しないか、鋭意開発中です。</span>
                </div>
            </div>
        </v-main>
    </div>
</template>

<script lang="ts">
import Vue from 'vue';
import Header from '@/components/Header.vue';
import Navigation from '@/components/Navigation.vue';

export default Vue.extend({
    name: 'Home',
    components: {
        Header,
        Navigation,
    },
});
</script>
