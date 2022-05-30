
import Vue from 'vue';
import VueRouter from 'vue-router';

import TVHome from '@/views/TV/Home.vue';
import TVWatch from '@/views/TV/Watch.vue';
import SettingsGeneral from '@/views/Settings/General.vue';
import SettingsAccount from '@/views/Settings/Account.vue';
import SettingsJikkyo from '@/views/Settings/Jikkyo.vue';
import SettingsTwitter from '@/views/Settings/Twitter.vue';
import SettingsEnvironment from '@/views/Settings/Environment.vue';
import Login from '@/views/Login.vue';
import Register from '@/views/Register.vue';
import NotFound from '@/views/NotFound.vue';

Vue.use(VueRouter);

const routes = [
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
    path: '/tv/watch/:channel_id',
    name: 'TV Watch',
    component: TVWatch,
  },
  {
    path: '/settings/',
    redirect: '/settings/general',
  },
  {
    path: '/settings/general',
    name: 'Settings General',
    component: SettingsGeneral,
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
    path: '/settings/environment',
    name: 'Settings Environment',
    component: SettingsEnvironment,
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
];

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
});

export default router;
