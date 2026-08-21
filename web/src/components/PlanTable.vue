<script setup>
// ④ 구성표 표 구조 편집기 — "구간 배분" 표만 구조화 편집하고 나머지 문서는 그대로 보존한다.
// 예산 게이지가 여기서 실시간으로 돈다 (03 ④: "예산이 여기서 결정된다").
import { computed, reactive, watch } from 'vue';

const props = defineProps({ markdown: String, budgetText: String });
const emit = defineEmits(['update:markdown']);

const SECTION = '## 구간 배분';

function locate(md) {
  const lines = md.split('\n');
  const s = lines.findIndex((l) => l.trim().startsWith(SECTION));
  if (s < 0) return null;
  let header = -1;
  let end = -1;
  for (let i = s + 1; i < lines.length; i += 1) {
    if (lines[i].startsWith('## ')) break;
    if (!lines[i].startsWith('|')) {
      if (header >= 0 && end >= 0) break;
      continue;
    }
    const cells = lines[i].split('|').map((c) => c.trim());
    if (header < 0 && lines[i].includes('구간') && lines[i].includes('화면')) header = i;
    else if (header >= 0) end = i;
  }
  return header >= 0 ? { lines, header, end } : null;
}

const state = reactive({ headerCells: [], rows: [], ok: false, idIdx: 0, charsIdx: 3 });

function parse() {
  const loc = locate(props.markdown ?? '');
  state.ok = Boolean(loc);
  if (!loc) return;
  const { lines, header, end } = loc;
  state.headerCells = lines[header].slice(1, -1).split('|').map((c) => c.trim());
  state.idIdx = state.headerCells.findIndex((c) => c.includes('구간'));
  state.charsIdx = state.headerCells.findIndex((c) => c.includes('글자수'));
  state.rows = [];
  for (let i = header + 1; i <= end; i += 1) {
    const cells = lines[i].slice(1, -1).split('|').map((c) => c.trim());
    if (cells.every((c) => /^[-: ]*$/.test(c))) continue; // 구분선
    state.rows.push(cells);
  }
}
watch(() => props.markdown, parse, { immediate: true });

const isTotalRow = (cells) => cells.some((c) => c.includes('합계'));
const charsSum = computed(() =>
  state.rows.filter((r) => !isTotalRow(r))
    .reduce((n, r) => n + (parseInt((r[state.charsIdx] ?? '').replace(/\D/g, ''), 10) || 0), 0));
const budget = computed(() => {
  const m = /([\d,]+)\s*자/.exec(props.budgetText ?? '');
  return m ? Number(m[1].replaceAll(',', '')) : 1850;
});
const pct = computed(() => Math.round((charsSum.value / budget.value) * 100));

function serialize() {
  const loc = locate(props.markdown);
  if (!loc) return;
  const { lines, header, end } = loc;
  const sep = lines.slice(header + 1, end + 1).find((l) => /^\|[-: |]+\|$/.test(l.trim()))
    ?? `|${state.headerCells.map(() => '---').join('|')}|`;
  const rowLines = state.rows.map((cells) => `| ${cells.join(' | ')} |`);
  const next = [...lines.slice(0, header + 1), sep, ...rowLines, ...lines.slice(end + 1)];
  emit('update:markdown', next.join('\n'));
}

function addRow() {
  state.rows.splice(state.rows.length, 0, state.headerCells.map((_, i) =>
    i === state.idIdx ? 'new' : i === state.charsIdx ? '0' : ''));
  serialize();
}
function removeRow(i) {
  state.rows.splice(i, 1);
  serialize();
}
</script>

<template>
  <div v-if="state.ok">
    <div class="mb-2 flex items-center gap-3">
      <span class="text-sm">
        예산 {{ charsSum.toLocaleString() }} / {{ budget.toLocaleString() }}자
      </span>
      <el-progress :percentage="Math.min(100, pct)" :show-text="false" class="w-48"
                   :status="pct > 100 ? 'exception' : undefined" />
      <span :class="pct > 100 ? 'text-sm font-bold text-[color:var(--vs-danger)]' : 'text-sm vs-ink-2'">
        {{ pct }}%{{ pct > 100 ? ' — 넘치면 압축이 아니라 회차 분할' : '' }}
      </span>
    </div>
    <table class="w-full border-collapse text-sm">
      <thead>
        <tr>
          <th v-for="h in state.headerCells" :key="h"
              class="border bg-[color:var(--vs-bg-page)] px-2 py-1 text-left text-xs">{{ h }}</th>
          <th class="border bg-[color:var(--vs-bg-page)] px-1" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, ri) in state.rows" :key="ri"
            :class="{ 'bg-[color:var(--vs-bg-page)] vs-ink-3': isTotalRow(row) }">
          <td v-for="(cell, ci) in row" :key="ci" class="border px-1 py-0.5">
            <input :value="cell" class="w-full bg-transparent px-1 py-0.5 text-sm outline-none"
                   @change="(e) => { row[ci] = e.target.value; serialize(); }" />
          </td>
          <td class="border px-1 text-center">
            <button v-if="!isTotalRow(row)" class="text-xs text-red-400 hover:text-red-600"
                    @click="removeRow(ri)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>
    <el-button size="small" class="mt-2" @click="addRow">+ 구간 추가</el-button>
  </div>
  <el-alert v-else type="info" :closable="false"
            title="구간 배분 표를 찾지 못했습니다 — 원문 편집으로 작성하세요 (헤더에 '구간'과 '화면' 필요)" />
</template>
