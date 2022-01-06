<template>
    <div class="comment-container">
        <section class="comment-header">
            <h2 class="comment-header__title">
                <Icon class="comment-header__title-icon" icon="bi:chat-left-text-fill" height="20px" />
                <span class="comment-header__title-text">コメント</span>
            </h2>
            <button v-ripple class="comment-header__button ml-auto">
                <Icon icon="heroicons-solid:filter" height="12.5px" />
                <span class="ml-1">コメントフィルター</span>
            </button>
        </section>

    </div>
</template>
<script lang="ts">

import { PropType } from 'vue';

import { IChannel } from '@/interface';
import Mixin from '@/views/TV/Mixin.vue';

export default Mixin.extend({
    name: 'Comment',
    props: {
        // channel_props: {
        //     type: Object as PropType<IChannel>,
        //     required: true,
        // }
    }
});

</script>
<style lang="scss" scoped>

.comment-container {
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;

    .comment-header {
        display: flex;
        align-items: center;
        width: 100%;
        height: 28px;

        &__title {
            display: flex;
            align-items: center;
            font-size: 19.5px;
            font-weight: bold;
            line-height: 145%;

            &-icon {
                margin-bottom: -2px;  // 高さ調整
            }
            &-text {
                margin-left: 12px;
            }
        }

        &__button {
            display: flex;
            align-items: center;
            height: 28px;
            padding: 0 9px;
            border-radius: 4px;
            background: var(--v-background-lighten2);
            font-size: 12.5px;
            line-height: 1.8;
            letter-spacing: 0;
        }
    }
}

</style>