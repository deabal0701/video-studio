<script setup>
// ② 커리큘럼 보드 — 상태 칸반 + [회차 생성] (03_screens ②).
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { api } from '../api/client';

const props = defineProps({ course: Object, episodes: Object });
const emit = defineEmits(['changed']);

// 에이전트 게이트 — 키 없으면 버튼 비활성 + 사유 툴팁 (05: "키 없으면 메뉴 통째로 비활성")
const agent = ref({ enabled: false, reason: '확인 중…' });
onMounted(async () => {
  agent.value = await api('/agent/status').catch(() => agent.value);
});

async function aiDraft(ep) {
  try {
    const { value: brief } = await ElMessageBox.prompt(
      `${ep.n}강 "${ep.title}" 의 주제·방향 (brief)`, 'AI 초안');
    if (!brief) return;
    if ((props.episodes[ep.id]?.state ?? 'empty') === 'empty') {
      await api(`/courses/${props.course.course}/episodes`, {
        method: 'POST', body: JSON.stringify({ n: ep.n }),
      });
    }
    const out = await api('/agent/draft', {
      method: 'POST', body: JSON.stringify({ episodeId: ep.id, brief }),
    });
    ElMessage.success(`AI 초안 잡 ${out.jobId} 시작 — 작업 큐에서 진행을 보세요`);
    emit('changed');
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.detail?.message ?? e.message ?? String(e));
  }
}

const STATE = {
  empty: { label: '⬜ 대기', type: 'info' },
  wip: { label: '🔄 제작 중', type: 'warning' },
  done: { label: '✅ 완료', type: 'success' },
};
const creating = ref(0);

async function createEpisode(ep) {
  creating.value = ep.n;
  try {
    const out = await api(`/courses/${props.course.course}/episodes`, {
      method: 'POST',
      body: JSON.stringify({ n: ep.n }),
    });
    ElMessage.success(`${out.id} 골격 생성 — 대본은 scenes.json 을 채우세요`);
    emit('changed');
  } catch (e) {
    ElMessage.error(e.message);
  } finally {
    creating.value = 0;
  }
}

// 커리큘럼에 없는 새 회차 — n 은 다음 번호 자동, 제목만 묻는다
async function addEpisode() {
  const n = Math.max(0, ...props.course.episodes.map((e) => e.n)) + 1;
  try {
    const { value } = await ElMessageBox.prompt(`${n}강 제목`, '회차 추가');
    if (!value) return;
    const out = await api(`/courses/${props.course.course}/episodes`, {
      method: 'POST',
      body: JSON.stringify({ n, title: value }),
    });
    ElMessage.success(`${out.id} 골격 생성`);
    emit('changed');
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message ?? String(e));
  }
}
</script>

<template>
  <div class="vs-card-grid">
    <el-card v-for="ep in course.episodes" :key="ep.id" shadow="hover">
      <div class="flex items-center justify-between">
        <div class="font-semibold">{{ ep.n }}강 {{ ep.title }}</div>
        <el-tag :type="STATE[episodes[ep.id]?.state ?? 'empty'].type" size="small">
          {{ STATE[episodes[ep.id]?.state ?? 'empty'].label }}
        </el-tag>
      </div>
      <div class="mt-1 text-sm vs-ink-2">{{ ep.subtitle }}</div>
      <div v-if="ep['근거']" class="mt-1 text-xs vs-ink-3">근거: {{ ep['근거'] }}</div>
      <div class="mt-2 flex items-center gap-2">
        <el-tag v-if="episodes[ep.id]?.stale" type="danger" size="small">재빌드 필요</el-tag>
        <template v-if="(episodes[ep.id]?.state ?? 'empty') === 'empty'">
          <el-button size="small" type="primary" plain
                     :loading="creating === ep.n" @click="createEpisode(ep)">
            회차 생성
          </el-button>
          <el-tooltip :content="agent.reason" :disabled="agent.enabled">
            <span>
              <el-button size="small" :disabled="!agent.enabled" @click="aiDraft(ep)">
                ✨ AI 초안
              </el-button>
            </span>
          </el-tooltip>
        </template>
        <template v-else>
          <router-link :to="`/episodes/${ep.id}`">
            <el-button size="small">열기</el-button>
          </router-link>
          <el-tooltip :content="agent.reason" :disabled="agent.enabled">
            <span>
              <el-button size="small" :disabled="!agent.enabled" @click="aiDraft(ep)">
                ✨ AI 초안
              </el-button>
            </span>
          </el-tooltip>
        </template>
      </div>
    </el-card>
    <el-card shadow="never" class="flex items-center justify-center border-dashed">
      <el-button text type="primary" @click="addEpisode">+ 회차 추가</el-button>
    </el-card>
  </div>
</template>
