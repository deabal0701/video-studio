import { createRouter, createWebHistory } from 'vue-router';

// 03_screens.md 화면 지도 — 1단계는 읽기 전용 콘솔 몫만 (①③⑤ 편집은 2~3단계).
export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/DashboardView.vue') },
    { path: '/courses/:cid', component: () => import('./views/CourseView.vue') },
    { path: '/episodes/:id', component: () => import('./views/EpisodeView.vue') },
    { path: '/jobs', component: () => import('./views/JobsView.vue') },
  ],
});
