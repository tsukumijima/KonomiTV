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
            <div class="mt-5">
                <div class="program-info__status">
                    <Icon icon="ic:round-date-range" height="17px" style="margin-left: -2px; margin-right: -1.7px; margin-bottom: -3px;" />
                    <span class="ml-2">録画期間: {{playerStore.recorded_program.is_partially_recorded ? '(一部のみ録画)' : ''}}</span><br>
                    <span>{{ProgramUtils.getRecordingTime(playerStore.recorded_program)}}</span>
                </div>
                <div class="program-info__status">
                    <Icon icon="bi:chat-left-text-fill" height="12.5px" style="margin-bottom: -3px" />
                    <span class="ml-2">コメント数:</span>
                    <span class="ml-2">{{comment_count ?? '--'}}</span>
                </div>
                <div v-ripple class="program-info__button" @click="toggleMylist">
                    <template v-if="isInMylist">
                        <Icon icon="fluent:checkmark-16-filled" width="18px" height="18px"
                            style="color: rgb(var(--v-theme-primary)); margin-bottom: -1px" />
                        <span style="margin-left: 6px;">マイリストに追加済み</span>
                    </template>
                    <template v-else>
                        <Icon icon="fluent:add-16-filled" width="18px" height="18px" style="margin-bottom: -1px" />
                        <span style="margin-left: 6px;">マイリストに追加</span>
                    </template>
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

import Message from '@/message';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore from '@/stores/SettingsStore';
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
        ...mapStores(usePlayerStore, useSettingsStore),

        // マイリストに追加されているかどうか
        isInMylist(): boolean {
            return this.settingsStore.settings.mylist.some(item =>
                item.type === 'RecordedProgram' && item.id === this.playerStore.recorded_program.id
            );
        },
    },
    methods: {
        // マイリストの追加/削除を切り替える
        toggleMylist(): void {
            const program = this.playerStore.recorded_program;
            if (this.isInMylist) {
                // マイリストから削除
                this.settingsStore.settings.mylist = this.settingsStore.settings.mylist.filter(item =>
                    !(item.type === 'RecordedProgram' && item.id === program.id)
                );
                Message.show('マイリストから削除しました。');
            } else {
                // マイリストに追加
                this.settingsStore.settings.mylist.push({
                    type: 'RecordedProgram',
                    id: program.id,
                    created_at: Utils.time(),  // 秒単位
                });
            }
        },
    },
    created() {
        // PlayerController 側からCommentReceived イベントで過去ログコメントを受け取り、コメント数を算出する
        this.playerStore.event_emitter.on('CommentReceived', (event) => {
            if (event.is_initial_comments === true) {  // 録画では初期コメントしか発生しない
                this.comment_count = event.comments.length;
            }
        });
    },
    beforeUnmount() {
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
            margin-top: 8px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12.5px;
            line-height: 170%;
            @include smartphone-horizontal {
                font-size: 11.5px;
            }
        }

        .program-info__button {
            display: inline-flex;
            align-items: center;
            padding: 5px 8px;
            margin-top: 16px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 12.7px;
            line-height: 170%;
            background: rgb(var(--v-theme-background-lighten-1));
            border-radius: 4px;
            user-select: none;
            transition: color 0.15s ease;
            cursor: pointer;
            @include smartphone-horizontal {
                font-size: 11.5px;
            }

            &:hover {
                color: rgb(var(--v-theme-text));
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