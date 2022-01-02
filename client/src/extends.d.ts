
// ブラウザの JavaScript API のうち、開発時点でマイナーすぎて @types が定義されていない API の型を定義

// TypeScript types for the Picture-in-Picture API
// ref: https://gist.github.com/Rendez/6e088e8713f47e87ab04efcc22f365b1

interface PictureInPictureResizeEvent extends Event {
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

interface Document {
    readonly pictureInPictureEnabled: boolean;
    exitPictureInPicture(): Promise<void>;
}

interface DocumentOrShadowRoot {
    readonly pictureInPictureElement: HTMLVideoElement | null;
}
