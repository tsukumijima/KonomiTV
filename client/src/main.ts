
import axios from 'axios';
import { Icon } from '@iconify/vue2';
import Vue from 'vue';
import VueAxios from 'vue-axios';

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
