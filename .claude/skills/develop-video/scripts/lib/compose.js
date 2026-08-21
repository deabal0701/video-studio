// ffmpeg 합성 — 통짜 녹화본을 씬 단위로 잘라 이어 붙이고, 내레이션·BGM·문구를 얹는다.
//
// 변형(variant)마다 씬을 골라 쓸 수 있으므로 한 번 촬영으로 30초/15초/숏츠 버전이 모두 나온다.
// 오디오는 씬 길이에 맞춰 무음을 덧댄(apad) 뒤 이어 붙이므로 영상과 프레임 단위로 맞는다.
//
// 화면에 얹는 글자는 5종이고 전부 하나의 ASS 파일에 스타일만 달리해 들어간다.
//   Sub   자막(CC)            하단 중앙 — 기본은 항상 굽는다. subtitles:false 로만 끈다(.srt 는 그대로 나감)
//   Cap   상단 헤드라인        상단 중앙 — 소리 없이 보는 시청자용
//   Badge 강조 뱃지            헤드라인 바로 아래
//   Mark  로고 워터마크        기본 오른쪽 위 — 판때기 없이, 첫 프레임부터 끝까지 계속
//   End*  엔드카드 문구         마지막에 붙는 브랜드 화면
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, defaultSubtitleFont, ensureDir, mediaDuration, run } from './util.js';
import { assColour, timedCues, writeAss, writeSrt } from './overlay.js';
import { buildPresenterTrack } from './presenter.js';
import { motionClipsFor, renderMotionClip } from './motion.js';
import { renderMediaClip } from './media.js';

// 모션 템플릿은 대본 폴더(전용) → 공용 motion/ 순으로 찾는다. 한 영상에서만 쓰는 전용
// 템플릿(한강 단면도 등)을 projects/<id>/ 에 대본과 같이 두기 위한 것. projectDir 는
// build.js 가 대본 파일 위치로 채워 준다 — 전용 템플릿은 공용 _base.css·_params.js 를
// `../../motion/` 상대 경로로 참조해야 한다(프레임 굽기가 file:// 로 열기 때문).
function resolveMotionFile(motion, name) {
  const local = motion.projectDir && path.join(motion.projectDir, name);
  if (local && fs.existsSync(local)) return local;
  return path.join(motion.dir ?? 'motion', name);
}

// 씬 오디오를 각자 목표 길이만큼 무음으로 늘린 뒤 하나로 이어 붙인다.
async function buildNarration(segments, file) {
  const inputs = segments.flatMap((s) => ['-i', s.audioFile]);
  const chains = segments.map(
    (s, i) => `[${i}:a]aresample=48000,apad,atrim=0:${s.duration.toFixed(3)},asetpts=N/SR/TB[a${i}]`
  );
  const filter = [
    ...chains,
    `${segments.map((_, i) => `[a${i}]`).join('')}concat=n=${segments.length}:v=0:a=1[out]`,
  ].join(';');

  await run('ffmpeg', [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...inputs,
    '-filter_complex',
    filter,
    ...['-map', '[out]', '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2'],
    file,
  ]);
  return file;
}

async function makeSilence(seconds, file) {
  await run('ffmpeg', [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'],
    ...['-t', seconds.toFixed(3), '-c:a', 'pcm_s16le'],
    file,
  ]);
  return file;
}

// 문구 종류별 스타일. 크기는 전부 '짧은 변' 기준 — 세로 영상에서 높이에 비례시키면 폭을 넘어간다.
// (export 는 검증용 — 스틸 프레임에 자막·워터마크만 얹어 눈으로 보려면 이 함수가 필요하다.)
export function buildStyles(width, height, config, variant, presenterTrack) {
  const base = Math.min(width, height);
  const font = String(config.subtitleFont ?? defaultSubtitleFont()).replace(/[,\n]/g, '');
  const marginH = Math.round(width * 0.06);

  const subSizeForBand = Math.round(base * (variant.subtitleScale ?? config.subtitleScale ?? 0.05));
  const subMarginV = Math.round(height * (variant.subtitleMargin ?? config.subtitleMargin ?? 0.07));
  const subtitleBoxless = (variant.subtitleBox ?? config.subtitleBox) === false;

  // 인물이 자막대와 세로로 겹치면 자막이 그 위에 그려진다(ass가 overlay 뒤에 온다).
  // 그럴 때만 인물 쪽 여백을 넓혀 자막을 반대쪽으로 밀어낸다. 정렬 키워드가 아니라 실제
  // 좌표로 판정해야 한다 — 좌표를 직접 준 경우(쇼츠)는 우하단이어도 자막 위쪽일 수 있다.
  const bandTop = height - subMarginV - Math.round(subSizeForBand * 3.4);
  const overlapsBand = presenterTrack && presenterTrack.y + presenterTrack.size > bandTop;
  const onRight = presenterTrack && presenterTrack.x + presenterTrack.size / 2 > width / 2;
  const clearance = presenterTrack ? presenterTrack.x + presenterTrack.size : 0;
  const subMarginL = overlapsBand && !onRight ? clearance + marginH : marginH;
  const subMarginR = overlapsBand && onRight ? width - presenterTrack.x + marginH : marginH;
  const fit = (size, left, right) => Math.floor((width - left - right) / (size * 0.98));
  const units = (size) => fit(size, marginH, marginH);

  const subSize = Math.round(base * (variant.subtitleScale ?? config.subtitleScale ?? 0.05));
  const capSize = Math.round(base * (variant.captionScale ?? config.captionScale ?? 0.072));
  const badgeSize = Math.round(base * (variant.badgeScale ?? config.badgeScale ?? 0.036));
  const markSize = Math.round(base * (config.watermarkScale ?? 0.028));

  const capMarginV = Math.round(height * (variant.captionMargin ?? config.captionMargin ?? 0.05));
  const captionPlain = (variant.captionStyle ?? config.captionStyle) === 'plain';
  const endTop = Math.round(height * (config.endCardTop ?? 0.4));
  const endTitleSize = Math.round(base * 0.1);
  const endSubSize = Math.round(base * 0.05);
  const endUrlSize = Math.round(base * 0.035);

  return {
    // subtitleBox: false 로 글자 뒤 판을 없앤다. 판이 사라지면 배경이 그대로 비치므로
    // 테두리를 두 배로 키우고 그림자를 넣어 밝은 화면에서도 흰 글자가 읽히게 한다.
    Sub: {
      font,
      size: subSize,
      alignment: 2,
      marginL: subMarginL,
      marginR: subMarginR,
      marginV: Math.round(height * (variant.subtitleMargin ?? config.subtitleMargin ?? 0.07)),
      primary: config.subtitleColour ? assColour(config.subtitleColour) : undefined,
      // 4 = 문단 전체에 판 하나(libass 확장). 3(줄마다 판)은 한글 자막이 2줄을 넘으면
      // 반투명 판끼리 겹쳐 이중으로 어두운 띠가 생기고 윗줄 글자를 침범한다 — ai-lecture
      // 3줄 자막에서 실제로 걸렸다.
      borderStyle: subtitleBoxless ? 1 : 4,
      box: config.subtitleBoxColour ?? assColour(config.background ?? '#0B1020', 0x8c),
      outlineColour: assColour(config.subtitleOutlineColour ?? '#000000'),
      // 판 없는 자막은 테두리를 두르지 않는다 — 0.016(9:16에서 17px)은 글자가 검정
      // 덩어리로 뭉쳤고, 0.006 으로 줄여도 윤곽선이 지저분하다. 대신 그림자만 남긴다.
      // 그림자는 글자를 감싸지 않고 아래로만 떨어져 흰 글자가 밝은 하늘에서도 떠 보인다.
      // 완전히 지우려면 subtitleOutline: 0 · subtitleShadow: 0 을 준다.
      outline: Math.round(base * (variant.subtitleOutline ?? config.subtitleOutline ?? (subtitleBoxless ? 0 : 0.008))),
      shadow: Math.round(base * (variant.subtitleShadow ?? config.subtitleShadow ?? (subtitleBoxless ? 0.004 : 0))),
      maxUnits: fit(subSize, subMarginL, subMarginR),
      maxLines: 3, // 넘치는 분량은 잘리지 않는다 — timedCues가 여러 장으로 나눈다
    },
    // 캡션은 두 가지 결. box는 어두운 여백 띠(쇼츠) 위에서, plain은 밝은 앱 화면 위에서 낫다.
    // 흰 앱 화면에 반투명 회색 판을 얹으면 판때기처럼 보인다.
    Cap: {
      font,
      size: capSize,
      alignment: 8,
      marginH,
      marginV: capMarginV,
      ...(captionPlain
        ? {
            primary: assColour(config.captionColour ?? '#0B1020'),
            box: assColour('#FFFFFF', 0x1e),
            borderStyle: 1,
            outline: Math.round(base * 0.005),
            shadow: Math.round(base * 0.003),
          }
        : {
            box: assColour(config.background ?? '#0B1020', 0x59),
            outline: Math.round(base * 0.01),
          }),
      maxUnits: units(capSize),
      maxLines: 2,
    },
    Badge: {
      font,
      size: badgeSize,
      alignment: 8,
      marginH,
      // 헤드라인 바로 아래 — 어느 비율에서도 유튜브 UI와 겹치지 않는 자리다.
      marginV: capMarginV + Math.round(capSize * 1.75),
      box: assColour(config.brand ?? '#3E63DD', 0x14),
      outline: Math.round(base * 0.009),
      maxUnits: units(badgeSize),
      maxLines: 1,
    },
    Mark: {
      font,
      size: markSize,
      // 기본 자리는 오른쪽 위. 자막대(하단)·헤드라인(상단 중앙)과 겹치지 않고, 앱 화면에서도
      // 보통 이 구석이 가장 비어 있다.
      alignment: variant.watermarkAlign ?? config.watermarkAlign ?? 9,
      marginH: Math.round(width * (variant.watermarkMarginH ?? config.watermarkMarginH ?? 0.035)),
      // 세로 변형은 유튜브 UI가 상단 약 90px을 덮으므로 watermarkMargin으로 더 내려 준다.
      marginV: Math.round(height * (variant.watermarkMargin ?? config.watermarkMargin ?? 0.03)),
      // 워터마크는 흰 앱 화면 위에도, 어두운 여백 띠 위에도 얹힌다. 예전처럼 반투명 판(BorderStyle 3)을
      // 깔면 밝은 화면에서 회색 판때기가 그대로 드러난다. 판 없이 글자 테두리와 그림자만으로
      // 읽히게 해서, 어두운 배경에서는 글자만 떠 있는 것처럼 보이게 한다.
      // 테두리는 얇게(1px 안팎) — 굵으면 글자를 갉아먹어 어두운 배경에서 지저분해진다.
      // 밝은 배경에서의 가독성은 테두리보다 그림자가 벌어 준다.
      primary: assColour(config.watermarkColour ?? '#FFFFFF', 0x1a),
      box: assColour(config.watermarkEdge ?? config.background ?? '#0B1020'), // 판이 아니라 글자 테두리 색
      borderStyle: 1,
      // 그림자(BackColour)는 libass 가 검정 고정이라, 밝은 앱 화면에서는 글자 아래로
      // 검은 얼룩이 깔린다. 그림자를 0 으로 끄고 테두리로만 읽히게 하려면 테두리를
      // 두껍게 줄 수 있어야 하므로 watermarkOutline 으로 연다(기본값은 종전과 같다).
      outline: Math.max(1, Math.round(base * (config.watermarkOutline ?? 0.001))),
      // 그림자 0.002(9:16에서 2px)는 밝은 B롤 위에서 워터마크를 못 살린다 — 금색 파티클
      // 화면에서 거의 사라졌다. 0.004 로 키우면 어두운 배경에서 지저분해지지 않으면서
      // 밝은 배경에서도 글자 윤곽이 남는다.
      shadow: Math.max(2, Math.round(base * (config.watermarkShadow ?? 0.004))),
      bold: false,
      maxUnits: units(markSize),
      maxLines: 1,
    },
    EndTitle: {
      font,
      size: endTitleSize,
      alignment: 8,
      marginH,
      marginV: endTop,
      borderStyle: 1,
      outline: 0,
      maxUnits: units(endTitleSize),
      maxLines: 1,
    },
    EndSub: {
      font,
      size: endSubSize,
      alignment: 8,
      marginH,
      marginV: endTop + Math.round(endTitleSize * 1.5),
      borderStyle: 1,
      outline: 0,
      bold: false,
      maxUnits: units(endSubSize),
      maxLines: 2,
    },
    EndUrl: {
      font,
      size: endUrlSize,
      alignment: 8,
      marginH,
      marginV: endTop + Math.round(endTitleSize * 1.5) + Math.round(endSubSize * 2.4),
      primary: assColour(config.brandText ?? '#93A4F5'),
      borderStyle: 1,
      outline: 0,
      bold: false,
      maxUnits: units(endUrlSize),
      maxLines: 1,
    },
  };
}

/**
 * 하나의 변형을 완성 mp4로 만든다.
 * @returns {{file:string, duration:number}}
 */
export async function composeVariant({ variant, take, scenes, endCard, config, dirs }) {
  const byId = new Map(scenes.map((s) => [s.id, s]));
  const timelineById = new Map(take.scenes.map((s) => [s.id, s]));
  const ids = variant.scenes ?? scenes.map((s) => s.id);
  const offset = config.syncOffset ?? 0;

  const segments = ids.map((id) => {
    const scene = byId.get(id);
    const slot = timelineById.get(id);
    if (!scene || !slot) throw new Error(`변형 ${variant.id}: 씬 '${id}'를 찾지 못했습니다.`);
    return {
      id,
      audioFile: scene.audioFile,
      narration: scene.narration,
      caption: scene.caption,
      badge: scene.badge,
      presenter: scene.presenter,
      duration: slot.end - slot.start,
      videoStart: take.leadIn + slot.start + offset,
      videoEnd: take.leadIn + slot.end + offset,
    };
  });

  const width = variant.width;
  const height = variant.height;
  const fps = config.fps ?? 30;
  const bg = variant.background ?? config.background ?? '#0B1020';
  const useEndCard = Boolean(endCard) && variant.endCard !== false;
  const endDuration = useEndCard ? (endCard.duration ?? 3) : 0;

  // ── 구간 조립 ──
  // 화면 녹화 씬, 모션그래픽 구간, 엔드카드를 하나의 순서로 늘어놓는다. 이후 영상·오디오·문구가
  // 전부 이 목록을 기준으로 만들어지므로 중간에 무엇을 끼워 넣어도 타이밍이 어긋나지 않는다.
  // 화면 녹화가 없는 영상(모션·사진 전용)은 모션을 **변형 크기로 직접** 렌더한다.
  // 가로로 만든 카드를 세로에 끼워 넣으면 위아래가 텅 비어 쇼츠로 못 쓴다.
  // 녹화본이 있으면 concat 하려면 크기가 같아야 하므로 촬영 크기를 따라간다.
  const nativeMotion = !take.videoFile;
  const motionWidth = nativeMotion ? width : take.width;
  const motionHeight = nativeMotion ? height : take.height;

  // 모션 템플릿(_params.js)이 질의 문자열에서 읽는 CSS 변수 이름에 맞춰 넘긴다.
  // 값이 없는 키는 아예 빼야 한다 — URLSearchParams 가 undefined 를 "undefined" 문자열로 넣는다.
  const brandParams = Object.fromEntries(
    Object.entries({
      brand: config.brand,
      brandSoft: config.brandText,
      bg: variant.background ?? config.background,
      fg: config.foreground,
      font: config.motionFont,
      fontUrl: config.motionFontUrl,
    }).filter(([, v]) => v)
  );

  const motionClips = motionClipsFor(config.motion, variant.id);
  const renderMotion = async (clip) => ({
    kind: 'motion',
    id: clip.id,
    duration: clip.duration,
    narration: clip.narration ?? '', // 모션 구간의 말도 자막으로 나간다(구간별 끄기 없음)
    // 헤드라인·뱃지도 씬과 똑같이 받는다 — 스톡 영상(B롤) 위에 글자를 얹을 때 쓴다.
    // 판이 없어 밝거나 무늬가 복잡한 소재에서는 읽히지 않으니, 그럴 때는 프레임을 뽑아
    // 카드 배경으로 까는 쪽을 쓴다(develop-lecture 의 오프닝이 그 방식이다).
    caption: clip.caption,
    badge: clip.badge,
    audioFile: clip.audioFile,
    // 소스 두 갈래 — video는 내려받은 스톡 클립(ffmpeg 정규화), file은 HTML 템플릿(프레임 굽기).
    // 어느 쪽이든 "그 구간 길이의 mp4"가 나오므로 뒤 단계는 차이를 모른다.
    clipFile: clip.video
      ? await renderMediaClip({
          file: clip.video,
          start: clip.videoStart ?? 0,
          shade: clip.shade ?? 0,
          duration: clip.duration,
          width: motionWidth,
          height: motionHeight,
          fps,
          dirs,
          id: clip.id,
          force: config.motionForce,
        })
      : await renderMotionClip({
          file: resolveMotionFile(config.motion, clip.file),
          duration: clip.duration,
          width: motionWidth,
          height: motionHeight,
          fps,
          dirs,
          id: clip.id,
          // 브랜드 색을 모션 카드에도 넘긴다 — 이게 없으면 render.brand 를 아무리 바꿔도
          // 자막·뱃지 색만 바뀌고 카드는 템플릿 기본색(파랑) 그대로 나온다.
          // 와이프는 클립 끝에 맞춰 떨어져야 한다. 내레이션 길이에 따라 구간이 늘어나면 템플릿의
          // 고정 지연으로는 와이프가 먼저 끝나 버려 남은 시간이 흰 화면으로 남는다.
          params: {
            ...brandParams,
            wipeAt: Math.max(0, clip.duration - 0.45).toFixed(2),
            ...clip.params, // 클립이 직접 지정한 값이 항상 이긴다
            // 클립 최상위의 `wipe` 도 params 의 것과 똑같이 먹힌다. 템플릿에 닿는 것은 params
            // 뿐이라 예전에는 `{"id":"ch1","wipe":"off"}` 가 **조용히 무시**됐다 — 대본은
            // 껐다고 믿는데 흰 면이 그대로 떨어져 카드가 통째로 지워진 프레임이 남았다
            // (cloud-lecture 에서 챕터 카드 6곳 전부가 이 경우였다).
            ...(clip.wipe !== undefined && (clip.params ?? {}).wipe === undefined
              ? { wipe: clip.wipe }
              : {}),
          },
          force: config.motionForce,
        }),
  });

  const pieces = [];
  for (const seg of segments) {
    for (const clip of motionClips.filter((c) => c.before === seg.id)) {
      pieces.push(await renderMotion(clip));
    }
    pieces.push({ kind: 'scene', ...seg });
  }
  for (const clip of motionClips.filter((c) => c.before === 'end')) {
    pieces.push(await renderMotion(clip));
  }
  if (useEndCard) pieces.push({ kind: 'endcard', id: 'endcard', duration: endDuration });

  // 인물 PiP — 직접 촬영한 클립을 타임라인에 맞춘 투명 배경 트랙으로 먼저 뽑아 둔다.
  // 자막 여백을 인물 자리만큼 비워야 해서 문구 스타일보다 먼저 계산한다.
  const presenterTrack =
    config.presenter && config.presenter.enabled !== false && variant.presenter !== false
      ? await buildPresenterTrack({
          // 인물은 실제 화면 씬에만 얹는다 — 모션 구간과 엔드카드는 비워 둔다.
          segments: pieces.map((p) => ({
            id: p.kind === 'scene' ? p.id : null,
            duration: p.duration,
            presenter: p.presenter,
          })),
          tail: 0,
          presenter: config.presenter,
          variant,
          fps,
          dirs,
          id: variant.id,
        })
      : null;

  // ── 문구 이벤트 (변형별로 씬이 빠질 수 있으므로 누적 시간을 다시 계산한다) ──
  const styles = buildStyles(width, height, config, variant, presenterTrack);
  const cues = [];
  const events = [];
  let cursor = 0;
  let endCardStart = 0;
  for (const s of pieces) {
    const start = cursor;
    const end = cursor + s.duration;
    if (s.kind === 'endcard') endCardStart = start;
    if (s.narration) {
      // 자막은 말이 있는 곳이면 어디서나 **항상** 굽는다 — 씬이든 모션 구간이든, 변형이 무엇이든.
      // 끄는 스위치를 두지 않는 이유: 소리를 켜지 않고 보는 시청자가 다수이고, 자막이 있다 없다
      // 하면 그 구간만 정보가 사라진다. 사이드카 .srt는 같은 내용으로 함께 나간다.
      const parts = timedCues(
        s.narration,
        start + 0.08,
        end - 0.05,
        styles.Sub.maxUnits,
        styles.Sub.maxLines
      );
      // subtitles: false 는 **화면에 굽는 것만** 끈다. cues 는 그대로 쌓여 .srt 사이드카로 나가므로
      // 유튜브에 올릴 때 자막을 따로 붙일 수 있다. 기본값은 켬 — 끄는 것은 명시적 선택이다.
      const burnSubs = (variant.subtitles ?? config.subtitles) !== false;
      for (const part of parts) {
        cues.push(part);
        if (burnSubs) events.push({ style: 'Sub', ...part });
      }
    }
    if (s.caption && variant.captions !== false) {
      events.push({ style: 'Cap', start: start + 0.1, end: end - 0.05, text: s.caption });
    }
    if (s.badge) {
      const at = start + (s.badge.at ?? 0.6);
      events.push({
        style: 'Badge',
        start: at,
        end: Math.min(end - 0.05, at + (s.badge.duration ?? s.duration)),
        text: s.badge.text ?? s.badge,
      });
    }
    cursor = end;
  }
  const totalDuration = cursor;

  // 워터마크는 첫 프레임부터 마지막 프레임까지 끊기지 않는다 — 인트로·모션 구간·엔드카드에도
  // 그대로 남는다. 어디를 잘라 공유해도 누가 만든 영상인지 남아 있어야 한다.
  const markText = typeof config.watermark === 'string' ? config.watermark : config.watermark?.text;
  if (markText?.trim()) {
    events.push({ style: 'Mark', start: 0, end: totalDuration, text: markText.trim() });
  } else {
    console.warn(
      `  ! ${variant.id}: render.watermark.text 가 비어 있어 워터마크를 넣지 못했습니다.`
    );
  }
  if (useEndCard) {
    const from = endCardStart + 0.15;
    const to = endCardStart + endDuration;
    if (endCard.title) events.push({ style: 'EndTitle', start: from, end: to, text: endCard.title });
    if (endCard.subtitle)
      events.push({ style: 'EndSub', start: from + 0.15, end: to, text: endCard.subtitle });
    if (endCard.url) events.push({ style: 'EndUrl', start: from + 0.3, end: to, text: endCard.url });
  }

  // srt는 완성본과 짝이라 final/ 로, ass는 ffmpeg에 먹이는 중간물이라 work/ 로 간다.
  writeSrt(cues, path.join(ensureDir(dirs.final), `${variant.id}.srt`), styles.Sub.maxUnits); // 유튜브 업로드용
  const assName = `${variant.id}.ass`;
  writeAss(path.join(ensureDir(dirs.work), assName), { width, height, styles, events });

  // ── 오디오 ──
  // 말이 없는 구간(모션·엔드카드)은 그 길이만큼 무음을 만들어 끼운다. 그래야 뒤 구간의
  // 음성이 화면과 어긋나지 않는다.
  const narrationSegments = [];
  for (const p of pieces) {
    const audioFile =
      p.audioFile ??
      (p.kind === 'endcard' ? endCard.audioFile : null) ??
      (await makeSilence(p.duration, path.join(dirs.work, `${variant.id}.${p.id}.silence.wav`)));
    narrationSegments.push({ audioFile, duration: p.duration });
  }
  const narrationFile = path.join(dirs.work, `${variant.id}.narration.wav`);
  await buildNarration(narrationSegments, narrationFile);

  // ── 영상 ──
  // bgm 경로는 예나 지금이나 "영상 작업 폴더 기준"이다 — out/ 구조가 깊어져도 기준은 AD_DIR로 고정한다.
  const bgmFile = config.bgm ? path.resolve(AD_DIR, config.bgm) : null;
  const hasBgm = Boolean(bgmFile && fs.existsSync(bgmFile));

  // 화면 씬이 하나도 없으면(모션그래픽 전용 영상) 녹화본 자체가 없다. 입력 번호를 고정하지
  // 않고 실제로 넣은 순서대로 매긴다.
  const hasTake = Boolean(take.videoFile);
  const inputs = hasTake ? ['-i', take.videoFile, '-i', narrationFile] : ['-i', narrationFile];
  const takeIndex = 0;
  const narrationIndex = hasTake ? 1 : 0;
  let nextIndex = narrationIndex + 1;

  // 구간마다 영상 소스가 다르다 — 씬은 통짜 녹화본에서 잘라 쓰고, 모션은 별도 mp4,
  // 엔드카드는 단색 소스다(문구는 geometry 뒤에 ASS로 그리므로 여기선 배경만 만든다).
  const videoChains = [];
  const videoLabels = [];
  pieces.forEach((p, i) => {
    if (p.kind === 'scene') {
      videoChains.push(
        `[${takeIndex}:v]trim=start=${p.videoStart.toFixed(3)}:end=${p.videoEnd.toFixed(3)},setpts=PTS-STARTPTS[v${i}]`
      );
    } else if (p.kind === 'motion') {
      inputs.push('-i', p.clipFile);
      videoChains.push(
        `[${nextIndex}:v]trim=0:${p.duration.toFixed(3)},setpts=PTS-STARTPTS,format=yuv420p,setsar=1[v${i}]`
      );
      nextIndex += 1;
    } else {
      const endBg = (endCard.background ?? bg).replace('#', '0x');
      inputs.push(
        ...['-f', 'lavfi', '-t', p.duration.toFixed(3)],
        ...['-i', `color=c=${endBg}:s=${motionWidth}x${motionHeight}:r=${fps}`]
      );
      videoChains.push(`[${nextIndex}:v]format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v${i}]`);
      nextIndex += 1;
    }
    videoLabels.push(`[v${i}]`);
  });

  let presenterIndex = -1;
  if (presenterTrack) {
    inputs.push('-i', presenterTrack.file);
    presenterIndex = nextIndex;
    nextIndex += 1;
  }

  let bgmIndex = -1;
  if (hasBgm) {
    inputs.push('-stream_loop', '-1', '-i', bgmFile);
    bgmIndex = nextIndex;
    nextIndex += 1;
  }

  // padY: 세로 영상은 화면을 위로 올려 하단에 자막 자리를 비운다 — 쇼츠 UI(제목·채널명)가
  // 하단 약 330px을 덮으므로 가운데 정렬로 두면 자막이 가려진다.
  //
  // 변형 크기로 직접 렌더한 경우(nativeMotion)에는 자를 것도 밀어 올릴 것도 없다.
  // 그대로 두면 크기가 같은데 y 오프셋을 주게 되어 ffmpeg 이 "입력이 패딩 영역을 벗어난다"로 죽는다.
  const padY = nativeMotion || variant.padY === undefined ? '(oh-ih)/2' : String(variant.padY);
  const geometry = [
    !nativeMotion && variant.crop ? `crop=${variant.crop}` : null,
    `fps=${fps}`,
    `scale=${width}:${height}:force_original_aspect_ratio=decrease`,
    `pad=${width}:${height}:(ow-iw)/2:${padY}:color=${bg}`,
    'setsar=1',
  ]
    .filter(Boolean)
    .join(',');

  // BGM은 내레이션이 나올 때 자동으로 눌러 준다(사이드체인 더킹). 일정 볼륨으로 깔면 말과
  // 배경음이 같은 대역에서 싸워 대사가 묻힌다. 더킹을 끄려면 bgmDucking: false.
  const narrationVolume = config.narrationGain ?? 1.0;
  const audioChain = hasBgm
    ? [
        `[${narrationIndex}:a]volume=${narrationVolume},asplit=2[na][nakey]`,
        `[${bgmIndex}:a]volume=${config.bgmGain ?? 0.18}[bg]`,
        config.bgmDucking === false
          ? `[nakey]anullsink;[bg]anull[bgmix]`
          : `[bg][nakey]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=380[bgmix]`,
        `[na][bgmix]amix=inputs=2:duration=first:dropout_transition=0[am]`,
        `[am]loudnorm=I=-14:TP=-1.5:LRA=11[aout]`,
      ].join(';')
    : `[${narrationIndex}:a]volume=${narrationVolume},loudnorm=I=-14:TP=-1.5:LRA=11[aout]`;

  // 자막·헤드라인은 인물 위에 그려야 한다 — ass를 overlay 뒤에 둔다.
  const paintChains = presenterTrack
    ? [
        `[vc]${geometry}[vgeo]`,
        `[${presenterIndex}:v]setpts=PTS-STARTPTS[pres]`,
        `[vgeo][pres]overlay=x=${presenterTrack.x}:y=${presenterTrack.y}:eof_action=pass[vpip]`,
        `[vpip]ass=${assName}[vout]`,
      ]
    : [`[vc]${geometry},ass=${assName}[vout]`];

  const filter = [
    ...videoChains,
    `${videoLabels.join('')}concat=n=${videoLabels.length}:v=1:a=0[vc]`,
    ...paintChains,
    audioChain,
  ].join(';');

  const outFile = path.join(ensureDir(dirs.final), `${variant.id}.mp4`);
  // 자막 필터에 윈도 드라이브 경로(D:\)를 넣으면 필터그래프 파싱이 깨진다 — ass가 있는 work/에서
  // 실행하고, 출력만 final/로 내보낸다. 출력 인자는 필터그래프가 아니라서 상대 경로여도 안전하다.
  const outArg = path.relative(dirs.work, outFile).split(path.sep).join('/');
  await run(
    'ffmpeg',
    [
      ...['-hide_banner', '-loglevel', 'error', '-y'],
      ...inputs,
      '-filter_complex',
      filter,
      ...['-map', '[vout]', '-map', '[aout]'],
      ...['-c:v', 'libx264', '-preset', config.preset ?? 'medium', '-crf', String(config.crf ?? 19)],
      ...['-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', String(fps)],
      ...['-c:a', 'aac', '-b:a', '192k', '-ar', '48000'],
      ...['-movflags', '+faststart', '-shortest'],
      outArg,
    ],
    { cwd: ensureDir(dirs.work) }
  );

  return { file: outFile, duration: await mediaDuration(outFile) };
}
