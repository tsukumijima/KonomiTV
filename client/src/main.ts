
import axios from 'axios';
import { Icon } from '@iconify/vue2';
import Vue from 'vue';
import VueAxios from 'vue-axios';
import VTooltip from 'v-tooltip';
import 'v-tooltip/dist/v-tooltip.css'

import App from './App.vue';
import VTabItem from '@/components/VTabItem';
import VTabs from '@/components/VTabs';
import VTabsItems from '@/components/VTabsItems';
import vuetify from './plugins/vuetify';
import router from './router';
import mixin from './mixins';
import './service-worker';

// Production Tip を非表示に
Vue.config.productionTip = false;

// Axios を使う
Vue.use(VueAxios, axios);

// VTooltip を使う
// ref: https://v-tooltip.netlify.app/guide/config.html#default-values
VTooltip.options.offset = [0, 7];
VTooltip.options.themes.tooltip.hideTriggers = null;
VTooltip.options.themes.tooltip.delay.show = 0;
Vue.use(VTooltip);

// Iconify（アイコン）のグローバルコンポーネント
Vue.component('Icon', Icon);

// VTabItem の挙動を改善するグローバルコンポーネント
Vue.component('v-tab-item-fix', VTabItem);

// VTabs の挙動を改善するグローバルコンポーネント
Vue.component('v-tabs-fix', VTabs);

// VTabsItems の挙動を改善するグローバルコンポーネント
Vue.component('v-tabs-items-fix', VTabsItems);

// グローバル Mixin を登録
Vue.mixin(mixin);

// Vue を初期化
new Vue({
    router,
    vuetify,
    render: h => h(App),
}).$mount('#app');
