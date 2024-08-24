

import { createRouter, createWebHistory } from 'vue-router';

import Utils from '@/utils';


// Vue Router v4
// ref: https://router.vuejs.org/guide/

const router = createRouter({

    // ルーティングのベース URL
    history: createWebHistory(import.meta.env.BASE_URL),

    // ルーティング設定
    routes: [
        {
            path: '/',
            redirect: '/tv/',
        },
        {
            path: '/tv/',
            name: 'TV Home',
            component: () => import('@/views/TV/Home.vue'),
        },
        {
            path: '/tv/watch/:display_channel_id',
            name: 'TV Watch',
            component: () => import('@/views/TV/Watch.vue'),
        },
        {
            path: '/videos/watch/:video_id',
            name: 'Videos Watch',
            component: () => import('@/views/Videos/Watch.vue'),
        },
        {
            path: '/mypage/',
            name: 'MyPage',
            component: () => import('@/views/MyPage.vue'),
        },
        {
            path: '/settings/',
            name: 'Settings Index',
            component: () => import('@/views/Settings/Index.vue'),
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
            component: () => import('@/views/Settings/General.vue'),
        },
        {
            path: '/settings/quality',
            name: 'Settings Quality',
            component: () => import('@/views/Settings/Quality.vue'),
        },
        {
            path: '/settings/caption',
            name: 'Settings Caption',
            component: () => import('@/views/Settings/Caption.vue'),
        },
        {
            path: '/settings/data-broadcasting',
            name: 'Settings Data Broadcasting',
            component: () => import('@/views/Settings/DataBroadcasting.vue'),
        },
        {
            path: '/settings/capture',
            name: 'Settings Capture',
            component: () => import('@/views/Settings/Capture.vue'),
        },
        {
            path: '/settings/account',
            name: 'Settings Account',
            component: () => import('@/views/Settings/Account.vue'),
        },
        {
            path: '/settings/jikkyo',
            name: 'Settings Jikkyo',
            component: () => import('@/views/Settings/Jikkyo.vue'),
        },
        {
            path: '/settings/twitter',
            name: 'Settings Twitter',
            component: () => import('@/views/Settings/Twitter.vue'),
        },
        {
            path: '/settings/server',
            name: 'Settings Server',
            component: () => import('@/views/Settings/Server.vue'),
        },
        {
            path: '/login/',
            name: 'Login',
            component: () => import('@/views/Login.vue'),
        },
        {
            path: '/register/',
            name: 'Register',
            component: () => import('@/views/Register.vue'),
        },
        {
            path: '/:pathMatch(.*)*',
            name: 'NotFound',
            component: () => import('@/views/NotFound.vue'),
        },
    ],

    // ページ遷移時のスクロールの挙動の設定
    scrollBehavior(to, from, savedPosition) {
        if (savedPosition) {
            // 戻る/進むボタンが押されたときは保存されたスクロール位置を使う
            return savedPosition;
        } else {
            // それ以外は常に先頭にスクロールする
            return {top: 0, left: 0};
        }
    }
});

// ルーティングの変更時に View Transitions API を適用する
// ref: https://developer.mozilla.org/ja/docs/Web/API/View_Transitions_API
router.beforeResolve((to, from, next) => {
    // View Transition API を適用しないルートの prefix
    // to と from の両方のパスがこの prefix で始まる場合は View Transition API を適用しない
    const no_transition_routes = [
        '/tv/watch/',
        '/videos/watch/',
    ];
    if (document.startViewTransition && !no_transition_routes.some((route) => to.path.startsWith(route) && from.path.startsWith(route))) {
        document.startViewTransition(() => {
            next();
        });
    } else {
        next();
    }
});

export default router;
