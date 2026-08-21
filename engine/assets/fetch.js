// 소재 내려받기 — 무료 스톡 사이트의 직접 링크만 받는다.
//
// 사용:
//   node assets/fetch.js bgm  <url> [파일명]
//   node assets/fetch.js clip <url> [파일명]
//   node assets/fetch.js list
//
// 왜 허용 목록을 두는가: 유튜브 등에서 내려받은 영상·음원을 광고에 쓰면 이용약관 위반이자
// 저작권·초상권 문제가 된다. 정식으로 다운로드를 제공하고 상업적 사용을 허용하는 곳만 받는다.
// 라이선스 요약은 CATALOG.md 참고.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ASSETS_DIR = path.dirname(fileURLToPath(import.meta.url));

// 정식 배포 호스트만. 여기 없는 곳에서 받으려면 라이선스를 직접 확인하고 추가한다.
const ALLOWED_HOSTS = new Set([
  'assets.mixkit.co',
  'videos.pexels.com',
  'images.pexels.com',
  'cdn.pixabay.com',
  'pixabay.com',
  'assets.coverr.co',
]);

const KINDS = {
  bgm: { dir: 'bgm', exts: ['.mp3', '.m4a', '.wav', '.ogg'] },
  clip: { dir: 'presenter', exts: ['.mp4', '.mov', '.webm'] },
  photo: { dir: 'photo', exts: ['.jpg', '.jpeg', '.png', '.webp', '.avif'] },
  broll: { dir: 'broll', exts: ['.mp4', '.mov', '.webm'] },
};

function usage(message) {
  if (message) process.stderr.write(`${message}\n\n`);
  process.stdout.write(
    [
      '사용법:',
      '  node assets/fetch.js bgm   <url> [파일명]   배경음악을 assets/bgm/에 받는다',
      '  node assets/fetch.js clip  <url> [파일명]   인물 클립을 assets/presenter/에 받는다',
      '  node assets/fetch.js photo <url> [파일명]   사진을 assets/photo/에 받는다 (photo.html 배경)',
      '  node assets/fetch.js broll <url> [파일명]   B롤 영상을 assets/broll/에 받는다 (클립 video)',
      '  node assets/fetch.js list                   받아 둔 소재 목록',
      '',
      `허용 호스트: ${[...ALLOWED_HOSTS].join(', ')}`,
      '',
      '받은 파일은 git에서 제외된다(재배포 금지 라이선스가 대부분).',
      '어디서 받았는지는 CATALOG.md에 남길 것.',
    ].join('\n') + '\n'
  );
  process.exit(message ? 1 : 0);
}

function list() {
  for (const [kind, meta] of Object.entries(KINDS)) {
    const dir = path.join(ASSETS_DIR, meta.dir);
    const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => !f.startsWith('.')) : [];
    process.stdout.write(`\n[${kind}] ${path.relative(process.cwd(), dir)}\n`);
    if (!files.length) {
      process.stdout.write('  (없음)\n');
      continue;
    }
    for (const file of files) {
      const size = fs.statSync(path.join(dir, file)).size / 1024 / 1024;
      process.stdout.write(`  ${file.padEnd(40)} ${size.toFixed(1)} MB\n`);
    }
  }
  process.stdout.write('\n');
}

async function fetchAsset(kind, url, name) {
  const meta = KINDS[kind];
  if (!meta) usage(`알 수 없는 종류: ${kind}`);

  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    usage(`URL이 올바르지 않습니다: ${url}`);
  }
  if (!ALLOWED_HOSTS.has(parsed.hostname)) {
    process.stderr.write(
      `허용되지 않은 호스트입니다: ${parsed.hostname}\n` +
        '무료 스톡의 직접 링크만 받습니다. CATALOG.md를 확인하세요.\n'
    );
    process.exit(1);
  }

  const fallback = path.basename(parsed.pathname) || `asset-${kind}`;
  const fileName = name ?? fallback;
  if (!meta.exts.some((ext) => fileName.toLowerCase().endsWith(ext))) {
    process.stderr.write(`${kind}에 맞지 않는 확장자입니다 (${meta.exts.join(', ')}): ${fileName}\n`);
    process.exit(1);
  }

  const dir = path.join(ASSETS_DIR, meta.dir);
  fs.mkdirSync(dir, { recursive: true });
  const target = path.join(dir, fileName);

  process.stdout.write(`받는 중: ${url}\n`);
  const res = await fetch(url, { headers: { 'User-Agent': 'develop-video/1.0' } });
  if (!res.ok) {
    process.stderr.write(`실패 ${res.status} ${res.statusText}\n`);
    process.exit(1);
  }
  fs.writeFileSync(target, Buffer.from(await res.arrayBuffer()));
  const mb = fs.statSync(target).size / 1024 / 1024;
  process.stdout.write(`저장: ${path.relative(process.cwd(), target)} (${mb.toFixed(1)} MB)\n`);
  process.stdout.write('출처와 라이선스를 CATALOG.md에 기록하세요.\n');
}

const [kind, url, name] = process.argv.slice(2);
if (!kind || kind === '--help' || kind === '-h') usage();
else if (kind === 'list') list();
else if (!url) usage('URL이 필요합니다.');
else await fetchAsset(kind, url, name);
