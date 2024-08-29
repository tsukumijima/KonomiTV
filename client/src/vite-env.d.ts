/// <reference types="vite/client" />
/// <reference types="vite-plugin-comlink/client" />

import { Icon } from '@iconify/vue';


declare module '*.vue' {
    import type { DefineComponent } from 'vue';
    const component: DefineComponent<{}, {}, any>;
    export default component;
}

// **** ライブラリの型定義 *****

// グローバルコンポーネントの型定義
// "@vue/runtime-core" ではなく "vue" の型を拡張しないとすべての型が壊れてしまう
// ref: https://github.com/nuxt/nuxt/pull/28542
declare module 'vue' {
    export interface GlobalComponents {
        Icon: typeof Icon;
    }
}

// vue-virtual-scroller
// ref: https://github.com/Akryum/vue-virtual-scroller/issues/199#issuecomment-1762889915
declare module 'vue-virtual-scroller' {
    import type {
        ComponentOptionsMixin,
        ComponentPropsOptions,
        ComputedOptions,
        DefineComponent,
        MethodOptions
    } from 'vue';
    type ArrayElement<ArrayType extends readonly unknown[]> = ArrayType extends readonly (infer ElementType)[]
        ? ElementType
        : never;
    type RecycleScrollerProps = {
        items: any[];
        direction?: 'vertical' | 'horizontal';
        itemSize?: number | null;
        gridItems?: number;
        itemSecondarySize?: number;
        minItemSize?: number;
        sizeField?: string;
        typeField?: string;
        keyField?: string;
        pageMode?: boolean;
        prerender?: number;
        buffer?: number;
        emitUpdate?: boolean;
        updateInterval?: number;
        listClass?: string;
        itemClass?: string;
        listTag?: string;
        itemTag?: string;
    };
    type RecycleScrollerEmits = 'resize' | 'visible' | 'hidden' | 'update' | 'scroll-start' | 'scroll-end';
    type RecycleScrollerEmitFunctions = {
        resize: () => void;
        visible: () => void;
        hidden: () => void;
        update: (tartIndex: number, endIndex: number, visibleStartIndex: number, visibleEndIndex: number) => void;
        'scroll-start': () => void;
        'scroll-end': () => void;
    };
    type RecycleScrollerSlotProps = {
        item: ArrayElement<RecycleScrollerProps['items']>;
        index: number;
        active: boolean;
    };
    type RecycleScrollerSlots = {
        default: (slotProps: any) => VNode[];
        before: () => VNode[];
        empty: () => VNode[];
        after: () => VNode[];
    };
    interface RecycleScrollerPublicMethods extends MethodOptions {
        getScroll(): { start: number; end: number };
        scrollToItem(index: number): void;
        scrollToPosition(position: number);
    }
    /* eslint-disable @typescript-eslint/indent */
    export const RecycleScroller: DefineComponent<
        ComponentPropsOptions<RecycleScrollerProps>,
        object,
        object,
        ComputedOptions,
        RecycleScrollerPublicMethods,
        ComponentOptionsMixin,
        ComponentOptionsMixin,
        RecycleScrollerEmitFunctions,
        RecycleScrollerEmits,
        RecycleScrollerProps,
    >;
    export const DynamicScroller: RecycleScroller;
    type DynamicScrollerItemProps = {
        item: any;
        active: boolean;
        sizeDependencies?: any[];
        watchData?: boolean;
        tag?: string;
        emitResize?: boolean;
        onResize: () => void;
    };
    type DynamicScrollerItemEmits = 'resize';
    export const DynamicScrollerItem: DefineComponent<
        ComponentPropsOptions<DynamicScrollerItemProps>,
        object,
        object,
        ComputedOptions,
        MethodOptions,
        ComponentOptionsMixin,
        ComponentOptionsMixin,
        DynamicScrollerItemEmits[],
        DynamicScrollerItemEmits,
        DynamicScrollerItemProps
    >;
}

// ***** ブラウザの JavaScript API のうち、開発時点でマイナーすぎて @types が定義されていない API の型定義 *****

declare global {

    // location.reload() の forceReload 引数
    // ref: https://developer.mozilla.org/en-US/docs/Web/API/Location/reload
    interface Location {
        reload(forceReload?: boolean): void;
    }

    // View Transitions API
    // ref: https://developer.mozilla.org/ja/docs/Web/API/View_Transitions_API
    interface Document {
        startViewTransition?: (callback: () => Promise<void> | void) => {
            finished: Promise<void>;
            updateCallbackDone: Promise<void>;
            ready: Promise<void>;
            skipTransition: () => void;
        }
    }

    // Virtual Keyboard API
    // ref: https://www.w3.org/TR/virtual-keyboard/
    interface Navigator {
        readonly virtualKeyboard: VirtualKeyboard;
    }
    interface VirtualKeyboard {
        show(): undefined;
        hide(): undefined;
        readonly boundingRect: DOMRectReadOnly;
        overlaysContent: boolean;
        ongeometrychange: VirtualKeyboardGeometryChangeEventListener;
        addEventListener(
            type: 'geometrychange',
            listener: VirtualKeyboardGeometryChangeEventListener,
            options?: boolean | AddEventListenerOptions
        ): void;
        removeEventListener(
            type: 'geometrychange',
            listener: VirtualKeyboardGeometryChangeEventListener,
            options?: boolean | EventListenerOptions
        ): void;
    }
    interface VirtualKeyboardGeometryChangeEvent extends Event {
        readonly currentTarget: VirtualKeyboard;
        readonly srcElement: VirtualKeyboard;
        readonly target: VirtualKeyboard;
    }
    type VirtualKeyboardGeometryChangeEventListener = ((ev: VirtualKeyboardGeometryChangeEvent) => any) | null;

    // Picture-in-Picture API
    // ref: https://gist.github.com/Rendez/6e088e8713f47e87ab04efcc22f365b1
    interface PictureInPictureResizeEvent extends Event {
        readonly currentTarget: PictureInPictureWindow;
        readonly srcElement: PictureInPictureWindow;
        readonly target: PictureInPictureWindow;
    }
    interface PictureInPictureWindow {
        readonly width: number;
        readonly height: number;
        onresize(this: PictureInPictureWindow, ev: PictureInPictureResizeEvent): void;
        addEventListener(
            type: 'resize',
            listener: EventListenerOrEventListenerObject,
            options?: boolean | AddEventListenerOptions
        ): void;
        removeEventListener(
            type: 'resize',
            listener: EventListenerOrEventListenerObject,
            options?: boolean | EventListenerOptions
        ): void;
    }
    interface PictureInPictureEvent extends Event {
        readonly pictureInPictureWindow: PictureInPictureWindow;
    }
    type PictureInPictureEventListener = ((this: HTMLVideoElement, ev: PictureInPictureEvent) => any) | null;
    interface HTMLVideoElement {
        autoPictureInPicture: boolean;
        disablePictureInPicture: boolean;
        requestPictureInPicture(): Promise<PictureInPictureWindow>;
        onenterpictureinpicture: PictureInPictureEventListener;
        onleavepictureinpicture: PictureInPictureEventListener;
    }
    interface Element {
        webkitRequestFullscreen?(): Promise<void>;
        onwebkitfullscreenchange?: ((this: Element, ev: Event) => any) | null;
    }
    interface Document {
        readonly pictureInPictureEnabled: boolean;
        exitPictureInPicture(): Promise<void>;
        webkitFullscreenElement?: Element;
        webkitExitFullscreen?(): Promise<void>;
    }
    interface DocumentOrShadowRoot {
        readonly pictureInPictureElement: HTMLVideoElement | null;
        webkitFullscreenElement?: Element;
    }

    // Document Picture-in-Picture API
    // ref: https://wicg.github.io/document-picture-in-picture/#api
    // ref: https://github.com/BenjaminAster/TypeScript-types-for-new-JavaScript/blob/main/wicg/document-picture-in-picture.d.ts
    // eslint-disable-next-line no-var
    declare var documentPictureInPicture: DocumentPictureInPicture;
    declare class DocumentPictureInPicture extends EventTarget {
        requestWindow(options?: DocumentPictureInPictureOptions): Promise<Window>;
        readonly window: Window | null;
        onenter: ((this: DocumentPictureInPicture, ev: DocumentPictureInPictureEvent) => any) | null;
        addEventListener<K extends keyof DocumentPictureInPictureEventMap>(type: K, listener: (this: DocumentPictureInPicture, ev: DocumentPictureInPictureEventMap[K]) => any, options?: boolean | AddEventListenerOptions): void;
        addEventListener(type: string, listener: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions): void;
        removeEventListener<K extends keyof DocumentPictureInPictureEventMap>(type: K, listener: (this: DocumentPictureInPicture, ev: DocumentPictureInPictureEventMap[K]) => any, options?: boolean | EventListenerOptions): void;
        removeEventListener(type: string, listener: EventListenerOrEventListenerObject, options?: boolean | EventListenerOptions): void;
    }
    interface DocumentPictureInPictureEventMap {
        'enter': DocumentPictureInPictureEvent;
    }
    interface DocumentPictureInPictureOptions {
        width?: number;
        height?: number;
        disallowReturnToOpener?: boolean;
    }
    declare class DocumentPictureInPictureEvent {
        constructor(type: string, eventInitDict: DocumentPictureInPictureEventInit);
        readonly window: Window;
    }
    interface DocumentPictureInPictureEventInit {
        window: Window;
    }
}
