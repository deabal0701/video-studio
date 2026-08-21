# Video Studio — 설계서 묶음

> 강좌·영상 제작 파이프라인(develop-video · develop-lecture)을 **웹 앱 → 상용 서비스**로
> 키우기 위한 설계 정본. 이 폴더째 신규 프로젝트 저장소로 옮겨 `docs/design/` 으로 쓴다.

## 문서 인덱스

| 문서 | 내용 |
|---|---|
| [00_overview.md](00_overview.md) | 비전 · 문제 정의 · 제품 원칙 · **확정 결정 전체 표** |
| [01_architecture.md](01_architecture.md) | 3층 구조 · 신규 repo 디렉토리 · 기술 스택 · LangChain/LangGraph 판단 |
| [02_data-model.md](02_data-model.md) | 파일 SSOT 스키마 · **경로 규칙(함정 5종)** · 길이 계산 · 동시성 |
| [03_screens.md](03_screens.md) | 화면 11종 상세 — 레이아웃 · 필드 · 검증 · 상호작용 |
| [04_api.md](04_api.md) | REST + SSE 설계 · 빌드 잡 상태머신 · 큐 정책 · engine 호출 계약 |
| [05_agent.md](05_agent.md) | 에이전트 설계 — Claude Agent SDK(Python) · 역할 경계 · 비용 |
| [06_roadmap.md](06_roadmap.md) | 0~4단계 로드맵 · 상용화 트랙 · **라이선스 리스크** |

## 새 저장소로 가져갈 것 (카피 목록)

이 설계는 h5-saas 저장소의 실물을 기반으로 한다. 신규 저장소를 만들 때 아래를 카피한다.

| 무엇 | 원본 경로 (h5-saas 기준) | 새 저장소 위치 | 비고 |
|---|---|---|---|
| 이 설계서 | `tools/video-studio-design/` | `docs/design/` | 폴더째 |
| **엔진 (렌더 파이프라인)** | `.claude/skills/develop-video/scripts/` | `engine/` | ★ **tools/video 가 아니라 스킬 쪽** — 로컬 tools/video 는 preflight 가 빠진 구본이다 |
| 모션 템플릿 공용분 | `.claude/skills/develop-video/templates/motion/` | `engine/motion/` | `_base.css`·`_params.js` 포함 |
| 대본 템플릿 | `.claude/skills/develop-video/templates/*.json` + `develop-lecture/templates/` | `engine/templates/` | scenes 골격 · course.json · course-intro/stinger · termnote.css |
| 스킬 (제작 규약 SSOT) | `.claude/skills/develop-video/` · `.claude/skills/develop-lecture/` | `.claude/skills/` | 에이전트가 읽는다. SKILL.md·references·agents·workflows·examples 전부 |
| chapters 스크립트 | `.claude/skills/develop-lecture/scripts/chapters.js` | `engine/chapters.js` | 유튜브 챕터 계산 |
| 표본 데이터 (개발 픽스처) | `tools/video/projects/hr-basics*` · `rest-api-lecture` 등 | `fixtures/projects/` | 실전 대본이 최고의 테스트 데이터 |
| 폰트 | `h5-saas-alpha/insait-frontend/src/assets/fonts/PretendardVariable.woff2` + LICENSE | `engine/fonts/` | ★ 현재 대본들이 h5-saas 내부 경로를 fontUrl 로 참조 — 독립 시 반드시 동봉 (SIL OFL이라 재배포 가능) |
| 제작 기록 (참고) | `.claude/memory/<영상id>.md` 중 영상 관련 | `docs/records/` | 함정·판단 기록. 선택 |

**카피하지 않는 것**: `assets/` 소재 파일(무료 스톡 재배포 금지 — `CATALOG.md`+`fetch.js` 만 가져가 다시 받는다), `out/` 산출물, `node_modules`.

## 첫 실행 순서 (새 저장소에서)

1. `engine/` 에서 `npm i -D playwright && npx playwright install chromium`
2. `node engine/check-tts.js` — TTS 동작 확인 (edge 는 키 불요)
3. `node engine/build.js --scenes engine/templates/scenes.selftest.json` — 20초 셀프테스트
4. fixtures 회차 하나로 `node engine/build.js --project fixtures/projects/hr-basics-01` 재현
5. 그다음 [06_roadmap.md](06_roadmap.md) 1단계(읽기 전용 콘솔) 착수

## 결정 요약 (상세 근거는 각 문서)

| 항목 | 결정 |
|---|---|
| 서버 | **Python 3.12+ / FastAPI** |
| UI | **Vue 3 + Vite + Element Plus + Tailwind** (h5-saas 프론트와 동일 스택) |
| 렌더 엔진 | **Node CLI 유지 — 포팅 금지.** 서버가 subprocess 로 호출 |
| DB | **없음 — 파일이 SSOT.** 목록용 파생 캐시(SQLite)만, 언제든 재생성 |
| 에이전트 | **Claude Agent SDK (Python).** LangChain/LangGraph **미채택** — [05_agent.md](05_agent.md) |
| 에이전트 범위 | 초안 생성·도식 생성·평가만. 편집·빌드·검수는 결정적 코드 (1~3단계는 API 키 불요) |
