# 07 — 데스크톱 전환 (로컬 단독 설치형)

> 2026-08-21 사용자 결정. 웹(Vue+FastAPI) 콘솔을 **PySide6 데스크톱 앱**으로 재편하고,
> 설치기 하나로 담당자 Windows PC 에 배포한다. **담당자는 `VideoStudio.exe` 하나만
> 더블클릭한다** — Node·ffmpeg·Chromium 은 설치본 안의 부품이고 사용자에게 보이지 않는다.
> 화면의 내용·검증 규칙(결함 차단 4종·예산 게이지·If-Match 등)은 03_screens 그대로 유지 —
> 바뀌는 것은 담는 그릇뿐이다. 화면 도식 원본: [화면 지도 아티팩트](https://claude.ai/code/artifact/9c1774b5-ee9c-4c7c-a351-dd51e9f8d701).

관련 확정 결정: [00_overview](00_overview.md) **D12(설치형 데스크톱·HTTP 제거) ·
D13(PySide6) · D14(런타임 동봉 — 엔진 포팅 안 함) · D15(에이전트 이중 제공자·테스트 최저가)**.

## 왜 이 구조인가

| 검토 | 판정 · 근거 (2026-08-21 실측) |
|---|---|
| "실행파일 하나" ≠ "Node 제거" | PyInstaller 산출물에 node.exe 를 동봉하면 사용자 경험은 동일(exe 더블클릭 1회). Node 는 ffmpeg 같은 내부 부품이다 |
| 엔진 Python 포팅 (Node 완전 제거) | **안 한다 (D4 유지).** 3,243줄 포팅 자체는 가능(playwright-python·ffmpeg subprocess·tts 는 이미 Python)하나, 검증된 렌더 결과의 프레임 단위 회귀 검증 비용(+5~6주)이 실익(용량 −70MB)을 압도. **상용 S1(워커 컨테이너화) 시점에 재평가** ([06](06_roadmap.md)) |
| TTS 는 이미 Python | 엔진의 `lib/tts.js` 가 `edge-tts`(Python 패키지)를 subprocess 로 부른다 — 현 시스템도 두 런타임이 필요했다. 설치본은 `edge-tts.exe` 셔틀로 해결(아래) |
| HTTP 계층(FastAPI) | **제거.** UI 가 core 를 직접 호출한다. 포트 충돌·방화벽 팝업·서버 수명 관리·HTTP 계층의 보안면(preview 임의 파일 읽기 등)이 통째로 사라진다 |
| UI 후보 비교 | PyQt6 = GPL(사내 배포도 부담) → 탈락. Tkinter = html 애니메이션 프리뷰 불가(D10 포기) → 탈락. Flet/NiceGUI = 결국 브라우저 렌더 → 탈락. **PySide6 = LGPL·QWebEngineView(D10 유지)·QMediaPlayer** → 채택 |

## 아키텍처 (01 의 3층 수정판)

```
┌─ app/  PySide6 데스크톱 (단일 프로세스) ─────────────────────┐
│  MainWindow(내비+페이지 스택+상태바) · 화면 ①~⑦ · 위저드/설정  │
│  qtbridge: JobQueue.listener → Qt Signal (SSE 의 등가물)      │
└──────────────┬───────────────────────────────────────────────┘
               │ 직접 호출 (HTTP 없음)
┌─ core/  Python — 로직 전부 (변경 최소) ───────────────────────┐
│  기존 모듈 유지 + env.py(경로·실행환경 계산 — 신설)             │
│  + facade.py(화면이 부르는 유스케이스 — api 라우터 로직 이관)   │
└──────────────┬───────────────────────────────────────────────┘
               │ subprocess (번들 runtime/ 의 node·ffmpeg 사용)
┌─ engine/  Node CLI (vendored — 무수정 유지) ──────────────────┘
```

의존 방향은 그대로 위→아래 단방향. **core 가 UI 무관·단독 테스트 가능**하게 설계된 것이
이 전환의 배당금이다 — 로직 재작성이 아니라 껍데기 교체다 (재사용 ~1,400줄 / 삭제 ~2,300줄
/ 신규 UI ~2,800줄).

## 화면 재편 — 창 지도

웹 라우팅 7경로 → **단일 메인 창 + 페이지 6종(QStackedWidget) + 모달 5종 + 신규 3종**.

```
첫 실행 위저드 ─1회→ ┌─ MainWindow ──────────────────────────────┐
                     │ 좌측 내비: 대시보드 · 강좌들 · 라이브러리 ·   │
                     │            작업 큐 · 설정(★신규)            │
                     │ 페이지: 대시보드 → 강좌(탭①②③) → 회차(탭④⑤⑥⑦)│
                     │ 하단 상태바: 빌드 잡 칩·진행률·중단 (전 페이지) │
                     └───────────────────────────────────────────┘
모달: 새 강좌 위저드 · 템플릿 피커 · B롤 피커 · AI 초안 brief · 충돌/삭제 확인
```

| 재편 결정 | 내용 |
|---|---|
| 단일 창 | 다중 창(회차별 창) 대신 웹과 같은 단일 창 + 페이지 전환. 잡 큐·상태바가 전역이라 단순하고 학습 부담이 적다. 회차 비교는 ⑥ "직전 회차 타이틀 나란히"가 담당 |
| 템플릿 갤러리 → 피커 모달 | 독립 페이지 격하. 갤러리는 ⑤에서 클립에 꽂을 때만 쓰인다 |
| 잡 칩 → 하단 상태바 | 데스크톱 관례. 진행률 바 + [중단] + 자가진단 요약 상주, 클릭 시 작업 큐 페이지 |
| ★ 신규 화면 3종 | **첫 실행 위저드**(아래) · **설정**(키 4종·데이터 폴더·자가진단·에이전트 제공자/테스트 모드 스위치) · **토스트/알림**(ElMessage 등가) |
| 단발 영상 동선 | v1 은 현행 유지(목록 노출만) — 승격은 별도 결정 |

각 화면의 내용·필드·검증은 [03_screens](03_screens.md) ①~⑦ 절이 계속 정본이다.

## 웹 → 데스크톱 기술 대응

| 웹 (제거 대상) | 데스크톱 (PySide6) |
|---|---|
| vue-router 7경로 | 좌측 내비 + `QStackedWidget` 페이지 6종 |
| 상단 잡 칩 + SSE `/api/events` | 하단 상태바 잡 위젯 — `JobQueue.listener` → Qt Signal (**core 무수정** — listener 훅 그대로) |
| 잡 SSE `/jobs/{id}/events` | `QThreadPool` 워커가 `subscribe()` 소비 → Signal 릴레이 |
| iframe + `preview.js` + URL 질의 params | `QWebEngineView` — 같은 문서·같은 질의·같은 `getAnimations` 시킹 (**D10 유지**) |
| `<video>`·`<audio>` (mp4·TTS 캐시) | `QMediaPlayer` + `QVideoWidget` / `QAudioOutput` |
| If-Match / 409 (HTTP 낙관적 잠금) | facade 의 etag 검사로 **동일 유지** — 외부 편집(에디터·Claude Code) 충돌은 여전히 실재 |
| watchfiles (uvicorn lifespan) | `QFileSystemWatcher` → 인덱서 재스캔 + 화면 갱신 Signal |
| ElMessage / ElMessageBox | 토스트 오버레이·상태바 메시지 / `QMessageBox`·모달 |
| vuedraggable 클립 정렬 | `QListWidget` InternalMove 드래그 |
| srt 다운로드 링크 | 다른 이름으로 저장 다이얼로그 + [폴더 열기] |
| tokens.css 디자인 토큰 (D11) | Qt 스타일시트 상수로 이식 — 색·간격·라운드 값 유지 |

## 경로·실행환경 계층 — `core/env.py` (신설)

설치 폴더(읽기 전용)와 데이터 폴더(쓰기)를 가르는 것이 설치형의 핵심이다.
개발 모드(저장소 안 실행)와 설치 모드를 자동 판별하고, 아래를 한 곳에서 결정한다.

```
설치 폴더 (읽기 전용)                      데이터 폴더 (쓰기)
%LOCALAPPDATA%\Programs\VideoStudio\      %LOCALAPPDATA%\VideoStudio\
  VideoStudio.exe  _internal\               projects\   ← 파일 SSOT
  engine\  runtime\{node,ffmpeg,chromium,     out\      ← 빌드 산출물 (--out 으로 지정)
           edge-tts.exe}                      .cache\  logs\
키: %USERPROFILE%\.claude\develop-video.env  (엔진이 이미 읽는 공용 규약 — 위저드가 기록)
```

- `install_dir / engine_dir / runtime_dir` · `data_dir / projects_dir / out_root / cache_dir`
  (`log_dir` 은 부르는 곳이 없어 2026-08-22 제거 — 파일 로깅을 넣을 때 되살린다)
- `child_env()`: 자식 프로세스 PATH 맨 앞에 runtime\(node·ffmpeg·edge-tts 셔틀) 주입 +
  `PLAYWRIGHT_BROWSERS_PATH` = 번들 chromium. 엔진은 `'ffmpeg'`·`edge-tts` 를 맨이름으로
  찾으므로 PATH 주입만으로 동작한다 (2026-08-21 엔진 실측 — lib 전역·tts.js 후보 1순위)
- 산출물은 `build.js --out <data>/out` · `inspect.js --out` · `chapters.js --video-root` 로
  데이터 폴더에 쓴다 — **엔진 무수정** (전부 기존 CLI 인자, 실측 확인)
- 설치 루트에 빈 `package.json` 을 놓아 엔진의 `findRoot`/`envFiles` 상향 탐색을 설치
  폴더에서 멈춘다 (남의 폴더의 .env 를 줍지 않게)

### 설치 폴더 쓰기 예외 — `engine/assets/` 하나뿐 (2026-08-22 결정)

원칙은 "설치 폴더는 읽기 전용"이고, 예외는 **스톡 소재 다운로드**뿐이다.

| 왜 예외인가 | 왜 데이터 폴더로 못 옮기나 |
|---|---|
| 소재는 재배포 금지라 설치본에 못 넣고 사용자가 직접 받는다 (R3) | `scenes.json` 의 `bgm`·`video` 는 **엔진 루트 기준** 상대경로다 (02 경로 표) — 엔진 무수정 원칙상 소재는 `engine/assets/` 아래여야 한다 |
| 설치 위치가 `%LOCALAPPDATA%\Programs` (per-user) 라 관리자 권한 없이 쓸 수 있다 | CATALOG.md(라이선스 정본)도 받을 때마다 한 줄씩 추가된다 — 소재와 같은 폴더가 맞다 |

따라서 **다른 모든 쓰기(projects·out·캐시·로그·프리뷰 임시문서)는 데이터 폴더로 가야 하고**,
`packaging/smoke-frozen.py` 가 실행 전후 설치 폴더 스냅샷을 대조해 **`engine/assets/` 밖의
새 파일·변경 파일이 하나라도 있으면 실패**로 처리한다 (5-1 env.py 수정의 종단 수용 기준).

부작용: 제거 시 받아 둔 소재도 함께 지워진다 — 재다운로드가 가능하고 출처는 CATALOG.md 에
남으므로 감수한다. 사용자 데이터(projects·out)는 데이터 폴더라 제거·재설치에도 남는다.

## 이관 시 함께 고치는 결함 (설치본에서 즉시 깨지는 지점 — 2026-08-21 리뷰)

| # | 위치 | 수정 |
|---|---|---|
| 1 | `core/__init__.py`·`status.py` 경로 하드코딩 | env.py 로 이전 (설치 폴더에 쓰기 시도 방지) |
| 2 | `engine_io.py` subprocess `text=True` 인코딩 미지정 | `encoding="utf-8"` — 기본 cp949 로는 한글 로그가 깨져 `_STEP_RE`(`모션`) 매칭 실패 = 진행 표시 붕괴 |
| 3 | subprocess 전부 | `creationflags=CREATE_NO_WINDOW` — GUI 에서 콘솔 창 깜빡임 방지 |
| 4 | `engine_io.chapters` 의 symlink | junction(`mklink /J` 등가) 으로 — symlink 는 개발자 모드/관리자 권한 필요. `deliverables.py` 가 예외를 삼켜 챕터가 조용히 비는 결함도 함께 |
| 5 | 저장 계열 `write_text` | `newline="\n"` 통일 — Windows 기본 개행 번역이 LF 정본을 CRLF 로 바꿔 무손실 라운드트립(02) 위반. 라운드트립 테스트를 `read_bytes` 비교로 강화 |
| 6 | `jobs.py` 종료 잡 무한 보존 | 보존 상한 (최근 N건) |

## 단일 실행파일 — 패키징

| 항목 | 결정 |
|---|---|
| PyInstaller | **onedir** (onefile 금지 — 600MB 를 매 실행 임시 해제라 기동 30초+·백신 오탐). onedir+설치기도 "exe 더블클릭 1회"는 동일하고 기동 2~3초 |
| 설치기 | Inno Setup · `PrivilegesRequired=lowest` · `{localappdata}\Programs\VideoStudio` — **관리자 권한 불요** (VS Code 방식) |
| 런타임 번들 | Node 공식 zip → `runtime\node\` · ffmpeg **LGPL shared 빌드**(라이선스 분쟁 여지 제거) · `npm ci` 결과 + Playwright Chromium |
| edge-tts 셔틀 | PyInstaller 로 `edge-tts.exe` 소형 빌드 → runtime\ PATH 선두. 엔진 tts.js 의 탐색 1순위(`edge-tts`)에 걸린다 — 동결 앱에 `python` 이 없어도 동작 |
| 용량 | **실측 1,100MB** (2026-08-22 — 설계 추정 600MB 는 낙관적이었다). 내역: `runtime\chromium` 430MB(Playwright 렌더용) · `_internal` 391MB(PySide6+QtWebEngine) · `ffmpeg` 152MB(LGPL shared) · `node` 87MB · `edge-tts` 15MB · `engine` 20MB. 압축 설치본은 그보다 작다. **큰 덩어리는 Chromium 두 벌**(Playwright 430MB = 프레임 렌더 D14 · QtWebEngine ~150MB = 라이브 프리뷰 D10) — 하는 일이 달라 공유가 안 된다. 줄인 것: Playwright `chromium_headless_shell` 제거(−271MB — 엔진은 `chromium.launch()` 풀 브라우저를 쓴다) · 스톡 소재 제외(−25MB, 아래) · **안 쓰는 Qt 자산 제외(−191MB, 아래)** |
| 안 쓰는 Qt 자산 | `excludes=` 는 **파이썬 바인딩(.pyd)만** 막는다 — DLL·qml·리소스는 훅이 그대로 수집한다. 이걸 모르고 1,291MB 를 "Chromium 이 크니 어쩔 수 없다"로 넘겼었다. 실측 내역: `qtwebengine_devtools_resources.debug.pak` **72MB(디버그 산출물)** · 전 언어 `qtwebengine_locales` 44MB · 안 쓰는 모듈 DLL(3D·Quick3D·Charts·Controls2 스타일·Pdf·VirtualKeyboard…) 45MB · `qtbase_*.qm` 185개 9MB. spec 의 `_prune()` 이 걷어낸다(binaries 364→265, datas 2702→1820). **판정은 추정이 아니라 동결 스모크** — 잘못 빼면 프리뷰가 안 뜨고 스모크가 잡는다 |
| 소재 제외 (필수) | `engine/assets/{bgm,broll,photo,presenter}` 는 **설치본에 넣지 않는다** — 스톡 재배포 금지(R3). `CATALOG.md`(라이선스 정본)·`fetch.js` 만 넣고 실물은 첫 실행 위저드가 원 출처에서 받는다. collect-runtime.ps1 의 robocopy `/XD` 가 이를 강제하고, 소재 없이도 동결본이 뜨는 것을 스모크로 확인했다 |
| 코드 서명 | 필수 — 없으면 SmartScreen 차단. 사내 CA 또는 OV 인증서 ([06 리스크](06_roadmap.md)) |
| 소재 | 설치본에 **넣지 않는다** (스톡 재배포 금지 — R3). 첫 실행 위저드가 CATALOG 출처에서 다운로드 |

## 첫 실행 위저드 (설치본 전용 · 신규)

```
1 데이터 폴더 확정 → 2 자가진단(node·ffmpeg·chromium·edge 연결) → 3 키 설정(선택) → 4 소재 다운로드
```

- 모든 단계 건너뛰기 가능 — **키 없이도 앱은 완결 동작** (원칙 2 유지: TTS 는 edge 폴백,
  에이전트 버튼은 비활성+사유)
- 3단계 키(Azure·ElevenLabs·Anthropic·OpenAI)는 `%USERPROFILE%\.claude\develop-video.env` 에
  기록 — 엔진이 이미 읽는 규약이라 엔진 무수정
- 2단계 실패 시 설정›진단 화면으로 안내 (무엇이 없는지 담당자가 읽고 조치)
- 키 배포 정책(담당자 개별 발급 vs 공용 키)은 배포 전 사용자 결정 사항 — 특히 eleven 은
  글자수 과금이라 공용 키 공유 시 소진이 빠르다

## 에이전트 — 이중 제공자 (D15 · [05_agent](05_agent.md) 갱신분)

에이전트는 v1 에 포함하되 제공자를 추상화한다. 전환 스위치는 **설정 화면**.

```
AGENT_PROVIDER=claude|openai    AGENT_TEST_MODE=1 → 최저가 모델 강제
claude: 기존 claude-agent-sdk 경로 그대로 · 테스트 = claude-haiku-4-5 ($1/$5 MTok — 4단계 실측 $0.46/편)
openai: OPENAI_API_KEY·OPENAI_MODEL — 구조화 생성 + 파일 기입은 우리 코드가 결정적으로 수행
```

## 제거 일정 — 시점이 완료 조건이다

| 대상 | 제거 시점 |
|---|---|
| `api/` (FastAPI ~850줄) + fastapi·uvicorn·sse-starlette·watchfiles 의존성 | **5-2 facade 추출 완료 시** — 라우터 안의 순수 로직(`_path_issues`·`_save_with_ifmatch`·`_title_frame_url` 등)을 core 로 내린 뒤 |
| ~~`web/` (Vue ~1,595줄)~~ | **삭제 완료 (2026-08-21 — D16, 5-5 앞당김).** `api/` 삭제로 이미 실행 불가였고, 이식 대조본은 커밋 `a731a62` 가 보관 |
| `engine/` 의 미사용 lib(record·presenter) | **제거 안 함** — 엔진 무수정 원칙 |
| ~~`projects/` 검증 잔재(bread-basics*·test)~~ | **삭제 완료 (2026-08-21 사용자 지시).** 픽스처 정본은 `fixtures/projects/hr-basics*` |

## 단계 계획 (5단계 — 세부 체크리스트는 [BUILD_LOOP](../BUILD_LOOP.md))

| 하위 | 내용 | 수용 기준 |
|---|---|---|
| 5-0 | 위험 스파이크 | ① PATH 빈 환경 + 번들 경로 주입만으로 픽스처 빌드 성공(임시 폴더 복사본·`--out` 외부 지정) ② PySide6 60줄로 course-intro.html 프리뷰 + `getAnimations` 시킹 동작 ③ edge-tts 셔틀만으로 TTS 합성 |
| 5-1 | env.py + engine_io 보강 | 위 "이관 시 함께 고치는 결함" 6종 반영 · 기존 pytest 전건 통과 |
| 5-2 | facade 추출 → api/ 삭제 | 라우터가 facade 껍데기化 → API 테스트 5종을 facade 직접 호출로 재작성 → api/ 삭제 후에도 스위트 통과 |
| 5-3 | Qt 셸 + 읽기 콘솔 | 대시보드·보드·회차(빌드+진행 로그·프레임·mp4 재생) — 1단계 수용 기준의 Qt 등가를 실측 |
| 5-4 | 편집 ①②③ + 스캐폴딩 | 2단계 수용 기준의 Qt 등가 (개설→회차 생성→빌드, 라운드트립 diff 0 유지) |
| 5-5 | ⑤ 본체 + ④⑥⑦ (web/ 는 D16 으로 선삭제) | 3단계 수용 기준의 Qt 등가 — 새 회차를 화면만으로 완성, 결함 4종 입력 차단 실측 |
| 5-6 | 에이전트 이중 제공자 + 설정 화면 | claude(하이쿠)·openai 양 경로로 초안→평가 완주 · AGENT_TEST_MODE 실측 |
| 5-7 | 설치본 | 깨끗한 Windows PC(개발 도구 없음)에서 설치→위저드→픽스처 빌드 성공 |
| 5-8 | 배포 준비 | 코드 서명 · 라이선스 고지(PySide6 LGPL·ffmpeg·폰트) · 사용 안내 · 업데이트 경로 |

기간 추정: 1인 6~8주. 5-0~5-2(약 1주)가 끝나면 되돌릴 수 없는 결정이 전부 실측 검증된 상태가 된다.
