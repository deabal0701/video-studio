# 04 — 유스케이스 계약 (구 API) · 잡 큐 · engine 호출 계약

> **2026-08-21 데스크톱 전환 (D12):** HTTP 계층은 제거된다. 아래 REST 표의 각 행은
> `core/facade.py` 유스케이스의 계약으로 **1:1 승계**된다 — 경로 표기는 유스케이스 이름의
> 역할을 하고, 상태 코드는 예외 종류로 바뀐다 (409→`EtagMismatch`, 422→`ValidationError` 류).
> SSE 는 잡 큐 이벤트의 Qt Signal 릴레이로 대체된다 ([07_desktop.md](07_desktop.md) 대응표).
> 잡 상태머신·동시성 정책·engine 호출 계약은 변경 없이 그대로다.

## 원칙

- 모든 쓰기(파일 저장)는 **etag 검사** (etag = 파일 mtime+size 해시 — 구 If-Match). 불일치면
  현재 내용을 동봉해 실패 → 화면이 diff 표시 후 사람이 병합. 파일 SSOT 라(앱 밖에서
  에디터·Claude Code 가 같은 파일을 고친다) 낙관적 잠금이 유일한 정답 — HTTP 가 없어져도 유지.
- 자원 id = 폴더명 (`hr-basics`, `hr-basics-01`).
- 에러: `{code, message, hint?}` 구조의 예외. 검증 실패는 필드별 상세 동봉.

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
| `GET /api/episodes/{id}` | scenes.json 원문 + etag + 파생 상태 |
| `PUT /api/episodes/{id}` | 저장: `_` 보존 직렬화 → 검증 결과 + **pathIssues**(경로 역산 실존 검사) 동봉. 경로 기입은 UI 피커+paths.py 가 입력 시점에 수행 — "자산 참조 역산 응답" 방식은 3단계에서 이 구도로 대체 확정 (2026-08-15 실측) |
| `GET/PUT /api/episodes/{id}/plan` | plan.md 라운드트립 (④ 표 편집기) |
| `POST /api/episodes/{id}/plan/apply` | 구성표 → 클립 골격 반영 (없는 구간만 표 순서 자리에 삽입) |
| `POST /api/episodes/{id}/sync-course` | voice·render 를 course 값으로 맞춤 (일관성 [강좌 값으로 맞추기]) |
| `GET /api/episodes/{id}/inspect` | inspect.js 원본 JSON — ⑤ 에디터 재료 (templates 받는 키·audioCache 실측·media) |
| ~~`GET /api/episodes/{id}/files?path=…`~~ | **폐기 (2026-08-22 코드 리뷰).** 회차 폴더 원본 파일 읽기용이었으나 Qt 화면이 끝내 쓰지 않았다 — ⑤ 프리뷰는 `template_preview` + `paths.invert` 로 실제 경로를 직접 연다. `facade.episode_file` 삭제 |
| `POST /api/courses/{cid}/brandkit/apply` | 프리셋 타이틀 카드·스팅어 재카피 (③ — 덮어쓰기 확인은 화면 몫) |

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
| `GET /api/episodes/{id}/subtitle-check` | 자막 대조 — .srt ↔ 대본 공백무시 diff (어긋나면 첫 지점 전후 동봉) |
| `POST /api/episodes/{id}/bg-frame` | B롤 videoStart 프레임 → bg/ 저장 → html 기준 src 상대경로 반환 (⑤ title 특수 버튼) |
| `GET/PUT /api/episodes/{id}/review` | 검수 체크리스트 기록 (frames 확인 체크 등 — `out/review.json`) |
| `GET /api/episodes/{id}/deliverables` | 제목·설명·챕터(chapters.js)·srt 경로·썸네일 후보 |
| `POST /api/episodes/{id}/deliverables/save` | 편집한 제목·설명 → youtube.md 저장 (⑦) |
| `GET /api/media/{id}/**` | out/ 산출물 접근 (데스크톱은 파일 경로 직접 반환 — QMediaPlayer 가 읽음) |

### 자산·템플릿·TTS

| 메서드·경로 | 동작 |
|---|---|
| `GET /api/assets?kind=broll\|bgm\|photo\|font` | 라이브러리 (길이·해상도·라이선스 메타) |
| `POST /api/assets` | `{kind, url, name?}` — fetch.js 로직 (허용 호스트 검증) + 라이선스 필수 |
| `GET /api/assets/file?kind=…&name=…` | 소재 실물 (BGM 재생·B롤 프리뷰용) |
| `GET /api/templates?scope=common\|{episodeId}` | 모션 템플릿 + `paramsKeys` + 썸네일 |
| `GET /api/templates/preview?file=…` | QWebEngineView 용 렌더 문서 (preview.js — params 는 URL 질의). **file 은 갤러리 목록의 화이트리스트만 허용** — 임의 경로 통과 금지 (2026-08-21 리뷰: HTTP 시절 저장소 밖 파일 읽기 가능 결함) |
| `POST /api/tts/sample` | `{text, voice}` → mp3 (미리듣기 — edge 무료) |
| ~~`POST /api/episodes/{id}/tts`~~ | **폐기 (2026-08-22 코드 리뷰).** `submit_build(only="tts")` 한 줄 래퍼(`facade.refresh_tts`)였고 화면은 `submit_build` 를 직접 부른다 — 같은 일을 하는 두 번째 문이라 삭제 |

### 에이전트 (4단계 — [05_agent.md](05_agent.md))

| 메서드·경로 | 동작 |
|---|---|
| `POST /api/agent/draft` | `{episodeId, brief, sourceDocs[]}` → 잡 (plan.md+facts.md+scenes.json 초안) |
| `POST /api/agent/diagram` | `{episodeId, clipId, describe}` → 잡 (motion html 생성) |
| `POST /api/agent/review` | `{episodeId}` → 잡 (reviewer — 점수·지적) |
| `GET /api/agent/status` | 게이트 — 선택 제공자(D15: claude\|openai)의 키 유무·모델. 없으면 버튼 비활성+사유 |
| `GET /api/agent/usage` | 토큰·비용 미터 (`.cache/agent-usage.jsonl` 적산) |

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

## 잡 이벤트 스키마 (구 SSE → Qt Signal 페이로드)

```
progress   {"jobId","phase":"tts|record|compose|verify","step":"s1a","pct":44,"msg":"모션 렌더 7/16"}
log        {"jobId","line":"  · hook   8.9s  이 사람은…"}
done       {"jobId","result":{"files":[…],"duration":296.2}}
failed     {"jobId","error":"…","logTail":[…]}
```

phase·step 은 build.js stdout 을 파싱해 얻는다 (아래 계약). 이벤트 원천은 동일하게
`JobQueue.subscribe()`(잡별)·`listener` 훅(전역)이고, 데스크톱에서는 qtbridge 가 이를
Qt Signal 로 릴레이한다 — 하단 상태바 칩·보드 실시간 갱신용. 파일 외부 변경 알림은
QFileSystemWatcher 가 같은 채널로 발행한다.

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
