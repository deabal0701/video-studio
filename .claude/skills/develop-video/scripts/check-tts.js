// TTS 연결 점검 — 영상을 만들기 전에 "지금 이 환경에서 어느 제공자로 소리가 나오는가"를 확인한다.
// 대본 없이 짧은 한 문장을 실제로 합성해 보므로, 키·리전·네트워크·edge-tts 설치까지 한 번에 걸린다.
//
//   node tools/video/check-tts.js                   전체 점검 (edge · sapi · azure · eleven)
//   node tools/video/check-tts.js --provider azure   하나만
//   node tools/video/check-tts.js --lang en --gender male
//   node tools/video/check-tts.js --keep             생성된 mp3를 지우지 않는다 (목소리 들어볼 때)
//   node tools/video/check-tts.js --list-voices      ElevenLabs 보유 목소리와 voice_id 목록
//   node tools/video/check-tts.js --sample-voices 8  같은 문장을 목소리 8개로 만들어 비교(귀로 고른다)
//   node tools/video/check-tts.js --sample-voices 5 --sample-text "오늘은 로그인 화면을 만들어 봅니다."
//
// ElevenLabs 는 유료(글자수 과금)다. 전체 점검이 쓰는 양은 한 문장(10자 안팎)이고,
// 크레딧 잔량은 글자를 쓰지 않는 조회로 먼저 보여 준다.
//
// 키 값은 절대 찍지 않는다 — 길이와 앞 4글자만 보여 준다.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { displayPath, ensureDir, envFiles, loadEnv, mediaDuration, parseArgs, tryRun } from './lib/util.js';
import {
  ELEVEN_PRESETS,
  PROVIDER_LIST,
  elevenSubscription,
  elevenVoices,
  resolveVoice,
  resolveVoiceFor,
  synthDirect,
} from './lib/tts.js';

const args = parseArgs();
const lang = args.lang ?? 'ko';
const gender = args.gender ?? 'female';
const voice = resolveVoice({ lang, gender, ...(args.voice ? { voice: args.voice } : {}) });
const text = args.text ?? { ko: '연결 테스트입니다.', en: 'Connection test.', ja: '接続テストです。', zh: '连接测试。' }[lang] ?? '연결 테스트입니다.';

const mask = (v) => (v ? `${v.slice(0, 4)}… (${v.length}자)` : '(없음)');
const ok = (s) => `  OK   ${s}`;
const bad = (s) => `  실패 ${s}`;

// ── 1. .env ───────────────────────────────────────────────────────────────────
process.stdout.write('[1] .env\n');
const found = envFiles();
if (!found.length) process.stdout.write('  (없음 — 셸 환경변수만 씁니다)\n');
for (const f of found) process.stdout.write(`  · ${displayPath(f)}\n`);
const applied = loadEnv();
for (const { file, count } of applied) {
  process.stdout.write(`    → ${displayPath(file)} 에서 ${count}개 적용\n`);
}
process.stdout.write(`  AZURE_SPEECH_KEY    ${mask(process.env.AZURE_SPEECH_KEY)}\n`);
process.stdout.write(`  AZURE_SPEECH_REGION ${process.env.AZURE_SPEECH_REGION || '(없음)'}\n`);
process.stdout.write(`  ELEVENLABS_API_KEY  ${mask(process.env.ELEVENLABS_API_KEY)}\n`);

// ── 2. 외부 도구 ──────────────────────────────────────────────────────────────
process.stdout.write('\n[2] 외부 도구\n');
for (const [label, cmd, argv] of [
  ['ffmpeg', 'ffmpeg', ['-version']],
  ['ffprobe', 'ffprobe', ['-version']],
]) {
  const res = await tryRun(cmd, argv);
  process.stdout.write(res ? ok(`${label}  ${res.out.split('\n')[0].slice(0, 60)}`) + '\n' : bad(`${label} — PATH에 없습니다`) + '\n');
}

// ── 3. 제공자별 실제 합성 ─────────────────────────────────────────────────────
// 씬 파이프라인(synthesizeScenes)을 그대로 쓰지 않고 제공자를 직접 부른다 —
// 여기서는 폴백이 끼면 안 된다. 어느 제공자가 살아 있는지를 있는 그대로 봐야 한다.
const targets = args.provider ? [args.provider] : PROVIDER_LIST;
// 프로세스마다 다른 폴더를 쓴다 — 두 작업을 동시에 점검해도 샘플이 서로 덮어쓰지 않는다.
const dir = ensureDir(path.join(os.tmpdir(), `develop-video-check-${process.pid}`));

// ── ElevenLabs 는 유료라 먼저 잔량을 본다 (이 조회는 글자를 쓰지 않는다) ──────────────
// 크레딧 조회와 목소리 조회는 **API 키 권한이 다르다**(user_read vs voices_read).
// 그래서 둘을 따로 감싼다 — 크레딧을 못 본다고 목소리 목록까지 막히면 아무것도 못 고른다.
if (targets.includes('eleven') && process.env.ELEVENLABS_API_KEY) {
  process.stdout.write('\n[2.5] ElevenLabs\n');
  try {
    const sub = await elevenSubscription();
    const used = sub.character_count ?? 0;
    const limit = sub.character_limit ?? 0;
    process.stdout.write(
      `  크레딧 — 등급 ${sub.tier ?? '?'} · ${used.toLocaleString()}/${limit.toLocaleString()}자 사용` +
        ` (남은 ${(limit - used).toLocaleString()}자)\n`
    );
  } catch (err) {
    const detail = String(err.message);
    process.stdout.write(`  크레딧 조회 실패 — ${detail.split('\n')[0]}\n`);
    if (/missing_permissions|user_read/.test(detail)) {
      process.stdout.write(
        '    → API 키에 user_read 권한이 없습니다. 합성에는 지장이 없지만 잔량을 못 봅니다.\n' +
          '       elevenlabs.io → API Keys 에서 권한을 켜거나 키를 다시 발급하세요.\n'
      );
    }
  }
  try {
    // 목소리 고르기 — 같은 문장을 여러 목소리로 만들어 놓고 귀로 비교한다.
    // 대본을 쓰기 전에 이걸 한 번 돌려 목소리를 정하는 게 순서다.
    if (args['sample-voices']) {
      const want = Number.parseInt(args['sample-voices'], 10);
      const limit = Number.isFinite(want) ? want : 8;
      const voices = await elevenVoices();
      // 기준값 목록에 있는 이름을 앞으로 당긴다 — 한국어에 맞는 것부터 듣게 된다.
      const preferred = [...(ELEVEN_PRESETS.female ?? []), ...(ELEVEN_PRESETS.male ?? [])];
      const rank = (v) => {
        const i = preferred.findIndex((n) => String(v.name).toLowerCase().includes(n.toLowerCase()));
        return i < 0 ? 999 : i;
      };
      const picked = [...voices].sort((a, b) => rank(a) - rank(b)).slice(0, limit);
      const sampleDir = ensureDir(path.join(dir, 'voices'));
      const sampleText = args['sample-text'] ?? text;
      process.stdout.write(
        `  샘플 ${picked.length}개 생성 (각 ${sampleText.length}자 · 합계 약 ${picked.length * sampleText.length}자 과금)\n`
      );
      for (const v of picked) {
        const out = path.join(sampleDir, `${String(v.name).replace(/[^\w가-힣.-]+/g, '_')}.mp3`);
        try {
          await synthDirect('eleven', {
            text: sampleText,
            file: out,
            voice: v.voice_id,
            voiceConfig: { lang, gender },
            rate: '+0%',
            volume: '+0%',
            pitch: '+0Hz',
          });
          process.stdout.write(`    ✓ ${String(v.name).padEnd(30)} ${v.voice_id}\n`);
        } catch (err) {
          process.stdout.write(`    ✗ ${String(v.name).padEnd(30)} ${String(err.message).split('\n')[0]}\n`);
        }
      }
      process.stdout.write(`  들어보기: ffplay -autoexit -nodisp "${sampleDir}\\<이름>.mp3"\n`);
      process.stdout.write(`  폴더 열기: explorer "${sampleDir}"\n`);
      process.stdout.write(`  정한 뒤: .env 의 ELEVENLABS_VOICE_ID 또는 scenes.json 의 voice.voice 에 이름/ID를 넣는다\n`);
    }
    if (args['list-voices']) {
      const voices = await elevenVoices();
      process.stdout.write(`  보유 목소리 ${voices.length}개\n`);
      for (const v of voices.slice(0, 30)) {
        process.stdout.write(
          `    ${String(v.name).padEnd(18)} ${String(v.labels?.gender ?? '-').padEnd(8)}` +
            ` ${String(v.category ?? '').padEnd(9)} ${v.voice_id}\n`
        );
      }
      process.stdout.write(`  → 고정하려면 scenes.json 의 voice.voice 나 ELEVENLABS_VOICE_ID 에 id 를 넣는다\n`);
    }
  } catch (err) {
    process.stdout.write(`  목소리 조회 실패 — ${String(err.message).split('\n')[0]}\n`);
  }
}

process.stdout.write(`\n[3] 합성 (${lang}/${gender} · ${voice})\n    "${text}"\n`);
const results = [];
for (const name of targets) {
  const file = path.join(dir, `check-${name}.${name === 'sapi' ? 'wav' : 'mp3'}`);
  fs.rmSync(file, { force: true });
  const started = process.hrtime.bigint();
  try {
    const voiceConfig = { lang, gender, ...(args.voice ? { voice: args.voice } : {}) };
    await synthDirect(name, {
      text,
      file,
      // 목소리 이름 체계가 제공자마다 다르다 — sapi 는 윈도 설치 음성, eleven 은 계정별 voice_id.
      voice: resolveVoiceFor(name, voiceConfig),
      voiceConfig,
      rate: '+0%',
      volume: '+0%',
      pitch: '+0Hz',
    });
    const took = Number(process.hrtime.bigint() - started) / 1e9;
    const duration = await mediaDuration(file);
    const bytes = fs.statSync(file).size;
    process.stdout.write(ok(`${name.padEnd(5)} ${duration.toFixed(2)}s · ${(bytes / 1024).toFixed(0)}KB · ${took.toFixed(1)}s 걸림`) + '\n');
    results.push({ name, file, duration });
  } catch (err) {
    // 여러 줄짜리 안내(계정에 있는 목소리 목록 등)를 첫 줄만 잘라 버리면 원인을 못 찾는다.
    const [head, ...rest] = String(err.message).split('\n');
    process.stdout.write(bad(`${name.padEnd(5)} ${head}`) + '\n');
    for (const line of rest) process.stdout.write(`       ${line.trim()}\n`);
  }
}

// ── 4. 판정 ───────────────────────────────────────────────────────────────────
process.stdout.write('\n[4] 판정\n');
const live = new Set(results.map((r) => r.name));
if (live.has('azure')) {
  process.stdout.write('  azure 사용 가능 — --provider azure 로 쓸 수 있습니다.\n');
} else if (targets.includes('azure')) {
  process.stdout.write('  azure 사용 불가 — --provider azure 로 실행해도 edge로 자동 전환됩니다.\n');
}
if (live.has('eleven')) {
  process.stdout.write('  eleven 사용 가능 — --provider eleven (유료, 글자수 과금).\n');
} else if (targets.includes('eleven')) {
  process.stdout.write('  eleven 사용 불가 — --provider eleven 으로 실행해도 edge로 자동 전환됩니다.\n');
}
// 점검하지 않은 제공자를 "불가"로 말하지 않는다 — --provider 로 하나만 본 경우가 흔하다.
if (targets.includes('edge')) {
  process.stdout.write(
    live.has('edge')
      ? '  edge 사용 가능 — 기본 경로가 살아 있습니다(키 불필요).\n'
      : '  edge 사용 불가 — `pip install edge-tts` 또는 네트워크를 확인하세요.\n'
  );
} else {
  process.stdout.write('  (edge는 이번에 점검하지 않았습니다 — 인자 없이 실행하면 전체를 봅니다.)\n');
}
if (!live.size) {
  process.stdout.write(`  점검한 제공자(${targets.join(', ')}) 중 쓸 수 있는 것이 없습니다.\n`);
  process.exit(1);
}

if (args.keep) {
  process.stdout.write('\n생성된 파일 (ffplay로 들어 보세요)\n');
  for (const r of results) process.stdout.write(`  ffplay -autoexit -nodisp "${r.file}"\n`);
} else {
  for (const r of results) fs.rmSync(r.file, { force: true });
}
