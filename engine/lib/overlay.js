// 화면에 얹는 글자 전부 — 자막(CC), 상단 헤드라인, 강조 뱃지, 로고 워터마크, 엔드카드.
//
// SRT는 유튜브 업로드용 사이드카로만 쓰고 굽기는 ASS로 한다. SRT를 subtitles 필터에 그대로
// 넣으면 libass가 기본 스크립트 해상도(384×288)로 렌더한 뒤 영상 크기로 확대해 글자가 3~4배로
// 튄다. PlayRes를 영상 크기와 맞춘 ASS를 직접 쓰면 FontSize가 곧 픽셀 값이 되고, 스타일을
// 여러 개 둘 수 있어 문구 종류별로 위치·크기를 나눌 수 있다.
import fs from 'node:fs';
import path from 'node:path';
import { ensureDir } from './util.js';

const DEFAULT_UNITS = 22;

// 한글은 글자폭이 글꼴 크기와 거의 같고 라틴 문자는 그 절반쯤이다. 줄바꿈을 글자 수가 아니라
// 이 '폭 단위'로 계산해야 16:9와 9:16에서 같은 규칙으로 안 넘친다.
const visualWidth = (text) =>
  [...text].reduce((sum, ch) => sum + (ch.codePointAt(0) < 0x1100 ? 0.55 : 1), 0);

export function wrap(text, maxUnits = DEFAULT_UNITS, maxLines = 3) {
  if (visualWidth(text) <= maxUnits) return [text];
  const lines = [];
  let line = '';
  for (const word of text.split(' ')) {
    if (line && visualWidth(`${line} ${word}`) > maxUnits) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);
  return lines.slice(0, maxLines); // 넘치면 광고 화면을 가린다
}

// 예산을 넘는 한 문장을 단어 단위로 다시 끊는다(문장 부호가 없는 긴 문장 대비).
function splitByWords(text, budget) {
  const parts = [];
  let cur = '';
  for (const word of text.split(' ')) {
    if (cur && visualWidth(`${cur} ${word}`) > budget) {
      parts.push(cur);
      cur = word;
    } else {
      cur = cur ? `${cur} ${word}` : word;
    }
  }
  if (cur) parts.push(cur);
  return parts;
}

/**
 * 화면 한 장(maxLines 줄)에 안 들어가는 자막을 여러 장으로 쪼갠다.
 * wrap()은 넘치는 줄을 **버리므로**, 쪼개지 않으면 긴 내레이션의 뒷문장이 화면에도 .srt에도
 * 영영 나오지 않는다. 자막을 항상 띄우기로 한 이상 잘라 버리는 경로는 없어야 한다.
 */
export function splitCue(text, maxUnits = DEFAULT_UNITS, maxLines = 3) {
  const budget = Math.max(1, maxUnits * maxLines);
  const source = String(text ?? '').trim();
  if (!source) return [];

  // 폭 합계(budget)만으로 판정하면 안 된다 — 줄바꿈마다 줄 끝에 빈 자리가 남으므로
  // 합계가 예산 안이어도 실제로 감으면 maxLines를 넘길 수 있다. 그때 wrap()이 넘친 줄을
  // 잘라 버려 문장 끝이 통째로 사라진다(실제로 "…다음 단계" 뒤 "과제입니다."가 날아갔다).
  // 그래서 판정은 항상 **실제 줄 수**로 한다.
  const fitsOneCard = (s) => {
    if (visualWidth(s) > budget) return false;
    const lines = [];
    let line = '';
    for (const word of s.split(' ')) {
      if (line && visualWidth(`${line} ${word}`) > maxUnits) {
        lines.push(line);
        line = word;
      } else {
        line = line ? `${line} ${word}` : word;
      }
    }
    if (line) lines.push(line);
    return lines.length <= maxLines;
  };

  if (fitsOneCard(source)) return [source];

  // 문장 경계에서 먼저 끊는다 — 말의 단위와 자막 전환이 맞아야 읽힌다.
  const chunks = [];
  let cur = '';
  for (const sentence of source.split(/(?<=[.!?…])\s+/).filter(Boolean)) {
    for (const part of fitsOneCard(sentence) ? [sentence] : splitByWords(sentence, budget)) {
      if (cur && !fitsOneCard(`${cur} ${part}`)) {
        chunks.push(cur);
        cur = part;
      } else {
        cur = cur ? `${cur} ${part}` : part;
      }
    }
  }
  if (cur) chunks.push(cur);

  // 마지막 안전망 — 그래도 한 장에 안 들어가는 덩어리는 단어 단위로 더 쪼갠다.
  // 여기까지 왔는데 넘치면 글자가 잘리므로, 보기 나쁜 편이 사라지는 것보다 낫다.
  return chunks.flatMap((c) => (fitsOneCard(c) ? [c] : splitByWords(c, Math.floor(budget * 0.8))));
}

/** 자막 한 덩어리를 화면에 들어가는 크기로 쪼개고, 말한 시간을 글자 수에 비례해 나눈다. */
/**
 * 자막 한 장이 화면에 머무는 최대 시간(초).
 * 폭만 보고 쪼개면 "세 줄에 들어가니까 한 장"이 되어, 내레이션이 긴 구간에서는 같은 글자가
 * 15초 넘게 붙박이로 떠 있는다. 읽기 리듬이 끊기고, 이미 읽은 문장을 계속 보게 된다.
 * (cloud-lecture 1차에서 27장 중 18장이 10초를 넘겼다.)
 */
const MAX_CUE_SECONDS = 6;

export function timedCues(text, start, end, maxUnits = DEFAULT_UNITS, maxLines = 3) {
  let chunks = splitCue(text, maxUnits, maxLines);

  // 폭으로 쪼갠 뒤에도 한 장이 너무 오래 머물면 더 잘게 나눈다. 필요한 장수를 시간으로 구하고,
  // 그 장수가 나올 때까지 splitCue 에 점점 좁은 폭을 준다 — 자르는 자리는 splitCue 가 정하므로
  // 문장·어절 경계는 그대로 지켜진다.
  const span = Math.max(0, end - start);
  if (chunks.length && span / chunks.length > MAX_CUE_SECONDS) {
    const want = Math.ceil(span / MAX_CUE_SECONDS);
    for (let units = maxUnits; units >= 10 && chunks.length < want; units -= 4) {
      const narrower = splitCue(text, units, maxLines);
      if (narrower.length > chunks.length) chunks = narrower;
    }
  }

  // 좁은 폭으로 다시 쪼개면 "조퇴는 따로" · "붙입니다." 같은 한 뼘짜리 조각이 남는다.
  // 화면에 0.5초 떴다 사라지면 읽히지도 않고 깜빡임으로만 보이므로, 짧은 것은 이웃에 붙인다.
  // (한 장에 안 들어가게 되는 합치기는 하지 않는다 — 그러면 다시 글자가 잘린다.)
  if (chunks.length > 1) {
    const minUnits = Math.max(6, maxUnits * 0.45);
    const fits = (s) => visualWidth(s) <= maxUnits * maxLines;
    const merged = [];
    for (const c of chunks) {
      const prev = merged[merged.length - 1];
      const tooShort = visualWidth(c) < minUnits;
      if (prev && tooShort && fits(`${prev} ${c}`)) merged[merged.length - 1] = `${prev} ${c}`;
      else merged.push(c);
    }
    // 첫 조각이 짧으면 뒤에 붙인다(앞에 붙일 것이 없으므로).
    if (merged.length > 1 && visualWidth(merged[0]) < minUnits && fits(`${merged[0]} ${merged[1]}`)) {
      merged.splice(0, 2, `${merged[0]} ${merged[1]}`);
    }
    chunks = merged;
  }

  if (chunks.length <= 1) return chunks.map((t) => ({ start, end, text: t }));
  const widths = chunks.map(visualWidth);
  const total = widths.reduce((a, b) => a + b, 0) || 1;
  // 자막 장이 바뀔 때 앞 장을 아주 살짝 먼저 거둔다. 끝시각과 다음 시작시각이 같으면
  // 플레이어에 따라 두 장이 한 프레임 겹쳐 보이거나 전환이 끊긴 것처럼 읽힌다.
  const GAP = 0.08;
  let cursor = start;
  return chunks.map((text_, i) => {
    const from = cursor;
    const last = i === chunks.length - 1;
    cursor = last ? end : from + (end - start) * (widths[i] / total);
    return { start: from, end: last ? end : Math.max(from + 0.1, cursor - GAP), text: text_ };
  });
}

const srtStamp = (seconds) => {
  const ms = Math.max(0, Math.round(seconds * 1000));
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor((ms % 3600000) / 60000))}:${pad(
    Math.floor((ms % 60000) / 1000)
  )},${pad(ms % 1000, 3)}`;
};

const assStamp = (seconds) => {
  const cs = Math.max(0, Math.round(seconds * 100));
  const pad = (n) => String(n).padStart(2, '0');
  return `${Math.floor(cs / 360000)}:${pad(Math.floor((cs % 360000) / 6000))}:${pad(
    Math.floor((cs % 6000) / 100)
  )}.${pad(cs % 100)}`;
};

/** 유튜브 업로드용 사이드카 자막 (CC 트랙) */
export function writeSrt(cues, file, maxUnits = DEFAULT_UNITS) {
  const body = cues
    .filter((c) => c.text?.trim())
    .map(
      (c, i) =>
        `${i + 1}\n${srtStamp(c.start)} --> ${srtStamp(c.end)}\n${wrap(c.text, maxUnits).join('\n')}\n`
    )
    .join('\n');
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, body, 'utf8');
  return file;
}

// ASS 색은 &HAABBGGRR — AA는 투명도(00 불투명, FF 완전투명)이고 RGB가 뒤집혀 들어간다.
export function assColour(hex, alpha = 0) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex));
  if (!m) return '&H00FFFFFF';
  const [r, g, b] = [0, 2, 4].map((i) => m[1].slice(i, i + 2));
  return `&H${alpha.toString(16).padStart(2, '0').toUpperCase()}${b}${g}${r}`.toUpperCase();
}

function styleLine(name, s) {
  // BorderStyle 4 = 문단 전체에 판 하나(libass 확장, 판 색은 BackColour에서 읽는다).
  // 3 = 줄마다 판 — 여러 줄이면 반투명 판이 겹쳐 이중으로 어두운 띠가 생기므로 쓰지 않는다.
  // 1 = 판 없이 글자에 테두리만. 판을 뺄 때는 OutlineColour 가 판 색이 아니라 테두리 색이
  // 되므로 검정으로 돌리고, 테두리를 두껍게(+그림자) 줘야 밝은 배경에서 글자가 안 뭉개진다.
  // 판 색은 OutlineColour(3용)·BackColour(4용) 양쪽에 넣어 어느 스타일이든 같게 나온다.
  const boxless = s.borderStyle === 1;
  const border = boxless ? (s.outlineColour ?? '&H00000000') : (s.box ?? '&H8C1A1005');
  const back = boxless ? '&H00000000' : (s.box ?? '&H8C1A1005');
  return (
    `Style: ${name},${s.font},${s.size},${s.primary ?? '&H00FFFFFF'},&H000000FF,` +
    `${border},${back},${s.bold === false ? 0 : -1},0,0,0,100,100,` +
    `${s.spacing ?? 0},0,${s.borderStyle ?? 3},${s.outline ?? 4},${s.shadow ?? 0},${s.alignment ?? 2},` +
    `${s.marginL ?? s.marginH ?? 60},${s.marginR ?? s.marginH ?? 60},${s.marginV ?? 60},1`
  );
}

/**
 * 여러 스타일을 가진 굽기용 ASS를 만든다.
 * @param styles {name: {font,size,alignment,marginH,marginV,primary,box,maxUnits,maxLines}}
 * @param events [{ style, start, end, text }]
 */
export function writeAss(file, { width, height, styles, events }) {
  const head = [
    '[Script Info]',
    'ScriptType: v4.00+',
    `PlayResX: ${width}`,
    `PlayResY: ${height}`,
    'WrapStyle: 2',
    'ScaledBorderAndShadow: yes',
    '',
    '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,' +
      ' Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline,' +
      ' Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    ...Object.entries(styles).map(([name, s]) => styleLine(name, s)),
    '',
    '[Events]',
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
  ];
  const lines = events
    .filter((e) => e.text?.trim() && e.end > e.start)
    .map((e) => {
      const s = styles[e.style] ?? {};
      const text = wrap(e.text, s.maxUnits ?? DEFAULT_UNITS, s.maxLines ?? 3)
        .join('\\N')
        .replace(/[{}]/g, '');
      return `Dialogue: 0,${assStamp(e.start)},${assStamp(e.end)},${e.style},,0,0,0,,${text}`;
    });
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, `${[...head, ...lines].join('\n')}\n`, 'utf8');
  return file;
}
