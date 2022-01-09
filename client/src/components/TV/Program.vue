<template>
    <div class="program-container">
        <section class="program-broadcaster">
            <img class="program-broadcaster__icon" :src="`${api_base_url}/channels/${($route.params.channel_id)}/logo`">
            <div class="program-broadcaster__number">Ch: {{channel_props.channel_number}}</div>
            <div class="program-broadcaster__name">{{channel_props.channel_name}}</div>
        </section>
        <section class="program-info">
            <h1 class="program-info__title" v-html="decorateProgramInfo(channel_props.program_present, 'title')"></h1>
            <div class="program-info__time">{{getProgramTime(channel_props.program_present)}}</div>
            <div class="program-info__description" v-html="decorateProgramInfo(channel_props.program_present, 'description')"></div>
            <div class="program-info__genre-container">
                <div class="program-info__genre" :key="genre_index"
                    v-for="(genre, genre_index) in getAttribute(channel_props.program_present, 'genre', [])">
                    {{genre.major}} / {{genre.middle}}
                </div>
            </div>
            <div class="program-info__next">
                <span class="program-info__next-decorate">NEXT</span>
                <Icon class="program-info__next-icon" icon="fluent:fast-forward-20-filled" width="16px" />
            </div>
            <span class="program-info__next-title" v-html="decorateProgramInfo(channel_props.program_following, 'title')"></span>
            <div class="program-info__next-time">{{getProgramTime(channel_props.program_following)}}</div>
            <div class="program-info__status">
                <div class="program-info__status-force"
                    :class="`program-info__status-force--${getChannelForceType(channel_props.channel_force)}`">
                    <Icon icon="fa-solid:fire-alt" height="14px" />
                    <span class="ml-2">勢い:</span>
                    <span class="ml-2">{{getAttribute(channel_props, 'channel_force', '--')}} コメ/分</span>
                </div>
                <div class="program-info__status-viewers ml-5">
                    <Icon icon="fa-solid:eye" height="14px" />
                    <span class="ml-2">視聴数:</span>
                    <span class="ml-1">{{channel_props.viewers}}</span>
                </div>
            </div>
        </section>
        <section class="program-detail-container">
            <div class="program-detail" :key="detail_heading"
                v-for="(detail_text, detail_heading) in getAttribute(channel_props.program_present, 'detail', {})">
                <h2 class="program-detail__heading">{{detail_heading}}</h2>
                <div class="program-detail__text">{{detail_text}}</div>
            </div>
        </section>
    </div>
</template>
<script lang="ts">

import { PropType } from 'vue';

import { IChannel } from '@/interface';
import Mixin from '@/views/TV/Mixin.vue';

export default Mixin.extend({
    name: 'Program',
    props: {
        // チャンネル情報
        channel_props: {
            type: Object as PropType<IChannel>,
            required: true,
        }
    }
});

</script>
<style lang="scss" scoped>

.program-container {
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;

    .program-broadcaster {
        display: none;
        align-items: center;
        min-width: 0;
        @media screen and (max-height: 450px) {
            display: flex;
            margin-top: 16px;
        }

        &__icon {
            display: inline-block;
            flex-shrink: 0;
            width: 43px;
            height: 24px;
            border-radius: 3px;
            background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
            object-fit: cover;
            user-select: none;
            @media screen and (max-height: 450px) {
                width: 42px;
                height: 23.5px;
            }
        }

        &__number {
            flex-shrink: 0;
            margin-left: 12px;
            font-size: 16.5px;
        }

        &__name {
            margin-left: 5px;
            font-size: 16.5px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
    }

    .program-info {
        .program-info__title {
            font-size: 22px;
            font-weight: bold;
            line-height: 145%;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.05em;  // 字間を少し空ける
            @media screen and (max-height: 450px) {
                margin-top: 10px;
                font-size: 18px;
            }
        }
        .program-info__time {
            margin-top: 8px;
            color: var(--v-text-darken1);
            font-size: 14px;
            @media screen and (max-height: 450px) {
                font-size: 13px;
            }
        }
        .program-info__description {
            margin-top: 12px;
            color: var(--v-text-darken1);
            font-size: 12px;
            line-height: 168%;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.08em;  // 字間を少し空ける
            @media screen and (max-height: 450px) {
                margin-top: 8px;
                font-size: 11px;
            }
        }
        .program-info__genre-container {
            display: flex;
            flex-wrap: wrap;
            margin-top: 10px;

            .program-info__genre {
                display: inline-block;
                font-size: 10.5px;
                padding: 3px;
                margin-top: 4px;
                margin-right: 4px;
                border-radius: 4px;
                background: var(--v-background-lighten2);
                @media screen and (max-height: 450px) {
                    font-size: 9px;
                }
            }
        }
        .program-info__next {
            display: flex;
            align-items: center;
            margin-top: 18px;
            color: var(--v-text-base);
            font-size: 14px;
            font-weight: bold;
            @media screen and (max-height: 450px) {
                margin-top: 14px;
                font-size: 13px;
            }
            &-decorate {
                flex-shrink: 0;
            }
            &-icon {
                flex-shrink: 0;
                margin-left: 3px;
                font-size: 15px;
            }
        }
        .program-info__next-title {
            display: -webkit-box;
            margin-top: 2px;
            color: var(--v-text-base);
            font-size: 14px;
            font-weight: bold;
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @media screen and (max-height: 450px) {
                font-size: 13px;
            }
        }
        .program-info__next-time {
            margin-top: 3px;
            color: var(--v-text-darken1);
            font-size: 13.5px;
        }

        .program-info__status {
            display: flex;
            align-items: center;
            margin-top: 16px;
            font-size: 14px;
            color: var(--v-text-darken1);
            @media screen and (max-height: 450px) {
                margin-top: 10px;
                font-size: 12px;
            }

            &-force, &-viewers {
                display: flex;
                align-items: center;
            }

            &-force--festival {
                color: #E7556E;
            }
            &-force--so-many {
                color: #E76B55;
            }
            &-force--many {
                color: #E7A355;
            }
        }
    }

    .program-detail-container {
        margin-top: 24px;
        margin-bottom: 24px;
        @media screen and (max-height: 450px) {
            margin-top: 20px;
        }

        .program-detail {
            margin-top: 16px;

            .program-detail__heading {
                font-size: 18px;
                @media screen and (max-height: 450px) {
                    font-size: 16px;
                }
            }
            .program-detail__text {
                margin-top: 8px;
                color: var(--v-text-darken1);
                font-size: 12px;
                line-height: 168%;
                overflow-wrap: break-word;
                white-space: pre-wrap;  // \n で改行する
                font-feature-settings: "palt" 1;  // 文字詰め
                letter-spacing: 0.08em;  // 字間を少し空ける
                @media screen and (max-height: 450px) {
                    font-size: 11px;
                }
            }
        }
    }
}

</style>