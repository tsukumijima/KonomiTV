
import Vue from 'vue';
import axios from 'axios';
import VueAxios from 'vue-axios';
import App from './App.vue';
import vuetify from './plugins/vuetify';
import router from './router';
import mixin from './mixins';
import './registerServiceWorker';


// Production Tip を非表示に
Vue.config.productionTip = false;

// Axios を使う
Vue.use(VueAxios, axios);

// mixin を登録
Vue.mixin(mixin);

// Vue を初期化
new Vue({
    router,
    vuetify,
    render: h => h(App),
}).$mount('#app');
