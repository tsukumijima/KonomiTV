
import type { DefineComponent } from 'vue';

// Vue コンポーネントの型定義
// ref: https://azukiazusa.dev/blog/volar-vuetify2-x/
declare module 'vue' {
    export interface GlobalComponents {
        RouterLink: typeof import('vue-router')['RouterLink']
        RouterView: typeof import('vue-router')['RouterView']
        Icon: typeof import('@iconify/vue2')['Icon']
        VTabItemFix: DefineComponent<{
            /** Configure the active CSS class applied when the link is active. You can find more information about the [**active-class** prop](https://router.vuejs.org/api/#active-class) on the vue-router documentation. */
            activeClass?: string | null
            /** Removes the ability to click or target the component. */
            disabled?: boolean | null
            /** Will force the components content to render on mounted. This is useful if you have content that will not be rendered in the DOM that you want crawled for SEO. */
            eager?: boolean | null
            /** Sets the DOM id on the component */
            id?: string | null
            /** Sets the reverse transition */
            reverseTransition?: boolean | string | null
            /** The transition used when the component progressing through items. Can be one of the [built in transitions](/styles/transitions) or one your own. */
            transition?: boolean | string | null
            /** Sets the value of the tab. If not provided, the index will be used. */
            value?: any | null
        },
        {
            $scopedSlots: Readonly<{
            /** The default Vue slot. */
                default: undefined
            }>
        }>
        VTabsFix: DefineComponent<{
            /** The **active-class** applied to children when they are activated. */
            activeClass?: string | null
            /** Make `v-tabs` lined up with the toolbar title */
            alignWithTitle?: boolean | null
            /** Changes the background color of the component. */
            backgroundColor?: string | null
            /** Forces the selected tab to be centered */
            centerActive?: boolean | null
            /** Centers the tabs */
            centered?: boolean | null
            /** Applies specified color to the control - it can be the name of material color (for example `success` or `purple`) or css color (`#033` or `rgba(255, 0, 0, 0.5)`). You can find a list of built-in classes on the [colors page](/styles/colors#material-colors). */
            color?: string | null
            /** Applies the dark theme variant to the component. You can find more information on the Material Design documentation for [dark themes](https://material.io/design/color/dark-theme.html). */
            dark?: boolean | null
            /** `v-tabs-item` min-width 160px, max-width 360px */
            fixedTabs?: boolean | null
            /** Force `v-tab`'s to take up all available space */
            grow?: boolean | null
            /** Sets the height of the tabs bar */
            height?: number | string | null
            /** Hide's the generated `v-tabs-slider` */
            hideSlider?: boolean | null
            /** Will stack icon and text vertically */
            iconsAndText?: boolean | null
            /** Applies the light theme variant to the component. */
            light?: boolean | null
            /** Sets the designated mobile breakpoint for the component. */
            mobileBreakpoint?: string | number | null
            /** Right pagination icon */
            nextIcon?: string | null
            /** Does not require an active item. Useful when using `v-tab` as a `router-link` */
            optional?: boolean | null
            /** Left pagination icon */
            prevIcon?: string | null
            /** Aligns tabs to the right */
            right?: boolean | null
            /** Show pagination arrows if the tab items overflow their container. For mobile devices, arrows will only display when using this prop. */
            showArrows?: boolean | string | null
            /** Changes the background color of an auto-generated `v-tabs-slider` */
            sliderColor?: string | null
            /** Changes the size of the slider, **height** for horizontal, **width** for vertical. */
            sliderSize?: number | string | null
            /** The designated model value for the component. */
            value?: any | null
            /** Stacks tabs on top of each other vertically. */
            vertical?: boolean | null
        },
        {
            $scopedSlots: Readonly<{
            /** The default Vue slot. */
                default: undefined
            }>
        }>
        VTabsItemsFix: DefineComponent<{
            /** The **active-class** applied to children when they are activated. */
            activeClass?: string | null
            /** If `true`, window will "wrap around" from the last item to the first, and from the first item to the last */
            continuous?: boolean | null
            /** Applies the dark theme variant to the component. You can find more information on the Material Design documentation for [dark themes](https://material.io/design/color/dark-theme.html). */
            dark?: boolean | null
            /** Applies the light theme variant to the component. */
            light?: boolean | null
            /** Forces a value to always be selected (if available). */
            mandatory?: boolean | null
            /** Sets a maximum number of selections that can be made. */
            max?: number | string | null
            /** Allow multiple selections. The **value** prop must be an _array_. */
            multiple?: boolean | null
            /** Icon used for the "next" button if `show-arrows` is `true` */
            nextIcon?: boolean | string | null
            /** Icon used for the "prev" button if `show-arrows` is `true` */
            prevIcon?: boolean | string | null
            /** Reverse the normal transition direction. */
            reverse?: boolean | null
            /** Display the "next" and "prev" buttons */
            showArrows?: boolean | null
            /** Display the "next" and "prev" buttons on hover. `show-arrows` MUST ALSO be set. */
            showArrowsOnHover?: boolean | null
            /** Specify a custom tag used on the root element. */
            tag?: string | null
            /** Provide a custom **left** and **right** function when swiped left or right. */
            touch?: object | null
            /** Disable touch support. */
            touchless?: boolean | null
            /** The designated model value for the component. */
            value?: any | null
            /** Apply a custom value comparator function */
            valueComparator?: Function | null
            /** Uses a vertical transition when changing windows. */
            vertical?: boolean | null
        },
        {
            $scopedSlots: Readonly<{
                /** The default Vue slot. */
                default: undefined
            }>
        }>
    }
}

// ***** ブラウザの JavaScript API のうち、開発時点でマイナーすぎて @types が定義されていない API の型定義 *****

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
    webkitRequestFullscreen(): Promise<void>;
}
interface Document {
    readonly pictureInPictureEnabled: boolean;
    webkitFullscreenElement: Element;
    exitPictureInPicture(): Promise<void>;
    webkitExitFullscreen(): Promise<void>;
}
interface DocumentOrShadowRoot {
    readonly pictureInPictureElement: HTMLVideoElement | null;
    webkitFullscreenElement: Element;
}
