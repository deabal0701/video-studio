<script setup>
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { api } from '../api/client';

const router = useRouter();
const courses = ref([]);
const error = ref('');
onMounted(async () => {
  try {
    courses.value = await api('/courses');
  } catch (e) {
    error.value = e.message;
  }
});

// [새 강좌] 위저드 — 스킬의 "강좌 개설 질문 4개"가 그대로 폼 (03 ①)
const wizard = ref(false);
const creating = ref(false);
const bgmList = ref([]);
const form = reactive({
  course: '',
  title: '',
  tagline: '',
  audience: '',
  voicePreset: 'female',
  palette: { brand: '#3E63DD', brandSoft: '#93A4F5', bg: '#070b14' },
  bgm: 'assets/bgm/mixkit-623-loop.mp3',
});

async function openWizard() {
  wizard.value = true;
  if (!bgmList.value.length) bgmList.value = await api('/assets?kind=bgm').catch(() => []);
}

async function create() {
  creating.value = true;
  try {
    const voice = form.voicePreset === 'male'
      ? { provider: 'edge', lang: 'ko', gender: 'male', rate: '+19%' }
      : { provider: 'edge', lang: 'ko', gender: 'female', rate: '+8%' };
    const { id } = await api('/courses', {
      method: 'POST',
      body: JSON.stringify({ course: form.course, title: form.title, tagline: form.tagline,
                             audience: form.audience, voice, palette: form.palette,
                             bgm: form.bgm }),
    });
    ElMessage.success(`${id} 개설됨 — 커리큘럼에서 회차를 만드세요`);
    router.push(`/courses/${id}`);
  } catch (e) {
    ElMessage.error(e.detail?.message ?? e.message);
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <div class="vs-page-head">
    <div>
      <h1 class="vs-page-title">강좌</h1>
      <p class="vs-page-desc">시리즈와 단발 영상을 한 곳에서 — 카드를 열어 회차를 만들고 빌드하세요</p>
    </div>
    <el-button type="primary" @click="openWizard">+ 새 강좌</el-button>
  </div>
  <el-alert v-if="error" :title="error" type="error" class="mb-4" />
  <div class="vs-card-grid">
    <router-link
      v-for="c in courses"
      :key="c.id"
      :to="c.single ? `/episodes/${c.id}` : `/courses/${c.id}`"
    >
      <el-card shadow="hover">
        <div class="font-semibold">{{ c.title }}</div>
        <div class="mt-1 text-sm vs-ink-2">
          <template v-if="c.single">단발 영상</template>
          <template v-else>
            {{ c.episodeCount }}부작 · 스캐폴딩 {{ c.scaffolded }} · 완료 {{ c.done }}
          </template>
        </div>
        <el-progress
          v-if="!c.single"
          class="mt-2"
          :percentage="c.episodeCount ? Math.round((c.done / c.episodeCount) * 100) : 0"
        />
      </el-card>
    </router-link>
  </div>

  <el-dialog v-model="wizard" title="새 강좌 개설 — 한 번 정하면 시리즈 내내 고정됩니다" width="560">
    <el-form label-width="80px" label-position="left">
      <el-form-item label="강좌 id">
        <el-input v-model="form.course" placeholder="kebab-case (예: hr-basics)" />
      </el-form-item>
      <el-form-item label="강좌명"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="태그라인">
        <el-input v-model="form.tagline" placeholder="예: 개념 하나를, 5분에" />
      </el-form-item>
      <el-form-item label="대상">
        <el-input v-model="form.audience" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="목소리">
        <el-radio-group v-model="form.voicePreset">
          <el-radio value="female">선희 +8%</el-radio>
          <el-radio value="male">인준 +19%</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="브랜드">
        <el-color-picker v-model="form.palette.brand" />
        <el-color-picker v-model="form.palette.brandSoft" class="ml-2" />
        <el-color-picker v-model="form.palette.bg" class="ml-2" />
      </el-form-item>
      <el-form-item label="BGM">
        <el-select v-model="form.bgm">
          <el-option v-for="b in bgmList" :key="b.ref" :value="b.ref" :label="b.name" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="wizard = false">취소</el-button>
      <el-button type="primary" :loading="creating" @click="create">개설</el-button>
    </template>
  </el-dialog>
</template>
