
/**
 * 共通ユーティリティ
 */
export default class Utils {

    // バージョン情報
    // ビルド時の環境変数 (vue.config.js に記載) から取得
    static readonly version: string = process.env.VUE_APP_VERSION;

    // バックエンドの API のベース URL
    static readonly api_base_url = (() => {
        if (process.env.NODE_ENV === 'development') {
            // デバッグ時はポートを 7000 に強制する
            return `${window.location.protocol}//${window.location.hostname}:7000/api`;
        } else {
            // ビルド後は同じポートを使う
            return `${window.location.protocol}//${window.location.host}/api`;
        }
    })();

    // デフォルトの設定値
    // ここを変えたときはサーバー側の app.schemas も変更すること
    static readonly default_settings = {

        // ピン留めしているチャンネルの ID (ex: gr011) が入るリスト
        pinned_channel_ids: [] as string[],

        // テレビのストリーミング画質（1080p）
        tv_streaming_quality: '1080p' as ('1080p' | '810p' | '720p' | '540p' | '480p' | '360p' | '240p'),

        // 前回視聴画面を開いた際にパネルが表示されていたかどうか
        is_latest_panel_display: true as boolean,

        // 既定のパネルの表示状態（前回の状態を復元する）
        panel_display_state: 'RestorePreviousState' as ('RestorePreviousState' | 'AlwaysDisplay' | 'AlwaysFold'),

        // 既定で表示されるパネルのタブ（番組情報タブ）
        panel_active_tab: 'Program' as ('Program' | 'Channel' | 'Comment' | 'Twitter'),

        // コメントの速さ (1倍)
        comment_speed_rate: 1 as number,

        // コメントのフォントサイズ (34px)
        comment_font_size: 34 as number,

        // コメントの遅延時間 (1秒)
        comment_delay_time: 1 as number,
    };


    /**
     * プレイヤーの背景画像をランダムで取得し、その URL を返す
     * @returns ランダムで設定されたプレイヤーの背景画像の URL
     */
    static generatePlayerBackgroundURL(): string {
        const background_count = 12;  // 12種類から選択
        const random = (Math.floor(Math.random() * background_count) + 1);
        return `/assets/images/player-backgrounds/${random.toString().padStart(2, '0')}.jpg`;
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
        const settings: object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utils.default_settings;

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
        const settings: object = JSON.parse(localStorage.getItem('KonomiTV-Settings')) || Utils.default_settings;

        // そのキーが default_settings に定義されているときだけ
        // バージョン違いなどで LocalStorage には登録されていないキーだが default_settings には登録されているケースが発生し得るため
        if (key in this.default_settings) {

            // 設定値を新しい値で置き換え
            settings[key] = value;

            // LocalStorage に保存
            localStorage.setItem('KonomiTV-Settings', JSON.stringify(settings));
        }
    }
}
