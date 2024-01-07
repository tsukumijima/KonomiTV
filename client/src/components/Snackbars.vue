<template>
    <div class="snackbar-container">
        <!-- Vuetify の Snackbar を使うとかえってスタック上に積み上げるのが困難だったため独自に実装した -->
        <div class="snackbar elevation-8"
            :class="{
                [`bg-${snackbar.level === 'default' ? 'background-lighten-2' : snackbar.level}`]: true,
                'snackbar--showing' : snackbar.showing,
                'snackbar--destroying' : snackbar.destroying,
            }"
            v-for="snackbar in useSnackbarsStore().snackbars" :key="snackbar.id">
            <div class="snackbar__content">
                <!-- level に応じたアイコンを表示する -->
                <v-icon class="mr-3" size="large" v-if="snackbar.level === 'success'">mdi-check-circle</v-icon>
                <v-icon class="mr-3" size="large" v-else-if="snackbar.level === 'warning'">mdi-alert-circle</v-icon>
                <v-icon class="mr-3" size="large" v-else-if="snackbar.level === 'error'">mdi-close-circle</v-icon>
                <v-icon class="mr-3" size="large" v-else-if="snackbar.level === 'info'">mdi-information</v-icon>
                <div class="d-flex flex-column">
                    <p v-for="(text, index) in snackbar.text.split('\n')" :key="index">{{ text }}</p>
                </div>
            </div>
            <v-btn class="snackbar__action" :class="{'text-primary': snackbar.level === 'default'}" variant="text"
                @click="snackbar.hide()">閉じる</v-btn>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { useSnackbarsStore } from '@/stores/SnackbarsStore';

</script>
<style lang="scss" scoped>

.snackbar-container {
    display: flex;
    flex-direction: column-reverse;  // 下から上に積み上がるようにする
    align-items: center;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    pointer-events: none;
    z-index: 9999;
    @include smartphone-vertical {
        // BottomNavigation と重ならないようにする
        padding-bottom: calc(env(safe-area-inset-bottom) + 56px) !important;
    }

    // Vuetify 2 の v-snackbar のスタイル定義をほぼそのまま移植したもの
    // Vuetify 3 の v-snackbar は HTML / CSS から大幅に変更されているため、以前の外観を再現すべく別途移植した
    .snackbar {
        display: flex;
        align-items: center;
        position: relative;
        margin: 8px;
        margin-top: 0px;
        max-width: 672px;
        min-width: 344px;
        min-height: 48px;
        padding: 0;
        border-radius: 4px;
        opacity: 0;
        visibility: hidden;
        transition-duration: 0.2s;
        transition-timing-function: cubic-bezier(0, 0, 0.2, 1);
        overflow: hidden;
        pointer-events: auto;
        z-index: 1;

        &--showing {
            opacity: 1;
            visibility: visible;
        }

        &--destroying {
            // 高さを 0.3 秒かけて 0px にして、なめらかにスタックの空白を詰める
            height: 0px;
            min-height: 0px;
            margin: 0px;
            transition-duration: 0.3s;
        }

        &__content {
            display: flex;
            align-items: center;
            flex-grow: 1;
            padding: 14px 16px;
            margin-right: auto;
            font-size: 0.875rem;
            font-weight: 400;
            text-align: initial;
            letter-spacing: 0.0178571429em;
            line-height: 1.25rem;
        }

        &__action {
            display: flex;
            align-items: center;
            align-self: center;
            margin-right: 8px;
        }
    }
}

</style>