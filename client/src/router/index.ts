
import Vue from 'vue';
import VueRouter from 'vue-router';

import Utils from '@/utils';
import Login from '@/views/Login.vue';
import NotFound from '@/views/NotFound.vue';
import Register from '@/views/Register.vue';
import SettingsAccount from '@/views/Settings/Account.vue';
import SettingsCaption from '@/views/Settings/Caption.vue';
import SettingsCapture from '@/views/Settings/Capture.vue';
import SettingsDataBroadcasting from '@/views/Settings/DataBroadcasting.vue';
import SettingsGeneral from '@/views/Settings/General.vue';
import SettingsIndex from '@/views/Settings/Index.vue';
import SettingsJikkyo from '@/views/Settings/Jikkyo.vue';
import SettingsServer from '@/views/Settings/Server.vue';
import SettingsTwitter from '@/views/Settings/Twitter.vue';
import TVHome from '@/views/TV/Home.vue';
import TVWatch2 from '@/views/TV/Watch2.vue';

Vue.use(VueRouter);

const router = new VueRouter({

    // History API モード
    mode: 'history',

    // ルーティングのベース URL
    base: process.env.BASE_URL,

    // ルーティング設定
    routes: [
        {
            path: '/',
            redirect: '/tv/',
        },
        {
            path: '/tv/',
            name: 'TV Home',
            component: TVHome,
        },
        {
            path: '/tv/watch2/:display_channel_id',
            name: 'TV Watch2',
            component: TVWatch2,
        },
        {
            path: '/settings/',
            name: 'Settings Index',
            component: SettingsIndex,
            beforeEnter: (to, from, next) => {

                // スマホ縦画面・スマホ横画面・タブレット縦画面では設定一覧画面を表示する（画面サイズの関係）
                if (Utils.isSmartphoneVertical() || Utils.isSmartphoneHorizontal() || Utils.isTabletVertical()) {
                    next();  // 通常通り遷移
                    return;
                }

                // それ以外の画面サイズでは全般設定にリダイレクト
                next({path: '/settings/general/'});
            }
        },
        {
            path: '/settings/general',
            name: 'Settings General',
            component: SettingsGeneral,
        },
        {
            path: '/settings/caption',
            name: 'Settings Caption',
            component: SettingsCaption,
        },
        {
            path: '/settings/data-broadcasting',
            name: 'Settings Data Broadcasting',
            component: SettingsDataBroadcasting,
        },
        {
            path: '/settings/capture',
            name: 'Settings Capture',
            component: SettingsCapture,
        },
        {
            path: '/settings/account',
            name: 'Settings Account',
            component: SettingsAccount,
        },
        {
            path: '/settings/jikkyo',
            name: 'Settings Jikkyo',
            component: SettingsJikkyo,
        },
        {
            path: '/settings/twitter',
            name: 'Settings Twitter',
            component: SettingsTwitter,
        },
        {
            path: '/settings/server',
            name: 'Settings Server',
            component: SettingsServer,
        },
        {
            path: '/login/',
            name: 'Login',
            component: Login,
        },
        {
            path: '/register/',
            name: 'Register',
            component: Register,
        },
        {
            path: '*',
            name: 'NotFound',
            component: NotFound,
        },
    ],

    // ページ遷移時のスクロールの挙動の設定
    // ref: https://v3.router.vuejs.org/ja/guide/advanced/scroll-behavior.html
    scrollBehavior (to, from, savedPosition) {
        if (savedPosition) {
            // 戻る/進むボタンが押されたときは保存されたスクロール位置を使う
            return savedPosition;
        } else {
            // それ以外は常に先頭にスクロールする
            return {x: 0, y: 0};
        }
    }
});

export default router;
