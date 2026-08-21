<script setup>
// 강좌 화면 — ① 설정 · ② 커리큘럼 · ③ 브랜드 킷 (03 화면 지도의 탭 구조)
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api } from '../api/client';
import CourseSettings from '../components/CourseSettings.vue';
import CourseBoard from '../components/CourseBoard.vue';
import BrandKit from '../components/BrandKit.vue';

const route = useRoute();
const data = ref(null);
const bgmList = ref([]);

async function load() {
  data.value = await api(`/courses/${route.params.cid}`);
  bgmList.value = await api('/assets?kind=bgm');
}
onMounted(load);
</script>

<template>
  <div v-if="data">
    <div class="vs-page-head">
      <div>
        <h1 class="vs-page-title">{{ data.course.title }}</h1>
        <p class="vs-page-desc">{{ data.course.tagline }} · {{ data.course.episodeLength }}</p>
      </div>
    </div>
    <el-tabs>
      <el-tab-pane label="② 커리큘럼" lazy>
        <CourseBoard :course="data.course" :episodes="data.episodes" @changed="load" />
      </el-tab-pane>
      <el-tab-pane label="① 강좌 설정" lazy>
        <CourseSettings :key="data.etag" :course="data.course" :etag="data.etag"
                        :bgm-list="bgmList" @saved="load" />
      </el-tab-pane>
      <el-tab-pane label="③ 브랜드 킷" lazy>
        <BrandKit :key="data.etag" :course="data.course" :etag="data.etag" @saved="load" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
