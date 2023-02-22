
import axios from 'axios';

import Utils from '@/utils';

// ref: https://note.com/quoizunda/n/nb62e13e73499

// Axios のインスタンスを作成
const axios_instance = axios.create();

// HTTP リクエスト前に割り込んで行われる処理
axios_instance.interceptors.request.use((config) => {

    // API のベース URL を設定
    // BaseURL が明示的に指定されているときは設定しない
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

    return config;
});

// HTTP リクエスト後に割り込んで行われる処理
axios_instance.interceptors.response.use(
    (response) => response,
    (error) => {

        // 401 Unauthorized が返ってきたら、アクセストークンを削除してログアウト状態にする
        // JWT の有効期限が切れたときに発生する
        // アクセストークンが削除されていないと、余計なリクエストが発生してしまう
        if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
            Utils.deleteAccessToken();
        }

        // エラーをそのまま返す
        return Promise.reject(error);
    }
);

// ここで返したインスタンスを VueAxios (Vue.axios) に設定する
export default axios_instance;
