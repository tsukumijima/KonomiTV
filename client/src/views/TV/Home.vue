<template>
    <v-main>
        <Header/>
    </v-main>
</template>

<script lang="ts">
import Vue from 'vue';
import Header from '@/components/Header.vue';

export default Vue.extend({
    name: 'Home',
    components: {
        Header,
    },
});
</script>
