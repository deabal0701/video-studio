# Video Studio — 프로젝트 지침

강좌(시리즈) 영상 제작 스튜디오. 웹 앱으로 시작해 상용 서비스로 키운다.

## 설계 정본 (SSOT)

**[docs/design/](docs/design/README.md) 이 설계 정본이다. 작업 착수 전 해당 문서를 먼저 읽는다:**

| 작업 | 먼저 읽을 문서 |
|---|---|
| 모든 세션 공통 | [00_overview.md](docs/design/00_overview.md) — 원칙·확정 결정 D1~D10 |
| 구조·스택·디렉토리 | [01_architecture.md](docs/design/01_architecture.md) |
| course/scenes 스키마·경로 규칙 | [02_data-model.md](docs/design/02_data-model.md) — ★ 경로 함정 5종 표 |
| 화면 개발 | [03_screens.md](docs/design/03_screens.md) |
| API·잡 큐·엔진 호출 | [04_api.md](docs/design/04_api.md) |
| 에이전트 기능 | [05_agent.md](docs/design/05_agent.md) |
| 단계·수용 기준·리스크 | [06_roadmap.md](docs/design/06_roadmap.md) |

구현하며 설계와 어긋나는 결정이 나오면 설계서를 함께 고친다(00_overview 결정 표에 날짜와 함께).

## 확정 결정 요약 (상세·근거는 00_overview)

- 서버 **Python 3.12+/FastAPI** · UI **Vue 3+Vite+Element Plus+Tailwind** · DB 없음(파일 SSOT, SQLite 는 파생 캐시만)
- 렌더 엔진 = `engine/` Node CLI — **수정 금지·포팅 금지**, subprocess 호출. 고칠 일이 생기면 [engine/ENGINE_VERSION.md](engine/ENGINE_VERSION.md) 규칙
- 에이전트 = Claude Agent SDK(Python), **저작·평가만**(LangChain/LangGraph 미채택). 1~3단계는 API 키 없이 완결 동작
- 빌드는 처음부터 잡 큐, 스토리지 접근은 처음부터 추상화 계층(상용 전환 대비)

## 작업 규칙

- **파일이 SSOT** — `projects/<id>/`(course.json·scenes.json·plan.md)가 정본, `out/`은 파생물. 저장 시 `_` 접두 주석 필드·키 순서 보존(라운드트립 무손실).
- **경로 문자열을 손으로 만들지 않는다** — 상대경로 기준이 5종([02](docs/design/02_data-model.md)). 경로는 `core/paths.py` 계산기가 기입하고, 그 실측 5행이 단위 테스트다.
- 제작 규약(대본 문법·도식 규칙·검증 절차)의 정본 = [.claude/skills/](.claude/skills/) 의 develop-video·develop-lecture. 코드로 복제하지 말고 기계화 가능한 검증만 옮긴다.
- 픽스처 = `fixtures/projects/hr-basics*`. 경로 이전 완료(2026-08-14) — 이 저장소 단독으로 재현 빌드된다. 미디어 파일(bgm·broll)은 커밋 안 되므로 새 클론에서는 engine/assets/CATALOG.md 출처에서 다시 받는다.
- 구현 진행의 SSOT = [docs/BUILD_LOOP.md](docs/BUILD_LOOP.md) — 세션을 새로 열면 이 파일의 루프 프로토콜대로 다음 미완 단계를 이어간다. Python 은 conda `penv3.13-insait`.
- 커밋은 사용자가 요청할 때만.

## 진행 상태

- [x] 저장소 이행 (2026-08-14 — h5-saas 에서 설계서·엔진·스킬·픽스처)
- [x] 0단계 — 엔진 셀프테스트·inspect.js·픽스처 경로 이전·Python 골격 (2026-08-14 수용 기준 충족 — 픽스처 재현 빌드 292.77s mp4+srt·프레임 검수 통과·pytest 11건)
- [x] 1단계 — 읽기 전용 콘솔 (2026-08-14 수용 기준 충족 — 화면에서 빌드·프레임 4+1종·mp4 재생 Playwright 실측, pytest 26건)
- [x] 2단계 — 강좌 편집 (2026-08-15 수용 기준 충족 — 화면 개설→회차 생성→빌드 E2E 실측, 라운드트립 diff 0, pytest 59건)
- [x] 3단계 — 대본 에디터 (2026-08-15 수용 기준 충족 — 새 회차를 화면만으로 완성(대본→빌드→검수→배포) E2E 실측, 결함 4종 입력 시점 차단, pytest 66건)
- [x] 4단계 — 에이전트 (2026-08-15 수용 기준 충족 — 실키로 AI 초안→손질→빌드→AI 평가 완주($0.46), 키 없이 1~3단계 동작 재확인. 모델은 당분간 전부 Haiku — .env 오버라이드)

단계가 끝나면 이 체크박스를 갱신한다.
