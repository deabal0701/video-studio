// 영상 파이프라인 공용 유틸 — 외부 프로세스 실행, 미디어 길이 측정, 환경 탐색.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const AD_DIR = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
export const OUT_DIR = path.join(AD_DIR, 'out');

// ── 영상 한 편의 폴더 구조 ────────────────────────────────────────────────────
// 영상 한 편(= scenes.json 하나) 이 out/<영상 id>/ 하나를 차지한다. 한 저장소에서 홍보·매뉴얼·
// 릴리스 노트를 같이 만들어도 서로 섞이지 않고, 지난 영상을 다시 뽑을 때 그 폴더만 있으면 된다.
// 안쪽은 "납품할 것"과 "지워도 되는 것"이 눈으로 갈리게 나눈다.
//
//   out/<id>/final/    <변형>.mp4 · <변형>.srt   납품물. 이 폴더만 넘기면 된다
//   out/<id>/raw/      take.webm · timeline.json 재촬영 없이 다시 합성하려면 필요 — 지우지 않는다
//   out/<id>/audio/    씬별 음성 · manifest.json TTS 캐시 (지우면 다시 합성한다)
//   out/<id>/motion/   모션·B롤 렌더 결과        캐시
//   out/<id>/work/     ass · 무음 · 마스크       중간물. 언제든 지워도 된다
//   out/<id>/frames/   검증용 프레임 캡처        6단계에서 눈으로 확인한 근거를 남긴다
export const VIDEO_SUBDIRS = ['final', 'raw', 'audio', 'motion', 'work', 'frames'];

// 영상 id는 그대로 폴더 이름이 된다 — 경로에 못 쓰는 글자만 막는다.
// 글자·숫자는 유니코드로 받는다(`\w`는 한글을 버려서 "매뉴얼 v2"가 "v2"가 된다).
// 공백·슬래시·따옴표 따위는 하이픈으로 바꾼다.
export function videoId(raw) {
  const id = String(raw ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}._-]+/gu, '-')
    .replace(/^[-.]+|[-.]+$/g, '');
  return id || 'default';
}

export function videoDirs(outRoot, id) {
  const dirs = { id: videoId(id), root: path.join(outRoot, videoId(id)) };
  for (const name of VIDEO_SUBDIRS) dirs[name] = path.join(dirs.root, name);
  return dirs;
}

export function ensureVideoDirs(dirs) {
  for (const name of VIDEO_SUBDIRS) ensureDir(dirs[name]);
  return dirs;
}

// ── 사람이 읽어야 하는 오류 ───────────────────────────────────────────────────
// "Playwright 를 설치하세요" 같은 안내는 조치 방법이 메시지 안에 다 들어 있다. 그런데 그대로
// 던지면 Node 가 스택 트레이스를 함께 찍어서, 정작 읽어야 할 두 줄이 프레임 대여섯 줄 사이에
// 파묻힌다 — 처음 클론한 사람이 "무엇을 설치해야 하는지"를 못 찾는다. 이 표시가 붙은 오류는
// build.js 가 메시지만 깔끔하게 찍는다. 진짜 버그(예상 못 한 오류)는 스택을 그대로 남긴다.
export function expected(message) {
  const err = new Error(message);
  err.expected = true;
  return err;
}

// ── 영상 폴더 잠금 ────────────────────────────────────────────────────────────
// 서로 다른 id 는 쓰는 경로가 하나도 겹치지 않아 마음껏 병렬로 돌려도 된다. 문제는 **같은 id**다.
// 두 프로세스가 같은 폴더를 쓰면 ass·무음·완성본을 서로 덮어쓰고 모션 프레임 폴더를 서로
// rm -rf 해서, 양쪽 다 "완료"를 찍는데 나온 mp4 는 h264 NAL 이 깨져 있다. 실패보다 나쁘다 —
// 성공했다고 믿고 납품하게 된다. 파일 하나로 선점해 두 번째 실행을 시작 전에 끊는다.
function pidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0); // 신호 0 은 보내지 않고 존재만 확인한다
    return true;
  } catch (err) {
    return err.code === 'EPERM'; // 살아 있지만 남의 프로세스
  }
}

export function lockVideoDir(dirs) {
  const file = path.join(dirs.root, '.lock');
  const mine = `${JSON.stringify({ pid: process.pid, at: new Date().toISOString() })}\n`;

  try {
    fs.writeFileSync(file, mine, { flag: 'wx' }); // 이미 있으면 EEXIST
  } catch (err) {
    if (err.code !== 'EEXIST') throw err;
    let owner = null;
    try {
      owner = JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
      /* 내용이 깨진 잠금은 주인이 없는 것으로 본다 */
    }
    if (owner && pidAlive(owner.pid)) {
      throw expected(
        `같은 영상 id 로 이미 실행 중입니다: ${dirs.id} (pid ${owner.pid}, ${owner.at} 시작)\n` +
          `  --project 로 id 를 나누세요. 두 작업이 같은 폴더를 쓰면 결과물이 조용히 깨집니다.\n` +
          `  강제로 풀려면: rm ${file}`
      );
    }
    // 죽은 프로세스(강제 종료·재부팅)가 남긴 잠금 — 이어받는다.
    fs.writeFileSync(file, mine, 'utf8');
  }

  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    fs.rmSync(file, { force: true });
  };
  // 정상 종료·예외·process.exit(--only tts 등) 모두 'exit' 를 거친다.
  process.on('exit', release);
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.on(signal, () => {
      release();
      process.exit(130);
    });
  }
  return release;
}

// 프로젝트 루트는 깊이를 가정하지 않고 위로 올라가며 찾는다 — 이 파이프라인은 어느 저장소의
// 어느 하위 경로에 놓이든 동작해야 한다.
function findRoot(from) {
  let dir = from;
  for (let i = 0; i < 8; i += 1) {
    if (fs.existsSync(path.join(dir, '.git')) || fs.existsSync(path.join(dir, 'package.json'))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return from;
}

export const ROOT = findRoot(path.dirname(AD_DIR));

// ── .env ──────────────────────────────────────────────────────────────────────
// API 키(Azure Speech 등)를 파일로 두기 위한 최소 로더. 외부 의존성을 늘리지 않으려고
// dotenv 패키지를 쓰지 않는다 — 이 파이프라인의 의존성은 ffmpeg·Playwright·edge-tts뿐이다.

// 영상 작업 폴더에서 위로 올라가며 .env를 모은다 (tools/video/.env → … → 저장소 루트/.env).
// 저장소 표시(.git·package.json)를 만나면 거기까지만 본다 — 남의 저장소나 홈 디렉터리의
// .env를 주워 오면 안 된다. 마지막으로 실행 위치(cwd)도 본다.
// 가까운 파일이 먼저 오고, 먼저 들어간 값이 이긴다.
export function envFiles() {
  const seen = new Set();
  const files = [];
  const add = (dir) => {
    const file = path.join(dir, '.env');
    if (seen.has(file)) return;
    seen.add(file);
    if (fs.existsSync(file)) files.push(file);
  };
  let dir = AD_DIR;
  for (let i = 0; i < 8; i += 1) {
    add(dir);
    // 영상 작업 폴더 자신은 저장소 루트로 보지 않는다 — 여기에도 package.json 을 깔기 때문이다.
    const isRoot =
      i > 0 && (fs.existsSync(path.join(dir, '.git')) || fs.existsSync(path.join(dir, 'package.json')));
    const parent = path.dirname(dir);
    if (isRoot || parent === dir) break;
    dir = parent;
  }
  add(process.cwd());

  // 마지막 후보(우선순위 가장 낮음) — 사용자 홈의 **공용 키 파일**.
  //
  //   %USERPROFILE%\.claude\develop-video.env   (Windows)
  //   ~/.claude/develop-video.env               (macOS·Linux)
  //
  // 이게 있어야 "스킬 폴더만 복사하면 끝"이 azure·eleven 까지 성립한다. 프로젝트마다 .env 를
  // 심으면 키가 저장소 수만큼 흩어지고 교체할 때 전부 찾아다녀야 한다.
  //
  // **스킬 폴더 안에 두지 않는 이유**: 그 폴더는 프로젝트 사이를 복사해 다니라고 만든 물건이다.
  // 키를 넣으면 사본마다 비밀이 따라다니고, 남에게 스킬을 건네는 순간 같이 건너간다.
  // 키는 한 곳(여기 또는 셸 환경변수)에 두고 코드가 찾아가는 쪽이 맞다.
  //
  // 위의 위로-올라가기가 홈 디렉터리를 훑지 않는 규칙과 충돌하지 않는다 — 그건 남의 `.env` 를
  // **우연히** 주워 오지 말자는 것이고, 이건 이 파이프라인 전용 이름을 **일부러** 찾는 것이다.
  const home = process.env.USERPROFILE || process.env.HOME;
  if (home) {
    const shared = path.join(home, '.claude', 'develop-video.env');
    if (!seen.has(shared)) {
      seen.add(shared);
      if (fs.existsSync(shared)) files.push(shared);
    }
  }
  return files;
}

// KEY=VALUE 한 줄 형식만 받는다. `export ` 접두사·따옴표·주석(#)은 벗겨 낸다.
export function parseEnv(text) {
  const out = {};
  for (const raw of text.replace(/^\uFEFF/, '').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 1) continue;
    const key = line.slice(0, eq).replace(/^export\s+/, '').trim();
    let value = line.slice(eq + 1).trim();
    const quoted = value.length > 1 && (value.startsWith('"') || value.startsWith("'")) && value.at(-1) === value[0];
    // 따옴표로 감쌌으면 안쪽을 그대로 쓰고(값에 # 이 들어갈 수 있다), 아니면 줄 끝 주석을 자른다.
    value = quoted ? value.slice(1, -1) : value.replace(/\s+#.*$/, '').trim();
    if (key) out[key] = value;
  }
  return out;
}

// 이미 설정된 환경변수는 덮어쓰지 않는다 — 셸에서 준 값이 파일보다 우선한다.
// 빈 값(`AZURE_SPEECH_KEY=`)은 "설정 안 함"으로 본다. 샘플을 그대로 복사해 두어도
// 빈 문자열 키로 Azure 호출이 401로 죽지 않게 하기 위함이다.
export function loadEnv() {
  const loaded = [];
  for (const file of envFiles()) {
    let applied = 0;
    for (const [key, value] of Object.entries(parseEnv(fs.readFileSync(file, 'utf8')))) {
      if (!value) continue;
      if (process.env[key]) continue;
      process.env[key] = value;
      applied += 1;
    }
    if (applied) loaded.push({ file, count: applied });
  }
  return loaded;
}

// Playwright 설치 위치는 저장소마다 다르다(루트·backend·frontend·apps/* …). 순서대로 찾는다.
let cachedPlaywright = null;
export function resolvePlaywright() {
  if (cachedPlaywright) return cachedPlaywright;
  const anchors = [AD_DIR, ROOT];
  for (const entry of ['backend', 'server', 'api', 'frontend', 'web', 'app', 'apps', 'packages']) {
    const dir = path.join(ROOT, entry);
    if (!fs.existsSync(dir)) continue;
    anchors.push(dir);
    for (const child of fs.readdirSync(dir, { withFileTypes: true })) {
      if (child.isDirectory()) anchors.push(path.join(dir, child.name));
    }
  }
  for (const anchor of anchors) {
    for (const name of ['playwright', 'playwright-core']) {
      try {
        cachedPlaywright = createRequire(path.join(anchor, 'noop.js'))(name);
        return cachedPlaywright;
      } catch {
        /* 다음 후보 */
      }
    }
  }
  // 브라우저 실물(수 GB)은 ~/.cache/ms-playwright 에 전역으로 공유되므로, 이미 다른 프로젝트에서
  // 받아 두었다면 아래 설치는 18MB 짜리 패키지만 받고 몇 초 만에 끝난다.
  throw expected(
    'Playwright를 찾지 못했습니다. 영상 작업 폴더에 설치하세요:\n' +
      `  npm --prefix ${path.relative(process.cwd(), AD_DIR) || '.'} i -D playwright\n` +
      `  npx --prefix ${path.relative(process.cwd(), AD_DIR) || '.'} playwright install chromium   # 브라우저가 없을 때만\n` +
      '저장소 어딘가(프론트엔드 등)에 이미 있으면 그걸 그대로 씁니다 — 또 깔 필요 없습니다.'
  );
}

// 자막 글꼴은 시스템에 설치된 것만 쓸 수 있다 — OS별 한글 기본값.
export function defaultSubtitleFont() {
  if (process.platform === 'win32') return 'Malgun Gothic';
  if (process.platform === 'darwin') return 'Apple SD Gothic Neo';
  return 'Noto Sans CJK KR';
}

// 경로를 사람이 읽을 수 있게 찍는다 — 프로젝트 안이면 상대 경로, 밖이면 절대 경로(홈은 ~ 로).
// 상대 경로로만 찍으면 홈의 공용 .env 가 `..\..\..\..\..\..\..\..\.claude\develop-video.env`
// 가 되어 어디를 읽었는지 알아볼 수 없다.
export function displayPath(file) {
  const rel = path.relative(process.cwd(), file);
  // 윈도에서 드라이브가 다르면(D:\작업 ↔ C:\Users\…) path.relative 는 상대 경로를 만들지 못하고
  // **절대 경로를 그대로** 돌려준다. `..` 로 시작하지 않는다고 "프로젝트 안"으로 보면 홈 경로가
  // 안 줄어든다 — 그래서 절대 경로인지도 함께 본다.
  if (rel && !rel.startsWith('..') && !path.isAbsolute(rel)) return rel;
  const home = process.env.USERPROFILE || process.env.HOME;
  if (home && file.startsWith(home)) return `~${file.slice(home.length)}`;
  return file;
}

export function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

// 셸을 거치지 않고(인자 배열 그대로) 실행한다 — 한글·따옴표가 든 대본을 그대로 넘기기 위함.
export function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { windowsHide: true, ...opts });
    let out = '';
    let err = '';
    child.stdout?.on('data', (d) => {
      out += d;
    });
    child.stderr?.on('data', (d) => {
      err += d;
    });
    child.on('error', reject);
    child.on('close', (code) =>
      code === 0
        ? resolve({ out, err })
        : reject(new Error(`${cmd} ${args.join(' ')}\n→ exit ${code}\n${err.slice(-3000)}`))
    );
  });
}

export async function tryRun(cmd, args, opts) {
  try {
    return await run(cmd, args, opts);
  } catch {
    return null;
  }
}

export async function mediaDuration(file) {
  const { out } = await run('ffprobe', [
    '-v',
    'error',
    '-show_entries',
    'format=duration',
    '-of',
    'csv=p=0',
    file,
  ]);
  const seconds = Number.parseFloat(out.trim());
  if (!Number.isFinite(seconds)) throw new Error(`길이를 읽지 못했습니다: ${file}`);
  return seconds;
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const secs = (n) => `${n.toFixed(2)}s`;

export function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

export function writeJson(file, value) {
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

// --flag value / --flag 형태만 받는 최소 파서 (tools/ 다른 스크립트와 같은 수준으로 단순하게).
export function parseArgs(argv = process.argv.slice(2)) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith('--')) continue;
    const key = argv[i].slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      args[key] = next;
      i += 1;
    } else {
      args[key] = true;
    }
  }
  return args;
}
