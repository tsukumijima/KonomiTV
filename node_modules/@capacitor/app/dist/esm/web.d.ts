import { WebPlugin } from '@capacitor/core';
import type { AppInfo, AppPlugin, AppLaunchUrl, AppState } from './definitions';
export declare class AppWeb extends WebPlugin implements AppPlugin {
    constructor();
    exitApp(): Promise<void>;
    getInfo(): Promise<AppInfo>;
    getLaunchUrl(): Promise<AppLaunchUrl>;
    getState(): Promise<AppState>;
    minimizeApp(): Promise<void>;
    toggleBackButtonHandler(): Promise<void>;
    private handleVisibilityChange;
}
