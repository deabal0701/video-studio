<script setup>
import { onMounted, ref } from 'vue';
import { api } from '../api/client';
import { useJobsStore } from '../stores/jobs';

const jobs = useJobsStore();
const usage = ref(null); // AI 사용량 미터 (04_api: /api/agent/usage)
const TYPE = {
  done: 'success', failed: 'danger', blocked: 'danger', canceled: 'info',
  running: 'warning', verifying: 'warning', preflight: 'warning', queued: 'info',
};
onMounted(() => {
  jobs.refresh();
  api('/agent/usage').then((v) => (usage.value = v)).catch(() => {});
});
</script>

<template>
  <div class="vs-page-head">
    <div>
      <h1 class="vs-page-title">작업 큐</h1>
      <p class="vs-page-desc">동시 상한 2 · 같은 회차 직렬 · preflight 치명이면 굽지 않음 (04_api 정책)</p>
    </div>
    <el-tag v-if="usage" round type="info">
      AI 사용량 {{ usage.count }}회 · ${{ usage.totalCostUsd }}
    </el-tag>
  </div>
  <div class="vs-panel">
    <el-table :data="jobs.jobs">
      <el-table-column prop="jobId" label="잡" width="80" />
      <el-table-column label="회차" width="220">
        <template #default="{ row }">
          <router-link :to="`/episodes/${row.episodeId}`"
                       class="text-[color:var(--vs-link)] hover:underline">
            {{ row.episodeId }}
          </router-link>
        </template>
      </el-table-column>
      <el-table-column label="상태" width="140">
        <template #default="{ row }">
          <el-tag :type="TYPE[row.state] ?? 'info'" size="small">{{ row.state }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="error" label="오류" />
    </el-table>
  </div>
</template>
