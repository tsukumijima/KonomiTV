<template>
    <div class="program-container">
        <section class="program-info">
            <h1 class="program-info__title"
                v-html="ProgramUtils.decorateProgramInfo(playerStore.recorded_program, 'title')">
            </h1>
            <div class="program-info__broadcaster" v-if="playerStore.recorded_program.channel !== null">
                <img class="program-info__broadcaster-icon" :src="`${Utils.api_base_url}/channels/${playerStore.recorded_program.channel.id}/logo`">
                <div class="program-info__broadcaster-container">
                    <div class="d-flex align-center">
                        <div class="program-info__broadcaster-number">Ch: {{playerStore.recorded_program.channel.channel_number}}</div>
                        <div class="program-info__broadcaster-name">{{playerStore.recorded_program.channel.name}}</div>
                    </div>
                    <div class="program-info__broadcaster-time">
                        {{ProgramUtils.getProgramTime(playerStore.recorded_program)}}
                    </div>
                </div>
            </div>
            <div class="program-info__description"
                v-html="ProgramUtils.decorateProgramInfo(playerStore.recorded_program, 'description')">
            </div>
            <div class="program-info__genre-container">
                <div class="program-info__genre" :key="genre_index"
                    v-for="(genre, genre_index) in playerStore.recorded_program.genres ?? []">
                    {{genre.major}} / {{genre.middle}}
                </div>
            </div>
            <div class="program-info__status">
                <div class="program-info__status-force">
                    <Icon icon="bi:chat-left-text-fill" height="14px" style="margin-top: 3px" />
                    <span class="ml-2">コメント数:</span>
                    <span class="ml-2">{{comment_count ?? '--'}}</span>
                </div>
            </div>
        </section>
        <section class="program-detail-container">
            <div class="program-detail" :key="detail_heading"
                v-for="(detail_text, detail_heading) in playerStore.recorded_program.detail ?? {}">
                <h2 class="program-detail__heading">{{detail_heading}}</h2>
                <div class="program-detail__text" v-html="Utils.URLtoLink(detail_text)"></div>
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
            Utils: Object.freeze(Utils),
            ProgramUtils: Object.freeze(ProgramUtils),

            // コメント数カウント
            comment_count: null as number | null,
        };
    },
    computed: {
        ...mapStores(usePlayerStore),
    },
    created() {
        // PlayerController 側からCommentReceived イベントで過去ログコメントを受け取り、コメント数を算出する
        this.playerStore.event_emitter.on('CommentReceived', (event) => {
            if (event.is_initial_comments === true) {  // 録画では初期コメントしか発生しない
                this.comment_count = event.comments.length;
            }
        });
    },
    beforeDestroy() {
        // CommentReceived イベントの全てのイベントハンドラーを削除
        this.playerStore.event_emitter.off('CommentReceived');
    },
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
        .program-info__broadcaster {
            display: flex;
            align-items: center;
            min-width: 0;
            margin-top: 16px;
            color: var(--v-text-darken1);
            &-icon {
                display: inline-block;
                flex-shrink: 0;
                width: 44px;
                height: 36px;
                border-radius: 3px;
                background: linear-gradient(150deg, var(--v-gray-base), var(--v-background-lighten2));
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
            .program-info__broadcaster-container {
                display: flex;
                flex-direction: column;
                margin-left: 12px;
                .program-info__broadcaster-number {
                    flex-shrink: 0;
                    font-size: 14px;
                    @include tablet-vertical {
                        margin-left: 16px;
                        font-size: 13px;
                    }
                }
                .program-info__broadcaster-name {
                    margin-left: 5px;
                    font-size: 14px;
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                    @include tablet-vertical {
                        margin-left: 8px;
                        font-size: 13px;
                    }
                    @include smartphone-vertical {
                        font-size: 13px;
                    }
                }
                .program-info__broadcaster-time {
                    margin-top: 2px;
                    color: var(--v-text-darken1);
                    font-size: 13.5px;
                    @include smartphone-horizontal {
                        font-size: 12.5px;
                    }
                }
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
                background: var(--v-background-lighten2);
                @include smartphone-horizontal {
                    font-size: 9px;
                }
            }
        }

        .program-info__status {
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