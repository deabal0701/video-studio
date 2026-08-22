"""Qt 표준 문구를 한국어로 (09 G6).

Qt 가 스스로 그리는 버튼·메뉴는 우리 문자열이 아니다 — `QDialogButtonBox.Cancel` 은
"Cancel", `QMessageBox.question` 은 "Yes"/"No" 로 나온다 (2026-08-22 실측: 새 강좌
위저드에 영문 "Cancel" 이 그대로 보였다). Qt 가 함께 배포하는 `qtbase_ko.qm` 을 얹으면
표준 문구 전체가 한 번에 한국어가 된다.

번역 파일이 없는 환경(동결본에서 누락 등)에서도 앱은 그대로 떠야 하므로 **최선 노력**이다.
우리 코드가 직접 쓰는 버튼은 번역 파일과 무관하게 한국어 문자열을 명시한다.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

_keep: list[QTranslator] = []   # GC 되면 번역이 풀린다 — 앱 수명 동안 붙잡아 둔다


def install_korean(app) -> bool:
    """`qtbase_ko.qm` 을 찾아 얹는다. 성공하면 True."""
    roots = [Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath))]
    try:    # pip 휠은 패키지 안에 넣는다 (conda 는 Qt 쪽 경로만 있다)
        import PySide6

        roots.append(Path(PySide6.__file__).parent / "translations")
    except Exception:       # noqa: BLE001 — 번역은 있으면 좋은 것, 없다고 죽지 않는다
        pass
    for root in roots:
        qm = root / "qtbase_ko.qm"
        if not qm.exists():
            continue
        tr = QTranslator()
        if tr.load(str(qm)):
            app.installTranslator(tr)
            _keep.append(tr)
            QLocale.setDefault(QLocale(QLocale.Korean, QLocale.SouthKorea))
            return True
    return False
