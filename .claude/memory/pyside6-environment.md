# PySide6 실행 환경 — conda 로 통일 (2026-08-21 확정)

**파이썬은 conda `penv3.13-insait` 하나다** — core·pytest·앱(PySide6) 전부.
단, PySide6 는 **pip 휠 금지, conda-forge 빌드 필수**:

```
conda install -n penv3.13-insait -c conda-forge pyside6 qt6-webengine qt6-multimedia
```

## 왜 (5-0~5-4 실측 이력)

- **pip 휠 PySide6 는 conda 파이썬에서 Qt6Core.dll 로드 실패** (WinError 127 —
  PATH 정리·MSVC 런타임 대조로도 해결 안 됨. conda 파이썬의 DLL 배치와 충돌).
- conda-forge 가 conda 생태계에 맞게 빌드한 pyside6 는 정상. **WebEngine·Multimedia 는
  별도 패키지**(`qt6-webengine`·`qt6-multimedia`) — 빼먹으면 해당 임포트만 "모듈 없음".
- 공유 env 영향 실측: libexpat·libffi·openssl 빌드 승격뿐 (dry-run 확인 완료).
- 통일 검증: 앱 스모크(대시보드→회차→검수 프레임 5장) conda 파이썬으로 통과.
- 한때 python.org venv(.qt-venv) 우회를 썼다 — 폐기. `packaging/setup-qt-venv.ps1` 은
  **PyInstaller 패키징(5-7)에서만** 재평가 (동결 빌드는 비-conda 가 정석일 수 있음).

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
