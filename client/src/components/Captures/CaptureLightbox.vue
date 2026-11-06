<template>
    <Teleport to="body">
        <!-- 暗幕・ボタン・情報欄はフェードで開閉し、画像だけはタイルとの間を拡大・縮小していく (CaptureTransition.ts を参照) -->
        <transition name="capture-lightbox-fade">
            <div v-if="capture !== null" ref="rootRef" class="capture-lightbox" tabindex="-1"
                :class="{
                    'capture-lightbox--portrait': isPortrait,
                    'capture-lightbox--info': isInfoOpen,
                    'capture-lightbox--control': isControlVisible,
                }"
                :style="{ background: `rgba(0, 0, 0, ${backdropOpacity})` }"
                @mousemove="showControl">
                <div class="capture-lightbox__main">
                    <!-- 上のバー: 閉じる・お気に入り・タグ・ダウンロード・情報・削除 -->
                    <div class="capture-lightbox__bar" :style="{ opacity: backdropOpacity }">
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="'閉じる (Esc)'" @click="close">
                            <Icon icon="fluent:arrow-left-24-regular" width="24px" />
                        </div>
                        <v-spacer></v-spacer>
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="capture.is_favorite ? 'お気に入りから外す (F)' : 'お気に入りに追加 (F)'"
                            @click="toggleFavorite">
                            <Icon :icon="capture.is_favorite ? 'fluent:heart-24-filled' : 'fluent:heart-24-regular'" width="24px"
                                :class="{'text-primary': capture.is_favorite}" />
                        </div>
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="'タグを付ける (T)'" @click="openTagDialog">
                            <Icon icon="fluent:tag-24-regular" width="24px" />
                        </div>
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="'ダウンロード (D)'" @click="download">
                            <Icon icon="fluent:arrow-download-24-regular" width="24px" />
                        </div>
                        <!-- 拡大 (拡大している間にもう一度押すと元の大きさに戻す) -->
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="isZoomed ? '元の大きさに戻す' : '拡大'" @click="toggleZoom">
                            <Icon :icon="isZoomed ? 'fluent:zoom-out-24-regular' : 'fluent:zoom-in-24-regular'" width="24px" />
                        </div>
                        <!-- 情報 (横画面では右のパネル、縦画面では下のシート) の開閉 (開いている間はアイコンを塗りつぶしにする) -->
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="isInfoOpen ? '情報を閉じる (I)' : '情報を開く (I)'"
                            @click="setInfoOpen(!isInfoOpen)">
                            <Icon :icon="isInfoOpen ? 'fluent:info-24-filled' : 'fluent:info-24-regular'" width="24px" />
                        </div>
                        <!-- その他の操作 (録画番組のメニューと同じく、取り消せない削除は区切り線の下に赤で置き、押し間違えにくくする) -->
                        <v-menu v-if="canSetThumbnail" v-model="isMenuOpen" location="bottom end" :z-index="2400">
                            <template #activator="{ props: menuProps }">
                                <div v-ripple class="capture-lightbox__button" v-bind="menuProps">
                                    <Icon icon="fluent:more-vertical-24-filled" width="24px" />
                                </div>
                            </template>
                            <v-list density="compact" bg-color="background-lighten-1">
                                <v-list-item @click="setAsThumbnail">
                                    <template #prepend>
                                        <Icon icon="fluent:image-20-regular" width="20px" height="20px" />
                                    </template>
                                    <v-list-item-title class="ml-3">録画番組のサムネイルにする</v-list-item-title>
                                </v-list-item>
                                <v-divider></v-divider>
                                <v-list-item class="capture-lightbox__menu-item--danger" @click="requestDelete">
                                    <template #prepend>
                                        <Icon icon="fluent:delete-20-regular" width="20px" height="20px" />
                                    </template>
                                    <v-list-item-title class="ml-3">キャプチャを削除</v-list-item-title>
                                </v-list-item>
                            </v-list>
                        </v-menu>
                        <!-- 録画のないキャプチャでは削除のほかに項目がないので、選択中のバーと同じく、確認のダイアログを開く削除のボタンを右端に赤で置く -->
                        <div v-else v-ripple class="capture-lightbox__button capture-lightbox__button--danger" v-ftooltip.bottom="'キャプチャを削除 (Delete)'"
                            @click="requestDelete">
                            <Icon icon="fluent:delete-24-regular" width="24px" />
                        </div>
                    </div>

                    <!-- 画像: 前・今・次の3枚を横に並べ、指の動きに合わせて全体をずらす -->
                    <div ref="stageRef" class="capture-lightbox__stage" :style="stageStyle"
                        @click.self="onStageClick"
                        @touchstart="onStageTouchStart" @touchmove="onStageTouchMove"
                        @touchend="onStageTouchEnd" @touchcancel="onStageTouchEnd"
                        @wheel="onStageWheel" @gesturestart="onStageGestureStart" @gesturechange="onStageGestureChange"
                        @gestureend="onStageGestureEnd">
                        <div class="capture-lightbox__track" :style="trackStyle" @click.self="onStageClick">
                            <div v-for="slide in slides" :key="slide.key" class="capture-lightbox__slide"
                                :style="{ left: `calc(${slide.offset * 100}% + ${slide.offset * SLIDE_GAP}px)` }"
                                @click.self="onStageClick">
                                <img v-if="slide.capture !== null" class="capture-lightbox__image" :src="Captures.getImageURL(slide.capture)"
                                    :class="{'capture-lightbox__image--current': slide.offset === 0}" decoding="async"
                                    :style="[getImageSizeStyle(slide.capture), slide.offset === 0 ? zoomStyle : {}]"
                                    :alt="slide.capture.caption_text ?? ''" draggable="false"
                                    @pointerdown="onImagePointerDown" @pointermove="onImagePointerMove"
                                    @pointerup="onImagePointerUp" @pointercancel="onImagePointerUp">
                            </div>
                        </div>
                        <div v-ripple class="capture-lightbox__nav capture-lightbox__nav--prev"
                            :class="{'capture-lightbox__nav--hidden': prevCapture === null}" @click.stop="move(-1)">
                            <Icon icon="fluent:chevron-left-24-regular" width="32px" />
                        </div>
                        <div v-ripple class="capture-lightbox__nav capture-lightbox__nav--next"
                            :class="{'capture-lightbox__nav--hidden': nextCapture === null}" @click.stop="move(1)">
                            <Icon icon="fluent:chevron-right-24-regular" width="32px" />
                        </div>
                    </div>

                    <!-- 拡大している間は、画像のどこを表示しているかを示す縮小図と、拡大率のスライダーを出す (マウスを動かしている間だけ出す) -->
                    <div v-if="isZoomed" class="capture-lightbox__zoom">
                        <div class="capture-lightbox__zoom-map"
                            @pointerdown="onZoomMapPointerDown" @pointermove="onZoomMapPointerMove"
                            @pointerup="onZoomMapPointerUp" @pointercancel="onZoomMapPointerUp">
                            <img class="capture-lightbox__zoom-image" :src="Captures.getImageURL(capture)" alt="" draggable="false">
                            <div class="capture-lightbox__zoom-view" :style="zoomViewStyle"></div>
                        </div>
                        <div class="capture-lightbox__zoom-slider">
                            <div v-ripple class="capture-lightbox__zoom-step" @click="setZoom(zoom - ZOOM_STEP)">
                                <Icon icon="fluent:subtract-16-filled" width="18px" />
                            </div>
                            <v-slider :model-value="zoom" :min="MIN_ZOOM" :max="MAX_ZOOM" :step="0.1" color="primary" track-color="text-darken-2"
                                thumb-size="14" hide-details class="mx-1" @update:model-value="setZoom" />
                            <div v-ripple class="capture-lightbox__zoom-step" @click="setZoom(zoom + ZOOM_STEP)">
                                <Icon icon="fluent:add-16-filled" width="18px" />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 情報: 横画面では右からせり出すパネル、縦画面では下から出るシート -->
                <aside class="capture-lightbox__info" :style="infoStyle"
                    @touchstart="onSheetTouchStart" @touchmove="onSheetTouchMove"
                    @touchend="onSheetTouchEnd" @touchcancel="onSheetTouchEnd">
                    <div v-if="isPortrait" class="capture-lightbox__sheet-handle" @click="setInfoOpen(false)"></div>
                    <!-- 横画面のパネルは、視聴画面のパネルと同じ「閉じる」ボタンでも閉じられるようにする -->
                    <div v-else class="capture-lightbox__info-header">
                        <div v-ripple class="capture-lightbox__info-close" @click="setInfoOpen(false)">
                            <Icon icon="akar-icons:chevron-right" width="25px" />
                            <span>閉じる</span>
                        </div>
                    </div>
                    <div ref="infoScrollRef" class="capture-lightbox__info-scroll">
                        <CaptureInfo :capture="capture" :detail="detail" :program="program" :tag-names="tagNames"
                            @open-program="openProgram" @play="playRecording" />
                    </div>
                </aside>

                <CaptureTagDialog v-model:show="isTagDialogOpen" :captures="[capture]" @updated="onTagsUpdated" />
                <!-- キーボードだけでも続けて削除できるよう、確認のダイアログを開いたら削除のボタンにフォーカスを当て、Enter キーで確定できるようにする -->
                <!-- Tab キーでキャンセルのボタンへ移ってから Enter キーを押すと、キャンセルになる -->
                <v-dialog max-width="520" :model-value="isDeleteConfirmOpen" @update:model-value="isDeleteConfirmOpen = $event"
                    @after-enter="deleteButtonRef?.$el.focus()">
                    <v-card>
                        <v-card-title class="d-flex justify-center pt-6 font-weight-bold">このキャプチャを削除しますか？</v-card-title>
                        <v-card-text class="pt-2 pb-0">
                            <div class="text-error-lighten-1 font-weight-bold">
                                保存先にある画像ファイルも削除され、元に戻すことはできません。<br>
                                同じ画像が他のフォルダにもある場合は、それらも一緒に削除されます。
                            </div>
                        </v-card-text>
                        <v-card-actions class="pt-4 px-6 pb-6">
                            <v-spacer></v-spacer>
                            <v-btn color="text" variant="text" height="40" @click="isDeleteConfirmOpen = false">
                                <Icon icon="fluent:dismiss-16-filled" width="18px" height="18px" />
                                <span class="ml-1">キャンセル</span>
                            </v-btn>
                            <v-btn ref="deleteButtonRef" color="error" variant="flat" height="40" class="px-3" :loading="isDeleting" @click="deleteCapture">
                                <Icon icon="fluent:delete-16-regular" width="18px" height="18px" />
                                <span class="ml-1">キャプチャを削除</span>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-dialog>
            </div>
        </transition>
    </Teleport>
</template>
<script lang="ts">

// 情報パネル (シート) を開いているか
// 既定では開いておき、閉じたら別のキャプチャや別の一覧で開いても閉じたままにする (このタブを開いている間だけ覚える)
let isInfoOpenRemembered = true;

</script>
<script lang="ts" setup>

import { ComponentPublicInstance, computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import CaptureInfo from '@/components/Captures/CaptureInfo.vue';
import CaptureTagDialog from '@/components/Captures/CaptureTagDialog.vue';
import { canAnimateCaptureImage, findTileImage, flyCaptureImage } from '@/components/Captures/CaptureTransition';
import Message from '@/message';
import Captures, { ICapture, ICaptureDetail, ICaptureProgram, ICaptureTag } from '@/services/Captures';
import Videos from '@/services/Videos';
import useUserStore from '@/stores/UserStore';
import { dayjs } from '@/utils';


const props = defineProps<{
    // 表示中のキャプチャ (null なら閉じている)
    capture: ICapture | null;
    // 一覧側が持っている番組の情報 (詳細の取得を待たずに番組名を出すため)
    programHint?: ICaptureProgram | null;
    // 前後のキャプチャを返す関数 (一覧によって前後のたどり方が違うので、一覧側から渡す)
    navigate: (capture: ICapture, delta: 1 | -1) => Promise<ICapture | null | undefined>;
    // 閉じる前に、一覧の中でそのキャプチャのタイルが見える位置までスクロールさせる関数 (一覧によってスクロールの仕方が違うので、一覧側から渡す)
    reveal?: (capture: ICapture) => Promise<void>;
}>();

const emit = defineEmits<{
    (event: 'update:capture', capture: ICapture | null): void;
    (event: 'updated', capture: ICapture): void;
    (event: 'deleted', capture_ids: number[]): void;
}>();

const router = useRouter();
const userStore = useUserStore();
const rootRef = ref<HTMLElement | null>(null);
const stageRef = ref<HTMLElement | null>(null);
const infoScrollRef = ref<HTMLElement | null>(null);

// 隣り合う画像の間の隙間 (送るときに、前後の画像の境目が分かるようにする)
const SLIDE_GAP = 24;
// 上のバーの高さ
const BAR_HEIGHT = 56;
// 位置を合わせるときのアニメーション (視聴画面のパネルと同じ動きにする)
const EASING = 'cubic-bezier(0.26, 0.68, 0.55, 0.99)';

const isTagDialogOpen = ref(false);
const isDeleteConfirmOpen = ref(false);
const isDeleting = ref(false);
// ︙ のメニューを開いているか (戻る操作でメニューだけを閉じるため)
const isMenuOpen = ref(false);
// 確認のダイアログの削除のボタン (開いたときにフォーカスを当てるため)
const deleteButtonRef = ref<ComponentPublicInstance | null>(null);
const detail = ref<ICaptureDetail | null>(null);
const tags = ref<ICaptureTag[]>([]);

const isAdmin = computed(() => userStore.user?.is_admin === true);
const program = computed(() => detail.value?.program ?? props.programHint ?? null);
const tagNames = computed(() => {
    const ids = new Set(props.capture?.tag_ids ?? []);
    return tags.value.filter(tag => ids.has(tag.id)).map(tag => tag.name);
});

// 縦画面 (スマホとタブレットの縦持ち) では情報を下のシートに、それ以外では右のパネルに出す
// 区切りは視聴画面でパネルが下に回る条件と同じにする
const portraitQuery = window.matchMedia('(max-width: 1280px) and (orientation: portrait)');
const isPortrait = ref(portraitQuery.matches);
const viewportWidth = ref(window.innerWidth);
const viewportHeight = ref(window.innerHeight);
const onViewportChange = () => {
    isPortrait.value = portraitQuery.matches;
    viewportWidth.value = window.innerWidth;
    viewportHeight.value = window.innerHeight;
};
onMounted(() => {
    portraitQuery.addEventListener('change', onViewportChange);
    window.addEventListener('resize', onViewportChange);
});
onBeforeUnmount(() => {
    portraitQuery.removeEventListener('change', onViewportChange);
    window.removeEventListener('resize', onViewportChange);
});

const isInfoOpen = ref(isInfoOpenRemembered);
const setInfoOpen = (value: boolean) => {
    isInfoOpen.value = value;
    isInfoOpenRemembered = value;
};


// ---------- 前後のキャプチャ ----------

// 前後のキャプチャ (undefined は読み込み中、null はその向きにもうない)
const prevCapture = ref<ICapture | null | undefined>(undefined);
const nextCapture = ref<ICapture | null | undefined>(undefined);

// 直前に表示していたキャプチャ (下の watch は開いた状態で作られるとすぐ実行されるので、その前に宣言しておく)
let lastShownCapture: ICapture | null = null;

// 表示するキャプチャが変わるたびに、詳細 (番組・ファイルの場所) と前後のキャプチャを取り直す
// 隣へ送ったときは、送る前の今のキャプチャがそのまま反対側の隣になるので、取り直さずに使う
watch(() => props.capture?.id, async (id, oldId) => {
    detail.value = null;
    if (id === undefined || props.capture === null) {
        prevCapture.value = undefined;
        nextCapture.value = undefined;
        return;
    }
    const current = props.capture;
    const previous = lastShownCapture;
    lastShownCapture = current;
    if (oldId !== undefined && previous !== null && nextCapture.value?.id === id) {
        prevCapture.value = previous;
        nextCapture.value = undefined;
    } else if (oldId !== undefined && previous !== null && prevCapture.value?.id === id) {
        nextCapture.value = previous;
        prevCapture.value = undefined;
    } else {
        prevCapture.value = undefined;
        nextCapture.value = undefined;
    }
    await nextTick();
    rootRef.value?.focus();
    infoScrollRef.value?.scrollTo({ top: 0 });
    void resolveNeighbors(current);
    const fetched = await Captures.fetchCapture(id);
    if (props.capture?.id === id) {
        detail.value = fetched;
    }
}, { immediate: true });

// お気に入りやタグを変えたときは、同じキャプチャの新しい内容に差し替える
watch(() => props.capture, (capture) => {
    if (capture !== null && lastShownCapture?.id === capture.id) {
        lastShownCapture = capture;
    }
});

const resolveNeighbors = async (capture: ICapture) => {
    for (const delta of [1, -1] as const) {
        const target = delta === 1 ? nextCapture : prevCapture;
        if (target.value !== undefined) {
            continue;
        }
        const neighbor = await props.navigate(capture, delta);
        // 読み込めず分からなかった隣 (undefined) は持たずにおき、送るときに読み直す
        if (props.capture?.id === capture.id && neighbor !== undefined) {
            target.value = neighbor;
        }
    }
};

// 本人のタグの名前を出すため、ログインしていればタグの一覧を持っておく
watch(() => props.capture !== null, async (isOpen) => {
    if (isOpen && userStore.is_logged_in) {
        // 読み込めなかったときは (エラーはサービス側で表示済み)、タグが付いていないように見せないよう、前に読めた一覧を使い続ける
        tags.value = (await Captures.fetchTags()) ?? tags.value;
    }
}, { immediate: true });

// 並べる3枚 (同じキャプチャの要素を使い回すよう、キャプチャの ID で区別する)
const slides = computed(() => {
    const items: { key: string; offset: number; capture: ICapture | null }[] = [];
    const entries: [number, ICapture | null | undefined][] = [[-1, prevCapture.value], [0, props.capture], [1, nextCapture.value]];
    for (const [offset, capture] of entries) {
        items.push({ key: capture ? `capture-${capture.id}` : `empty-${offset}`, offset, capture: capture ?? null });
    }
    return items;
});


// 画像の表示の大きさは、読み込みを待たずにキャプチャの縦横の大きさから決める
// 読み込む前の画像は大きさを持たず、開くときにタイルの画像が拡大していく先の位置と大きさを決められないため
const getImageSizeStyle = (capture: ICapture) => ({
    width: `min(100cqw, calc(100cqh * ${capture.image_width} / ${capture.image_height}))`,
    aspectRatio: `${capture.image_width} / ${capture.image_height}`,
});


// ---------- 送りと閉じるの動き ----------

// 横のずれ (指で引いている量か、送るアニメーションの行き先)
const dragX = ref(0);
// 下へ引いて閉じるときの縦のずれ
const dismissY = ref(0);
// 指に追従している間と、送った直後に位置を戻す瞬間は、アニメーションを止める
const isFollowingFinger = ref(false);
const isSnapping = ref(false);
const isSliding = ref(false);

const trackStyle = computed(() => ({
    transform: `translate3d(${dragX.value}px, ${dismissY.value}px, 0)`,
    transition: isFollowingFinger.value || isSnapping.value ? 'none' : `transform 0.3s ${EASING}`,
}));
const backdropOpacity = computed(() => Math.max(0, 1 - Math.abs(dismissY.value) / 500));

// 閉じるときは、開くときの逆に、1枚表示の画像が一覧のタイルの位置まで縮んでいくように見せる
// 一覧のタイルを先に画面に見える位置までスクロールさせてから、画像の複製を1枚だけタイルの位置まで動かし、暗幕・ボタン・情報欄は同時にフェードアウトさせる
let isClosing = false;
const close = async () => {
    const current = props.capture;
    if (current === null || isClosing) {
        return;
    }
    // 動きを減らす設定のときは、フェードだけで閉じる
    if (canAnimateCaptureImage() === false) {
        emit('update:capture', null);
        return;
    }
    isClosing = true;
    // 拡大したまま閉じると、拡大した画像からタイルへ縮んでいくように見えるので、先に元の大きさへ戻す
    if (isZoomed.value) {
        resetZoom(true);
        await nextTick();
    }
    await props.reveal?.(current);

    // 戻る先のタイルが画面に見えているときだけ、画像をタイルの位置まで縮めていく (見えていなければフェードだけで閉じる)
    const image = rootRef.value?.querySelector<HTMLImageElement>('.capture-lightbox__image--current') ?? null;
    const tileImage = findTileImage(current.id);
    const tileRect = tileImage?.getBoundingClientRect();
    let flight: ReturnType<typeof flyCaptureImage> | null = null;
    if (image !== null && tileImage !== null && tileRect !== undefined && tileRect.bottom > 0 && tileRect.top < window.innerHeight) {
        flight = flyCaptureImage(image.currentSrc || image.src, image.getBoundingClientRect(), tileRect);
        // 縮んでいく間は、フェードアウトしていく拡大表示の画像とタイルの画像を隠し、複製の1枚だけを見せる
        // 選択の枠・チェック・アイコンは画像の上に重なるので、縮み終わってから表示する (CaptureTile.vue の capture-tile--landing)
        image.style.visibility = 'hidden';
        tileImage.style.visibility = 'hidden';
        tileImage.closest('.capture-tile')?.classList.add('capture-tile--landing');
    }
    emit('update:capture', null);
    if (flight !== null && tileImage !== null) {
        await flight.finished;
        tileImage.style.removeProperty('visibility');
        tileImage.closest('.capture-tile')?.classList.remove('capture-tile--landing');
        flight.element.remove();
    }
    isClosing = false;
};

// 前後へ送る (矢印キー・矢印ボタン・スワイプで共通)
// 隣の画像を今の位置まで滑らせてから、表示中のキャプチャを差し替える
// 送るアニメーションの途中でもう一度押されたら、途中の送りをすぐに完了させてから、続けて次へ送る
// 連打されたときも押した回数だけ順に送れるよう、送り始めるまでの処理は1回ずつ順番に行う
let moveQueue: Promise<void> = Promise.resolve();
// 送るアニメーションの途中のときに、その送りをすぐに完了させる関数
let finishSlide: (() => Promise<void>) | null = null;
const move = (delta: 1 | -1) => {
    moveQueue = moveQueue.then(() => startSlide(delta));
    return moveQueue;
};
const startSlide = async (delta: 1 | -1) => {
    if (props.capture === null) {
        return;
    }
    if (finishSlide !== null) {
        await finishSlide();
    }
    if (props.capture === null) {
        return;
    }
    // 送り始めたときのキャプチャ (待っている間に閉じたり別のキャプチャを開いたりしたら、送るのをやめるため)
    const current = props.capture;
    const target = delta === 1 ? nextCapture : prevCapture;
    if (target.value === undefined) {
        const fetched = await props.navigate(current, delta);
        // 隣を取得している間に閉じたり別のキャプチャを開いたりしたら、今の表示の隣として持たずに、位置だけを戻して送るのをやめる
        if (props.capture?.id !== current.id) {
            isFollowingFinger.value = false;
            dragX.value = 0;
            return;
        }
        target.value = fetched;
    }
    const neighbor = target.value;
    if (neighbor === null || neighbor === undefined) {
        // もう隣がないときは、元の位置へ戻す
        isFollowingFinger.value = false;
        dragX.value = 0;
        return;
    }
    isSliding.value = true;
    isFollowingFinger.value = false;
    const width = stageRef.value?.clientWidth ?? window.innerWidth;
    dragX.value = -delta * (width + SLIDE_GAP);

    // アニメーションが終わったとき (途中でもう一度押されたときはその時点) に、表示中のキャプチャを隣へ差し替える
    let isFinished = false;
    const finish = async () => {
        if (isFinished) {
            return;
        }
        isFinished = true;
        finishSlide = null;
        // 滑らせている間に閉じたり別のキャプチャを開いたりしたら、隣へ差し替えずに位置だけを戻して終える
        if (props.capture?.id !== current.id) {
            isSliding.value = false;
            dragX.value = 0;
            return;
        }
        // 差し替えと同時に位置を戻す (隣の画像がそのまま中央の枠へ移るので、見た目は動かない)
        isSnapping.value = true;
        emit('update:capture', neighbor);
        dragX.value = 0;
        await nextTick();
        await new Promise(resolve => requestAnimationFrame(resolve));
        isSnapping.value = false;
        isSliding.value = false;
    };
    finishSlide = finish;
    window.setTimeout(() => void finish(), 300);
};


// ---------- 情報のシート (縦画面) ----------

// シートの閉じ具合 (0 で開いている、1 で閉じている)
// 指で引いている間は指に合わせ、離したら開くか閉じるかに寄せる
const sheetDragProgress = ref<number | null>(null);
const sheetProgress = computed(() => sheetDragProgress.value ?? (isInfoOpen.value ? 0 : 1));
// シートを開いたときの画像の枠の高さ (16:9 の画像が幅いっぱいに収まる高さ)
const openStageHeight = computed(() => Math.round(viewportWidth.value * 9 / 16) + 24);
// シートが動ける距離 (開いた位置から画面の下端まで)
const sheetRange = computed(() => Math.max(viewportHeight.value - BAR_HEIGHT - openStageHeight.value, 1));

const stageStyle = computed(() => {
    if (!isPortrait.value) {
        return {};
    }
    // シートを開くと画像の枠はバーの下の 16:9 の範囲へ、閉じると画面全体へ広がる
    const progress = sheetProgress.value;
    const top = BAR_HEIGHT * (1 - progress);
    const height = (BAR_HEIGHT + openStageHeight.value) * (1 - progress) + viewportHeight.value * progress - top;
    return {
        top: `${top}px`,
        height: `${height}px`,
        transition: sheetDragProgress.value !== null ? 'none' : `top 0.3s ${EASING}, height 0.3s ${EASING}`,
    };
});
const infoStyle = computed(() => {
    if (!isPortrait.value) {
        return {};
    }
    return {
        top: `${BAR_HEIGHT + openStageHeight.value}px`,
        transform: `translateY(${sheetProgress.value * 100}%)`,
        transition: sheetDragProgress.value !== null ? 'none' : `transform 0.3s ${EASING}`,
    };
});

// 指を離したときに、動いた量と速さからシートを開くか閉じるかを決める
const settleSheet = (velocityY: number) => {
    const progress = sheetDragProgress.value;
    sheetDragProgress.value = null;
    if (progress === null) {
        return;
    }
    if (Math.abs(velocityY) > 0.4) {
        setInfoOpen(velocityY < 0);
    } else {
        setInfoOpen(progress < 0.5);
    }
};


// ---------- タッチの操作 ----------

// 1回のタッチの記録 (動き始めた向きで、横の送り・縦のシート・下へ引いて閉じる、のどれかに決める)
interface ITouchTrack {
    startX: number;
    startY: number;
    lastY: number;
    lastTime: number;
    velocityY: number;
    startTime: number;
    axis: 'X' | 'Y' | null;
    // 縦に動かしたとき、何を動かすか
    verticalTarget: 'Sheet' | 'Dismiss' | 'Scroll' | null;
    // 拡大している間に触り始めたときの、表示する場所のずれ (拡大していないときは null)
    // 拡大している間の指の動きは、隣へ送るスワイプではなく表示する場所の移動として扱う
    pan: { x: number; y: number } | null;
}
let touch: ITouchTrack | null = null;
// 指で触った直後のクリックで閉じないよう、タッチの操作中であることを覚える
let lastTouchTime = 0;
// 動いたとみなすまでの距離
const AXIS_LOCK_DISTANCE = 8;

const beginTouch = (event: TouchEvent): ITouchTrack => {
    const point = event.touches[0];
    lastTouchTime = Date.now();
    return {
        startX: point.clientX, startY: point.clientY, lastY: point.clientY,
        lastTime: event.timeStamp, velocityY: 0, startTime: event.timeStamp,
        axis: null, verticalTarget: null,
        pan: isZoomed.value ? { x: panX.value, y: panY.value } : null,
    };
};

// 2本の指でのピンチの記録 (前回の指の間の距離と、2本の指の中点)
// 写真アプリと同じく、2本の指の間隔に合わせて拡大・縮小し、中点の動きに合わせて表示する場所をずらす
interface IPinchTrack {
    distance: number;
    centerX: number;
    centerY: number;
}
let pinch: IPinchTrack | null = null;
// 画像を表示する領域に触れている指の数 (指で触れている間のピンチを、Safari のジェスチャーのイベントではなく Touch イベントで扱うため)
let stageTouchCount = 0;
const measurePinch = (event: TouchEvent): IPinchTrack => {
    const [first, second] = [event.touches[0], event.touches[1]];
    return {
        distance: Math.max(Math.hypot(second.clientX - first.clientX, second.clientY - first.clientY), 1),
        centerX: (first.clientX + second.clientX) / 2,
        centerY: (first.clientY + second.clientY) / 2,
    };
};

// 2本目の指が置かれたときに、1本指で始めた操作 (横の送り・縦のシート・下へ引いて閉じる・拡大中の移動) をやめて、画像とシートを元の位置へ戻す
const cancelOneFingerDrag = () => {
    touch = null;
    isFollowingFinger.value = false;
    isZoomFollowing.value = false;
    dragX.value = 0;
    dismissY.value = 0;
    sheetDragProgress.value = null;
};

// 直前のタップの時刻と位置 (写真アプリと同じく、同じ場所を素早く2回タップしたら拡大・縮小する)
let lastTap: { time: number; x: number; y: number } | null = null;
const DOUBLE_TAP_INTERVAL = 300;
const DOUBLE_TAP_DISTANCE = 30;
const trackVelocity = (track: ITouchTrack, event: TouchEvent) => {
    const y = event.touches[0].clientY;
    const elapsed = Math.max(event.timeStamp - track.lastTime, 1);
    track.velocityY = (y - track.lastY) / elapsed;
    track.lastY = y;
    track.lastTime = event.timeStamp;
};

const onStageTouchStart = (event: TouchEvent) => {
    stageTouchCount = event.touches.length;
    // 2本目の指が置かれたら、1本指の操作をやめて元の位置へ戻し、ピンチでの拡大・縮小を始める
    // 隣へ送っている途中は、送った後に拡大率が元に戻るので、ピンチを始めない
    if (event.touches.length >= 2) {
        cancelOneFingerDrag();
        lastTap = null;
        if (event.touches.length === 2 && !isSliding.value) {
            pinch = measurePinch(event);
            // 指の動きに合わせて細かく拡大率が変わるので、ピンチしている間はアニメーションを止める
            isZoomFollowing.value = true;
            lastTouchTime = Date.now();
        } else {
            pinch = null;
            isZoomFollowing.value = false;
        }
        return;
    }
    if (event.touches.length !== 1 || isSliding.value) {
        touch = null;
        return;
    }
    touch = beginTouch(event);
    // 拡大している間は、指に合わせて表示する場所をずらすので、アニメーションを止める
    if (touch.pan !== null) {
        isZoomFollowing.value = true;
    }
    showControl();
};
const onStageTouchMove = (event: TouchEvent) => {
    // ピンチしている間は、2本の指の間隔の変化に合わせて、中点を中心に拡大・縮小し、中点の動きに合わせて表示する場所をずらす
    if (pinch !== null) {
        if (event.touches.length !== 2) {
            return;
        }
        event.preventDefault();
        const next = measurePinch(event);
        setZoom(zoom.value * next.distance / pinch.distance, { clientX: next.centerX, clientY: next.centerY });
        setPan(panX.value + next.centerX - pinch.centerX, panY.value + next.centerY - pinch.centerY);
        pinch = next;
        return;
    }
    if (touch === null || event.touches.length !== 1) {
        return;
    }
    const dx = event.touches[0].clientX - touch.startX;
    const dy = event.touches[0].clientY - touch.startY;
    trackVelocity(touch, event);
    if (touch.axis === null) {
        if (Math.hypot(dx, dy) < AXIS_LOCK_DISTANCE) {
            return;
        }
        touch.axis = Math.abs(dx) > Math.abs(dy) ? 'X' : 'Y';
        if (touch.axis === 'Y' && touch.pan === null) {
            // 縦画面では上下でシートを開閉し、シートを閉じているときに下へ引いたら1枚表示を閉じる (写真アプリと同じ)
            const isOpeningOrClosingSheet = isPortrait.value && (isInfoOpen.value || dy < 0);
            touch.verticalTarget = isOpeningOrClosingSheet ? 'Sheet' : 'Dismiss';
        }
    }
    event.preventDefault();
    // 拡大している間は、送りやシートの操作ではなく、拡大した画像の表示する場所を指に合わせてずらす
    if (touch.pan !== null) {
        setPan(touch.pan.x + dx, touch.pan.y + dy);
        showControl();
        return;
    }
    isFollowingFinger.value = true;
    if (touch.axis === 'X') {
        followHorizontal(dx);
    } else if (touch.verticalTarget === 'Sheet') {
        const base = isInfoOpen.value ? 0 : 1;
        sheetDragProgress.value = Math.min(Math.max(base + dy / sheetRange.value, 0), 1);
    } else if (touch.verticalTarget === 'Dismiss') {
        dismissY.value = Math.max(dy, 0);
    }
};
const onStageTouchEnd = (event: TouchEvent) => {
    stageTouchCount = event.touches.length;
    // ピンチの途中で指を離したときは、ピンチを終える
    // 拡大したまま1本の指が残っていれば、写真アプリと同じく、残った指でそのまま表示する場所をずらせるようにする
    if (pinch !== null) {
        if (event.touches.length >= 2) {
            return;
        }
        pinch = null;
        lastTouchTime = Date.now();
        isZoomFollowing.value = false;
        if (event.touches.length === 1 && isZoomed.value) {
            touch = beginTouch(event);
            isZoomFollowing.value = true;
        }
        return;
    }
    if (touch === null) {
        return;
    }
    const track = touch;
    touch = null;
    lastTouchTime = Date.now();
    isFollowingFinger.value = false;
    if (track.pan !== null) {
        isZoomFollowing.value = false;
    } else if (track.axis === 'X') {
        finishHorizontal(event, track);
    } else if (track.verticalTarget === 'Sheet') {
        settleSheet(track.velocityY);
    } else if (track.verticalTarget === 'Dismiss') {
        // 十分に下へ引いたか、素早く払ったら閉じる
        if (dismissY.value > 120 || track.velocityY > 0.5) {
            void close();
        }
        dismissY.value = 0;
    }

    // 動かさずに離したタッチ (タップ) が、直前のタップと同じ場所で素早く続いたら、ダブルタップとして拡大・縮小する
    // 長く押してから離したときは、タップとして扱わない
    const isTap = track.axis === null && event.timeStamp - track.startTime < DOUBLE_TAP_INTERVAL;
    if (isTap === false) {
        lastTap = null;
        return;
    }
    const point = event.changedTouches[0];
    let isDoubleTap = false;
    if (lastTap !== null) {
        const isQuick = event.timeStamp - lastTap.time < DOUBLE_TAP_INTERVAL;
        const isNear = Math.hypot(point.clientX - lastTap.x, point.clientY - lastTap.y) < DOUBLE_TAP_DISTANCE;
        isDoubleTap = isQuick && isNear;
    }
    if (isDoubleTap === false) {
        lastTap = { time: event.timeStamp, x: point.clientX, y: point.clientY };
        return;
    }
    // 拡大していれば元の大きさに戻し、拡大していなければタップした場所を中心に拡大する
    lastTap = null;
    if (isZoomed.value) {
        resetZoom();
    } else {
        setZoom(DEFAULT_ZOOM, point);
    }
};

// 横に引いている間は、画像の並び全体を指に合わせてずらす
const followHorizontal = (dx: number) => {
    // もう隣がない向きへは、重く引っ張られるようにする
    const hasNeighbor = dx < 0 ? nextCapture.value !== null : prevCapture.value !== null;
    dragX.value = hasNeighbor ? dx : dx * 0.25;
};
// 横に引いて離したときに、前後へ送るか元に戻すかを決める
const finishHorizontal = (event: TouchEvent, track: ITouchTrack) => {
    const dx = event.changedTouches[0].clientX - track.startX;
    const elapsed = Math.max(event.timeStamp - track.startTime, 1);
    const width = stageRef.value?.clientWidth ?? window.innerWidth;
    // 幅の2割以上引いたか、素早く払ったら送る
    if (Math.abs(dx) > width * 0.2 || (Math.abs(dx) > 30 && Math.abs(dx) / elapsed > 0.5)) {
        void move(dx < 0 ? 1 : -1);
    } else {
        dragX.value = 0;
    }
};

// シートの上でのタッチ (写真アプリと同じく、シートの上でも横に引けば前後へ送る)
// 縦に引いたときは中身をスクロールし、中身が一番上までスクロールされているときに下へ引くとシートを閉じる
const onSheetTouchStart = (event: TouchEvent) => {
    // 画像の上で1本指の操作をしている途中に、2本目の指がシートに置かれたときも、1本指の操作をやめて元の位置へ戻す
    if (event.touches.length >= 2) {
        cancelOneFingerDrag();
        return;
    }
    if (!isPortrait.value || event.touches.length !== 1 || isSliding.value) {
        touch = null;
        return;
    }
    touch = beginTouch(event);
};
const onSheetTouchMove = (event: TouchEvent) => {
    if (touch === null || !isPortrait.value) {
        return;
    }
    const dx = event.touches[0].clientX - touch.startX;
    const dy = event.touches[0].clientY - touch.startY;
    trackVelocity(touch, event);
    if (touch.axis === null) {
        if (Math.hypot(dx, dy) < AXIS_LOCK_DISTANCE) {
            return;
        }
        touch.axis = Math.abs(dx) > Math.abs(dy) ? 'X' : 'Y';
        const isAtTop = (infoScrollRef.value?.scrollTop ?? 0) <= 0;
        if (touch.axis === 'Y') {
            touch.verticalTarget = dy > 0 && isAtTop ? 'Sheet' : 'Scroll';
        }
    }
    if (touch.axis === 'X') {
        event.preventDefault();
        isFollowingFinger.value = true;
        followHorizontal(dx);
        return;
    }
    if (touch.verticalTarget !== 'Sheet') {
        return;
    }
    event.preventDefault();
    sheetDragProgress.value = Math.min(Math.max(dy / sheetRange.value, 0), 1);
};
const onSheetTouchEnd = (event: TouchEvent) => {
    if (touch === null) {
        return;
    }
    const track = touch;
    touch = null;
    lastTouchTime = Date.now();
    isFollowingFinger.value = false;
    if (track.axis === 'X') {
        finishHorizontal(event, track);
    } else if (track.verticalTarget === 'Sheet') {
        settleSheet(track.velocityY);
    }
};

// 画像の外の黒い部分をマウスでクリックしたら閉じる (指で触ったときは、送りやシートの操作と紛れるので閉じない)
const onStageClick = () => {
    if (Date.now() - lastTouchTime < 800) {
        return;
    }
    void close();
};


// ---------- 拡大 ----------

// 拡大率は、拡大していないときの表示の大きさを 1 とした倍率で持つ (拡大のボタンを押すと 2 倍にする)
const MIN_ZOOM = 1;
const MAX_ZOOM = 4;
const DEFAULT_ZOOM = 2;
const ZOOM_STEP = 0.5;
const zoom = ref(MIN_ZOOM);
// 拡大した画像の中心を、表示する領域の中心からずらしている量 (px)
const panX = ref(0);
const panY = ref(0);
// ドラッグに追従している間と、閉じる前に元の大きさへ戻す瞬間は、アニメーションを止める
const isZoomFollowing = ref(false);
const isZoomed = computed(() => zoom.value > MIN_ZOOM);

// 拡大していないときの画像の表示の大きさと、画像を表示する領域の大きさ (拡大率を変えたときと、ずらしたときに取り直す)
const zoomBox = ref({ imageWidth: 0, imageHeight: 0, stageWidth: 0, stageHeight: 0 });
const measureZoomBox = () => {
    const image = stageRef.value?.querySelector<HTMLImageElement>('.capture-lightbox__image--current');
    if (image === undefined || image === null || stageRef.value === null) {
        return;
    }
    // offsetWidth と offsetHeight は transform の拡大を含まない、元の表示の大きさを返す
    zoomBox.value = {
        imageWidth: image.offsetWidth,
        imageHeight: image.offsetHeight,
        stageWidth: stageRef.value.clientWidth,
        stageHeight: stageRef.value.clientHeight,
    };
};

// 拡大した画像の端が、表示する領域の内側に入り込まないところまでだけずらせるようにする
const setPan = (x: number, y: number) => {
    const box = zoomBox.value;
    const maxX = Math.max(0, (box.imageWidth * zoom.value - box.stageWidth) / 2);
    const maxY = Math.max(0, (box.imageHeight * zoom.value - box.stageHeight) / 2);
    panX.value = Math.min(Math.max(x, -maxX), maxX);
    panY.value = Math.min(Math.max(y, -maxY), maxY);
};

// 拡大率を変えても、表示している場所の中心が変わらないようにする
// トラックパッドのピンチでは、指の間にある場所 (マウスカーソルの位置) が動かないように拡大する
const setZoom = (value: number, focus: { clientX: number; clientY: number } | null = null) => {
    measureZoomBox();
    const next = Math.min(Math.max(value, MIN_ZOOM), MAX_ZOOM);
    const ratio = next / zoom.value;
    // 拡大の中心にする位置の、表示する領域の中心からのずれ (指定がなければ領域の中心)
    let focusX = 0;
    let focusY = 0;
    if (focus !== null && stageRef.value !== null) {
        const rect = stageRef.value.getBoundingClientRect();
        focusX = focus.clientX - (rect.left + rect.width / 2);
        focusY = focus.clientY - (rect.top + rect.height / 2);
    }
    zoom.value = next;
    setPan(focusX - (focusX - panX.value) * ratio, focusY - (focusY - panY.value) * ratio);
    showControl();
};
const resetZoom = (instant = false) => {
    isZoomFollowing.value = instant;
    zoom.value = MIN_ZOOM;
    panX.value = 0;
    panY.value = 0;
    // アニメーションなしで戻したときは、戻した位置が描画されてから、次に拡大するときのアニメーションを戻す
    if (instant) {
        window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
            isZoomFollowing.value = false;
        }));
    }
};
const toggleZoom = () => {
    if (isZoomed.value) {
        resetZoom();
    } else {
        setZoom(DEFAULT_ZOOM);
    }
};

// 隣のキャプチャへ送ったら、元の大きさに戻す
watch(() => props.capture?.id, () => resetZoom(true));

const zoomStyle = computed(() => ({
    transform: `translate3d(${panX.value}px, ${panY.value}px, 0) scale(${zoom.value})`,
    transition: isZoomFollowing.value ? 'none' : `transform 0.2s ${EASING}`,
    cursor: isZoomed.value ? (isZoomFollowing.value ? 'grabbing' : 'grab') : undefined,
}));

// 縮小図の中で、いま表示している範囲を示す枠の位置と大きさ (縮小図の大きさに対する割合)
const zoomViewStyle = computed(() => {
    const box = zoomBox.value;
    const scaledWidth = box.imageWidth * zoom.value;
    const scaledHeight = box.imageHeight * zoom.value;
    if (scaledWidth === 0 || scaledHeight === 0) {
        return {};
    }
    const width = Math.min(1, box.stageWidth / scaledWidth);
    const height = Math.min(1, box.stageHeight / scaledHeight);
    const centerX = 0.5 - panX.value / scaledWidth;
    const centerY = 0.5 - panY.value / scaledHeight;
    return {
        left: `${(centerX - width / 2) * 100}%`,
        top: `${(centerY - height / 2) * 100}%`,
        width: `${width * 100}%`,
        height: `${height * 100}%`,
    };
});

// 拡大している間は、画像をマウスでドラッグして表示する場所をずらす
// 指での操作は、ピンチやダブルタップと一緒に Touch イベントで扱う (上のタッチの操作を参照)
let panStart: { pointerId: number; x: number; y: number; panX: number; panY: number } | null = null;
const onImagePointerDown = (event: PointerEvent) => {
    if (!isZoomed.value || event.pointerType === 'touch') {
        return;
    }
    event.preventDefault();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    measureZoomBox();
    panStart = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: panX.value, panY: panY.value };
    isZoomFollowing.value = true;
};
const onImagePointerMove = (event: PointerEvent) => {
    if (panStart === null || panStart.pointerId !== event.pointerId) {
        return;
    }
    setPan(panStart.panX + event.clientX - panStart.x, panStart.panY + event.clientY - panStart.y);
    showControl();
};
const onImagePointerUp = (event: PointerEvent) => {
    if (panStart === null || panStart.pointerId !== event.pointerId) {
        return;
    }
    panStart = null;
    isZoomFollowing.value = false;
};

// トラックパッドのピンチと Ctrl キーを押しながらのホイールで拡大・縮小する
// Chrome・Edge・Firefox はピンチを Ctrl キー付きのホイールとして、Safari は独自のジェスチャーのイベントとして送ってくる
// どちらも既定ではページ全体を拡大してしまうので、拡大表示の中では止めて画像の拡大に使う
let zoomGestureTimer: number | null = null;
const followZoomGesture = () => {
    // 指の動きに合わせて細かく拡大率が変わるので、動かしている間はアニメーションを止める
    isZoomFollowing.value = true;
    if (zoomGestureTimer !== null) {
        window.clearTimeout(zoomGestureTimer);
    }
    zoomGestureTimer = window.setTimeout(() => {
        isZoomFollowing.value = false;
    }, 150);
};
const onStageWheel = (event: WheelEvent) => {
    if (!event.ctrlKey) {
        return;
    }
    // Safari のジェスチャーのイベントで拡大している間に、同じピンチが Ctrl キー付きのホイールとしても届いたときは、二重に拡大しないよう無視する
    if (isGesturing) {
        event.preventDefault();
        return;
    }
    event.preventDefault();
    followZoomGesture();
    // ピンチは小さな量が続けて届き、マウスのホイールは1回で大きな量が届くので、1回あたりの変化に上限を設ける
    const delta = Math.min(Math.max(event.deltaY, -50), 50);
    setZoom(zoom.value * Math.exp(-delta * 0.01), event);
};
// Safari のジェスチャーのイベントは、ピンチを始めたときからの拡大率 (scale) を送ってくる
let gestureStartZoom = MIN_ZOOM;
let isGesturing = false;
// iPhone や iPad の画面を指でピンチしたときは、同じピンチが Touch イベントでも届くので、指で触れている間は Touch イベントだけで拡大・縮小し、ジェスチャーのイベントは Mac のトラックパッドのピンチに使う
// ジェスチャーのイベントは2本目の指の Touch イベントより先に届くので、1本目の指が触れた時点からの指の数で判定する
const onStageGestureStart = (event: Event) => {
    event.preventDefault();
    if (stageTouchCount > 0) {
        return;
    }
    isGesturing = true;
    gestureStartZoom = zoom.value;
};
const onStageGestureEnd = (event: Event) => {
    event.preventDefault();
    isGesturing = false;
};
const onStageGestureChange = (event: Event) => {
    event.preventDefault();
    if (isGesturing === false) {
        return;
    }
    followZoomGesture();
    const gesture = event as Event & { scale: number; clientX: number; clientY: number };
    setZoom(gestureStartZoom * gesture.scale, gesture);
};

// 縮小図を押したりドラッグしたりした位置が、表示する領域の中心に来るようにずらす
let isZoomMapDragging = false;
const moveToZoomMapPoint = (event: PointerEvent) => {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    setPan((0.5 - x) * zoomBox.value.imageWidth * zoom.value, (0.5 - y) * zoomBox.value.imageHeight * zoom.value);
};
const onZoomMapPointerDown = (event: PointerEvent) => {
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    isZoomMapDragging = true;
    isZoomFollowing.value = true;
    measureZoomBox();
    moveToZoomMapPoint(event);
};
const onZoomMapPointerMove = (event: PointerEvent) => {
    if (isZoomMapDragging) {
        moveToZoomMapPoint(event);
        showControl();
    }
};
const onZoomMapPointerUp = () => {
    isZoomMapDragging = false;
    isZoomFollowing.value = false;
};


// ---------- 操作ボタンの表示 ----------

// 矢印とパネルの開閉ボタンは、視聴画面と同じくマウスを動かしている間だけ出す
const isControlVisible = ref(true);
let controlTimer: number | null = null;
const showControl = () => {
    isControlVisible.value = true;
    if (controlTimer !== null) {
        window.clearTimeout(controlTimer);
    }
    controlTimer = window.setTimeout(() => {
        isControlVisible.value = false;
    }, 3000);
};
onMounted(showControl);
onBeforeUnmount(() => {
    if (controlTimer !== null) {
        window.clearTimeout(controlTimer);
    }
});


// ---------- お気に入り・タグ・削除・番組への移動 ----------

// お気に入りとタグはログインが必要 (家族と共用するときに、それぞれの分類が混ざらないようにするため)
const requireLogin = () => {
    if (!userStore.is_logged_in) {
        Message.warning('お気に入りとタグを使うには、KonomiTV アカウントにログインしてください。');
        return false;
    }
    return true;
};

// 隣へ送るアニメーションの途中は、表示中のキャプチャが送る前のキャプチャのままなので、そのまま操作すると見ていないキャプチャに効いてしまう
// 送っている途中に押された操作は、送りをすぐに完了させてから、送り先のキャプチャ (画面に見えているキャプチャ) を対象にする
const finishSlideBeforeAction = async () => {
    if (finishSlide !== null) {
        await finishSlide();
    }
};

const toggleFavorite = async () => {
    if (props.capture === null || !requireLogin()) {
        return;
    }
    await finishSlideBeforeAction();
    if (props.capture === null) {
        return;
    }
    // 応答を待つ間に隣のキャプチャへ送られても、お気に入りのボタンを押したキャプチャに結果を反映する
    const target = props.capture;
    const next = !target.is_favorite;
    if (await Captures.updateFavorites([target.id], next)) {
        const updated = { ...target, is_favorite: next };
        // 送ったあとは、お気に入りのボタンを押したキャプチャが隣として覚えられているので、戻ったときにも新しい状態で出るよう差し替える
        for (const neighbor of [prevCapture, nextCapture]) {
            if (neighbor.value?.id === updated.id) {
                neighbor.value = updated;
            }
        }
        emit('updated', updated);
    }
};

const openTagDialog = async () => {
    if (requireLogin()) {
        await finishSlideBeforeAction();
        isTagDialogOpen.value = true;
    }
};
// 表示しているキャプチャを、保存先にあるファイル名でブラウザのダウンロードフォルダへ保存する
const download = async () => {
    await finishSlideBeforeAction();
    if (props.capture !== null) {
        await Captures.downloadImages([props.capture]);
    }
};
const onTagsUpdated = async (captures: ICapture[]) => {
    if (captures[0] !== undefined) {
        // 応答を待つ間に隣のキャプチャへ送られても、戻ったときに新しいタグで出るよう、隣として覚えているキャプチャも差し替える
        const updated = captures[0];
        for (const neighbor of [prevCapture, nextCapture]) {
            if (neighbor.value?.id === updated.id) {
                neighbor.value = updated;
            }
        }
        emit('updated', updated);
    }
    tags.value = (await Captures.fetchTags()) ?? tags.value;
};

// 削除は管理者だけができるが、項目は誰にでも表示し、管理者でなければ押したときにログインし直す必要があることを伝える
const requestDelete = () => {
    if (!isAdmin.value) {
        Message.warning('キャプチャを削除するには管理者権限が必要です。\n管理者アカウントでログインし直してください。');
        return;
    }
    isDeleteConfirmOpen.value = true;
};

const deleteCapture = async () => {
    // 削除の途中で Enter キーが続けて押されたときは、最初の削除だけを送る
    if (props.capture === null || isDeleting.value) {
        return;
    }
    // 選択中のバーと同じく、応答が返るまでは確認のダイアログを開いたまま削除のボタンを読み込み中にする
    isDeleting.value = true;
    const current = props.capture;
    const result = await Captures.deleteCaptures([current.id]);
    isDeleting.value = false;
    isDeleteConfirmOpen.value = false;
    if (result === null) {
        return;
    }
    if (result.failed_capture_ids.length > 0) {
        Message.error('一部のファイルを削除できませんでした。もう一度お試しください。');
        return;
    }
    Message.success('キャプチャを削除しました。');
    // 削除したら次のキャプチャへ送り、なければ閉じる
    // 削除の応答を待つ間に閉じたり別のキャプチャを開いたりしたときは、一覧への通知だけにして、今の表示はそのまま保つ
    const neighbor = (await props.navigate(current, 1)) ?? (await props.navigate(current, -1)) ?? null;
    emit('deleted', [current.id]);
    if (props.capture?.id !== current.id) {
        return;
    }
    lastShownCapture = null;
    emit('update:capture', neighbor);
};

// 対応する録画があるときだけ、録画番組のサムネイルにできる
const canSetThumbnail = computed(() => (program.value?.recorded_program_ids.length ?? 0) > 0);

// このキャプチャを、対応する録画番組のサムネイルにする
const setAsThumbnail = async () => {
    if (props.capture === null || program.value === null || program.value.recorded_program_ids.length === 0) {
        return;
    }
    const videoId = program.value.recorded_program_ids[0];
    if (await Videos.updateThumbnailFromCapture(videoId, props.capture.id)) {
        Message.success('録画番組のサムネイルを、このキャプチャに変更しました。');
    }
};

const openProgram = () => {
    if (program.value === null) {
        return;
    }
    leaveTo(`/captures/programs/${program.value.id}`);
};

const playRecording = async () => {
    if (program.value === null || props.capture === null) {
        return;
    }
    // 押したときのキャプチャと録画 (録画の情報を待つ間に隣へ送られたり閉じられたりしたら、録画へは移らずに終える)
    const current = props.capture;
    const videoId = program.value.recorded_program_ids[0];
    // キャプチャの再生位置は番組開始からの秒数なので、録画開始のマージンを足して録画ファイル上の位置にしてから渡す
    let query = '';
    if (current.playback_position !== null) {
        const video = await Videos.fetchVideo(videoId);
        if (props.capture?.id !== current.id) {
            return;
        }
        // 番組の途中から録画した場合は録画開始のマージンが 0 に丸められているので、番組の開始時刻と録画の開始時刻の差から求める
        // 差がマイナスなら、録画が始まるまでの分だけ録画ファイル上の位置が手前になる
        let offset = video?.recording_start_margin ?? 0;
        if (video !== null && video.recorded_video.recording_start_time !== null) {
            offset = (dayjs(video.start_time).valueOf() - dayjs(video.recorded_video.recording_start_time).valueOf()) / 1000;
        }
        query = `?playback_position=${Math.max(0, offset + current.playback_position)}`;
    }
    leaveTo(`/videos/watch/${videoId}${query}`);
};


// ---------- 戻る操作 ----------

// 戻る操作 (Android の戻るボタンやブラウザの戻る) では、写真アプリと同じく1枚表示だけを閉じて一覧へ戻る
// そのため開いたときに同じ URL の履歴を1つ積み、戻る操作でその履歴が外れたら閉じる
// 積む状態は今の履歴の状態を写したものにして、Vue Router が持つ位置の情報をそのまま保つ
let hasHistoryEntry = false;
const onPopState = () => {
    if (hasHistoryEntry) {
        // ︙ のメニューや、タグや削除の確認のダイアログが上に重なっているときは、写真アプリと同じく一番上のものだけを閉じ、1枚表示の履歴を積み直す
        // Vuetify も戻る操作で開いているメニューやダイアログを閉じようとし、開いたままだと戻る操作を取り消すときにさらに1つ前の履歴へ戻ってしまう
        // Vuetify の判定は後から非同期で行われるので、ここで先に閉じておくと、Vuetify は戻る操作をそのまま通す
        if (isTagDialogOpen.value || isDeleteConfirmOpen.value || isMenuOpen.value) {
            isTagDialogOpen.value = false;
            isDeleteConfirmOpen.value = false;
            isMenuOpen.value = false;
            window.history.pushState({ ...window.history.state }, '');
            return;
        }
        // ショートカットの一覧のように、拡大表示の外の部品が開いたダイアログが重なっているときも、そのダイアログだけを閉じる
        // 開閉の状態は拡大表示から変えられないので、Vuetify のダイアログが Esc キーで閉じる処理を、ダイアログの中で Esc キーを押したときと同じイベントで呼び出す
        // ダイアログの中で押されたキーは、拡大表示と一覧のキーの処理がどちらも見送るので、閉じるのはダイアログだけになる
        const overlayContent = document.querySelector('.v-dialog.v-overlay--active > .v-overlay__content');
        if (overlayContent !== null) {
            overlayContent.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            window.history.pushState({ ...window.history.state }, '');
            return;
        }
        hasHistoryEntry = false;
        emit('update:capture', null);
    }
};
onMounted(() => window.addEventListener('popstate', onPopState));
onBeforeUnmount(() => window.removeEventListener('popstate', onPopState));

// 1枚表示から別の画面へ移るときは、積んだ履歴をその画面で置き換える (戻ると一覧に帰るようにする)
// 番組のキャプチャの一覧から同じ番組を開いたときのように、移る先が今の画面と同じなら、普通に閉じて積んだ履歴を戻す
const leaveTo = (path: string) => {
    if (router.resolve(path).fullPath === router.currentRoute.value.fullPath) {
        void close();
        return;
    }
    // 別の画面へ移るときは、一覧のタイルへ戻るアニメーションをせずにすぐ閉じる
    hasHistoryEntry = false;
    emit('update:capture', null);
    void router.replace(path);
};


// ---------- キーボードとページのスクロール ----------

// キーボードの操作 (左右で前後、Esc と Space で閉じる、F でお気に入り、T でタグ、I で情報、Delete で削除)
const onKeyDown = (event: KeyboardEvent) => {
    if (props.capture === null || isTagDialogOpen.value || isDeleteConfirmOpen.value) {
        return;
    }
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
    }
    // ショートカットの一覧など、上に重なったダイアログの中で押されたキーは、そのダイアログに任せる
    if (event.target instanceof Element && event.target.closest('.v-overlay__content') !== null) {
        return;
    }
    // Mac のキーボードには Delete キーがないため、Finder と同じく Command+Backspace でも削除できるようにする
    if (event.key === 'Backspace' && event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        event.stopImmediatePropagation();
        requestDelete();
        return;
    }
    // Ctrl・Command・Alt と一緒に押したキーは、ページ内検索 (Ctrl+F) などのブラウザのショートカットとしてブラウザに任せる
    if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
    }
    // 拡大率のスライダーを操作した後の左右の矢印キーは、スライダーで拡大率を変える操作としてスライダーに任せる
    const isArrowKey = event.key === 'ArrowLeft' || event.key === 'ArrowRight';
    if (isArrowKey && event.target instanceof Element && event.target.closest('.v-slider') !== null) {
        return;
    }
    switch (event.key) {
        case 'ArrowLeft': void move(-1); break;
        case 'ArrowRight': void move(1); break;
        case 'Escape': void close(); break;
        // macOS のクイックルックと同じく、一覧で Space を押して開いたら、もう一度 Space を押すと閉じる
        case ' ': void close(); break;
        case 'Delete': requestDelete(); break;
        case 'f': case 'F': void toggleFavorite(); break;
        case 't': case 'T': void openTagDialog(); break;
        case 'd': case 'D': void download(); break;
        case 'i': case 'I': setInfoOpen(!isInfoOpen.value); break;
        default: return;
    }
    event.preventDefault();
    // 動きを減らす設定のときは、Space や Esc で拡大表示がすぐに閉じるため、同じキーを一覧のキーの処理 (CaptureKeyboard.ts) が受け取ると、開き直したり選択を解除したりしてしまう
    // 拡大表示が扱ったキーは、ここで伝わるのを止めて、拡大表示の操作だけで終える
    event.stopImmediatePropagation();
};
// 一覧のキーの処理も window で受け取るので、それより先に必ず受け取れるよう、キャプチャフェーズで受け取る
onMounted(() => window.addEventListener('keydown', onKeyDown, { capture: true }));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown, { capture: true }));

// 開いている間はページのスクロールを止める
// App.vue の html の overflow-y の指定より優先されるよう、Vuetify のダイアログと同じクラスを付ける
// 先に付けておくと、上に重ねたタグのダイアログは html を対象から外すので、ダイアログを閉じてもクラスが残る
watch(() => props.capture !== null, (isOpen) => {
    if (isOpen) {
        document.documentElement.classList.add('v-overlay-scroll-blocked');
    } else {
        document.documentElement.classList.remove('v-overlay-scroll-blocked');
    }
    if (isOpen && !hasHistoryEntry) {
        // 1枚表示から別の画面へ移って戻ったときに、Vue Router が一覧の位置を戻せるよう、積む前に今の履歴へスクロール位置を書いておく
        window.history.replaceState({ ...window.history.state, scroll: { left: window.scrollX, top: window.scrollY } }, '');
        window.history.pushState({ ...window.history.state }, '');
        hasHistoryEntry = true;
    }
    // 閉じるボタンや Esc で閉じたときは、積んだ履歴を戻して外す
    if (!isOpen && hasHistoryEntry) {
        hasHistoryEntry = false;
        window.history.back();
    }
    if (!isOpen) {
        lastShownCapture = null;
        dragX.value = 0;
        dismissY.value = 0;
        isTagDialogOpen.value = false;
        isDeleteConfirmOpen.value = false;
        isMenuOpen.value = false;
    }
}, { immediate: true });
onBeforeUnmount(() => {
    document.documentElement.classList.remove('v-overlay-scroll-blocked');
});

</script>
<style lang="scss" scoped>

.capture-lightbox {
    position: fixed;
    inset: 0;
    // ページ側でスクロールバーの幅を確保している (scrollbar-gutter: stable) ため、inset だけでは右端にその幅のすき間ができる
    // 画面の幅いっぱいに広げて、後ろのページを覆う
    width: 100vw;
    // 下のナビゲーションより前に出し、中で開くタグのダイアログ (Vuetify の v-dialog は 2400) よりは後ろにする
    z-index: 2300;
    display: flex;
    overflow: hidden;
    color: rgb(var(--v-theme-text));
    outline: none;
    // 画像やボタンを押したときに文字が選択されないようにする (情報欄の読む文だけ、CaptureInfo.vue で選択できるように戻す)
    user-select: none;

    &__main {
        position: relative;
        flex: 1;
        min-width: 0;
        height: 100%;
    }

    &__bar {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        display: flex;
        align-items: center;
        gap: 2px;
        height: calc(56px + env(safe-area-inset-top));
        padding: env(safe-area-inset-top) 8px 0;
        background: linear-gradient(to bottom, rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0));
        z-index: 3;
    }
    &__button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        color: rgb(var(--v-theme-text));
        cursor: pointer;
        text-decoration: none;
        &:hover {
            background: rgba(var(--v-theme-text), 0.1);
        }
        @media (hover: none) {
            &:hover {
                background: transparent;
            }
        }
        // 取り消せない削除は、ほかの操作と見分けられるよう赤で表示する (CaptureSelectionBar.vue と同じ色)
        &--danger {
            color: rgb(var(--v-theme-error-lighten-1));
        }
    }

    &__stage {
        position: absolute;
        inset: 0;
        overflow: hidden;
        // 横の送りと縦のシートの操作は自前で扱うので、ブラウザのスクロールやズームの身振りを止める
        touch-action: none;
    }
    &__track {
        position: absolute;
        inset: 0;
        will-change: transform;
    }
    &__slide {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 100%;
        // 画像の大きさを、スライドの大きさに対する割合 (cqw・cqh) で決めるため
        container-type: size;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    &__image {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        user-select: none;
        -webkit-user-drag: none;
    }

    // 前後の矢印 (マウスを動かしている間だけ出す。スマホではスワイプで送るので出さない)
    &__nav {
        position: absolute;
        top: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 52px;
        height: 52px;
        margin-top: -26px;
        border-radius: 50%;
        background: rgba(0, 0, 0, 0.4);
        color: rgb(var(--v-theme-text));
        cursor: pointer;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        z-index: 2;
        &--prev {
            left: 20px;
        }
        &--next {
            right: 20px;
        }
        &--hidden {
            display: none;
        }
        @media (hover: none) {
            display: none;
        }
    }

    // 拡大している間の縮小図と拡大率のスライダー (矢印と同じく、マウスを動かしている間だけ出す)
    &__zoom {
        position: absolute;
        top: 60px;
        right: 16px;
        width: 260px;
        padding: 10px;
        border-radius: 12px;
        background: rgb(var(--v-theme-background-lighten-1), 0.92);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
        z-index: 3;
        user-select: none;
        &-map {
            position: relative;
            overflow: hidden;
            border-radius: 6px;
            cursor: pointer;
            touch-action: none;
        }
        &-image {
            display: block;
            width: 100%;
            -webkit-user-drag: none;
        }
        &-view {
            position: absolute;
            border: 2px solid rgb(var(--v-theme-text));
            border-radius: 3px;
            box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.45);
            pointer-events: none;
        }
        &-slider {
            display: flex;
            align-items: center;
            margin-top: 6px;
        }
        &-step {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
            cursor: pointer;
        }
        @media (hover: none) {
            display: none;
        }
    }

    &--control {
        .capture-lightbox__nav, .capture-lightbox__zoom {
            opacity: 1;
            visibility: visible;
        }
    }

    // 情報パネル (横画面): 視聴画面のパネルと同じく、右からせり出して画像の幅を押し縮める
    &__info {
        display: flex;
        flex-direction: column;
        flex-shrink: 0;
        width: 352px;
        height: 100%;
        margin-right: -352px;
        background: rgb(var(--v-theme-background));
        color: rgb(var(--v-theme-text));
        transition: margin-right 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);
        @include smartphone-horizontal {
            width: 310px;
            margin-right: -310px;
        }
        &-header {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            height: 70px;
            padding: 0 16px;
            padding-top: env(safe-area-inset-top);
            @include smartphone-horizontal {
                height: 52px;
            }
        }
        // 視聴画面のパネルの「閉じる」ボタンと同じ見た目
        &-close {
            display: flex;
            position: relative;
            align-items: center;
            left: -4px;
            height: 35px;
            padding: 0 4px;
            border-radius: 5px;
            font-size: 16px;
            font-weight: bold;
            user-select: none;
            cursor: pointer;
            svg {
                position: relative;
                left: -4px;
            }
        }
        &-scroll {
            flex: 1;
            min-height: 0;
            overflow-y: auto;
            overscroll-behavior: contain;
            // 横の操作は前後の送りに使うので、ブラウザには縦のスクロールだけを任せる
            touch-action: pan-y;
        }
    }
    &--info:not(&--portrait) &__info {
        margin-right: 0;
    }

    // 縦画面: 情報は画像の下に開くシートにする (写真アプリと同じく、16:9 の画像の下の余白に最初から出しておく)
    &--portrait {
        .capture-lightbox__main {
            position: absolute;
            inset: 0;
        }
        .capture-lightbox__stage {
            inset: auto 0 auto 0;
        }
        .capture-lightbox__info {
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            width: auto;
            height: auto;
            margin-right: 0;
            border-radius: 16px 16px 0 0;
            box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.3);
            z-index: 4;
        }
    }
    &__sheet-handle {
        flex-shrink: 0;
        width: 40px;
        height: 4px;
        margin: 10px auto 14px;
        border-radius: 2px;
        background: rgb(var(--v-theme-text-darken-2));
        cursor: pointer;
    }
}

// 取り消せない操作 (削除) のメニュー項目は、録画番組のメニューと同じく赤で示す
.capture-lightbox__menu-item--danger {
    color: rgb(var(--v-theme-error)) !important;
}

.capture-lightbox-fade-enter-active, .capture-lightbox-fade-leave-active {
    transition: opacity 0.18s ease;
}
.capture-lightbox-fade-enter-from, .capture-lightbox-fade-leave-to {
    opacity: 0;
}

</style>
<style lang="scss">

// 拡大表示の開閉で、タイルと1枚表示の間を拡大・縮小していく画像の複製 (CaptureTransition.ts の flyCaptureImage() を参照)
// body の直下に置くので、スコープなしのスタイルで指定する
// 拡大表示 (2300) より前、拡大表示の中で開くダイアログ (2400) より後ろに重ねる
.capture-flying-image {
    position: fixed;
    z-index: 2350;
    margin: 0;
    // 外枠の伸び縮みは左上を基準にし、はみ出した画像を切り抜く
    overflow: hidden;
    transform-origin: 0 0;
    pointer-events: none;
    will-change: transform;
    // 中の画像は外枠の中央を基準に拡大し、外枠と同じ大きさで画像の全体を表示する
    &__image {
        display: block;
        width: 100%;
        height: 100%;
        transform-origin: 50% 50%;
        will-change: transform;
    }
}

</style>
