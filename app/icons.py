"""아이콘 — **코드로 그린다**. 이모지·이미지 파일을 쓰지 않는다.

이모지는 OS 폰트가 제멋대로 그린다(⬜→체크박스, 🔄→END 화살표 실측)는 이유로 08 §5 가
금지했고 `tests/test_repo_hygiene.py` 가 집행한다. 그래서 아이콘이 필요해지면 답은
**QPainter 로 직접 그리기**다:

- 어느 PC 에서나 같은 그림 (폰트·아이콘 테마에 의존하지 않는다)
- 색을 인자로 받으므로 프로젝트 브랜드 색으로 칠할 수 있다
- 파일이 없으니 동결본에 뭘 더 넣을 것도 없다

좌표는 24×24 격자에 그리고 필요한 크기로 렌더한다. 화면 배율(devicePixelRatio)을 곱해
그려야 고DPI 에서 뭉개지지 않는다.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF)

GRID = 24.0


def _canvas(size: int, ratio: float) -> tuple[QPixmap, QPainter]:
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.setDevicePixelRatio(ratio)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    # setDevicePixelRatio 를 준 QPixmap 은 **논리 좌표가 이미 size** 다 —
    # 여기에 ratio 를 또 곱하면 두 배로 그려져 잘린다 (2026-08-22 실측)
    p.scale(size / GRID, size / GRID)
    return px, p


def _stroke(p: QPainter, color: str, width: float = 1.9) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)


# ── 낱개 그림 (24×24 격자) ───────────────────────────────────────────────────
def _draw_dashboard(p: QPainter, color: str) -> None:
    """네 칸 격자 — 여러 프로젝트를 한눈에."""
    _stroke(p, color)
    for x, y in ((4, 4), (13.5, 4), (4, 13.5), (13.5, 13.5)):
        p.drawRoundedRect(QRectF(x, y, 6.5, 6.5), 1.6, 1.6)


def _draw_library(p: QPainter, color: str) -> None:
    """겹친 판 — 쌓여 있는 소재."""
    _stroke(p, color)
    p.drawRoundedRect(QRectF(4, 5, 16, 5.5), 1.6, 1.6)
    p.drawLine(6, 13, 18, 13)
    p.drawLine(7.5, 16.5, 16.5, 16.5)
    p.drawLine(9, 19.5, 15, 19.5)


def _draw_jobs(p: QPainter, color: str) -> None:
    """점 + 줄 세 벌 — 줄 서 있는 작업."""
    _stroke(p, color)
    for y in (6.5, 12, 17.5):
        p.drawEllipse(QRectF(4, y - 1.4, 2.8, 2.8))
        p.drawLine(10, y, 20, y)


def _draw_settings(p: QPainter, color: str) -> None:
    """슬라이더 세 줄 — 톱니바퀴는 작게 그리면 뭉개진다."""
    _stroke(p, color)
    for y, knob in ((6.5, 15.5), (12, 8.5), (17.5, 13)):
        p.drawLine(4, y, 20, y)
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(knob - 1.9, y - 1.9, 3.8, 3.8))
        p.setBrush(Qt.NoBrush)


def _draw_film(p: QPainter, color: str, *, stacked: bool) -> None:
    """필름 한 칸 — 프로젝트. 시리즈면 두 장을 겹쳐 '여러 편'을 드러낸다."""
    _stroke(p, color)
    if stacked:
        p.drawRoundedRect(QRectF(3, 4.5, 15, 12), 2.0, 2.0)
        body = QRectF(6, 7.5, 15, 12)
    else:
        body = QRectF(4.5, 6, 15, 12)
    p.setBrush(QColor(color))
    p.setOpacity(0.14)
    p.drawRoundedRect(body, 2.0, 2.0)
    p.setOpacity(1.0)
    _stroke(p, color)
    p.drawRoundedRect(body, 2.0, 2.0)
    # 재생 삼각형 — 이게 있어야 '영상'으로 읽힌다
    cx, cy = body.center().x(), body.center().y()
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(cx - 1.8, cy - 2.8), QPointF(cx + 2.8, cy),
                             QPointF(cx - 1.8, cy + 2.8)]))


_SHAPES = {
    "dashboard": _draw_dashboard,
    "library": _draw_library,
    "jobs": _draw_jobs,
    "settings": _draw_settings,
}


# ── 밖에서 쓰는 것 ───────────────────────────────────────────────────────────
def nav(name: str, color: str, size: int = 18, ratio: float = 2.0) -> QIcon:
    """내비 아이콘. 모르는 이름이면 빈 아이콘 — 화면이 죽지 않는다."""
    draw = _SHAPES.get(name)
    if draw is None:
        return QIcon()
    px, p = _canvas(size, ratio)
    try:
        draw(p, color)
    finally:
        p.end()
    return QIcon(px)


def project(brand: str, *, series: bool = False, size: int = 22,
            ratio: float = 2.0) -> QIcon:
    """프로젝트 아이콘 — **그 프로젝트의 브랜드 색**으로 칠한 필름.

    색이 곧 프로젝트 정체성이라(팔레트가 타이틀 카드에 그대로 쓰인다) 목록에서
    색만 보고도 어느 프로젝트인지 알아본다.
    """
    px, p = _canvas(size, ratio)
    try:
        _draw_film(p, brand or "#5B8DEF", stacked=series)
    finally:
        p.end()
    return QIcon(px)
