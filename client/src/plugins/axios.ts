
import axios from 'axios';

import useUserStore from '@/store/UserStore';
import Utils from '@/utils';

// ref: https://note.com/quoizunda/n/nb62e13e73499

// Axios のインスタンスを作成
const axios_instance = axios.create();

// HTTP リクエスト前に割り込んで行われる処理
axios_instance.interceptors.request.use((config) => {

    // API のベース URL を設定 (config.baseURL が指定されていない場合のみ)
    if (config.baseURL === undefined) {
        config.baseURL = Utils.api_base_url;
    }

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

    // タイムアウト時間を30秒に設定
    config.timeout = 30 * 1000;

    return config;
});

// HTTP リクエスト後に割り込んで行われる処理
axios_instance.interceptors.response.use(
    (response) => response,
    (error) => {

        // 401 Unauthorized が返ってきたら、ログアウトさせる
        // JWT の有効期限が切れたときに発生する
        if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
            const user_store = useUserStore();
            user_store.logout(true);
        }

        // エラーをそのまま返す
        return Promise.reject(error);
    }
);

export default axios_instance;
