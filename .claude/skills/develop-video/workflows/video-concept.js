export const meta = {
  name: 'video-concept',
  description: '영상 컨셉 5안을 병렬 생성하고 3개 관점으로 검증해 1안을 확정한다',
  whenToUse: 'develop-video 4단계(대본 작성) 직전. 쇼츠·홍보·강의처럼 도입부가 성패를 가르는 영상에서 컨셉이 확정되지 않았을 때.',
  phases: [
    { title: '발산', detail: '컨셉 5안 병렬 생성 — 서로의 안을 모른다' },
    { title: '검증', detail: '안마다 제작가능성·후킹·사실 3개 관점 동시 심사' },
    { title: '종합', detail: '생존안 비교 후 1안 확정' },
  ],
}

// args: { brief, videoId, kind, constraints, videoRoot, assetsRoot }
// args 는 JSON 문자열이 아니라 실제 객체로 넘긴다. 문자열로 오면 아래에서 되살린다.
let a = args || {}
if (typeof a === 'string') {
  try {
    a = JSON.parse(a)
  } catch (e) {
    a = {}
  }
}

// 브리프 없이는 돌지 않는다. 기본값으로 조용히 진행하면 에이전트들이 스스로 주제를
// 정해 엉뚱한 컨셉에 수십만 토큰을 쓴다 — 실제로 한 번 그렇게 태웠다.
if (!a.brief || !String(a.brief).trim()) {
  return {
    status: 'no-brief',
    message: 'brief 가 비어 있어 중단했다. args 를 JSON 문자열이 아닌 객체로 넘겼는지 확인하라. 에이전트는 하나도 띄우지 않았다.',
    received: JSON.stringify(args),
  }
}

const brief = String(a.brief).trim()
const videoId = a.videoId || 'video'
const kind = a.kind || '쇼츠'
const constraints = a.constraints || '(명시된 제약 없음)'
const videoRoot = a.videoRoot || 'tools/video'
const assetsRoot = a.assetsRoot || '.claude/skills/develop-video/assets'

const CONTEXT = `
## 영상 정보
- 영상 id: ${videoId}
- 종류: ${kind}
- 브리프: ${brief}
- 제약: ${constraints}

## 이 저장소에서 쓸 수 있는 것
- 모션 템플릿: ${videoRoot}/motion/ (intro·chapter·stat·outro·photo·voicecard 등 .html)
- 소재: ${assetsRoot}/ 아래 photo/ broll/ bgm/ presenter/
- 소재 목록: ${assetsRoot}/CATALOG.md
- 문법: .claude/skills/develop-video/references/authoring.md
`.trim()

// ── 발산: 3개 서로 다른 각도. 각자 다른 안을 모른 채 독립 생성 ──────────
//
// 5개에서 3개로 줄였다. 첫 실행(21 에이전트·83만 토큰)에서 5안 중 3안이 탈락했고,
// 값진 지적은 각도의 개수가 아니라 검증 관점 3개에서 나왔다. 각도는 성격이 겹치지
// 않는 셋만 남긴다 — 논리(통념 반박) · 수치(숫자) · 이미지(시각).
// '서사 몰입'과 '질문 던지기'는 통념 반박과 훅 구조가 겹쳐 뺐다.
const ANGLES = [
  { key: 'contrarian', label: '통념 반박', hint: '시청자가 실제로 가진 통념을 먼저 특정하고 그것을 뒤집어라. 없는 통념을 지어내지 마라. 답을 미루는 질문으로 여는 변형도 좋다 — 다만 틀린 프레임을 미끼로 쓰지 마라.' },
  { key: 'number', label: '숫자 선타격', hint: '수치로 시작한다. 저장소나 공개 자료에 근거가 있는 숫자만 써라. 없으면 이 각도는 성립하지 않는다고 적어라.' },
  { key: 'visual', label: '시각 충격', hint: '말이 아니라 이미지만으로 이상함을 전달한다. 쓸 사진·영상이 실제로 있는지, 그 사진이 정말 당신이 상상한 구도인지 반드시 열어서 확인하라. 한 장면·한 사람에서 시작해 확장하는 서사형도 이 각도에 포함된다.' },
]

const IDEA_SCHEMA = {
  type: 'object',
  required: ['title', 'openingSeconds', 'body', 'assetsNeeded', 'whyItWorks'],
  properties: {
    title: { type: 'string', description: '안 이름 (10자 내외)' },
    openingSeconds: { type: 'string', description: '오프닝 3초를 구간별로. 예: 0.0-1.2s 화면/자막' },
    body: { type: 'string', description: '오프닝 이후 전개를 3~5문장으로' },
    assetsNeeded: { type: 'array', items: { type: 'string' }, description: '필요한 파일 경로. 이미 있는 것과 새로 구해야 하는 것을 구분해 적을 것' },
    whyItWorks: { type: 'string', description: '왜 스크롤을 멈추게 하는가' },
  },
}

phase('발산')

const LENSES = [
  {
    key: 'feasible',
    label: '제작가능성',
    prompt: (i) => `당신은 영상 제작 실무자다. 아래 컨셉이 **지금 이 저장소에서 실제로 만들 수 있는지**만 판정하라.

반드시 파일을 직접 열어 확인하라 — 추측 금지:
- ${assetsRoot}/photo/ · broll/ 에 필요한 소재가 실제로 있는가 (ls 로 확인)
- ${assetsRoot}/CATALOG.md 에 등재되어 있는가
- ${videoRoot}/motion/ 의 템플릿이 요구하는 연출을 지원하는가 (html 을 열어 params 를 확인)
- 없는 소재를 새로 구해야 한다면 그것이 무료 스톡(Mixkit·Pexels·Pixabay·Coverr)에서 조달 가능한가

**"소재가 없어서 착수 불가"인 안을 반드시 걸러내라.** 그것이 이 심사의 존재 이유다.

컨셉:
${JSON.stringify(i, null, 2)}`,
  },
  {
    key: 'hook',
    label: '후킹',
    prompt: (i) => `당신은 쇼츠 조회수를 분석하는 사람이다. 아래 컨셉의 **오프닝 3초가 실제로 스크롤을 멈추게 하는지**만 본다.

- 3초 안에 "이건 봐야겠다"가 성립하는가, 아니면 그냥 설명인가
- 훅이 가정하는 시청자 심리가 실재하는가 (예: "고장이라고 생각한다"는 통념이 정말 있나)
- 반전이 있다면 이탈 전에 도착하는가
- 틀린 프레임을 미끼로 던지고 나중에 뒤집는 구조라면, 낚인 채 이탈하는 시청자가 얼마나 될지 지적하라

**이해시키는 것과 궁금하게 만드는 것은 다르다.** 정보 밀도가 높다고 좋은 훅이 아니다.

컨셉:
${JSON.stringify(i, null, 2)}`,
  },
  {
    key: 'fact',
    label: '사실검증',
    prompt: (i) => `당신은 팩트체커다. 아래 컨셉에 **근거 없는 주장이 있는지**만 찾는다.

develop-video 원칙: "내레이션에 없는 기능이나 검증되지 않은 수치를 쓰지 않는다. 저장소에 근거가 있는 문구만 쓴다."

- 등장하는 모든 숫자를 나열하고 각각의 출처를 저장소에서 찾아라 (README·문서·코드를 grep)
- 출처를 못 찾은 숫자는 전부 위험으로 표시하라
- 제품 기능을 주장한다면 실제로 그 기능이 코드에 있는지 확인하라
- 저작권·초상권 문제가 될 소재 사용이 있는지 보라

**숫자 하나가 틀리면 영상 전체의 신뢰가 무너진다.** 관대하게 넘어가지 마라.

컨셉:
${JSON.stringify(i, null, 2)}`,
  },
]

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['viable', 'severity', 'strongest', 'fatalFlaw', 'hiddenAssumption', 'fixable'],
  properties: {
    viable: { type: 'boolean', description: '이 관점에서 이 안이 살아남는가' },
    severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'none'], description: 'blocker = 착수 자체가 불가' },
    strongest: { type: 'string', description: '이 관점에서 본 최대 강점' },
    fatalFlaw: { type: 'string', description: '최대 결함. 없으면 "없음"' },
    hiddenAssumption: { type: 'string', description: '이 안이 말없이 전제하는 것' },
    fixable: { type: 'string', description: '고칠 수 있다면 어떻게. 불가면 "불가"와 이유' },
  },
}

// 발산 → 검증을 pipeline 으로. 안 하나가 5안 전부를 기다리지 않는다.
const reviewed = await pipeline(
  ANGLES,
  (angle) =>
    agent(
      `${CONTEXT}

## 당신의 임무
"${angle.label}" 각도로 이 영상의 컨셉을 **1안** 만들어라.
${angle.hint}

오프닝 3초를 구간별로 쪼개서 쓰고, 필요한 소재는 실제 경로로 적어라.
${assetsRoot}/ 와 ${videoRoot}/motion/ 을 직접 확인해서 있는 것과 없는 것을 구분하라.

다른 각도의 안은 보지 못한다. 당신의 각도에 충실하라.`,
      { label: `안:${angle.label}`, phase: '발산', schema: IDEA_SCHEMA },
    ).then((idea) => (idea ? { ...idea, angle: angle.key, angleLabel: angle.label } : null)),

  (idea) => {
    if (!idea) return null
    return parallel(
      LENSES.map((lens) => () =>
        agent(lens.prompt(idea), {
          label: `검증:${idea.angleLabel}/${lens.label}`,
          phase: '검증',
          schema: VERDICT_SCHEMA,
        }).then((v) => (v ? { lens: lens.key, lensLabel: lens.label, ...v } : null)),
      ),
    ).then((verdicts) => ({ idea, verdicts: verdicts.filter(Boolean) }))
  },
)

const scored = reviewed.filter(Boolean).filter((r) => r.verdicts.length > 0)

// blocker 가 하나라도 있으면 탈락. 나머지는 major 개수로 정렬.
const survivors = scored.filter((r) => !r.verdicts.some((v) => v.severity === 'blocker'))
const killed = scored.filter((r) => r.verdicts.some((v) => v.severity === 'blocker'))

log(`발산 ${scored.length}안 → 생존 ${survivors.length}안 / 탈락 ${killed.length}안`)
for (const k of killed) {
  const b = k.verdicts.find((v) => v.severity === 'blocker')
  log(`  탈락: ${k.idea.title} (${k.idea.angleLabel}) — ${b.lensLabel}: ${b.fatalFlaw}`)
}

if (survivors.length === 0) {
  return {
    status: 'all-blocked',
    message: '모든 안이 blocker 판정. 브리프나 제약을 재검토해야 한다.',
    killed: killed.map((k) => ({
      title: k.idea.title,
      angle: k.idea.angleLabel,
      blockers: k.verdicts.filter((v) => v.severity === 'blocker').map((v) => `${v.lensLabel}: ${v.fatalFlaw}`),
    })),
  }
}

phase('종합')

const FINAL_SCHEMA = {
  type: 'object',
  required: ['chosen', 'why', 'openingSeconds', 'revisions', 'openRisks', 'nextMoves', 'runnerUp'],
  properties: {
    chosen: { type: 'string', description: '확정한 안 이름' },
    why: { type: 'string', description: '왜 이 안인가. 3가지 근거' },
    openingSeconds: { type: 'string', description: '검증 결과를 반영해 수정한 오프닝 3초 구간표' },
    revisions: { type: 'array', items: { type: 'string' }, description: '원안에서 무엇을 어떻게 고쳤는가' },
    openRisks: { type: 'array', items: { type: 'string' }, description: '미해결 리스크. 특히 사실검증에서 나온 미검증 수치' },
    nextMoves: { type: 'array', items: { type: 'string' }, description: '대본 쓰기 전에 확인할 것' },
    runnerUp: { type: 'string', description: '차점안과 보류 사유. 나중에 병합 가능한 요소가 있으면 적어라' },
  },
}

const final = await agent(
  `${CONTEXT}

## 당신의 임무
아래는 5개 각도로 만든 컨셉과, 각각에 대한 3개 관점(제작가능성·후킹·사실검증)의 독립 심사 결과다.
blocker 판정을 받은 안은 이미 제외되었다.

**생존안 중 하나를 확정하고, 심사에서 나온 지적을 반영해 수정하라.**

지켜야 할 것:
- 심사가 지적한 결함을 그냥 무시하고 원안을 밀지 마라. 고치거나, 못 고치면 다른 안을 골라라
- 사실검증에서 "출처 없음" 판정을 받은 숫자는 최종안에 그대로 남기지 마라. 검증 전까지는 다른 표현으로 대체하라
- 차점안에 병합할 만한 요소가 있으면 가져와라
- 미해결 리스크를 숨기지 마라. 특히 근거를 못 찾은 수치는 openRisks 에 반드시 명시하라

## 생존안과 심사 결과
${JSON.stringify(survivors, null, 2)}

## 탈락안 (참고 — 여기서 아이디어를 가져와도 되지만 blocker 사유는 반복하지 마라)
${JSON.stringify(
  killed.map((k) => ({ title: k.idea.title, angle: k.idea.angleLabel, blockers: k.verdicts.filter((v) => v.severity === 'blocker') })),
  null,
  2,
)}`,
  { label: '종합', phase: '종합', schema: FINAL_SCHEMA },
)

return {
  status: 'ok',
  videoId,
  kind,
  brief,
  generated: scored.length,
  survived: survivors.length,
  killed: killed.map((k) => ({
    title: k.idea.title,
    angle: k.idea.angleLabel,
    blockers: k.verdicts.filter((v) => v.severity === 'blocker').map((v) => `${v.lensLabel}: ${v.fatalFlaw}`),
  })),
  candidates: survivors.map((s) => ({
    title: s.idea.title,
    angle: s.idea.angleLabel,
    openingSeconds: s.idea.openingSeconds,
    verdicts: s.verdicts.map((v) => ({ lens: v.lensLabel, severity: v.severity, flaw: v.fatalFlaw })),
  })),
  final,
}
