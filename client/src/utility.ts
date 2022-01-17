
/**
 * ユーティリティ
 */
export default class Utility {

    // デフォルトの設定値
    static readonly default_settings = {

        // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
        pinned_channel_ids: [] as string[],

        // テレビのストリーミング画質（1080p）
        tv_streaming_quality: '1080p' as ('1080p' | '810p' | '720p' | '540p' | '480p' | '360p' | '240p'),

        // 前回視聴画面を開いた際にパネルが表示されていたかどうか
        is_latest_panel_display: true as boolean,

        // 既定のパネルの表示状態（常に表示する）
        panel_display_state: 'AlwaysDisplay' as ('AlwaysDisplay' | 'AlwaysFold' | 'RestorePreviousState'),

        // 既定で表示されるパネルのタブ（番組情報タブ）
        panel_active_tab: 'Program' as ('Program' | 'Channel' | 'Comment' | 'Twitter'),
    };

    /**
     * プレイヤーの背景画像をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景画像の URL
     */
    static generatePlayerBackgroundURL(): string {
        const background_count = 12;  // 12種類から選択
        const random = (Math.floor(Math.random() * background_count) + 1);
        return `/assets/img/player-backgrounds/${random.toString().padStart(2, '0')}.jpg`;
    }

    /**
     * 設定を LocalStorage から取得する
     * @param key 設定のキー名
     * @returns 設定されている値
     */
    static getSettingsItem(key: string): any | null {

        // LocalStorage から KonomiTV-Settings を取得
        // データは JSON で管理し、LocalStorage 上の一つのキーにまとめる
        // キーが存在しない場合はデフォルトの設定値を使う
        const settings:object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utility.default_settings;

        // そのキーが保存されているときだけ、設定値を返す
        if (key in settings) {
            return settings[key];
        } else {
            // デフォルトの設定値にあればそれを使う
            if (key in this.default_settings) {
                return this.default_settings[key];
            } else {
                return null;
            }
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

        // そのキーがデフォルトの設定値に定義されているときだけ
        // バージョン違いなどで settings には登録されていないキーだが default_settings には登録されているケースが発生し得るため
        if (key in this.default_settings) {

            // 設定値を新しい値で置き換え
            settings[key] = value;

            // LocalStorage に保存
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));
        }
    }
}
