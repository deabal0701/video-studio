// 스톡 영상 구간 — 내려받은 클립을 그 구간 길이에 딱 맞는 mp4 한 장으로 정규화한다.
//
// 왜 별도 조각 종류를 만들지 않았는가: 합성기는 모션 구간을 이미 "그 길이짜리 mp4를 입력으로
// 받아 붙이는" 방식으로 처리한다(compose.js). 그러니 소스만 바꿔 끼우면 순서·자막·오디오
// 무음 padding·변형별 포함 여부가 전부 공짜로 따라온다. 대본에서는 모션 클립에 file 대신
// video를 쓰면 된다.
//
// 왜 HTML에 <video>를 넣지 않는가: 모션 렌더러는 document.getAnimations()의 currentTime만
// 밀며 프레임을 찍는다. <video>는 거기에 걸리지 않아 첫 프레임에서 얼어붙는다. 영상 다루기는
// 어차피 ffmpeg이 제일 잘한다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, ensureDir, run } from './util.js';

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.avif'];

function isFresh(source, output) {
  if (!fs.existsSync(output)) return false;
  return fs.statSync(output).mtimeMs >= fs.statSync(source).mtimeMs;
}

/**
 * 스톡 클립 하나를 duration 초짜리 mp4로 정규화한다 (소리는 버린다).
 * @param {object} o
 * @param {string} o.file    영상 작업 폴더 기준 상대 경로 (bgm과 같은 기준)
 * @param {number} o.start   소스에서 잘라 올 시작 시각(초). 기본 0
 * @param {number} o.shade   0~1. 위에 까는 검은 막의 진하기. 기본 0(그대로)
 * @returns {string} 만들어진 클립 경로
 */
export async function renderMediaClip({ file, duration, width, height, fps, dirs, id, force, start = 0, shade = 0 }) {
  const source = path.resolve(AD_DIR, file);
  if (!fs.existsSync(source)) throw new Error(`영상 소재가 없습니다: ${source}`);
  if (IMAGE_EXTS.includes(path.extname(source).toLowerCase())) {
    throw new Error(
      `사진은 video가 아니라 photo.html 템플릿으로 넣습니다: ${path.basename(source)}\n` +
        `  { "file": "photo.html", "params": { "src": "<motion/ 기준 상대경로>" } }`
    );
  }

  const key = JSON.stringify({ file, start, duration, width, height, fps, shade });
  const stamp = crypto.createHash('sha1').update(key).digest('hex').slice(0, 8);
  const output = path.join(ensureDir(dirs.motion), `${id}-media-${stamp}.mp4`);
  if (!force && isFresh(source, output)) return output;

  // 소스가 구간보다 짧으면 마지막 프레임을 물려 채운다(tpad). 짧은 B롤을 이어 붙이면
  // 점프컷처럼 튀는데, 생애사·다큐 톤에서는 한 프레임 붙드는 편이 덜 거슬린다.
  // shade: 자막은 B롤 위에 판 없이 얹히므로(subtitleBox:false) 밝거나 무늬가 복잡한
  // 소재에서는 흰 글자가 묻힌다 — 금색 파티클과 초록 헥스코드에서 실제로 걸렸다.
  // photo.html 의 shade 와 같은 역할을 여기서도 한다. 0.35 안팎이면 소재는 살고 글자는 뜬다.
  const dim = Math.min(Math.max(Number(shade) || 0, 0), 1);
  const chain = [
    `fps=${fps}`,
    `scale=${width}:${height}:force_original_aspect_ratio=increase`,
    `crop=${width}:${height}`,
    'setsar=1',
    ...(dim > 0 ? [`colorlevels=romax=${(1 - dim).toFixed(3)}:gomax=${(1 - dim).toFixed(3)}:bomax=${(1 - dim).toFixed(3)}`] : []),
    `tpad=stop_mode=clone:stop_duration=${duration.toFixed(3)}`,
    'format=yuv420p',
  ].join(',');

  await run('ffmpeg', [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...(start > 0 ? ['-ss', String(start)] : []),
    ...['-i', source],
    ...['-t', duration.toFixed(3)],
    ...['-an', '-vf', chain],
    ...['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p'],
    output,
  ]);

  return output;
}
