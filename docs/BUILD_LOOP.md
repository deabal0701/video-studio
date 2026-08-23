# BUILD_LOOP — 단계 실행 루프 SSOT

이 파일은 **구현 진행의 단일 정본(SSOT)** 이다. 어떤 세션이든(사람·Claude·/loop 반복)
아래 프로토콜만 따르면 이어서 진행할 수 있다. 설계 내용의 정본은 여전히
[docs/design/](design/README.md)이고, 이 파일은 "지금 어디까지 왔고 다음에 무엇을 하는가"만 담는다.

## 루프 프로토콜

1. 이 파일과 [CLAUDE.md](../CLAUDE.md) 진행 상태를 읽는다.
2. 아래 단계 표에서 **첫 번째 미완(⬜/🔄) 단계**를 찾는다.
3. 그 단계의 "투입 프롬프트"를 그대로 수행한다. 착수 전 해당 설계 문서를 먼저 읽는다.
4. 끝나면 **수용 기준을 항목별로 실측 검증**하고(추정 금지 — 명령 실행·파일 확인),
   이 파일의 단계 표·완료 기록과 CLAUDE.md 체크박스를 갱신한다.
5. 설계와 어긋난 결정이 나왔으면 설계서(00_overview 결정 표 포함)를 함께 고친다.
6. 다음 반복으로 — 모든 단계가 ✅ 이면 루프 종료.

`/loop` 로 돌릴 때의 반복 프롬프트:

```
docs/BUILD_LOOP.md 의 루프 프로토콜을 따라, 다음 미완 단계를 이어서 진행하라.
```

## 단계 표

| 단계 | 이름 | 상태 | 수용 기준 (정본: [06_roadmap.md](design/06_roadmap.md)) |
|---|---|---|---|
| 0 | 저장소 스캐폴딩 | ✅ 2026-08-14 | 새 저장소 단독으로(h5-saas 없이) 픽스처 회차 빌드 성공 — 292.77s mp4+srt, 프레임 검수 통과 |
| 1 | 읽기 전용 콘솔 | ✅ 2026-08-14 | 화면에서 픽스처 회차 빌드(SSE 진행 확인) → 프레임 4+1종 확인 → mp4 재생 — Playwright 실측 |
| 2 | 강좌 편집 | ✅ 2026-08-15 | 화면만으로 개설→회차 생성→(파일 편집)→빌드 완주 — Playwright 실측. 라운드트립 diff 0 은 테스트 고정 |
| 3 | 대본 에디터 | ✅ 2026-08-15 | 새 회차(hr-basics-02)를 화면만으로 완성 — 대본(피커·자동 폼)→빌드(46.2s mp4)→검수(자막 diff 0)→youtube.md. 결함 입력 시점 차단 실측 |
| 4 | 에이전트 | ✅ 2026-08-15 | AI 초안($0.25)→손질→빌드(109s mp4)→AI 평가($0.21, 6항목 채점) 실키 완주. 1~3단계 키 없이 동작 ✅ |
| 5 | 데스크톱 전환 | 🔄 5-8 까지 코드 완료 · **사용자 준비물 대기** (2026-08-22) | 깨끗한 Windows PC 에서 설치→위저드→픽스처 빌드·검수·배포 준비물까지 화면만으로 완주 (정본: [07_desktop.md](design/07_desktop.md) — 하위 5-0~5-8) |

상태 기호: ⬜ 미착수 · 🔄 진행 중 · ✅ 수용 기준 충족 (검증 완료)

## 단계별 투입 프롬프트

### 0단계

```
0단계를 진행하라. docs/design/06_roadmap.md 의 0단계 작업과 수용 기준을 따르되, 순서는:
1. engine 셀프테스트 (npm install → check-tts → scenes.selftest.json 빌드)
2. inspect.js 작성 (docs/design/04_api.md 의 계약대로 — 기존 lib 재사용, 기존 파일 무수정)
3. 픽스처(fixtures/projects/hr-basics-01) 경로 이전 — bgm·broll·fontUrl 을 이 저장소 기준으로
   고치고 재현 빌드 성공까지. office-talk.mp4 는 CATALOG.md 출처에서 재다운로드
4. Python 골격 (pyproject + core 뼈대 + 테스트 러너)
끝나면 CLAUDE.md 진행 상태를 갱신하고, 수용 기준 충족 여부를 항목별로 보고하라.
```

세부 체크리스트 (진행하며 갱신):

- [x] 0-1 engine 셀프테스트: `npm install` → `check-tts`(edge OK·ffmpeg/ffprobe OK) →
      `scenes.selftest.json` 빌드 → mp4 2개 + srt 2개 (2026-08-14)
- [x] 0-2 `engine/inspect.js` 신설 — `{preflight, templates, media, audioCache}` JSON 출력
      (preflight.js·templateKeys·ffprobe 재사용, 기존 파일 무수정. ENGINE_VERSION.md 에 기록)
- [x] 0-3 픽스처 경로 이전: bgm·broll·모션 file·fontUrl·html 의 _base.css 참조 전부 교정
      (현행 엔진 실측: bgm·video=엔진 루트, 모션 file=대본 폴더 — 02 문서 표 갱신),
      office-talk.mp4 재다운로드(18.92s, Pexels), preflight 이상 없음,
      재현 빌드 성공 — final 292.77s mp4+srt, 프레임 5장 눈검수 통과 (2026-08-14)
- [x] 0-4 Python 골격: pyproject.toml + core 모듈 뼈대(storage·paths·schema·validate·indexer·jobs·engine_io)
      + api/main.py + pytest 7건 통과 (conda `penv3.13-video`)
- [x] CLAUDE.md·이 파일 상태 갱신 + 수용 기준 항목별 보고 (2026-08-14)

### 1단계

```
1단계(읽기 전용 콘솔)를 진행하라. docs/design/06_roadmap.md 1단계 범위와 수용 기준,
04_api.md 의 해당 API·SSE·engine 호출 계약을 따르라.
```

범위 요약: core = storage(LocalFS)·indexer·engine_io·jobs(빌드만) / api = 조회 전부 + build + SSE /
web = 대시보드·강좌·회차 목록·scenes 뷰어(편집 없음)·빌드 버튼+진행·프레임 그리드·mp4 재생.

선행 진행 (0단계 빌드 대기 중 착수):

- [x] core/jobs.py 잡 큐 구현 — preflight 강제·동시 상한 2·같은 회차 직렬·이벤트 구독(subscribe)
      + tests/test_jobs.py 4건 통과 (2026-08-14. 실행 중 취소(SIGTERM)·verifying 단계는 후반 과제)
- [x] api: 조회 라우터(courses·episodes·plan·파생 상태 배지) + preflight + build 제출 +
      jobs 조회/취소 + SSE 릴레이(04 스키마 progress/log/done/failed) + out/ 미디어 서빙
      — tests/test_api.py 6건 통과. 루트는 VIDEO_STUDIO_PROJECTS 로 주입(개발=fixtures/projects) (2026-08-14)
- [x] 검수 조회 API: 프레임 preset=review(4분위+엔드카드 4+1종, out/frames 캐시)·임의 시각 t=,
      무음 검출(silencedetect + uniform-breath/clip-end 분류), voice/render 일관성 대조
      — core/media_ops.py + api/routers/review.py, tests 5건 (2026-08-14. 미빌드 회차는 409 not_built)
- [x] core/indexer Index(SQLite 캐시, .cache/ — 구조만 저장·파생 상태는 계속 계산) +
      lifespan watchfiles 감시(외부 변경 → 재스캔 + fs 이벤트) + 전역 SSE /api/events
      (core/events.EventBus — 잡 이벤트도 listener 로 릴레이) — tests 3건 (2026-08-14.
      주의: 무한 SSE 를 TestClient 스트림으로 중간에 끊으면 매달린다 — 버스를 직접 테스트할 것)
- [x] jobs 실행 중 취소(SIGTERM→5초 뒤 SIGKILL, 엔진 .lock 은 SIGTERM 정리 루틴이 해제) +
      verifying 단계(완료 직후 프레임 4+1종·무음 리포트 자동 생성 — 실패해도 빌드는 done, 로그만)
      — tests/test_jobs.py 5건 (2026-08-14. --only 부분 빌드는 verifying 생략)
- [x] web: Vue 3+Vite+Element Plus+Tailwind v4 골격 + 대시보드(강좌 카드)·커리큘럼 보드(읽기
      전용, 상태·stale 배지)·대본 뷰어(클립 표·글자수)·빌드 버튼(전체/tts/compose)+SSE 진행 로그·
      검수 탭(프레임 4+1 그리드·무음 리포트·일관성 경고)·mp4 재생(Range)·작업 큐·전역 잡 칩.
      Playwright 브라우저 스모크로 실측 (2026-08-14. 실행: uvicorn :8000 + `npm run dev` :5173,
      VIDEO_STUDIO_PROJECTS=fixtures/projects)

### 2단계

```
2단계(강좌 편집)를 진행하라. core/paths.py 경로 계산기부터 — 02_data-model.md 의
실측 5행이 단위 테스트 케이스다. 그다음 화면 ①③과 회차 스캐폴딩.
```

주의: schema 라운드트립(`_` 필드·키 순서·2칸 들여쓰기 보존) · If-Match 낙관적 잠금.

진행 체크리스트:

- [x] core/paths.py 계산기 완성 — compute/invert(역산)·공용 motion 폴백·bundled_font_ref.
      **실측 5행 테스트 + 역산 라운드트립 + 픽스처 전 경로 실존 검증** = tests/test_paths.py 9건 (2026-08-14)
- [x] schema.Document 무손실 라운드트립 — 무수정이면 원문 그대로(diff 0, 손서식 보존),
      수정 시 표준형(2칸·키순서·`_` 보존) — tests/test_schema_roundtrip.py 2건 (2026-08-14)
- [x] 저장 API: PUT /api/courses/{cid}·/api/episodes/{id} — If-Match 필수(없으면 428),
      불일치 409 + 현재 내용 동봉(클라 diff 용), id≠폴더명 422, pydantic(extra allow) 검증,
      Document 저장(무수정이면 API 경유에도 diff 0 — 테스트 고정), 응답에 일관성 재검사 동봉
      — tests/test_save_api.py 6건 (2026-08-14. 자산 참조→경로 기입은 ⑤ 에디터(3단계)에서)
- [x] 회차 스캐폴딩: core/scaffold.py + POST /api/courses/{cid}/episodes — 템플릿(engine/templates/
      lecture/episode.scenes.json) + voice 복사·render 얹기(생성 직후 일관성 0건을 테스트로 고정)·
      palette 전 클립 주입·fontUrl 위치별 계산·강좌 html 경로 기입·plan.md 카피·커리큘럼 자동 등록·
      중복 409 — tests/test_scaffold.py 5건 (2026-08-14)
- [x] TTS 미리듣기: engine_io.tts_sample(check-tts.js --text --keep 경유, ffplay 라인 파싱) +
      POST /api/tts/sample → audio/mpeg. edge 실합성 실측 20KB (2026-08-14. 04 문서의
      `--sample-text` 표기는 실제 CLI 의 `--text` 가 맞다)
- [x] 미디어 라이브러리 API: core/library.py + GET/POST /api/assets — 목록 = 폴더 스캔 ×
      CATALOG.md 표 파싱(출처·라이선스) × ffprobe 실측(길이·해상도) 조인 + scenes 기입값(ref)
      미리 계산. 받기 = fetch.js 경유(허용 호스트 검증 유지) + **라이선스 없으면 422** +
      CATALOG.md 표에 자동 한 줄 추가(정본 유지) — tests/test_library.py 5건 (2026-08-15)
- [x] web 화면 ①(강좌 설정 폼 — 목소리 프리셋+TTS 미리듣기·팔레트·BGM 선택+재생·If-Match
      저장·409 안내) ③(브랜드 킷 — palette 저장·간이 프리뷰) + ②의 [회차 생성] 버튼 +
      /api/assets/file 소재 서빙 — 브라우저 실측: 회차 생성→열기 전환·설정 저장 왕복·프리뷰
      즉시 반영 (2026-08-15. 실물 iframe 프리뷰·프리셋 갤러리는 3단계 preview.js 와 함께)
- [x] 신규 강좌 개설: scaffold_course + POST /api/courses (course.json 템플릿 + palette↔render
      동기화 + intro/stinger 카피 — 공용 _base.css 참조를 목적지 기준으로 재계산) + 대시보드
      [새 강좌] 위저드 + 보드 [+ 회차 추가](커리큘럼 밖 회차) — tests 2건 (2026-08-15)

### 3단계

```
3단계(대본 에디터)의 구현 계획을 세워라. 03_screens.md 의 ⑤ 화면 설계와
02_data-model.md 의 clip 스키마·검증 규칙 기준. 클립 에디터 → params 자동 폼 →
프리뷰 → 검수 자동화 순으로 나눠 단계별 완료 조건을 제시하라.
```

규모가 크므로 **계획 승인 후 구현**. 계획이 승인되면 이 파일에 세부 체크리스트를 추가하고 진행한다.

#### 3단계 구현 계획 (2026-08-15 수립 — 루프 상시 지시 "계속 구현하라"를 승인으로 갈음)

**3A. 클립 에디터 골격** (⑤ 좌·중 — scenes.json 구조화 편집)
- 클립 리스트(드래그 정렬=배열 순서·골격 위치 규약 경고)·추가(종류 선택→id 골격 관례 자동 제안)·삭제
- 내레이션 텍스트영역+글자수 뱃지, 예산 게이지(course.episodeLength 역산·실측/추정 라벨 구분)
- 저장 = 기존 PUT(If-Match) 재사용, `_` 보존
- **완료 조건**: 픽스처 회차를 화면에서 열어 수정·정렬·저장 후에도 빌드 성공·diff 최소

**3B. params 자동 폼 + 자산 피커** (결함 차단 4종 — 이 앱의 1원칙)
- inspect.js templateKeys → **받는 키만 폼 생성** (자유 키 입력 자체가 없음)
- 템플릿 피커(공용+회차 전용 갤러리·paramsKeys)·B롤 피커(라이브러리 조인 — `duration > 소스−videoStart` 즉시 빨강)
- 경로는 자산 참조→paths.py 기입·src 존재 검사·palette/fontUrl 자동 주입("상속 중" 뱃지, 수동 입력 불가)
- title 특수: [프레임 추출] 버튼 — videoStart 시각 프레임→bg/ 저장→src 자동 기입
- 발화시각 계산기: 구절 선택→글자수÷페이스(6.4자/초)→t1·t2 기입
- **완료 조건**: 틀린 params 키·깨진 경로·초과 B롤을 화면에서 만들 수 없음을 실측

**3C. 프리뷰 + 부분 TTS** (⑤ 우)
- engine/preview.js 신설(css/js 인라인 자체완결 문서·params 는 서빙 URL 질의로 — _params.js 가
  location.search 를 읽는 엔진 방식 그대로) + GET /api/templates(갤러리)·/api/templates/preview
- iframe 렌더 + 시간 스크럽(document.getAnimations currentTime 시킹 — 엔진 렌더 방식과 동일)
- 클립 음성: TTS 캐시 재생 + [이 클립만 TTS 갱신](--only tts 잡)
- **완료 조건**: 픽스처 클립 프리뷰가 브라우저에 뜨고 스크럽·params 반영이 동작

**3D. 구성표 ④ + 검수 ⑥ 완성 + 배포 ⑦**
- plan.md 표 라운드트립 편집기+예산 게이지+[대본으로 반영](행→클립 골격)
- 검수: 자막 대조(.srt↔대본 diff 0)·검수 체크리스트 기록(out/review.json)·직전 회차 타이틀 프레임 쌍
- 배포: deliverables API(제목·설명·챕터 chapters.js·srt·썸네일 후보) + ⑦ 화면·복사 버튼
- **완료 조건 = 3단계 수용 기준**: 새 회차 한 편을 코드·에디터 없이 화면만으로 완성

체크리스트:

- [x] 3A 클립 에디터 골격 — 리스트(▲▼ 정렬·골격 순서 경고·실측/추정 라벨)·추가(id 골격 관례
      자동 제안 chN/sNx/brollN)·삭제·내레이션+글자수·예산 게이지(course.episodeLength 역산 —
      픽스처 113% 초과가 빨강으로 실측됨)·저장(If-Match·`_` 보존 왕복) + GET /api/episodes/{id}/inspect.
      브라우저 실측 (2026-08-15. 드래그 정렬은 ▲▼ 버튼으로 대체 — 필요시 vuedraggable 후보)
- [x] 3B 결함 차단 4종 — 브라우저 실측 (2026-08-15):
      ① params 자동 폼(받는 키만 노출·자유 키 입력 없음·안 받는 키는 빨간 목록+[제거])
      ② 피커로만 선택(템플릿 갤러리·B롤 라이브러리) + 저장 시 경로 실존 검사(pathIssues —
      PUT 응답, src/fontUrl 까지) + [B롤 프레임 추출→src 기입] 버튼(POST bg-frame,
      videoStart↔프레임 일치를 한 버튼으로)
      ③ 자동 주입 키(brand·bg·fontUrl…)는 "강좌 상속 중" 뱃지만 — 폼 비노출
      ④ B롤 길이 즉시 검사(구간>소스−videoStart → 빨강, preflight 와 같은 문구)
      + 발화시각 계산기(구절 선택→글자수÷6.4→tN 키에 원클릭 기입)
- [x] 3C-엔진 preview.js + inspect.js --list-templates + /api/templates(·/preview) (2026-08-15)
- [x] 3C-화면 — ⑤ 3열 완성 (2026-08-15 브라우저 실측): iframe 프리뷰(preview.js 문서 + URL
      질의 params — 경로형 src/fontUrl 은 API 자산 URL 로 치환)·시간 스크럽(getAnimations
      currentTime 시킹, 1533ms 실측)·B롤 video 프리뷰·음성 캐시 재생(/api/media audio)·
      [TTS 실측 갱신](--only tts 잡 → 완료 시 실측 길이 재조회) + 회차 파일 서빙(/files)
- [x] 3D — 브라우저 실측 (2026-08-15):
      ④ plan.md 편집기(GET/PUT If-Match 라운드트립 — 표 구조 편집기·[대본으로 반영]은 후속 백로그)
      ⑥ 검수 완성: 자막 대조(.srt↔대본 공백무시 diff 0 실측 1,900자+·어긋나면 첫 지점 전후 표시)·
      검수 체크리스트(out/review.json GET/PUT — "봤다"의 기록)
      ⑦ 배포: deliverables API(제목 `[강좌명] n강 — 제목`·설명(promise+챕터+재생목록 자리)·
      챕터 chapters.js 실측(심링크 임시 루트로 구 배치 가정 우회)·srt 다운로드·썸네일 후보) +
      화면(전 항목 편집·복사·[youtube.md 저장]) — tests/test_deliverables.py 5건
- [x] 수용 기준 실측 (2026-08-15) — **hr-basics-02 를 코드·에디터 없이 화면만으로 완성**:
      보드 [회차 생성] → ⑤에서 B롤 피커·videoStart 초과 차단 실측·[프레임 추출→src]·
      템플릿 피커(stat/voicecard/cloud-layers)·내레이션 → 저장(경로 문제 0) → 빌드 done
      (46.2s mp4+srt) → ⑥ 프레임 5장·자막 diff 0·체크 기록 → ⑦ 제목·실측 챕터·youtube.md 저장.
      메모: 시나리오에서 ch1 의 params.title 입력을 생략해 "[챕터 제목]" 플레이스홀더가 챕터에
      남음 — 입력 자체는 3B 폼으로 가능(실측 완료). 저장 직후 B롤 검사 오탐(자산 목록 재조회
      레이스)은 로딩 중 중립 표시로 수정

### 4단계

```
4단계(에이전트)를 진행하라. docs/design/05_agent.md 의 A(초안)·B(도식)·C(평가) + 사용량 미터.
키 없으면 비활성 — 1~3단계 기능이 키 없이 전부 동작함을 재확인하라.
```

진행 체크리스트:

- [x] core/agents/runner.py — 3종(draft·diagram·review) 단발 세션, 05 실행 설계 그대로
      (settingSources=project 로 스킬 네이티브 로드·acceptEdits·maxTurns 120·금지 도구).
      query_fn 주입으로 SDK 없이 테스트 가능 (2026-08-15. claude-agent-sdk 0.2.138,
      optional-dependencies "agent" 그룹)
- [x] 잡 큐 통합 — kind=agent 잡(같은 SSE·취소·회차 직렬화=편집 잠금)
- [x] 키 게이트 — ANTHROPIC_API_KEY 없으면 /api/agent/* 403 + 화면 버튼 비활성(사유 툴팁).
      키 없이 나머지 전부 동작 = 스위트 70건이 키 없이 통과
- [x] API: GET /agent/status·/agent/usage(토큰·비용 적산 .cache/agent-usage.jsonl) +
      POST /agent/draft·diagram·review
- [x] 화면: ② [✨ AI 초안](미생성 회차는 스캐폴딩 후 제출) · 회차 [✨ AI 평가](잡 SSE 로그
      릴레이) · 작업 큐에 사용량 미터
- [x] **실 키 완주 검증 (2026-08-15)** — hr-basics-03(조직)으로 전 동선 실측, 총 $0.46:
      ① AI 초안(Haiku·26턴·$0.25) → plan/facts/scenes 생성. 초안 결함 4종(JSON 콤마·text 키·
      화면 누락·구 경로 B롤) 발생 — 전부 앱 검증기가 잡는 부류, 손질 후 preflight 이상 없음
      ② 빌드 done → 109.1s mp4+srt ③ AI 평가(Haiku·25턴·$0.21) → out/review-agent.json
      6항목 채점(overall 2.6 — 검증용 stat 카드 남발을 정확히 지적 = "글자 카드로 때우지
      않는다" 규약이 평가자에게 살아 있음). 사용량 미터에 모델·비용 적산 확인.
      모델 정책: 당분간 전부 Haiku(.env 오버라이드 유지 — 사용자 지시), Opus/Sonnet 은 명시
      지시 시. SDK 자식 프로세스 키 주입 보강(runner.py)

후속 백로그 (설계서 명시 항목 순차 처리):

- [x] ④ [대본으로 반영] — POST plan/apply: 구간 배분 표 파싱 → 없는 구간만 표 순서 자리에
      골격 클립 삽입(화면 칸 해석: 도식→motion/ 우선, B롤→엔진 assets 참조), 글자수 →
      `_목표글자수` 주석 필드, palette·fontUrl 자동 주입, 기존 클립 보존 — tests 2건 (2026-08-15)
- [x] 일관성 [강좌 값으로 맞추기] — POST sync-course (If-Match): voice 복사 + render 얹기 →
      대조 0건 실측, motion 보존 — tests 1건 (2026-08-15)
- [x] 검수 프레임 명암 자동 선별 — signalstats YAVG 한 패스 표본으로 밝은/어두운 지점 실측
      선별 + 타이틀은 클립 시작 시각(chapters 와 같은 누적 규칙, media_ops.clip_start_times)
      +1.2s + 모션(50%)·마지막(98%) = 4+1종에 kind 라벨 — tests 3건 (2026-08-15)
- [x] ⑥ 직전 회차 타이틀 프레임 쌍 — consistency 응답에 titlePair(직전 n-1 회차·이번 회차
      타이틀 프레임 url 쌍, 둘 다 빌드된 경우) + 검수 탭 나란히 표시. 1강은 쌍 없음 (2026-08-15)
- [x] 클립 리스트 드래그 정렬 — vuedraggable(≡ 핸들, ▲▼ 대체), 드래그→저장 왕복 브라우저
      실측 (2026-08-15)
- [x] 브랜드 킷 프리셋 갤러리(기본 1종) — copy_brand_kit 분리 + POST brandkit/apply
      (덮어쓰기 확인 모달·공용 참조 재계산) — tests 1건 (2026-08-15)
- [x] plan 표 구조 편집기 — ④ 표 편집/원문 토글: "구간 배분" 표만 구조화 편집(셀 수정·행
      추가/삭제·합계 행 보호)하고 나머지 문서는 보존, 예산 게이지 실시간(셀 수정 즉시 반영
      실측 2,763/1,850자) — 브라우저 실측 (2026-08-15)

~~백로그 소진~~ → **2026-08-21 사용자 결정: 5단계(데스크톱 전환) 착수.** 상용 트랙은 5단계 뒤.
- [ ] 상용 트랙 S1~S4 (06_roadmap — 5단계 완성 뒤 착수 판단. S1 시점에 엔진 포팅 재평가)

### 5단계 (데스크톱 전환 — 2026-08-21 착수 결정)

```
5단계를 진행하라. docs/design/07_desktop.md 가 정본 — 하위 단계 표(5-0~5-8)의 첫 미완
항목을 순서대로. 각 하위 단계의 수용 기준을 실측 검증하고 이 체크리스트를 갱신하라.
Python 은 conda penv3.13-video (.claude/memory/python-environment.md — 의존성 설치 상태 주의).
```

주의: 엔진 무수정 원칙 유지 (산출물 경로는 `--out`, 실행환경은 env.py 의 child_env 주입).
api/·web/ 는 삭제 완료 (api/=5-2 · web/=2026-08-21 D16 조기 삭제). 구 Vue 화면을 대조해야
하면 커밋 `a731a62` 에서 꺼낸다 — `git show a731a62:web/src/components/ClipEditor.vue`.

진행 체크리스트 (수용 기준 상세: 07 단계 표):

- [x] 5-0 위험 스파이크 (2026-08-21 — 3종 전부 실측 통과):
      ① 이식성 — 임시 폴더 사본 + PATH=runtime 3폴더(+System32)만 + PLAYWRIGHT_BROWSERS_PATH
      + `--out` 외부 지정으로 셀프테스트(mp4 2개) 및 **픽스처 풀빌드 292.766667s = 0단계
      기준(292.77s) 정확 일치**, 8s 프레임 눈검수 통과. 소재 3종(CATALOG 출처) 재다운로드 포함
      ② PySide6 6.11.2 — QWebEngineView 로드·URL 질의 params DOM 반영·getAnimations
      currentTime=2500ms 시킹 + Chromium 교차 스크린샷으로 타이틀 카드 시각 검증.
      발견 2건: conda 환경에서 Qt6Core DLL 충돌(→ python.org venv 사용, .claude/memory 기록)·
      프리뷰는 wipe 포함 전체 params 필요(흰 전환막)
      ③ edge-tts 셔틀 — PATH 1순위 해석으로 합성 확인 (자기완결 exe 빌드는 5-7)
- [x] 5-1 core/env.py + 결함 수정 (2026-08-21) — env.py(설치/데이터 분리·child_env)·
      engine_io(utf-8·CREATE_NO_WINDOW·--out·junction)·write_text newline 9곳·잡 보존 상한
      + **추가 발견 4건 수정**: 드라이브 교차 relpath(절대경로 폴백 — 구 저장소가 C:라 잠복)·
      워크트리 CRLF(.gitattributes eol=lf + 픽스처 정규화 + Document 원문 개행 보존)·
      jobs _set 상태/이벤트 레이스·indexer sqlite 연결 누수.
      **pytest 78건 전건 통과 (스킵 0 — out 캐시 이식으로 검수·배포 테스트까지 활성)**
- [x] 5-2 facade 추출 (2026-08-21) — (a) core/facade.py 신설(Studio + StudioError 예외
      위계 — 04 표 전량 이관, **preview 화이트리스트** 포함) (b) 라우터 8종 껍데기化 →
      기존 HTTP 테스트 78건 전건 통과로 **등가 증명** (c) 테스트 13종을 conftest(studio·
      fixtures_root·copy_root) + Studio 직호출로 재작성, 화이트리스트 회귀 테스트 추가
      (d) **api/ 삭제** + pyproject 정리(fastapi·uvicorn·sse-starlette·watchfiles·httpx 제거,
      wheel packages=core만) → **79건 전건 통과.** 파일 감시(watchfiles)의 역할은 5-3 의
      QFileSystemWatcher 가 승계 예정
- [x] 5-3 Qt 셸 + 읽기 콘솔 (2026-08-21) — app/(theme=D11 토큰 이식·bridge·MainWindow·
      대시보드·강좌 보드·회차 페이지 ⑤뷰어/⑥검수) + packaging/setup-qt-venv.ps1.
      **실측(스모크·실창 캡처)**: 대시보드→강좌→회차 탐색 · 클립 16행 · 검수 프레임 4+1종
      (kind 라벨·명암 실측 시각) · 무음 리포트 · mp4 소스 로드 · **실엔진 TTS 부분빌드 done**
      (진행 로그 릴레이·상태 칩·잡 칩 복귀 — 1단계 실측과 동일 방식).
      함정 2건 해결·기록: 클로저 시그널 연결=direct(워커에서 위젯 접근)·QRunnable autoDelete
      로 큐드 전달 유실 → **영속 디스패처(QObject) 경유로 확립** (bridge.py — 이후 전 화면 공통).
      offscreen 캡처는 한글 폰트 미로드(두부) — 자동화 캡처는 실창로, 잔여 육안 확인
      (mp4 소리·영상 실재생)은 사람 확인 항목
- [x] 5-4 편집 ①②③ + 스캐폴딩 + 새 강좌 위저드 (2026-08-21) — course_settings(목소리
      프리셋+TTS 실합성 미리듣기·팔레트 피커·BGM 콤보+듣기·etag 저장+일관성 배지)·
      brandkit(간이 프리뷰·프리셋 재적용 확인 모달)·보드 [회차 생성]/[+ 회차 추가]·
      새 강좌 위저드 + widgets(ColorButton·AudioPreview).
      **E2E 실측(스모크)**: 빈 루트 → 위저드 개설(qt-demo·BGM 목록 로드) → 회차 생성
      (qt-demo-01) → (대본은 파일 편집 — 2단계 방식) → **화면 전체 빌드 done → mp4+srt +
      verifying 자동 생성(프레임 5장)** → 타이틀 카드 프레임 눈검수(위저드 팔레트·워터마크
      상속 확인). ① 탭 실창 캡처: 픽스처 값 로드·인준 프리셋 자동 체크·TTS "재생 중" 실측.
      발견·수정 2건: repo engine/node_modules 미설치(전체 빌드에서 첫 노출 — npm install),
      입력 위젯 OS 다크 팔레트 상속(theme 기본 스타일 추가). 라운드트립 diff 0 은
      테스트(79건)가 계속 고정
- [x] 5-5 ⑤ 대본 에디터 + ④⑥⑦ (2026-08-22) — app/pages/{clip_editor,plan_tab,deploy_tab}.py
      신설 + episode.py 전면 개편 + app/bootstrap.py(QtWebEngine 기동 설정).
      **실측(스모크 전 구간 통과 · 실창 눈검수)**:
      ⑤ 3열 — 클립 16 드래그 리스트(실측 라벨)·예산 2,074/1,850자 **112% 빨강**·
      **결함 차단 4종**: ① 받는 키만 폼(progress·wipe 만 노출, brand/bg/fontUrl 은
      "강좌 상속 중" 뱃지) + 오타 키 `tterm` 주입 → 빨간 경고 1건 → [제거] → 0건
      ② 피커로만 선택 ③ 자동 주입 키 폼 비노출 ④ videoStart 18s → "구간 2.0s > 소스 0.9s
      — 마지막 1.1s 정지 프레임" 즉시 빨강(정상 시 "여유 13.9s ✓") · 발화시각 계산기
      (구절→3.12s) · **프리뷰 실물 렌더**(QWebEngineView 가 hook-bill 을 한글로 그림,
      anims 2, 스크럽 3.5s→currentTime 3500ms) · 음성 캐시 8.3s ·
      **연속 저장 2회 etag 왕복(409 교착 없음 — 구 웹 결함 회귀 방지)**
      ④ plan 16행 파싱·예산 99% · ⑥ 프레임 5장·자막 diff 0(1,565자)·체크리스트 기록·무음 0
      ⑦ 제목 `[인사 기본개념 강좌] 1강 — 구성원`·챕터 5·srt·썸네일 5·youtube.md 저장
      발견·수정 1건: **QtWebEngine 은 GPU 컨텍스트 실패 시 페이지를 아예 못 연다**
      (loadFinished=False). QApplication 이전 임포트 + `--disable-gpu` 폴백을 bootstrap 으로
      고정 — 담당자 PC GPU 사정이 제각각이라 설치본에도 필요.
      남긴 것: ④ 셀 단위 구조 편집(현재는 원문 편집 + 파싱 표 미리보기 + 예산 게이지)
- [x] 5-6 에이전트 이중 제공자 + 설정 화면 (2026-08-22) — core/agents/providers.py(제공자
      선택·모델 해석·키 게이트)·openai_runner.py(구조화 생성 + **파일 기입은 우리 코드**)·
      core/config.py(홈 공용 .env 병합 쓰기·자가진단) + app/pages/settings.py +
      ②[✨ AI 초안]·회차[✨ AI 평가] 배선.
      **실측(스모크 전 구간 통과 · 실창 눈검수)**:
      · 기본 claude·키 없음 → 비활성 + 사유. 화면에서 OpenAI 키 입력 + 제공자 전환 +
        테스트 모드 체크 → 저장 → **"사용 가능 ✓ · 모델 전부 gpt-4o-mini (테스트 모드 —
        최저가 강제)"**, 파일에 `AGENT_PROVIDER=openai`·`AGENT_TEST_MODE=1` 기록
      · AI 버튼 게이트: 키 있으면 활성(툴팁에 제공자·모델), **키를 지우면 다시 잠김**
      · 자가진단 9항목 전부 판정(Node v24·ffmpeg·ffprobe·Playwright·Chromium·데이터 폴더·키 3종)
      · openai 경로: 가짜 클라이언트로 draft → plan.md·facts.md·scenes.json 기입,
        내레이션·`_화면메모` 반영, **골격 밖 새 클립에도 palette 자동 주입**, `_경로메모` 보존
      · 키 마스킹(Password 에코)·저장 위치 표시·셸/저장소 우선 시 경고 문구
      **pytest 93건** (test_providers 6 + test_config 4 신설). 실키 완주는 사용자 판단
      (claude 경로는 4단계에서 이미 실키 완주 — openai 는 키 제공 시)
- [x] 5-7 설치본 🔄 (2026-08-22 — **동결본 실측 통과. 남은 것은 사용자 준비물 2종**)
      packaging/{VideoStudio.spec, collect-runtime.ps1, VideoStudio.iss, smoke-frozen.py} +
      app/{pages/first_run.py, smoke_probe.py}.
      **동결 환경**: conda `penv3.13-video` (pip 휠 PySide6 — 2026-08-22 재통일로 .qt-venv
      은퇴. PyInstaller 훅은 pip 휠 배치만 알며(실측 conda-forge 0 / pip 144 DLL), 깨끗한
      conda env 에선 pip 휠이 정상이라 개발·동결이 한 env 가 됐다)
      **동결본 스모크 PASS** (임시 폴더 사본 + **PATH=System32 만**으로 실행):
      기동(frozen=true)·강좌 1·클립 16·**템플릿 20(node subprocess 가 설치 배치에서 동작)**·
      **프리뷰 렌더**(anims 2·"김민준 신규 구성원…"·시킹 후 고유색 28)·**설치 폴더 쓰기 0건**
      발견·수정 3건:
      ① `.cache/index-*.sqlite` 가 설치 폴더로 샘 → indexer·agents USAGE_FILE 을
         `env.cache_dir()` 로 (5-1 에서 놓친 경로 — 스냅샷 검사가 잡았다)
      ② 스모크 판정이 느슨해 조기 통과(JS 응답만 확인) → URL 대기 + **시킹 후** 픽셀
         고유색>1 을 판정에 포함 (t=0 은 페이드인 전이라 단색이 정상)
      ③ **설치본에 스톡 소재가 들어감(R3 재배포 금지 위반)** → robocopy `/XD` 로 제외.
         headless shell 제거·Qt 자산 가지치기와 함께 1,586→**1,100MB**
      ⬜ 남은 것 (사용자 준비물): **깨끗한 Windows PC 설치 실측** · Inno Setup 컴파일(ISCC)
      첫 실행 위저드. 깨끗한 PC 실측
- [x] 5-8 배포 준비 🔄 (2026-08-22 — **서명 외 전부 완료. 남은 것은 인증서**)
      · **라이선스 고지**: `packaging/NOTICE.md`(구성요소 8종 표 + LGPL 교체권·소스 제공 안내
        + 소재 미동봉·edge TTS 약관 고지) + `collect-licenses.ps1`.
        **전문 10종 실제 동봉 확인** — LGPL-3.0·GPL-3.0·LGPL-2.1·ffmpeg·node·playwright·
        Pretendard·pydantic·edge-tts·chromium. 발견: **PySide6 휠에 LGPL 전문이 없고**
        (상용 참조만) Playwright Chromium 에도 라이선스 파일이 0개 → 정본(gnu.org·chromium
        저장소)에서 받아 캐시. **누락 시 빌드 실패**로 막음 (고지 없는 배포 사고 방지)
      · **사용 안내**: `packaging/사용안내.md` — 담당자용(설치·첫 실행 4단계·영상 한 편
        만들기 6단계·문제 해결 표·업데이트/제거). 설치기가 시작 메뉴에 바로가기로 건다
      · **업데이트 경로**: 새 Setup 덮어쓰기 — 데이터 폴더가 분리돼 작업 파일 보존.
        제거 시 데이터 폴더는 남고 받아 둔 소재만 사라짐(재다운로드 가능)
      · **`build-installer.ps1`** — 동결→런타임→라이선스→**스모크→설치기** 한 명령.
        스모크 실패면 설치기를 만들지 않는다. ISCC 없으면 그 단계만 건너뛰고 안내
      · 설치기: `InfoBeforeFile=NOTICE.md`(LGPL prominent notice) + SignTool 절 주석으로 예약
      발견·수정 1건: 신규 ps1 3종의 **BOM 누락으로 한글이 깨져 파서 오류** — BOM+CRLF 부여
        (3c 가 경고한 함정을 그대로 밟음. 08 §9 규칙이 맞았다)
      ⬜ 남은 것 (사용자 준비물): **코드 서명 인증서** (없으면 SmartScreen 차단)

## 완료 기록

| 날짜 | 단계 | 내용 |
|---|---|---|
| 2026-08-23 | I-2 구현 | **앱 화면 녹화를 제품 기능으로** (사용자 지시: "프로그램을 통해 외부 화면을 캡쳐하고 영상을 제작하라"). 엔진은 처음부터 할 수 있었는데 앱에서 도달할 길이 없었다 — 그 길을 냈다. **신규 `engine/probe.js`**(앱 전용 4호): 대상 앱을 열어 조작 가능한 요소를 훑고(글자·Playwright selector·**네이티브 CSS 경로**), 로그인 세션을 `storageState` 로 저장한다. **위저드에 "앱 주소"·로그인 칸** → `course.capture` → 스캐폴딩이 녹화 씬을 살리고 `baseUrl` 기입. **AI 는 훑어 온 목록에서만 셀렉터를 고르고**(지어내면 조용히 건너뛴다) 액션 변환은 결정적. **비밀번호는 어디에도 안 남는다** — 대본엔 `.env` 이름만, 세션은 빌드 직전에 새로 딴다. 실측 결함 3종 수정: `highlight` 가 `:has-text()` 로 빌드를 죽임(네이티브 CSS 로 번역+optional) · SPA 타이밍 때문에 성공한 로그인을 실패로 판정(경로 방문 뒤 최종 판정) · 스크롤 "3"이 3px 이 되어 정지 화면(화면 단위로 해석). **결과**: 앱에서 만든 인사잇 HR 홍보 92.7초 — 로그인된 대시보드·인사기본 7종 메뉴가 실제로 찍혔다. pytest 183 |
| 2026-08-23 | D18 실측3 | **AI 도식의 색이 프로젝트와 어긋나던 근본 원인 3종 수정** (사용자 지적: "배경과 컬러가 왜 일관성이 없는가"). **하이쿠 탓이 아니라 프롬프트 결함이었다.** ⓐ `skill_prompts.DIAGRAM_SECTIONS` 가 authoring.md "모션그래픽 구간"을 deep=False 로 떠서 **바로 다음 소절 "한 영상에서만 쓰는 전용 도식"이 통째로 빠졌다** — 공용 `_base.css` 참조 규칙이 거기 있었다. 모델이 `../_base.css` 를 지어냈고, 스킬이 경고한 그대로 "스타일 없는 맨 HTML 이 조용히 찍힌다"가 실현돼 브랜드 변수(--bg·--brand)가 하나도 안 걸렸다 → 모델 자기 색(보라·분홍 그라디언트)만 남았다. ⓑ 역할 선언이 "같은 폴더 상대경로로 참조한다"라고 **틀린 안내**를 하고 있었다(정답은 배치가 정한다 — 스킬 예시 `../../motion/`, 이 저장소 `../../../../engine/motion/`). → 공용 링크를 `_fix_shared_links` 가 `paths.compute` 로 **우리가 기입**한다(PATH_PARAMS 와 같은 원칙 — 경로는 모델이 안 쓴다). ⓒ 팔레트를 프롬프트에 넣은 적이 없었다 → `diagram_rules(palette)` 로 전달 + "색은 직접 정하지 마라, var(--bg)·var(--brand) 를 써라" 규칙 추가. **실측 대조**(금리 s1 도식 재생성): 흰 배경+보라/분홍/청록 무지개 → **어두운 남색 배경(#0B1220)+브랜드 파랑 계열**(#A9C6FF=brandSoft 그대로). 공용 링크 2종 실재 확인. pytest 177(+2). 남은 것: 모델이 var() 대신 팔레트 파생 리터럴을 쓰는 경향 (색은 맞아 시각적 일관성은 확보) |
| 2026-08-23 | D18 실측2 | **영상 3편 화면 실측 + AI 경로 결함 4종 수정** (사용자 지시: 다른 방식·인사잇 홍보·교육영상). 만든 것: ① 온보딩 홍보 17.0s — 라이브러리에서 Pexels 사진 받기·초록 팔레트·인준(남) 목소리·photo.html 켄번즈 ② 인사잇 HR 홍보 10.9s — 실서비스(white.insait.com)를 열어 실제 메뉴 7종을 근거로 대본(파랑=브랜드색) ③ 교육 '금리란?' 65.0s — 강의 골격 9클립·AI 도식 4장(렌더 확인 3통과/1수정)·평가 4.2. **결함 4종**: ⓐ 분량 초과(10초 요청에 110자 → 15.4s) → 예산 초과를 되먹임 항목에 추가(BUDGET_SLACK 1.25) → 72자/10.9s ⓑ B롤 미선택으로 빌드가 결함 차단에 막힘(나머지는 다 채워 놓고) → 되먹임 + 그래도 비면 임시 선택 후 고지 ⓒ **모델이 경로형 param 을 지어냄** — title.src 에 `bg/<회차>-frame.jpg` (기준 html 에서는 없는 경로 → 조용히 빈 배경). PATH_PARAMS(src·fontUrl)를 모델 기입에서 제외 → _title_bg 가 실물 프레임을 뽑아 정확한 상대경로 기입 ⓓ 되먹임 뒤에도 남은 내레이션 자리표시자 → 지어내지 않고 비우고 고지(TTS 가 대괄호를 읽거나 빌드가 막히는 것 방지). pytest 175(+6). 하네스 쪽 결함 1건도 발견(자동 빌드가 로그를 지워 완료 판정이 어긋남 — 앱은 정상) |
| 2026-08-23 | D18 실측 | **화면 실측 완주 + 결함 2종 발견·수정.** 실창에서 [새 영상 만들기](위저드 모달) → [AI 로 대본 쓰기](모달) → 자동 빌드 → [AI 평가] 를 끝까지 구동(실키·haiku, 캡처 8장). **① AI 가 무음 영상을 만들었다** — 단발 골격은 내레이션이 최상위 scenes(앱 녹화)에 있어 카드에 `narration` 키가 없는데, 러너가 그 키를 '말하지 않는 구간'으로 읽어 비워 뒀다(사람은 ⑤ 에디터에서 칠 수 있는 자리다). → 골격에 말할 자리가 하나도 없으면 카드에 내레이션을 달도록(`_may_speak`, 병합 전 1회 확정). **② 클립 5개 중 4개가 조용히 사라졌다** — `compose.js` 는 `before` 가 가리키는 씬이 없으면 클립을 오류 없이 버리는데, 단발은 녹화 씬을 걷어내면서 `before:"s1"` 을 그대로 뒀다. **AI 와 무관한 스캐폴딩 결함**(사람이 써도 같았다) → `_trim_clips` 가 남은 클립을 전부 `"end"` 로 옮긴다. 02_data-model 에 `before` 함정 기록. **실측 대조**: 3.2초·무음·카드 1장 → **17.8초·내레이션 133자·클립 3장·자막 3구간**, AI 평가 3.2 → 4.0. pytest 169(+4 회귀). 동결 스모크에 'AI 규약 발췌' 판정 추가 |
| 2026-08-23 | D18 | **에이전트 전면 HTTP 전환 (사용자 지시: "API 키 하나로 독립적으로 도는 앱").** claude-agent-sdk·CLI 의존 제거 → `anthropic`/`openai` 순수 HTTP 구조화 생성으로 대칭 이중화. 신설: skill_prompts(스킬 규약 절 발췌 조립 — 제목 표류는 테스트가 잡음)·llm(제공자 중립 complete — json_schema·vision·프롬프트 캐시)·engine/snapshot.js(정지 프레임 캡처, 신설 예외 3호). runner 전면 개편: 초안=구성표→내레이션 2단계+검증 되먹임 1회+자리표시자 file 클립 도식 연쇄+타이틀 bg 프레임 추출, 도식=렌더 프레임 vision 확인 루프, 평가=프레임 채점(전 제공자). openai_runner 삭제(흡수). 근거 문서는 경로가 아니라 **내용**을 전달(기존 결함 수정). 자가진단 "AI 규약(스킬)" 행, collect-runtime 6단계(스킬 md 동봉·누락 시 실패), 잡 큐 미터 토큰 표시. 설계서 6종 갱신(00 D18·01 예외/비교표 주석·05 전면 개정·07·CLAUDE·TODO). pytest 165(+17 — 오케스트레이션 전체를 llm 주입으로 검증) · **실키 실측**: claude HTTP 구조화 응답 OK(하이쿠, 토큰 166+9). 남은 실측: 실키 초안→빌드→평가 완주([docs/TODO-agent-http.md](TODO-agent-http.md)) |
| 2026-08-21 | 정리 | **잔재 일괄 삭제 (사용자 지시).** `web/`(Vue 29파일·1,595줄 — D16 으로 5-5 앞당김) · `projects/` 검증 잔재(bread-basics·bread-basics-01·test) · `core/events.py`(SSE 전용 EventBus — 소비자 소멸, Qt 는 JobQueue.listener→Signal 직결)와 그 테스트 · `web/dist`·`engine/out/qt-demo-01`·`.cache/*.sqlite`·`__pycache__` 파생물. 참조 문서 8종 갱신(D11 토큰 정본 → `app/theme.py`, D16 신설). pytest 78건 전건 통과 |
| 2026-08-14 | — | 저장소 이행 완료 (설계서·엔진·스킬·픽스처). BUILD_LOOP.md 작성, 0단계 착수 |
| 2026-08-14 | 0 | **수용 기준 충족.** 셀프테스트 mp4 2개 · inspect.js 신설 · 픽스처 경로 이전 후 hr-basics-01 재현 빌드(292.77s, 4:53 — 허용 4:40~5:20 내) · Python 골격(conda penv3.13-video, pytest 11건). 실측 반영: 02 경로 표를 현행 엔진 기준으로 교체(bgm·video=엔진 루트, 모션 file=대본 폴더), 자막 폰트는 시스템 폰트 제약 확인 — subtitleFont 지정 제거·R2 는 상용 트랙으로. 픽스처 실결함 1건(billing.html 미수용 tterm param) preflight 로 검출·제거 |
| 2026-08-14 | 1(선행) | core/jobs.py 잡 큐 + 테스트 4건 (0단계 빌드 대기 중 착수) |
| 2026-08-15 | 2 | **수용 기준 충족.** paths.py(실측 5행+역산) · Document(diff 0) · 저장 API(If-Match/409+현재본) · 회차 스캐폴딩(일관성 0건) · 강좌 개설(템플릿+참조 재계산) · TTS 미리듣기(edge 실측) · 라이브러리(CATALOG 정본 파싱/추가·라이선스 필수) · web ①②③. **E2E 실측**: 빈 루트에서 위저드 개설(demo-course) → 보드 회차 추가 → 파일로 대본 편집 → 화면 빌드 done → 15s mp4·프레임 5장·타이틀 카드 눈검수(파랑 팔레트 정상). pytest 59건 |
| 2026-08-22 | 5-7·5-8 | **설치본 파이프라인 완성 — 준비물 대기.** 동결 환경=pip 휠 venv 확정(conda 는 Qt 자산 미포함), 동결본 스모크 PASS(PATH=System32·설치 폴더 쓰기 0건·프리뷰 고유색 28), 라이선스 10종 동봉(휠에 LGPL 전문이 없어 정본에서 수집·누락 시 빌드 실패), 담당자 사용 안내, build-installer.ps1 한 명령. 결함 4건 수정(캐시 누수·조기 통과 판정·**스톡 소재 동봉(R3 위반)**·ps1 BOM). 용량 1,586→1,291MB. 남은 것: 깨끗한 PC·ISCC·서명 인증서 |
| 2026-08-22 | env | **환경 재통일 — conda `penv3.13-video` 하나, 전부 pip** (사용자 지시: insait 와 분리). 깨끗한 env 를 만들어 보니 pip 휠 PySide6 가 정상 — 8-21 의 WinError 127 은 conda 자체가 아니라 **insait env 의 DLL 오염**이었다(libffi 3.7 승격이 ctypes 까지 깨뜨림). pip 휠이면 PyInstaller 훅도 정상이라 **`.qt-venv` 은퇴** — 개발·pytest·캡처·동결이 한 env. 부수 효과: 새 env 에 conda ffmpeg 가 없어 시스템 ffmpeg(libass 있음)가 잡힘 — 개발 빌드의 합성 실패도 자연 해소. insait 는 우리가 넣은 것(pyside6·qt6-*·claude-agent-sdk) 제거로 원상 복구(단 ffi.dll 사본은 ctypes 복구라 유지) |
| 2026-08-22 | 5-7 | **자가진단이 거짓말하던 지점 하나.** ffmpeg 가 PATH 에 있는지만 보고 OK 라고 했는데, **conda-forge ffmpeg 9.0.1 에는 `ass` 필터(libass)가 없다** — 존재 검사는 통과하고 빌드는 `[3] 합성` 에서 `No option name near '<회차>.ass'` 로 죽는다. 개발 환경에서 앱의 [빌드] 가 깨져 있었고 아무도 몰랐다(직접 `node build.js` 를 돌리면 시스템 ffmpeg 가 잡혀 성공하므로 가려졌다). **설치본 동봉본(7.1 full)에는 있어 배포본은 무사하다.** 자가진단에 "ffmpeg 자막" 행 추가 + 테스트 4건 |
| 2026-08-22 | 5-7 | **설치본 용량 1,291→1,100MB (−191MB).** `excludes=` 가 파이썬 바인딩만 막고 **DLL·qml·리소스는 그대로 수집**되고 있었다 — WebEngine 디버그 pak 72MB·전 언어 locales 44MB·안 쓰는 모듈 DLL 45MB·전 언어 qm 9MB. spec 에 `_prune()` 추가, **동결 스모크 PASS 로 판정**(프리뷰 로드·픽셀). 프리뷰 고유색 28→17 은 가지치기가 아니라 09 의 16:9 고정 때문 — 가지치기 없는 conda 트리에서도 17 로 대조 확인. 덤: `collect-runtime.ps1` 이 자기 머리말 규칙(네이티브 종료코드로 판정)을 두 곳에서 어겨 **깨끗한 재빌드에서만 터지던 잠복 결함** 수정 |
| 2026-08-22 | 5-6 | **에이전트 이중 제공자 + 설정 화면.** providers(제공자·모델·키 게이트)·openai_runner(구조화 생성+결정적 파일 기입)·config(홈 .env 병합·자가진단 9항목)·설정 화면. 화면에서 openai 전환+테스트 모드 → 최저가 강제 실측, 키 넣고 빼며 AI 버튼 게이트 실측. pytest 93건 |
| 2026-08-22 | 5-5 | **⑤ 대본 에디터 + ④⑥⑦ — 3단계 등가 실측.** 결함 차단 4종 전부 화면 상태로 검증(받는 키만·오타 키 경고·상속 뱃지·B롤 초과 빨강), 프리뷰 실물 렌더+스크럽 시킹, 연속 저장 etag 왕복. QtWebEngine GPU 폴백을 bootstrap 으로 고정 |
| 2026-08-21 | 5-4 | **편집 ①②③ + 위저드 — 2단계 등가 실측** (빈 루트 위저드 개설→회차 생성→화면 전체 빌드 done→mp4·타이틀 카드 눈검수. TTS 실합성 미리듣기 "재생 중" 실측). **파이썬 conda 통일**(사용자 지시): pip 휠 대신 conda-forge pyside6+qt6-webengine+qt6-multimedia — 앱 스모크 conda 로 통과, .qt-venv 폐기(패키징 후보로만), run.ps1/README/메모리 갱신 |
| 2026-08-21 | 5-3 | **Qt 셸 + 읽기 콘솔 — 1단계 등가 실측.** app/ 신설(D11 토큰 스타일시트·영속 디스패처 브리지·대시보드/보드/회차 ⑤⑥), 실엔진 TTS 빌드 화면 완주(로그·칩), 검수 프레임 4+1·무음·mp4 로드. Qt 스레딩 함정 2건(direct 클로저·autoDelete 유실) 해결책 확립. 실창 캡처 눈검수 통과 |
| 2026-08-21 | 5-2 | **facade 추출 완료 — HTTP 계층 소멸.** Studio(04 계약 전량)+예외 위계, 라우터 껍데기化로 등가 증명(78건) 후 테스트 13종 facade 직호출 전환·api/ 삭제·의존성 정리. 최종 79건 전건 통과. preview 임의 경로 읽기 결함은 화이트리스트+회귀 테스트로 봉쇄 |
| 2026-08-21 | 5-0·5-1 | **스파이크 3종 통과 + env 계층·결함 10종 수정.** 이식 빌드 292.766667s 정확 재현(제한 PATH·번들 런타임·외부 --out) · PySide6 프리뷰 시킹 검증(conda 충돌 → python.org venv) · edge-tts 셔틀 해석 확인. env.py 신설, 07 결함 6종 + 추가 발견 4종(크로스드라이브 relpath·CRLF 워크트리·jobs 레이스·sqlite 누수) 수정. pytest 78건 전건 통과(스킵 0) |
| 2026-08-21 | 5(설계) | **데스크톱 전환 결정·설계 완료** (D12~D15). 07_desktop.md 신설 + 00·01·03·04·05·06·README 정합 수정. 사전 실측: 엔진 `--out`/`--video-root` 지원·ffmpeg 맨이름 호출·edge-tts=Python 확인, Azure 키 실합성 OK·Eleven 키 인증 OK(user_read 권한만 결핍), 저장소 .env 7키 로드 확인. 코드리뷰 결함 6종은 5-1 에 편입. 화면 도식 아티팩트 승인 |
| 2026-08-14 | 1 | **수용 기준 충족.** core(jobs 취소·verifying / indexer SQLite 캐시 / events 버스 / status·media_ops) + api(조회·build·잡 SSE·전역 SSE·media·검수) + web(대시보드·보드·대본 뷰어·빌드+SSE 로그·프레임 그리드·mp4). pytest 26건. 브라우저 실측: 대시보드→보드→회차 화면에서 TTS 부분빌드 완주(전체 빌드는 같은 경로 — API 로 0단계에 기실측)·프레임 5장·mp4 재생. 의도 검증 완료: 데이터 모델·stdout 파서·SSE 전부 실동작 |

## 알려진 결손·리스크 메모 (착수 전 확인)

- 픽스처 대본의 bgm·broll·fontUrl 이 구(h5-saas) 상대경로 — 0-3 에서 이전.
- `engine/assets/broll/office-talk.mp4` 없음 — CATALOG.md 출처에서 재다운로드.
- 자막 기본 폰트 "Malgun Gothic" → Pretendard 교체는 0단계에서 engine/fonts 동봉과 함께 (R2).
- 엔진은 무수정 원칙 — 신규 파일은 inspect.js·preview.js·snapshot.js 만 허용 (01_architecture).
