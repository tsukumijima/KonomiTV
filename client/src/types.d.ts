
// ***** ブラウザの JavaScript API のうち、開発時点でマイナーすぎて @types が定義されていない API の型定義 *****

// location.reload() の forceReload 引数
// ref: https://developer.mozilla.org/en-US/docs/Web/API/Location/reload
interface Location {
    reload(forceReload?: boolean): void;
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
