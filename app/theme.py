"""theme — D11 디자인 토큰의 **정본** (apple.com 실측값).

화면 코드에 색·간격·라운드를 하드코딩하지 않는다 — 여기 상수와 STYLESHEET 만 쓴다.
web/ 삭제(2026-08-21)로 구 web/src/styles/tokens.css 의 정본 지위를 이 모듈이 승계했다
(03_screens 공통 규칙 · D16).
"""

# ── 색 — 표면 ────────────────────────────────────────────────────────────────
BG_PAGE = "#f5f5f7"
BG_SURFACE = "#ffffff"
BG_DARK = "#161617"          # 로그·코드 패널

# ── 색 — 텍스트 ──────────────────────────────────────────────────────────────
INK = "#1d1d1f"
INK_2 = "#6e6e73"
INK_3 = "#86868b"

# ── 색 — 선·상태 ─────────────────────────────────────────────────────────────
SEPARATOR = "#d2d2d7"
ACCENT = "#0071e3"
ACCENT_HOVER = "#0077ed"
ACCENT_SOFT = "#f0f6fd"
SUCCESS = "#34c759"
WARNING = "#ff9500"
DANGER = "#ff3b30"

# ── 타이포·리듬 ──────────────────────────────────────────────────────────────
FONT_STACK = "'Segoe UI', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
TEXT_TITLE = 28
TEXT_SECTION = 17
TEXT_BODY = 14
TEXT_CAPTION = 12
RADIUS_CARD = 18
RADIUS_CONTROL = 8
GAP_CARD = 20
GAP_SECTION = 40
GAP_STACK = 16
PAGE_PAD = 22
RD_FIELD = 720               # 입력 필드 최대 폭 — 읽는 폭 제한 (08_qt-style §4)
CARD_W = 320                 # 카드 폭 상한 — 1장일 때 화면 폭으로 늘어나는 것 방지 (09 G3)
VIDEO_H = 300                # 검수 영상 높이 — 재생 눌렀을 때만 이만큼 펼친다 (09 G1)
THUMB_H = 180                # 검수 프레임 썸네일 높이 — 96 은 자막이 안 읽혔다

# ── 아이콘 정책 (09 G4) ──────────────────────────────────────────────────────
# **의미를 이모지에 싣지 않는다.** 이모지는 OS 폰트가 제멋대로 그린다 — 실측(2026-08-22):
#   ⬜ → 체크박스 아이콘 · 🔄 → "END" 화살표 · ✅ → 초록 체크 · 🏠🎞⚙🔧 → 크기·색 제각각
# 상태는 **색 점 + 한국어 라벨**로 말한다. dot() 는 그 색 점을 만든다.
STATE_COLORS = {"empty": INK_3, "wip": WARNING, "done": SUCCESS}


def dot(color: str, size: int = 9) -> str:
    """상태 색 점 — QLabel 에 styleSheet 로 붙인다 (텍스트 없는 원)."""
    return (f"background: {color}; border-radius: {size // 2}px;"
            f" min-width: {size}px; max-width: {size}px;"
            f" min-height: {size}px; max-height: {size}px;")


def make_palette():
    """라이트 팔레트 명시 — OS 다크모드가 QSS 미적용 위젯을 오염시키는 것을 차단 (08 §1·§2).

    QSS 보다 먼저 `app.setPalette()` 로 건다. QSS 가 안 덮은 모든 색 역할의 폴백이
    이 팔레트가 되므로, Windows 테마와 무관하게 offscreen 캡처 = 실창이 된다.
    """
    from PySide6.QtGui import QColor, QPalette

    p = QPalette()
    c = QColor
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        p.setColor(group, QPalette.Window, c(BG_PAGE))
        p.setColor(group, QPalette.Base, c(BG_SURFACE))
        p.setColor(group, QPalette.AlternateBase, c(BG_PAGE))
        p.setColor(group, QPalette.Text, c(INK))
        p.setColor(group, QPalette.WindowText, c(INK))
        p.setColor(group, QPalette.Button, c(BG_SURFACE))
        p.setColor(group, QPalette.ButtonText, c(INK))
        p.setColor(group, QPalette.ToolTipBase, c(BG_SURFACE))
        p.setColor(group, QPalette.ToolTipText, c(INK))
        p.setColor(group, QPalette.PlaceholderText, c(INK_3))
        p.setColor(group, QPalette.Highlight, c(ACCENT))
        p.setColor(group, QPalette.HighlightedText, c("#ffffff"))
    p.setColor(QPalette.Disabled, QPalette.Text, c(INK_3))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, c(INK_3))
    return p


STYLESHEET = f"""
* {{ font-family: {FONT_STACK}; font-size: {TEXT_BODY}px; color: {INK}; }}
QMainWindow, QStackedWidget > QWidget {{ background: {BG_PAGE}; }}

/* 툴팁 — 반드시 QSS 로 명시한다. 팔레트(ToolTipBase/Text)만으로는 Windows 다크 모드가
   덮어써 검정 배경에 검정 글자가 됐다 (2026-08-22 실측 — "글자가 안 보인다").
   border-radius 는 쓰지 않는다: 툴팁은 네이티브 창이라 모서리 밖이 검게 남는다. */
QToolTip {{
  background: {BG_SURFACE}; color: {INK};
  border: 1px solid {SEPARATOR}; padding: 6px 10px;
}}

/* 입력 위젯 — 흰 배경·테두리 명시 (OS 테마 차단, 08 §5. border 는 background 와 세트) */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
  background: {BG_SURFACE}; border: 1px solid {SEPARATOR};
  border-radius: {RADIUS_CONTROL}px; padding: 5px 10px;
  selection-background-color: {ACCENT}; selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
  border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {{
  background: {BG_PAGE}; color: {INK_3};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
  background: {BG_SURFACE}; border: 1px solid {SEPARATOR};
  selection-background-color: {ACCENT_SOFT}; selection-color: {ACCENT};
}}

/* 좌측 내비 */
QListWidget#nav {{
  background: {BG_SURFACE}; border: none; border-right: 1px solid {SEPARATOR};
  padding-top: 8px; outline: none;
}}
QListWidget#nav::item {{ padding: 9px 16px; border: none; color: {INK_2}; }}
QListWidget#nav::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT};
  border-left: 3px solid {ACCENT}; }}

/* 카드·패널 */
QFrame#card {{ background: {BG_SURFACE}; border: 1px solid {SEPARATOR};
  border-radius: {RADIUS_CARD}px; }}
QFrame#panel {{ background: {BG_SURFACE}; border: 1px solid {SEPARATOR};
  border-radius: 12px; }}

/* 텍스트 위계 */
QLabel#pageTitle {{ font-size: {TEXT_TITLE}px; font-weight: 700; }}
QLabel#pageDesc {{ color: {INK_2}; }}
QLabel#sectionTitle {{ font-size: {TEXT_SECTION}px; font-weight: 600; }}
QLabel#caption {{ font-size: {TEXT_CAPTION}px; color: {INK_3}; }}

/* 버튼 — pill (D11) */
QPushButton {{ background: {BG_SURFACE}; border: 1px solid {SEPARATOR};
  border-radius: 15px; padding: 5px 16px; }}
QPushButton:hover {{ border-color: {INK_3}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#danger {{ color: {DANGER}; border-color: {DANGER}; }}
QPushButton:disabled {{ color: {INK_3}; border-color: {SEPARATOR}; background: {BG_PAGE}; }}

/* 상태 칩 — 5종. 색이 곧 뜻이므로 새 색을 만들지 말고 이 중에서 고른다 (08 §5)
   info 중립 · run 진행 중(파랑) · warn 주의(주황) · ok 성공 · err 실패
   run 은 2026-08-22 에 주황→파랑으로 옮겼다: warn 이 생기며 주황이 "주의" 로 갔고,
   진행 중을 주의색으로 칠하면 정상 빌드가 경고처럼 보였다. */
/* 카드 구석 삭제 — 평소엔 옅게, 올리면 위험색 (10: "삭제가 보이지 않는다") */
QPushButton#cardDelete {{ border: none; background: transparent; color: {INK_3};
  padding: 2px 8px; font-size: 12px; }}
QPushButton#cardDelete:hover {{ color: {DANGER}; font-weight: 700; }}

/* 팔레트 프리셋 — 선택된 것이 한눈에 (10: "선택한 내용이 선택이 안 된다") */
QPushButton#palettePreset {{ padding: 8px 14px; border: 2px solid {SEPARATOR};
  border-radius: 10px; background: {BG_SURFACE}; }}
QPushButton#palettePreset:checked {{ border: 2px solid {ACCENT};
  background: {ACCENT_SOFT}; font-weight: 700; }}

QLabel[chip="info"] {{ background: {BG_PAGE}; color: {INK_2};
  border-radius: 11px; padding: 2px 12px; }}
QLabel[chip="run"] {{ background: {ACCENT_SOFT}; color: {ACCENT};
  border-radius: 11px; padding: 2px 12px; }}
QLabel[chip="warn"] {{ background: #fff3e0; color: {WARNING};
  border-radius: 11px; padding: 2px 12px; }}
QLabel[chip="ok"] {{ background: #e8f7ee; color: {SUCCESS};
  border-radius: 11px; padding: 2px 12px; }}
QLabel[chip="err"] {{ background: #fdecea; color: {DANGER};
  border-radius: 11px; padding: 2px 12px; }}

/* 로그 패널 */
QPlainTextEdit#log {{ background: {BG_DARK}; color: #e8e8ed; border: none;
  border-radius: 12px; padding: 10px; font-family: Consolas, monospace;
  font-size: {TEXT_CAPTION}px; }}

/* 탭 */
QTabBar::tab {{ padding: 7px 18px; background: transparent; color: {INK_3};
  border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
QTabWidget::pane {{ border: none; }}

/* 표 */
QTableWidget {{ background: {BG_SURFACE}; border: 1px solid {SEPARATOR};
  border-radius: 12px; gridline-color: {SEPARATOR}; }}
QHeaderView::section {{ background: {BG_SURFACE}; border: none;
  border-bottom: 1px solid {SEPARATOR}; padding: 6px 10px; color: {INK_3};
  font-size: {TEXT_CAPTION}px; }}

QStatusBar {{ background: {BG_SURFACE}; border-top: 1px solid {SEPARATOR}; }}
QScrollArea {{ border: none; background: transparent; }}
"""
