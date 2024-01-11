<template>
    <div class="program-container">
        <section class="program-broadcaster">
            <img class="program-broadcaster__icon" :src="`${Utils.api_base_url}/channels/${channelsStore.channel.current.id}/logo`">
            <div class="program-broadcaster__number">Ch: {{channelsStore.channel.current.channel_number}}</div>
            <div class="program-broadcaster__name">{{channelsStore.channel.current.name}}</div>
        </section>
        <section class="program-info">
            <h1 class="program-info__title"
                v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_present, 'title')">
            </h1>
            <div class="program-info__time">
                {{ProgramUtils.getProgramTime(channelsStore.channel.current.program_present)}}
            </div>
            <div class="program-info__description"
                v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_present, 'description')">
            </div>
            <div class="program-info__genre-container">
                <div class="program-info__genre" :key="genre_index"
                    v-for="(genre, genre_index) in channelsStore.channel.current.program_present?.genres ?? []">
                    {{genre.major}} / {{genre.middle}}
                </div>
            </div>
            <div class="program-info__next">
                <span class="program-info__next-decorate">NEXT</span>
                <Icon class="program-info__next-icon" icon="fluent:fast-forward-20-filled" width="16px" />
            </div>
            <span class="program-info__next-title"
                v-html="ProgramUtils.decorateProgramInfo(channelsStore.channel.current.program_following, 'title')">
            </span>
            <div class="program-info__next-time">
                {{ProgramUtils.getProgramTime(channelsStore.channel.current.program_following)}}
            </div>
            <div class="program-info__status">
                <div class="program-info__status-force"
                    :class="`program-info__status-force--${ChannelUtils.getChannelForceType(channelsStore.channel.current.jikkyo_force)}`">
                    <Icon icon="fa-solid:fire-alt" height="14px" />
                    <span class="ml-2">勢い:</span>
                    <span class="ml-2">{{channelsStore.channel.current.jikkyo_force ?? '--'}} コメ/分</span>
                </div>
                <div class="program-info__status-viewers ml-5">
                    <Icon icon="fa-solid:eye" height="14px" />
                    <span class="ml-2">視聴数:</span>
                    <span class="ml-1">{{channelsStore.channel.current.viewer_count}}</span>
                </div>
            </div>
        </section>
        <section class="program-detail-container">
            <div class="program-detail" :key="detail_heading"
                v-for="(detail_text, detail_heading) in channelsStore.channel.current.program_present?.detail ?? {}">
                <h2 class="program-detail__heading">{{detail_heading}}</h2>
                <div class="program-detail__text" v-html="Utils.URLtoLink(detail_text)"></div>
            </div>
        </section>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import useChannelsStore from '@/stores/ChannelsStore';
import Utils, { ChannelUtils, ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'Panel-ProgramTab',
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            ChannelUtils: Object.freeze(ChannelUtils),
            ProgramUtils: Object.freeze(ProgramUtils),
        };
    },
    computed: {
        ...mapStores(useChannelsStore),
    }
});

</script>
<style lang="scss" scoped>

.program-container {
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;
    @include tablet-vertical {
        padding-left: 24px;
        padding-right: 24px;
    }

    .program-broadcaster {
        display: none;
        align-items: center;
        min-width: 0;
        @include tablet-vertical {
            display: flex;
            margin-top: 20px;
        }
        @include smartphone-horizontal {
            display: flex;
            margin-top: 16px;
        }
        @include smartphone-vertical {
            display: flex;
            margin-top: 16px;
        }

        &__icon {
            display: inline-block;
            flex-shrink: 0;
            width: 43px;
            height: 24px;
            border-radius: 3px;
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
            object-fit: cover;
            user-select: none;
            @include tablet-vertical {
                width: 58px;
                height: 32px;
            }
            @include smartphone-horizontal {
                width: 42px;
                height: 23.5px;
            }
            @include smartphone-vertical {
                width: 58px;
                height: 32px;
            }
        }

        &__number {
            flex-shrink: 0;
            margin-left: 12px;
            font-size: 16.5px;
            @include tablet-vertical {
                margin-left: 16px;
                font-size: 19px;
            }
        }

        &__name {
            margin-left: 5px;
            font-size: 16.5px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
            @include tablet-vertical {
                margin-left: 8px;
                font-size: 19px;
            }
            @include smartphone-vertical {
                font-size: 18px;
            }
        }
    }

    .program-info {
        .program-info__title {
            font-size: 22px;
            font-weight: bold;
            line-height: 145%;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.05em;  // 字間を少し空ける
            @include tablet-vertical {
                margin-top: 16px;
            }
            @include smartphone-horizontal {
                margin-top: 10px;
                font-size: 18px;
            }
            @include smartphone-vertical {
                margin-top: 16px;
                font-size: 19px;
            }
        }
        .program-info__time {
            margin-top: 8px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 14px;
            @include smartphone-horizontal {
                font-size: 13px;
            }
        }
        .program-info__description {
            margin-top: 12px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12px;
            line-height: 168%;
            overflow-wrap: break-word;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.08em;  // 字間を少し空ける
            @include smartphone-horizontal {
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
                background: rgb(var(--v-theme-background-lighten-2));
                @include smartphone-horizontal {
                    font-size: 9px;
                }
            }
        }
        .program-info__next {
            display: flex;
            align-items: center;
            margin-top: 18px;
            color: rgb(var(--v-theme-text));
            font-size: 14px;
            font-weight: bold;
            user-select: none;
            @include smartphone-horizontal {
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
            color: rgb(var(--v-theme-text));
            font-size: 14px;
            font-weight: bold;
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @include smartphone-horizontal {
                font-size: 13px;
            }
        }
        .program-info__next-time {
            margin-top: 3px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 13.5px;
        }

        .program-info__status {
            display: flex;
            align-items: center;
            margin-top: 16px;
            font-size: 14px;
            color: rgb(var(--v-theme-text-darken-1));
            @include smartphone-horizontal {
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
        @include tablet-vertical {
            margin-top: 20px;
            margin-bottom: 20px;
        }
        @include smartphone-horizontal {
            margin-top: 20px;
            margin-bottom: 16px;
        }

        .program-detail {
            margin-top: 16px;

            .program-detail__heading {
                font-size: 18px;
                @include smartphone-horizontal {
                    font-size: 16px;
                }
            }
            .program-detail__text {
                margin-top: 8px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 12px;
                line-height: 168%;
                overflow-wrap: break-word;
                white-space: pre-wrap;  // \n で改行する
                font-feature-settings: "palt" 1;  // 文字詰め
                letter-spacing: 0.08em;  // 字間を少し空ける
                @include smartphone-horizontal {
                    font-size: 11px;
                }

                // リンクの色
                :deep(a:link), :deep(a:visited) {
                    color: rgb(var(--v-theme-primary-lighten-1));
                    text-decoration: underline;
                    text-underline-offset: 3px;  // 下線と字の間隔を空ける
                }
            }
        }
    }
}

</style>