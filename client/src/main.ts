
import { Icon } from '@iconify/vue2';
import { polyfill as SeamlessScrollPolyfill } from "seamless-scroll-polyfill";
import Vue from 'vue';
import VueAxios from 'vue-axios';
import VueVirtualScroller from 'vue-virtual-scroller';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import VuetifyMessageSnackbar from 'vuetify-message-snackbar';
import VTooltip from 'v-tooltip';
import 'v-tooltip/dist/v-tooltip.css';

import App from '@/App.vue';
import VTabItem from '@/components/VTabItem';
import VTabs from '@/components/VTabs';
import VTabsItems from '@/components/VTabsItems';
import axios from '@/plugins/axios';
import vuetify from '@/plugins/vuetify';
import router from '@/router';
import '@/service-worker';
import Utils from './utils';

// スムーズスクロール周りの API の polyfill を適用
// Element.scrollInfoView() のオプション指定を使うために必要
SeamlessScrollPolyfill();

// Production Tip を非表示に
Vue.config.productionTip = false;

// Axios を使う
Vue.use(VueAxios, axios);

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
const trigger = window.matchMedia('(hover: none)').matches ? [] : ['hover', 'focus', 'touch'];
VTooltip.options.themes.tooltip.showTriggers = trigger;
VTooltip.options.themes.tooltip.hideTriggers = trigger;
VTooltip.options.themes.tooltip.delay.show = 0;
VTooltip.options.offset = [0, 7];
Vue.use(VTooltip);

// Iconify（アイコン）のグローバルコンポーネント
Vue.component('Icon', Icon);

// VTabItem の挙動を改善するグローバルコンポーネント
Vue.component('v-tab-item-fix', VTabItem);

// VTabs の挙動を改善するグローバルコンポーネント
Vue.component('v-tabs-fix', VTabs);

// VTabsItems の挙動を改善するグローバルコンポーネント
Vue.component('v-tabs-items-fix', VTabsItems);

// Vue を初期化
new Vue({
    router,
    vuetify,
    render: h => h(App),
}).$mount('#app');

// ログイン時かつ設定の同期が有効なとき、ページ遷移に関わらず、常に3秒おきにサーバーから設定を取得する
// 初回のページレンダリングに間に合わないのは想定内（同期の完了を待つこともできるが、それだと表示速度が遅くなるのでしょうがない）
window.setInterval(async () => {
    if (Utils.getAccessToken() !== null && Utils.getSettingsItem('sync_settings') === true) {
        Utils.syncServerSettingsToClient();
    }
}, 3 * 1000);  // 3秒おき
