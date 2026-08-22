# PySide6 실행 환경 — conda penv3.13-video 하나 (2026-08-22 재통일)

## 한 줄 규칙

**모든 것이 conda `penv3.13-video` 다** — 개발·pytest·앱 실행·캡처·**동결(PyInstaller)까지**.
설치는 전부 pip: `pip install PySide6 pydantic pytest pytest-timeout claude-agent-sdk openai
edge-tts pyinstaller`. `run.ps1 -Setup` 이 자동으로 한다. `.qt-venv` 는 은퇴했다(삭제됨).

## 이력 — 왜 두 번 바뀌었나

1. **2026-08-21**: penv3.13-insait 에서 pip 휠 PySide6 가 Qt6Core.dll WinError 127 로
   죽어 conda-forge 빌드로 갔다. 동결은 conda-forge 배치(Qt 자산이 site-packages 밖
   `$PREFIX\Library\`)를 PyInstaller 훅이 못 찾아(실측 0개 vs pip 휠 144개 DLL)
   별도 `.qt-venv` 를 뒀다 — 환경이 둘.
2. **2026-08-22**: insait 와 분리하려고 깨끗한 `penv3.13-video` 를 만들어 보니
   **pip 휠 PySide6 가 정상**. WinError 127 의 진범은 conda 가 아니라 **insait env 의
   DLL 오염**(수많은 `Libraryin` DLL — libffi 승격으로 ctypes 까지 깨져 있었다)이었다.
   pip 휠이면 PyInstaller 훅도 정상이라 **동결까지 한 env 로 합쳐졌다**. 검증:
   pytest 141 · GUI 스모크(프리뷰 로드·고유색 34) · 동결 Qt DLL 42종+WebEngineProcess+icudtl.

## 지키는 것

- **이 env 에 conda 패키지를 더하지 않는다** — 특히 ffmpeg (conda-forge ffmpeg 9.0.1 은
  libass 없음 — `ass` 필터가 없어 빌드가 합성에서 죽는다. 시스템 ffmpeg 를 쓰는 것이 맞고,
  자가진단 "ffmpeg 자막" 행이 지킨다). Qt 도 conda-forge 로 다시 깔면 훅이 빈손이 된다.
- insait 는 인사이트 프로젝트 전용으로 돌려놨다 (pyside6·qt6-*·claude-agent-sdk 제거).
  insait 의 `Libraryinfi.dll` 사본은 남겨 뒀다 — libffi 3.7 승격이 깨뜨린 ctypes 의
  복구라 지우면 그 env 의 ctypes 가 다시 죽는다.

## 함께 알아둘 것

- QWebEngineView: DOM·URL 질의 params·`getAnimations` currentTime 시킹 전부 동작.
  `view.grab()` 이 공백이라던 5-0 관찰은 **원인이 로드 실패였다** — `app/bootstrap.py` 의
  Chromium 플래그(`--disable-gpu --no-sandbox --disable-gpu-compositing`)를 주면
  offscreen 에서도 픽셀이 정상 캡처된다 (2026-08-22 재실측: 플래그 없음 → loadFinished
  ok=False·고유색 1 / 있음 → ok=True·고유색 8). 정본 규칙은 docs/design/08_qt-style.md §6·§9.
- offscreen 플랫폼은 한글 폰트를 못 잡아 두부(□)로 보인다 — **단 Qt 위젯 텍스트에 한정**.
  QWebEngineView 안의 웹 콘텐츠는 offscreen 에서도 한글이 정상 렌더된다 (2026-08-22 실측).
- 모션 문서는 투명/와이프 규약: 프리뷰에 실제 클립 params 전체(wipe 포함)를 넘겨야 실물과 같다.
- Qt 스레딩: 시그널→클로저 연결은 direct(워커 실행), QRunnable autoDelete 는 큐드 전달 유실
  → **영속 디스패처(app/bridge.py)** 경유가 이 앱의 규약.
