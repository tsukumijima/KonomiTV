
import Vue from 'vue';
import VueRouter from 'vue-router';

import TVHome from '@/views/TV/Home.vue';
import TVWatch from '@/views/TV/Watch.vue';
import SettingsGeneral from '@/views/Settings/General.vue';
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
