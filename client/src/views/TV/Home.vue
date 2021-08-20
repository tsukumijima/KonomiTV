<template>
    <div class="route-container">
        <Header/>
        <v-main>
            <Navigation/>
            <div class="channels-container">
                <v-tabs centered class="channels-tab">
                    <v-tab class="channels-tab__item">ピン留め</v-tab>
                    <v-tab class="channels-tab__item">地デジ</v-tab>
                    <v-tab class="channels-tab__item">BS</v-tab>
                    <v-tab class="channels-tab__item">CS</v-tab>
                </v-tabs>
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

<style lang="scss">
.channels-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    margin: 12px 21px;

    .channels-tab .v-tabs-bar {
        height: 58px;
        background: linear-gradient(to bottom, var(--v-background-base) calc(100% - 3px), var(--v-background-lighten1) 3px);  // 下線を引く

        .v-tabs-slider-wrapper {
            height: 3px !important;
        }

        .channels-tab__item {
            width: 98px;
            padding: 0;
            color: var(--v-text-base) !important;
            font-size: 16px;
        }
    }
}
</style>
