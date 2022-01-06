<template>
    <div class="comment-container">
        <section class="comment-header">
            <h2 class="comment-header__title">
                <Icon class="comment-header__title-icon" icon="bi:chat-left-text-fill" height="18.5px" />
                <span class="comment-header__title-text">コメント</span>
            </h2>
            <button v-ripple class="comment-header__button ml-auto">
                <Icon icon="heroicons-solid:filter" height="11px" />
                <span class="ml-1">コメントフィルター</span>
            </button>
        </section>
        <DynamicScroller class="comment-list" :direction="vertical" :items="comment_list" :min-item-size="34">
            <template v-slot="{item, _, active}">
            <DynamicScrollerItem :item="item" :active="active"  :size-dependencies="[item.text]">
                <div class="comment">
                    <span class="comment__text">{{item.text}}</span>
                    <span class="comment__time">{{item.time}}</span>
                </div>
            </DynamicScrollerItem>
            </template>
        </DynamicScroller>
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
    },
    data() {
        return {
            comment_list: [
                {'id': 1, time:'12:34:56', text:'ああああああああああ'},
                {'id': 2, time:'12:35:56', text:'いいいいいいいいいいいいいいいいいいいいい'},
                {'id': 3, time:'12:36:56', text:'ああああああああああああああああああああああああああああああああああああああああああ'},
                {'id': 4, time:'12:37:56', text:'ええええええええええええええええええええええええええええええええええええええええええ'},
                {'id': 5, time:'12:38:56', text:'おおおおおおおおおおおおおおおおおおおおお'},
                {'id': 6, time:'12:39:56', text:'かかかかかかっかかかかかかっかかかかかかか'},
                {'id': 11, time:'12:34:56', text:'ああああああああああ'},
                {'id': 12, time:'12:35:56', text:'いいいいいいいいいいいいいいいいいいいいい'},
                {'id': 13, time:'12:36:56', text:'ああああああああああああああああああああああああああああああああああああああああああ'},
                {'id': 14, time:'12:37:56', text:'ええええええええええええええええええええええええええええええええええええええええええ'},
                {'id': 15, time:'12:38:56', text:'おおおおおおおおおおおおおおおおおおおおお'},
                {'id': 16, time:'12:39:56', text:'かかかかかかっかかかかかかっかかかかかかか'},
                {'id': 21, time:'12:34:56', text:'ああああああああああ'},
                {'id': 22, time:'12:35:56', text:'いいいいいいいいいいいいいいいいいいいいい'},
                {'id': 23, time:'12:36:56', text:'ああああああああああああああああああああああああああああああああああああああああああ'},
                {'id': 24, time:'12:37:56', text:'ええええええええええええええええええええええええええええええええええええええええええ'},
                {'id': 25, time:'12:38:56', text:'おおおおおおおおおおおおおおおおおおおおお'},
                {'id': 26, time:'12:39:56', text:'かかかかかかっかかかかかかっかかかかかかか'},
                {'id': 31, time:'12:34:56', text:'ああああああああああ'},
                {'id': 32, time:'12:35:56', text:'いいいいいいいいいいいいいいいいいいいいい'},
                {'id': 33, time:'12:36:56', text:'ああああああああああああああああああああああああああああああああああああああああああ'},
                {'id': 34, time:'12:37:56', text:'ええええええええええええええええええええええええええええええええええええええええええ'},
                {'id': 35, time:'12:38:56', text:'おおおおおおおおおおおおおおおおおおおおお'},
                {'id': 36, time:'12:39:56', text:'かかかかかかっかかかかかかっかかかかかかか'},
                {'id': 41, time:'12:34:56', text:'ああああああああああ'},
                {'id': 42, time:'12:35:56', text:'いいいいいいいいいいいいいいいいいいいいい'},
                {'id': 43, time:'12:36:56', text:'ああああああああああああああああああああああああああああああああああああああああああ'},
                {'id': 44, time:'12:37:56', text:'ええええええええええええええええええええええええええええええええええええええええええ'},
                {'id': 45, time:'12:38:56', text:'おおおおおおおおおおおおおおおおおおおおお'},
                {'id': 46, time:'12:39:56', text:'かかかかかかっかかかかかかっかかかかかかか'},
                {'id': 51, time:'12:34:56', text:'ああああああああああ'},
                {'id': 52, time:'12:35:56', text:'いいいいいいいいいいいいいいいいいいいいい'},
                {'id': 53, time:'12:36:56', text:'ああああああああああああああああああああああああああああああああああああああああああ'},
                {'id': 54, time:'12:37:56', text:'ええええええええええええええええええええええええええええええええええええええええええ'},
                {'id': 55, time:'12:38:56', text:'おおおおおおおおおおおおおおおおおおおおお'},
                {'id': 56, time:'12:39:56', text:'かかかかかかっか'},
            ],
        }
    }
});

</script>
<style lang="scss" scoped>

.comment-container {
    display: flex;
    flex-direction: column;

    .comment-header {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        width: 100%;
        height: 26px;
        padding-left: 16px;
        padding-right: 16px;

        &__title {
            display: flex;
            align-items: center;
            font-size: 18.5px;
            font-weight: bold;
            line-height: 145%;

            &-icon {
                margin-bottom: -3px;  // 高さ調整
            }
            &-text {
                margin-left: 12px;
            }
        }

        &__button {
            display: flex;
            align-items: center;
            height: 26px;
            padding: 0 9px;
            border-radius: 4px;
            background: var(--v-background-lighten3);
            font-size: 11px;
            line-height: 1.8;
            letter-spacing: 0;
        }
    }

    .comment-list {
        width: 100%;
        height: 100%;
        margin-top: 16px;
        padding-left: 16px;
        padding-right: 10px;
        padding-bottom: 12px;
        overflow-y: scroll !important;

        .comment {
            display: flex;
            align-items: center;
            min-height: 28px;
            margin-top: 6px;

            &__text {
                font-size: 13px;
            }

            &__time {
                flex-shrink: 0;
                margin-left: auto;
                padding-left: 8px;
                color: var(--v-text-darken1);
                font-size: 13px;
            }
        }
    }
}

</style>