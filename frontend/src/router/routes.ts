import { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/login', component: () => import('pages/LoginPage.vue') },
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/tasks' },
      { path: 'tasks', component: () => import('pages/TaskSelectionPage.vue'), meta: { requiresAuth: true } },
      { path: 'compare/:taskId', component: () => import('pages/ComparisonPage.vue'), meta: { requiresAuth: true } },
      { path: 'rate/:taskId', component: () => import('pages/RatingPage.vue'), meta: { requiresAuth: true } },
      { path: 'leaderboard', component: () => import('pages/LeaderboardPage.vue'), meta: { requiresAuth: true } },
      { path: 'admin', component: () => import('pages/AdminPage.vue'), meta: { requiresAuth: true } },
    ],
  },
  { path: '/:catchAll(.*)*', component: () => import('pages/ErrorNotFound.vue') },
];

export default routes;
