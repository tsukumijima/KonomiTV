<template>
    <CapturePage :crumbs="[
        { name: 'ホーム', path: '/' },
        { name: 'キャプチャ', path: '/captures/' },
        { name: '番組別', path: '/captures/programs/' },
        { name: program ? program.title : '番組', path: route.fullPath, disabled: true },
    ]">
        <div class="capture-program">
            <!-- 番組名から並べ替えまでの見出しの部分 (スマホの縦画面ではマイリストの見出しと同じく左右に 8px を加える) -->
            <div class="capture-program__intro">
                <!-- 戻るボタンと同じ行には番組名だけを置く -->
                <div class="capture-program__header">
                    <div v-ripple class="capture-program__back" @click="$router.back()">
                        <Icon icon="fluent:chevron-left-12-filled" width="27px" />
                    </div>
                    <h2 class="capture-program__title" v-if="program" v-html="ProgramUtils.decorateProgramInfo(program, 'title')"></h2>
                    <h2 class="capture-program__title" v-else>{{ isLoading ? '読み込み中...' : 'この番組のキャプチャ' }}</h2>
                </div>
                <!-- PC では番組の情報の右に並べ替えを置き、並べ替えのためだけの段を作らない (スマホの縦画面では一覧の直前に置く) -->
                <div class="capture-program__body">
                    <!-- 1枚表示の情報欄と同じ部品で、局ロゴ・局名・放送時間・枚数と番組概要を出し、録画の再生を続ける -->
                    <div v-if="program" class="capture-program__meta">
                        <CaptureProgramInfo :program="program" :capture-count="captures.length > 0 ? captures.length : null" />
                        <div v-if="program.recorded_program_ids.length > 0" class="capture-program__actions">
                            <v-btn color="primary" variant="flat" height="38" class="capture-program__action"
                                :to="`/videos/watch/${program.recorded_program_ids[0]}`">
                                <Icon icon="fluent:play-20-filled" width="18px" />
                                <span class="ml-2">録画を再生</span>
                            </v-btn>
                        </div>
                    </div>
                    <div v-if="captures.length > 0" class="capture-program__toolbar">
                    <v-select v-model="order" class="capture-program__order"
                        :items="[
                            { title: '再生位置順', value: 'PlaybackPosition' },
                            { title: '撮影日時が新しい順', value: 'CapturedAtDesc' },
                            { title: '撮影日時が古い順', value: 'CapturedAtAsc' },
                        ]"
                        color="primary" bg-color="background-lighten-1" variant="solo" density="comfortable" hide-details flat />
                    </div>
                </div>
            </div>

            <div v-if="isLoadFailed" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">キャプチャを読み込めませんでした。</div>
                <div class="capture-empty__sub">KonomiTV サーバーが起動しているか確認してから、ページを再読み込みしてください。</div>
            </div>
            <div v-else-if="!isLoading && captures.length === 0" class="capture-empty">
                <Icon class="capture-empty__icon" icon="fluent:image-20-regular" width="54px" height="54px" />
                <div class="capture-empty__message">この番組のキャプチャはまだありません。</div>
                <div class="capture-empty__sub">この番組の視聴中にキャプチャを撮影すると、<br class="d-sm-none">ここに表示されます。</div>
            </div>

            <div class="capture-program__grid" :class="{'capture-program__grid--captions': hasCaptions}">
                <div v-for="capture in captures" :key="capture.id" class="capture-program__item">
                    <div class="capture-program__tile">
                        <CaptureTile :capture="capture" :show-position="order === 'PlaybackPosition'"
                            :selected="selection.isSelected(capture)" :selecting="selection.isSelecting.value"
                            @open="openedCapture = capture"
                            @toggle="(shiftKey) => selection.toggle(capture, shiftKey ? captures : null)"
                            @updated="onUpdated([$event])" />
                    </div>
                    <!-- 字幕が出ていなかった場面は何も書かない (「字幕なし」と書くと、それ自体がセリフに見えるため) -->
                    <div v-if="hasCaptions" class="capture-program__caption">{{ capture.caption_text ?? '' }}</div>
                </div>
            </div>
        </div>

        <CaptureSelectionBar :selection="selection" @updated="onUpdated" @deleted="onDeleted" />
        <CaptureLightbox :capture="openedCapture" :program-hint="program" :navigate="navigate"
            @update:capture="openedCapture = $event" @updated="onUpdated([$event])" @deleted="onDeleted" />
    </CapturePage>
</template>
<script lang="ts" setup>

import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import CaptureLightbox from '@/components/Captures/CaptureLightbox.vue';
import CapturePage from '@/components/Captures/CapturePage.vue';
import CaptureProgramInfo from '@/components/Captures/CaptureProgramInfo.vue';
import { useCaptureSelection } from '@/components/Captures/CaptureSelection';
import CaptureSelectionBar from '@/components/Captures/CaptureSelectionBar.vue';
import CaptureTile from '@/components/Captures/CaptureTile.vue';
import Captures, { CaptureSortOrder, ICapture, ICaptureFilter, ICaptureProgram } from '@/services/Captures';
import Videos from '@/services/Videos';
import useUserStore from '@/stores/UserStore';
import { ProgramUtils } from '@/utils';


const route = useRoute();
const userStore = useUserStore();
const selection = useCaptureSelection();

const program = ref<ICaptureProgram | null>(null);
const captures = ref<ICapture[]>([]);
const isLoading = ref(true);
// 読み込みに失敗したか (0件と区別して、読み込めなかったことを伝えるため)
const isLoadFailed = ref(false);
const order = ref<CaptureSortOrder>('PlaybackPosition');
const openedCapture = ref<ICapture | null>(null);

// どの入口から来たかで、絞り込みの条件を変える
// - /captures/programs/:capture_program_id: キャプチャの番組の ID
// - /captures/recorded/:video_id: 録画番組のメニューから (番組キーが同じキャプチャ)
// - /captures/broadcast?network_id=...: ライブ視聴から (番組キーそのもの)
const filter = computed<ICaptureFilter>(() => {
    if (route.params.capture_program_id !== undefined) {
        return { capture_program_id: Number(route.params.capture_program_id) };
    }
    if (route.params.video_id !== undefined) {
        return { recorded_program_id: Number(route.params.video_id) };
    }
    return {
        network_id: Number(route.query.network_id),
        service_id: Number(route.query.service_id),
        event_id: Number(route.query.event_id),
        start_time: String(route.query.start_time ?? ''),
    };
});

// 字幕のあるキャプチャが1枚でもあれば、タイルの下にセリフを出す (絵コンテのように場面を追えるように)
const hasCaptions = computed(() => captures.value.some(capture => capture.caption_text));

// 読み込みごとに増やす番号 (並べ替えを続けて変えたときに、最新の読み込みの応答だけを反映するため)
let loadGeneration = 0;

const load = async () => {
    loadGeneration++;
    const myGeneration = loadGeneration;
    isLoading.value = true;
    const result = await Captures.fetchAllCaptures({ order: order.value, filter: filter.value });
    if (myGeneration !== loadGeneration) {
        return;
    }
    isLoading.value = false;
    isLoadFailed.value = result === null;
    if (result === null) {
        captures.value = [];
        return;
    }
    captures.value = result.captures;
    // 番組の情報は、ID で来たときは番組の API から、それ以外はキャプチャが参照する番組から取る
    let nextProgram: ICaptureProgram | null = result.programs[0] ?? null;
    if (route.params.capture_program_id !== undefined) {
        nextProgram = (await Captures.fetchProgram(Number(route.params.capture_program_id))) ?? nextProgram;
    }
    // キャプチャがまだ無い番組でも見出しに番組名や局ロゴを出せるよう、入口に応じて番組の情報を補う
    if (nextProgram === null) {
        nextProgram = await fetchFallbackProgram();
    }
    if (myGeneration === loadGeneration) {
        program.value = nextProgram;
    }
};

/**
 * キャプチャがまだ無いときに、見出しに出す番組の情報を入口に応じて取る
 * - 録画番組から来たとき: 録画番組の API から取る
 * - ライブの番組パネルから来たとき: 画面の移動と一緒に渡された番組の情報を使う
 * @returns 番組の情報 (取れなければ null)
 */
const fetchFallbackProgram = async (): Promise<ICaptureProgram | null> => {
    if (route.params.video_id !== undefined) {
        const video = await Videos.fetchVideo(Number(route.params.video_id));
        if (video === null) {
            return null;
        }
        return {
            id: 0,
            network_id: video.network_id ?? 0,
            service_id: video.service_id ?? 0,
            event_id: video.event_id ?? 0,
            start_time: video.start_time,
            end_time: video.end_time,
            duration: video.duration,
            title: video.title,
            description: video.description,
            channel: video.channel === null ? null : {
                id: video.channel.id,
                display_channel_id: video.channel.display_channel_id,
                name: video.channel.name,
                type: video.channel.type,
            },
            recorded_program_ids: [video.id],
        };
    }
    const hint = (window.history.state as { capture_program_hint?: ICaptureProgram } | null)?.capture_program_hint;
    return hint ?? null;
};
watch(order, load);
watch(() => route.fullPath, () => {
    selection.clear();
    openedCapture.value = null;
    void load();
});

const navigate = async (capture: ICapture, delta: 1 | -1) => {
    const index = captures.value.findIndex(item => item.id === capture.id);
    return captures.value[index + delta] ?? null;
};
// 削除したキャプチャは、取り直しを待たずに一覧から外す (取り直しの間に1枚表示が削除したキャプチャを隣として拾わないため)
const onDeleted = (deletedIds: number[]) => {
    const ids = new Set(deletedIds);
    captures.value = captures.value.filter(capture => !ids.has(capture.id));
    void load();
};
const onUpdated = (updated: ICapture[]) => {
    const byId = new Map(updated.map(capture => [capture.id, capture]));
    captures.value = captures.value.map(capture => byId.get(capture.id) ?? capture);
    if (openedCapture.value !== null && byId.has(openedCapture.value.id)) {
        openedCapture.value = byId.get(openedCapture.value.id)!;
    }
};

onMounted(async () => {
    await userStore.fetchUser();
    await load();
});

</script>
<style lang="scss" scoped>

.capture-program {
    display: flex;
    flex-direction: column;
    min-width: 0;

    &__intro {
        @include smartphone-vertical {
            padding: 0px 8px;
        }
    }
    &__header {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        padding-top: 8px;
    }
    &__back {
        display: flex;
        flex-shrink: 0;
        margin-left: -8px;
        padding: 6px;
        border-radius: 50%;
        cursor: pointer;
    }
    &__title {
        min-width: 0;
        font-size: 22px;
        font-weight: 700;
        line-height: 1.45;
        margin-top: 2px;
        @include smartphone-vertical {
            font-size: 18px;
        }
    }
    &__actions {
        display: flex;
        margin-top: 16px;
    }
    &__action {
        border-radius: 7px;
        letter-spacing: 0;
    }
    // PC では、番組の情報と並べ替えを横に並べ、並べ替えの下端を番組の情報の下端にそろえる
    &__body {
        display: flex;
        align-items: flex-end;
        gap: 24px;
        @include smartphone-vertical {
            flex-direction: column;
            align-items: stretch;
            gap: 0;
        }
    }
    &__meta {
        flex: 1;
        min-width: 0;
    }
    &__toolbar {
        display: flex;
        flex-shrink: 0;
        justify-content: flex-end;
        @include smartphone-vertical {
            margin-top: 16px;
        }
    }
    // 高さと角の丸みは「録画を再生」ボタン (38px・7px) にそろえ、文字は上下の余白を詰めて中央に置く
    &__order {
        flex: 0 0 190px;
        @include smartphone-vertical {
            flex: 1 0 100%;
        }
        :deep(.v-field) {
            padding-right: 6px !important;
            border-radius: 7px;
        }
        :deep(.v-field__input) {
            align-items: center;
            min-height: 38px !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
            padding-left: 14px !important;
            padding-right: 0px !important;
            font-size: 15px !important;
        }
    }

    &__grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 8px;
        margin-top: 20px;
        @include smartphone-vertical {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 6px 4px;
        }
        &--captions {
            row-gap: 12px;
        }
    }
    &__item {
        min-width: 0;
    }
    &__tile {
        aspect-ratio: 16 / 9;
    }
    &__caption {
        margin-top: 5px;
        padding: 0 2px;
        font-size: 12.5px;
        line-height: 1.45;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        @include smartphone-vertical {
            font-size: 11.5px;
        }
    }
}

</style>
