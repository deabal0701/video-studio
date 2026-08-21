// 인물 PiP — 직접 촬영한 클립(또는 사진)을 씬 타임라인에 맞춰 한 장의 투명 배경 트랙으로 만든다.
//
// 씬마다 한 컷씩 찍으면 같은 파일이 음성(tts.js의 file 제공자)과 인물 영상 양쪽으로 쓰인다.
// 클립이 씬보다 짧으면 마지막 프레임을 물려 채우고(tpad), 길면 잘라 정확히 맞춘다.
// 사진을 넣으면 얼어붙어 보이지 않게 아주 느린 줌을 건다.
//
// 합성을 두 번에 나눈 이유: 투명 배경 트랙을 먼저 뽑아 두면 본 합성에서는 overlay 한 번으로
// 끝나고, 인물 트랙만 따로 열어 확인할 수 있다.
//
// alphamerge에 shortest=1이 반드시 필요하다. 마스크가 `-loop 1`로 들어오는 무한 스트림이라
// 이게 없으면 첫 구간에서 끝나지 않고 계속 프레임을 뱉어 뒤 구간이 아예 나오지 않는다.
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, ensureDir, run } from './util.js';

const VIDEO_EXTS = ['mp4', 'mov', 'mkv', 'webm'];
const IMAGE_EXTS = ['png', 'jpg', 'jpeg', 'webp'];

export function findPresenterMedia(dir, id) {
  for (const ext of [...VIDEO_EXTS, ...IMAGE_EXTS]) {
    const file = path.join(dir, `${id}.${ext}`);
    if (fs.existsSync(file)) return { file, isImage: IMAGE_EXTS.includes(ext) };
  }
  return null;
}

// 원형 마스크는 geq로 만든다 — 픽셀마다 식을 계산하는 느린 필터라 정지 이미지로 한 번만 굽고
// 이후엔 그 PNG를 재사용한다 (영상 전체에 걸면 몇 분씩 걸린다).
async function makeCircleMask(size, file) {
  if (fs.existsSync(file)) return file;
  await run('ffmpeg', [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...['-f', 'lavfi', '-i', `color=c=black:s=${size}x${size}`],
    ...[
      '-vf',
      `geq=lum='if(lte(hypot(X-${size / 2},Y-${size / 2}),${size / 2 - 1}),255,0)':cb=128:cr=128,format=gray`,
    ],
    ...['-frames:v', '1'],
    file,
  ]);
  return file;
}

// 원본에서 정사각형을 어디서 얼마나 떼어낼지. 그냥 가운데를 자르면 얼굴이 보통 화면 위쪽에
// 있어서 원 안이 책상·가슴으로 차 버린다. zoom으로 좁히고 focus로 얼굴에 맞춘다.
function squareCrop({ zoom = 1, focusX = 0.5, focusY = 0.5 }) {
  const side = `min(iw,ih)*${zoom}`;
  return `crop='${side}':'${side}':'(iw-${side})*${focusX}':'(ih-${side})*${focusY}'`;
}

// 좌표를 식이 아니라 실제 숫자로 낸다 — 자막과 겹치는지 판정하려면 값이 필요하다.
function alignPosition(align, { width, height, size, marginX, marginY }) {
  const [vertical, horizontal] = String(align ?? 'middle-right').split('-');
  const x =
    horizontal === 'left'
      ? marginX
      : horizontal === 'center'
        ? Math.round((width - size) / 2)
        : width - size - marginX;
  const y =
    vertical === 'top'
      ? marginY
      : vertical === 'middle'
        ? Math.round((height - size) / 2)
        : height - size - marginY;
  return { x, y };
}

/**
 * 인물 트랙(투명 배경 mov)을 만든다. 쓸 소재가 하나도 없으면 null.
 * @param segments [{ id, duration }] — 변형이 고른 씬만
 * @param tail 엔드카드 등 인물이 나오지 않는 꼬리 길이(초)
 */
export async function buildPresenterTrack({ segments, tail, presenter, variant, fps, dirs, id }) {
  // 기본값을 영상 id 로 갈라 둔다. presenter/ 를 통째로 쓰면 두 영상에 같은 씬 id(intro 등)가
  // 있을 때 **뒤 영상이 앞 영상의 촬영분을 말없이 집어 간다** — 합성은 그대로 성공하므로
  // 재생해 보기 전에는 모른다. out/ 과 달리 여기는 자동으로 안 갈리던 유일한 경로였다.
  const dir = path.resolve(AD_DIR, presenter.dir ?? path.join('presenter', dirs.id));
  const only = presenter.scenes ? new Set(presenter.scenes) : null;

  // 프레이밍은 씬마다 다르다 — 테이크·소재가 바뀌면 얼굴 위치가 달라지므로 씬별로 덮어쓴다.
  const plan = segments.map((s) => ({
    duration: s.duration,
    media: only && !only.has(s.id) ? null : findPresenterMedia(dir, s.id),
    framing: { ...presenter, ...(s.presenter ?? {}) },
  }));
  if (tail > 0) plan.push({ duration: tail, media: null });
  if (!plan.some((p) => p.media)) return null;

  const size = Math.round(
    Math.min(variant.width, variant.height) * (variant.presenterSize ?? presenter.size ?? 0.22)
  );
  const maskFile = await makeCircleMask(size, path.join(ensureDir(dirs.work), `mask-${size}.png`));

  const inputs = [];
  const chains = [];
  let index = 0;
  let masked = 0; // 원형 마스크를 씌울 구간 수 — 마스크 스트림을 그만큼 split 해야 한다

  for (const [i, step] of plan.entries()) {
    const d = step.duration.toFixed(3);
    const crop = squareCrop({
      zoom: variant.presenterZoom ?? step.framing?.zoom ?? 1,
      focusX: step.framing?.focusX ?? 0.5,
      focusY: step.framing?.focusY ?? 0.5,
    });
    if (!step.media) {
      // 인물이 없는 구간 — 완전히 투명하게 비워 둔다.
      // (마스크를 트랙 전체에 한 번만 걸면 alphamerge가 이 투명도를 덮어써서 검은 원이 남는다.)
      inputs.push(...['-f', 'lavfi', '-t', d, '-i', `color=c=black:s=${size}x${size}:r=${fps}`]);
      chains.push(`[${index}:v]format=rgba,colorchannelmixer=aa=0,setsar=1[p${i}]`);
    } else if (step.media.isImage) {
      inputs.push(...['-loop', '1', '-t', d, '-i', step.media.file]);
      chains.push(
        `[${index}:v]${crop},scale=${size * 3}:${size * 3},` +
          `zoompan=z='min(zoom+0.0004,1.1)':d=${Math.max(1, Math.round(step.duration * fps))}:` +
          `s=${size}x${size}:fps=${fps},format=rgba,setsar=1[c${i}]`,
        `[c${i}][m${masked}]alphamerge=shortest=1[p${i}]`
      );
      masked += 1;
    } else {
      inputs.push('-i', step.media.file);
      chains.push(
        `[${index}:v]fps=${fps},${crop},scale=${size}:${size},` +
          `tpad=stop_mode=clone:stop_duration=30,` +
          `trim=0:${d},setpts=PTS-STARTPTS,format=rgba,setsar=1[c${i}]`,
        `[c${i}][m${masked}]alphamerge=shortest=1[p${i}]`
      );
      masked += 1;
    }
    index += 1;
  }

  inputs.push('-loop', '1', '-i', maskFile);
  const maskIndex = index;
  const total = plan.reduce((sum, p) => sum + p.duration, 0);

  const splits = Array.from({ length: masked }, (_, i) => `[m${i}]`).join('');
  const filter = [
    `[${maskIndex}:v]format=gray,split=${masked}${splits}`,
    ...chains,
    `${plan.map((_, i) => `[p${i}]`).join('')}concat=n=${plan.length}:v=1:a=0[out]`,
  ].join(';');

  const file = path.join(ensureDir(dirs.work), `${id}.presenter.mov`);
  await run('ffmpeg', [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...inputs,
    '-filter_complex',
    filter,
    ...['-map', '[out]', '-c:v', 'qtrle', '-t', total.toFixed(3)],
    file,
  ]);

  const marginX = Math.round(variant.width * (presenter.margin ?? 0.04));
  const marginY = Math.round(variant.height * (presenter.margin ?? 0.04));
  // 좌표를 직접 준 경우가 우선 — 쇼츠처럼 유튜브 UI를 피해 "안전 영역 안의 우하단"에
  // 놓아야 할 때는 정렬 키워드로 표현할 수 없다.
  const px = variant.presenterX ?? presenter.x;
  const py = variant.presenterY ?? presenter.y;
  const position =
    px !== undefined && py !== undefined
      ? { x: Number(px), y: Number(py) }
      : alignPosition(variant.presenterAlign ?? presenter.align, {
          width: variant.width,
          height: variant.height,
          size,
          marginX,
          marginY,
        });

  return { file, ...position, size };
}
