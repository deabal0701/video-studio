# 01 — 아키텍처

> **2026-08-21 데스크톱 전환 (D12·D13 — [07_desktop.md](07_desktop.md)):** web(Vue)+api(FastAPI)
> 두 층을 `app/`(PySide6) 한 층으로 교체한다. 아래 구조도는 전환 후 목표 상태이고,
> 전환 전 웹 구조·제거 일정은 07 문서가 정본이다. core 이하는 변하지 않는다.

## 전체 구조 — 3층 + 파일 SSOT

```
┌─ app/  PySide6 데스크톱 (단일 프로세스) ──────────────────────┐
│  강좌 설정 · 커리큘럼 · 대본 에디터 · 빌드/검수 · 배포 산출물     │
│  + 첫 실행 위저드 · 설정(키·진단) — qtbridge 가 잡 이벤트 릴레이  │
└──────────────┬───────────────────────────────────────────────┘
               │ 직접 호출 (HTTP 없음 — facade 유스케이스)
┌─ core/  Python — 로직 전부 (UI 무관, 단독 테스트 가능) ────────┐
│  env        설치/데이터 폴더·자식 프로세스 실행환경 (07 — 신설)  │
│  facade     화면이 부르는 유스케이스 (구 api 라우터 로직 이관)   │
│  paths      상대경로 계산기 (기준 5종 — 02 문서)                │
│  schema     course/scenes 모델 (pydantic) + 직렬화              │
│  validate   글자수 예산 · 일관성 대조 · params/경로 검사         │
│  indexer    projects/ 스캔 → 강좌·회차 목록 (SQLite 캐시)       │
│  jobs       빌드 잡 큐 · 동시성 정책 · 진행 이벤트               │
│  engine_io  Node CLI 호출 계약 (subprocess · stdout 파싱)       │
│  agents     에이전트 러너 — Claude/OpenAI 이중 (D15)            │
└──────────────┬───────────────────────────────────────────────┘
               │ subprocess (설치본은 번들 runtime/ 의 node·ffmpeg)
┌─ engine/  Node CLI (vendored — 수정 금지) ────────────────────┐
│  build.js · check-tts.js · chapters.js · inspect.js · preview.js│
│  lib/ (tts·record·motion·overlay·compose·preflight·…)          │
│  motion/ 공용 템플릿 · templates/ 대본 골격 · fonts/            │
└──────────────┬───────────────────────────────────────────────┘
               ▼ 읽고 쓴다
┌─ projects/  파일 SSOT (설치본은 %LOCALAPPDATA%\VideoStudio\) ──┐
│  <강좌id>/course.json · course-intro.html · course-stinger.html │
│  <강좌id>-NN/scenes.json · plan.md · facts.md · motion/ · bg/   │
│  out/ (빌드 산출물 — 파생물, 삭제 가능 · --out 으로 데이터 폴더에)│
└───────────────────────────────────────────────────────────────┘
```

**의존 방향은 위→아래 단방향.** engine 은 core 를 모르고, core 는 app 을 모른다.
app 이 없어도 core 가 완결(단독 테스트)이고, core 가 없어도 engine 은 CLI 로 돈다 (지금과 동일).

## 신규 저장소 디렉토리

```
video-studio/
├── README.md
├── docs/
│   ├── design/            ← 이 설계서 묶음
│   └── records/           ← 제작 판단 기록 (h5-saas .claude/memory 에서 선별 카피)
├── .claude/
│   └── skills/            ← develop-video · develop-lecture 카피 (에이전트 규약 SSOT)
├── engine/                ← Node CLI vendoring (스킬 scripts/ 가 원본)
│   ├── build.js  check-tts.js  chapters.js  inspect.js  preview.js
│   ├── lib/  motion/  templates/  fonts/  assets/(CATALOG.md·fetch.js 만)
│   ├── package.json  ENGINE_VERSION.md      ← 동기화 기록 (아래)
├── core/                  ← Python 패키지 (로직 전부)
│   ├── env.py  facade.py  ← 5단계 신설 (07_desktop)
│   ├── paths.py  schema.py  validate.py
│   ├── indexer.py  jobs.py  engine_io.py
│   └── agents/            (4단계 — 5-6 에서 Claude/OpenAI 이중화)
├── app/                   ← PySide6 데스크톱 (5단계 신설 — windows/ widgets/ qtbridge.py)
├── packaging/             ← PyInstaller spec · 런타임 수집 · Inno Setup · edge-tts 셔틀 (5-7)
├── projects/              ← 사용자 데이터 (개발 기본 루트 — 설치본은 %LOCALAPPDATA%\VideoStudio\)
├── fixtures/projects/     ← 개발·테스트 픽스처 (h5-saas 실전 대본 카피)
├── tests/                 ← core 단위 테스트 (경로 계산·검증기가 최우선 대상)
└── pyproject.toml
```

구 웹 콘솔 `api/`(FastAPI)·`web/`(Vue) 은 저장소에서 제거됐다 — `api/` 는 5-2 완료 시점,
`web/` 은 2026-08-21 사용자 지시(D16)로 조기 삭제. 이식 대조가 필요하면 커밋 `a731a62`
에서 꺼낸다(`git show a731a62:web/src/...`).

## engine vendoring — 동기화 규칙

**교훈**: h5-saas 의 `tools/video/` 는 스킬 `scripts/` 보다 낡아 **preflight 가 통째로 빠진 채**
영상을 굽고 있었다. 사본 두 개가 생기면 반드시 갈라진다. 그래서:

1. **원본 = `.claude/skills/develop-video/scripts/`** (스킬이 규약과 코드를 함께 관리).
2. `engine/ENGINE_VERSION.md` 에 "언제 어느 커밋의 스킬에서 떠 왔나 + 로컬 수정 목록(원칙 0건)"을 기록.
3. 엔진을 고치고 싶으면 **스킬 쪽을 고치고 다시 떠 온다.** 앱 저장소에서 직접 고치는 것은
   핫픽스뿐이고, 그 경우 ENGINE_VERSION.md 에 남겨 다음 동기화 때 상류로 올린다.
4. 예외 — **`inspect.js`·`preview.js` 는 앱이 추가하는 신규 파일** (기존 lib 재사용, 기존 파일 무수정):
   - `inspect.js`: preflight·templateKeys·ffprobe 길이·TTS 캐시 조회를 **JSON 으로 출력**하는
     기계용 CLI. Python 이 검증 로직을 재구현하지 않기 위한 다리다 ([04_api.md](04_api.md) 계약).
   - `preview.js`: 모션 html 1장을 파라미터 주입 상태로 서빙/렌더 (기존 preview-motion.mjs 정리판).

## 기술 스택 확정

| 층 | 선택 | 버전 기준 |
|---|---|---|
| 로직 | Python 3.12+ · pydantic v2 | conda `penv3.13-insait`. ~~FastAPI·uvicorn·sse-starlette~~ — D12 로 제거 (5-2) |
| 파일 감시 | ~~watchfiles~~ → `QFileSystemWatcher` (5-3) | 외부 편집(Claude Code) 감지 → 인덱스 갱신·편집 충돌 경고 — 역할 동일 |
| 캐시 | SQLite (표준 lib) — 파생 캐시 전용 | 스키마 버전 불일치 시 통째 재생성 |
| UI | **PySide6 (LGPL)** — QWebEngineView(프리뷰)·QMediaPlayer(재생) (D13) | ~~Vue 3.5·Vite·Element Plus·Tailwind~~ 는 1~4단계 검증 후 5-5 에서 제거. 디자인 토큰(D11) 값은 Qt 스타일시트로 이식 |
| 엔진 | Node 20.12+ · Playwright(Chromium) · ffmpeg | 기존 그대로. 설치본은 runtime/ 동봉 (D14 — [07](07_desktop.md)) |
| TTS | edge(기본·키 불요) / azure / eleven | 엔진이 이미 지원. Azure·Eleven 실키 확보·인증 실측 (2026-08-21). 상용은 azure 계약([06](06_roadmap.md)) |
| 에이전트 | `claude-agent-sdk`(기본) + OpenAI SDK(선택) — D15 | [05_agent.md](05_agent.md) |
| 패키징 | PyInstaller(onedir) + Inno Setup — 관리자 권한 불요 설치 | [07_desktop.md](07_desktop.md) |

## LangChain / LangGraph 를 쓰는가 — **아니오**

질문이 나온 김에 판단 근거를 정본으로 남긴다.

| 관점 | LangChain/LangGraph | Claude Agent SDK | 이 프로젝트에서 |
|---|---|---|---|
| 제작 규약 주입 | 1,200줄 규약(SKILL.md 2종)을 프롬프트 체인으로 **재인코딩**해야 함 | `.claude/skills/` 를 **네이티브 로드** (settingSources) — agent.mjs PoC 로 검증됨 | SDK 압승. 규약은 살아 있는 문서고, 스킬을 고치면 에이전트가 바로 따라온다 |
| 도구 | 파일·bash 도구를 직접 정의·바인딩 | Read/Write/Edit/Bash/Glob/Grep 내장 + 권한 모델(allow/deny) 내장 | 에이전트가 할 일이 "대본 파일을 읽고·쓰고·빌드 돌리고·프레임을 눈으로 본다"라 내장 도구 그 자체 |
| 멀티스텝 제어 | LangGraph 의 강점 — 결정적 그래프·체크포인트 | 에이전틱 루프 (모델이 판단) | **우리의 결정적 오케스트레이션은 이미 일반 코드다** (큐·빌드 파이프라인·검증기). 그래프로 짤 대상이 남아 있지 않다 |
| 멀티 프로바이더 | 강점 (모델 교체 자유) | Anthropic 계열 중심 | 규약·평가 지침이 Claude 기준으로 축적돼 있어 교체 요구 없음. 필요해지면 그때 경계(core/agents 인터페이스)만 지키면 된다 |
| 관측·재시도·컨텍스트 관리 | 직접 조립 | SDK 내장 | — |

**요약**: 이 시스템에서 "오케스트레이션이 필요한 결정적 부분"은 전부 일반 Python 코드와
Node CLI 로 이미 존재하고, "에이전트가 필요한 부분"은 열린 저작 작업(대본 초안·도식 생성·평가)
뿐이다. 열린 저작 작업은 그래프가 아니라 **도구를 쥔 단일 에이전트 루프**가 맞는 형태고,
그 루프+도구+규약 로딩을 SDK 가 전부 내장한다. LangChain 을 끼우면 추상화 한 겹이 늘 뿐
얻는 것이 없다. (스킬의 컨셉 검증처럼 병렬 다안 생성이 필요하면 `asyncio.gather` 로 SDK
query 를 N 개 띄우면 된다 — 그래프 프레임워크가 필요한 규모가 아니다.)

## "agent 방식"인가 — **하이브리드** (에이전트는 저작·평가만)

| 작업 | 방식 | 이유 |
|---|---|---|
| 강좌 설정·대본 편집·경로 계산·검증 | 결정적 코드 | 정답이 있는 계산. 에이전트를 끼우면 느리고 비싸고 비결정적 |
| 빌드·프레임 추출·무음 검출·챕터 계산 | 결정적 코드 (engine CLI) | 이미 CLI 로 완성 |
| **대본 초안 생성** (주제→구성표→scenes.json) | 에이전트 | 열린 저작. 스킬 규약(골격·분량·재미 장치·용어 규칙)을 읽고 수행 |
| **도식 html 생성** (설명 구간의 모션 그래픽) | 에이전트 | 열린 저작. 연출 팔레트 규약 준수 |
| **자료조사** (facts.md — 수치·출처) | 에이전트 (웹 검색 도구) | 스킬의 자료조사 규율 그대로 |
| **평가** (reviewer) | 에이전트 (별도 세션) | "만든 쪽이 채점하지 않는다" 규약 — 컨텍스트 없는 새 세션이 산출물만 보고 채점 |

에이전트 산출물도 결국 **같은 파일**(scenes.json·motion/*.html·facts.md)에 떨어지므로,
사람이 화면에서 이어서 고칠 수 있다. "AI 초안 → 화면에서 손질 → 빌드"가 주 동선이다.
상세 설계는 [05_agent.md](05_agent.md).

## 로컬 모드 / 상용 모드

같은 코드가 설정으로 갈린다. 로컬 모드가 기본이고 1~3단계의 전부다.

| | 로컬 (데스크톱 앱) | 상용 (별도 트랙) |
|---|---|---|
| storage | **추상화 없음** — `core.env`(데이터 폴더) + `core.paths`(상대경로)로 파일을 직접 읽고 쓴다 | `S3Storage(bucket, prefix=tenant/…)` + 로컬 작업 캐시 — **이 시점에 storage 계층을 신설한다** |
| jobs | in-process 큐 (동시 2) | 큐 서비스 + 렌더 워커 풀 (컨테이너: Node+Chromium+ffmpeg — 이 시점에 엔진 Python 포팅 재평가, D14) |
| 인증 | 없음 (단일 사용자 데스크톱) | 세션 + 테넌트 격리 |
| 에이전트 키 | 사용자 본인 키 (.env / 첫 실행 위저드) | 서비스 키 + 사용량 미터링 |

**jobs 인터페이스를 1단계부터 지키는 것**이 상용 전환 비용을 정하는 전부다 (D8).

> **D9(storage 추상화) 정정 — 2026-08-22 코드 리뷰.** `core/storage.py`(Storage 프로토콜 +
> LocalFS)는 0단계에 만들어 두고 **끝내 아무도 쓰지 않았다** — facade·indexer·schema 전부
> `pathlib` 로 직접 읽고 쓴다. 참조자는 자기 자신을 검사하는 테스트 하나뿐이었다. 쓰이지 않는
> 인터페이스는 이음매가 아니라 **이음매가 있다는 착각**이라, 파일을 지우고 이 표에 현실을 적었다.
> 상용 전환 때는 `core.env`·`core.paths` 를 통과하는 파일 접근을 storage 로 감싸며 신설한다
> (그 접근이 두 모듈에 모여 있는 것이 실제 이음매다).
