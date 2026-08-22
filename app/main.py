"""진입점 — `python -m app` (conda penv3.13-insait). 저장소 루트를 sys.path 에 보장한다."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import bootstrap  # noqa: E402,F401 — QApplication 이전에 끝나야 하는 설정
from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    from app import i18n, theme

    i18n.install_korean(app)   # Qt 표준 버튼("Cancel"·"Yes") 한국어화 (09 G6)
    from app.main_window import MainWindow

    # 3층 스타일 규칙 — 이 순서 고정 (08_qt-style §1: 스타일 → 팔레트 → QSS)
    app.setStyle("Fusion")
    app.setPalette(theme.make_palette())
    app.setStyleSheet(theme.STYLESHEET)
    win = MainWindow()

    # 동결본 스모크 (5-7) — VS_SMOKE_OUT 이 있으면 자가검사만 하고 종료한다.
    # 설치본이 "혼자서" 뜨는지(플랫폼 플러그인·엔진 경로·WebEngine)를 실측하는 경로.
    if os.environ.get("VS_SMOKE_OUT"):
        from app.smoke_probe import run_probe

        return run_probe(app, win)

    # 첫 실행 위저드 — 설치본에서 1회 (07). 건너뛰어도 앱은 그대로 뜬다
    from app.pages.first_run import FirstRunWizard, needs_first_run

    if needs_first_run():
        FirstRunWizard(win.make_studio, win).exec()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
