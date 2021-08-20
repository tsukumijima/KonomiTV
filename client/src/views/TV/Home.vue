<template>
    <div class="route-container">
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
    created() {
        this.init();
    },
    methods: {
        init() {
            Vue.axios.get('http://localhost:7000/api/channels').then((response) => {
                console.log(response.data)
            });
        }
    }
});
</script>
