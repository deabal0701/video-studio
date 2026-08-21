// 대본 정적 검사 + 메타 조회를 JSON 한 방으로 — 기계(Python core/engine_io.py)용 CLI.
//
//   node engine/inspect.js --project <id|dir> [--json]
//   node engine/inspect.js --scenes <scenes.json 경로> [--out <out 루트>]
//
// 출력 계약 (docs/design/04_api.md):
//   {
//     preflight:  [{level:'error'|'warn', clip, msg}],
//     templates:  { "<clip.file>": { params: [...], path, exists } },
//     media:      { "<clip.video|render.bgm>": { duration, width, height, path, exists } },
//     audioCache: { "<clip.id>": duration }
//   }
//
// 규칙: 읽기와 계산뿐 — 아무것도 고치지 않는다. 기존 lib(preflight·util)를 재사용하고
// 기존 엔진 파일은 무수정(01_architecture 의 vendoring 예외 조항 — 앱 전용 신설 파일).
import fs from 'node:fs';
import path from 'node:path';
import { preflight } from './lib/preflight.js';
import { AD_DIR, OUT_DIR, parseArgs, readJson, run, videoDirs } from './lib/util.js';

// ── 템플릿이 받는 params — lib/preflight.js templateKeys 와 동일 규칙 ──────────
// (그 함수는 export 되지 않아 규칙을 그대로 옮겼다. data-p 속성 + 스크립트가 .get() 으로
// 직접 읽는 키 + _params.js 공통 키. 원본이 바뀌면 여기도 함께 맞춘다 — ENGINE_VERSION.md)
const COMMON_PARAMS = [
  'wipe', 'wipeAt', 'wipeColor', 'brand', 'brandSoft', 'bg', 'fg', 'font', 'fontUrl',
  'progress',
];
function templateKeys(file) {
  const html = fs.readFileSync(file, 'utf8');
  const keys = new Set();
  for (const m of html.matchAll(/data-p="([a-zA-Z][\w-]*)"/g)) keys.add(m[1]);
  for (const m of html.matchAll(/\.get\(\s*['"]([a-zA-Z][\w-]*)['"]\s*\)/g)) keys.add(m[1]);
  return [...keys];
}

const args = parseArgs();

// ── 갤러리 모드: --list-templates — 공용 motion/ (+ --project 회차 전용) 전체 목록 ──
// GET /api/templates 용 (04_api). 대본 없이도 동작한다.
if (args['list-templates']) {
  const dirs = [
    { scope: 'common', dir: path.join(AD_DIR, 'motion') },
    ...(args.project
      ? [{ scope: 'project', dir: path.resolve(String(args.project), 'motion') },
         { scope: 'project', dir: path.resolve(String(args.project)) }]
      : []),
  ];
  const templates = {};
  for (const { scope, dir } of dirs) {
    if (!fs.existsSync(dir)) continue;
    for (const name of fs.readdirSync(dir)) {
      if (!name.endsWith('.html') || name.startsWith('_')) continue;
      const file = path.join(dir, name);
      if (!fs.statSync(file).isFile()) continue;
      const key = scope === 'common' ? name : `motion/${name}`;
      if (templates[key]) continue;
      templates[key] = {
        scope, path: file,
        params: [...new Set([...templateKeys(file), ...COMMON_PARAMS])].sort(),
      };
    }
  }
  process.stdout.write(`${JSON.stringify({ templates }, null, 2)}\n`);
  process.exit(0);
}

// ── 대본 파일 결정 — build.js 와 같은 규칙 + --project 에 디렉토리 경로도 허용 ──
// (04_api 는 `--project <dir>` 로 부른다. build.js 의 id 방식도 그대로 동작해야 한다.)
let configFile;
if (args.scenes) {
  configFile = path.resolve(String(args.scenes));
} else if (args.project) {
  const p = String(args.project);
  const asDir = path.resolve(p);
  configFile = fs.existsSync(path.join(asDir, 'scenes.json'))
    ? path.join(asDir, 'scenes.json')
    : path.join(AD_DIR, 'projects', p, 'scenes.json');
} else {
  configFile = path.join(AD_DIR, 'scenes.json');
}
if (!fs.existsSync(configFile)) {
  process.stderr.write(`대본을 찾지 못했습니다: ${configFile}\n`);
  process.exit(2);
}

const config = readJson(configFile);
if (config.render?.motion) config.render.motion.projectDir = path.dirname(configFile);

const fallbackId = path.basename(configFile, '.json').replace(/^scenes[.\-_]?/, '');
const dirs = videoDirs(
  args.out ? path.resolve(String(args.out)) : OUT_DIR,
  (args.project && !fs.existsSync(path.resolve(String(args.project)))) ? args.project : (config.id ?? fallbackId)
);
const motionDir = path.resolve(AD_DIR, config.render?.motion?.dir ?? 'motion');
const clips = config.render?.motion?.clips ?? [];

// ── TTS 캐시 — 실측 음성 길이 (build.js [0] 사전 점검과 같은 읽기) ──────────────
const audioCache = {};
try {
  const manifest = readJson(path.join(dirs.audio, 'manifest.json'));
  for (const [key, v] of Object.entries(manifest)) {
    audioCache[key.replace(/^motion-/, '')] = v.duration;
  }
} catch {
  /* 첫 실행이면 캐시가 없다 */
}

// compose.js resolveMotionFile 과 같은 순서 — 전용(projects/<id>/) 먼저, 공용 motion/ 폴백.
const resolveTemplate = (name) =>
  [path.join(path.dirname(configFile), name), path.join(motionDir, name)].find((f) => fs.existsSync(f))
  ?? path.join(motionDir, name);

const templates = {};
for (const clip of clips) {
  if (!clip.file || templates[clip.file]) continue;
  const tpl = resolveTemplate(clip.file);
  const exists = fs.existsSync(tpl);
  templates[clip.file] = {
    params: exists ? [...new Set([...templateKeys(tpl), ...COMMON_PARAMS])].sort() : [],
    path: tpl,
    exists,
  };
}

// ── 미디어 실측 (ffprobe) — B롤은 엔진 루트 기준, bgm 은 out/<id>/work/ 기준 ──────
async function probe(file) {
  try {
    const { out } = await run('ffprobe', [
      '-v', 'error',
      '-select_streams', 'v:0',
      '-show_entries', 'stream=width,height:format=duration',
      '-of', 'json', file,
    ]);
    const info = JSON.parse(out);
    return {
      duration: Number.parseFloat(info.format?.duration) || 0,
      width: info.streams?.[0]?.width ?? 0,
      height: info.streams?.[0]?.height ?? 0,
    };
  } catch {
    return { duration: 0, width: 0, height: 0 };
  }
}

const media = {};
const mediaTargets = [];
for (const clip of clips) {
  if (clip.video && !mediaTargets.some(([k]) => k === clip.video)) {
    mediaTargets.push([clip.video, path.resolve(AD_DIR, clip.video)]);
  }
}
if (config.render?.bgm) {
  // compose.js 실측: "bgm 경로는 영상 작업 폴더 기준" — AD_DIR(엔진 루트)로 고정돼 있다.
  mediaTargets.push([config.render.bgm, path.resolve(AD_DIR, config.render.bgm)]);
}
for (const [key, abs] of mediaTargets) {
  const exists = fs.existsSync(abs);
  media[key] = { ...(exists ? await probe(abs) : { duration: 0, width: 0, height: 0 }), path: abs, exists };
}

// ── 사전 점검 — lib/preflight.js 그대로 ──────────────────────────────────────
const findings = preflight({
  config,
  motionDir,
  videoRoot: AD_DIR,
  audioDurations: audioCache,
  videoId: dirs.id,
});

process.stdout.write(
  `${JSON.stringify({ preflight: findings, templates, media, audioCache }, null, 2)}\n`
);
