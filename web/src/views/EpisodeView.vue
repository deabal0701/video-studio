<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRoute } from 'vue-router';
import { api, sse } from '../api/client';
import ClipEditor from '../components/ClipEditor.vue';
import DeployTab from '../components/DeployTab.vue';
import PlanTable from '../components/PlanTable.vue';

const route = useRoute();
const eid = route.params.id;

const data = ref(null); // GET /api/episodes/:id
const consistency = ref(null);
const inspect = ref(null);   // GET /api/episodes/:id/inspect — 에디터 재료
const budgetText = ref('');  // course.episodeLength — 예산 게이지 원천
const agent = ref({ enabled: false, reason: '' });
const error = ref('');

async function aiReview() {
  try {
    const { jobId } = await api('/agent/review', {
      method: 'POST', body: JSON.stringify({ episodeId: eid }),
    });
    building.value = true;
    logs.value = [`AI 평가 잡 ${jobId} — 진행 로그:`];
    closeSse = sse(`/jobs/${jobId}/events`, ({ event, data: d }) => {
      if (d?.line) logs.value.push(d.line);
      if (event === 'done') finish('AI 평가 완료');
      if (event === 'failed') finish(`AI 평가 실패: ${d?.error ?? ''}`);
    });
  } catch (e) {
    ElMessageBoxSafe(e);
  }
}
function ElMessageBoxSafe(e) {
  error.value = e.detail?.message ?? e.message ?? String(e);
}

// ── 빌드 (⑥ 상단) ──────────────────────────────────────────────────────────
const building = ref(false);
const jobState = ref('');
const logs = ref([]);
let closeSse = null;

async function build(only = null) {
  error.value = '';
  logs.value = [];
  building.value = true;
  try {
    const { jobId } = await api(`/episodes/${eid}/build`, {
      method: 'POST',
      body: JSON.stringify(only ? { only } : {}),
    });
    closeSse = sse(`/jobs/${jobId}/events`, ({ event, data: d }) => {
      if (event === 'progress' && d?.phase) jobState.value = String(d.phase);
      if (d?.msg || d?.line) logs.value.push(d.msg ?? d.line);
      if (event === 'done') finish('done');
      if (event === 'failed') finish(`실패: ${d?.error ?? ''}`);
    });
  } catch (e) {
    building.value = false;
    error.value = e.message;
  }
}
function finish(state) {
  jobState.value = state;
  building.value = false;
  closeSse?.();
  load(); // 파생 상태(final·stale) 새로고침
}
onUnmounted(() => closeSse?.());

// ── 검수 (⑥ — 프레임 그리드·무음·자막 대조·체크리스트) ──────────────────────
const frames = ref([]);
const silence = ref(null);
const subtitleCheck = ref(null);
const checklist = ref({ items: {} });
const CHECK_ITEMS = ['밝은 프레임 워터마크', '어두운 프레임 자막', '타이틀 프레임', '마지막 프레임', '무음 리포트 확인'];
const KIND_LABEL = { title: '타이틀', bright: '밝은☀', dark: '어두운🌙', motion: '모션', last: '마지막' };
async function loadReview() {
  try {
    frames.value = (await api(`/episodes/${eid}/frames?preset=review`)).frames;
    silence.value = await api(`/episodes/${eid}/silence`);
    subtitleCheck.value = await api(`/episodes/${eid}/subtitle-check`);
    checklist.value = await api(`/episodes/${eid}/review`);
  } catch (e) {
    if (e.status !== 409) error.value = e.message; // 409 = 아직 빌드 전
  }
}
async function saveChecklist() {
  checklist.value = await api(`/episodes/${eid}/review`, {
    method: 'PUT', body: JSON.stringify(checklist.value),
  });
}

// ── ④ 구성표 (plan.md — 표 구조 편집기는 후속, 지금은 마크다운 라운드트립) ──
const plan = ref(null);
const planMode = ref('table');
async function loadPlan() {
  plan.value = await api(`/episodes/${eid}/plan`).catch(() => ({ markdown: '', etag: null }));
}
async function syncCourse() {
  try {
    const out = await api(`/episodes/${eid}/sync-course`, {
      method: 'POST', headers: { 'If-Match': data.value.etag },
    });
    error.value = '';
    await load();
    if (!out.consistency.length) logs.value = [];
  } catch (e) {
    error.value = e.detail?.message ?? e.message;
  }
}
async function planApply() {
  try {
    const out = await api(`/episodes/${eid}/plan/apply`, { method: 'POST' });
    await load();
    ElMessage.success(out.added.length
      ? `클립 골격 추가: ${out.added.join(', ')} — ⑤ 에서 내레이션을 채우세요`
      : '반영할 새 구간 없음 (기존 클립은 보존)');
  } catch (e) {
    ElMessage.error(e.detail?.message ?? e.message);
  }
}
async function savePlan() {
  const out = await api(`/episodes/${eid}/plan`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...(plan.value.etag ? { 'If-Match': plan.value.etag } : {}) },
    body: JSON.stringify({ markdown: plan.value.markdown }),
  });
  plan.value.etag = out.etag;
}

const clips = computed(() => data.value?.scenes?.render?.motion?.clips ?? []);
const narrationTotal = computed(() =>
  clips.value.reduce((sum, c) => sum + (c.narration?.length ?? 0), 0),
);
const videoUrl = computed(() =>
  data.value?.final?.length ? `/api/media/${eid}/final/${data.value.final[0]}` : null,
);

async function load() {
  data.value = await api(`/episodes/${eid}`);
  consistency.value = await api(`/episodes/${eid}/consistency`);
  api(`/episodes/${eid}/inspect`).then((v) => (inspect.value = v)).catch(() => {});
  if (consistency.value?.course) {
    api(`/courses/${consistency.value.course}`)
      .then((c) => (budgetText.value = c.course.episodeLength ?? ''))
      .catch(() => {});
  }
  if (data.value.final?.length) loadReview();
}
onMounted(() => {
  load().catch((e) => (error.value = e.message));
  loadPlan();
  api('/agent/status').then((v) => (agent.value = v)).catch(() => {});
});
</script>

<template>
  <div v-if="data">
    <div class="vs-page-head">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="vs-page-title">{{ eid }}</h1>
          <el-tag v-if="data.stale" type="danger" round>대본이 더 새것 — 재빌드 필요</el-tag>
          <el-tag v-if="consistency?.problems?.length" type="warning" round>
            강좌 일관성 {{ consistency.problems.length }}건 어긋남
          </el-tag>
        </div>
        <p class="vs-page-desc">구성표 → 대본 → 검수 → 배포 — 탭 순서가 제작 순서입니다</p>
      </div>
      <div class="flex items-center gap-2">
        <el-button :loading="building" type="primary" @click="build()">빌드</el-button>
        <el-button :disabled="building" size="small" @click="build('tts')">TTS만</el-button>
        <el-button :disabled="building" size="small" @click="build('compose')">합성만</el-button>
        <el-tooltip :content="agent.reason || '완성본을 새 세션이 채점합니다'" :disabled="false">
          <span>
            <el-button size="small" :disabled="!agent.enabled || building" @click="aiReview">
              ✨ AI 평가
            </el-button>
          </span>
        </el-tooltip>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" class="mb-4" />

    <el-alert v-if="consistency?.problems?.length" type="warning" class="mb-4" :closable="false">
      <template #title>
        {{ consistency.problems.join(' · ') }}
        <el-button size="small" type="warning" plain class="ml-2" @click="syncCourse">
          강좌 값으로 맞추기
        </el-button>
      </template>
    </el-alert>

    <!-- 빌드 진행 (SSE) -->
    <el-card v-if="building || logs.length" class="mb-4">
      <div class="mb-2 font-semibold">
        빌드 진행 — {{ jobState || '대기' }}
        <el-icon v-if="building" class="is-loading ml-1"><i /></el-icon>
      </div>
      <pre class="max-h-48 overflow-auto rounded-lg bg-[color:var(--vs-bg-dark)] p-3 text-xs text-slate-100">{{
        logs.slice(-100).join('\n')
      }}</pre>
    </el-card>

    <el-tabs>
      <!-- ⑤ 대본 에디터 (3A 골격 — params 폼·피커·프리뷰는 3B·3C) -->
      <el-tab-pane label="⑤ 대본 에디터">
        <ClipEditor :key="data.etag" :eid="eid" :scenes="data.scenes" :etag="data.etag"
                    :inspect="inspect" :budget-text="budgetText" @saved="load" />
      </el-tab-pane>

      <!-- ④ 구성표 -->
      <el-tab-pane label="④ 구성표" lazy>
        <div v-if="plan" class="max-w-5xl">
          <el-radio-group v-model="planMode" size="small" class="mb-3">
            <el-radio-button value="table">표 편집</el-radio-button>
            <el-radio-button value="raw">원문 (markdown)</el-radio-button>
          </el-radio-group>
          <PlanTable v-if="planMode === 'table'" v-model:markdown="plan.markdown"
                     :budget-text="budgetText" />
          <el-input v-else v-model="plan.markdown" type="textarea" :rows="20" class="font-mono" />
          <div class="mt-3 flex gap-2">
            <el-button type="primary" @click="savePlan">plan.md 저장</el-button>
            <el-button @click="planApply">대본으로 반영 (없는 구간 → 클립 골격)</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- ⑥ 검수 -->
      <el-tab-pane label="⑥ 검수">
        <template v-if="videoUrl">
          <video :src="videoUrl" controls class="mb-4 w-full max-w-3xl rounded shadow" />
          <h3 class="vs-section-title">검수 프레임 (4+1종 — 명암 실측 선별)</h3>
          <div class="mb-4 grid grid-cols-2 gap-2 md:grid-cols-5">
            <figure v-for="f in frames" :key="f.kind ?? f.t">
              <img :src="f.url" class="rounded border" />
              <figcaption class="text-center text-xs vs-ink-3">
                {{ KIND_LABEL[f.kind] ?? '' }} {{ f.t }}s
              </figcaption>
            </figure>
          </div>

          <template v-if="consistency?.titlePair?.prev">
            <h3 class="vs-section-title">타이틀 일관성 — 직전 회차와 나란히</h3>
            <div class="mb-4 grid max-w-3xl grid-cols-2 gap-2">
              <figure>
                <img :src="consistency.titlePair.prev" class="rounded border" />
                <figcaption class="text-center text-xs vs-ink-3">
                  {{ consistency.titlePair.prevId }}
                </figcaption>
              </figure>
              <figure>
                <img :src="consistency.titlePair.current" class="rounded border" />
                <figcaption class="text-center text-xs vs-ink-3">이번 회차</figcaption>
              </figure>
            </div>
          </template>
          <h3 class="vs-section-title">자막 대조</h3>
          <div v-if="subtitleCheck" class="mb-4 text-sm">
            <el-tag v-if="subtitleCheck.ok" type="success">
              .srt ↔ 대본 diff 0 ({{ subtitleCheck.chars?.toLocaleString() }}자) ✓
            </el-tag>
            <el-alert v-else type="error" :closable="false"
                      :title="`자막이 대본과 다르다 — ${subtitleCheck.reason}`">
              <div class="font-mono text-xs">srt: …{{ subtitleCheck.srtAround }}…</div>
              <div class="font-mono text-xs">대본: …{{ subtitleCheck.scriptAround }}…</div>
            </el-alert>
          </div>

          <h3 class="vs-section-title">검수 체크리스트 <span class="vs-section-note">— "봤다"의 기록 (out/review.json)</span></h3>
          <div class="mb-4">
            <el-checkbox v-for="item in CHECK_ITEMS" :key="item"
                         :model-value="checklist.items[item] ?? false"
                         @update:model-value="(v) => { checklist.items[item] = v; saveChecklist(); }">
              {{ item }}
            </el-checkbox>
            <span v-if="checklist.updatedAt" class="ml-2 text-xs vs-ink-3">
              기록 {{ checklist.updatedAt }}
            </span>
          </div>

          <h3 class="vs-section-title">무음 리포트</h3>
          <div v-if="silence" class="text-sm">
            총 {{ silence.silences.length }}건 · {{ silence.total }}초
            <el-tag v-if="!silence.suspect.length" type="success" size="small" class="ml-1">
              전부 문장 호흡 (정상)
            </el-tag>
            <el-table v-else :data="silence.suspect" size="small" class="mt-2 max-w-xl">
              <el-table-column prop="start" label="시작(s)" width="90" />
              <el-table-column prop="duration" label="길이(s)" width="90" />
              <el-table-column prop="cause" label="분류" />
            </el-table>
          </div>
        </template>
        <el-empty v-else description="아직 완성본이 없습니다 — 먼저 빌드하세요" />
      </el-tab-pane>

      <!-- ⑦ 배포 -->
      <el-tab-pane label="⑦ 배포" lazy>
        <DeployTab :eid="eid" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
