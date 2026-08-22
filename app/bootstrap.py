"""bootstrap — QApplication 생성 **전에** 끝나야 하는 설정 (임포트만으로 적용).

QtWebEngine(⑤ 프리뷰 — D10) 은 두 가지를 기동 전에 요구한다:

1. **QApplication 보다 먼저 임포트** — QtWebEngineWidgets 임포트가 AA_ShareOpenGLContexts
   를 세우기 때문. 늦게 임포트하면 경고/미동작.
2. **GPU 실패 시 소프트웨어 렌더링 폴백** — 2026-08-22 실측: 이 PC(offscreen·가상 GPU)에서
   플래그 없이는 `loadFinished(ok=False)` 로 **페이지가 아예 안 뜬다**. 플래그를 주면
   "Failed to create GLES3 context, fallback to GLES2" 경고만 남기고 정상 로드된다.
   담당자 PC 의 GPU·드라이버 사정은 제각각이라 설치본에서도 이 폴백이 필요하다.

`QTQUICK`/`QT_QPA_PLATFORM` 등 호출자가 이미 정한 값은 덮지 않는다.
"""

from __future__ import annotations

import os

_FLAGS = "--disable-gpu --no-sandbox --disable-gpu-compositing"
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", _FLAGS)

# QApplication 보다 먼저 — 임포트 자체가 목적 (AA_ShareOpenGLContexts)
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402,F401
