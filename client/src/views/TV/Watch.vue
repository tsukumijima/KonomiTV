<template>
    <div class="route-container">
        <Header/>
        <v-main>
            <Navigation/>
            <div class="d-flex justify-center align-center w-100">
                <div class="d-flex justify-center align-center flex-column">
                    <h1>視聴ページ</h1>
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
    data() {
        return {
        }
    },
    // 開始時に実行
    created() {
    },
    // 終了時に実行
    destroyed() {
    },
    methods: {
    }
});
</script>

<style lang="scss">

</style>
