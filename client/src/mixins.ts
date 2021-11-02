
import Vue from 'vue';

// すべてのページで使うグローバルなプロパティを定義
export default Vue.extend({
    data() {

        // バックエンドの API のベース URL
        let api_base_url = `${window.location.protocol}//${window.location.host}/api`;
        if (process.env.NODE_ENV === 'development') {
            // デバッグ時はポートを 7000 に強制する
            api_base_url = `${window.location.protocol}//${window.location.hostname}:7000/api`;
        }

        // バージョン
        const version = process.env.VUE_APP_VERSION;

        return {

            // 設定値
            api_base_url: api_base_url,
            version: version,
        }
    }
});
