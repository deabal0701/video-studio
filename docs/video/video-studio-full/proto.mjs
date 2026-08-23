// 프로토 렌더 — 굽기 전에 템플릿 한 장씩 눈으로 본다.
//
//   node docs/video/video-studio-full/proto.mjs [구간id ...]
//
// 대본(scenes.json)에서 **params 를 그대로 읽어** 렌더한다. 손으로 옮겨 적으면
// "프로토는 멀쩡한데 완성본은 다른" 상황이 생긴다(2026-08-22 실측 교훈).
// engine/lib/motion.js 와 같은 방식으로 띄운다 — file:// + 질의문자열 + getAnimations()
// currentTime 밀기. 그래서 여기 보이는 것이 곧 완성본의 그 프레임이다.
//
// 전체 빌드는 수십 분, 이 스크립트는 십여 초다. 크롭이 말한 것을 잘라 먹었는지,
// 도식의 글자가 넘쳤는지는 여기서 잡는다.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(DIR, '../../..');
const OUT = path.join(DIR, 'proto');
fs.mkdirSync(OUT, { recursive: true });

const config = JSON.parse(fs.readFileSync(path.join(DIR, 'scenes.json'), 'utf8'));
const clips = config.render.motion.clips;
const only = process.argv.slice(2);

// 언제의 프레임을 볼 것인가.
//   appshot: 강조(ht)가 뜬 직후 — 강조가 엉뚱한 데를 가리키는지 보려면 그때다
//   도식   : 마지막 요소가 뜬 뒤 — 등장 시각을 대본에서 받으므로 t* 중 최대값을 쓴다
//            (예전엔 8.4초 고정이라 반쯤 그려진 그림만 보고 "괜찮다"고 넘겼다)
const timeFor = (c) => {
  const p = c.params ?? {};
  if (p.ht) return Number(p.ht) + 1.6;
  const ts = Object.entries(p)
    .filter(([k]) => /^t\d$|^t[gsn]$/.test(k))
    .map(([, v]) => Number(v))
    .filter((v) => Number.isFinite(v));
  return ts.length ? Math.max(...ts) + 2.2 : 8.4;
};

// Windows 절대경로는 동적 import 에 그대로 못 넣는다 — file:// URL 로 바꿔야 한다.
// playwright 는 CJS 라 네임스페이스가 default 아래로 들어오는 경우가 있다.
const pw = await import(
  pathToFileURL(path.join(REPO, 'engine/node_modules/playwright/index.js')).href
);
const chromium = pw.chromium ?? pw.default?.chromium;
const browser = await chromium.launch({
  headless: true,
  args: ['--allow-file-access-from-files', '--force-device-scale-factor=1'],
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });

let n = 0;
for (const clip of clips) {
  if (only.length && !only.includes(clip.id)) continue;
  // 공용 템플릿(intro·chapter·outro)은 이미 검증된 것이라 건너뛴다
  const local = path.join(DIR, clip.file);
  if (!fs.existsSync(local)) continue;

  const query = new URLSearchParams(clip.params ?? {}).toString();
  const url = `file://${local.replace(/\\/g, '/')}${query ? `?${query}` : ''}`;
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready).catch(() => {});
  // 그림(appshot)은 로드를 기다린다 — 안 기다리면 틀 폭 계산(fitFrame) 전에 찍힌다
  await page.evaluate(() => {
    const img = document.getElementById('shot');
    if (!img) return null;
    return img.complete ? null : new Promise((r) => img.addEventListener('load', r, { once: true }));
  });
  const t = timeFor(clip);
  await page.evaluate((ms) => {
    for (const a of document.getAnimations()) { a.pause(); a.currentTime = ms; }
  }, t * 1000);
  const file = path.join(OUT, `${clip.id}.png`);
  await page.screenshot({ path: file });
  n += 1;
  process.stdout.write(`  ✓ ${clip.id.padEnd(11)} t=${t.toFixed(1)}s  ${clip.file}\n`);
}
await browser.close();
process.stdout.write(`\n${n}장 → ${OUT}\n`);
