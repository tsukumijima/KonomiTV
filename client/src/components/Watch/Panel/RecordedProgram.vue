<template>
    <div class="recorded-program-container">
        <section class="recorded-program-info">
            <h1 class="recorded-program-info__title"
                v-html="ProgramUtils.decorateProgramInfo(playerStore.recorded_program, 'title')">
            </h1>
            <div class="recorded-program-info__time">
                {{ProgramUtils.getProgramTime(playerStore.recorded_program)}}
            </div>
            <div class="recorded-program-info__description"
                v-html="ProgramUtils.decorateProgramInfo(playerStore.recorded_program, 'description')">
            </div>
            <div class="recorded-program-info__genre-container">
                <div class="recorded-program-info__genre" :key="genre_index"
                    v-for="(genre, genre_index) in playerStore.recorded_program.genres ?? []">
                    {{genre.major}} / {{genre.middle}}
                </div>
            </div>
            <div class="recorded-program-info__status">
                <div class="recorded-program-info__status-force">
                    <Icon icon="fa-solid:fire-alt" height="14px" />
                    <span class="ml-2">コメント数:</span>
                    <span class="ml-2">{{'--'}} コメ</span>
                </div>
            </div>
        </section>
        <section class="recorded-program-detail-container">
            <div class="recorded-program-detail" :key="detail_heading"
                v-for="(detail_text, detail_heading) in playerStore.recorded_program.detail ?? {}">
                <h2 class="recorded-program-detail__heading">{{detail_heading}}</h2>
                <div class="recorded-program-detail__text" v-html="Utils.URLtoLink(detail_text)"></div>
            </div>
        </section>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent } from 'vue';

import usePlayerStore from '@/stores/PlayerStore';
import Utils, { ProgramUtils } from '@/utils';

export default defineComponent({
    name: 'Panel-RecordedProgramTab',
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Utils,
            ProgramUtils: ProgramUtils,
        };
    },
    computed: {
        ...mapStores(usePlayerStore),
    }
});

</script>
<style lang="scss" scoped>

.recorded-program-container {
    padding-left: 16px;
    padding-right: 16px;
    overflow-y: auto;
    @include tablet-vertical {
        padding-left: 24px;
        padding-right: 24px;
    }

    .recorded-program-info {
        .recorded-program-info__title {
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
        .recorded-program-info__time {
            margin-top: 8px;
            color: var(--v-text-darken1);
            font-size: 14px;
            @include smartphone-horizontal {
                font-size: 13px;
            }
        }
        .recorded-program-info__description {
            margin-top: 12px;
            color: var(--v-text-darken1);
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
        .recorded-program-info__genre-container {
            display: flex;
            flex-wrap: wrap;
            margin-top: 10px;

            .recorded-program-info__genre {
                display: inline-block;
                font-size: 10.5px;
                padding: 3px;
                margin-top: 4px;
                margin-right: 4px;
                border-radius: 4px;
                background: var(--v-background-lighten2);
                @include smartphone-horizontal {
                    font-size: 9px;
                }
            }
        }

        .recorded-program-info__status {
            display: flex;
            align-items: center;
            margin-top: 16px;
            font-size: 14px;
            color: var(--v-text-darken1);
            @include smartphone-horizontal {
                margin-top: 10px;
                font-size: 12px;
            }

            &-force, &-viewers {
                display: flex;
                align-items: center;
            }
        }
    }

    .recorded-program-detail-container {
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

        .recorded-program-detail {
            margin-top: 16px;

            .recorded-program-detail__heading {
                font-size: 18px;
                @include smartphone-horizontal {
                    font-size: 16px;
                }
            }
            .recorded-program-detail__text {
                margin-top: 8px;
                color: var(--v-text-darken1);
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
                    color: var(--v-primary-lighten1);
                    text-underline-offset: 3px;  // 下線と字の間隔を空ける
                }
            }
        }
    }
}

</style>