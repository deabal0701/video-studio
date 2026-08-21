<script setup>
// ① 강좌 설정 — course.json 편집 폼 (03_screens ①). 저장 = PUT + If-Match.
import { computed, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '../api/client';

const props = defineProps({ course: Object, etag: String, bgmList: Array });
const emit = defineEmits(['saved']);

const form = reactive(JSON.parse(JSON.stringify(props.course)));
const saving = ref(false);

// 목소리 프리셋 (develop-lecture 규약: 선희 +8% · 인준 +19%)
const voicePreset = computed({
  get: () => (form.voice?.gender === 'male' ? 'male' : 'female'),
  set: (v) => {
    form.voice = v === 'male'
      ? { provider: 'edge', lang: 'ko', gender: 'male', rate: '+19%' }
      : { provider: 'edge', lang: 'ko', gender: 'female', rate: '+8%' };
  },
});

const listening = ref(false);
async function preview() {
  listening.value = true;
  try {
    const res = await fetch('/api/tts/sample', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: '이 목소리로 강좌 전체를 읽습니다. 개념 하나를 오 분에 담아냅니다.',
        gender: form.voice?.gender ?? 'female',
      }),
    });
    if (!res.ok) throw new Error('TTS 실패 — 네트워크를 확인하세요');
    new Audio(URL.createObjectURL(await res.blob())).play();
  } catch (e) {
    ElMessage.error(e.message);
  } finally {
    listening.value = false;
  }
}

let bgmAudio = null;
function playBgm() {
  bgmAudio?.pause();
  const name = form.render?.bgm?.split('/').pop();
  if (!name) return;
  bgmAudio = new Audio(`/api/assets/file?kind=bgm&name=${encodeURIComponent(name)}`);
  bgmAudio.volume = 0.5;
  bgmAudio.play();
}

async function save() {
  saving.value = true;
  try {
    const out = await api(`/courses/${form.course}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': props.etag },
      body: JSON.stringify(form),
    });
    const n = Object.keys(out.consistency ?? {}).length;
    ElMessage.success(n ? `저장됨 — 회차 ${n}개가 강좌와 어긋남 (보드 배지 확인)` : '저장됨');
    emit('saved');
  } catch (e) {
    if (e.status === 409) {
      await ElMessageBox.alert(
        '파일이 밖에서(에디터·Claude Code) 바뀌었습니다. 새로고침 후 다시 수정하세요.',
        '저장 충돌', { confirmButtonText: '새로고침' });
      emit('saved');
    } else ElMessage.error(e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
    <el-form label-width="90px" label-position="left">
      <el-form-item label="강좌명"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="태그라인"><el-input v-model="form.tagline" /></el-form-item>
      <el-form-item label="대상">
        <el-input v-model="form.audience" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="분량"><el-input v-model="form.episodeLength" /></el-form-item>

      <el-divider content-position="left">목소리 (시리즈 내내 고정)</el-divider>
      <el-form-item label="프리셋">
        <el-radio-group v-model="voicePreset">
          <el-radio value="female">선희 +8%</el-radio>
          <el-radio value="male">인준 +19%</el-radio>
        </el-radio-group>
        <el-button size="small" class="ml-3" :loading="listening" @click="preview">
          ▶ 미리듣기
        </el-button>
      </el-form-item>

      <el-divider content-position="left">브랜드</el-divider>
      <el-form-item label="brand">
        <el-color-picker v-model="form.palette.brand" />
        <el-color-picker v-model="form.palette.brandSoft" class="ml-2" />
        <el-color-picker v-model="form.palette.bg" class="ml-2" />
        <span class="ml-2 text-xs vs-ink-3">brand · soft · bg</span>
      </el-form-item>

      <el-divider content-position="left">사운드</el-divider>
      <el-form-item label="BGM">
        <el-select v-model="form.render.bgm" class="w-64">
          <el-option v-for="b in bgmList" :key="b.ref" :value="b.ref"
                     :label="`${b.name} (${Math.round(b.duration)}s${b.licensed ? '' : ' · ⚠ 라이선스 없음'})`" />
        </el-select>
        <el-button size="small" class="ml-2" @click="playBgm">▶ 듣기</el-button>
      </el-form-item>
      <el-form-item label="gain">
        <el-input-number v-model="form.render.bgmGain" :step="0.02" :min="0" :max="1" />
        <el-checkbox v-model="form.render.bgmDucking" class="ml-3">더킹</el-checkbox>
      </el-form-item>

      <el-button type="primary" :loading="saving" @click="save">저장</el-button>
    </el-form>

    <!-- 라이브 프리뷰 — 간이 모사. 실물 iframe(preview.js) 연동은 3단계 -->
    <div>
      <div class="mb-2 text-sm vs-ink-2">타이틀 카드 프리뷰 (간이 — 실물 렌더는 3단계)</div>
      <div class="flex aspect-video w-full flex-col items-center justify-center rounded-lg shadow"
           :style="{ background: form.palette.bg }">
        <div class="text-sm tracking-widest" :style="{ color: form.palette.brandSoft }">
          — {{ form.title }} —
        </div>
        <div class="mt-2 rounded-full px-3 py-0.5 text-xs font-bold text-white"
             :style="{ background: form.palette.brand }">N강</div>
        <div class="mt-3 text-4xl font-black text-white">회차 제목</div>
        <div class="mt-3 h-1 w-10" :style="{ background: form.palette.brand }" />
      </div>
      <div class="mt-4 flex aspect-video w-full flex-col items-center justify-center rounded-lg shadow"
           :style="{ background: form.palette.bg }">
        <div class="text-2xl font-black" :style="{ color: form.palette.brand }">
          {{ form.title }}
        </div>
        <div class="mt-2 text-sm text-slate-300">{{ form.tagline }}</div>
        <div class="mt-1 text-[10px] text-slate-500">스팅어 3초 — 회차 무관 고정</div>
      </div>
    </div>
  </div>
</template>
