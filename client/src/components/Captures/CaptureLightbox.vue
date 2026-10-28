<template>
    <Teleport to="body">
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
                        <a v-ripple class="capture-lightbox__button" v-ftooltip.bottom="'ダウンロード'"
                            :href="Captures.getImageURL(capture)" :download="downloadName" @click.stop>
                            <Icon icon="fluent:arrow-download-24-regular" width="24px" />
                        </a>
                        <!-- 情報 (横画面では右のパネル、縦画面では下のシート) の開閉 (開いている間はアイコンを塗りつぶしにする) -->
                        <div v-ripple class="capture-lightbox__button" v-ftooltip.bottom="isInfoOpen ? '情報を閉じる (I)' : '情報を開く (I)'"
                            @click="setInfoOpen(!isInfoOpen)">
                            <Icon :icon="isInfoOpen ? 'fluent:info-24-filled' : 'fluent:info-24-regular'" width="24px" />
                        </div>
                        <!-- その他の操作 (録画番組のメニューと同じく、取り消せない削除は区切り線の下に赤で置き、押し間違えにくくする) -->
                        <v-menu v-if="canSetThumbnail || isAdmin" location="bottom end" :z-index="2400">
                            <template #activator="{ props: menuProps }">
                                <div v-ripple class="capture-lightbox__button" v-bind="menuProps">
                                    <Icon icon="fluent:more-vertical-24-filled" width="24px" />
                                </div>
                            </template>
                            <v-list density="compact" bg-color="background-lighten-1">
                                <v-list-item v-if="canSetThumbnail" @click="setAsThumbnail">
                                    <template #prepend>
                                        <Icon icon="fluent:image-20-regular" width="20px" height="20px" />
                                    </template>
                                    <v-list-item-title class="ml-3">録画番組のサムネイルにする</v-list-item-title>
                                </v-list-item>
                                <v-divider v-if="canSetThumbnail && isAdmin"></v-divider>
                                <v-list-item v-if="isAdmin" class="capture-lightbox__menu-item--danger" @click="isDeleteConfirmOpen = true">
                                    <template #prepend>
                                        <Icon icon="fluent:delete-20-regular" width="20px" height="20px" />
                                    </template>
                                    <v-list-item-title class="ml-3">キャプチャを削除</v-list-item-title>
                                </v-list-item>
                            </v-list>
                        </v-menu>
                    </div>

                    <!-- 画像: 前・今・次の3枚を横に並べ、指の動きに合わせて全体をずらす -->
                    <div ref="stageRef" class="capture-lightbox__stage" :style="stageStyle"
                        @click.self="onStageClick"
                        @touchstart="onStageTouchStart" @touchmove="onStageTouchMove"
                        @touchend="onStageTouchEnd" @touchcancel="onStageTouchEnd">
                        <div class="capture-lightbox__track" :style="trackStyle" @click.self="onStageClick">
                            <div v-for="slide in slides" :key="slide.key" class="capture-lightbox__slide"
                                :style="{ left: `calc(${slide.offset * 100}% + ${slide.offset * SLIDE_GAP}px)` }"
                                @click.self="onStageClick">
                                <img v-if="slide.capture !== null" class="capture-lightbox__image" :src="Captures.getImageURL(slide.capture)"
                                    :class="{'capture-lightbox__image--current': slide.offset === 0}"
                                    :alt="slide.capture.caption_text ?? ''" draggable="false">
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
                <v-dialog max-width="520" :model-value="isDeleteConfirmOpen" @update:model-value="isDeleteConfirmOpen = $event">
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
                            <v-btn color="error" variant="flat" height="40" class="px-3" @click="deleteCapture">
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

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import CaptureInfo from '@/components/Captures/CaptureInfo.vue';
import CaptureTagDialog from '@/components/Captures/CaptureTagDialog.vue';
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
const detail = ref<ICaptureDetail | null>(null);
const tags = ref<ICaptureTag[]>([]);

const isAdmin = computed(() => userStore.user?.is_admin === true);
const program = computed(() => detail.value?.program ?? props.programHint ?? null);
const tagNames = computed(() => {
    const ids = new Set(props.capture?.tag_ids ?? []);
    return tags.value.filter(tag => ids.has(tag.id)).map(tag => tag.name);
});
const downloadName = computed(() => detail.value?.files[0]?.file_name ?? `capture-${props.capture?.id}.jpg`);

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

const close = () => {
    emit('update:capture', null);
};

// 前後へ送る (矢印キー・矢印ボタン・スワイプで共通)
// 隣の画像を今の位置まで滑らせてから、表示中のキャプチャを差し替える
const move = async (delta: 1 | -1) => {
    if (props.capture === null || isSliding.value) {
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
    await new Promise(resolve => window.setTimeout(resolve, 300));
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
    };
};
const trackVelocity = (track: ITouchTrack, event: TouchEvent) => {
    const y = event.touches[0].clientY;
    const elapsed = Math.max(event.timeStamp - track.lastTime, 1);
    track.velocityY = (y - track.lastY) / elapsed;
    track.lastY = y;
    track.lastTime = event.timeStamp;
};

const onStageTouchStart = (event: TouchEvent) => {
    if (event.touches.length !== 1 || isSliding.value) {
        touch = null;
        return;
    }
    touch = beginTouch(event);
    showControl();
};
const onStageTouchMove = (event: TouchEvent) => {
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
        if (touch.axis === 'Y') {
            // 縦画面では上下でシートを開閉し、シートを閉じているときに下へ引いたら1枚表示を閉じる (写真アプリと同じ)
            const isOpeningOrClosingSheet = isPortrait.value && (isInfoOpen.value || dy < 0);
            touch.verticalTarget = isOpeningOrClosingSheet ? 'Sheet' : 'Dismiss';
        }
    }
    event.preventDefault();
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
    } else if (track.verticalTarget === 'Dismiss') {
        // 十分に下へ引いたか、素早く払ったら閉じる
        if (dismissY.value > 120 || track.velocityY > 0.5) {
            close();
        }
        dismissY.value = 0;
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
    close();
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

const toggleFavorite = async () => {
    if (props.capture === null || !requireLogin()) {
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

const openTagDialog = () => {
    if (requireLogin()) {
        isTagDialogOpen.value = true;
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

const deleteCapture = async () => {
    if (props.capture === null) {
        return;
    }
    isDeleteConfirmOpen.value = false;
    const current = props.capture;
    const result = await Captures.deleteCaptures([current.id]);
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
        // タグや削除の確認のダイアログが上に重なっているときは、写真アプリと同じく一番上のダイアログだけを閉じ、1枚表示の履歴を積み直す
        if (isTagDialogOpen.value || isDeleteConfirmOpen.value) {
            isTagDialogOpen.value = false;
            isDeleteConfirmOpen.value = false;
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
        close();
        return;
    }
    hasHistoryEntry = false;
    close();
    void router.replace(path);
};


// ---------- キーボードとページのスクロール ----------

// キーボードの操作 (左右で前後、Esc で閉じる、F でお気に入り、T でタグ、I で情報)
const onKeyDown = (event: KeyboardEvent) => {
    if (props.capture === null || isTagDialogOpen.value || isDeleteConfirmOpen.value) {
        return;
    }
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
    }
    // Ctrl・Command・Alt と一緒に押したキーは、ページ内検索 (Ctrl+F) などのブラウザのショートカットとしてブラウザに任せる
    if (event.ctrlKey || event.metaKey || event.altKey) {
        return;
    }
    switch (event.key) {
        case 'ArrowLeft': void move(-1); break;
        case 'ArrowRight': void move(1); break;
        case 'Escape': close(); break;
        case 'f': case 'F': void toggleFavorite(); break;
        case 't': case 'T': openTagDialog(); break;
        case 'i': case 'I': setInfoOpen(!isInfoOpen.value); break;
        default: return;
    }
    event.preventDefault();
};
onMounted(() => window.addEventListener('keydown', onKeyDown));
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown));

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

    &--control {
        .capture-lightbox__nav {
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

// 一覧のタイルから開いたときに、タイルの画像から拡大していく表示中の画像 (CaptureTile.vue の openWithTransition() を参照)
// View Transitions API の疑似要素は文書の最上位にできるので、スコープなしのスタイルで指定する
.capture-lightbox__image--current {
    view-transition-name: capture-lightbox-image;
}
::view-transition-group(capture-lightbox-image) {
    animation-duration: 0.3s;
    animation-timing-function: cubic-bezier(0.26, 0.68, 0.55, 0.99);
}
::view-transition-old(capture-lightbox-image),
::view-transition-new(capture-lightbox-image) {
    // タイルは画像を切り抜いて並べているので、縦横比の違いで画像が伸び縮みしないよう、切り抜いたまま重ねる
    height: 100%;
    object-fit: cover;
}

</style>
