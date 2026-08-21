// 유튜브 광고 영상 빌드 — 대본(scenes.json) → 음성 → 화면 녹화 → 합성.
// 사용:
//   node tools/ad-video/build.js                       전체 실행 (기본 변형 모두)
//   node tools/ad-video/build.js --only tts            음성만 (목소리·속도 고를 때)
//   node tools/ad-video/build.js --only record         녹화만 (타임라인 갱신)
//   node tools/ad-video/build.js --only compose        합성만 (자막·BGM 손볼 때, 재촬영 없음)
//   node tools/ad-video/build.js --variant shorts-9x16 특정 변형만
//   node tools/ad-video/build.js --provider sapi       오프라인 폴백 음성
//   node tools/ad-video/build.js --headed              브라우저를 띄워 놓고 촬영 (디버깅)
import fs from 'node:fs';
import path from 'node:path';
import { composeVariant } from './lib/compose.js';
import { preflight, reportPreflight, scanBlankFrames } from './lib/preflight.js';
import { recordTake } from './lib/record.js';
import { resolveVoice, synthesizeScenes } from './lib/tts.js';
import { AD_DIR, OUT_DIR, displayPath, ensureVideoDirs, loadEnv, lockVideoDir, parseArgs, readJson, run, secs, videoDirs } from './lib/util.js';

// 조치 방법이 메시지에 다 들어 있는 오류(util.js 의 expected)는 스택 없이 그것만 찍는다.
// 스택을 함께 찍으면 "무엇을 설치하라"는 두 줄이 프레임 사이에 파묻혀 안 읽힌다.
// 표시가 없는 오류는 진짜 버그이므로 스택을 그대로 남긴다.
// 최상위 await 에서 던진 오류는 uncaughtException 이 아니라 unhandledRejection 으로 오므로 둘 다 받는다.
const bail = (err) => {
  if (err?.expected) process.stderr.write(`\n${err.message}\n`);
  else console.error(err);
  process.exit(1);
};
process.on('uncaughtException', bail);
process.on('unhandledRejection', bail);

// API 키(Azure Speech 등)는 .env 에서 읽는다. 셸에 이미 있는 값이 우선이고, 없을 때만 채운다.
for (const { file, count } of loadEnv()) {
  process.stdout.write(`.env ${displayPath(file)} — ${count}개 적용\n`);
}

const args = parseArgs();
const only = args.only ?? 'all';
// 대본은 --scenes 가 우선이고, 없으면 --project 로 projects/<id>/scenes.json 을 찾는다.
// 영상 한 편의 입력물(대본·전용 모션·facts)은 projects/<id>/ 한 폴더에 모은다 —
// 대본이 tools/video 직속에 평평하게 쌓이면 영상 수만큼 무한히 늘어난다.
const projectScenes = args.project && !args.scenes
  ? path.join(AD_DIR, 'projects', String(args.project), 'scenes.json')
  : null;
const configFile = path.resolve(
  args.scenes ?? (projectScenes && fs.existsSync(projectScenes) ? projectScenes : path.join(AD_DIR, 'scenes.json'))
);
const config = readJson(configFile);

const baseUrl = (args['base-url'] ?? config.baseUrl).replace(/\/$/, '');
// 목소리(성별·언어)와 제공자는 명령줄에서 덮어쓸 수 있다.
const voice = {
  ...config.voice,
  ...(args.provider ? { provider: args.provider } : {}),
  ...(args.gender ? { gender: args.gender } : {}),
  ...(args.lang ? { lang: args.lang } : {}),
  ...(args.voice ? { voice: args.voice } : {}),
};
const render = config.render ?? {};
// 전용 모션 템플릿(한 영상에서만 쓰는 것)은 대본 옆에 둔다. compose 가 대본 폴더를 먼저
// 뒤지고 없으면 공용 motion/ 으로 내려가므로, 공용 폴더가 영상별 파일로 어질러지지 않는다.
if (render.motion) render.motion.projectDir = path.dirname(configFile);

// 영상 한 편 = out/<id>/ 한 폴더. id는 --project > scenes.json의 "id" > 대본 파일 이름 순으로 정한다
// (scenes.json → default, scenes.promo.json → promo). 여러 편을 만들어도 서로 덮어쓰지 않는다.
const fallbackId = path.basename(configFile, '.json').replace(/^scenes[.\-_]?/, '');
const dirs = ensureVideoDirs(
  videoDirs(args.out ? path.resolve(args.out) : OUT_DIR, args.project ?? config.id ?? fallbackId)
);
// 다른 id 끼리는 쓰는 경로가 안 겹쳐 병렬로 돌려도 되지만, 같은 id 를 겹쳐 돌리면 서로의
// 중간물을 덮어써서 양쪽 다 "완료"를 찍고도 깨진 mp4 가 나온다. 여기서 미리 끊는다.
lockVideoDir(dirs);

// 세로(쇼츠) 변형은 켜고 끌 수 있다 — 세로 비율인지로 판별한다.
const isVertical = (v) => v.height > v.width;
let variants = config.variants.filter((v) => !args.variant || v.id === args.variant);
if (args['no-shorts']) variants = variants.filter((v) => !isVertical(v));
if (args['only-shorts']) variants = variants.filter(isVertical);
if (!variants.length) throw new Error(`변형을 찾지 못했습니다: ${args.variant}`);

const step = (n, title) => process.stdout.write(`\n[${n}] ${title}\n`);

// ── 0. 사전 점검 ──────────────────────────────────────────────────────────────
// 굽기 전에 대본을 정적으로 훑는다. 이 파이프라인의 결함은 대부분 오류를 내지 않고
// "합성 성공 + 화면만 틀림"으로 끝나는데, 그걸 알아채려면 수십 분을 굽고 프레임을 뽑아야 한다.
// 판단 자료는 굽기 전에 이미 다 있으므로 여기서 1초에 잡는다. --skip-preflight 로 끌 수 있다.
if (!args['skip-preflight']) {
  step(0, '사전 점검');
  // 지난 실행이 남긴 음성 길이가 있으면 쓴다 — B롤이 소스보다 길어지는지는 음성 길이로 정해지는데,
  // 굽기 전에는 그 값이 없다. 캐시가 있으면 정확히, 없으면 선언한 duration 으로만 본다.
  let audioDurations = {};
  try {
    const manifest = readJson(path.join(dirs.audio, 'manifest.json'));
    for (const [key, v] of Object.entries(manifest)) {
      audioDurations[key.replace(/^motion-/, '')] = v.duration;
    }
  } catch {
    /* 첫 실행이면 캐시가 없다 — 그래도 나머지 검사는 그대로 돈다 */
  }

  const found = preflight({
    config,
    motionDir: path.resolve(AD_DIR, config.render?.motion?.dir ?? 'motion'),
    videoRoot: AD_DIR,
    audioDurations,
    videoId: dirs.id,
  });
  if (reportPreflight(found)) {
    process.stdout.write('\n대본을 고친 뒤 다시 실행하세요 (무시하려면 --skip-preflight).\n');
    process.exit(1);
  }
}

// ── 1. 음성 ───────────────────────────────────────────────────────────────────
step(1, `TTS (${voice.provider} / ${resolveVoice(voice)})`);
const scenes = await synthesizeScenes(config.scenes, voice, dirs, { force: Boolean(args.force) });
for (const s of scenes) {
  process.stdout.write(`  · ${s.id.padEnd(6)} ${secs(s.audioDuration).padStart(7)}${s.cached ? '  (캐시)' : ''}  ${s.narration}\n`);
}
// 엔드카드는 촬영 대상이 아니라 합성 단계에서 만드는 화면이라 음성만 따로 만든다.
let endCard = render.endCard ?? null;
if (endCard?.narration) {
  const [spoken] = await synthesizeScenes([{ id: 'endcard', narration: endCard.narration }], voice, dirs, {
    force: Boolean(args.force),
  });
  endCard = {
    ...endCard,
    audioFile: spoken.audioFile,
    duration: Math.max(endCard.duration ?? 0, spoken.audioDuration + 0.8),
  };
  process.stdout.write(`  · 엔드카드 ${secs(endCard.duration).padStart(7)}  ${endCard.narration}\n`);
}

// 클립에 voice를 주면 그 구간만 다른 목소리로 읽는다 — 목소리 견본 카탈로그나 두 사람이
// 주고받는 구성에 쓴다. 문자열이면 목소리 id 를, 객체면 전역 voice 위에 덮어쓸 값을 준다
// (`{ "gender": "male", "rate": "+8%" }` 처럼 일부만 바꿔도 된다).
// 캐시 해시가 voiceConfig 를 포함하므로(lib/tts.js) 목소리만 바꿔도 그 구간만 다시 만든다.
const clipVoice = (clip) =>
  !clip.voice
    ? voice
    : { ...voice, ...(typeof clip.voice === 'string' ? { voice: clip.voice } : clip.voice) };

// 모션 구간도 대사가 있으면 미리 만들어 두고, 그 길이만큼 구간을 늘린다.
for (const clip of render.motion?.clips ?? []) {
  if (!clip.narration) continue;
  const spokenVoice = clipVoice(clip);
  const [spoken] = await synthesizeScenes(
    [{ id: `motion-${clip.id}`, narration: clip.narration }],
    spokenVoice,
    dirs,
    { force: Boolean(args.force) }
  );
  clip.audioFile = spoken.audioFile;
  clip.duration = Math.max(clip.duration ?? 0, spoken.audioDuration + 0.5);
  const tag = clip.voice ? `  [${resolveVoice(spokenVoice)}]` : '';
  process.stdout.write(
    `  · 모션 ${clip.id.padEnd(8)} ${secs(clip.duration).padStart(7)}${tag}  ${clip.narration}\n`
  );
}

const narrationTotal =
  scenes.reduce((sum, s) => sum + s.audioDuration + (s.hold ?? 0.6), 0) +
  (render.motion?.clips ?? []).reduce((sum, c) => sum + (c.duration ?? 0), 0) +
  (endCard?.duration ?? 0);
process.stdout.write(`  합계 ${secs(narrationTotal)} (hold·엔드카드 포함)\n`);
if (only === 'tts') process.exit(0);

// ── 2. 녹화 ───────────────────────────────────────────────────────────────────
const timelineFile = path.join(dirs.raw, 'timeline.json');
let take;
if (!scenes.length) {
  // 모션그래픽 전용 영상 — 찍을 화면이 없으니 앱을 띄울 필요도 없다.
  // 이 검사가 --only compose보다 먼저다. 녹화를 아예 안 했으니 timeline.json도 없고,
  // 뒤에 두면 모션 전용 영상에서 "timeline.json이 없습니다"로 재합성이 막힌다.
  take = { videoFile: '', leadIn: 0, ...config.capture, scenes: [] };
  step(2, '녹화 건너뜀 — 화면 씬이 없습니다 (모션그래픽 전용)');
} else if (only === 'compose') {
  if (!fs.existsSync(timelineFile)) {
    throw new Error('timeline.json이 없습니다. --only record 를 먼저 실행하세요.');
  }
  take = readJson(timelineFile);
  step(2, '녹화 건너뜀 — 기존 take.webm 사용');
} else {
  step(2, `녹화 (${baseUrl} · ${config.capture.width}×${config.capture.height})`);
  take = await recordTake(scenes, { ...config.capture, storageState: config.capture.storageState ? path.resolve(AD_DIR, config.capture.storageState) : '' }, dirs, {
    headed: Boolean(args.headed),
    baseUrl,
  });
  process.stdout.write(`  리드인 ${secs(take.leadIn)} · 본편 ${secs(take.scenes.at(-1).end)}\n`);
}
if (only === 'record') process.exit(0);

// ── 3. 합성 ───────────────────────────────────────────────────────────────────
step(3, `합성 (${variants.length}개 변형)`);
for (const variant of variants) {
  const result = await composeVariant({ variant, take, scenes, endCard, config: render, dirs });
  process.stdout.write(
    `  ✓ ${path.relative(process.cwd(), result.file)}  ${secs(result.duration)}  ${variant.label ?? ''}\n`
  );
  // 완성본에 빈 화면(전환 공백)이 남았는지 바로 재 본다. 눈으로 프레임을 뽑기 전에는
  // 안 보이는 결함이고, 사람이 지나치면 그대로 나간다 — 실제로 두 번 통과했다.
  const blanks = await scanBlankFrames(result.file, { run });
  if (blanks.length) {
    const total = blanks.reduce((a, b) => a + b.duration, 0);
    process.stdout.write(
      `    ⚠ 빈 화면 ${blanks.length}곳 · 합계 ${total.toFixed(1)}s — 가장 긴 곳 ` +
        blanks.sort((a, b) => b.duration - a.duration).slice(0, 3)
          .map((b) => `${b.start.toFixed(1)}s(${b.duration.toFixed(1)}s)`).join(', ') + '\n'
    );
  }
}
process.stdout.write(
  `\n완료 — ${path.relative(process.cwd(), dirs.root)}\n` +
    `  final/   납품물 (mp4 · srt)\n` +
    `  raw/     take.webm · timeline.json — 재합성에 쓰이므로 지우지 않는다\n` +
    `  audio/ motion/  캐시 · work/ 중간물 · frames/ 검증 캡처\n`
);
