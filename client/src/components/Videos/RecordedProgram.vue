<template>
    <router-link v-ripple class="recorded-program" :to="`/videos/watch/${program.id}`">
        <div class="recorded-program__container">
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
                <svg width="22px" height="22px" viewBox="0 0 15.2 15.2">
                    <path fill="currentColor" d="M8 2.5a.5.5 0 0 0-1 0V7H2.5a.5.5 0 0 0 0 1H7v4.5a.5.5 0 0 0 1 0V8h4.5a.5.5 0 0 0 0-1H8z"></path>
                </svg>
            </div>
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
    height: 125px;
    padding: 0px 16px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s;
    text-decoration: none;
    user-select: none;
    box-sizing: border-box;
    cursor: pointer;
    content-visibility: auto;
    contain-intrinsic-height: auto 125px;
    @include smartphone-vertical {
        height: auto;
        padding: 0px 9px;
        contain-intrinsic-height: auto 115px;
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

    &__container {
        display: flex;
        align-items: center;
        width: 100%;
        height: 100%;
        padding: 12px 0px;
        @include smartphone-vertical {
            padding: 9px 0px;
        }
    }

    &__thumbnail {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        aspect-ratio: 16 / 9;
        height: 100%;
        overflow: hidden;
        @include smartphone-vertical {
            width: 120px;
            aspect-ratio: 3 / 2;
        }

        &-image {
            width: 100%;
            border-radius: 4px;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            @include smartphone-vertical {
                aspect-ratio: 3 / 2;
            }
        }
    }

    &__content {
        display: flex;
        flex-direction: column;
        justify-content: center;
        flex-grow: 1;
        min-width: 0;  // magic!
        margin-left: 16px;
        margin-right: 40px;
        @include tablet-vertical {
            margin-right: 16px;
        }
        @include smartphone-horizontal {
            margin-right: 20px;
        }
        @include smartphone-vertical {
            margin-left: 12px;
            margin-right: 14px;
        }

        &-title {
            display: -webkit-box;
            font-size: 17px;
            font-weight: 700;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 1;  // 1行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                font-size: 15px;
            }
            @include smartphone-horizontal {
                font-size: 14px;
            }
            @include smartphone-vertical {
                font-size: 13px;
                -webkit-line-clamp: 2;  // 2行までに制限
            }
        }

        &-meta {
            display: flex;
            align-items: center;
            margin-top: 4px;
            font-size: 13.8px;
            @include tablet-vertical {
                flex-wrap: wrap;
            }
            @include smartphone-horizontal {
                margin-top: 6px;
                flex-wrap: wrap;
            }
            @include smartphone-vertical {
                flex-wrap: wrap;
                margin-top: 4px;
                font-size: 12px;
            }

            &-broadcaster {
                display: flex;
                align-items: center;
                min-width: 0;  // magic!

                &-icon {
                    flex-shrink: 0;
                    width: 28px;
                    height: 16px;
                    margin-right: 10px;
                    border-radius: 2px;
                    // 読み込まれるまでのアイコンの背景
                    background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                    object-fit: cover;
                    @include smartphone-vertical {
                        margin-right: 4px;
                        width: 24px;
                        height: 14px;
                    }
                }

                &-name {
                    color: rgb(var(--v-theme-text-darken-1));
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include tablet-vertical {
                        font-size: 13px;
                    }
                    @include smartphone-horizontal {
                        font-size: 13px;
                    }
                    @include smartphone-vertical {
                        margin-left: 4px;
                        font-size: 12px;
                    }
                }
            }

            &-time {
                display: inline-block;
                flex-shrink: 0;
                margin-left: 10px;
                color: rgb(var(--v-theme-text-darken-1));
                border-left: 1px solid rgb(var(--v-theme-text-darken-1));
                padding-left: 10px;
                height: 16px;
                line-height: 15.5px;
                @include tablet-vertical {
                    margin-top: 2px;
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    margin-top: 2px;
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 12px;
                }
                @include smartphone-vertical {
                    margin-top: 1px;
                    margin-left: 0px;
                    border-left: none;
                    padding-left: 0px;
                    font-size: 11.4px;
                }
            }
        }

        &-description {
            display: -webkit-box;
            margin-top: 6px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 11.5px;
            line-height: 155%;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                margin-top: 3.5px;
                font-size: 11px;
            }
            @include smartphone-horizontal {
                margin-top: 3.5px;
                font-size: 11px;
            }
            @include smartphone-vertical {
                margin-top: 1.5px;
                font-size: 11px;
                -webkit-line-clamp: 1;  // 1行までに制限
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
        @include tablet-vertical {
            right: 6px;
            width: 28px;
            height: 28px;
            svg {
                width: 18px;
                height: 18px;
            }
        }
        @include smartphone-horizontal {
            right: 6px;
            width: 28px;
            height: 28px;
            svg {
                width: 18px;
                height: 18px;
            }
        }
        @include smartphone-vertical {
            right: 4px;
            width: 28px;
            height: 28px;
            svg {
                width: 18px;
                height: 18px;
            }
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
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                &:before {
                    opacity: 0;
                }
            }
        }
    }
}

</style>
