<template>
    <div class="series-container">
        鋭意実装中…
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import usePlayerStore from '@/stores/PlayerStore';
import Utils from '@/utils';

export default defineComponent({
    name: 'Panel-SeriesTab',
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
        };
    },
    computed: {
        ...mapStores(usePlayerStore),
    }
});

</script>
<style lang="scss" scoped>

.series-container {
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;
    @include tablet-vertical {
        margin-top: 20px;
        padding-left: 24px;
        padding-right: 24px;
    }
    @include smartphone-horizontal {
        margin-top: 12px;
    }
    @include smartphone-vertical {
        margin-top: 14px;
    }
}

</style>