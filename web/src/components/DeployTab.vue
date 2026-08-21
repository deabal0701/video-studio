<script setup>
// ⑦ 배포 산출물 — youtube.md 자동 생성 대체 (03). 전 항목 편집 가능 + 복사 버튼.
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { api } from '../api/client';

const props = defineProps({ eid: String });
const data = ref(null);
const form = reactive({ title: '', description: '' });

onMounted(async () => {
  try {
    data.value = await api(`/episodes/${props.eid}/deliverables`);
    form.title = data.value.title;
    form.description = data.value.description;
  } catch (e) {
    ElMessage.error(e.message);
  }
});

async function copy(text, label) {
  await navigator.clipboard.writeText(text);
  ElMessage.success(`${label} 복사됨`);
}
async function saveMd() {
  await api(`/episodes/${props.eid}/deliverables/save`, {
    method: 'POST', body: JSON.stringify({ ...form }),
  });
  ElMessage.success('youtube.md 저장됨');
}
</script>

<template>
  <div v-if="data" class="max-w-3xl">
    <el-form label-width="70px" label-position="left">
      <el-form-item label="제목">
        <div class="flex w-full gap-2">
          <el-input v-model="form.title" />
          <el-button @click="copy(form.title, '제목')">복사</el-button>
        </div>
      </el-form-item>
      <el-form-item label="설명">
        <el-input v-model="form.description" type="textarea" :rows="10" />
      </el-form-item>
      <div class="mb-4 flex gap-2">
        <el-button @click="copy(form.description, '설명')">설명 복사</el-button>
        <el-button type="primary" plain @click="saveMd">youtube.md 저장</el-button>
        <a v-for="s in data.srt" :key="s" :href="`/api/media/${eid}/final/${s}`" download>
          <el-button>⬇ {{ s }}</el-button>
        </a>
      </div>
    </el-form>

    <h3 class="vs-section-title">썸네일 후보 (검수 프레임)</h3>
    <div class="grid grid-cols-5 gap-2">
      <a v-for="t in data.thumbnails" :key="t" :href="`/api/media/${eid}/frames/${t}`" target="_blank">
        <img :src="`/api/media/${eid}/frames/${t}`" class="rounded border" />
      </a>
    </div>
  </div>
  <el-empty v-else description="배포 준비물을 만들려면 먼저 빌드하세요" />
</template>
