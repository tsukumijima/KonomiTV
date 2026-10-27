<template>
    <CapturePage :crumbs="[
        { name: 'ホーム', path: '/' },
        { name: 'キャプチャ', path: '/captures/' },
        { name: '番組', path: '/captures/programs/', disabled: true },
    ]">
        <CaptureHeader title="番組" active-tab="Programs" @scanned="reset" />
        <div class="capture-programs__toolbar">
            <v-text-field v-model="queryInput" class="capture-programs__search" color="primary" bg-color="background-lighten-1"
                variant="solo" density="comfortable" hide-details flat clearable placeholder="番組名・チャンネル名で絞り込む"
                @keydown.enter="applyQuery" @click:clear="queryInput = ''; applyQuery()">
                <template #prepend-inner>
                    <Icon icon="fluent:search-20-regular" width="18px" class="text-text-darken-1" />
                </template>
            </v-text-field>
            <v-select v-model="recordedFilter" class="capture-programs__recorded"
                :items="[{ title: 'すべての番組', value: null }, { title: '録画のある番組', value: true }, { title: '録画のない番組', value: false }]"
                color="primary" bg-color="background-lighten-1" variant="solo" density="comfortable" hide-details flat />
        </div>

        <div v-if="isLoadFailed" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">番組の一覧を読み込めませんでした。</div>
            <div class="capture-empty__sub">KonomiTV サーバーが動いているかを確認してから、ページを再読み込みしてください。</div>
        </div>
        <div v-else-if="!isLoading && programs.length === 0 && (String(route.query.query ?? '') !== '' || recordedFilter !== null)" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:search-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">条件に合う番組はありません。</div>
            <div class="capture-empty__sub">検索語を消すか、「すべての番組」に戻すと、ほかの番組も表示されます。</div>
        </div>
        <div v-else-if="!isLoading && programs.length === 0" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:video-clip-multiple-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">番組ごとにまとめられるキャプチャはまだありません。</div>
            <div class="capture-empty__sub">KonomiTV の視聴画面で撮ったキャプチャは、<br class="d-none d-sm-inline">撮影した番組の放送回ごとに、ここへまとまります。</div>
        </div>
        <div class="capture-programs__grid">
            <router-link v-for="program in programs" :key="program.id" v-ripple class="capture-program-card"
                :to="`/captures/programs/${program.id}`">
                <div class="capture-program-card__cover">
                    <img :src="Captures.getImageURL(program.cover_capture)" loading="lazy" decoding="async" alt="">
                    <span v-if="program.recorded_program_ids.length > 0" class="capture-program-card__badge">録画あり</span>
                    <span class="capture-program-card__count">{{ program.capture_count.toLocaleString() }}枚</span>
                </div>
                <div class="capture-program-card__meta">
                    <div class="capture-program-card__title" v-html="ProgramUtils.decorateProgramInfo(program, 'title')"></div>
                    <div class="capture-program-card__sub">
                        <span v-if="program.channel" class="capture-program-card__channel">{{ program.channel.name }}</span>
                        <span>{{ formatStart(program.start_time) }}</span>
                    </div>
                </div>
            </router-link>
        </div>
        <div ref="sentinelRef" class="capture-programs__sentinel">
            <Icon v-if="isLoading" icon="line-md:loading-twotone-loop" width="28px" />
        </div>
    </CapturePage>
</template>
<script lang="ts" setup>

import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import CaptureHeader from '@/components/Captures/CaptureHeader.vue';
import CapturePage from '@/components/Captures/CapturePage.vue';
import Captures, { ICaptureProgramAlbum } from '@/services/Captures';
import Utils, { dayjs, ProgramUtils } from '@/utils';


const route = useRoute();
const router = useRouter();

const programs = ref<ICaptureProgramAlbum[]>([]);
const nextCursor = ref<string | null>(null);
const isLoading = ref(false);
const isEnd = ref(false);
const queryInput = ref(String(route.query.query ?? ''));
// 最初のページを読み込めなかったか (0件と区別して、読み込めなかったことを伝えるため)
const isLoadFailed = ref(false);
const recordedFilter = ref<boolean | null>(route.query.has_recorded_program === 'true' ? true : route.query.has_recorded_program === 'false' ? false : null);
let generation = 0;
// 戻る操作でこの一覧へ戻ったときの、離れたときのスクロール位置
// 続きのページは下端の目印が見えるまで読み込まないので、この位置が画面に入るところまで続けて読み込み、Vue Router が位置を戻せる高さにする
let restoringScrollTop: number | null = window.history.state?.scroll?.top ?? null;

// 次のページを読み込む (下端の目印が見えたら呼ばれる)
const loadMore = async () => {
    if (isLoading.value || isEnd.value) {
        return;
    }
    isLoading.value = true;
    const myGeneration = generation;
    const result = await Captures.fetchPrograms({
        cursor: nextCursor.value,
        query: String(route.query.query ?? ''),
        has_recorded_program: recordedFilter.value,
    });
    if (myGeneration !== generation) {
        return;
    }
    isLoading.value = false;
    if (result === null) {
        isEnd.value = true;
        isLoadFailed.value = programs.value.length === 0;
        return;
    }
    isLoadFailed.value = false;
    programs.value = [...programs.value, ...result.programs];
    nextCursor.value = result.next_cursor;
    isEnd.value = result.next_cursor === null;
    // 1ページで画面が埋まらないときは、続けて読み込む
    requestAnimationFrame(checkSentinel);
};
const reset = () => {
    generation++;
    programs.value = [];
    nextCursor.value = null;
    isEnd.value = false;
    isLoading.value = false;
    void loadMore();
};

const applyQuery = () => {
    const query = { ...route.query, query: queryInput.value?.trim() || undefined };
    void router.replace({ query });
};
watch(recordedFilter, (value) => {
    void router.replace({ query: { ...route.query, has_recorded_program: value === null ? undefined : String(value) } });
});
watch(() => [route.query.query, route.query.has_recorded_program], () => {
    restoringScrollTop = null;
    reset();
});

const sentinelRef = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;
const checkSentinel = () => {
    if (sentinelRef.value === null) {
        return;
    }
    const sentinelTop = sentinelRef.value.getBoundingClientRect().top;
    // 戻る操作で戻ったときは、離れたときの位置が画面に入る高さになるまで続けて読み込む
    if (restoringScrollTop !== null && window.scrollY + sentinelTop >= restoringScrollTop + window.innerHeight) {
        restoringScrollTop = null;
    }
    if (sentinelTop < window.innerHeight + 400 || restoringScrollTop !== null) {
        void loadMore();
    }
};
onMounted(() => {
    observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            void loadMore();
        }
    }, { rootMargin: '400px 0px' });
    if (sentinelRef.value !== null) {
        observer.observe(sentinelRef.value);
    }
    reset();
});
onBeforeUnmount(() => observer?.disconnect());

const formatStart = (value: string) => Utils.apply28HourClock(dayjs(value).format('YYYY/MM/DD (dd) HH:mm'));

</script>
<style lang="scss" scoped>

.capture-programs {
    &__toolbar {
        display: flex;
        gap: 10px;
        margin-bottom: 16px;
        @include smartphone-vertical {
            flex-direction: column;
            gap: 8px;
        }
    }
    &__search {
        flex: 1;
        max-width: 420px;
        @include smartphone-vertical {
            max-width: none;
        }
    }
    &__recorded {
        flex: 0 0 180px;
        @include smartphone-vertical {
            flex: none;
        }
    }
    &__grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 16px;
        @include smartphone-vertical {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
        }
    }
    &__sentinel {
        display: flex;
        justify-content: center;
        padding: 24px 0;
        color: rgb(var(--v-theme-text-darken-1));
    }
}

.capture-program-card {
    display: flex;
    flex-direction: column;
    min-width: 0;
    border-radius: 10px;
    overflow: hidden;
    background: rgb(var(--v-theme-background-lighten-1));
    color: rgb(var(--v-theme-text));
    text-decoration: none;
    transition: background-color 0.15s ease;
    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }

    &__cover {
        position: relative;
        aspect-ratio: 16 / 9;
        background: rgb(var(--v-theme-background-lighten-2));
        img {
            display: block;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
    }
    &__badge {
        position: absolute;
        top: 8px;
        left: 8px;
        padding: 1px 8px;
        border-radius: 10px;
        background: rgb(var(--v-theme-primary));
        color: #fff;
        font-size: 11.5px;
        line-height: 20px;
    }
    &__count {
        position: absolute;
        right: 8px;
        bottom: 8px;
        padding: 1px 8px;
        border-radius: 10px;
        background: rgba(0, 0, 0, 0.66);
        color: #fff;
        font-size: 12px;
        line-height: 20px;
    }
    &__meta {
        padding: 10px 12px 12px;
        @include smartphone-vertical {
            padding: 8px 9px 10px;
        }
    }
    &__title {
        font-size: 14.5px;
        font-weight: 700;
        line-height: 1.45;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        @include smartphone-vertical {
            font-size: 13px;
        }
    }
    &__sub {
        display: flex;
        flex-wrap: wrap;
        gap: 2px 10px;
        margin-top: 6px;
        font-size: 12.5px;
        color: rgb(var(--v-theme-text-darken-1));
        @include smartphone-vertical {
            font-size: 11.5px;
        }
    }
    &__channel {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
}

</style>
