<template>
    <!-- 番組の局ロゴ・局名・放送時間と、番組概要 (1枚表示の情報欄と番組の画面で同じ見た目にする) -->
    <div class="capture-program-info">
        <div class="capture-program-info__broadcaster">
            <img v-if="program.channel !== null" class="capture-program-info__broadcaster-icon"
                :src="`${Utils.api_base_url}/channels/${program.channel.id}/logo`" @error="onLogoError">
            <div class="capture-program-info__broadcaster-container">
                <div v-if="program.channel !== null" class="capture-program-info__broadcaster-name">{{ program.channel.name }}</div>
                <div class="capture-program-info__broadcaster-time">
                    {{ formatBroadcast(program) }}<template v-if="captureCount !== null"> / {{ captureCount.toLocaleString() }}枚</template>
                </div>
            </div>
        </div>
        <div v-if="program.description" class="capture-program-info__description"
            v-html="ProgramUtils.decorateProgramInfo(program, 'description')"></div>
    </div>
</template>
<script lang="ts" setup>

import { ICaptureProgram } from '@/services/Captures';
import Utils, { dayjs, ProgramUtils } from '@/utils';


withDefaults(defineProps<{
    program: ICaptureProgram;
    // 番組の画面では、この番組で撮ったキャプチャの枚数を放送時間の横に出す
    captureCount?: number | null;
}>(), {
    captureCount: null,
});

// 局ロゴが取れないときは、ほかの画面と同じく既定のロゴに差し替える
// 既定のロゴも取れないとき (サーバーに接続できないときなど) は、同じ URL を設定し直して読み込みを繰り返すのを避けるため、そのままにする
const onLogoError = (event: Event) => {
    const image = event.target as HTMLImageElement;
    const fallbackUrl = `${Utils.api_base_url}/channels/gr001/logo`;
    if (image.src !== fallbackUrl) {
        image.src = fallbackUrl;
    }
};

// 放送時間は、ほかの画面の番組情報 (ProgramUtils.getProgramTime()) と同じく、番組の長さを分で添える
// 終了時刻が不明な放送回は、同じく放送時間未定と表示する
const formatBroadcast = (program: ICaptureProgram) => {
    const start = dayjs(program.start_time).format('YYYY/MM/DD (dd) HH:mm');
    if (program.end_time === null || program.duration === null) {
        return Utils.apply28HourClock(`${start} ～ --:-- (放送時間未定)`);
    }
    // 分単位の番組長 (割り切れない場合は小数第2位で四捨五入)
    const duration = Math.round(program.duration / 60 * 100) / 100;
    return Utils.apply28HourClock(`${start} ～ ${dayjs(program.end_time).format('HH:mm')} (${duration}分)`);
};

</script>
<style lang="scss" scoped>

// 録画予約の詳細ドロワーの番組情報 (ReservationProgramInfo.vue) と同じ寸法にする
.capture-program-info {
    &__broadcaster {
        display: flex;
        align-items: center;
        min-width: 0;
        margin-top: 14px;
        color: rgb(var(--v-theme-text-darken-1));
        &-icon {
            display: inline-block;
            flex-shrink: 0;
            width: 44px;
            height: 36px;
            margin-right: 12px;
            border-radius: 3px;
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
            object-fit: cover;
            user-select: none;
        }
        &-container {
            display: flex;
            flex-direction: column;
            min-width: 0;
        }
        &-name {
            font-size: 14px;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
        &-time {
            margin-top: 2px;
            font-size: 13.5px;
            @include smartphone-vertical {
                font-size: 12.5px;
            }
        }
    }

    // 番組概要は読んで写したくなる文なので、ページ全体で止めている文字の選択をここだけ戻す
    &__description {
        user-select: text;
        margin-top: 12px;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 12.5px;
        line-height: 168%;
        overflow-wrap: break-word;
        font-feature-settings: "palt" 1;  // 文字詰め
        letter-spacing: 0.08em;  // 字間を少し空ける
    }
}

</style>
