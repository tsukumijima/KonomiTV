<template>
    <CapturePage :crumbs="[
        { name: 'ホーム', path: '/' },
        { name: 'キャプチャ', path: '/captures/' },
        { name: '番組別', path: '/captures/programs/', disabled: true },
    ]">
        <CaptureHeader title="番組別" active-tab="Programs" @scanned="reset" @uploaded="reset" />
        <div class="capture-programs__toolbar">
            <v-text-field v-model="queryInput" class="capture-programs__search" color="primary" bg-color="background-lighten-1"
                variant="solo" density="comfortable" hide-details flat clearable placeholder="番組名・チャンネル名で絞り込む"
                @keydown.enter="applyQuery" @click:clear="queryInput = ''; applyQuery()">
                <template #prepend-inner>
                    <Icon icon="fluent:search-20-regular" width="18px" class="text-text-darken-1" />
                </template>
            </v-text-field>
            <!-- 絞り込みは検索欄の隣、並べ替えは同じ行の右端に配置する (スマホの縦画面では検索欄の下に2つを並べる) -->
            <div class="capture-programs__selects">
                <v-select v-model="recordedFilter" class="capture-programs__select"
                    :items="[{ title: 'すべての番組', value: null }, { title: '録画番組あり', value: true }, { title: '録画番組なし', value: false }]"
                    color="primary" bg-color="background-lighten-1" variant="solo" density="comfortable" hide-details flat />
                <v-select v-model="order" class="capture-programs__select capture-programs__select--order"
                    :items="[{ title: '放送が新しい順', value: 'BroadcastAtDesc' }, { title: '放送が古い順', value: 'BroadcastAtAsc' }]"
                    color="primary" bg-color="background-lighten-1" variant="solo" density="comfortable" hide-details flat />
            </div>
        </div>

        <!-- 最初のページの読み込み中は、ほかのキャプチャの画面と同じく見出しより下の領域の中央にスピナーを表示する -->
        <div v-if="isLoading && programs.length === 0" class="capture-loading">
            <Icon icon="line-md:loading-twotone-loop" width="48px" height="48px" />
        </div>
        <div v-else-if="isLoadFailed" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:cloud-error-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">番組の一覧を読み込めませんでした。</div>
            <div class="capture-empty__sub">KonomiTV サーバーが起動しているか確認してから、ページを再読み込みしてください。</div>
        </div>
        <div v-else-if="!isLoading && programs.length === 0 && (String(route.query.query ?? '') !== '' || recordedFilter !== null)" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:search-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">条件に一致する番組はありません。</div>
            <div class="capture-empty__sub">検索キーワードを消去するか、絞り込みを「すべての番組」に戻すと、他の番組も表示されます。</div>
        </div>
        <div v-else-if="!isLoading && programs.length === 0" class="capture-empty">
            <Icon class="capture-empty__icon" icon="fluent:video-clip-multiple-20-regular" width="54px" height="54px" />
            <div class="capture-empty__message">番組情報が記録されたキャプチャはまだありません。</div>
            <div class="capture-empty__sub">視聴画面でキャプチャを撮影すると、<br class="d-none d-sm-inline">番組の放送回ごとにここにまとまって表示されます。</div>
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
                    <!-- 局ロゴ・局名・放送時間は、番組名の行数にかかわらずカードの下端にそろえる -->
                    <div class="capture-program-card__broadcaster">
                        <img v-if="program.channel !== null" class="capture-program-card__broadcaster-icon" loading="lazy" decoding="async"
                            :src="`${Utils.api_base_url}/channels/${program.channel.id}/logo`" @error="onLogoError">
                        <div class="capture-program-card__broadcaster-container">
                            <div class="capture-program-card__broadcaster-name">{{ program.channel?.name ?? 'チャンネル情報なし' }}</div>
                            <div class="capture-program-card__broadcaster-time">{{ formatBroadcast(program.start_time, program.end_time) }}</div>
                        </div>
                    </div>
                </div>
            </router-link>
        </div>
        <!-- 番組が0件の間は、読み込み中や空の状態の表示が上下中央に配置されるよう、無限スクロールの監視用の要素の余白をなくす -->
        <div ref="sentinelRef" class="capture-programs__sentinel" :class="{'capture-programs__sentinel--empty': programs.length === 0}">
            <!-- 2ページ目以降の読み込み中のみ、一覧の下端にスピナーを表示する -->
            <Icon v-if="isLoading && programs.length > 0" icon="line-md:loading-twotone-loop" width="28px" />
            <!-- 2ページ目以降を読み込めなかったときは、一覧の下端に読み込めなかったことと再読み込みのボタンを表示する -->
            <div v-else-if="isMoreLoadFailed" class="capture-programs__more-failed">
                <div>続きの番組を読み込めませんでした。</div>
                <v-btn class="mt-3 px-4" color="secondary" variant="flat" height="40" @click="retryLoadMore">
                    <Icon icon="fluent:arrow-clockwise-16-filled" width="18px" height="18px" />
                    <span class="ml-1">再読み込み</span>
                </v-btn>
            </div>
        </div>
    </CapturePage>
</template>
<script lang="ts" setup>

import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import CaptureHeader from '@/components/Captures/CaptureHeader.vue';
import CapturePage from '@/components/Captures/CapturePage.vue';
import Captures, { CaptureProgramSortOrder, ICaptureProgramAlbum } from '@/services/Captures';
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
// 2ページ目以降を読み込めなかったか (最後まで読み込んだことと区別して、続きを読み直せるようにするため)
const isMoreLoadFailed = ref(false);
const recordedFilter = ref<boolean | null>(route.query.has_recorded_program === 'true' ? true : route.query.has_recorded_program === 'false' ? false : null);
// 並び順は絞り込みと同じく URL のクエリパラメータに保持し、ブラウザバックしても維持されるようにする
const order = ref<CaptureProgramSortOrder>(route.query.order === 'BroadcastAtAsc' ? 'BroadcastAtAsc' : 'BroadcastAtDesc');
let generation = 0;
// 戻る操作でこの一覧へ戻ったときの、離れたときのスクロール位置
// 続きのページは下端の目印が見えるまで読み込まないので、この位置が画面に入るところまで続けて読み込み、Vue Router が位置を戻せる高さにする
let restoringScrollTop: number | null = window.history.state?.scroll?.top ?? null;

// 次のページを読み込む (下端の目印が見えたら呼ばれる)
const loadMore = async () => {
    if (isLoading.value || isEnd.value || isLoadFailed.value || isMoreLoadFailed.value) {
        return;
    }
    isLoading.value = true;
    const myGeneration = generation;
    const result = await Captures.fetchPrograms({
        cursor: nextCursor.value,
        query: String(route.query.query ?? ''),
        has_recorded_program: recordedFilter.value,
        order: order.value,
    });
    if (myGeneration !== generation) {
        return;
    }
    isLoading.value = false;
    // 読み込めなかったときは、最後まで読み込んだ扱いにせず、読み込めなかったことを表示する
    // 自動では読み直さず、最初のページならページの再読み込み、2ページ目以降なら一覧の下端の再読み込みのボタンから読み直す
    if (result === null) {
        isLoadFailed.value = programs.value.length === 0;
        isMoreLoadFailed.value = programs.value.length > 0;
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
    isLoadFailed.value = false;
    isMoreLoadFailed.value = false;
    void loadMore();
};

// 2ページ目以降を読み込めなかったときに、一覧の下端の再読み込みのボタンから続きを読み直す
const retryLoadMore = () => {
    isMoreLoadFailed.value = false;
    void loadMore();
};

// event は入力欄で Enter キーを押したときだけ渡される
const applyQuery = (event?: KeyboardEvent) => {
    // IME で入力中の文字を確定する Enter キーでは絞り込まない
    if (event !== undefined && Utils.isIMEComposing(event)) {
        return;
    }
    const query = { ...route.query, query: queryInput.value?.trim() || undefined };
    void router.replace({ query });
};
watch(recordedFilter, (value) => {
    void router.replace({ query: { ...route.query, has_recorded_program: value === null ? undefined : String(value) } });
});
watch(order, (value) => {
    void router.replace({ query: { ...route.query, order: value === 'BroadcastAtDesc' ? undefined : value } });
});
watch(() => [route.query.query, route.query.has_recorded_program, route.query.order], () => {
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

// 終了時刻が不明な放送回は、ほかの画面の番組情報と同じく終了時刻を --:-- と表示する
// スマホの縦画面では、2列のカードに終了時刻まで収まるよう、録画番組の短い表記 (ProgramUtils.getProgramTime()) と同じく曜日を省く
const formatBroadcast = (start: string, end: string | null) => {
    const startFormat = Utils.isSmartphoneVertical() ? 'YYYY/MM/DD HH:mm' : 'YYYY/MM/DD (dd) HH:mm';
    if (end === null) {
        return Utils.apply28HourClock(`${dayjs(start).format(startFormat)} ～ --:--`);
    }
    return Utils.apply28HourClock(`${dayjs(start).format(startFormat)} ～ ${dayjs(end).format('HH:mm')}`);
};

// 局ロゴが取れないときは、ほかの画面と同じく既定のロゴに差し替える
// 既定のロゴも取れないとき (サーバーに接続できないときなど) は、同じ URL を設定し直して読み込みを繰り返すのを避けるため、そのままにする
const onLogoError = (event: Event) => {
    const image = event.target as HTMLImageElement;
    const fallbackUrl = `${Utils.api_base_url}/channels/gr001/logo`;
    if (image.src !== fallbackUrl) {
        image.src = fallbackUrl;
    }
};

</script>
<style lang="scss" scoped>

.capture-programs {
    // 検索欄と選択欄の高さは、タグの画面の検索欄 (Tags.vue) と同じ標準の高さのままにし、文字だけを録画番組の一覧の並べ替えの選択欄にそろえて小さくする
    &__toolbar {
        display: flex;
        gap: 10px;
        // 下までスクロールしてから検索や絞り込みを変えられるよう、ヘッダーの下に隠れる位置まで来たら画面の上端にくっつける
        // くっついている間も後ろの番組のカードが透けないよう背景を塗り、上下の余白も背景に含める (止まっているときの見た目は変えない)
        position: sticky;
        top: 65px;
        z-index: 5;
        margin-top: -10px;
        padding-top: 10px;
        padding-bottom: 16px;
        background: rgb(var(--v-theme-background));
        // スマホの横画面では上部のヘッダーを表示せず、縦画面では上部のバーがページと一緒にスクロールするので、どちらも画面の最上端にくっつける
        @include smartphone-horizontal {
            top: 0;
        }
        @include smartphone-vertical {
            top: 0;
        }
        // 検索欄と2つの選択欄を1行に並べられない画面幅では、1段目に検索欄を全幅で、2段目に選択欄を並べる
        @include tablet-vertical {
            flex-direction: column;
        }
        @include smartphone-horizontal {
            flex-direction: column;
            gap: 8px;
        }
        @include smartphone-vertical {
            flex-direction: column;
            gap: 8px;
        }
        :deep(.v-field__input) {
            font-size: 14px !important;
        }
        // 選択欄の文字は、選んだ値を読み取りやすいよう検索欄の文字より1段大きくする
        :deep(.v-select .v-field__input) {
            font-size: 15px !important;
        }
    }
    // 1行に並べる場合は検索欄の幅を優先して確保し、残りの幅に選択欄を並べる
    &__search {
        flex: 0 1 420px;
        min-width: 0;
        @include tablet-vertical {
            flex: none;
        }
        @include smartphone-horizontal {
            flex: none;
        }
        @include smartphone-vertical {
            flex: none;
        }
    }
    &__selects {
        display: flex;
        flex: 1 1 auto;
        gap: 10px;
        min-width: 0;
        @include smartphone-horizontal {
            gap: 8px;
        }
        @include smartphone-vertical {
            gap: 8px;
        }
    }
    // 絞り込みと並べ替えの選択欄は同じ幅に揃える (2段目に並べる場合は、それぞれ半分ずつの幅に広げる)
    &__select {
        flex: 0 0 196px;
        @include tablet-vertical {
            flex: 1 1 0;
            min-width: 0;
        }
        @include smartphone-horizontal {
            flex: 1 1 0;
            min-width: 0;
        }
        @include smartphone-vertical {
            flex: 1 1 0;
            min-width: 0;
        }
        &--order {
            margin-left: auto;
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
        &--empty {
            padding: 0;
        }
    }
    &__more-failed {
        display: flex;
        flex-direction: column;
        align-items: center;
        font-size: 14px;
        text-align: center;
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
        // 画像は枠いっぱいに重ねて切り抜き、4:3 などのキャプチャでも画像の縦横比で枠が押し広げられず 16:9 のまま表示する
        img {
            position: absolute;
            inset: 0;
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
        color: rgb(var(--v-theme-text));
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
        color: rgb(var(--v-theme-text));
        font-size: 12px;
        line-height: 20px;
    }
    // 同じ行のカードは高さがそろうので、番組名の下を伸ばして局名と放送時間を下端に置く
    &__meta {
        display: flex;
        flex-direction: column;
        flex: 1;
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
    &__broadcaster {
        display: flex;
        align-items: center;
        min-width: 0;
        margin-top: auto;
        padding-top: 8px;
        color: rgb(var(--v-theme-text-darken-1));
        // 局ロゴは番組の情報欄 (CaptureProgramInfo.vue) と同じ縦横比にする
        &-icon {
            flex-shrink: 0;
            width: 36px;
            height: 29.5px;
            margin-right: 10px;
            border-radius: 3px;
            background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
            object-fit: cover;
            user-select: none;
            // スマホの縦画面では、2列のカードに放送時間が収まるよう局ロゴを出さない
            @include smartphone-vertical {
                display: none;
            }
        }
        &-container {
            display: flex;
            flex-direction: column;
            min-width: 0;
        }
        &-name, &-time {
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
        &-name {
            font-size: 13px;
            @include smartphone-vertical {
                font-size: 11.5px;
            }
        }
        &-time {
            margin-top: 1px;
            font-size: 12.5px;
            @include smartphone-vertical {
                font-size: 11px;
            }
        }
    }
}

</style>
