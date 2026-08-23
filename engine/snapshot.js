// 모션 html 1장을 지정 시각으로 시킹해 **정지 프레임 png 1장**으로 굽는다.
//
//   node engine/snapshot.js --file <이름|경로> [--project <회차 폴더>] --out <png>
//                           [--at 3] [--width 1920] [--height 1080] [--params "a=1&b=2"]
//
// AI 도식의 렌더 확인 루프(05_agent D18)가 이 프레임을 vision 되먹임으로 쓴다.
// 시킹 방식은 lib/motion.js 와 동일 — getAnimations 를 멈추고 currentTime 을 민다
// (헤드리스 녹화는 프레임이 빠져 못 쓴다는 실측 그대로).
//
// 01_architecture 의 vendoring 예외 조항에 따른 앱 전용 신설 파일 3호(inspect·preview 와
// 같은 조항) — 기존 엔진 파일 무수정, lib 재사용만.
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, parseArgs, resolvePlaywright } from './lib/util.js';

const args = parseArgs();
if (!args.file || !args.out) {
  process.stderr.write(
    '사용: node snapshot.js --file <이름|경로> --out <png> [--project <회차 폴더>] [--at 3]\n');
  process.exit(2);
}

// preview.js resolveMotionFile 과 같은 순서 — 회차 전용 먼저, 공용 motion/ 폴백.
const candidates = [
  args.project && path.resolve(String(args.project), String(args.file)),
  args.project && path.resolve(String(args.project), 'motion', String(args.file)),
  path.resolve(AD_DIR, 'motion', String(args.file)),
  path.resolve(String(args.file)),
].filter(Boolean);
const source = candidates.find((f) => fs.existsSync(f) && fs.statSync(f).isFile());
if (!source) {
  process.stderr.write(`템플릿을 찾지 못했습니다: ${args.file}\n`);
  process.exit(2);
}

const width = Number(args.width ?? 1920);
const height = Number(args.height ?? 1080);
const atMs = Math.max(0, Number(args.at ?? 3) * 1000);

const { chromium } = resolvePlaywright();
const browser = await chromium.launch({
  headless: true,
  // file:// 웹폰트 로드 — motion.js 렌더와 같은 조건으로 찍는다
  args: ['--allow-file-access-from-files', '--force-device-scale-factor=1'],
});
try {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  const query = args.params ? `?${args.params}` : '';
  await page.goto(`file://${source.replace(/\\/g, '/')}${query}`, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready).catch(() => {});
  await page.evaluate((ms) => {
    for (const animation of document.getAnimations()) {
      animation.pause();
      animation.currentTime = ms;
    }
  }, atMs);
  await page.screenshot({ path: String(args.out) });
} finally {
  await browser.close().catch(() => {});
}
