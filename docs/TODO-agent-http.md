# 에이전트 전면 HTTP 전환 — 작업 목록 (2026-08-23)

> **결정 D18 (2026-08-23 확정 — 00_overview 결정 표)**: 에이전트 3종(초안·도식·평가)을 **순수 HTTP 구조화 생성**으로 전면 교체한다.
> Claude Code CLI·claude-agent-sdk 의존을 제거하고, OpenAI 키든 Anthropic 키든 **키 하나만으로**
> 독립 동작한다. 스킬 문서(.claude/skills)는 앱을 만들기 위한 규약 정본이었으므로, 이제 앱이
> **규약 절을 발췌해 시스템 프롬프트로 조립**한다 (전문 복사 아님 — 절차 부분은 앱이 이미 수행).
> 품질은 에이전틱 대신 **검증 재생성 루프**(초안: validate.py)와 **렌더 확인 루프**(도식: 프레임
> 캡처를 이미지로 되먹임)로 확보한다. 파일 기입은 전 제공자 공통 **결정적**(우리 코드).

체크가 끝나면 표시한다. 순서는 위→아래.

## 1. 설계서 (코드보다 먼저)

- [x] `00_overview.md` — 확정 결정 표에 **D18 신설** (순수 HTTP 전환·CLI 제거·스킬 발췌 주입),
      D15 행에 "구현은 D18 로 대체" 이력 주석
- [x] `05_agent.md` — **전면 개정**: 단일 HTTP 러너 구조(제공자 대칭), 스킬 규약 발췌 조립표,
      초안 2단계(구성표→내레이션)+검증 루프, 도식 렌더 확인 루프, 평가(프레임 vision).
      CLI·settingSources·acceptEdits 서술 전부 제거
- [x] `01_architecture.md` — engine 신설 파일 예외에 `snapshot.js` 추가 (inspect·preview 와 같은 조항)
- [x] `07_desktop.md` — 에이전트 절 갱신 (CLI 불요·스킬 md 동봉·anthropic 패키지), 런타임 번들 표에 스킬 행
- [x] `CLAUDE.md` — 확정 결정 요약의 에이전트 행 갱신

## 2. 코드 — core/agents

- [x] `skill_prompts.py` **신설** — 스킬 md 에서 제목(heading) 단위로 규약 절을 발췌·조립.
      작업종(draft·diagram·review)×프로젝트 종류(시리즈/단발)별 절 목록을 코드에 선언,
      발췌 실패(제목 개명 등)는 즉시 오류 → 테스트가 표류를 잡는다. 평가는 `agents/reviewer.md` 전문
- [x] `llm.py` **신설** — 제공자 중립 `complete(system, user, json_schema=None, images=None)`
      → (파싱 결과, usage). claude=`anthropic` 패키지(`output_config.format`=json_schema,
      system 블록 `cache_control` 로 규약 캐싱, base64 이미지), openai=기존 `_structured` 이식.
      클라이언트 주입으로 키 없이 테스트
- [x] `runner.py` **전면 개편** — 세 작업의 오케스트레이션(제공자 공통):
      - draft: ① 구성표·근거(산문 중심) → ② 클립 내레이션(구조화, 같은 system 재사용=캐시 적중)
        → 결정적 기입(`_apply_draft` 이식) → `validate.draft_defects`+`consistency` 검증 →
        결함을 사람 말로 되먹여 **1회 재생성** → 잔여 결함은 로그로 보고(빌드 제출 차단이 최종 방어선).
        근거 문서(sourceDocs)는 **경로가 아니라 내용**을 읽어 전달 (기존 결함 수정)
      - diagram: 생성·기입 → `engine_io.snapshot()` 으로 중간 시각 프레임 캡처 → 이미지를 되먹여
        "의도대로인가" 확인, 아니면 수정본 재기입 (1회). 캡처 불가 환경이면 확인 생략+로그
      - review: 검수 프레임 4+1장 vision 채점 (기존 openai 경로 이식 — 이제 양 제공자)
      - `make_agent_work(..., llm_call=주입)` 로 테스트. 이벤트·usage 계약(잡 큐)은 불변
- [x] `openai_runner.py` **삭제** — 구조화 생성·기입 로직은 llm/runner 로 흡수
- [x] `providers.py` — 게이트(키만 검사)는 **그대로가 정답이 됨**. 주석·문서화만 갱신
- [x] `config.diagnose()` — "AI 규약(스킬 문서)" 행 추가 (동봉 누락 감지)

## 3. 코드 — engine (기존 파일 무수정)

- [x] `engine/snapshot.js` **신설** — 모션 html 1장을 지정 시각으로 시킹해 png 1장 캡처
      (motion.js 의 getAnimations 시킹·chromium 기동 방식 재사용, lib 만 import)
- [x] `core/engine_io.py` — `snapshot(file, project_dir, out_png, at_sec, params)` 헬퍼

## 4. 의존성·패키징

- [x] `pyproject.toml` — `agent = ["anthropic>=…"]` 로 교체 (claude-agent-sdk 제거), agent-openai 유지
- [x] conda `penv3.13-video` 에 `anthropic` pip 설치 (claude-agent-sdk 는 제거)
- [x] `packaging/collect-runtime.ps1` — 6단계 신설: `.claude/skills` 를 dist 에 복사
      (assets 미디어·예제 jpg 제외 — R3 재배포 금지 준수)
- [x] `packaging/VideoStudio.spec` — hiddenimports 에 `anthropic`·`core.agents.llm`·
      `core.agents.skill_prompts` (openai_runner 항목 제거)

## 5. 테스트

- [x] `tests/test_skill_prompts.py` **신설** — 선언된 절 전부 발췌 성공(제목 표류 감지)·
      시리즈/단발 조립 차이·reviewer 전문 포함
- [x] `tests/test_agents.py` **재작성** — query_fn 주입 → llm_call 주입.
      초안: 가짜 응답 → plan/facts/scenes 기입·검증 루프(1회차 결함→2회차 통과) 실측.
      게이트·잡 큐 통합·usage 미터·unknown kind 는 의도 유지
- [x] `tests/test_providers.py` — 무변경 통과 확인
- [x] 전체 pytest 전건 통과

## 6. 마무리

- [x] `docs/BUILD_LOOP.md` 완료 기록 행 추가
- [x] 실측 완주 (2026-08-23): **화면에서** [새 영상 만들기]→[AI 로 대본 쓰기]→자동 빌드→[AI 평가]
      (실키·haiku). 헤드리스로 강좌 초안도 별도 완주 — **도식 렌더 확인 루프 실동작 확인**
      (4장 중 2장이 렌더를 보고 수정 재기입, 호출 10회 / 토큰 10,303+20,316).
      결함 2종 발견·수정: 단발 무음 영상 · `before` 고아 클립 (BUILD_LOOP 참조)
- [x] 동결 스모크에 스킬 동봉 확인 — 프로브가 `skill_prompts.health()` 로 **발췌까지** 검사하고
      (파일만 있고 제목이 어긋나도 잡힌다) 판정 조건에 편입. collect-runtime 은 누락 시 빌드 실패

## 범위 밖 (이번에 안 함)

- openai 기본 모델 상향 (설정 화면에서 지정하는 현행 전제 유지 — 문서에 권장만 명시)
- CLI 경로 부활·동봉 (D18 로 종결)
- 상용 모드 워커 분리 (05_agent 상용 절 그대로)
