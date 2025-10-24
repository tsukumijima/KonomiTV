<template>
    <v-dialog max-width="770" transition="slide-y-transition" :model-value="show" @update:model-value="$emit('update:show', $event)">
        <v-card class="clip-video-info">
            <v-card-title class="px-5 pt-6 pb-3 d-flex align-center font-weight-bold" style="height: 60px;">
                <Icon icon="fluent:document-20-filled" height="26px" />
                <span class="ml-3">クリップ動画情報</span>
                <v-spacer></v-spacer>
                <div v-ripple class="d-flex align-center rounded-circle cursor-pointer px-2 py-2" @click="$emit('update:show', false)">
                    <Icon icon="fluent:dismiss-12-filled" width="23px" height="23px" />
                </div>
            </v-card-title>
            <div class="px-5 pb-6">
                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-2">
                    <Icon icon="fluent:video-clip-20-filled" width="24px" height="20px" />
                    <span class="ml-2">クリップ情報</span>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">タイトル</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.title }}</div>
                </div>
                <div class="clip-video-info__item" v-if="clipVideo.alternate_title">
                    <div class="clip-video-info__item-label">別タイトル</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.alternate_title }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">元番組タイトル</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.recorded_program.title }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">元動画での開始位置</div>
                    <div class="clip-video-info__item-value">{{ formattedStartTime }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">元動画での終了位置</div>
                    <div class="clip-video-info__item-value">{{ formattedEndTime }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">クリップの長さ</div>
                    <div class="clip-video-info__item-value">{{ formattedDuration }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">作成日時</div>
                    <div class="clip-video-info__item-value">{{ formattedCreatedAt }}</div>
                </div>

                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:folder-20-filled" width="22px" height="20px" />
                    <span class="ml-2">ファイル情報</span>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">ファイルパス</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.file_path }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">ファイルサイズ</div>
                    <div class="clip-video-info__item-value">{{ Utils.formatBytes(clipVideo.file_size) }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">ファイルハッシュ</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.file_hash }}</div>
                </div>

                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:video-20-filled" width="24px" height="20px" />
                    <span class="ml-2">映像情報</span>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">コンテナ形式</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.container_format }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">コーデック</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.video_codec }} ({{ clipVideo.video_codec_profile }})</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">解像度</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.video_resolution_width }}×{{ clipVideo.video_resolution_height }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">フレームレート</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.video_frame_rate }} fps</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">スキャン方式</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.video_scan_type }}</div>
                </div>

                <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                    <Icon icon="fluent:speaker-2-20-filled" width="24px" height="20px" />
                    <span class="ml-2">音声情報（主音声）</span>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">コーデック</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.primary_audio_codec }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">チャンネル</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.primary_audio_channel }}</div>
                </div>
                <div class="clip-video-info__item">
                    <div class="clip-video-info__item-label">サンプリングレート</div>
                    <div class="clip-video-info__item-value">{{ clipVideo.primary_audio_sampling_rate ? `${clipVideo.primary_audio_sampling_rate / 1000}kHz` : '不明' }}</div>
                </div>

                <template v-if="clipVideo.secondary_audio_codec">
                    <div class="text-subtitle-1 d-flex align-center font-weight-bold mt-4">
                        <Icon icon="fluent:speaker-2-20-filled" width="24px" height="20px" />
                        <span class="ml-2">音声情報（副音声）</span>
                    </div>
                    <div class="clip-video-info__item">
                        <div class="clip-video-info__item-label">コーデック</div>
                        <div class="clip-video-info__item-value">{{ clipVideo.secondary_audio_codec }}</div>
                    </div>
                    <div class="clip-video-info__item">
                        <div class="clip-video-info__item-label">チャンネル</div>
                        <div class="clip-video-info__item-value">{{ clipVideo.secondary_audio_channel }}</div>
                    </div>
                    <div class="clip-video-info__item">
                        <div class="clip-video-info__item-label">サンプリングレート</div>
                        <div class="clip-video-info__item-value">{{ clipVideo.secondary_audio_sampling_rate ? `${clipVideo.secondary_audio_sampling_rate / 1000}kHz` : '不明' }}</div>
                    </div>
                </template>
            </div>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import { IClipVideo } from '@/services/ClipVideos';
import Utils, { dayjs } from '@/utils';

const props = defineProps<{
    clipVideo: IClipVideo;
    show: boolean;
}>();

defineEmits<{
    (e: 'update:show', value: boolean): void;
}>();

const formatSeconds = (seconds: number): string => {
    const total = Math.max(0, Math.floor(seconds));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
};

const formattedStartTime = computed(() => formatSeconds(props.clipVideo.start_time));
const formattedEndTime = computed(() => formatSeconds(props.clipVideo.end_time));
const formattedDuration = computed(() => formatSeconds(props.clipVideo.duration));
const formattedCreatedAt = computed(() => {
    return Utils.apply28HourClock(dayjs(props.clipVideo.created_at).format('YYYY/MM/DD (dd) HH:mm:ss'));
});

</script>
<style lang="scss" scoped>

.clip-video-info {
    &__item {
        display: flex;
        margin-top: 8px;

        &-label {
            flex-shrink: 0;
            width: 150px;
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
