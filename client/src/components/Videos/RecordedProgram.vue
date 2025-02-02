<template>
    <router-link v-ripple class="recorded-program" :to="`/videos/watch/${program.id}`">
        <div class="recorded-program__thumbnail">
            <img class="recorded-program__thumbnail-image" :src="`${Utils.api_base_url}/videos/${program.id}/thumbnail`">
        </div>
        <div class="recorded-program__content">
            <div class="recorded-program__content-title"
                v-html="ProgramUtils.decorateProgramInfo(program, 'title')"></div>
            <div class="recorded-program__content-meta">
                <div class="recorded-program__content-meta-broadcaster" v-if="program.channel">
                    <img class="recorded-program__content-meta-broadcaster-icon" :src="`${Utils.api_base_url}/channels/${program.channel.id}/logo`">
                    <span class="recorded-program__content-meta-broadcaster-name">Ch: {{program.channel.channel_number}} {{program.channel.name}}</span>
                </div>
                <div class="recorded-program__content-meta-broadcaster" v-else>
                    <span class="recorded-program__content-meta-broadcaster-name">チャンネル情報なし</span>
                </div>
                <div class="recorded-program__content-meta-time">{{ProgramUtils.getProgramTime(program)}}</div>
            </div>
            <div class="recorded-program__content-description"
                v-html="ProgramUtils.decorateProgramInfo(program, 'description')"></div>
        </div>
        <div v-ripple class="recorded-program__mylist"
            v-ftooltip="'マイリストに追加する'"
            @click.prevent.stop="Message.warning('マイリスト機能は現在開発中です。')"
            @mousedown.prevent.stop="">
            <Icon icon="fluent:add-20-regular" width="24px" />
        </div>
    </router-link>
</template>
<script lang="ts" setup>

import Message from '@/message';
import { IRecordedProgram } from '@/services/Videos';
import Utils, { ProgramUtils } from '@/utils';

// Props
defineProps<{
    program: IRecordedProgram;
}>();

</script>
<style lang="scss" scoped>

.recorded-program {
    display: flex;
    position: relative;
    width: 100%;
    height: 100px;
    padding: 12px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s;
    text-decoration: none;
    user-select: none;
    box-sizing: border-box;
    cursor: pointer;
    content-visibility: auto;
    contain-intrinsic-height: auto 100px;

    @include smartphone-vertical {
        height: 90px;
        padding: 10px;
        contain-intrinsic-height: auto 90px;
    }

    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }
    // タッチデバイスで hover を無効にする
    @media (hover: none) {
        &:hover {
            background: rgb(var(--v-theme-background-lighten-1));
        }
    }

    &__thumbnail {
        flex-shrink: 0;
        width: 136px;
        height: 76px;
        border-radius: 4px;
        overflow: hidden;
        @include smartphone-vertical {
            width: 124px;
            height: 70px;
        }

        &-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
    }

    &__content {
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        min-width: 0;  // magic!
        margin-left: 16px;
        margin-right: 48px;
        @include smartphone-vertical {
            margin-left: 12px;
            margin-right: 40px;
        }

        &-title {
            display: -webkit-box;
            font-size: 15px;
            font-weight: 700;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 1;  // 1行までに制限
            -webkit-box-orient: vertical;
            @include smartphone-vertical {
                font-size: 14px;
            }
        }

        &-meta {
            display: flex;
            align-items: center;
            margin-top: 6px;
            @include smartphone-vertical {
                margin-top: 4px;
            }

            &-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;  // magic!

                &-icon {
                    flex-shrink: 0;
                    width: 28px;
                    height: 16px;
                    border-radius: 2px;
                    // 読み込まれるまでのアイコンの背景
                    background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                    object-fit: cover;
                    @include smartphone-vertical {
                        width: 24px;
                        height: 14px;
                    }
                }

                &-name {
                    margin-left: 6px;
                    font-size: 12px;
                    color: rgb(var(--v-theme-text-darken-1));
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include smartphone-vertical {
                        font-size: 11px;
                        margin-left: 4px;
                    }
                }
            }

            &-time {
                flex-shrink: 0;
                margin-left: 12px;
                font-size: 12px;
                color: rgb(var(--v-theme-text-darken-1));
                @include smartphone-vertical {
                    margin-left: 10px;
                    font-size: 11px;
                }
            }
        }

        &-description {
            display: -webkit-box;
            margin-top: 6px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12px;
            line-height: 160%;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 1;  // 1行までに制限
            -webkit-box-orient: vertical;
            @include smartphone-vertical {
                margin-top: 4px;
                font-size: 11px;
                line-height: 150%;
            }
        }
    }

    &__mylist {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        position: absolute;
        top: 50%;
        right: 12px;
        transform: translateY(-50%);
        width: 32px;
        height: 32px;
        color: rgb(var(--v-theme-text-darken-1));
        border-radius: 50%;
        transition: color 0.15s ease, background-color 0.15s ease;
        user-select: none;
        @include smartphone-vertical {
            right: 10px;
            width: 28px;
            height: 28px;
        }

        &:before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: inherit;
            background-color: currentColor;
            color: inherit;
            opacity: 0;
            transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
            pointer-events: none;
        }
        &:hover {
            color: rgb(var(--v-theme-text));
            &:before {
                opacity: 0.15;
            }
        }
    }
}

</style>
