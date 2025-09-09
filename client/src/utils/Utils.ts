
import { AxiosResponseHeaders, RawAxiosResponseHeaders } from 'axios';

import useSettingsStore from '@/stores/SettingsStore';


/**
 * 共通ユーティリティ
 */
export default class Utils {

    // バージョン情報
    // ビルド時の環境変数 (vue.config.js に記載) から取得
    static readonly version: string = import.meta.env.KONOMITV_VERSION;

    // バックエンドの API のベース URL
    // Worker からも参照できるように self.location を使う
    static readonly api_base_url = (() => {
        if (import.meta.env.DEV === true) {
            // デバッグ時はポートを 7000 に強制する
            return `${self.location.protocol}//${self.location.hostname}:7000/api`;
        } else {
            // ビルド後は同じポートを使う
            return `${self.location.protocol}//${self.location.host}/api`;
        }
    })();

    // パフォーマンス最適化のため、apply28HourClock() で利用する正規表現を事前コンパイル
    private static readonly date_week_time_pattern = /(\d{4})\/(\d{2})\/(\d{2})\s+\((.)\)\s+([0-2]\d):(\d{2})(?::(\d{2}))?/g;
    private static readonly date_time_pattern = /(\d{4})\/(\d{2})\/(\d{2})\s+([0-2]\d):(\d{2})(?::(\d{2}))?/g;
    private static readonly month_day_time_pattern = /(\d{2})\/(\d{2})\s+([0-2]\d):(\d{2})(?::(\d{2}))?/g;
    private static readonly standalone_time_pattern = /(^|[^0-9])([0-2]\d):(\d{2})(?::(\d{2}))?/g;
    private static readonly time_quick_pattern = /([0-2]\d):\d{2}/;


    /**
     * アクセストークンを LocalStorage から取得する
     * @returns JWT アクセストークン（ログインしていない場合は null が返る）
     */
    static getAccessToken(): string | null {

        // LocalStorage の取得結果をそのまま返す
        // LocalStorage.getItem() はキーが存在しなければ（=ログインしていなければ）null を返す
        return localStorage.getItem('KonomiTV-AccessToken');
    }


    /**
     * アクセストークンを LocalStorage に保存する
     * @param access_token 発行された JWT アクセストークン
     */
    static saveAccessToken(access_token: string): void {

        // そのまま LocalStorage に保存
        localStorage.setItem('KonomiTV-AccessToken', access_token);
    }


    /**
     * アクセストークンを LocalStorage から削除する
     * アクセストークンを削除することで、ログアウト相当になる
     */
    static deleteAccessToken(): void {

        // LocalStorage に KonomiTV-AccessToken キーが存在しない
        if (localStorage.getItem('KonomiTV-AccessToken') === null) return;

        // KonomiTV-AccessToken キーを削除
        localStorage.removeItem('KonomiTV-AccessToken');
    }


    /**
     * ブラウザが実行されている OS に応じて、"Alt" または "Option" を返す
     * キーボードショートカットのコンビネーションキーの説明を OS によって分けるために使う
     * @returns ブラウザが実行されている OS が macOS なら Option を、それ以外なら Alt を返す
     */
    static AltOrOption(): 'Alt' | 'Option' {
        return Utils.isMacOS() ? 'Option' : 'Alt';
    }


    /**
     * ブラウザが実行されている OS に応じて、"Ctrl" または "Cmd" を返す
     * キーボードショートカットのコンビネーションキーの説明を OS によって分けるために使う
     * @returns ブラウザが実行されている OS が macOS なら Cmd を、それ以外なら Ctrl を返す
     */
    static CtrlOrCmd(): 'Ctrl' | 'Cmd' {
        return Utils.isMacOS() ? 'Cmd' : 'Ctrl';
    }


    /**
     * 28 時間表記を適用する
     * 与えられた文字列内の時刻表記 (HH:mm / HH:mm:ss / YYYY/MM/DD (dd) HH:mm[:ss] / YYYY/MM/DD HH:mm[:ss]) を検出し、
     * 0〜3 時台を 24〜27 に置換する。日付・曜日を含む場合は 1 日前に補正する。
     * @param text 入力文字列
     * @returns 変換後の文字列
     */
    static apply28HourClock(text: string): string {
        const settings_store = useSettingsStore();
        if (settings_store.settings.use_28hour_clock !== true) {
            return text;
        }

        // 時刻が含まれていなければ早期リターン（軽量化）
        if (Utils.time_quick_pattern.test(text) === false) {
            return text;
        }

        // ユーティリティ: 日付文字列 YYYY/MM/DD を 1 日戻す
        const prevDateStr = (y: number, m: number, d: number, withWeek: boolean): string => {
            const date = new Date(y, m - 1, d);
            date.setDate(date.getDate() - 1);
            const yy = date.getFullYear();
            const mm = String(date.getMonth() + 1).padStart(2, '0');
            const dd = String(date.getDate()).padStart(2, '0');
            if (withWeek) {
                const weeks = '日月火水木金土';
                const w = weeks[date.getDay()];
                return `${yy}/${mm}/${dd} (${w})`;
            }
            return `${yy}/${mm}/${dd}`;
        };

        // 1) YYYY/MM/DD (w) HH:mm[:ss]
        text = text.replace(Utils.date_week_time_pattern,
            (_m, y, m, d, _w, hh, mm, ss) => {
                const hour = parseInt(hh, 10);
                if (hour >= 0 && hour <= 3) {
                    const newDate = prevDateStr(parseInt(y, 10), parseInt(m, 10), parseInt(d, 10), true);
                    const newH = String(hour + 24).padStart(2, '0');
                    return `${newDate} ${newH}:${mm}${ss ? `:${ss}` : ''}`;
                }
                return `${y}/${m}/${d} (${_w}) ${hh}:${mm}${ss ? `:${ss}` : ''}`;
            }
        );

        // 2) YYYY/MM/DD HH:mm[:ss]
        text = text.replace(Utils.date_time_pattern,
            (_m, y, m, d, hh, mm, ss) => {
                const hour = parseInt(hh, 10);
                if (hour >= 0 && hour <= 3) {
                    const newDate = prevDateStr(parseInt(y, 10), parseInt(m, 10), parseInt(d, 10), false);
                    const newH = String(hour + 24).padStart(2, '0');
                    return `${newDate} ${newH}:${mm}${ss ? `:${ss}` : ''}`;
                }
                return `${y}/${m}/${d} ${hh}:${mm}${ss ? `:${ss}` : ''}`;
            }
        );

        // 3) MM/DD HH:mm[:ss]
        const baseYear = new Date().getFullYear();
        text = text.replace(Utils.month_day_time_pattern,
            (_m, m, d, hh, mm, ss) => {
                const hour = parseInt(hh, 10);
                if (hour >= 0 && hour <= 3) {
                    // 年は表示されないため、現在年を基準に日付計算のみ行う
                    const date = new Date(baseYear, parseInt(m, 10) - 1, parseInt(d, 10));
                    date.setDate(date.getDate() - 1);
                    const mm2 = String(date.getMonth() + 1).padStart(2, '0');
                    const dd2 = String(date.getDate()).padStart(2, '0');
                    const newH = String(hour + 24).padStart(2, '0');
                    return `${mm2}/${dd2} ${newH}:${mm}${ss ? `:${ss}` : ''}`;
                }
                return `${m}/${d} ${hh}:${mm}${ss ? `:${ss}` : ''}`;
            }
        );

        // 4) standalone HH:mm[:ss]
        text = text.replace(Utils.standalone_time_pattern,
            (_m, pre, hh, mm, ss) => {
                const hour = parseInt(hh, 10);
                if (hour >= 0 && hour <= 3) {
                    const newH = String(hour + 24).padStart(2, '0');
                    return `${pre}${newH}:${mm}${ss ? `:${ss}` : ''}`;
                }
                return `${pre}${hh}:${mm}${ss ? `:${ss}` : ''}`;
            }
        );

        return text;
    }


    /**
     * Axios のレスポンスヘッダを Headers (fetch) に変換する
     * @param headers Axios のレスポンスヘッダ
     * @returns Headers (fetch) オブジェクト
     */
    static convertAxiosHeadersToFetchHeaders(headers: RawAxiosResponseHeaders | AxiosResponseHeaders): Headers {
        const fetchHeaders = new Headers();
        for (const key in headers) {
            if (Object.prototype.hasOwnProperty.call(headers, key)) {
                fetchHeaders.append(key, headers[key] as string);
            }
        }
        return fetchHeaders;
    }


    /**
     * 再帰的にオブジェクトを凍結する
     * ref: https://unyacat.net/2021/01/20/vue-freeze-faster/
     * @param object 凍結するオブジェクト
     * @returns 再帰的に凍結されたオブジェクト
     */
    static deepObjectFreeze<T extends object>(object: T): T {
        Object.keys(object).forEach(prop => {
            if (typeof object[prop] === 'object' && !Object.isFrozen(object[prop])) Utils.deepObjectFreeze(object[prop]);
        });
        return Object.freeze(object);
    }


    /**
     * Blob に格納されているデータをブラウザにダウンロードさせる
     * @param blob Blob オブジェクト
     * @param filename 保存するファイル名
     */
    static downloadBlobData(blob: Blob, filename: string): void {

        // Blob URL を発行
        const blob_url = URL.createObjectURL(blob);

        // 画像をダウンロード
        const link = document.createElement('a');
        link.download = filename;
        link.href = blob_url;
        link.click();

        // Blob URL を破棄
        URL.revokeObjectURL(blob_url);
    }


    /**
     * innerHTML しても問題ないように HTML の特殊文字をエスケープする
     * PHP の htmlspecialchars() と似たようなもの
     * @param content HTML エスケープされてないテキスト
     * @returns HTML エスケープされたテキスト
     */
    static escapeHTML(content: string): string {

        // HTML エスケープが必要な文字
        // ref: https://www.php.net/manual/ja/function.htmlspecialchars.php
        const html_escape_table = {
            '&': '&amp;',
            '"': '&quot;',
            '\'': '&apos;',
            '<': '&lt;',
            '>': '&gt;',
        };

        // ref: https://qiita.com/noriaki/items/4bfef8d7cf85dc1035b3
        return content.replace(/[&"'<>]/g, (match) => {
            return html_escape_table[match];
        });
    }


    /**
     * バイト単位の数値をフォーマットする
     * @param bytes バイト数
     * @param decimal_places 小数点以下の桁数
     * @param gb_only GB 単位でのみフォーマットするかどうか
     * @returns フォーマットされた文字列 (例: 1.23KB)
     */
    static formatBytes(bytes: number, decimal_places: number = 2, gb_only: boolean = false): string {
        if (gb_only) {
            const gb_bytes = bytes / (1024 * 1024 * 1024);
            return `${gb_bytes.toFixed(decimal_places)}GB`;
        }

        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let unit_index = 0;

        while (bytes >= 1024 && unit_index < units.length - 1) {
            bytes /= 1024;
            unit_index++;
        }

        return `${bytes.toFixed(decimal_places)}${units[unit_index]}`;
    }


    /**
     * OAuth 連携時のポップアップを画面中央に表示するための windowFeatures 文字列を取得する
     * ref: https://qiita.com/catatsuy/items/babce8726ea78f5d25b1
     * @returns window.open() で使う windowFeatures 文字列
     */
    static getWindowFeatures(): string {

        // ポップアップウインドウのサイズ
        const popupSizeWidth = 650;
        const popupSizeHeight = window.screen.height >= 800 ? 800 : window.screen.height - 100;

        // ポップアップウインドウの位置
        const posTop = (window.screen.height - popupSizeHeight) / 2;
        const posLeft = (window.screen.width - popupSizeWidth) / 2;

        return `toolbar=0,status=0,top=${posTop},left=${posLeft},width=${popupSizeWidth},height=${popupSizeHeight},modal=yes,alwaysRaised=yes`;
    }


    /**
     * 現在フォーカスを持っている要素に指定された CSS クラスが付与されているか
     * @param class_name 存在を確認する CSS クラス名
     * @returns document.activeElement が class_name で指定したクラスを持っているかどうか
     */
    static hasActiveElementClass(class_name: string): boolean {
        if (document.activeElement === null) return false;
        return document.activeElement.classList.contains(class_name);
    }

    /**
     * デバイスの OS が Android かどうか
     * @returns デバイスの OS が Android なら true を返す
     */
    static isAndroid(): boolean {
        return /Android/i.test(navigator.userAgent);
    }


    /**
     * ブラウザが Firefox かどうか
     * @returns ブラウザが Firefox なら true を返す
     */
    static isFirefox(): boolean {
        return /Firefox/i.test(navigator.userAgent);
    }


    /**
     * ブラウザが Safari かどうか
     * @returns ブラウザが Safari なら true を返す
     */
    static isSafari(): boolean {
        return /Safari/i.test(navigator.userAgent) && !/Chrome/i.test(navigator.userAgent);
    }


    /**
     * デバイスの OS が macOS かどうか
     * キーボードショートカットで使うキーを OS によって分けるために使う
     * @returns デバイスの OS が macOS なら true を返す
     */
    static isMacOS(): boolean {
        // iPhone・iPad で純正キーボードを接続した場合も一応想定して、iPhone・iPad も含める
        return /iPhone|iPad|Macintosh/i.test(navigator.userAgent);
    }


    /**
     * モバイルデバイス (スマホ・タブレット) かどうかを User-Agent から判定する
     * @returns モバイルデバイス (スマホ・タブレット) なら true を返す
     */
    static isMobileDevice(): boolean {
        // Macintosh が入っているのは、iPadOS は既定でデスクトップ表示モードが有効になっていて、UA だけでは Mac と判別できないため
        // Mac にタッチパネル付きの機種は存在しないので、'ontouchend' in document で判定できる
        // Windows タブレットはマウスやキーボードを付けたら普通の PC になるケースもあって判断が非常に難しく、需要も少ないため除外している
        return /iPhone|iPad|iPod|Macintosh|Android|Mobile/i.test(navigator.userAgent) && 'ontouchend' in document;
    }


    /**
     * 表示端末がタッチデバイスかどうか (Utils.isMobileDevice() とは異なり、モバイルデバイスかどうかは問わない)
     * おそらく Windows タブレットや Chromebook なども含まれる
     * @returns タッチデバイスなら true を返す
     */
    static isTouchDevice(): boolean {
        return window.matchMedia('(hover: none)').matches;
    }


    /**
     * 表示画面がデスクトップかどうか (メディアクエリの定義は variables.scss と同一)
     * @returns デスクトップなら true を返す
     */
    static isDesktop(): boolean {
        return window.matchMedia('(min-width: 1280.01px)').matches;
    }


    /**
     * 表示画面がタブレット横画面かどうか (メディアクエリの定義は variables.scss と同一)
     * @returns タブレット横画面なら true を返す
     */
    static isTabletHorizontal(): boolean {
        return window.matchMedia('(min-width: 960.01px) and (max-width: 1280px) and (orientation: landscape)').matches;
    }


    /**
     * 表示画面がスマホ横画面かどうか (メディアクエリの定義は variables.scss と同一)
     * @returns スマホ横画面なら true を返す
     */
    static isSmartphoneHorizontal(): boolean {
        return window.matchMedia('(max-width: 960px) and (orientation: landscape)').matches;
    }


    /**
     * 表示画面がタブレット縦画面かどうか (メディアクエリの定義は variables.scss と同一)
     * @returns タブレット縦画面なら true を返す
     */
    static isTabletVertical(): boolean {
        return window.matchMedia('(min-width: 600.1px) and (max-width: 1280px) and (orientation: portrait)').matches;
    }


    /**
     * 表示画面がスマホ縦画面かどうか (メディアクエリの定義は variables.scss と同一)
     * @returns スマホ縦画面なら true を返す
     */
    static isSmartphoneVertical(): boolean {
        return window.matchMedia('(max-width: 600px) and (orientation: portrait)').matches;
    }


    /**
     * 任意の桁で切り捨てする
     * ref: https://qiita.com/nagito25/items/0293bc317067d9e6c560#comment-87f0855f388953843037
     * @param value 切り捨てする数値
     * @param base どの桁で切り捨てするか (-1 → 10の位 / 3 → 小数第3位）
     * @return 切り捨てした値
     */
    static mathFloor(value: number, base: number = 0): number {
        return Math.floor(value * (10**base)) / (10**base);
    }


    /**
     * setInterval() を Web Worker で実行する
     * 実際にコールバック関数が実行される環境自体はメインスレッドで、タブがバックグラウンドに回った場合でも Web Worker 上でコールバックが叩き起こされる
     * 通常タブがバックグラウンドに回ると setInterval() が勝手に間引かれてしまうので、その影響を受けない Web Worker から叩き起こすことで間引きを防ぐ (邪悪…)
     * ref: https://gist.github.com/kawaz/72f61d8389fed0e9d4e7dc9eb01b39c8
     * @param callback コールバック関数
     * @param interval インターバル (ミリ秒単位)
     * @param args コールバック関数に渡す引数 (可変長)
     * @returns setInterval を停止するための関数 (戻り値が本家 setInterval() と異なるので注意)
     */
    static setIntervalInWorker(callback: (...args: any[]) => void, interval: number = 1000, ...args: any[]): () => void {
        try {
            const worker_code = `
                self.addEventListener('message', msg => {
                    setInterval(() => self.postMessage(null), msg.data);
                });
            `;
            const worker = new Worker(`data:text/javascript;base64,${btoa(worker_code)}`);
            worker.onmessage = () => callback(...args);  // Web Worker 側から叩き起こしてコールバック関数を実行する
            worker.postMessage(interval);
            return () => worker.terminate();
        } catch (_) {
            // なんらかの理由で Web Worker が使えなければ通常の setInterval() を使う
            const timer_id = setInterval(callback, interval, ...args);
            return () => clearInterval(timer_id);
        }
    }


    /**
     * async/await で秒単位でスリープする
     * @param seconds 待機する秒数 (ミリ秒単位ではないので注意)
     * @returns Promise を返すので、await sleep(1); のように使う
     */
    static async sleep(seconds: number): Promise<number> {
        return await new Promise(resolve => setTimeout(resolve, seconds * 1000));
    }


    /**
     * 現在時刻の UNIX タイムスタンプ (秒単位) を取得する (デバッグ用)
     * @returns 現在時刻の UNIX タイムスタンプ (秒単位)
     */
    static time(): number {
        return Date.now() / 1000;
    }


    /**
     * 指定された値の型の名前を取得する
     * ref: https://qiita.com/amamamaou/items/ef0b797156b324bb4ef3
     * @returns 指定された値の型の名前
     */
    static typeof(value: any): string {
        return Object.prototype.toString.call(value).slice(8, -1).toLowerCase();
    }


    /**
     * 文字列中に含まれる URL をリンクの HTML に置き換える
     * @param text 置換対象の文字列
     * @returns URL をリンクに置換した文字列
     */
    static URLtoLink(text: string): string {

        // HTML の特殊文字で表示がバグらないように、事前に HTML エスケープしておく
        text = Utils.escapeHTML(text);

        // ref: https://www.softel.co.jp/blogs/tech/archives/6099
        const pattern = /(https?:\/\/[-A-Z0-9+&@#/%?=~_|!:,.;]*[-A-Z0-9+&@#/%=~_|])/ig;
        return text.replace(pattern, '<a href="$1" target="_blank">$1</a>');
    }


    /**
     * デバイスがオンラインになるまで待機する
     * @returns Promise を返すので、await waitUntilOnline(); のように使う
     */
    static async waitUntilOnline(): Promise<void> {
        return await new Promise(resolve => {
            window.addEventListener('online', () => resolve());
        });
    }
}
