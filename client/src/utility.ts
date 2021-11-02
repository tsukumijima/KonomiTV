
/**
 * ユーティリティ
 */
export default class Utility {

    // デフォルトの設定値
    static default_settings = {

        // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
        pinned_channel_ids: [] as string[],

    };

    /**
     * 設定を LocalStorage に取得する
     * @param key 設定のキー名
     * @returns 設定されている値
     */
    static getSettingsItem(key: string): any | null {

        // LocalStorage から KonomiTV-Settings を取得
        // データは JSON で管理し、LocalStorage 上の一つのキーにまとめる
        // キーが存在しない場合はデフォルトの設定値を使う
        const settings:object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utility.default_settings;

        // そのキーが定義されているときだけ、設定値を返す
        if (key in settings) {
            return settings[key];
        } else {
            return null;
        }
    }

    /**
     * 設定を LocalStorage に保存する
     * @param key 設定のキー名
     * @param value 設定する値
     */
    static setSettingsItem(key: string, value: any): void {

        // LocalStorage から KonomiTV-Settings を取得
        const settings:object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utility.default_settings;

        // そのキーが定義されているときだけ
        if (key in settings) {

            // 設定値を新しい値で置き換え
            settings[key] = value;

            // LocalStorage に保存
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));
        }
    }
}
