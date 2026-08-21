<script setup>
// ⑤ 대본 에디터 — 3A 골격 + 3B 결함 차단 4종:
//   ① 오타 params → 템플릿이 받는 키만 폼 생성 (자유 키 입력 없음, 안 받는 키는 빨간 목록)
//   ② 상대경로 오류 → 피커로만 선택, 경로는 서버(paths.py)가 기입·검사(pathIssues)
//   ③ 브랜드 색·폰트 누락 → 자동 주입 키는 "강좌 상속 중" 뱃지 (수동 입력 불가)
//   ④ B롤 길이 초과 → 피커가 소재 길이를 알므로 duration > 소스−videoStart 즉시 빨강
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import draggable from 'vuedraggable';
import { api } from '../api/client';

const props = defineProps({
  eid: String, scenes: Object, etag: String, inspect: Object, budgetText: String,
});
const emit = defineEmits(['saved']);

const doc = reactive(JSON.parse(JSON.stringify(props.scenes)));
const clips = computed(() => doc.render?.motion?.clips ?? []);
const selected = ref(0);
const dirty = ref(false);
watch(doc, () => (dirty.value = true), { deep: true });

const gallery = ref([]);      // /api/templates?scope=eid — 피커 + 받는 키
const brollAssets = ref([]);  // /api/assets?kind=broll — 피커 + 길이
onMounted(async () => {
  gallery.value = await api(`/templates?scope=${props.eid}`).catch(() => []);
  brollAssets.value = await api('/assets?kind=broll').catch(() => []);
});

// ── 길이·예산 (02 — 강좌 6.4자/초) ──────────────────────────────────────────
const PACE = 6.4;
const audioCache = computed(() => props.inspect?.audioCache ?? {});
const clipSeconds = (c) => {
  const measured = audioCache.value[c.id];
  if (measured) return { s: Math.max(c.duration ?? 0, measured + 0.5), measured: true };
  if (c.narration) return { s: Math.max(c.duration ?? 0, c.narration.length / PACE + 0.5), measured: false };
  return { s: c.duration ?? 0, measured: true };
};
const narrationTotal = computed(() => clips.value.reduce((n, c) => n + (c.narration?.length ?? 0), 0));
const totalSeconds = computed(() => clips.value.reduce((n, c) => n + clipSeconds(c).s, 0));
const allMeasured = computed(() => clips.value.every((c) => clipSeconds(c).measured));
const budget = computed(() => {
  const m = /([\d,]+)\s*자/.exec(props.budgetText ?? '');
  return m ? Number(m[1].replaceAll(',', '')) : 1850;
});
const budgetPct = computed(() => Math.min(150, Math.round((narrationTotal.value / budget.value) * 100)));

const SKELETON = ['broll', 'title', 'hook', 'stinger', 'promise'];
const skeletonWarning = computed(() => {
  const ids = clips.value.map((c) => c.id).filter((id) => SKELETON.includes(id));
  return ids.join(',') !== SKELETON.filter((s) => ids.includes(s)).join(',')
    ? '골격 위치 규약(broll→title→hook→stinger→promise)과 순서가 다릅니다' : '';
});

// ── params 자동 폼 (③ 결함 차단 ①·③) ──────────────────────────────────────
// 강좌가 자동 주입하는 키 — 폼에 노출하지 않고 "상속 중" 뱃지만 (03 ⑤ 표)
const AUTO_KEYS = ['brand', 'brandSoft', 'bg', 'fg', 'font', 'fontUrl', 'wipeAt', 'wipeColor'];
const cur = computed(() => clips.value[selected.value]);
const acceptedKeys = computed(() => {
  const f = cur.value?.file;
  if (!f) return [];
  return props.inspect?.templates?.[f]?.params
    ?? gallery.value.find((t) => t.file === f)?.params ?? [];
});
const editableKeys = computed(() =>
  acceptedKeys.value.filter((k) => !AUTO_KEYS.includes(k) && k !== 'wipe'));
const unknownParams = computed(() => {
  if (!cur.value?.file || !acceptedKeys.value.length) return [];
  return Object.keys(cur.value.params ?? {}).filter((k) => !acceptedKeys.value.includes(k));
});
const setParam = (k, v) => {
  cur.value.params = cur.value.params ?? {};
  if (v === '' || v == null) delete cur.value.params[k];
  else cur.value.params[k] = v;
};
const dropUnknown = (k) => delete cur.value.params[k];

// ── 피커 (② 결함 차단) ─────────────────────────────────────────────────────
const tplPicker = ref(false);
const brollPicker = ref(false);
function pickTemplate(t) {
  cur.value.file = t.file;
  delete cur.value.video;
  delete cur.value.videoStart;
  tplPicker.value = false;
}
function pickBroll(a) {
  cur.value.video = a.ref;
  cur.value.videoStart = cur.value.videoStart ?? 0;
  cur.value.shade = cur.value.shade ?? 0.35;
  delete cur.value.file;
  delete cur.value.params;
  brollPicker.value = false;
}

// ── B롤 길이 검사 (④ 결함 차단 — 초과분은 정지 프레임) ─────────────────────
const brollCheck = computed(() => {
  const c = cur.value;
  if (!c?.video) return null;
  if (!brollAssets.value.length) return null; // 라이브러리 로딩 중 — 오탐 방지
  const src = brollAssets.value.find((a) => a.ref === c.video)
    ?? { duration: props.inspect?.media?.[c.video]?.duration ?? 0 };
  if (!src.duration) return { ok: false, msg: '소재 길이를 모릅니다 — 경로를 확인하세요' };
  const need = clipSeconds(c).s;
  const avail = src.duration - (c.videoStart ?? 0);
  return need > avail + 0.05
    ? { ok: false, msg: `구간 ${need.toFixed(1)}s > 쓸 수 있는 소스 ${avail.toFixed(1)}s — 마지막 ${(need - avail).toFixed(1)}s 정지 프레임` }
    : { ok: true, msg: `구간 ${need.toFixed(1)}s / 소스 여유 ${avail.toFixed(1)}s` };
});

// ── 발화시각 계산기 (03 ⑤ — 글자수÷페이스) ─────────────────────────────────
const selStart = ref(0);
const selText = ref('');
function onSelect(e) {
  selStart.value = e.target.selectionStart ?? 0;
  selText.value = (cur.value?.narration ?? '').slice(e.target.selectionStart, e.target.selectionEnd);
}
const spokenAt = computed(() => (selStart.value / PACE).toFixed(2));
const timeKeys = computed(() => editableKeys.value.filter((k) => /^t\d|^tterm|At$|Time$/i.test(k)));

// ── title 프레임 추출 (③ ⑤ 특수 버튼 — videoStart↔프레임 일치를 한 버튼으로) ──
const firstBroll = computed(() => clips.value.find((c) => c.video));
const canExtract = computed(() =>
  cur.value?.file && acceptedKeys.value.includes('src') && Boolean(firstBroll.value));
async function extractFrame() {
  const b = firstBroll.value;
  try {
    const out = await api(`/episodes/${props.eid}/bg-frame`, {
      method: 'POST',
      body: JSON.stringify({ video: b.video, videoStart: b.videoStart ?? 0,
                             clipFile: cur.value.file }),
    });
    setParam('src', out.src);
    ElMessage.success(`bg/${out.file} 추출 — src 기입됨 (B롤 ${b.videoStart ?? 0}s 프레임)`);
  } catch (e) {
    ElMessage.error(e.message);
  }
}

// ── 리스트 조작·저장 (3A) ───────────────────────────────────────────────────
function nextId(kind) {
  const ids = new Set(clips.value.map((c) => c.id));
  if (kind === 'chapter') { for (let n = 1; ; n += 1) if (!ids.has(`ch${n}`)) return `ch${n}`; }
  if (kind === 'diagram') {
    for (let n = 1; ; n += 1) for (const suf of ['a', 'b', 'c'])
      if (!ids.has(`s${n}${suf}`)) return `s${n}${suf}`;
  }
  for (let n = 1; ; n += 1) if (!ids.has(n === 1 ? 'broll' : `broll${n}`)) return n === 1 ? 'broll' : `broll${n}`;
}
function addClip(kind) {
  const id = nextId(kind);
  const clip = kind === 'chapter'
    ? { id, file: 'chapter.html', before: 'end', narration: '', params: { wipe: 'off' } }
    : kind === 'broll'
      ? { id, video: '', videoStart: 0, shade: 0.35, duration: 2.0, before: 'end' }
      : { id, file: '', before: 'end', narration: '', params: { wipe: 'off' } };
  doc.render.motion.clips.splice(selected.value + 1, 0, clip);
  selected.value += 1;
}
async function removeClip(i) {
  await ElMessageBox.confirm(`${clips.value[i].id} 클립을 삭제할까요?`, '삭제');
  doc.render.motion.clips.splice(i, 1);
  selected.value = Math.max(0, selected.value - 1);
}

// ── 프리뷰 (3C — D10: 프리뷰가 곧 실물) ─────────────────────────────────────
const iframeKey = ref(0);
const iframeEl = ref(null);
const scrub = ref(0);
const previewUrl = computed(() => {
  const c = cur.value;
  if (!c?.file) return null;
  const q = new URLSearchParams({ file: c.file, scope: props.eid });
  for (const [k, v] of Object.entries(c.params ?? {})) {
    if (v == null || v === '') continue;
    // 경로형 params 는 프리뷰 문서 기준으로는 깨진다 — API 자산 URL 로 치환 (실물 빌드는 원값)
    if (k === 'fontUrl') q.set(k, '/api/assets/file?kind=font&name=PretendardVariable.woff2');
    else if (k === 'src') q.set(k, `/api/episodes/${props.eid}/files?path=bg/${v.split('/').pop()}`);
    else q.set(k, String(v));
  }
  return `/api/templates/preview?${q.toString()}`;
});
const brollPreviewUrl = computed(() => {
  const c = cur.value;
  if (!c?.video) return null;
  return `/api/assets/file?kind=broll&name=${encodeURIComponent(c.video.split('/').pop())}#t=${c.videoStart ?? 0}`;
});
function seek(sec) {
  // 엔진 렌더와 같은 방식 — document.getAnimations() 의 currentTime 을 직접 민다 (motion.js)
  const doc = iframeEl.value?.contentDocument;
  if (!doc) return;
  for (const a of doc.getAnimations({ subtree: true })) {
    a.pause();
    a.currentTime = sec * 1000;
  }
}
watch(scrub, (s) => seek(s));
watch(cur, () => { scrub.value = 0; iframeKey.value += 1; });
const audioUrl = computed(() =>
  audioCache.value[cur.value?.id]
    ? `/api/media/${props.eid}/audio/motion-${cur.value.id}.mp3` : null);

// [TTS 실측 갱신] — --only tts 잡 (몇 초·무료) → 완료 시 inspect 재조회를 부모에 요청
const ttsRunning = ref(false);
async function refreshTts() {
  ttsRunning.value = true;
  try {
    const { jobId } = await api(`/episodes/${props.eid}/tts`, { method: 'POST' });
    for (let i = 0; i < 120; i += 1) {
      await new Promise((r) => setTimeout(r, 1000));
      const j = await api(`/jobs/${jobId}`);
      if (['done', 'failed', 'blocked', 'canceled'].includes(j.state)) {
        if (j.state === 'done') { ElMessage.success('TTS 실측 갱신 완료'); emit('saved'); }
        else ElMessage.error(`TTS 갱신 ${j.state}: ${j.error ?? ''}`);
        return;
      }
    }
  } catch (e) {
    ElMessage.error(e.message);
  } finally {
    ttsRunning.value = false;
  }
}

const saving = ref(false);
const pathIssues = ref([]);
async function save() {
  saving.value = true;
  try {
    const out = await api(`/episodes/${props.eid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'If-Match': props.etag },
      body: JSON.stringify(doc),
    });
    dirty.value = false;
    pathIssues.value = out.pathIssues ?? [];
    if (pathIssues.value.length) {
      ElMessage.warning(`저장됨 — 경로 문제 ${pathIssues.value.length}건 (아래 목록)`);
    } else {
      ElMessage.success(out.consistency?.length
        ? `저장됨 — 강좌 일관성 ${out.consistency.length}건 어긋남` : '저장됨');
      emit('saved');
    }
  } catch (e) {
    if (e.status === 409) {
      await ElMessageBox.alert('파일이 밖에서 바뀌었습니다 — 새로고침 후 다시 수정하세요.', '저장 충돌');
      emit('saved');
    } else ElMessage.error(e.message);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="grid grid-cols-12 gap-4">
    <!-- 좌: 클립 리스트 + 예산 -->
    <div class="col-span-3">
      <el-alert v-if="skeletonWarning" :title="skeletonWarning" type="warning"
                :closable="false" class="mb-2" />
      <draggable v-model="doc.render.motion.clips" item-key="id" handle=".drag-handle"
                 class="vs-panel divide-y"
                 @end="(e) => (selected = e.newIndex)">
        <template #item="{ element: c, index: i }">
          <div class="flex cursor-pointer items-center gap-2 px-3 py-2"
               :class="{ 'bg-[color:var(--vs-accent-soft)]': i === selected }" @click="selected = i">
            <span class="drag-handle cursor-grab vs-ink-3 hover:text-[color:var(--vs-ink)]">≡</span>
            <code class="w-16 text-xs font-bold">{{ c.id }}</code>
            <span class="flex-1 truncate text-xs vs-ink-2">{{ c.file ?? c.video ?? '—' }}</span>
            <el-tag size="small" :type="clipSeconds(c).measured ? 'success' : 'info'">
              {{ clipSeconds(c).s.toFixed(1) }}s{{ clipSeconds(c).measured ? '' : '?' }}
            </el-tag>
          </div>
        </template>
      </draggable>
      <div class="mt-2 flex gap-1">
        <el-button size="small" @click="addClip('chapter')">+ 챕터</el-button>
        <el-button size="small" @click="addClip('diagram')">+ 도식</el-button>
        <el-button size="small" @click="addClip('broll')">+ B롤</el-button>
      </div>
      <div class="vs-panel mt-4 p-3">
        <div class="mb-1 flex justify-between text-sm">
          <span>내레이션 {{ narrationTotal.toLocaleString() }} / {{ budget.toLocaleString() }}자</span>
          <span :class="budgetPct > 100 ? 'font-bold text-[color:var(--vs-danger)]' : 'vs-ink-2'">{{ budgetPct }}%</span>
        </div>
        <el-progress :percentage="Math.min(100, budgetPct)"
                     :status="budgetPct > 100 ? 'exception' : undefined" :show-text="false" />
        <div class="mt-1 text-xs vs-ink-2">
          {{ allMeasured ? '실측' : '추정' }} {{ Math.floor(totalSeconds / 60) }}:{{ String(Math.round(totalSeconds % 60)).padStart(2, '0') }}
          <span v-if="budgetPct > 100" class="text-[color:var(--vs-danger)]">— 넘치면 압축이 아니라 회차 분할</span>
        </div>
      </div>
      <el-button type="primary" class="mt-3 w-full" :loading="saving" :disabled="!dirty" @click="save">
        저장
      </el-button>
      <el-alert v-for="p in pathIssues" :key="p" :title="p" type="error" :closable="false" class="mt-2" />
    </div>

    <!-- 중: 클립 편집 -->
    <div class="col-span-5">
      <el-card v-if="cur">
        <div class="mb-3 flex items-center gap-3">
          <code class="text-lg font-bold">{{ cur.id }}</code>
          <el-button size="small" type="danger" plain class="ml-auto" @click="removeClip(selected)">삭제</el-button>
        </div>

        <!-- 화면 선택 — 피커로만 (경로 문자열을 만지지 않는다) -->
        <el-form label-width="90px" label-position="left">
          <el-form-item label="화면">
            <template v-if="cur.video !== undefined">
              <code class="text-xs">{{ cur.video || '(B롤 미선택)' }}</code>
              <el-button size="small" class="ml-2" @click="brollPicker = true">B롤 선택…</el-button>
            </template>
            <template v-else>
              <code class="text-xs">{{ cur.file || '(템플릿 미선택)' }}</code>
              <el-button size="small" class="ml-2" @click="tplPicker = true">템플릿 선택…</el-button>
            </template>
          </el-form-item>

          <el-form-item v-if="cur.video !== undefined" label="videoStart">
            <el-input-number v-model="cur.videoStart" :min="0" :step="0.5" />
            <span class="ml-3 text-xs vs-ink-3">shade</span>
            <el-input-number v-model="cur.shade" :min="0" :max="1" :step="0.05" class="ml-1" />
          </el-form-item>
          <el-alert v-if="brollCheck" :title="brollCheck.msg"
                    :type="brollCheck.ok ? 'success' : 'error'" :closable="false" class="mb-3" />

          <el-form-item label="내레이션">
            <el-input v-model="cur.narration" type="textarea" :rows="4" @select="onSelect"
                      :placeholder="cur.id === 'broll' ? '실사 인트로는 무내레이션(BGM만)이 관례' : ''" />
            <div class="mt-1 flex items-center gap-2 text-xs vs-ink-2">
              <span>{{ (cur.narration ?? '').length }}자 ·
                {{ audioCache[cur.id] ? `실측 ${audioCache[cur.id].toFixed(1)}s` : `추정 ${((cur.narration ?? '').length / 6.4).toFixed(1)}s` }}</span>
              <template v-if="selText">
                <span class="vs-ink-3">|</span>
                <span>"{{ selText.slice(0, 12) }}…" 발화 ≈ <b>{{ spokenAt }}s</b></span>
                <el-button v-for="k in timeKeys" :key="k" size="small" text type="primary"
                           @click="setParam(k, spokenAt)">→ {{ k }}</el-button>
              </template>
            </div>
          </el-form-item>

          <el-form-item v-if="!cur.narration" label="duration">
            <el-input-number v-model="cur.duration" :min="0.5" :step="0.5" />
            <span class="ml-2 text-xs vs-ink-3">무내레이션 클립만 직접 지정</span>
          </el-form-item>
        </el-form>

        <!-- params 자동 폼 — 템플릿이 받는 키만 -->
        <template v-if="cur.file && acceptedKeys.length">
          <el-divider content-position="left">
            params — {{ cur.file }} 이 받는 키만
            <el-button v-if="canExtract" size="small" class="ml-2" @click="extractFrame">
              B롤 프레임 추출 → src 기입
            </el-button>
          </el-divider>
          <div class="grid grid-cols-2 gap-x-6">
            <el-form-item v-for="k in editableKeys" :key="k" :label="k" label-width="90px">
              <el-input :model-value="cur.params?.[k] ?? ''" size="small"
                        @update:model-value="(v) => setParam(k, v)" />
            </el-form-item>
            <el-form-item label="wipe" label-width="90px">
              <el-select :model-value="cur.params?.wipe ?? 'off'" size="small"
                         @update:model-value="(v) => setParam('wipe', v)">
                <el-option value="off" label="off (모션 전용 기본)" />
                <el-option value="on" label="on (밝은 앱 화면으로 전환 시)" />
              </el-select>
            </el-form-item>
          </div>
          <div class="text-xs vs-ink-3">
            강좌 상속 중 (수동 입력 불가):
            <el-tag v-for="k in AUTO_KEYS.filter((k) => cur.params?.[k])" :key="k" size="small" class="mr-1">
              {{ k }} ✓
            </el-tag>
          </div>
          <el-alert v-for="k in unknownParams" :key="k" type="error" :closable="false" class="mt-2">
            <template #title>
              "{{ k }}" 는 {{ cur.file }} 이 받지 않는 키 — 화면에서 조용히 사라집니다
              <el-button size="small" text type="danger" @click="dropUnknown(k)">제거</el-button>
            </template>
          </el-alert>
        </template>
      </el-card>

      <!-- 템플릿 피커 -->
      <el-dialog v-model="tplPicker" title="도식 템플릿 선택" width="640">
        <el-table :data="gallery" size="small" max-height="420"
                  @row-click="pickTemplate" class="cursor-pointer">
          <el-table-column prop="file" label="파일" />
          <el-table-column prop="scope" label="범위" width="90" />
          <el-table-column label="받는 키" >
            <template #default="{ row }">
              <span class="text-xs vs-ink-2">
                {{ row.params.filter((k) => !AUTO_KEYS.includes(k) && k !== 'wipe').join(' · ') }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-dialog>

      <!-- B롤 피커 — 길이·라이선스를 보고 고른다 -->
      <el-dialog v-model="brollPicker" title="B롤 선택" width="640">
        <el-table :data="brollAssets" size="small" max-height="420"
                  @row-click="pickBroll" class="cursor-pointer">
          <el-table-column prop="name" label="파일" />
          <el-table-column label="길이·해상도" width="140">
            <template #default="{ row }">{{ row.duration }}s · {{ row.width }}×{{ row.height }}</template>
          </el-table-column>
          <el-table-column label="라이선스" width="150">
            <template #default="{ row }">
              <el-tag :type="row.licensed ? 'success' : 'danger'" size="small">
                {{ row.license || '없음' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-dialog>
    </div>

    <!-- 우: 프리뷰 (D10 — 엔진과 같은 문서·같은 시킹이라 프리뷰가 곧 실물) -->
    <div class="col-span-4">
      <el-card v-if="cur">
        <template v-if="previewUrl">
          <iframe ref="iframeEl" :key="iframeKey" :src="previewUrl"
                  class="aspect-video w-full rounded border-0 bg-black"
                  style="zoom: 0.9" />
          <div class="mt-2 flex items-center gap-2">
            <el-slider v-model="scrub" :min="0" :max="Math.max(1, clipSeconds(cur).s)"
                       :step="0.1" class="flex-1" />
            <span class="w-12 text-right text-xs vs-ink-2">{{ scrub.toFixed(1) }}s</span>
            <el-button size="small" @click="iframeKey += 1; scrub = 0">↻ 재생</el-button>
          </div>
        </template>
        <video v-else-if="brollPreviewUrl" :src="brollPreviewUrl" controls
               class="aspect-video w-full rounded bg-black" />
        <el-empty v-else description="화면을 선택하면 프리뷰가 뜹니다" :image-size="60" />

        <el-divider content-position="left">음성</el-divider>
        <audio v-if="audioUrl" :src="audioUrl" controls class="w-full" />
        <div v-else class="text-xs vs-ink-3">TTS 캐시 없음 — 아래 버튼으로 실측을 만드세요</div>
        <el-button size="small" class="mt-2" :loading="ttsRunning" @click="refreshTts">
          TTS 실측 갱신 (--only tts · 몇 초·무료)
        </el-button>
      </el-card>
    </div>
  </div>
</template>
