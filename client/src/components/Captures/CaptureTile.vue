<template>
    <!-- 拡大表示を閉じるときに、戻る先のタイルを探せるよう、キャプチャの ID を属性に持たせる -->
    <div class="capture-tile" :data-capture-id="capture.id"
        :class="{
            'capture-tile--selected': selected,
            'capture-tile--cursor': cursor,
            'capture-tile--previewed': previewed && !selected,
            'capture-tile--selecting': selecting,
        }"
        @click="onClick"
        @contextmenu.prevent="onContextMenu"
        @touchstart.passive="onTouchStart"
        @touchmove.passive="onTouchMove"
        @touchend="onTouchEnd"
        @touchcancel="cancelLongPress">
        <img ref="imageRef" class="capture-tile__image" :class="{'capture-tile__image--loaded': isLoaded}"
            :alt="capture.caption_text ?? ''" decoding="async" draggable="false" @load="isLoaded = true">
        <div class="capture-tile__shade"></div>
        <div v-ripple class="capture-tile__check" @click.stop="$emit('toggle', $event.shiftKey)">
            <Icon :icon="selected || previewed ? 'fluent:checkmark-circle-24-filled' : 'fluent:circle-24-regular'" width="24px" height="24px" />
        </div>
        <!-- お気に入りのボタン (お気に入りに追加済みなら常に出し、そうでなければマウスを乗せたときだけ出す) -->
        <!-- ログインしていないとき (is_favorite が null) も表示し、押したときに拡大表示と同じくログインが必要なことを伝える -->
        <div v-ripple class="capture-tile__favorite"
            :class="{'capture-tile__favorite--active': capture.is_favorite}"
            v-ftooltip.bottom="capture.is_favorite ? 'お気に入りから外す' : 'お気に入りに追加'"
            @click.stop="toggleFavorite">
            <Icon :icon="capture.is_favorite ? 'fluent:heart-24-filled' : 'fluent:heart-24-regular'" width="22px" height="22px" />
        </div>
        <div class="capture-tile__badges">
            <!-- 画像に写し込まれているものは、小さなタイルでも場所を取らないよう見慣れた記号で示し、言葉は読み上げとツールチップで伝える -->
            <span v-if="capture.is_caption_composited" class="capture-tile__badge" role="img" aria-label="字幕入り" title="字幕入り">
                <Icon icon="fluent:closed-caption-16-filled" width="16px" height="16px" />
            </span>
            <span v-if="capture.is_comment_composited" class="capture-tile__badge" role="img" aria-label="コメント入り" title="コメント入り">
                <Icon icon="fluent:comment-text-16-filled" width="15px" height="15px" />
            </span>
        </div>
        <div v-if="showPosition && capture.playback_position !== null" class="capture-tile__position">
            {{ formatPosition(capture.playback_position) }}
        </div>
    </div>
    <!-- 字幕が出ていなかった場面は何も書かない (「字幕なし」と書くと、それ自体がセリフに見えるため) -->
    <div v-if="showCaption" class="capture-tile-caption">{{ capture.caption_text ?? '' }}</div>
</template>
<script lang="ts" setup>

import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { openWithTransition } from '@/components/Captures/CaptureTransition';
import Message from '@/message';
import Captures, { ICapture } from '@/services/Captures';
import useUserStore from '@/stores/UserStore';


const props = withDefaults(defineProps<{
    capture: ICapture;
    selected?: boolean;
    cursor?: boolean;
    previewed?: boolean;
    selecting?: boolean;
    showPosition?: boolean;
    showCaption?: boolean;
}>(), {
    selected: false,
    cursor: false,
    previewed: false,
    selecting: false,
    showPosition: false,
    showCaption: false,
});

const emit = defineEmits<{
    (event: 'open'): void;
    (event: 'toggle', shiftKey: boolean): void;
    (event: 'updated', capture: ICapture): void;
}>();

const userStore = useUserStore();
const imageRef = ref<HTMLImageElement | null>(null);
const isLoaded = ref(false);

// 画面に見えている (と少し先の) タイルだけ画像を読み込み、画面外へ流れたタイルの読み込み中の画像は取り消す
// ブラウザ任せの loading="lazy" は画面外の画像まで先に大量に頼み、見えている画像がその後ろで待たされるので、読み込みの開始と取り消しを自前で行う
const observer = getSharedObserver();

onMounted(() => {
    if (imageRef.value !== null) {
        imageRef.value.dataset.src = Captures.getImageURL(props.capture);
        observer.observe(imageRef.value);
    }
});
onBeforeUnmount(() => {
    if (imageRef.value !== null) {
        observer.unobserve(imageRef.value);
    }
});

// 同じタイルの要素が別のキャプチャに使い回されたときは、画像を差し替える
watch(() => props.capture.id, () => {
    if (imageRef.value === null) {
        return;
    }
    isLoaded.value = false;
    imageRef.value.removeAttribute('src');
    imageRef.value.dataset.src = Captures.getImageURL(props.capture);
    observer.unobserve(imageRef.value);
    observer.observe(imageRef.value);
});

// お気に入りの切り替え
// 応答を待つ間にタイルが別のキャプチャに使い回されても、押したときのキャプチャに結果を当てる
let isUpdatingFavorite = false;
const toggleFavorite = async () => {
    // お気に入りはログインが必要なので、ログインしていなければ拡大表示や選択中のバーと同じ文言でログインを促す
    if (!userStore.is_logged_in) {
        Message.warning('お気に入りとタグを使うには、KonomiTV アカウントにログインしてください。');
        return;
    }
    if (isUpdatingFavorite) {
        return;
    }
    isUpdatingFavorite = true;
    const capture = props.capture;
    const next = capture.is_favorite !== true;
    const succeeded = await Captures.updateFavorites([capture.id], next);
    isUpdatingFavorite = false;
    if (succeeded) {
        Message.success(next ? 'キャプチャをお気に入りに追加しました。' : 'キャプチャをお気に入りから外しました。');
        emit('updated', { ...capture, is_favorite: next });
    }
};

// 選択モード中のクリックは選択の切り替え、それ以外は拡大表示
// 拡大表示は、タイルの画像が1枚表示の画像の位置まで拡大していくように開く
const onClick = (event: MouseEvent) => {
    if (props.selecting || event.shiftKey) {
        emit('toggle', event.shiftKey);
    } else {
        openWithTransition(isLoaded.value ? imageRef.value : null, () => emit('open'));
    }
};

// スマホでは長押しで選択を始める (HonomiTV 版の選択の作りと同じ)
// 長押しの判定はこのタイマーだけで行う
// Android Chrome は長押しで contextmenu も発火させるため、両方で切り替えると選んだ直後に外れてしまう
const LONG_PRESS_MS = 450;
// 指のわずかな揺れで長押しが取り消されないよう、この距離までの移動は長押しの続きとみなす
const LONG_PRESS_MOVE_TOLERANCE = 10;
let longPressTimer: number | null = null;
let longPressed = false;
let isTouching = false;
let touchStartX = 0;
let touchStartY = 0;
const onTouchStart = (event: TouchEvent) => {
    longPressed = false;
    isTouching = true;
    touchStartX = event.touches[0].clientX;
    touchStartY = event.touches[0].clientY;
    cancelLongPress();
    longPressTimer = window.setTimeout(() => {
        longPressed = true;
        emit('toggle', false);
        if ('vibrate' in navigator) {
            navigator.vibrate(30);
        }
    }, LONG_PRESS_MS);
};
const cancelLongPress = () => {
    if (longPressTimer !== null) {
        window.clearTimeout(longPressTimer);
        longPressTimer = null;
    }
};
const onTouchMove = (event: TouchEvent) => {
    // スクロールしようとして指が動いたときだけ、長押しを取り消す
    const dx = event.touches[0].clientX - touchStartX;
    const dy = event.touches[0].clientY - touchStartY;
    if (Math.hypot(dx, dy) > LONG_PRESS_MOVE_TOLERANCE) {
        cancelLongPress();
    }
};
const onTouchEnd = (event: TouchEvent) => {
    cancelLongPress();
    // 指を離した後に遅れて届く contextmenu も無視できるよう、触れている印は少し後で下ろす
    window.setTimeout(() => {
        isTouching = false;
    }, 600);
    // 長押しで選択したときは、続けて発生するクリックを取り消し、選択の操作だけで終える
    if (longPressed) {
        event.preventDefault();
    }
};

// 右クリックはマウスでの選択の切り替え
// 指での長押しから来た contextmenu は、長押しのタイマーが選択を済ませているので、ここでは処理を終える
const onContextMenu = (event: MouseEvent) => {
    if (isTouching || (event instanceof PointerEvent && event.pointerType === 'touch')) {
        return;
    }
    emit('toggle', event.shiftKey);
};

const formatPosition = (seconds: number) => {
    const sign = seconds < 0 ? '-' : '';
    const value = Math.floor(Math.abs(seconds));
    const hours = Math.floor(value / 3600);
    const minutes = Math.floor((value % 3600) / 60);
    const secs = value % 60;
    const mmss = `${String(minutes).padStart(hours > 0 ? 2 : 1, '0')}:${String(secs).padStart(2, '0')}`;
    return sign + (hours > 0 ? `${hours}:${mmss}` : mmss);
};

</script>
<script lang="ts">

// すべてのタイルで共有する IntersectionObserver
// タイルごとに作ると、数百枚のタイルで監視が重くなるため
let sharedObserver: IntersectionObserver | null = null;
function getSharedObserver(): IntersectionObserver {
    if (sharedObserver === null) {
        sharedObserver = new IntersectionObserver((entries) => {
            for (const entry of entries) {
                const image = entry.target as HTMLImageElement;
                if (entry.isIntersecting) {
                    if (!image.getAttribute('src') && image.dataset.src) {
                        image.src = image.dataset.src;
                    }
                } else if (!image.complete) {
                    // 読み込み中のまま画面外へ流れた画像は、読み込みを取り消して見えている画像に回線を譲る
                    image.removeAttribute('src');
                }
            }
        }, { rootMargin: '300px 0px' });
    }
    return sharedObserver;
}

</script>
<style lang="scss" scoped>

.capture-tile {
    position: relative;
    width: 100%;
    height: 100%;
    border-radius: 6px;
    overflow: hidden;
    background: rgb(var(--v-theme-background-lighten-1));
    cursor: pointer;
    user-select: none;
    -webkit-touch-callout: none;
    transition: transform 0.12s ease, outline-color 0.15s ease;

    &__image {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;
        opacity: 0;
        transition: opacity 0.2s ease;
        &--loaded {
            opacity: 1;
        }
    }

    // ホバー時と選択中だけ、上下を暗くしてチェックや印を読みやすくする
    &__shade {
        position: absolute;
        inset: 0;
        background: linear-gradient(to bottom, rgba(0, 0, 0, 0.45) 0%, rgba(0, 0, 0, 0) 32%, rgba(0, 0, 0, 0) 68%, rgba(0, 0, 0, 0.5) 100%);
        opacity: 0;
        transition: opacity 0.15s ease;
        pointer-events: none;
    }

    &__check {
        position: absolute;
        top: 4px;
        left: 4px;
        display: flex;
        padding: 2px;
        border-radius: 50%;
        color: rgba(var(--v-theme-text), 0.92);
        opacity: 0;
        transition: opacity 0.15s ease;
        filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.6));
    }

    &__badges {
        position: absolute;
        left: 6px;
        bottom: 5px;
        display: flex;
        align-items: center;
        gap: 4px;
        pointer-events: none;
    }
    // お気に入りのボタン (選択のチェックと対になるよう、右上に同じ大きさで置く)
    &__favorite {
        position: absolute;
        top: 4px;
        right: 4px;
        display: flex;
        padding: 3px;
        border-radius: 50%;
        color: rgba(var(--v-theme-text), 0.92);
        // 見えていない間は、スマホで右上を触ったときに知らずに切り替わらないよう、押せなくする
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.15s ease, visibility 0.15s ease;
        // 写真から浮かないよう、影は明るい画像の上でも形が分かる程度のごく薄いものにとどめる
        filter: drop-shadow(0 0 1px rgba(0, 0, 0, 0.3));
        // お気に入りに追加済みのハートも、選択のチェックと同じ白で示す
        &--active {
            color: rgb(var(--v-theme-text));
            opacity: 1;
            visibility: visible;
        }
    }
    &__badge {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 20px;
        border-radius: 4px;
        background: rgba(0, 0, 0, 0.6);
        color: rgb(var(--v-theme-text));
        // 入れ物はクリックを下のタイルへ通すが、印はマウスを乗せたときに言葉を出せるようにする (クリックは親のタイルへ伝わる)
        pointer-events: auto;
    }
    &__badges, &__position {
        transition: opacity 0.15s ease;
    }

    &__position {
        position: absolute;
        right: 5px;
        bottom: 5px;
        padding: 0px 6px;
        border-radius: 4px;
        background: rgba(0, 0, 0, 0.66);
        color: rgb(var(--v-theme-text));
        font-size: 12px;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        line-height: 20px;
        pointer-events: none;
    }

    @media (hover: hover) {
        &:hover {
            .capture-tile__shade, .capture-tile__check, .capture-tile__favorite {
                opacity: 1;
                visibility: visible;
            }
        }
    }

    // 選択モード中は全タイルにチェックを出し、選んだタイルは少し縮めて枠を付ける
    &--selecting {
        .capture-tile__check {
            opacity: 1;
        }
    }
    // Ctrl キーと矢印キーで動かしているカーソルの位置は、選択の枠と区別できるよう白い枠で示す
    &--cursor::after {
        content: '';
        position: absolute;
        inset: 0;
        border: 2px solid rgb(var(--v-theme-text));
        border-radius: inherit;
        pointer-events: none;
    }
    // Shift キーを押しながらマウスを乗せているときに、クリックすると選ばれる範囲は、選んだときより淡く示す
    &--previewed {
        outline: 3px solid rgb(var(--v-theme-primary), 0.5);
        outline-offset: -3px;
        .capture-tile__shade {
            opacity: 1;
        }
        .capture-tile__check {
            color: rgb(var(--v-theme-primary-lighten-1));
        }
    }
    // 拡大表示を閉じてこのタイルへ縮んでいく間は、画像の上に重なる枠とアイコンを隠し、縮み終わってからフェードインさせる
    // (縮んでいく画像の下に隠れたまま、縮み終わった瞬間に突然現れないようにするため。CaptureLightbox.vue の close() を参照)
    &--landing {
        outline-color: transparent !important;
        .capture-tile__shade, .capture-tile__check, .capture-tile__favorite, .capture-tile__badges, .capture-tile__position {
            opacity: 0 !important;
        }
    }
    &--selected {
        transform: scale(0.92);
        outline: 3px solid rgb(var(--v-theme-primary));
        outline-offset: -3px;
        .capture-tile__shade {
            opacity: 1;
        }
        .capture-tile__check {
            color: rgb(var(--v-theme-primary));
            background: rgb(var(--v-theme-text));
            padding: 0;
            margin: 2px;
        }
    }
}

.capture-tile-caption {
    margin-top: 4px;
    font-size: 12.5px;
    line-height: 1.45;
    color: rgb(var(--v-theme-text));
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

</style>
