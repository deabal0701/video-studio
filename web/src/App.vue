<script setup>
import { onMounted } from 'vue';
import { useJobsStore } from './stores/jobs';

const jobs = useJobsStore();
onMounted(() => jobs.connect());
</script>

<template>
  <div class="min-h-screen">
    <header class="vs-header">
      <div class="vs-container vs-header-inner">
        <router-link to="/" class="vs-brand">🎬 Video Studio</router-link>
        <nav class="vs-nav">
          <router-link to="/">대시보드</router-link>
          <router-link to="/jobs">작업 큐</router-link>
        </nav>
        <div class="ml-auto">
          <router-link to="/jobs">
            <el-tag v-if="jobs.active.length" type="warning" round effect="dark">
              빌드 {{ jobs.active.length }}건 진행 중 — {{ jobs.active[0].episodeId }}
              ({{ jobs.active[0].state }})
            </el-tag>
            <el-tag v-else type="info" round effect="plain">대기 중인 빌드 없음</el-tag>
          </router-link>
        </div>
      </div>
    </header>
    <main class="vs-container vs-main">
      <router-view />
    </main>
  </div>
</template>
