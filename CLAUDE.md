# Video Studio — 프로젝트 지침

강좌(시리즈) 영상 제작 스튜디오. **로컬 단독 설치형 데스크톱 앱**(담당자 Windows 배포)으로
만들고, 이후 상용 서비스로 키운다 (2026-08-21 전환 결정 D12 — 웹 콘솔은 1~4단계 검증용이었다).

## 설계 정본 (SSOT)

**[docs/design/](docs/design/README.md) 이 설계 정본이다. 작업 착수 전 해당 문서를 먼저 읽는다:**

| 작업 | 먼저 읽을 문서 |
|---|---|
| 모든 세션 공통 | [00_overview.md](docs/design/00_overview.md) — 원칙·확정 결정 D1~D16 |
| 구조·스택·디렉토리 | [01_architecture.md](docs/design/01_architecture.md) |
| course/scenes 스키마·경로 규칙 | [02_data-model.md](docs/design/02_data-model.md) — ★ 경로 함정 5종 표 |
| 화면 개발 | [03_screens.md](docs/design/03_screens.md) + **★ [08_qt-style.md](docs/design/08_qt-style.md)**(스타일 규칙) + [09_ui-review.md](docs/design/09_ui-review.md)(점검 대장) + [10_ux-plan.md](docs/design/10_ux-plan.md)(UX 재설계 계획) |
| 유스케이스(구 API)·잡 큐·엔진 호출 | [04_api.md](docs/design/04_api.md) |
| 에이전트 기능 | [05_agent.md](docs/design/05_agent.md) |
| 단계·수용 기준·리스크 | [06_roadmap.md](docs/design/06_roadmap.md) |
| **데스크톱 전환 (현행 작업)** | [07_desktop.md](docs/design/07_desktop.md) — PySide6·패키징·5단계 계획 |

구현하며 설계와 어긋나는 결정이 나오면 설계서를 함께 고친다(00_overview 결정 표에 날짜와 함께).

## 확정 결정 요약 (상세·근거는 00_overview)

- **설치형 데스크톱 앱** (D12) — UI **PySide6**(D13, HTTP 계층 없음 — core 직접 호출) · 로직 Python 3.12+ (core/) · DB 없음(파일 SSOT, SQLite 는 파생 캐시만). FastAPI(`api/`)·Vue(`web/`) 는 삭제 완료(2026-08-21)
- 렌더 엔진 = `engine/` Node CLI — **수정 금지·포팅 금지**(D14 — 설치본에 Node·ffmpeg·Chromium 동봉), subprocess 호출. 고칠 일이 생기면 [engine/ENGINE_VERSION.md](engine/ENGINE_VERSION.md) 규칙
- 에이전트 = **Claude Agent SDK 기본 + OpenAI 선택**(D15 — `AGENT_PROVIDER`, 테스트는 `AGENT_TEST_MODE`=최저가 모델), **저작·평가만**(LangChain/LangGraph 미채택). 키 없이도 앱 완결 동작
- 빌드는 처음부터 잡 큐, 스토리지 접근은 처음부터 추상화 계층(상용 전환 대비)
- 키(.env — Azure·Eleven·Anthropic 실키 확보 2026-08-21): 셸 → 저장소 `.env` → `~/.claude/develop-video.env` 순. 커밋 금지

## 작업 규칙

- **파일이 SSOT** — `projects/<id>/`(course.json·scenes.json·plan.md)가 정본, `out/`은 파생물. 저장 시 `_` 접두 주석 필드·키 순서 보존(라운드트립 무손실).
- **경로 문자열을 손으로 만들지 않는다** — 상대경로 기준이 5종([02](docs/design/02_data-model.md)). 경로는 `core/paths.py` 계산기가 기입하고, 그 실측 5행이 단위 테스트다.
- 제작 규약(대본 문법·도식 규칙·검증 절차)의 정본 = [.claude/skills/](.claude/skills/) 의 develop-video·develop-lecture. 코드로 복제하지 말고 기계화 가능한 검증만 옮긴다.
- 픽스처 = `fixtures/projects/hr-basics*`. 경로 이전 완료(2026-08-14) — 이 저장소 단독으로 재현 빌드된다. 미디어 파일(bgm·broll)은 커밋 안 되므로 새 클론에서는 engine/assets/CATALOG.md 출처에서 다시 받는다.
- 구현 진행의 SSOT = [docs/BUILD_LOOP.md](docs/BUILD_LOOP.md) — 세션을 새로 열면 이 파일의 루프 프로토콜대로 다음 미완 단계를 이어간다. Python 은 conda `penv3.13-video`.
- 커밋은 사용자가 요청할 때만.

## 진행 상태

- [x] 저장소 이행 (2026-08-14 — h5-saas 에서 설계서·엔진·스킬·픽스처)
- [x] 0단계 — 엔진 셀프테스트·inspect.js·픽스처 경로 이전·Python 골격 (2026-08-14 수용 기준 충족 — 픽스처 재현 빌드 292.77s mp4+srt·프레임 검수 통과·pytest 11건)
- [x] 1단계 — 읽기 전용 콘솔 (2026-08-14 수용 기준 충족 — 화면에서 빌드·프레임 4+1종·mp4 재생 Playwright 실측, pytest 26건)
- [x] 2단계 — 강좌 편집 (2026-08-15 수용 기준 충족 — 화면 개설→회차 생성→빌드 E2E 실측, 라운드트립 diff 0, pytest 59건)
- [x] 3단계 — 대본 에디터 (2026-08-15 수용 기준 충족 — 새 회차를 화면만으로 완성(대본→빌드→검수→배포) E2E 실측, 결함 4종 입력 시점 차단, pytest 66건)
- [x] 4단계 — 에이전트 (2026-08-15 수용 기준 충족 — 실키로 AI 초안→손질→빌드→AI 평가 완주($0.46), 키 없이 1~3단계 동작 재확인. 모델은 당분간 전부 Haiku — .env 오버라이드)
- [ ] 5단계 — 데스크톱 전환 🔄 5-6 까지 완료 (2026-08-21~22 — 스파이크·env·facade/api 삭제·Qt 읽기 콘솔·편집 ①②③/위저드·⑤ 대본 에디터+④⑥⑦(결함 차단 4종·프리뷰 스크럽)·에이전트 이중 제공자+설정 화면 실측. 파이썬은 conda `penv3.13-video` 하나로 통일(전부 pip — 2026-08-22 insait 분리·.qt-venv 은퇴). 5-7·5-8 은 코드까지 완료 — **남은 것은 사용자 준비물 3종**(깨끗한 Windows PC 설치 실측·Inno Setup·코드 서명 인증서). 체크리스트는 [BUILD_LOOP](docs/BUILD_LOOP.md))

단계가 끝나면 이 체크박스를 갱신한다.
