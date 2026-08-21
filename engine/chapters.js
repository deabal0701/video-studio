// 유튜브 챕터 타임스탬프 생성 — 설명란에 그대로 붙여 넣는 "MM:SS 제목" 목록을 찍는다.
//
// 사용: node .claude/skills/develop-lecture/scripts/chapters.js --project <영상 id> [--video-root tools/video]
//
// 대본(projects/<id>/scenes.json)의 클립 순서와 음성 캐시(out/<id>/audio/manifest.json)의
// 실측 길이로 각 클립의 시작 시각을 누적한다 — build.js 와 같은 규칙
// (구간 길이 = max(선언 duration, 음성 + 0.5초), 내레이션 없는 클립은 선언값 그대로).
// 챕터로 잡는 것: chapter.html 카드와 course-intro 타이틀. 첫 챕터가 0초가 아니면
// 유튜브 규격(첫 챕터는 00:00)에 맞춰 "00:00 오프닝"을 앞에 붙인다.
//
// 한계: 모션 전용 영상 기준이다. 화면 씬(scenes)이 있는 회차는 씬 길이가 녹화에서
// 정해지므로 out/<id>/raw/timeline.json 을 봐야 한다 — 그 경우 경고를 찍고 멈춘다.

import fs from 'node:fs';
import path from 'node:path';

const args = {};
for (let i = 2; i < process.argv.length; i += 1) {
  const a = process.argv[i];
  if (a.startsWith('--')) args[a.slice(2)] = process.argv[i + 1];
}
const project = args.project;
if (!project) {
  console.error('사용법: node chapters.js --project <영상 id> [--video-root tools/video]');
  process.exit(1);
}
const root = args['video-root'] ?? 'tools/video';

const scenesFile = path.join(root, 'projects', project, 'scenes.json');
const manifestFile = path.join(root, 'out', project, 'audio', 'manifest.json');
const config = JSON.parse(fs.readFileSync(scenesFile, 'utf8'));
if ((config.scenes ?? []).length) {
  console.error('화면 씬이 있는 대본이다 — 씬 길이는 녹화가 정하므로 out/<id>/raw/timeline.json 을 확인하라.');
  process.exit(1);
}
const manifest = fs.existsSync(manifestFile) ? JSON.parse(fs.readFileSync(manifestFile, 'utf8')) : {};

const stamp = (sec) => {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
};

const chapters = [];
let cursor = 0;
let missing = 0;
for (const clip of config.render?.motion?.clips ?? []) {
  const isChapter =
    /chapter\.html$/.test(clip.file ?? '') || /course-intro\.html$/.test(clip.file ?? '');
  if (isChapter) {
    const title = clip.params?.title ?? clip.id;
    const prefix = clip.params?.num ? `${clip.params.num}. `.replace(/(강)\. $/, '$1 — ') : '';
    chapters.push([cursor, `${prefix}${title}`]);
  }
  const spoken = manifest[`motion-${clip.id}`]?.duration;
  if (clip.narration && spoken === undefined) missing += 1;
  const dur = clip.narration && spoken !== undefined
    ? Math.max(clip.duration ?? 0, spoken + 0.5)
    : (clip.duration ?? 0);
  cursor += dur;
}

if (missing) {
  console.error(`경고: 음성 캐시에 없는 내레이션 클립 ${missing}개 — 시각이 선언 duration 으로만 계산됐다. 빌드(--only tts) 후 다시 돌려라.`);
}
if (!chapters.length) {
  console.error('챕터 카드(chapter.html·course-intro.html)가 대본에 없다.');
  process.exit(1);
}
if (chapters[0][0] > 0.5) chapters.unshift([0, '오프닝']);
else chapters[0][0] = 0;

for (const [t, title] of chapters) console.log(`${stamp(t)} ${title}`);
console.log(`\n(총 ${stamp(cursor)} · 유튜브 설명란에 그대로 붙여 넣는다 — 첫 줄이 00:00 이어야 챕터로 인식된다)`);
