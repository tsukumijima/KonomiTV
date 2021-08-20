<template>
    <div class="h-100">
        <Header/>
        <v-main>
            <Navigation/>
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
