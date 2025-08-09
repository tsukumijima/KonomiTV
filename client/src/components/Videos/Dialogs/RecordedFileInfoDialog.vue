<template>
    <v-dialog max-width="770" transition="slide-y-transition" :model-value="show" @update:model-value="$emit('update:show', $event)">
        <v-card class="video-info">
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="fluent:document-20-filled" height="26px" />
                <span class="ml-3">録画ファイル情報</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="$emit('update:show', false)">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-2">
                    <Icon icon="fluent:video-clip-20-filled" width="24px" height="20px" />
                    <span class="ml-2">ファイル情報</span>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">ファイルパス</div>
                    <div class="video-info__item-value">{{program.recorded_video.file_path}}</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">ファイルサイズ</div>
                    <div class="video-info__item-value">{{Utils.formatBytes(program.recorded_video.file_size)}}</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">録画期間</div>
                    <div class="video-info__item-value">
                        {{ProgramUtils.getRecordingTime(program)}}
                    </div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">最終更新日時</div>
                    <div class="video-info__item-value">
                        {{Utils.apply28HourClock(dayjs(program.recorded_video.file_modified_at).format('YYYY/MM/DD (dd) HH:mm:ss'))}}
                    </div>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-3">
                    <Icon icon="fluent:video-20-filled" width="24px" height="20px" />
                    <span class="ml-2">映像情報</span>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">コーデック</div>
                    <div class="video-info__item-value">{{program.recorded_video.video_codec}} ({{program.recorded_video.video_codec_profile}})</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">解像度</div>
                    <div class="video-info__item-value">{{program.recorded_video.video_resolution_width}}×{{program.recorded_video.video_resolution_height}}</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">フレームレート</div>
                    <div class="video-info__item-value">{{program.recorded_video.video_frame_rate}} fps</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">スキャン方式</div>
                    <div class="video-info__item-value">{{program.recorded_video.video_scan_type}}</div>
                </div>
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-3">
                    <Icon icon="fluent:speaker-2-20-filled" width="24px" height="20px" />
                    <span class="ml-2">音声情報（主音声）</span>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">コーデック</div>
                    <div class="video-info__item-value">{{program.recorded_video.primary_audio_codec}}</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">チャンネル</div>
                    <div class="video-info__item-value">{{program.recorded_video.primary_audio_channel}}</div>
                </div>
                <div class="video-info__item">
                    <div class="video-info__item-label">サンプリングレート</div>
                    <div class="video-info__item-value">{{program.recorded_video.primary_audio_sampling_rate ? `${program.recorded_video.primary_audio_sampling_rate / 1000}kHz` : '不明'}}</div>
                </div>

                <div v-if="program.recorded_video.secondary_audio_codec" class="text-subtitle-1 d-flex align-center font-weight-bold mt-3">
                    <Icon icon="fluent:speaker-2-20-filled" width="24px" height="20px" />
                    <span class="ml-2">音声情報（副音声）</span>
                </div>
                <template v-if="program.recorded_video.secondary_audio_codec">
                    <div class="video-info__item">
                        <div class="video-info__item-label">コーデック</div>
                        <div class="video-info__item-value">{{program.recorded_video.secondary_audio_codec}}</div>
                    </div>
                    <div class="video-info__item">
                        <div class="video-info__item-label">チャンネル</div>
                        <div class="video-info__item-value">{{program.recorded_video.secondary_audio_channel}}</div>
                    </div>
                    <div class="video-info__item">
                        <div class="video-info__item-label">サンプリングレート</div>
                        <div class="video-info__item-value">{{program.recorded_video.secondary_audio_sampling_rate ? `${program.recorded_video.secondary_audio_sampling_rate / 1000}kHz` : '不明'}}</div>
                    </div>
                </template>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { IRecordedProgram } from '@/services/Videos';
import Utils, { ProgramUtils, dayjs } from '@/utils';

// Props
defineProps<{
    program: IRecordedProgram;
    show: boolean;
}>();

// Emits
defineEmits<{
    (e: 'update:show', value: boolean): void;
}>();

</script>
<style lang="scss" scoped>

.video-info {
    &__item {
        display: flex;
        margin-top: 8px;

        &-label {
            flex-shrink: 0;
            width: 140px;
            color: rgb(var(--v-theme-text-darken-1));
            font-size: 14px;
        }

        &-value {
            flex-grow: 1;
            font-size: 14px;
            word-break: break-word;
        }
    }
}

</style>
