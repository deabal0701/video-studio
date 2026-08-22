# Video Studio

강좌(시리즈) 영상 제작 스튜디오 — **로컬 단독 설치형 Windows 데스크톱 앱**(PySide6)으로
담당자에게 배포하고, 이후 상용 서비스로 키운다. 대본·설정을 화면에서 편집하고, 버튼
하나로 빌드(TTS→렌더→합성)하고, 프레임 검수와 유튜브 업로드 준비물까지 받아 가는 앱.

> **전환 중 (2026-08-21 — [07_desktop.md](docs/design/07_desktop.md)):** 1~4단계는 웹
> (Vue+FastAPI) 콘솔로 구현·검증 완료. 5단계에서 같은 core 위의 PySide6 앱으로 교체하는 중이며
> **구 웹 콘솔 `api/`·`web/` 은 둘 다 삭제됐다** — 실행 진입점은 `app/` 하나다.
> Qt 화면은 5-4 까지 완료 — 읽기 콘솔·빌드·검수 + **강좌 편집(①③·위저드·회차 생성)**. ⑤ 대본 에디터는 5-5.
> 구 Vue 화면을 대조해야 하면 `git show a731a62:web/src/components/ClipEditor.vue` 로 꺼내 본다.

> **설계 정본 = [docs/design/](docs/design/README.md)** — 아키텍처·데이터 모델·화면·API·
> 에이전트·로드맵 전부. 작업 착수 전 [docs/design/00_overview.md](docs/design/00_overview.md)의
> 결정 표(D1~D10)를 먼저 읽는다.

## 구조

```
docs/design/       설계서 (정본)
.claude/skills/    develop-video · develop-lecture — 제작 규약 SSOT (에이전트가 읽는다)
engine/            Node CLI 렌더 엔진 (vendored — 수정 금지, ENGINE_VERSION.md 참조)
core/              Python — 로직 전부 (env·facade·storage·paths·schema·validate·indexer·jobs·engine_io)
app/               PySide6 데스크톱 UI — 실행 진입점 (`python -m app`)
run.ps1 · run.bat  실행 런처 (준비 자동화 — 아래 "실행")
packaging/         setup-qt-venv.ps1 (패키징 5-7 전용 후보) · PyInstaller·Inno Setup (5-7 예정)
projects/          사용자 데이터 (강좌·회차 — 파일이 SSOT)
fixtures/projects/ 개발·테스트 픽스처 (hr-basics 강좌 실전 대본)
tests/             core 단위 테스트 (경로 계산기 최우선)
```

## 실행

```powershell
.\run.ps1              # 앱 실행 (데이터 = projects\) — 준비가 안 돼 있으면 알아서 준비하고 띄운다
.\run.ps1 -Fixtures    # 데이터 = fixtures\projects (개발용 hr-basics)
.\run.ps1 -Setup       # 준비만 (최초 1회 — PySide6(conda-forge) · engine 의존성)
.\run.ps1 -Test        # pytest (conda penv3.13-insait) — 101건
```

`run.bat` 은 같은 것을 실행 정책 우회로 감싼 것이다(더블클릭·cmd 용).

전제: Node 20+ · ffmpeg/ffprobe · conda `penv3.13-insait` — **파이썬은 이 하나다**
(2026-08-21 통일). PySide6 는 pip 휠이 아니라 **conda-forge 빌드**를 쓴다(pip 휠은 conda
파이썬에서 Qt6Core DLL 충돌 — [.claude/memory/pyside6-environment.md](.claude/memory/pyside6-environment.md)).

런처 없이 손으로 하면:

```powershell
conda run -n penv3.13-insait pip install -e ".[dev]"    # core · 테스트
conda install -n penv3.13-insait -c conda-forge pyside6 qt6-webengine qt6-multimedia
cd engine; npm install; npx playwright install chromium; cd ..
conda run --no-capture-output -n penv3.13-insait python -m app   # 실행
```

미디어 소재(무료 스톡 — 저장소에 없음)는 CATALOG 출처에서 받는다:

```bash
node engine/assets/fetch.js broll https://videos.pexels.com/video-files/8033300/8033300-hd_1920_1080_25fps.mp4 office-talk.mp4
node engine/assets/fetch.js bgm https://assets.mixkit.co/music/623/623.mp3 mixkit-623.mp3
# (루프판 bgm/mixkit-623-loop.mp3 파생 방법은 engine/assets/CATALOG.md)
node engine/check-tts.js        # TTS·ffmpeg 점검 (edge — 키 불요)
```

에이전트(선택 기능)는 선택한 제공자의 키가 있어야 켜진다 — `AGENT_PROVIDER=claude|openai`,
키는 `.env` 의 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, 테스트는 `AGENT_TEST_MODE=1`(최저가
모델 강제 — D15). 키가 없어도 앱의 나머지 전부(편집·빌드·검수·배포)는 완결 동작한다.

## 배포본 빌드

```powershell
.\packaging\build-installer.ps1               # 동결 → 런타임 → 라이선스 → 스모크 → 설치기
.\packaging\build-installer.ps1 -SkipFreeze   # 동결 건너뛰고 나머지만 (반복 실행용)
```

한 명령이 5단계를 순서대로 밟고, **스모크가 실패하면 설치기를 만들지 않는다**(깨진 설치본이
나가는 것보다 안 나가는 게 낫다). 산출물은 `dist\VideoStudio\`(약 1.3GB — 내역은
[07_desktop.md](docs/design/07_desktop.md) 용량 표), 설치기는 Inno Setup(ISCC)이 있을 때 생성된다.

**동결만은 conda 가 아니라 `.qt-venv`(pip 휠)에서 한다** — conda-forge 는 Qt 자산을 파이썬
패키지 밖(`Library\bin`)에 두어 PyInstaller 훅이 빈손이 된다. 스크립트가 `.qt-venv` 를
알아서 만든다 ([08_qt-style.md](docs/design/08_qt-style.md) §9 의 배치 대조표).

남은 준비물: **Inno Setup**(설치기 생성) · **코드 서명 인증서**(없으면 SmartScreen 차단 —
`.iss` 의 SignTool 절은 채우기만 하면 되게 예약돼 있다) · **깨끗한 Windows PC**(설치 실측).

## 진행 상태

구현 진행의 SSOT = **[docs/BUILD_LOOP.md](docs/BUILD_LOOP.md)** (단계 표·수용 기준 실측
기록·세션 재개 프로토콜). 요약은 [CLAUDE.md](CLAUDE.md) 체크박스.
