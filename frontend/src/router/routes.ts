import { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('pages/LoginPage.vue') },
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/classify' },
      { path: 'tasks', redirect: '/classify' },
      { path: 'classify', component: () => import('pages/ClassificationPage.vue'), meta: { requiresAuth: true } },
      { path: 'leaderboard', component: () => import('pages/LeaderboardPage.vue'), meta: { requiresAuth: true } },
      { path: 'admin', component: () => import('pages/AdminPage.vue'), meta: { requiresAuth: true } },
    ],
  },
  { path: '/:catchAll(.*)*', component: () => import('pages/ErrorNotFound.vue') },
];

export default routes;
