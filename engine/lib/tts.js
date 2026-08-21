// 씬 내레이션 → 음성 파일. 제공자 4종을 같은 인터페이스로 감싼다.
//   edge  : Edge 읽어주기 엔드포인트 (키 불필요, Azure 뉴럴 음성과 동일 — 기본값)
//   sapi  : 윈도 내장 System.Speech (완전 오프라인, 네트워크 차단 환경 폴백)
//   azure : Azure Speech REST (정식 키 필요 — 운영·상용 납품용)
//   file  : 직접 녹음/촬영한 파일을 그대로 쓴다 (합성하지 않고 길이만 잰다)
//
// azure 는 키가 없거나 만료·쿼터 소진이면 자동으로 edge 로 내려간다 (아래 UNAVAILABLE_FALLBACK).
// 요금 때문에 키가 끊겨도 영상 제작이 멈추지 않는다 — 목소리 id 가 같아 결과물도 거의 같다.
//
// file 제공자가 이 파이프라인의 핵심 확장점이다. 씬마다 한 컷씩 찍은 영상을 넣으면
// 음성은 그 파일에서 나오고, 같은 파일이 인물 PiP 영상으로도 쓰인다 (compose.js의 presenter).
// 대본이 바뀌지 않은 씬은 manifest 해시로 건너뛴다 (반복 실행이 잦은 작업이라 캐시가 중요하다).
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { AD_DIR, ensureDir, mediaDuration, readJson, run, tryRun, writeJson } from './util.js';

// 녹음 파일로 받아들이는 확장자 — 영상 파일도 오디오 트랙만 뽑아 쓴다.
const VOICE_EXTS = ['wav', 'mp3', 'm4a', 'aac', 'flac', 'mp4', 'mov', 'mkv'];

export function findVoiceFile(dir, id) {
  for (const ext of VOICE_EXTS) {
    const file = path.join(dir, `${id}.${ext}`);
    if (fs.existsSync(file)) return file;
  }
  return null;
}

let pythonRunner = null;

// edge-tts는 PATH의 실행 파일일 수도, 파이썬 모듈일 수도 있다 — 처음 한 번만 탐색한다.
async function resolveEdgeRunner() {
  if (pythonRunner) return pythonRunner;
  const candidates = [
    ['edge-tts', []],
    ['py', ['-m', 'edge_tts']],
    ['python', ['-m', 'edge_tts']],
    ['python3', ['-m', 'edge_tts']],
  ];
  for (const [cmd, prefix] of candidates) {
    if (await tryRun(cmd, [...prefix, '--version'])) {
      pythonRunner = { cmd, prefix };
      return pythonRunner;
    }
  }
  throw new Error(
    'edge-tts를 찾지 못했습니다. `pip install edge-tts` 후 다시 실행하거나 --provider sapi 를 쓰세요.'
  );
}

async function synthEdge({ text, file, voice, rate, volume, pitch }) {
  const { cmd, prefix } = await resolveEdgeRunner();
  await run(cmd, [
    ...prefix,
    '--voice',
    voice,
    '--rate',
    rate,
    '--volume',
    volume,
    '--pitch',
    pitch,
    '--text',
    text,
    '--write-media',
    file,
  ]);
}

// PowerShell 인용 문제를 피하려고 대본을 파일로 넘긴다.
async function synthSapi({ text, file, voice, rate }) {
  const txt = `${file}.txt`;
  fs.writeFileSync(txt, text, 'utf8');
  const script = [
    'Add-Type -AssemblyName System.Speech',
    '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer',
    `$v = '${voice.replace(/'/g, "''")}'`,
    'if ($v) { try { $s.SelectVoice($v) } catch { } }',
    `$s.Rate = ${Math.round(Number.parseFloat(rate) / 10) || 0}`,
    `$s.SetOutputToWaveFile('${file.replace(/'/g, "''")}')`,
    `$s.Speak([IO.File]::ReadAllText('${txt.replace(/'/g, "''")}', [Text.Encoding]::UTF8))`,
    '$s.Dispose()',
  ].join('; ');
  await run('powershell', ['-NoProfile', '-NonInteractive', '-Command', script]);
  fs.rmSync(txt, { force: true });
}

// "이 제공자는 지금 통째로 못 쓴다"는 뜻의 에러 — 대본이나 씬 문제가 아니므로 폴백 대상이다.
function unavailable(message) {
  const err = new Error(message);
  err.unavailable = true;
  return err;
}

// 키 자체가 죽은 상태로 보는 응답 코드. 401 잘못된/만료된 키 · 402 결제 필요 ·
// 403 구독 정지·쿼터 소진 · 429 한도 초과. 그 밖(400 잘못된 SSML 등)은 대본 문제라 그대로 던진다.
const AZURE_DEAD_STATUS = new Set([401, 402, 403, 429]);

// 응답 코드로 이미 판정이 끝난 에러 — 다시 보내도 결과가 같으므로 재시도 대상이 아니다.
function fatal(message) {
  const err = new Error(message);
  err.azureFatal = true;
  return err;
}

// 한 번의 시도를 여기서 끊는다. 두지 않으면 undici 기본값(300초)까지 매달린다 —
// 실제로 헤더만 오고 본문이 멈춘 채 5분을 버티다 대본 전체가 무너진 적이 있다.
const AZURE_TIMEOUT_MS = 45_000;
const AZURE_ATTEMPTS = 3;

async function synthAzure({ text, file, voice, rate, pitch }) {
  const key = process.env.AZURE_SPEECH_KEY;
  const region = process.env.AZURE_SPEECH_REGION;
  if (!key || !region) {
    throw unavailable(
      'AZURE_SPEECH_KEY / AZURE_SPEECH_REGION 이 없습니다 (.env.sample 을 .env 로 복사해 채우세요)'
    );
  }
  const lang = voice.split('-').slice(0, 2).join('-');
  const ssml =
    `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="${lang}">` +
    `<voice name="${voice}"><prosody rate="${rate}" pitch="${pitch}">` +
    `${text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}` +
    `</prosody></voice></speak>`;

  let lastError;
  for (let attempt = 1; attempt <= AZURE_ATTEMPTS; attempt += 1) {
    try {
      const res = await fetch(`https://${region}.tts.speech.microsoft.com/cognitiveservices/v1`, {
        method: 'POST',
        headers: {
          'Ocp-Apim-Subscription-Key': key,
          'Content-Type': 'application/ssml+xml',
          'X-Microsoft-OutputFormat': 'audio-24khz-96kbitrate-mono-mp3',
          'User-Agent': 'develop-video',
        },
        body: ssml,
        signal: AbortSignal.timeout(AZURE_TIMEOUT_MS),
      });
      if (!res.ok) {
        const body = (await res.text()).slice(0, 500);
        if (AZURE_DEAD_STATUS.has(res.status)) {
          throw unavailable(`Azure TTS ${res.status} — 키 만료·결제·쿼터 문제로 보입니다: ${body}`);
        }
        throw fatal(`Azure TTS ${res.status}: ${body}`);
      }
      // 본문을 끝까지 받는 것까지가 한 번의 시도다. 여기서 멈추는 경우가 실제로 있어
      // 예전에는 이 줄이 try 밖에 있다가 잡히지 않은 채로 빌드를 통째로 죽였다.
      fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
      return;
    } catch (err) {
      if (err.unavailable || err.azureFatal) throw err;
      lastError = err;
      if (attempt < AZURE_ATTEMPTS) {
        process.stdout.write(
          `  ! Azure TTS 응답이 끊겼습니다 (${attempt}/${AZURE_ATTEMPTS}) — 다시 시도합니다: ${err.message}\n`
        );
      }
    }
  }
  // 리전 주소가 틀렸거나 망이 막힌 경우 — 남은 구간도 결과가 같으므로 제공자째로 내린다.
  throw unavailable(`Azure TTS 연결 실패 (${AZURE_ATTEMPTS}회 시도): ${lastError.message}`);
}


// ── ElevenLabs ────────────────────────────────────────────────────────────────
// 유료 API. 키는 .env 의 ELEVENLABS_API_KEY 하나뿐이고 리전 개념이 없다.
//
// 목소리 id 를 코드에 박아 두지 않는다 — 계정마다 보유 목록이 다르고(복제·커스텀 음성 포함)
// 프리메이드 id 도 바뀐다. 지정이 없으면 /v1/voices 를 조회해 성별 라벨로 고르고, 고른 이름을
// 화면에 찍어 준다. 고정하고 싶으면 scenes.json 의 voice.voice 나 ELEVENLABS_VOICE_ID 에 id 를 넣는다.
const ELEVEN_API = 'https://api.elevenlabs.io/v1';

// 401 잘못된 키 · 402 결제 필요 · 403 정지 · 429 한도 초과. 422(잘못된 목소리·모델)는
// 설정 문제라 폴백하지 않고 그대로 드러낸다 — 조용히 edge 로 내려가면 원인을 못 찾는다.
const ELEVEN_DEAD_STATUS = new Set([401, 402, 403, 429]);

async function elevenFetch(pathname, init = {}) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key) {
    throw unavailable('ELEVENLABS_API_KEY 가 없습니다 (.env.sample 을 .env 로 복사해 채우세요)');
  }
  let res;
  try {
    res = await fetch(`${ELEVEN_API}${pathname}`, {
      ...init,
      headers: { 'xi-api-key': key, ...(init.headers ?? {}) },
    });
  } catch (err) {
    throw unavailable(`ElevenLabs 연결 실패: ${err.message}`);
  }
  if (!res.ok) {
    const body = (await res.text()).slice(0, 500);
    // 무료 플랜은 보이스 라이브러리(공유) 목소리를 API 로 못 쓴다 — "내 음성"에 추가해도 마찬가지다.
    // 목소리를 잘못 고른 것이지 키가 죽은 게 아니므로, 원인을 분명히 적어서 알린다.
    if (/paid_plan_required|library voices/i.test(body)) {
      throw unavailable(
        'ElevenLabs 무료 플랜은 보이스 라이브러리 목소리를 API 로 쓸 수 없습니다 ' +
          '("내 음성"에 추가해도 안 됩니다).\n' +
          '  → 기본 제공(premade) 목소리를 쓰거나, 유료 플랜으로 올리세요.\n' +
          '  → 한국어 원어민 목소리가 필요하면 --provider azure (ko-KR-*Neural) 가 낫습니다.'
      );
    }
    // 크레딧 소진은 401/402 로 오면서 본문에 quota 가 들어오는 경우가 있어 본문도 본다.
    if (ELEVEN_DEAD_STATUS.has(res.status) || /quota|unusual_activity/i.test(body)) {
      throw unavailable(`ElevenLabs ${res.status} — 키·크레딧 문제로 보입니다: ${body}`);
    }
    throw new Error(`ElevenLabs ${res.status}: ${body}`);
  }
  return res;
}

export async function elevenVoices() {
  return (await (await elevenFetch('/voices')).json()).voices ?? [];
}

export async function elevenModels() {
  return (await (await elevenFetch('/models')).json()) ?? [];
}

// 크레딧 잔량 — 글자를 쓰지 않고 키만 확인할 때 쓴다(check-tts.js).
export async function elevenSubscription() {
  return (await elevenFetch('/user/subscription')).json();
}

// 한국어 목소리 기준값. ElevenLabs 목소리 id 는 계정마다 다르므로 **이름**으로 적어 둔다 —
// 이름은 보이스 라이브러리에서 바뀌지 않고, 사용자가 화면에서 본 그대로라 확인이 쉽다.
// 앞에 있는 것부터 찾아 계정에 있으면 그것을 쓴다. 하나도 없으면 성별 라벨로 고른다.
//
// 주의: ElevenLabs 의 "탐색(Voice Library)" 목소리는 **내 음성에 추가해야** API 로 쓸 수 있다.
// 추가하지 않으면 /v1/voices 에 안 나오고, 여기 이름도 못 찾는다.
export const ELEVEN_PRESETS = {
  // 이름 · 화면 설명 기준 성별 (라이브러리 설명에서 옮긴 것이라 계정 라벨과 다를 수 있다)
  female: [
    'Annie', //        친근·부드럽고 또렷 — 기준값. 강의·매뉴얼에 무난하다
    'Kanna', //        젊은 여성, 차분·친근 — 홍보·쇼츠
    'Sola', //         맑고 풍부 — 내레이션
    'Park Hyun-mi', // 중년 여성 — 신뢰감이 필요한 안내
    'Chungman', //     명상적·부드러움 — 느린 학습 영상
    'Hanabad', //      편안한 톤
  ],
  male: [
    'Taehyung', //     젊은 남성, 자연·친근·또렷 — 기준값
    'Hojin Lim', //    30대 남성, 자연스럽고 몰입감
    'Harry Kim', //    대화체, 차분
    'Juan', //         깊고 풍부한 스토리텔러 — 다큐·생애사
  ],
};

// 목소리 id 는 20자 안팎의 영숫자다. 공백이나 하이픈이 있으면 이름으로 본다.
const looksLikeVoiceId = (s) => /^[A-Za-z0-9]{18,26}$/.test(s);

const elevenPicked = new Map();

// "auto:female" → 계정이 가진 목소리 중 하나를 고른다. 한 번 고르면 실행 내내 같은 것을 쓴다
// (씬마다 다른 목소리가 나오면 영상이 망가진다).
async function resolveElevenVoice(spec) {
  if (looksLikeVoiceId(spec)) return { id: spec, name: spec };
  if (elevenPicked.has(spec)) return elevenPicked.get(spec);

  const voices = await elevenVoices();
  if (!voices.length) {
    throw unavailable(
      'ElevenLabs 계정에 쓸 수 있는 목소리가 없습니다.\n' +
        '  보이스 라이브러리(탐색)에서 쓸 목소리를 "내 음성"에 추가한 뒤 다시 실행하세요.'
    );
  }
  const byName = (name) =>
    voices.find((v) => String(v.name).toLowerCase().includes(String(name).toLowerCase()));

  let best;
  let how;
  if (!spec.startsWith('auto:')) {
    // 이름으로 지정 — 부분 일치로 찾는다("Annie" → "Annie - Friendly, Soft and Clear").
    best = byName(spec);
    if (!best) {
      throw new Error(
        `ElevenLabs 목소리를 찾지 못했습니다: "${spec}"\n` +
          `  계정에 있는 것: ${voices.map((v) => v.name).slice(0, 12).join(' · ')}\n` +
          `  전체 목록: node tools/video/check-tts.js --list-voices`
      );
    }
    how = '이름 지정';
  } else {
    const gender = spec.slice('auto:'.length);
    // ① 한국어 기준값 목록 순서대로 계정에서 찾는다
    for (const name of ELEVEN_PRESETS[gender] ?? []) {
      best = byName(name);
      if (best) {
        how = '기준값';
        break;
      }
    }
    // ② 없으면 성별 라벨 → 한국어 표기 → 이름순
    if (!best) {
      const score = (v) => {
        const labels = v.labels ?? {};
        const langs = JSON.stringify(v.verified_languages ?? labels.language ?? '');
        return (
          (String(labels.gender ?? '').toLowerCase() === gender ? 4 : 0) +
          (/ko|korean/i.test(langs) ? 2 : 0) +
          (v.category === 'premade' ? 1 : 0)
        );
      };
      best = [...voices].sort(
        (a, b) => score(b) - score(a) || String(a.name).localeCompare(String(b.name))
      )[0];
      how = '라벨 추정';
    }
  }

  const picked = { id: best.voice_id, name: best.name };
  elevenPicked.set(spec, picked);
  process.stdout.write(`  · ElevenLabs 목소리(${how}): ${picked.name}  [${picked.id}]\n`);
  return picked;
}

async function synthEleven({ text, file, voice, rate, voiceConfig }) {
  const picked = await resolveElevenVoice(voice);
  const model = voiceConfig?.model ?? process.env.ELEVENLABS_MODEL ?? 'eleven_multilingual_v2';
  // ElevenLabs 에는 pitch 가 없고 속도는 voice_settings.speed(배율)다. "+8%" → 1.08 로 옮긴다.
  // 기본값(1.0)일 때는 아예 안 보낸다 — 구형 API 가 speed 를 모르면 422 로 죽기 때문이다.
  const speed = Math.min(1.2, Math.max(0.7, 1 + (Number.parseFloat(rate) || 0) / 100));
  const settings = {
    stability: voiceConfig?.stability ?? 0.5,
    similarity_boost: voiceConfig?.similarity ?? 0.75,
    ...(Math.abs(speed - 1) > 0.001 ? { speed } : {}),
  };
  const res = await elevenFetch(`/text-to-speech/${picked.id}?output_format=mp3_44100_128`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, model_id: model, voice_settings: settings }),
  });
  fs.writeFileSync(file, Buffer.from(await res.arrayBuffer()));
}

// 목소리는 언어 × 성별로 고른다. voice에 정확한 id를 직접 쓰면 그쪽이 우선한다.
// (edge-tts `--list-voices`로 더 많은 후보를 볼 수 있다.)
const VOICE_TABLE = {
  ko: { female: 'ko-KR-SunHiNeural', male: 'ko-KR-InJoonNeural' },
  en: { female: 'en-US-JennyNeural', male: 'en-US-GuyNeural' },
  ja: { female: 'ja-JP-NanamiNeural', male: 'ja-JP-KeitaNeural' },
  zh: { female: 'zh-CN-XiaoxiaoNeural', male: 'zh-CN-YunxiNeural' },
};

export function resolveVoice(voiceConfig = {}) {
  return resolveVoiceFor(voiceConfig.provider === 'file' ? voiceConfig.fallback : voiceConfig.provider, voiceConfig);
}

// 목소리 이름은 제공자마다 체계가 다르다 — edge·azure 는 같은 뉴럴 id(ko-KR-SunHiNeural),
// sapi 는 윈도에 설치된 음성 이름, eleven 은 계정별 voice_id 다. 폴백으로 제공자가 바뀌면
// 이름도 같이 바뀌어야 한다(azure 이름을 edge 에 넘기면 우연히 되지만, eleven id 를 넘기면 죽는다).
export function resolveVoiceFor(provider, voiceConfig = {}) {
  if (provider === 'eleven') {
    return voiceConfig.voice ?? process.env.ELEVENLABS_VOICE_ID ?? `auto:${voiceConfig.gender ?? 'female'}`;
  }
  if (voiceConfig.voice) return voiceConfig.voice;
  if (provider === 'sapi') return ''; // 윈도 기본 목소리
  const table = VOICE_TABLE[voiceConfig.lang ?? 'ko'] ?? VOICE_TABLE.ko;
  return table[voiceConfig.gender ?? 'female'] ?? table.female;
}

const PROVIDERS = {
  edge: { synth: synthEdge, ext: 'mp3' },
  sapi: { synth: synthSapi, ext: 'wav' },
  azure: { synth: synthAzure, ext: 'mp3' },
  eleven: { synth: synthEleven, ext: 'mp3' },
};

export const PROVIDER_LIST = Object.keys(PROVIDERS);

// 제공자가 붙여 보내는 앞뒤 무음을 잘라낸다. Azure 는 앞 ~0.35초·뒤 ~1.1초를 항상 붙인다 —
// 클립마다 1.4초씩, 7클립 쇼츠에서 10초가 침묵으로 샜다. 클립 길이는 audioDuration 에서
// 계산되므로 여기서 안 자르면 그 무음이 화면 시간까지 늘린다.
// 문장 중간 호흡(쉼표)은 건드리지 않는다 — 앞뒤에서만 자른다.
// 앞 0.12초·뒤 0.25초는 남긴다: 첫 프레임과 동시에 말이 터지면 부자연스럽다.
async function trimEdgeSilence(file) {
  const trimmed = `${file}.trim${path.extname(file)}`;
  await run('ffmpeg', [
    ...['-hide_banner', '-loglevel', 'error', '-y'],
    ...['-i', file],
    '-af',
    'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,' +
      'areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.25,areverse',
    trimmed,
  ]);
  fs.renameSync(trimmed, file);
}

// 폴백 없이 지정한 제공자로 딱 한 번 합성한다 — 점검(check-tts.js)에서 쓴다.
// 씬 파이프라인과 달리 여기서는 "어느 제공자가 살아 있는가"를 있는 그대로 봐야 하므로 폴백이 없다.
export function synthDirect(name, args) {
  const provider = PROVIDERS[name];
  if (!provider) throw new Error(`알 수 없는 TTS 제공자: ${name} (${PROVIDER_LIST.join('|')})`);
  return provider.synth(args);
}

// 키가 필요한 제공자가 죽었을 때 대신 쓸 제공자.
// azure → edge 는 "무료 등급으로 내려간다"에 가깝다. edge-tts 는 Edge 브라우저의 읽어주기
// 엔드포인트로, 키 없이 같은 Azure 뉴럴 음성(ko-KR-SunHiNeural …)을 쓴다. 목소리 id 가 같으니
// scenes.json 을 한 줄도 안 고치고 이어서 만든다. 확장자도 둘 다 mp3 라 캐시 경로가 어긋나지 않는다.
// (다만 azure 전용 커스텀 보이스는 edge 에 없다 — 그때는 edge-tts 가 이름을 못 찾고 그대로 실패한다.)
const UNAVAILABLE_FALLBACK = { azure: 'edge', eleven: 'edge' };

// 한 번 죽은 제공자는 실행이 끝날 때까지 죽은 것으로 둔다 — 씬마다 401 을 다시 맞지 않는다.
// build.js 가 씬·엔드카드·모션을 나눠 호출하므로 이 상태는 모듈 수준에 둔다.
const degraded = new Map();

export function activeProvider(name) {
  return degraded.get(name) ?? name;
}

// 목소리 이름은 제공자별로 여기서 채운다 — 폴백으로 제공자가 바뀌면 이름도 함께 바뀌어야 한다.
async function synthWithFallback(name, args, { allowFallback = true } = {}) {
  const active = activeProvider(name);
  const forProvider = (p) => ({ ...args, voice: resolveVoiceFor(p, args.voiceConfig) });
  try {
    return await PROVIDERS[active].synth(forProvider(active));
  } catch (err) {
    const next = UNAVAILABLE_FALLBACK[active];
    if (!err.unavailable || !next || !allowFallback) throw err;
    degraded.set(name, next);
    process.stdout.write(`  ! ${active} 사용 불가 → ${next}(키 불필요)로 전환합니다\n    ${err.message}\n`);
    return PROVIDERS[next].synth(forProvider(next));
  }
}

/**
 * 씬별 음성을 만들고 실제 길이를 되돌려준다.
 * 영상은 이 길이에 맞춰 촬영되므로 이 단계가 파이프라인의 기준선이다.
 */
export async function synthesizeScenes(scenes, voiceConfig, dirs, { force = false } = {}) {
  const useFile = voiceConfig.provider === 'file';
  const synthName = useFile ? voiceConfig.fallback : voiceConfig.provider;
  const provider = synthName ? PROVIDERS[synthName] : null;
  if (synthName && !provider) {
    throw new Error(`알 수 없는 TTS 제공자: ${synthName} (edge|sapi|azure|file)`);
  }
  if (!useFile && !provider) {
    throw new Error(`알 수 없는 TTS 제공자: ${voiceConfig.provider} (edge|sapi|azure|file)`);
  }
  const dir = ensureDir(dirs.audio);
  const manifestFile = path.join(dir, 'manifest.json');
  const manifest = !force && fs.existsSync(manifestFile) ? readJson(manifestFile) : {};

  // file 제공자: 직접 녹음/촬영한 파일을 그대로 쓴다. 없는 씬은 fallback으로 합성해
  // 일부만 먼저 찍어 두고 나머지는 TTS로 메우는 식의 제작이 가능하다.
  // dir 을 안 주면 영상 id 로 갈린 폴더를 쓴다 — presenter/ 를 통째로 쓰면 씬 id 가 같은
  // 다른 영상의 녹음을 집어 간다(presenter.js 의 같은 주석 참조).
  const voiceDir = voiceConfig.dir
    ? path.resolve(AD_DIR, voiceConfig.dir)
    : path.join(AD_DIR, 'presenter', dirs.id);

  const results = [];
  for (const scene of scenes) {
    if (useFile) {
      const recorded = findVoiceFile(voiceDir, scene.id);
      if (recorded) {
        results.push({
          ...scene,
          audioFile: recorded,
          audioDuration: await mediaDuration(recorded),
          recorded: true,
        });
        continue;
      }
      if (!voiceConfig.fallback) {
        throw new Error(
          `녹음 파일이 없습니다: ${path.join(voiceDir, scene.id)}.{${VOICE_EXTS.join('|')}}\n` +
            `일부만 찍었다면 voice.fallback을 "edge"로 두면 나머지는 TTS로 채웁니다.`
        );
      }
    }

    // 폴백이 걸린 뒤에는 그쪽 확장자를 쓴다 (azure→edge 는 둘 다 mp3 라 실제로는 같다).
    const file = path.join(dir, `${scene.id}.${PROVIDERS[activeProvider(synthName)].ext}`);
    // 'trim1' 은 앞뒤 무음 트리밍 도입 표식 — 트리밍 전에 만든 캐시(무음 포함)를 한 번
    // 무효화한다. 지우면 예전 mp3 가 그대로 재사용돼 무음이 남는다.
    const hash = crypto
      .createHash('sha1')
      .update(JSON.stringify([scene.narration, voiceConfig, 'trim1']))
      .digest('hex')
      .slice(0, 12);
    const cached = manifest[scene.id];

    if (cached?.hash === hash && fs.existsSync(file)) {
      results.push({ ...scene, audioFile: file, audioDuration: cached.duration, cached: true });
      continue;
    }
    await synthWithFallback(
      synthName,
      {
        text: scene.narration,
        file,
        voiceConfig, // voice(목소리 이름)는 실제로 쓰는 제공자에 맞춰 synthWithFallback 이 채운다
        rate: voiceConfig.rate ?? '+0%',
        volume: voiceConfig.volume ?? '+0%',
        pitch: voiceConfig.pitch ?? '+0Hz',
      },
      // voice.strict: true 로 두면 폴백 없이 그대로 실패한다 — 납품본 목소리를 반드시
      // azure 로 맞춰야 해서 조용히 바뀌면 안 되는 경우에 쓴다.
      { allowFallback: !voiceConfig.strict }
    );
    await trimEdgeSilence(file);
    const duration = await mediaDuration(file);
    manifest[scene.id] = { hash, duration };
    results.push({ ...scene, audioFile: file, audioDuration: duration, cached: false });
  }

  writeJson(manifestFile, manifest);
  return results;
}
