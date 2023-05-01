
import axios from 'axios';

import Utils from '@/utils';


// Axios のインスタンスを作成
const axios_instance = axios.create();

// HTTP リクエスト前に割り込んで行われる処理
axios_instance.interceptors.request.use((config) => {

    // API のベース URL を設定 (config.baseURL が指定されていない場合のみ)
    if (config.baseURL === undefined) {
        config.baseURL = Utils.api_base_url;
    }

    // 外部サイトへの HTTP リクエストでは実行しない
    if (config.url?.startsWith('http') === false) {

        // アクセストークンが取得できたら（=ログインされていれば）
        // 取得したアクセストークンを Authorization ヘッダーに Bearer トークンとしてセット
        // これを忘れると（当然ながら）ログインしていない扱いになる
        const access_token = Utils.getAccessToken();
        if (access_token !== null) {
            config.headers['Authorization'] = `Bearer ${access_token}`;
        }

        // KonomiTV クライアントのバージョンを設定
        // 今のところ使わないが、将来的にクライアントとサーバーを分離することを見据えて念のため
        config.headers['X-KonomiTV-Version'] = Utils.version;
    }

    // タイムアウト時間を30秒に設定
    config.timeout = 30 * 1000;

    return config;
});

export default axios_instance;
