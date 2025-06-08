<template>
    <div class="reservation-program-info">
        <!-- 番組タイトル -->
        <div class="reservation-program-info__title"
            v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'title')"></div>

        <!-- 番組メタ情報 -->
        <div class="reservation-program-info__meta">
            <div class="reservation-program-info__meta-broadcaster">
                <img class="reservation-program-info__meta-broadcaster-icon" loading="lazy" decoding="async"
                    :src="`${Utils.api_base_url}/channels/${reservation.channel.id}/logo`"
                    @error="onLogoError">
                <span class="reservation-program-info__meta-broadcaster-name">Ch: {{ reservation.channel.channel_number }} {{ reservation.channel.name }}</span>
            </div>
            <div class="reservation-program-info__meta-time">{{ ProgramUtils.getProgramTime(reservation.program) }}</div>
            <!-- 赤い境界線 -->
            <div class="reservation-program-info__meta-divider"></div>
        </div>

        <!-- 番組概要 -->
        <div class="reservation-program-info__description"
            v-html="ProgramUtils.decorateProgramInfo(reservation.program, 'description')"></div>

        <!-- ジャンルチップ -->
        <div v-if="reservation.program.genres && reservation.program.genres.length > 0" class="reservation-program-info__genre">
            <v-chip
                color="background-lighten-2"
                size="small"
                variant="tonal">
                {{ reservation.program.genres[0].major }}{{ reservation.program.genres[0].middle ? ` / ${reservation.program.genres[0].middle}` : '' }}
            </v-chip>
        </div>

        <!-- 音声・映像情報 -->
        <div class="reservation-program-info__audio-video">
            <!-- 映像情報 -->
            <div class="reservation-program-info__info-item">
                <Icon icon="fluent:video-16-filled" width="16px" height="16px" />
                <span>映像: {{ reservation.program.video_type || 'MPEG-2 / 1080i' }}</span>
            </div>

            <!-- 主音声情報 -->
            <div class="reservation-program-info__info-item">
                <Icon icon="fluent:headphones-sound-wave-20-filled" width="16px" height="16px" />
                <span>主音声: {{ reservation.program.primary_audio_type }} {{ reservation.program.primary_audio_sampling_rate || '48kHz' }} / {{ reservation.program.primary_audio_language }}</span>
            </div>

            <!-- 副音声情報（存在する場合） -->
            <div v-if="reservation.program.secondary_audio_type" class="reservation-program-info__info-item">
                <Icon icon="fluent:headphones-sound-wave-20-filled" width="16px" height="16px" />
                <span>副音声: {{ reservation.program.secondary_audio_type }} {{ reservation.program.secondary_audio_sampling_rate || '48kHz' }} / {{ reservation.program.secondary_audio_language }}</span>
            </div>
        </div>

        <!-- 番組内容セクション -->
        <div v-if="reservation.program.detail && Object.keys(reservation.program.detail).length > 0" class="reservation-program-info__detail">
            <h3 class="reservation-program-info__detail-title">番組内容</h3>
            <div v-for="(content, key) in reservation.program.detail" :key="key"
                class="reservation-program-info__detail-content">
                {{ content }}
            </div>
        </div>

        <!-- 番組詳細があれば続きを表示 -->
        <div v-if="hasMoreContent" class="reservation-program-info__more">
            <h3 class="reservation-program-info__detail-title">番組内容つづき</h3>
            <div class="reservation-program-info__detail-content">
                <!-- 続きの内容がある場合の表示 -->
            </div>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { computed } from 'vue';

import { type IReservation } from '@/services/Reservations';
import Utils, { ProgramUtils } from '@/utils';

// Props
const props = defineProps<{
    reservation: IReservation;
}>();

// 番組詳細にさらに内容があるかどうか
const hasMoreContent = computed(() => {
    // 実際の判定ロジックはプロジェクトの実装に依存
    return false;
});

// ロゴ画像エラー時のフォールバック
const onLogoError = (event: Event) => {
    const target = event.target as HTMLImageElement;
    target.src = `${Utils.api_base_url}/channels/gr001/logo`;
};

</script>
<style lang="scss" scoped>

.reservation-program-info {
    display: flex;
    flex-direction: column;
    gap: 16px;
    color: rgb(var(--v-theme-text));

    &__title {
        font-size: 19px;
        font-weight: 700;
        line-height: 1.45;
        margin-top: 4px;
    }

    &__meta {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    &__meta-broadcaster {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    &__meta-broadcaster-icon {
        width: 44px;
        height: 36px;
        border-radius: 4px;
        object-fit: contain;
        background: rgb(var(--v-theme-background-lighten-1));
    }

    &__meta-broadcaster-name {
        font-family: 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 15.5px;
        font-weight: 600;
        line-height: 1.4;
        color: rgb(var(--v-theme-text-darken-1));
    }

    &__meta-time {
        font-family: 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 12.5px;
        font-weight: 600;
        line-height: 1.4;
        color: rgb(var(--v-theme-text-darken-1));
        margin-left: 56px; // アイコンの幅 + gap を考慮
    }

    &__meta-divider {
        width: 10px;
        height: 0;
        border-top: 1px solid #803434;
        margin-left: 56px;
        margin-top: 4px;
    }

    &__description {
        font-size: 12px;
        font-weight: 500;
        line-height: 1.65;
        color: rgb(var(--v-theme-text-darken-1));
        margin-top: 8px;
    }

    &__genre {
        margin-top: 4px;
    }

    &__audio-video {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-top: 8px;
    }

    &__info-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 500;
        line-height: 1.65;
        color: rgb(var(--v-theme-text-darken-1));

        svg {
            color: rgb(var(--v-theme-text));
            flex-shrink: 0;
        }
    }

    &__detail {
        margin-top: 8px;
    }

    &__detail-title {
        font-size: 18px;
        font-weight: 700;
        line-height: 1.5;
        color: rgb(var(--v-theme-text));
        margin-bottom: 8px;
    }

    &__detail-content {
        font-size: 12px;
        font-weight: 500;
        line-height: 1.68;
        color: rgb(var(--v-theme-text-darken-1));
    }

    &__more {
        margin-top: 16px;
    }
}
</style>