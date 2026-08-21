# 04 — API · 잡 큐 · engine 호출 계약

## 원칙

- REST + SSE. 웹소켓 불요 (서버→클라 단방향 스트림뿐).
- 모든 쓰기(파일 저장)는 **If-Match: `<etag>`** (etag = 파일 mtime+size 해시). 불일치 409 →
  클라가 diff 표시 후 사람이 병합. 파일 SSOT 라 낙관적 잠금이 유일한 정답.
- 자원 id = 폴더명 (`hr-basics`, `hr-basics-01`). URL 인코딩 주의 (한글 폴더 허용).
- 에러: `{code, message, hint?}`. 검증 실패는 422 + 필드별 상세.

## REST 설계

### 강좌·회차

| 메서드·경로 | 동작 |
|---|---|
| `GET /api/courses` | 강좌 목록 (인덱서 — id·title·회차수·상태 요약) |
| `POST /api/courses` | 개설: 폴더 + course.json + intro/stinger 템플릿 카피 |
| `GET /api/courses/{cid}` | course.json + 파생 상태(회차별 배지) |
| `PUT /api/courses/{cid}` | course.json 저장 (If-Match) → 일관성 재검사 결과 반환 |
| `GET /api/courses/{cid}/episodes` | 커리큘럼 보드 데이터 (episodes[] × 파생 상태 join) |
| `POST /api/courses/{cid}/episodes` | 회차 스캐폴딩 (템플릿+voice/render/palette 주입+골격 클립) |
| `GET /api/episodes/{id}` | scenes.json(자산 참조로 역산된 형태) + etag + 파생 상태 |
| `PUT /api/episodes/{id}` | 저장: 자산 참조 → 경로 계산 기입 → `_` 보존 직렬화 → 검증 결과 동봉 |
| `GET/PUT /api/episodes/{id}/plan` | plan.md 표 라운드트립 |
| `POST /api/episodes/{id}/plan/apply` | 구성표 → 클립 골격 반영 |

### 검증·빌드·검수

| 메서드·경로 | 동작 |
|---|---|
| `POST /api/episodes/{id}/preflight` | inspect.js 실행 → `{findings: [{level, clip, msg}]}` |
| `POST /api/episodes/{id}/build` | 잡 제출 `{only?: tts\|record\|compose, variant?, force?}` → `{jobId}` |
| `GET /api/jobs` · `GET /api/jobs/{jid}` | 큐 상태 |
| `GET /api/jobs/{jid}/events` | **SSE** — 아래 이벤트 스키마 |
| `POST /api/jobs/{jid}/cancel` | 프로세스 종료 (엔진 .lock 은 다음 실행이 이어받음) |
| `GET /api/episodes/{id}/frames?preset=review` | 검수 프레임 4+1종 자동 추출 (캐시) |
| `GET /api/episodes/{id}/frames?t=12.5` | 임의 시각 프레임 |
| `GET /api/episodes/{id}/silence` | silencedetect + 원인 분류 (`uniform-breath` vs `clip-end`) |
| `GET /api/episodes/{id}/consistency` | voice/render ≡ course + 직전 회차 타이틀 프레임 쌍 |
| `GET/PUT /api/episodes/{id}/review` | 검수 체크리스트 기록 (frames 확인 체크 등 — `out/review.json`) |
| `GET /api/episodes/{id}/deliverables` | 제목·설명·챕터(chapters.js)·srt 경로·썸네일 후보 |
| `GET /api/media/{id}/**` | out/ 정적 서빙 (mp4 Range 지원 — 재생용) |

### 자산·템플릿·TTS

| 메서드·경로 | 동작 |
|---|---|
| `GET /api/assets?kind=broll\|bgm\|photo\|font` | 라이브러리 (길이·해상도·라이선스 메타) |
| `POST /api/assets` | `{kind, url, name?}` — fetch.js 로직 (허용 호스트 검증) + 라이선스 필수 |
| `GET /api/templates?scope=common\|{episodeId}` | 모션 템플릿 + `paramsKeys` + 썸네일 |
| `GET /api/templates/preview?file=…&params=…` | iframe 용 렌더 문서 (preview.js) |
| `POST /api/tts/sample` | `{text, voice}` → mp3 (미리듣기 — edge 무료) |
| `POST /api/episodes/{id}/tts` | 특정 클립만 TTS 갱신 (`--only tts` 부분판) |

### 에이전트 (4단계 — [05_agent.md](05_agent.md))

| 메서드·경로 | 동작 |
|---|---|
| `POST /api/agent/draft` | `{episodeId, brief, sourceDocs[]}` → 잡 (plan.md+facts.md+scenes.json 초안) |
| `POST /api/agent/diagram` | `{episodeId, clipId, describe}` → 잡 (motion html 생성) |
| `POST /api/agent/review` | `{episodeId}` → 잡 (reviewer — 점수·지적) |
| `GET /api/agent/usage` | 토큰·비용 미터 |

## 빌드 잡 — 상태머신·큐 정책

```
queued → preflight → running(tts → record? → compose) → verifying(프레임 자동추출) → done
              └ blocked(사전점검 치명) ┘        └ failed(로그 보존) · canceled
```

- **preflight 는 잡의 1단계로 강제** — 치명(blocker)이면 굽지 않고 `blocked` (스킬: "끄고 굽지 않는다").
  `force` 는 경고급만 무시, blocker 는 무시 불가.
- `verifying`: 완료 직후 검수 프레임 4+1종·무음 리포트를 **자동 생성** — 사람이 ⑥ 화면을
  열면 이미 준비돼 있다 ("빌드가 도는 동안이 검증 시간" 규약의 자동화).

**동시성 정책** (스킬의 "지켜야 할 선"을 큐 규칙으로 옮김):

| 규칙 | 구현 |
|---|---|
| 같은 회차 동시 빌드 금지 | 큐 키 = episodeId 직렬화 + 엔진 `.lock` 이중 방어 |
| 화면 녹화(`scenes[]` 비어있지 않음) 잡은 전역 직렬 | 앱 상태 오염 방지. baseUrl 이 다르면 병렬 허용 |
| 모션 전용 잡 | 자유 병렬 |
| 전역 동시 상한 | 기본 2 (Chromium+ffmpeg 부하) — 설정 가능. 상용은 워커 수 |

잡 기록: `jobs/` (SQLite). 로그 파일은 `out/<id>/work/build-<jobId>.log` — 파일 SSOT 원칙 유지.

## SSE 이벤트 스키마

```
event: progress   data: {"jobId","phase":"tts|record|compose|verify","step":"s1a","pct":44,"msg":"모션 렌더 7/16"}
event: log        data: {"jobId","line":"  · hook   8.9s  이 사람은…"}
event: done       data: {"jobId","result":{"files":[…],"duration":296.2}}
event: failed     data: {"jobId","error":"…","logTail":[…]}
```

phase·step 은 build.js stdout 을 파싱해 얻는다 (아래 계약). 전역 스트림
`GET /api/events` 도 제공 (상단 바 칩·커리큘럼 보드 실시간 갱신용 — 잡 상태 변화 + 파일 외부 변경 알림).

## engine 호출 계약 (core/engine_io.py)

**엔진은 무수정 원칙** — Python 쪽이 엔진의 현재 출력 형식에 맞춘다. 단 `inspect.js` 는 신설([01](01_architecture.md)).

| 호출 | 명령 | 파싱 |
|---|---|---|
| 빌드 | `node engine/build.js --project <dir> [--only …] [--variant …]` | stdout 라인: `[N] 제목` = phase 전환 · `  · <id> <len>s` = step. **엔진 stdout 형식이 바뀌면 파서만 고치면 되도록 정규식을 한 모듈에 격리** |
| 사전점검+메타 | `node engine/inspect.js --project <dir> --json` | **신설.** `{preflight:[{level,clip,msg}], templates:{<file>:{params:[…]}}, media:{<file>:{duration,width,height}}, audioCache:{<id>:duration}}` — preflight.js·templateKeys·ffprobe 재사용, JSON 한 방 |
| TTS 샘플 | `node engine/check-tts.js --provider edge --text … --keep` | `ffplay …` 안내 라인에서 생성 파일 경로 (2026-08-14 실측 — `--sample-text` 는 `--sample-voices` 전용 인자였다) |
| 챕터 | `node engine/chapters.js --project <id> --video-root <root>` | stdout `MM:SS 제목` 라인 |
| 프리뷰 | `node engine/preview.js --file … --params-json …` | 자체완결 html 문서 반환 (stdout) |
| 프레임 추출 | ffmpeg 직접 (`-ss <t> -frames:v 1`) | — |
| 무음 | ffmpeg `silencedetect` | stderr 파싱 |

subprocess 규약: cwd = 엔진 루트 · 타임아웃(빌드 60분·기타 60초) · 취소 = SIGTERM→SIGKILL ·
stdout 은 라인 단위 스트리밍으로 SSE 에 릴레이.

## 인덱서

- 기동 시 projects/ 전체 스캔 → SQLite. 이후 watchfiles 증분.
- 강좌 판정: `course.json` 있는 폴더. 회차 판정: `<강좌id>-NN` 패턴 + scenes.json.
  패턴 밖 폴더는 "단발 영상"으로 목록에만 (편집 지원은 강좌와 동일 — course 상속 기능만 빠짐).
- 캐시는 언제나 삭제 가능. 스키마 버전 올리면 전체 재스캔.
