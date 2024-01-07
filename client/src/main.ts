
import { Icon } from '@iconify/vue';
import FloatingVue from 'floating-vue';
import 'floating-vue/dist/style.css';
import { createPinia } from 'pinia';
import { polyfill as SeamlessScrollPolyfill } from 'seamless-scroll-polyfill';
import { useRegisterSW } from 'virtual:pwa-register/vue';
import { createApp } from 'vue';
import VueVirtualScroller from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';

import App from '@/App.vue';
import Message from '@/message';
import vuetify from '@/plugins/vuetify';
import router from '@/router';
import useSettingsStore, { setLocalStorageSettings } from '@/stores/SettingsStore';
import Utils from '@/utils';


// スムーズスクロール周りの API の polyfill を適用
// Element.scrollInfoView() のオプション指定を使うために必要
SeamlessScrollPolyfill();

// ***** Vue アプリケーションの初期化 *****

// Vue アプリケーションを作成
const app = createApp(App);

// Pinia を使う
// ref: https://pinia.vuejs.org/cookbook/options-api.html
app.use(createPinia());

// Iconify (アイコン) のグローバルコンポーネントを登録
app.component('Icon', Icon);

// Vue Router を使う
app.use(router);

// Vuetify を使う
app.use(vuetify);

// vue-virtual-scroller を使う
app.use(VueVirtualScroller);

// FloatingVue を使う
// タッチデバイスでは無効化する
// ref: https://v-tooltip.netlify.app/guide/config#default-values
FloatingVue.options.themes.tooltip.triggers = Utils.isTouchDevice() ? [] : ['hover', 'focus', 'touch'];
FloatingVue.options.themes.tooltip.delay.show = 0;
FloatingVue.options.offset = [0, 7];
app.use(FloatingVue);

// マウントを実行
app.mount('#app');

// ***** Service Worker のイベントを登録 *****

const { updateServiceWorker } = useRegisterSW({
    // Service Worker の登録に成功したとき
    onRegisteredSW(registration) {
        console.log('Service worker has been registered.');
    },
    // Service Worker の登録に失敗したとき
    onRegisterError(error) {
        console.error('Error during service worker registration:', error);
    },
    // PWA がオフラインで利用可能になったとき
    onOfflineReady() {
        console.log('Content has been cached for offline use.');
    },
    // PWA の更新が必要なとき
    async onNeedRefresh() {
        console.log('New content is available; please refresh.');
        // リロードするまでトーストを表示し続ける
        Message.show('クライアントが新しいバージョンに更新されました。5秒後にリロードします。', 10);  // 10秒間表示
        await Utils.sleep(5);  // 5秒待つ
        // PWA (Service Worker) を更新し、ページをリロードする
        updateServiceWorker(true);
    },
});

// ***** 設定データの同期 *****

// 設定データをサーバーにアップロード中かどうか
let is_uploading_settings = false;

// 設定データの変更を監視する
const settings_store = useSettingsStore();
settings_store.$subscribe(async () => {

    // 設定データをアップロード中の場合は何もしない
    if (is_uploading_settings === true) {
        return;
    }

    // 設定データを LocalStorage に保存
    console.log('Client Settings Changed:', settings_store.settings);
    setLocalStorageSettings(settings_store.settings);

    // このクライアントの設定をサーバーに同期する (ログイン時かつ同期が有効な場合のみ実行される)
    await settings_store.syncClientSettingsToServer();

}, {detached: true});

// ログイン時かつ設定の同期が有効な場合、ページ遷移に関わらず、常に3秒おきにサーバーから設定を取得する
// 初回のページレンダリングに間に合わないのは想定内（同期の完了を待つこともできるが、それだと表示速度が遅くなるのでしょうがない）
window.setInterval(async () => {
    if (Utils.getAccessToken() !== null && settings_store.settings.sync_settings === true) {

        // サーバーに保存されている設定データをこのクライアントに同期する
        is_uploading_settings = true;
        await settings_store.syncClientSettingsFromServer();
        is_uploading_settings = false;

        // 設定データを LocalStorage に保存
        setLocalStorageSettings(settings_store.settings);
    }
}, 3 * 1000);  // 3秒おき
