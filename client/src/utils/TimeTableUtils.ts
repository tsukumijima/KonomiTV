
import type { Dayjs } from 'dayjs';

import { ITimeTableGenreColors, TimeTableGenreHighlightColor, TimeTableSizeOption } from '@/stores/SettingsStore';
import { dayjs } from '@/utils';


/**
 * デバイスタイプを表す型
 */
export type DeviceType = 'PC' | 'Tablet' | 'Smartphone';


/**
 * 番組表用のユーティリティクラス
 */
export class TimeTableUtils {

    /**
     * REGZA 風の時刻スケール背景色
     * 4時〜27時 (翌3時) までの24色を定義
     * 深夜は深い色、朝は緑〜青緑、昼は水色〜淡い青、夕方は紫〜ピンク、夜は赤紫〜深紫
     */
    static readonly TIME_SCALE_COLORS: { [hour: number]: string } = {
        // 早朝 (深い緑〜緑系)
        4: '#1a4d3a',
        5: '#2d5a4a',
        6: '#3d6a5a',
        7: '#4d7a6a',

        // 午前 (青緑〜水色系)
        8: '#3d6a7a',
        9: '#4d7a8a',
        10: '#5d8a9a',
        11: '#6d9aaa',

        // 昼 (水色〜薄い青紫系)
        12: '#7daaba',
        13: '#8db0c0',
        14: '#9db0c8',
        15: '#a8b0d0',

        // 夕方 (紫〜ピンク紫系)
        16: '#9a8ab0',
        17: '#a07aa8',
        18: '#a86a9a',
        19: '#b05a8a',

        // 夜 (赤紫〜深紫系)
        20: '#8a4a7a',
        21: '#7a4a6a',
        22: '#6a4a5a',
        23: '#5a4a5a',

        // 深夜 (濃い紫〜藍色系 / 28時間表記対応)
        24: '#4a4a6a',
        25: '#3a4a5a',
        26: '#2a4a4a',
        27: '#1a4a3a',

        // 0〜3時は24〜27時と同じ色を使用 (28時間表記オフの場合)
        0: '#4a4a6a',
        1: '#3a4a5a',
        2: '#2a4a4a',
        3: '#1a4a3a',
    };

    /**
     * ジャンルハイライトカラーの定義
     * REGZA ブルーレイレコーダーの番組表を参考にした配色
     */
    static readonly GENRE_HIGHLIGHT_COLORS: { [key in TimeTableGenreHighlightColor]: { highlight: string; background: string } } = {
        White: {
            highlight: '#ffffff',
            background: '#f8f8f8',
        },
        Yellow: {
            highlight: '#ffeb3b',
            background: '#fffde7',
        },
        Lime: {
            highlight: '#8bc34a',
            background: '#f1f8e9',
        },
        Blue: {
            highlight: '#03a9f4',
            background: '#e1f5fe',
        },
        Pink: {
            highlight: '#b55cd6',
            background: '#f2e6fb',
        },
        Red: {
            highlight: '#f44336',
            background: '#ffebee',
        },
        Orange: {
            highlight: '#ff9800',
            background: '#fff3e0',
        },
        Brown: {
            highlight: '#795548',
            background: '#efebe9',
        },
        Teal: {
            highlight: '#009688',
            background: '#e0f2f1',
        },
    };

    /**
     * 番組がない領域の背景色 (灰色)
     */
    static readonly EMPTY_CELL_BACKGROUND_COLOR = '#616161';

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
     * 時刻からその時刻の背景色を取得する
     * @param hour 時刻 (0〜39)
     * @returns 背景色
     */
    static getTimeScaleColor(hour: number): string {
        // 28以上の時刻 (翌日4時〜15時) は24を引いて通常の時刻として扱う
        // 例: 28時 → 4時の色、32時 → 8時の色
        if (hour >= 28) {
            const normalized_hour = hour - 24;
            return this.TIME_SCALE_COLORS[normalized_hour] || this.TIME_SCALE_COLORS[4];
        }
        // 0〜27 の範囲に正規化
        const normalized_hour = ((hour % 28) + 28) % 28;
        return this.TIME_SCALE_COLORS[normalized_hour] || this.TIME_SCALE_COLORS[0];
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

        // ユーザー設定から色を取得
        // 設定のキーは「・」(中黒) を使用しているため、API から返されるジャンル名の
        // 「/」を「・」に置換してマッチングを試みる
        // 例: API が "ニュース/報道" を返す場合 → "ニュース・報道" に変換して照合
        const genre_colors_map = genre_colors as unknown as Record<string, TimeTableGenreHighlightColor>;

        // まずそのまま照合を試みる
        if (genre_colors_map[genre_major] !== undefined) {
            return this.GENRE_HIGHLIGHT_COLORS[genre_colors_map[genre_major]];
        }

        // 「/」を「・」に置換して照合を試みる (API が / 区切りで返す場合への対応)
        const normalized_with_dot = genre_major.replace(/\//g, '・');
        if (genre_colors_map[normalized_with_dot] !== undefined) {
            return this.GENRE_HIGHLIGHT_COLORS[genre_colors_map[normalized_with_dot]];
        }

        // 「・」を「/」に置換して照合を試みる (逆のケースへの対応)
        const normalized_with_slash = genre_major.replace(/・/g, '/');
        if (genre_colors_map[normalized_with_slash] !== undefined) {
            return this.GENRE_HIGHLIGHT_COLORS[genre_colors_map[normalized_with_slash]];
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
     * 1日分の番組表の総高さを計算する (24時間分)
     * @param hour_height 1時間あたりの高さ (px)
     * @returns 総高さ (px)
     */
    static calculateTotalHeight(hour_height: number): number {
        return this.CHANNEL_HEADER_HEIGHT + (24 * hour_height);
    }


    /**
     * Y座標から時刻を逆算する
     * @param y_position Y座標 (px)
     * @param day_start_time その日の開始時刻 (4:00)
     * @param hour_height 1時間あたりの高さ (px)
     * @returns 時刻
     */
    static calculateTimeFromY(
        y_position: number,
        day_start_time: Dayjs,
        hour_height: number,
        channel_header_height: number = TimeTableUtils.CHANNEL_HEADER_HEIGHT,
    ): Dayjs {
        // ヘッダー分を引いてから計算
        const adjusted_y = y_position - channel_header_height;
        const elapsed_hours = adjusted_y / hour_height;
        const elapsed_ms = elapsed_hours * 60 * 60 * 1000;

        const result = day_start_time.add(elapsed_ms, 'millisecond');
        return result;
    }


    /**
     * 時刻を 28 時間表記に変換する
     * @param date 時刻
     * @param use_28hour_clock 28時間表記を使用するか
     * @returns 表示用の時刻文字列 (HH:mm 形式)
     */
    static formatTime(date: Dayjs, use_28hour_clock: boolean): string {
        let hours = date.hour();
        const minutes = date.minute();

        // 28時間表記の場合、0〜3時を 24〜27時に変換
        if (use_28hour_clock && hours >= 0 && hours < 4) {
            hours += 24;
        }

        const hours_str = hours.toString().padStart(2, '0');
        const minutes_str = minutes.toString().padStart(2, '0');

        return `${hours_str}:${minutes_str}`;
    }


    /**
     * 時刻を時のみの 28 時間表記に変換する
     * @param hour 時刻 (0〜23)
     * @param use_28hour_clock 28時間表記を使用するか
     * @returns 表示用の時刻 (数値)
     */
    static formatHour(hour: number, use_28hour_clock: boolean): number {
        // 28時間表記の場合、0〜3時を 24〜27時に変換
        if (use_28hour_clock && hour >= 0 && hour < 4) {
            return hour + 24;
        }
        return hour;
    }


    /**
     * 現在のデバイスタイプを判定する
     * @returns デバイスタイプ (PC/Tablet/Smartphone)
     */
    static getDeviceType(): DeviceType {
        const width = window.innerWidth;

        if (width < 600) {
            return 'Smartphone';
        } else if (width < 1280) {
            return 'Tablet';
        } else {
            return 'PC';
        }
    }


    /**
     * throttle 関数: 指定した間隔で関数の実行を制限する
     * @param func 実行する関数
     * @param limit 実行間隔 (ms)
     * @returns throttle された関数
     */
    static throttle<T extends (...args: any[]) => any>(
        func: T,
        limit: number,
    ): (...args: Parameters<T>) => void {
        let last_call = 0;
        let timeout_id: ReturnType<typeof setTimeout> | null = null;

        return function (this: any, ...args: Parameters<T>) {
            const now = dayjs().valueOf();
            const remaining = limit - (now - last_call);

            if (remaining <= 0) {
                if (timeout_id !== null) {
                    clearTimeout(timeout_id);
                    timeout_id = null;
                }
                last_call = now;
                func.apply(this, args);
            } else if (timeout_id === null) {
                timeout_id = setTimeout(() => {
                    last_call = dayjs().valueOf();
                    timeout_id = null;
                    func.apply(this, args);
                }, remaining);
            }
        };
    }


    /**
     * debounce 関数: 指定した時間が経過するまで関数の実行を遅延する
     * @param func 実行する関数
     * @param wait 待機時間 (ms)
     * @returns debounce された関数
     */
    static debounce<T extends (...args: any[]) => any>(
        func: T,
        wait: number,
    ): (...args: Parameters<T>) => void {
        let timeout_id: ReturnType<typeof setTimeout> | null = null;

        return function (this: any, ...args: Parameters<T>) {
            if (timeout_id !== null) {
                clearTimeout(timeout_id);
            }
            timeout_id = setTimeout(() => {
                func.apply(this, args);
            }, wait);
        };
    }
}

export default TimeTableUtils;
