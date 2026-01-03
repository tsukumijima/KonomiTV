
import type { Dayjs } from 'dayjs';

import { ITimeTableGenreColors, TimeTableGenreHighlightColor, TimeTableSizeOption } from '@/stores/SettingsStore';

/**
 * デバイスタイプを表す型
 */
export type DeviceType = 'PC' | 'Tablet' | 'Smartphone';


/**
 * 番組表用のユーティリティクラス
 */
export class TimeTableUtils {

    /**
     * ジャンルハイライトカラーの定義
     * REGZA ブルーレイレコーダーの番組表を参考にした配色
     * 実際の色指定は CSS 変数に寄せる
     */
    static readonly GENRE_HIGHLIGHT_COLORS: { [key in TimeTableGenreHighlightColor]: { highlight: string; background: string } } = {
        White: {
            highlight: 'var(--timetable-genre-highlight-white)',
            background: 'var(--timetable-genre-background-white)',
        },
        Pink: {
            highlight: 'var(--timetable-genre-highlight-pink)',
            background: 'var(--timetable-genre-background-pink)',
        },
        Red: {
            highlight: 'var(--timetable-genre-highlight-red)',
            background: 'var(--timetable-genre-background-red)',
        },
        Orange: {
            highlight: 'var(--timetable-genre-highlight-orange)',
            background: 'var(--timetable-genre-background-orange)',
        },
        Yellow: {
            highlight: 'var(--timetable-genre-highlight-yellow)',
            background: 'var(--timetable-genre-background-yellow)',
        },
        Lime: {
            highlight: 'var(--timetable-genre-highlight-lime)',
            background: 'var(--timetable-genre-background-lime)',
        },
        Teal: {
            highlight: 'var(--timetable-genre-highlight-teal)',
            background: 'var(--timetable-genre-background-teal)',
        },
        Cyan: {
            highlight: 'var(--timetable-genre-highlight-cyan)',
            background: 'var(--timetable-genre-background-cyan)',
        },
        Blue: {
            highlight: 'var(--timetable-genre-highlight-blue)',
            background: 'var(--timetable-genre-background-blue)',
        },
        Ochre: {
            highlight: 'var(--timetable-genre-highlight-ochre)',
            background: 'var(--timetable-genre-background-ochre)',
        },
        Brown: {
            highlight: 'var(--timetable-genre-highlight-brown)',
            background: 'var(--timetable-genre-background-brown)',
        },
    };

    /**
     * デバイスタイプごとのチャンネル列の幅 (px)
     */
    static readonly CHANNEL_WIDTH: { [deviceType in DeviceType]: { [key in TimeTableSizeOption]: number } } = {
        PC: {
            Wide: 180,
            Normal: 150,
            Narrow: 120,
        },
        Tablet: {
            Wide: 150,
            Normal: 120,
            Narrow: 100,
        },
        Smartphone: {
            Wide: 120,
            Normal: 100,
            Narrow: 80,
        },
    };

    /**
     * デバイスタイプごとの1時間あたりの高さ (px)
     */
    static readonly HOUR_HEIGHT: { [deviceType in DeviceType]: { [key in TimeTableSizeOption]: number } } = {
        PC: {
            Wide: 240,
            Normal: 180,
            Narrow: 120,
        },
        Tablet: {
            Wide: 200,
            Normal: 150,
            Narrow: 100,
        },
        Smartphone: {
            Wide: 160,
            Normal: 120,
            Narrow: 80,
        },
    };

    /**
     * 時刻スケールの幅 (px)
     */
    static readonly TIME_SCALE_WIDTH = 50;

    /**
     * 時刻スケールの幅（スマホ縦画面用、px）
     */
    static readonly TIME_SCALE_WIDTH_SMARTPHONE_VERTICAL = 30;

    /**
     * チャンネルヘッダーの高さ (px)
     */
    static readonly CHANNEL_HEADER_HEIGHT = 54;

    /**
     * チャンネルヘッダーの高さを取得する
     * @param channel_width チャンネル列の幅 (px)
     * @returns チャンネルヘッダーの高さ (px)
     */
    static getChannelHeaderHeight(channel_width: number): number {
        const logo_width = Math.round(Math.min(46, Math.max(32, channel_width * 0.3)));
        const logo_height = Math.round(logo_width * (2 / 3));
        const header_height = logo_height + 20;
        return Math.max(50, header_height);
    }



    /**
     * ジャンル大分類からハイライト色と背景色を取得する
     * @param genre_major ジャンル大分類 (例: "ニュース・報道", "アニメ・特撮")
     * @param genre_colors ユーザー設定のジャンル色マップ
     * @returns ハイライト色と背景色のオブジェクト
     */
    static getGenreColors(
        genre_major: string | undefined,
        genre_colors: ITimeTableGenreColors,
    ): { highlight: string; background: string } {
        // ジャンルが設定されていない場合は白を返す
        if (genre_major === undefined) {
            return this.GENRE_HIGHLIGHT_COLORS.White;
        }

        // まずそのまま照合を試みる
        if (genre_colors[genre_major] !== undefined) {
            return this.GENRE_HIGHLIGHT_COLORS[genre_colors[genre_major]];
        }

        // 「/」を「・」に置換して照合を試みる
        const normalized_with_dot = genre_major.replace(/\//g, '・');
        if (genre_colors[normalized_with_dot] !== undefined) {
            return this.GENRE_HIGHLIGHT_COLORS[genre_colors[normalized_with_dot]];
        }

        // 「・」を「/」に置換して照合を試みる (逆のケースへの対応)
        const normalized_with_slash = genre_major.replace(/・/g, '/');
        if (genre_colors[normalized_with_slash] !== undefined) {
            return this.GENRE_HIGHLIGHT_COLORS[genre_colors[normalized_with_slash]];
        }

        // どちらもマッチしない場合は白を返す
        return this.GENRE_HIGHLIGHT_COLORS.White;
    }


    /**
     * デバイスタイプに応じたチャンネル列の幅を取得する
     * @param size_option サイズオプション (Wide/Normal/Narrow)
     * @param device_type デバイスタイプ (PC/Tablet/Smartphone)
     * @returns チャンネル列の幅 (px)
     */
    static getChannelWidth(
        size_option: TimeTableSizeOption,
        device_type: DeviceType,
    ): number {
        return this.CHANNEL_WIDTH[device_type][size_option];
    }


    /**
     * デバイスタイプに応じた1時間あたりの高さを取得する
     * @param size_option サイズオプション (Wide/Normal/Narrow)
     * @param device_type デバイスタイプ (PC/Tablet/Smartphone)
     * @returns 1時間あたりの高さ (px)
     */
    static getHourHeight(
        size_option: TimeTableSizeOption,
        device_type: DeviceType,
    ): number {
        return this.HOUR_HEIGHT[device_type][size_option];
    }


    /**
     * デバイスタイプに応じた時刻スケールの幅を取得する
     * @param device_type デバイスタイプ (PC/Tablet/Smartphone)
     * @param is_smartphone_vertical スマホ縦画面かどうか
     * @returns 時刻スケールの幅 (px)
     */
    static getTimeScaleWidth(
        device_type: DeviceType,
        is_smartphone_vertical: boolean,
    ): number {
        if (device_type === 'Smartphone' && is_smartphone_vertical) {
            return this.TIME_SCALE_WIDTH_SMARTPHONE_VERTICAL;
        }
        return this.TIME_SCALE_WIDTH;
    }


    /**
     * 番組の開始時刻から表示位置 (Y座標) を計算する
     * @param start_time 番組の開始時刻
     * @param day_start_time その日の開始時刻 (4:00)
     * @param hour_height 1時間あたりの高さ (px)
     * @returns Y座標 (px)
     */
    static calculateProgramY(
        start_time: Dayjs,
        day_start_time: Dayjs,
        hour_height: number,
        channel_header_height: number = TimeTableUtils.CHANNEL_HEADER_HEIGHT,
    ): number {
        // 開始時刻からその日の開始時刻までの経過秒数を計算
        const elapsed_ms = start_time.valueOf() - day_start_time.valueOf();
        const elapsed_hours = elapsed_ms / (1000 * 60 * 60);

        // Y座標を計算 (ヘッダー分を加算)
        return channel_header_height + (elapsed_hours * hour_height);
    }


    /**
     * 番組の長さから表示高さを計算する
     * @param duration_seconds 番組の長さ (秒)
     * @param hour_height 1時間あたりの高さ (px)
     * @returns 表示高さ (px)
     */
    static calculateProgramHeight(
        duration_seconds: number,
        hour_height: number,
    ): number {
        const duration_hours = duration_seconds / 3600;
        return duration_hours * hour_height;
    }


    /**
     * 現在時刻から現在時刻バーの Y 座標を計算する
     * @param current_time 現在時刻
     * @param day_start_time その日の開始時刻 (4:00)
     * @param hour_height 1時間あたりの高さ (px)
     * @returns Y座標 (px)
     */
    static calculateCurrentTimeY(
        current_time: Dayjs,
        day_start_time: Dayjs,
        hour_height: number,
        channel_header_height: number = TimeTableUtils.CHANNEL_HEADER_HEIGHT,
    ): number {
        return this.calculateProgramY(current_time, day_start_time, hour_height, channel_header_height);
    }


    /**
     * 現在のデバイスタイプを判定する
     * タブレット横画面は幅的に PC 版のレイアウトが適切なため、'PC' として扱う
     * @returns デバイスタイプ (PC/Tablet/Smartphone)
     */
    static getDeviceType(): DeviceType {
        const width = window.innerWidth;
        const isLandscape = window.matchMedia('(orientation: landscape)').matches;

        if (width < 600) {
            return 'Smartphone';
        } else if (width < 1280) {
            // タブレット横画面 (960px以上の幅 & 横向き) は PC 扱いにする
            if (isLandscape && width >= 960) {
                return 'PC';
            }
            return 'Tablet';
        } else {
            return 'PC';
        }
    }


}
