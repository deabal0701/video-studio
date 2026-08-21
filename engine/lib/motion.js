// 모션그래픽 구간 — HTML/CSS 애니메이션을 프레임 단위로 굽어 광고 중간에 끼워 넣는다.
//
// 인트로·전환 카드·수치 강조처럼 "찍을 실물이 없는" 구간을 웹 기술로 만든다. 앱 화면 녹화와
// 같은 Playwright를 쓰지만 대상이 로컬 HTML이라는 점만 다르다.
//
// 녹화(recordVideo)가 아니라 프레임을 한 장씩 찍는 이유: 헤드리스 녹화는 프레임이 불규칙하게
// 빠져 결과물의 타임라인이 실시간과 어긋난다. 2~3초짜리 짧은 구간에서는 그 오차가 그대로
// "애니메이션이 잘렸다"로 나타난다. Web Animations API로 `currentTime`을 직접 밀어 가며
// 찍으면 프레임이 정확히 대응하고, 같은 입력이면 항상 같은 결과가 나온다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, ensureDir, resolvePlaywright, run } from './util.js';

// Playwright는 실제로 구울 때 찾는다 — 최상단에서 부르면 import 만으로 죽어서, 브라우저가
// 필요 없는 경로(`--only tts` 로 목소리부터 고르는 단계)까지 같이 막힌다. 게다가 안내문이
// 스택 트레이스에 파묻혀, 새로 클론한 사람이 "무엇을 설치해야 하는지"를 못 읽는다.

// 템플릿은 혼자 서 있지 않다 — 여섯 장 전부가 같은 폴더의 `_base.css`·`_params.js` 를 불러온다.
// html 하나만 보면 공용 파일에서 브랜드 색·여백을 고쳐도 캐시가 그대로 살아남아, 몇 번을 다시
// 돌려도 예전 카드가 나온다(원인을 찾기 어려운 종류의 고장이다). 딸린 `_*.css`·`_*.js` 까지 본다.
function sourceFiles(source) {
  const dir = path.dirname(source);
  const shared = fs
    .readdirSync(dir)
    .filter((name) => /^_.+\.(css|js)$/i.test(name))
    .map((name) => path.join(dir, name));
  return [source, ...shared];
}

// 소재가 하나라도 결과물보다 새로우면 다시 굽는다 — 프레임 캡처는 비싼 단계라 그 외에는 넘어간다.
function isFresh(sources, output) {
  if (!fs.existsSync(output)) return false;
  const outMs = fs.statSync(output).mtimeMs;
  return sources.every((file) => fs.statSync(file).mtimeMs <= outMs);
}

/**
 * HTML 한 장을 duration 초짜리 mp4로 굽는다.
 * params는 질의 문자열로 넘어가고 페이지가 `location.search`에서 읽는다 — 같은 템플릿을
 * 문구만 바꿔 여러 번 쓰기 위한 장치다(챕터 카드, 수치 강조 등).
 * @returns {string} 만들어진 클립 경로
 */
export async function renderMotionClip({
  file,
  duration,
  width,
  height,
  fps,
  dirs,
  id,
  force,
  params,
}) {
  const source = path.resolve(AD_DIR, file);
  if (!fs.existsSync(source)) throw new Error(`모션 파일이 없습니다: ${source}`);

  const query = new URLSearchParams(params ?? {}).toString();
  // 같은 템플릿이라도 문구나 길이가 다르면 다른 결과물이다 — 파일명에 해시를 넣어 캐시를 분리한다.
  // duration 을 키에 넣는 이유: 보통은 wipeAt(= duration 에서 계산)이 질의에 섞여 들어가지만,
  // 대본이 params.wipeAt 을 직접 지정하면 그 고리가 끊긴다. 그러면 내레이션이 길어져 구간이
  // 늘어나도 예전 길이의 클립이 그대로 나와 뒤 구간 전체가 밀린다.
  // file 도 키에 넣는다: 같은 구간의 템플릿만 바꾸면(stat.html → 도식.html) 문구·길이가 그대로라
  // 해시가 안 바뀌어 **예전 템플릿의 렌더가 그대로 재사용된다**. 합성은 성공하고 그 구간만
  // 옛 화면으로 나오므로 프레임을 뽑기 전에는 모른다 — 실제로 한 번 겪었다.
  const key = JSON.stringify({ file, query, duration: Number(duration.toFixed(3)) });
  const stamp = crypto.createHash('sha1').update(key).digest('hex').slice(0, 8);
  const output = path.join(ensureDir(dirs.motion), `${id}-${stamp}-${width}x${height}.mp4`);
  if (!force && isFresh(sourceFiles(source), output)) return output;

  // 프레임 폴더도 결과물과 같은 키로 나눈다. 같은 클립을 16:9·9:16 두 번 굽는데, 이름이
  // id 하나뿐이면 두 렌더가 같은 폴더를 쓰고 시작할 때 서로를 rm -rf 한다. 지금은 변형을
  // 순서대로 처리해 부딪히지 않지만, 결과물만 크기로 갈라 두고 임시물은 안 갈라 두면
  // 나중에 이 단계를 병렬로 돌리는 순간 조용히 깨진다.
  const frameDir = path.join(dirs.work, `frames-${id}-${stamp}-${width}x${height}`);
  fs.rmSync(frameDir, { recursive: true, force: true });
  ensureDir(frameDir);

  const { chromium } = resolvePlaywright();
  const browser = await chromium.launch({
    headless: true,
    // file:// 에서 웹폰트를 읽으려면 필요하다 (Pretendard를 frontend/public에서 그대로 쓴다).
    args: ['--allow-file-access-from-files', '--force-device-scale-factor=1'],
  });

  try {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
    const url = `file://${source.replace(/\\/g, '/')}${query ? `?${query}` : ''}`;
    await page.goto(url, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready).catch(() => {});

    const frames = Math.max(1, Math.round(duration * fps));
    for (let i = 0; i < frames; i += 1) {
      await page.evaluate((ms) => {
        for (const animation of document.getAnimations()) {
          animation.pause();
          animation.currentTime = ms;
        }
      }, (i / fps) * 1000);
      await page.screenshot({ path: path.join(frameDir, `f${String(i).padStart(5, '0')}.png`) });
    }

    await run('ffmpeg', [
      ...['-hide_banner', '-loglevel', 'error', '-y'],
      ...['-framerate', String(fps), '-i', path.join(frameDir, 'f%05d.png')],
      ...['-vf', `scale=${width}:${height},setsar=1`],
      ...['-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p'],
      output,
    ]);
  } finally {
    await browser.close().catch(() => {});
  }

  fs.rmSync(frameDir, { recursive: true, force: true });
  return output;
}

/** 변형이 쓸 모션 구간 목록을 정리한다 (변형별 제외 지원). */
export function motionClipsFor(motion, variantId) {
  if (!motion || motion.enabled === false) return [];
  return (motion.clips ?? []).filter(
    (clip) => clip.enabled !== false && (!clip.variants || clip.variants.includes(variantId))
  );
}
