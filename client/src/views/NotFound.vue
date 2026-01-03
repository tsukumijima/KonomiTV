<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <SPHeaderBar :hide-on-smartphone-vertical="true" />
            <div class="d-flex justify-center align-center w-100">
                <div class="d-flex justify-center align-center flex-column">
                    <h1>Not Found, or Under Development...</h1>
                    <span class="mt-4 text-text-darken-1">お探しのページは存在しないか、鋭意開発中です。</span>
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';

</script>
<style lang="scss" scoped>

h1 {
    @include tablet-vertical {
        font-size: 24px !important;
    }
    @include smartphone-horizontal {
        font-size: 24px !important;
    }
    @include smartphone-vertical {
        font-size: 24px !important;
        text-align: center;
    }
}
span {
    @include smartphone-horizontal {
        font-size: 15px !important;
    }
    @include smartphone-vertical {
        font-size: 14px !important;
    }
}

</style>