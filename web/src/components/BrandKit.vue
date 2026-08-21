<script setup>
// ③ 브랜드 킷 — palette 조정 + 카드·스팅어 프리뷰 (03_screens ③).
// 실물 iframe 프리뷰(preview.js)·프리셋 갤러리는 3단계에서 — 지금은 palette 저장이 본체.
import { reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '../api/client';

const props = defineProps({ course: Object, etag: String });
const emit = defineEmits(['saved']);

const palette = reactive({ ...props.course.palette });
const saving = ref(false);

// 프리셋 갤러리 — 1단계는 기본 1종 (03 ③). 적용 = 강좌 폴더로 카피(덮어씀)
const applying = ref(false);
async function applyPreset() {
  try {
    await ElMessageBox.confirm(
      '기존 course-intro.html · course-stinger.html 을 프리셋으로 덮어씁니다. 직접 수정한 내용은 사라집니다.',
      '프리셋 적용', { type: 'warning' });
    applying.value = true;
    const out = await api(`/courses/${props.course.course}/brandkit/apply`, { method: 'POST' });
    ElMessage.success(`카피됨: ${out.copied.join(', ')}`);
    emit('saved');
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message ?? String(e));
  } finally {
    applying.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const body = { ...props.course, palette: { ...palette } };
    await api(`/courses/${props.course.course}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': props.etag },
      body: JSON.stringify(body),
    });
    ElMessage.success('팔레트 저장됨 — 새 회차 스캐폴딩부터 자동 주입됩니다');
    emit('saved');
  } catch (e) {
    ElMessage.error(e.status === 409 ? '저장 충돌 — 새로고침 후 다시' : e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="max-w-2xl">
    <el-alert type="info" :closable="false" class="mb-4"
              title="스팅어는 회차마다 동일해야 합니다 — 회차별 편집 진입점은 없습니다 (강좌 일관성 규약)" />
    <div class="mb-4 flex items-center gap-6">
      <label class="text-sm">brand <el-color-picker v-model="palette.brand" /></label>
      <label class="text-sm">brandSoft <el-color-picker v-model="palette.brandSoft" /></label>
      <label class="text-sm">bg <el-color-picker v-model="palette.bg" /></label>
      <el-button type="primary" :loading="saving" @click="save">저장</el-button>
    </div>
    <div class="flex aspect-video flex-col items-center justify-center rounded-lg shadow"
         :style="{ background: palette.bg }">
      <div class="text-3xl font-black" :style="{ color: palette.brand }">
        {{ course.title }}
      </div>
      <div class="mt-2" :style="{ color: palette.brandSoft }">{{ course.tagline }}</div>
    </div>

    <el-divider content-position="left">프리셋 갤러리</el-divider>
    <el-card shadow="hover" class="max-w-sm">
      <div class="font-semibold">기본 — 강좌 타이틀 카드 + 시그니처 스팅어</div>
      <div class="mt-1 text-xs vs-ink-3">
        B롤 정지 프레임 배경 · 키커/회차 뱃지/제목 · 3초 스팅어. 색은 palette 연동.
      </div>
      <el-button size="small" class="mt-2" :loading="applying" @click="applyPreset">
        이 프리셋 적용 (기존 파일 덮어씀)
      </el-button>
    </el-card>
  </div>
</template>
