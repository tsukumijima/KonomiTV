<template>
    <div class="capture-info">
        <!-- 番組の情報 (録画予約の詳細ドロワーの番組情報と同じ並びにする) -->
        <section v-if="program !== null" class="capture-info__program">
            <h1 class="capture-info__title" v-html="ProgramUtils.decorateProgramInfo(program, 'title')"></h1>
            <CaptureProgramInfo :program="program" />
            <div class="capture-info__actions">
                <v-btn variant="flat" color="background-lighten-2" height="38" class="capture-info__action" @click="$emit('open-program')">
                    <Icon icon="fluent:image-multiple-20-regular" width="18px" />
                    <span class="ml-2">この番組のキャプチャ</span>
                </v-btn>
                <v-btn v-if="program.recorded_program_ids.length > 0" variant="flat" color="primary" height="38"
                    class="capture-info__action" @click="$emit('play')">
                    <Icon icon="fluent:play-20-filled" width="18px" />
                    <span class="ml-2">{{ capture.playback_position !== null ? 'この場面から再生' : '録画を再生' }}</span>
                </v-btn>
            </div>
        </section>
        <section v-else class="capture-info__program">
            <h1 class="capture-info__title">番組情報がありません</h1>
            <div class="capture-info__description">撮影時の番組情報が、この画像には記録されていません。</div>
        </section>

        <!-- 撮影したときに出ていた字幕 -->
        <div v-if="capture.caption_text" class="capture-info__caption">
            <div class="capture-info__caption-heading">
                <Icon icon="fluent:closed-caption-20-regular" width="18px" />
                <span>字幕テキスト</span>
            </div>
            <div class="capture-info__caption-text">{{ capture.caption_text }}</div>
        </div>

        <!-- キャプチャ自体の情報 -->
        <div class="capture-info__list">
            <div class="capture-info__row">
                <span class="capture-info__label">撮影日時</span>
                <span>{{ formatDateTime(capture.captured_at) }}</span>
            </div>
            <div v-if="capture.broadcast_at" class="capture-info__row">
                <span class="capture-info__label">放送日時</span>
                <span>{{ formatDateTime(capture.broadcast_at) }}</span>
            </div>
            <div v-if="capture.playback_position !== null" class="capture-info__row">
                <span class="capture-info__label">再生位置</span>
                <span>開始から {{ formatPosition(capture.playback_position) }}</span>
            </div>
            <div class="capture-info__row">
                <span class="capture-info__label">画像サイズ</span>
                <span>{{ capture.image_width }}×{{ capture.image_height }}・{{ Utils.formatBytes(capture.file_size) }}</span>
            </div>
            <div class="capture-info__row">
                <span class="capture-info__label">合成情報</span>
                <span>{{ contentLabel }}</span>
            </div>
            <div v-if="detail !== null" class="capture-info__row">
                <span class="capture-info__label">保存場所</span>
                <span class="capture-info__files">
                    <span v-for="file in detail.files" :key="file.file_path">
                        {{ file.file_path }}<template v-if="file.status !== 'Available'"> ({{ file.status === 'Missing' ? 'ファイルが見つかりません' : 'ファイルを読み込めません' }})</template>
                    </span>
                </span>
            </div>
        </div>

        <div v-if="tagNames.length > 0" class="capture-info__tags">
            <span v-for="name in tagNames" :key="name" class="capture-info__tag">
                <Icon icon="fluent:tag-16-regular" width="14px" />
                {{ name }}
            </span>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import CaptureProgramInfo from '@/components/Captures/CaptureProgramInfo.vue';
import { ICapture, ICaptureDetail, ICaptureProgram } from '@/services/Captures';
import Utils, { dayjs, ProgramUtils } from '@/utils';


const props = defineProps<{
    capture: ICapture;
    detail: ICaptureDetail | null;
    program: ICaptureProgram | null;
    tagNames: string[];
}>();

defineEmits<{
    (event: 'open-program'): void;
    (event: 'play'): void;
}>();

// 画像に何が写し込まれているか (映像だけか、字幕やコメントも一緒に撮ったか)
const contentLabel = computed(() => {
    const parts = ['映像'];
    if (props.capture.is_caption_composited) {
        parts.push('字幕');
    }
    if (props.capture.is_comment_composited) {
        parts.push('コメント');
    }
    return parts.length === 1 ? '映像のみ' : parts.join('と');
});

const formatDateTime = (value: string) => Utils.apply28HourClock(dayjs(value).format('YYYY/MM/DD (dd) HH:mm:ss'));
const formatPosition = (seconds: number) => {
    const sign = seconds < 0 ? '-' : '';
    const value = Math.floor(Math.abs(seconds));
    const minutes = Math.floor(value / 60);
    return `${sign}${minutes}分${String(value % 60).padStart(2, '0')}秒`;
};

</script>
<style lang="scss" scoped>

.capture-info {
    padding: 0px 20px 24px;
    color: rgb(var(--v-theme-text));
    @include smartphone-vertical {
        padding: 4px 16px calc(env(safe-area-inset-bottom) + 24px);
    }

    &__title {
        font-size: 19px;
        font-weight: bold;
        line-height: 145%;
        font-feature-settings: "palt" 1;  // 文字詰め
        letter-spacing: 0.05em;  // 字間を少し空ける
        @include smartphone-vertical {
            font-size: 17px;
        }
    }

    &__actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
    }
    // 2つのボタンは、横に収まるときは並べて幅を分け合い、収まらないときはそれぞれ全幅の行に折り返す
    &__action {
        flex: 1 1 auto;
        padding: 0 12px !important;
        border-radius: 6px;
        letter-spacing: 0;
        font-size: 13.5px;
    }

    &__caption {
        margin-top: 20px;
        padding: 10px 12px;
        border-radius: 8px;
        background: rgb(var(--v-theme-background-lighten-1));
        &-heading {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12.5px;
            color: rgb(var(--v-theme-text-darken-1));
        }
        // 字幕は写したくなる文なので、文字の選択を戻す
        &-text {
            user-select: text;
            margin-top: 4px;
            font-size: 14px;
            line-height: 1.6;
            white-space: pre-wrap;
        }
    }

    &__list {
        margin-top: 20px;
    }
    &__row {
        display: flex;
        gap: 12px;
        padding: 8px 0;
        font-size: 13.5px;
        line-height: 1.6;
        border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
    }
    &__label {
        flex-shrink: 0;
        width: 100px;
        color: rgb(var(--v-theme-text-darken-1));
    }
    // 保存場所は写したくなる文なので、文字の選択を戻す
    &__files {
        user-select: text;
        display: flex;
        flex-direction: column;
        min-width: 0;
        word-break: break-all;
    }

    &__tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 16px;
    }
    &__tag {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 2px 10px;
        border-radius: 12px;
        background: rgb(var(--v-theme-background-lighten-2));
        font-size: 12.5px;
    }
}

</style>
