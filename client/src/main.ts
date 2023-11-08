
import { Icon } from '@iconify/vue2';
import '@mdi/font/css/materialdesignicons.css';
import { createPinia, PiniaVuePlugin } from 'pinia';
import { polyfill as SeamlessScrollPolyfill } from 'seamless-scroll-polyfill';
import VTooltip from 'v-tooltip';
import 'v-tooltip/dist/v-tooltip.css';
import Vue from 'vue';
import VueVirtualScroller from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import VuetifyMessageSnackbar from 'vuetify-message-snackbar';

import App from '@/App.vue';
import VTabItem from '@/components/Vuetify/VTabItem';
import VTabs from '@/components/Vuetify/VTabs';
import VTabsItems from '@/components/Vuetify/VTabsItems';
import vuetify from '@/plugins/vuetify';
import router from '@/router';
import useSettingsStore, { setLocalStorageSettings } from '@/stores/SettingsStore';
import '@/service-worker';
import Utils from '@/utils';


// スムーズスクロール周りの API の polyfill を適用
// Element.scrollInfoView() のオプション指定を使うために必要
SeamlessScrollPolyfill();

// Production Tip を非表示にする
Vue.config.productionTip = false;

// 常に Vue.js devtools を有効にする
Vue.config.devtools = true;

// Pinia を使う
// ref: https://pinia.vuejs.org/cookbook/options-api.html
Vue.use(PiniaVuePlugin);
const pinia = createPinia();

// vue-virtual-scroller を使う
Vue.use(VueVirtualScroller);

// vuetify-message-snackbar を使う
// マイナーな OSS（しかも中国語…）だけど、Snackbar を関数で呼びたかったのでちょうどよかった
// ref: https://github.com/thinkupp/vuetify-message-snackbar
Vue.use(VuetifyMessageSnackbar, {
    // 画面上に配置しない
    top: false,
    // 画面下に配置する
    bottom: true,
    // デフォルトの背景色
    color: '#433532',
    // ダークテーマを適用する
    dark: true,
    // 影 (Elevation) の設定
    elevation: 8,
    // 2.5秒でタイムアウト
    timeout: 2500,
    // 要素が非表示になった後に DOM から要素を削除する
    autoRemove: true,
    // 閉じるボタンのテキスト
    closeButtonContent: '閉じる',
    // Vuetify のインスタンス
    vuetifyInstance: vuetify,
});

// VTooltip を使う
// タッチデバイスでは無効化する
// ref: https://v-tooltip.netlify.app/guide/config.html#default-values
const trigger = Utils.isTouchDevice() ? [] : ['hover', 'focus', 'touch'];
VTooltip.options.themes.tooltip.showTriggers = trigger;
VTooltip.options.themes.tooltip.hideTriggers = trigger;
VTooltip.options.themes.tooltip.delay.show = 0;
VTooltip.options.offset = [0, 7];
Vue.use(VTooltip);

// Iconify（アイコン）のグローバルコンポーネント
Vue.component('Icon', Icon);

// VTabItem / VTabs / VTabsItems の挙動を改善するグローバルコンポーネント
Vue.component('v-tab-item-fix', VTabItem);
Vue.component('v-tabs-fix', VTabs);
Vue.component('v-tabs-items-fix', VTabsItems);

// Vue を初期化
(window as any).KonomiTVVueInstance = new Vue({
    pinia,
    router,
    vuetify,
    render: h => h(App),
}).$mount('#app');

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

    // 設定データをサーバーに同期する (ログイン時かつ同期が有効な場合のみ)
    await settings_store.syncClientSettingsToServer();

}, {detached: true});

// ログイン時かつ設定の同期が有効な場合、ページ遷移に関わらず、常に3秒おきにサーバーから設定を取得する
// 初回のページレンダリングに間に合わないのは想定内（同期の完了を待つこともできるが、それだと表示速度が遅くなるのでしょうがない）
window.setInterval(async () => {
    if (Utils.getAccessToken() !== null && settings_store.settings.sync_settings === true) {

        // 設定データをサーバーにアップロード
        is_uploading_settings = true;
        await settings_store.syncClientSettingsFromServer();
        is_uploading_settings = false;

        // 設定データを LocalStorage に保存
        setLocalStorageSettings(settings_store.settings);
    }
}, 3 * 1000);  // 3秒おき
