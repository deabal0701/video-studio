// 전역 잡 칩 스토어 — /api/events(SSE) 를 앱 수명 동안 구독한다 (03: "빌드 진행은
// SSE 로 어느 화면에서든 상단 칩에 흐른다").
import { defineStore } from 'pinia';
import { api, sse } from '../api/client';

export const useJobsStore = defineStore('jobs', {
  state: () => ({
    jobs: [],          // GET /api/jobs 스냅샷
    lastEvent: null,   // 최근 전역 이벤트 (칩 표시용)
    connected: false,
  }),
  getters: {
    active: (s) => s.jobs.filter((j) => !['done', 'failed', 'blocked', 'canceled'].includes(j.state)),
  },
  actions: {
    async refresh() {
      this.jobs = await api('/jobs');
    },
    connect() {
      if (this.connected) return;
      this.connected = true;
      sse('/events', ({ event, data }) => {
        if (event === 'job') {
          this.lastEvent = data;
          this.refresh().catch(() => {});
        }
      });
      this.refresh().catch(() => {});
    },
  },
});
