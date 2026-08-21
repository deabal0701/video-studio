# Video Studio

강좌(시리즈) 영상 제작 스튜디오 — 웹 앱으로 시작해 상용 서비스로 키운다.
대본·설정을 화면에서 편집하고, 버튼 하나로 빌드(TTS→렌더→합성)하고, 프레임 검수와
유튜브 업로드 준비물까지 받아 가는 앱.

> **설계 정본 = [docs/design/](docs/design/README.md)** — 아키텍처·데이터 모델·화면·API·
> 에이전트·로드맵 전부. 작업 착수 전 [docs/design/00_overview.md](docs/design/00_overview.md)의
> 결정 표(D1~D10)를 먼저 읽는다.

## 구조

```
docs/design/       설계서 (정본)
.claude/skills/    develop-video · develop-lecture — 제작 규약 SSOT (에이전트가 읽는다)
engine/            Node CLI 렌더 엔진 (vendored — 수정 금지, ENGINE_VERSION.md 참조)
core/              Python — 로직 전부 (storage·paths·schema·validate·indexer·jobs·engine_io)
api/               FastAPI (REST + SSE)
web/               Vue 3 (Vite + Element Plus + Tailwind)
projects/          사용자 데이터 (강좌·회차 — 파일이 SSOT)
fixtures/projects/ 개발·테스트 픽스처 (hr-basics 강좌 실전 대본)
tests/             core 단위 테스트 (경로 계산기 최우선)
```

## 실행

전제: Node 20+ · ffmpeg/ffprobe · conda 환경 `penv3.13-insait` (Python 3.13).

```bash
# 1회 준비
cd engine && npm install && npx playwright install chromium && cd ..
conda run -n penv3.13-insait pip install -e ".[dev]"
# 미디어 소재(무료 스톡 — 저장소에 없음)는 CATALOG 출처에서 받는다:
node engine/assets/fetch.js broll https://videos.pexels.com/video-files/8033300/8033300-hd_1920_1080_25fps.mp4 office-talk.mp4
node engine/assets/fetch.js bgm https://assets.mixkit.co/music/623/623.mp3 mixkit-623.mp3
# (루프판 bgm/mixkit-623-loop.mp3 파생 방법은 engine/assets/CATALOG.md)

# 앱 (개발 — 픽스처를 데이터로)
VIDEO_STUDIO_PROJECTS=fixtures/projects conda run -n penv3.13-insait uvicorn api.main:app --port 8000
npm --prefix web run dev        # http://localhost:5173

# 검증
conda run -n penv3.13-insait python -m pytest -q     # 77건
node engine/check-tts.js                             # TTS 확인 (edge — 키 불요)
```

에이전트(4단계·선택 기능)는 `.env` 의 `ANTHROPIC_API_KEY` 가 있어야 켜진다 — 없어도
앱의 나머지 전부(편집·빌드·검수·배포)는 완결 동작한다.

## 진행 상태

구현 진행의 SSOT = **[docs/BUILD_LOOP.md](docs/BUILD_LOOP.md)** (단계 표·수용 기준 실측
기록·세션 재개 프로토콜). 요약은 [CLAUDE.md](CLAUDE.md) 체크박스.
