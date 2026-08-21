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
      + api/main.py + pytest 7건 통과 (conda `penv3.13-insait`)
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

**백로그 소진 — SSOT 상 남은 항목은 "4단계 실키 완주 검증"(키 제공 대기) 뿐.**
이후 루프는 매 반복 키 확인만 하며, 다음 갈래는 사용자 결정 사항: ① 키 제공 → 4단계 마감
② 상용 트랙 S1~S4 착수 지시 ③ 루프 중지.
- [ ] 상용 트랙 S1~S4 (06_roadmap — 4단계 실키 검증 뒤 착수 판단)

## 완료 기록

| 날짜 | 단계 | 내용 |
|---|---|---|
| 2026-08-14 | — | 저장소 이행 완료 (설계서·엔진·스킬·픽스처). BUILD_LOOP.md 작성, 0단계 착수 |
| 2026-08-14 | 0 | **수용 기준 충족.** 셀프테스트 mp4 2개 · inspect.js 신설 · 픽스처 경로 이전 후 hr-basics-01 재현 빌드(292.77s, 4:53 — 허용 4:40~5:20 내) · Python 골격(conda penv3.13-insait, pytest 11건). 실측 반영: 02 경로 표를 현행 엔진 기준으로 교체(bgm·video=엔진 루트, 모션 file=대본 폴더), 자막 폰트는 시스템 폰트 제약 확인 — subtitleFont 지정 제거·R2 는 상용 트랙으로. 픽스처 실결함 1건(billing.html 미수용 tterm param) preflight 로 검출·제거 |
| 2026-08-14 | 1(선행) | core/jobs.py 잡 큐 + 테스트 4건 (0단계 빌드 대기 중 착수) |
| 2026-08-15 | 2 | **수용 기준 충족.** paths.py(실측 5행+역산) · Document(diff 0) · 저장 API(If-Match/409+현재본) · 회차 스캐폴딩(일관성 0건) · 강좌 개설(템플릿+참조 재계산) · TTS 미리듣기(edge 실측) · 라이브러리(CATALOG 정본 파싱/추가·라이선스 필수) · web ①②③. **E2E 실측**: 빈 루트에서 위저드 개설(demo-course) → 보드 회차 추가 → 파일로 대본 편집 → 화면 빌드 done → 15s mp4·프레임 5장·타이틀 카드 눈검수(파랑 팔레트 정상). pytest 59건 |
| 2026-08-14 | 1 | **수용 기준 충족.** core(jobs 취소·verifying / indexer SQLite 캐시 / events 버스 / status·media_ops) + api(조회·build·잡 SSE·전역 SSE·media·검수) + web(대시보드·보드·대본 뷰어·빌드+SSE 로그·프레임 그리드·mp4). pytest 26건. 브라우저 실측: 대시보드→보드→회차 화면에서 TTS 부분빌드 완주(전체 빌드는 같은 경로 — API 로 0단계에 기실측)·프레임 5장·mp4 재생. 의도 검증 완료: 데이터 모델·stdout 파서·SSE 전부 실동작 |

## 알려진 결손·리스크 메모 (착수 전 확인)

- 픽스처 대본의 bgm·broll·fontUrl 이 구(h5-saas) 상대경로 — 0-3 에서 이전.
- `engine/assets/broll/office-talk.mp4` 없음 — CATALOG.md 출처에서 재다운로드.
- 자막 기본 폰트 "Malgun Gothic" → Pretendard 교체는 0단계에서 engine/fonts 동봉과 함께 (R2).
- 엔진은 무수정 원칙 — 신규 파일은 inspect.js·preview.js 만 허용 (01_architecture).
