<template>
    <div class="program-container" v-if="displayProgram && displayChannel">
        <section class="program-info">
            <h1 class="program-info__title"
                v-html="ProgramUtils.decorateProgramInfo(displayProgram, 'title')">
            </h1>
            <div class="program-info__broadcaster">
                <img class="program-info__broadcaster-icon"
                    :src="`${Utils.api_base_url}/channels/${displayChannel.id}/logo`"
                    @error="onLogoError">
                <div class="program-info__broadcaster-container">
                    <div class="d-flex align-center">
                        <div class="program-info__broadcaster-number">Ch: {{displayChannel.channel_number}}</div>
                        <div class="program-info__broadcaster-name">{{displayChannel.name}}</div>
                    </div>
                    <div class="program-info__broadcaster-time">
                        {{ProgramUtils.getProgramTime(displayProgram)}}
                    </div>
                </div>
            </div>
            <div class="program-info__description"
                v-html="ProgramUtils.decorateProgramInfo(displayProgram, 'description')">
            </div>
            <div class="program-info__genre-container" v-if="displayProgram.genres && displayProgram.genres.length > 0">
                <div class="program-info__genre" :key="genre_index"
                    v-for="(genre, genre_index) in displayProgram.genres">
                    {{genre.major}} / {{genre.middle}}
                </div>
            </div>
            <div class="mt-5">
                <!-- 映像・音声情報 -->
                <div class="program-info__status" v-if="displayProgram.video_codec && displayProgram.video_resolution">
                    <Icon icon="fluent:video-16-filled" height="17px" style="margin-left: -2px; margin-right: -1.7px; margin-bottom: -3px;" />
                    <span class="ml-2">映像: {{displayProgram.video_codec}} / {{displayProgram.video_resolution}}</span>
                </div>
                <div class="program-info__status">
                    <Icon icon="fluent:headphones-sound-wave-20-filled" height="17px" style="margin-left: -2px; margin-right: -1.7px; margin-bottom: -3px;" />
                    <span class="ml-2">主音声: {{displayProgram.primary_audio_type}} {{displayProgram.primary_audio_sampling_rate || 'Unknown'}} / {{displayProgram.primary_audio_language}}</span>
                </div>
                <div v-if="displayProgram.secondary_audio_type" class="program-info__status">
                    <Icon icon="fluent:headphones-sound-wave-20-filled" height="17px" style="margin-left: -2px; margin-right: -1.7px; margin-bottom: -3px;" />
                    <span class="ml-2">副音声: {{displayProgram.secondary_audio_type}} {{displayProgram.secondary_audio_sampling_rate || 'Unknown'}} / {{displayProgram.secondary_audio_language}}</span>
                </div>
            </div>
        </section>
        <section class="program-detail-container">
            <div class="program-detail" :key="detail_heading"
                v-for="(detail_text, detail_heading) in displayProgram.detail ?? {}">
                <h2 class="program-detail__heading">{{detail_heading}}</h2>
                <div class="program-detail__text" v-html="Utils.URLtoLink(detail_text)"></div>
            </div>
        </section>
    </div>
</template>
<script lang="ts">

import { defineComponent, PropType } from 'vue';

import { type IChannel } from '@/services/Channels';
import { type IProgram } from '@/services/Programs';
import { type IReservation } from '@/services/Reservations';
import Utils, { ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'ReservationProgramInfo',
    props: {
        // 予約情報（予約がある場合に使用）
        reservation: {
            type: Object as PropType<IReservation | null>,
            default: null,
        },
        // 番組情報（予約がない場合に使用）
        program: {
            type: Object as PropType<IProgram | null>,
            default: null,
        },
        // チャンネル情報（予約がない場合に使用）
        channel: {
            type: Object as PropType<IChannel | null>,
            default: null,
        },
    },
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
            ProgramUtils: Object.freeze(ProgramUtils),
        };
    },
    computed: {
        // 表示用の番組情報（reservation があればそちらを優先）
        displayProgram(): IProgram | null {
            return this.reservation?.program ?? this.program;
        },
        // 表示用のチャンネル情報（reservation があればそちらを優先）
        displayChannel(): IChannel | null {
            return this.reservation?.channel ?? this.channel;
        },
    },
    methods: {
        // ロゴ画像エラー時のフォールバック
        onLogoError(event: Event): void {
            const target = event.target as HTMLImageElement;
            target.src = `${Utils.api_base_url}/channels/gr001/logo`;
        },
    },
});

</script>
<style lang="scss" scoped>

.program-container {
    .program-info {
        .program-info__title {
            font-size: 19px;
            font-weight: bold;
            line-height: 145%;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.05em;  // 字間を少し空ける
        }

        .program-info__broadcaster {
            display: flex;
            align-items: center;
            min-width: 0;
            margin-top: 16px;
            color: rgb(var(--v-theme-text-darken-1));
            &-icon {
                display: inline-block;
                flex-shrink: 0;
                width: 44px;
                height: 36px;
                border-radius: 3px;
                background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                object-fit: cover;
                user-select: none;
            }

            .program-info__broadcaster-container {
                display: flex;
                flex-direction: column;
                margin-left: 12px;
                .program-info__broadcaster-number {
                    flex-shrink: 0;
                    font-size: 14px;
                    @include smartphone-horizontal {
                        font-size: 13.5px;
                    }
                }
                .program-info__broadcaster-name {
                    margin-left: 5px;
                    font-size: 14px;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include smartphone-horizontal {
                        font-size: 13.5px;
                    }
                }
                .program-info__broadcaster-time {
                    margin-top: 2px;
                    color: rgb(var(--v-theme-text-darken-1));
                    font-size: 13.5px;
                    @include smartphone-horizontal {
                        font-size: 12px;
                    }
                    @include smartphone-vertical {
                        font-size: 12.5px;
                    }
                }
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

        .program-info__status {
            margin-top: 4px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12.5px;
            line-height: 170%;
            @include smartphone-horizontal {
                font-size: 11.5px;
            }
        }
    }

    .program-detail-container {
        margin-top: 24px;
        margin-bottom: 12px;
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