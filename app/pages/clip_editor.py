"""⑤ 대본 에디터 — 3열 (03 ⑤ · 구 web ClipEditor.vue 의 Qt 이식, 5-5).

결함 차단 4종 (이 앱의 1원칙):
  ① 오타 params → 템플릿이 받는 키만 폼 생성 (자유 키 입력 없음, 안 받는 키는 빨간 목록+[제거])
  ② 상대경로 오류 → 피커로만 선택, 저장 시 경로 실존 검사(pathIssues)
  ③ 브랜드 색·폰트 누락 → 자동 주입 키는 "프로젝트 상속 중" 뱃지만 (폼 비노출)
  ④ B롤 길이 초과 → duration > 소스−videoStart 즉시 빨강

저장 응답의 etag 를 항상 채택한다 — 경로 문제가 있어도 다음 저장이 409 로 교착하지 않게
(구 웹 구현의 실결함 수정 — 2026-08-21 코드리뷰 3번).
"""

from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core import env, kinds, paths
from core.status import OUT_ROOT
# 강의 페이스(자/초)의 정본은 core.validate — 화면이 사본을 두면 갈라진다 (02 길이 계산)
from core.validate import CHARS_PER_SEC_LECTURE as PACE

from .. import theme
from ..bridge import error_text, guard, run_bg
from ..widgets import AudioPreview

SKELETON = ["broll", "title", "hook", "stinger", "promise"]
# 골격이 넣어 둔 자리표시자 표식 — core.scaffold 와 같은 규약("[…]" 로 시작·포함)
_PLACEHOLDER = "["
# 프로젝트가 자동 주입하는 키 — 폼 비노출, "상속 중" 뱃지만 (03 ⑤ 표 · 결함 차단 ③)
AUTO_KEYS = ("brand", "brandSoft", "bg", "fg", "font", "fontUrl",
             "wipeAt", "wipeColor")
TIME_KEY_RE = re.compile(r"^t\d|^tterm|At$|Time$", re.I)
# 화면 문구 폼의 표시 순서 — 제목이 맨 위 (10 지적 11: 템플릿 내부 순서 그대로면
# 제목이 맨 아래로 밀린다). 목록에 없는 키는 템플릿 순서대로 뒤에 붙는다.
PARAM_ORDER = ("title", "subtitle", "kicker", "num", "value", "unit",
               "text", "caption", "label", "src", "progress")


def spoken(clip: dict) -> str:
    """실제로 말할 내레이션 — 골격의 "[…]" 안내문은 **아직 쓴 글이 아니다**.

    54회차 P11: 시작 패널은 이 규칙(`_script_unwritten`)으로 "대본이 아직 비어 있습니다"
    라고 하는데 예산 게이지만 자리표시자까지 세서 같은 화면이 "232자 (13%)"라고 했다.
    규칙을 하나로 모아 패널·게이지·길이 추정이 같은 말을 하게 한다.
    """
    n = (clip.get("narration") or "").strip()
    return "" if n.startswith("[") else n


def clip_seconds(clip: dict, audio_cache: dict) -> tuple[float, bool]:
    """(길이 s, 실측 여부) — TTS 캐시 있으면 실측, 없으면 추정 (03 ⑤ 리스트 라벨)."""
    measured = audio_cache.get(clip.get("id"))
    if measured:
        return max(clip.get("duration") or 0, measured + 0.5), True
    narration = spoken(clip)
    if narration:
        return max(clip.get("duration") or 0,
                   len(narration) / PACE + 0.5), False
    return clip.get("duration") or 0, True


class PickerDialog(QDialog):
    """피커 공용 — 행 클릭으로 선택 (경로 문자열을 만지지 않는다, 결함 차단 ②).

    더블클릭은 지름길이고 정식 경로는 행 선택 → [선택] 버튼 — 더블클릭을 모르는
    초보자가 막히지 않게 (23회차 P15·P24). 빈 목록이면 표 대신 안내문을 보인다 (P9).
    """

    def __init__(self, title: str, headers: list[str], rows: list[list[str]],
                 parent=None, empty_text: str = "항목이 없습니다"):
        from PySide6.QtWidgets import QDialogButtonBox

        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 440)
        self.picked: int | None = None
        lay = QVBoxLayout(self)
        self.table = QTableWidget(len(rows), len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(cell))
        self.table.resizeColumnsToContents()
        self.table.cellDoubleClicked.connect(self._pick)
        lay.addWidget(self.table)
        if not rows:
            self.table.hide()
            empty = QLabel(empty_text)
            empty.setWordWrap(True)
            lay.addWidget(empty, 1, Qt.AlignCenter)
        hint = QLabel("행을 고르고 [선택] — 더블클릭해도 됩니다")
        hint.setObjectName("caption")
        if not rows:
            hint.hide()   # 고를 행이 없는데 고르라는 안내는 어색하다
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok = buttons.button(QDialogButtonBox.Ok)
        ok.setText("선택")
        ok.setObjectName("primary")
        ok.setEnabled(False)   # 고른 행이 있어야 눌린다 (P20)
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        self.table.itemSelectionChanged.connect(
            lambda: ok.setEnabled(self.table.currentRow() >= 0))
        buttons.accepted.connect(lambda: self._pick(self.table.currentRow(), 0))
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _pick(self, row: int, _col: int) -> None:
        if row < 0:
            return
        self.picked = row
        self.accept()


class _PreviewColumn(QWidget):
    """프리뷰를 16:9 로 잡아 두는 열.

    엔진 문서는 1920×1080 이라 위젯을 세로로 늘리면 문서 아래에 흰 띠가 남는다.
    폭이 정해질 때마다 높이를 다시 계산한다 (같은 값이면 건드리지 않는다 — 재귀 방지).
    """

    preview = None

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if self.preview is None:
            return
        want = round(self.preview.width() * 9 / 16)
        if self.preview.height() != want:
            self.preview.setFixedHeight(want)


class ClipEditorTab(QWidget):
    saved = Signal()          # 부모가 파생 상태 재조회
    tts_requested = Signal()  # [TTS 실측 갱신] — 부모의 잡 동선 재사용
    ai_requested = Signal(dict)  # AI 대본 — {"brief": ...} 또는 {"source": ...} (부모가 잡 제출)

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.eid: str | None = None
        self.doc: dict = {}
        self._etag: str | None = None
        self._inspect: dict = {}
        self._gallery: list[dict] = []
        self._brolls: list[dict] = []
        self._budget = 1850
        self._selected = -1
        self._loading = False
        self.audio = AudioPreview()

        split = QSplitter(Qt.Horizontal, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.addWidget(split)
        split.addWidget(self._make_left())
        split.addWidget(self._make_center())
        split.addWidget(self._make_right())
        split.setSizes([260, 520, 420])
        # 고정 픽셀 합(1200)이 창보다 넓으면 세 열이 비례로 눌리는데, **글 쓰는 가운데
        # 열이 먼저 무너졌다** — 1180px 실측에서 뷰포트 317 < 내용 최소 464 라 오른쪽이
        # 잘렸다(가로 스크롤은 금지 정책이라 그냥 사라진다). 가운데는 내용 최소폭을
        # 보장하고, 남는 폭을 줄일 곳은 프리뷰(오른쪽)로 (54회차 P6)
        split.setCollapsible(1, False)

    # ══ 좌: 클립 리스트 + 예산 ═══════════════════════════════════════════════
    def _make_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.skeleton_warn = QLabel("")
        self.skeleton_warn.setProperty("chip", "err")
        self.skeleton_warn.setWordWrap(True)
        self.skeleton_warn.hide()
        lay.addWidget(self.skeleton_warn)

        self.clip_list = QListWidget()
        self.clip_list.setDragDropMode(QAbstractItemView.InternalMove)  # 드래그 정렬 = 배열 순서
        # 골격의 자리표시자 이름("[회차 훅 도식 — 콜드 오픈. 구체…")이 길어 목록 아래에
        # 가로 스크롤바가 생겼다 (54회차 P6 — 좁은 창에서 가로 스크롤 금지).
        # 잘린 라벨은 툴팁이 통째로 보여 준다
        self.clip_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.clip_list.setTextElideMode(Qt.ElideRight)
        self.clip_list.currentRowChanged.connect(self._on_select)
        self.clip_list.model().rowsMoved.connect(self._on_reorder)
        lay.addWidget(self.clip_list, 1)

        add_row = QHBoxLayout()
        for label, kind in (("+챕터", "chapter"), ("+도식", "diagram"), ("+B롤", "broll")):
            b = QPushButton(label)
            b.clicked.connect(lambda _c=False, k=kind: self._add_clip(k))
            add_row.addWidget(b)
        self.del_btn = QPushButton("삭제")
        self.del_btn.setObjectName("danger")
        self.del_btn.clicked.connect(self._remove_clip)
        add_row.addWidget(self.del_btn)
        lay.addLayout(add_row)

        self.budget_label = QLabel("")
        lay.addWidget(self.budget_label)
        self.budget_bar = QProgressBar()
        self.budget_bar.setTextVisible(False)
        self.budget_bar.setFixedHeight(6)
        lay.addWidget(self.budget_bar)
        self.budget_note = QLabel("")
        self.budget_note.setObjectName("caption")
        self.budget_note.setWordWrap(True)
        lay.addWidget(self.budget_note)

        self.save_btn = QPushButton("저장")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        lay.addWidget(self.save_btn)
        self.issues = QLabel("")
        self.issues.setProperty("chip", "err")
        self.issues.setWordWrap(True)
        self.issues.hide()
        lay.addWidget(self.issues)
        return w

    # ══ 중: 클립 편집 (결함 차단 4종) ════════════════════════════════════════
    def _make_center(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # 화면은 가로 스크롤 금지 (09 G2)
        # 가로 스크롤을 끈 채로 폭이 모자라면 내용이 **그냥 잘린다** — 스플리터에게
        # 이 열의 최소폭을 알려 남는 부족분이 프리뷰 열로 가게 한다 (54회차 P6 실측:
        # 1180px 에서 뷰포트 317 < 내용 최소 464 라 오른쪽 절반이 사라졌다)
        scroll.setMinimumWidth(490)   # 세로 스크롤바(약 14px)까지 감안한 값
        w = QWidget()
        scroll.setWidget(w)
        lay = QVBoxLayout(w)

        # ── 시작 안내 — 대본이 비어 있을 때만 (10 P1: "대본을 쉽게 만들 방법이 없는가")
        self.start_panel = QWidget()
        self.start_panel.setObjectName("card")
        sp = QVBoxLayout(self.start_panel)
        sp.setContentsMargins(18, 16, 18, 16)
        sp_head = QLabel("대본이 아직 비어 있습니다")
        sp_head.setObjectName("sectionTitle")
        sp.addWidget(sp_head)
        sp_desc = QLabel("대본을 쓰면 위의 [빌드]가 영상으로 만듭니다. 셋 중 하나로 시작하세요:")
        sp_desc.setObjectName("caption")
        sp_desc.setWordWrap(True)
        sp.addWidget(sp_desc)
        self._sp_head, self._sp_desc = sp_head, sp_desc
        self._sp_buttons = QWidget()
        # 세로 배치 — 가로 한 줄은 좁은 창에서 잘린다 (10: "상단 틀이 안 맞는다" 재현 실측)
        sp_row = QVBoxLayout(self._sp_buttons)
        sp_row.setContentsMargins(0, 0, 0, 0)
        sp_row.setSpacing(8)
        ai_btn = QPushButton("AI 로 대본 쓰기")
        ai_btn.setObjectName("primary")
        ai_btn.setToolTip("주제만 알려주면 AI 가 전체 클립의 내레이션을 채웁니다")
        ai_btn.clicked.connect(self._start_ai)
        paste_btn = QPushButton("글 붙여넣기 → AI 가 배분")
        paste_btn.setToolTip("가진 원고를 붙여넣으면 AI 가 지어내지 않고 클립에 나눠 담습니다")
        paste_btn.clicked.connect(self._start_paste)
        self_btn = QPushButton("직접 쓰기")
        self_btn.clicked.connect(self._start_manual)
        for b in (ai_btn, paste_btn, self_btn):
            sp_row.addWidget(b, 0, Qt.AlignLeft)
        sp.addWidget(self._sp_buttons)
        # 진행 모드 — [시작] 뒤에 아무 일도 안 보이면 죽은 줄 안다 (10: "프로그레스바가
        # 가면서 대본이 생성되어야 하는 거 아닌가"). 같은 카드가 진행 표시로 변신한다.
        self.ai_bar = QProgressBar()
        # 불확정(0,0) 바는 전역 QSS 아래서 스타일 애니메이션이 멎어 **꽉 찬 정지 막대**로
        # 보인다 (2026-08-23 실측: LLM 응답을 기다리는 수십 초가 "멈춘 화면"으로 읽혔다).
        # 확정 범위를 두고 타이머(_ai_tick)가 값을 돌려 눈에 보이는 움직임을 만든다.
        self.ai_bar.setRange(0, 100)
        self.ai_bar.setTextVisible(False)   # 물결은 진행률이 아니다 — % 표기 금지
        self.ai_bar.setFixedHeight(8)
        self.ai_bar.hide()
        sp.addWidget(self.ai_bar)
        self._ai_ticks = 0
        self._ai_timer = QTimer(self)
        self._ai_timer.setInterval(120)
        self._ai_timer.timeout.connect(self._ai_tick)
        self.ai_line = QLabel("")
        self.ai_line.setObjectName("caption")
        self.ai_line.setWordWrap(True)
        self.ai_line.hide()
        sp.addWidget(self.ai_line)
        self.start_panel.hide()
        lay.addWidget(self.start_panel)
        # 접힌 뒤에도 AI 로 돌아올 길 — [직접 쓰기]가 편도문이면 안 된다
        # (2026-08-22 사용자: "직접 쓰기를 클릭 후 다시 돌아가려면?")
        self.ai_reopen = QPushButton("AI 도움받기 — 대본 쓰기 · 글 배분")
        self.ai_reopen.setFlat(True)
        self.ai_reopen.clicked.connect(self._reopen_ai)
        self.ai_reopen.hide()
        lay.addWidget(self.ai_reopen, 0, Qt.AlignLeft)

        self.cur_id = QLabel("")
        self.cur_id.setObjectName("sectionTitle")
        lay.addWidget(self.cur_id)

        # ── 묶음 1: 할 말 — 대본 화면의 본업이라 내레이션이 맨 위다 (10 지적 11).
        # 예전에는 화면 선택(위)과 화면 문구 폼(아래)이 내레이션을 사이에 두고
        # 갈라져 있어 "무엇이 어디 것인지" 읽히지 않았다.
        narr_head = QLabel("할 말 — 내레이션")
        narr_head.setObjectName("caption")
        lay.addWidget(narr_head)

        self.narration = QPlainTextEdit()
        self.narration.setMinimumHeight(96)
        self.narration.setMaximumHeight(320)
        self.narration.textChanged.connect(self._on_narration)
        self.narration.selectionChanged.connect(self._on_narr_select)
        lay.addWidget(self.narration, 1)   # 남는 높이는 글 쓰는 칸이 먹는다 (09 G3)
        self.narr_info = QLabel("")
        self.narr_info.setObjectName("caption")
        self.narr_info.setWordWrap(True)
        lay.addWidget(self.narr_info)
        # 발화시각 계산기 — 구절 선택 → 글자수÷페이스 → tN 원클릭 기입 (03 ⑤)
        self.spoken_row = QHBoxLayout()
        self.spoken_label = QLabel("")
        self.spoken_label.setObjectName("caption")
        self.spoken_row.addWidget(self.spoken_label)
        self.spoken_row.addStretch(1)
        lay.addLayout(self.spoken_row)

        # ── 묶음 2: 보이는 것 — 화면 고르기와 화면 문구를 한 자리에
        self.params_head = QHBoxLayout()
        screen_head = QLabel("보이는 것 — 화면")
        screen_head.setObjectName("caption")
        self.extract_btn = QPushButton("B롤 프레임을 이미지(src)로 가져오기")
        self.extract_btn.clicked.connect(self._extract_frame)
        self.params_head.addWidget(screen_head)
        self.params_head.addStretch(1)
        self.params_head.addWidget(self.extract_btn)
        lay.addSpacing(theme.GAP_STACK)
        lay.addLayout(self.params_head)

        pick_row = QHBoxLayout()
        self.screen_label = QLabel("—")   # 표시명이 본문이다 — 파일명은 괄호 보조 (10 #8)
        self.screen_label.setWordWrap(True)
        self.tpl_btn = QPushButton("템플릿 선택…")
        self.tpl_btn.clicked.connect(self._pick_template)
        self.broll_btn = QPushButton("B롤 선택…")
        self.broll_btn.clicked.connect(self._pick_broll)
        pick_row.addWidget(self.screen_label, 1)
        pick_row.addWidget(self.tpl_btn)
        pick_row.addWidget(self.broll_btn)
        lay.addLayout(pick_row)

        # B롤 전용 행 (videoStart·shade + 길이 즉시 검사 — 결함 ④)
        self.broll_row = QWidget()
        br = QHBoxLayout(self.broll_row)
        br.setContentsMargins(0, 0, 0, 0)
        self.video_start = QDoubleSpinBox()
        self.video_start.setRange(0, 3600)
        self.video_start.setDecimals(1)
        self.video_start.setSingleStep(0.5)
        self.video_start.setFixedWidth(90)
        self.video_start.valueChanged.connect(self._on_field_edit)
        self.shade = QDoubleSpinBox()
        self.shade.setRange(0, 1)
        self.shade.setDecimals(2)
        self.shade.setSingleStep(0.05)
        self.shade.setFixedWidth(90)
        self.shade.valueChanged.connect(self._on_field_edit)
        br.addWidget(QLabel(kinds.param_label("videoStart")))
        br.addWidget(self.video_start)
        br.addWidget(QLabel(kinds.param_label("shade")))
        br.addWidget(self.shade)
        br.addStretch(1)
        lay.addWidget(self.broll_row)
        self.broll_check = QLabel("")
        self.broll_check.setWordWrap(True)
        lay.addWidget(self.broll_check)

        self.params_title = QLabel("")   # 폼 안내 — 폼이 있을 때만 렌더가 채운다
        self.params_title.setObjectName("caption")
        lay.addWidget(self.params_title)
        self.params_form_holder = QWidget()
        self.params_form = QFormLayout(self.params_form_holder)
        self.params_form.setLabelAlignment(Qt.AlignRight)
        lay.addWidget(self.params_form_holder)

        self.inherit_label = QLabel("")
        self.inherit_label.setObjectName("caption")
        self.inherit_label.setWordWrap(True)
        lay.addWidget(self.inherit_label)
        self.unknown_box = QVBoxLayout()
        lay.addLayout(self.unknown_box)
        # 남는 세로 공간은 맨 아래로 — 내레이션 칸이 최대 높이에 걸리면 남는 공간이
        # 두 묶음 사이에 끼어 화면이 두 동강 나 보인다 (08 §4-1·6)
        lay.addStretch(1)
        return scroll

    # ══ 우: 프리뷰 (D10 — 같은 문서·같은 시킹이라 프리뷰가 곧 실물) ═══════════
    def _make_right(self) -> QWidget:
        w = _PreviewColumn()
        lay = QVBoxLayout(w)
        # QApplication 이전 임포트·GPU 폴백은 app.bootstrap 이 담당 (호출자가 임포트했어야 함)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        preview_head = QLabel("미리보기")
        preview_head.setObjectName("sectionTitle")
        lay.addWidget(preview_head)
        self.preview = QWebEngineView()
        self.preview.setMinimumHeight(240)
        w.preview = self.preview        # 폭이 바뀌면 16:9 로 다시 잡는다
        lay.addWidget(self.preview)
        scrub_row = QHBoxLayout()
        from PySide6.QtWidgets import QSlider

        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 100)  # ×0.1s
        self.scrub.valueChanged.connect(self._seek)
        self.scrub_label = QLabel("0.0s")
        self.scrub_label.setObjectName("caption")
        self.replay_btn = QPushButton("↻ 재생")
        self.replay_btn.clicked.connect(self._refresh_preview)
        scrub_row.addWidget(self.scrub, 1)
        scrub_row.addWidget(self.scrub_label)
        scrub_row.addWidget(self.replay_btn)
        lay.addLayout(scrub_row)
        # 프리뷰가 못 뜬 이유를 말한다 — 예전엔 `fail=lambda e: None` 로 삼켜서 **빈 화면만**
        # 남았다 (70회차 P18. 갓 만든 영상은 화면이 대부분 자리표시자라 이 상태가 기본이다).
        # 55회차 라이브러리와 같은 원칙: 못 읽었으면 못 읽었다고 말한다
        self.preview_note = QLabel("")
        self.preview_note.setObjectName("caption")
        self.preview_note.setWordWrap(True)
        self.preview_note.hide()
        lay.addWidget(self.preview_note)

        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget

        self.broll_video = QVideoWidget()
        self.broll_video.setMinimumHeight(240)
        self.broll_video.hide()
        self.broll_player = QMediaPlayer()
        self.broll_player.setVideoOutput(self.broll_video)
        lay.insertWidget(1, self.broll_video)   # [미리보기] 헤더 아래, 템플릿 프리뷰 자리
        self.broll_play_btn = QPushButton("▶ B롤 재생")
        self.broll_play_btn.clicked.connect(self._toggle_broll)
        self.broll_player.playbackStateChanged.connect(self._sync_broll_btn)
        self.broll_play_btn.hide()
        lay.addWidget(self.broll_play_btn)

        voice_head = QLabel("음성")
        voice_head.setObjectName("sectionTitle")
        lay.addWidget(voice_head)
        voice_row = QHBoxLayout()
        self.voice_btn = QPushButton("▶ 음성 듣기")
        self.voice_btn.clicked.connect(self._play_voice)
        self.audio.bind(self.voice_btn, "▶ 음성 듣기")
        self.tts_btn = QPushButton("음성 다시 만들기")
        self.tts_btn.clicked.connect(self.tts_requested.emit)
        voice_row.addWidget(self.voice_btn)
        voice_row.addWidget(self.tts_btn)
        voice_row.addStretch(1)
        lay.addLayout(voice_row)
        self.voice_note = QLabel("")
        self.voice_note.setObjectName("caption")
        lay.addWidget(self.voice_note)
        lay.addStretch(1)
        return w

    # ── 시작 안내 (10 P1) ───────────────────────────────────────────────────
    def _script_unwritten(self) -> bool:
        """모든 내레이션이 비었거나 골격의 "[…]" 안내문 그대로면 아직 안 쓴 것이다."""
        return not any(spoken(c) for c in self.clips)

    def _sync_start_panel(self) -> None:
        # 실패 안내가 떠 있는 동안엔 늦게 도착한 비동기 콜백이 패널을 되접으면
        # 안 된다 — 사용자가 다시 시작하거나 접기 전까지 유지 (31회차 P18)
        if getattr(self, "_ai_error", None):
            self.start_panel.setVisible(True)
            self.ai_reopen.hide()
            return
        has = bool(self.clips)
        show_panel = (has and self._script_unwritten()
                      and not getattr(self, "_panel_collapsed", False))
        self.start_panel.setVisible(show_panel)
        # 패널이 없을 때도 AI 진입로는 남긴다 (쓰던 중이든, 직접 쓰기로 접었든)
        self.ai_reopen.setVisible(has and not show_panel)

    def _ai_dialog(self, title: str, prompt: str) -> tuple[str, bool, list] | None:
        """주제 입력 + 근거 문서/폴더 + [영상까지 한 번에] — "알아서 다"가 기본값이다.

        Claude Code 에서 develop-video 스킬로 "만들어라" 하면 끝까지 가듯이, 이 앱의
        에이전트도 같은 스킬을 읽는다 — 대본이 끝나면 빌드를 자동으로 잇는다 (10 P1+).
        에이전트는 Read·Glob 도구가 있어 **글에 폴더 경로를 적어도 직접 읽지만**,
        [근거 추가] 로 고르면 전용 통로(sourceDocs)로 정확히 전달된다.
        """
        from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                                       QFileDialog, QHBoxLayout, QPlainTextEdit,
                                       QPushButton, QVBoxLayout)

        dlg = QDialog(self.window())
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(680)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(26, 24, 26, 20)
        lay.setSpacing(14)
        # 두 이야기를 " — " 로 이어 붙여 한 줄이 길었다 (63회차 P25) — 물음과 요령을 나눈다
        cap = QLabel(prompt)
        cap.setWordWrap(True)
        lay.addWidget(cap)
        tip = QLabel("폴더 경로를 글에 적으면 AI 가 그 내용을 직접 읽습니다.")
        tip.setObjectName("caption")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        text = QPlainTextEdit()
        text.setMinimumHeight(160)
        lay.addWidget(text)

        docs: list[str] = []
        docs_label = QLabel("")
        docs_label.setObjectName("caption")
        docs_label.setWordWrap(True)

        def add_files():
            files, _ = QFileDialog.getOpenFileNames(dlg, "근거 문서 선택")
            docs.extend(f for f in files if f not in docs)
            _sync()

        def add_dir():
            d = QFileDialog.getExistingDirectory(dlg, "근거 폴더 선택")
            if d and d not in docs:
                docs.append(d)
            _sync()

        def clear_docs():
            docs.clear()
            _sync()

        def _sync():
            # 절대경로 전문을 늘어놓으면 넉 줄을 먹고 무엇을 골랐는지 한눈에 안 들어온다
            # (63회차 P25 실측: 문서 4개에 381자·4줄). 이름으로 말하고 전문은 툴팁 —
            # 클립 목록(54회차)·작업 큐(60회차)와 같은 문법
            if docs:
                names = [Path(d).name or d for d in docs]
                shown = " · ".join(names[:4])
                more = f" 외 {len(names) - 4}개" if len(names) > 4 else ""
                docs_label.setText(f"근거 {len(docs)}개: {shown}{more}")
                docs_label.setToolTip("\n".join(docs))
            else:
                docs_label.setText("")
                docs_label.setToolTip("")
            clear_btn.setVisible(bool(docs))

        doc_row = QHBoxLayout()
        f_btn = QPushButton("근거 문서 추가…")
        f_btn.clicked.connect(add_files)
        d_btn = QPushButton("근거 폴더 추가…")
        d_btn.clicked.connect(add_dir)
        doc_hint = QLabel("(선택 — AI 가 여기 있는 내용만으로 씁니다. 지어내지 않게)")
        doc_hint.setObjectName("caption")
        # 잘못 넣은 근거를 뺄 길 — 없으면 취소하고 처음부터였다 (47회차 P21)
        clear_btn = QPushButton("근거 비우기")
        clear_btn.setFlat(True)
        clear_btn.clicked.connect(clear_docs)
        clear_btn.hide()
        doc_row.addWidget(f_btn)
        doc_row.addWidget(d_btn)
        doc_row.addWidget(clear_btn)
        doc_row.addStretch(1)
        lay.addLayout(doc_row)
        # 안내문을 버튼 옆에 두면 [근거 비우기] 가 나타나는 순간(=근거를 넣은 순간) 잘린다
        # — 넷이 한 줄에 안 들어간다 (63회차 P6 실측). 아래 줄로 내리고 줄바꿈을 준다
        doc_hint.setWordWrap(True)
        lay.addWidget(doc_hint)
        lay.addWidget(docs_label)

        auto = QCheckBox("영상까지 한 번에 — 대본이 끝나면 자동으로 빌드합니다 (몇 분 걸립니다)")
        auto.setChecked(True)
        lay.addWidget(auto)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok = buttons.button(QDialogButtonBox.Ok)
        ok.setText("시작")
        ok.setObjectName("primary")
        # 빈 글로 [시작]을 누르면 조용히 무시되던 결함 — 쓸 것이 있어야 눌린다 (P4)
        ok.setEnabled(False)
        text.textChanged.connect(
            lambda: ok.setEnabled(bool(text.toPlainText().strip())))
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() and text.toPlainText().strip():
            return text.toPlainText().strip(), auto.isChecked(), docs
        return None

    def _start_ai(self) -> None:
        got = self._ai_dialog("AI 로 대본 쓰기",
                              "무엇에 대한 영상인지 알려주세요 — 주제·강조점·꼭 들어갈 내용")
        if got:
            brief, auto, docs = got
            payload = {"brief": brief, "auto_build": auto}
            if docs:
                payload["sourceDocs"] = docs
            self.ai_requested.emit(payload)

    def _start_paste(self) -> None:
        got = self._ai_dialog("글 붙여넣기",
                              "가진 원고를 붙여넣으세요 — AI 가 지어내지 않고 이 글을 "
                              "클립에 나눠 담습니다")
        if got:
            text, auto, docs = got
            payload = {"brief": "붙여넣은 원고를 클립에 배분",
                       "source": text, "auto_build": auto}
            if docs:
                payload["sourceDocs"] = docs
            self.ai_requested.emit(payload)

    # ── AI 진행 표시 (부모 EpisodePage 가 잡 이벤트를 흘려준다) ─────────────
    def _clear_ai_error(self) -> None:
        self._ai_error = None

    def ai_progress_start(self, msg: str = "AI 가 대본을 쓰는 중입니다 — 몇 분 걸립니다. "
                                           "위의 [중단]으로 멈출 수 있습니다."
                          ) -> None:
        self._ai_error = None   # 새 시도 — 이전 실패 안내 해제
        self._panel_collapsed = False
        self.ai_reopen.hide()
        self.start_panel.show()
        self._sp_head.setText("AI 작업 중")
        self._sp_desc.setText(msg)
        self._sp_buttons.hide()
        self.ai_bar.show()
        self.ai_line.clear()
        self.ai_line.show()
        self._ai_ticks = 0
        self.ai_bar.setValue(0)
        self._ai_timer.start()

    def _ai_tick(self) -> None:
        """살아있음 표시 — 바 물결 + 제목 점. 진행률 정보는 아니다 (단계는 ai_line 이 말한다)."""
        self._ai_ticks += 1
        self.ai_bar.setValue(self._ai_ticks * 3 % 101)
        self._sp_head.setText("AI 작업 중 " + "·" * (self._ai_ticks // 5 % 4 + 1))

    def ai_progress_line(self, line: str) -> None:
        if line.strip():
            self.ai_line.setText(line.strip()[-160:])

    def ai_progress_state(self, msg: str) -> None:
        self._sp_desc.setText(msg)

    def ai_progress_end(self, error: str | None = None) -> None:
        self._ai_timer.stop()    # 먼저 멈춘다 — 늦은 틱이 끝난 제목을 되덮지 않게
        self._ai_error = error   # None 이면 해제 — _sync_start_panel 이 존중한다
        self._sp_head.setText("대본이 아직 비어 있습니다")
        self._sp_desc.setText("대본을 쓰면 위의 [빌드]가 영상으로 만듭니다. 셋 중 하나로 시작하세요:")
        self._sp_buttons.show()
        self.ai_bar.hide()
        self.ai_line.hide()
        self._sync_start_panel()
        if error:   # 실패 사유는 시작 패널이 말한다 — 로그만 보면 놓친다 (31회차 P18)
            self._panel_collapsed = False
            self.start_panel.show()
            self.ai_reopen.hide()
            self._sp_head.setText("AI 작업이 끝나지 못했습니다")
            self._sp_desc.setText(error)
            self._sp_buttons.show()   # "아래 버튼으로 다시"가 말뿐이면 안 된다

    def _start_manual(self) -> None:
        """첫 내레이션 자리로 데려간다 — 안내는 접히고, [AI 도움받기]로 되돌아온다."""
        self._ai_error = None   # 사용자가 다른 길을 골랐다 — 실패 안내 해제
        self._panel_collapsed = True
        self._sync_start_panel()
        if self.clips:
            self.clip_list.setCurrentRow(0)
        self.narration.setFocus()

    def _reopen_ai(self) -> None:
        """접힌 안내를 다시 편다 — 대본이 이미 있으면 덮어씀을 경고한다."""
        self._panel_collapsed = False
        if not self._script_unwritten():
            self._sp_head.setText("AI 로 다시 쓰기")
            self._sp_desc.setText("대본이 이미 있습니다 — AI 로 새로 쓰면 지금 내용을 "
                                  "덮어씁니다. 글 붙여넣기도 마찬가지입니다.")
        self.start_panel.show()
        self.ai_reopen.hide()

    # ── 문맥 ────────────────────────────────────────────────────────────────
    @property
    def clips(self) -> list[dict]:
        return self.doc.get("render", {}).get("motion", {}).get("clips", [])

    @property
    def cur(self) -> dict | None:
        return self.clips[self._selected] if 0 <= self._selected < len(self.clips) else None

    def _mark_dirty(self) -> None:
        if not self._loading:
            self._dirty = True

    def has_unsaved(self) -> bool:
        """저장하지 않은 대본 변경 여부 — 이탈 확인(P20)의 판단 재료."""
        return bool(getattr(self, "_dirty", False))

    def load(self, eid: str, scenes: dict, etag: str, inspect: dict,
             budget_text: str) -> None:
        if eid != getattr(self, "eid", None):
            # 앞 영상의 저장 결과가 그대로 남아 **다른 영상의 화면에서 그 영상의 결함처럼**
            # 읽혔다 — "저장됨 — 경로 문제: broll: B롤 없음 …" (54회차 P19·P11 실측).
            # 52(설정)·53(브랜드 킷)과 같은 결함·같은 처방 — 대상이 바뀌면 결과를 지운다
            self.issues.setText("")
            self.issues.hide()
        self.stop_media()
        self._loading = True
        self._dirty = False   # 새로 읽음 — 이전 편집 흔적 해제
        self.eid = eid
        self.doc = copy.deepcopy(scenes)
        self._etag = etag
        self._inspect = inspect or {}
        m = re.search(r"([\d,]+)\s*자", budget_text or "")
        self._budget = int(m.group(1).replace(",", "")) if m else 1850
        studio = self._make_studio()
        self._assets_ready = False
        self._assets_error = ""   # 앞 영상의 실패 사유를 물려주지 않는다
        # A3 가드 — 영상을 빠르게 옮기면 앞 영상의 갤러리(scope 전용 템플릿)가
        # 늦게 도착해 새 영상의 목록을 덮는다
        run_bg(lambda: (studio.templates(scope=eid), studio.assets("broll")),
               done=guard(self, "eid", eid, self._assets_loaded),
               fail=guard(self, "eid", eid, self._assets_failed))
        self._refresh_list(select=0)
        self._loading = False

    def set_inspect(self, inspect: dict) -> None:
        """[TTS 실측 갱신] 후 부모가 재조회한 inspect 를 주입 — 실측 라벨 갱신."""
        self._inspect = inspect or {}
        self._refresh_list(select=self._selected)

    def _assets_loaded(self, result) -> None:
        self._gallery, self._brolls = result
        self._assets_ready = True
        self._render_broll_check()

    def _assets_failed(self, err) -> None:
        """못 불러왔으면 **못 불러왔다고 말한다** — 예전엔 조용히 삼켜서 화면이
        "라이브러리 로딩 중…"에 영원히 머물렀다 (55회차 P18)."""
        self._gallery, self._brolls = [], []
        self._assets_ready = True
        self._assets_error = error_text(err)
        self._render_broll_check()

    @property
    def audio_cache(self) -> dict:
        return self._inspect.get("audioCache") or {}

    # ── 리스트·예산 ─────────────────────────────────────────────────────────
    def _refresh_list(self, select: int = -1) -> None:
        # clear()/addItem() 이 selection 시그널을 쏜다 — 막지 않으면 목록을 다시 그리는
        # 동안 _on_select 가 중간 상태로 불려 편집 중인 클립이 바뀐다 (08 §7)
        self.clip_list.blockSignals(True)
        self.clip_list.clear()
        for c in self.clips:
            secs, measured = clip_seconds(c, self.audio_cache)
            # 역할을 한국어로 먼저 — id 는 괄호 보조 (10 #8). 파일명 대신 표시명 —
            # "intro.html" 이 아니라 "타이틀 카드"가 읽혀야 한다 (10 지적 11)
            role = kinds.role_label(c.get("id"))
            screen = (kinds.screen_name(c["file"]) if c.get("file")
                      else str(c.get("video") or "—").split("/")[-1])
            label = (f"≡ {role} ({c.get('id', '?')}) · {screen}"
                     f"  {secs:.1f}s{'' if measured else '?'}")
            item = QListWidgetItem(label)
            # 라벨이 말줄임되므로 툴팁이 전문을 갖는다 (내레이션은 그 아래)
            item.setToolTip("\n\n".join(p for p in (label, spoken(c)) if p))
            self.clip_list.addItem(item)
        self.clip_list.blockSignals(False)
        self._sync_start_panel()
        if 0 <= select < len(self.clips):
            self.clip_list.setCurrentRow(select)
            self._selected = select
            self._render_clip()
        self._render_budget()
        self._render_skeleton_warn()

    def _render_budget(self) -> None:
        total = sum(len(spoken(c)) for c in self.clips)
        secs = sum(clip_seconds(c, self.audio_cache)[0] for c in self.clips)
        # "실측"은 TTS 캐시로 잰 것만 — 아직 안 쓴 대본은 골격 duration 의 합일 뿐이라
        # 실측이라 부르면 안 된다 (54회차: 자리표시자를 안 세게 바꾸자 전 클립이 '잴 것
        # 없음'이 되어 빈 대본이 "실측"으로 뒤집혔다)
        measured_all = (any(spoken(c) for c in self.clips)
                        and all(clip_seconds(c, self.audio_cache)[1] for c in self.clips))
        pct = round(total / self._budget * 100) if self._budget else 0
        self.budget_label.setText(f"전체 대본 {total:,}자 / 목표 {self._budget:,}자 ({pct}%)")
        self.budget_bar.setValue(min(100, pct))
        over = pct > 100
        self.budget_label.setStyleSheet(
            f"color: {theme.DANGER}; font-weight: 700;" if over else "")
        note = (f"영상 길이 {'실측' if measured_all else '추정'} "
                f"{int(secs // 60)}:{int(secs % 60):02d}")
        if over:
            note += " — 목표를 넘으면 말을 빠르게 하지 않고 영상을 나눕니다"
        self.budget_note.setText(note)

    def _render_skeleton_warn(self) -> None:
        ids = [c.get("id") for c in self.clips if c.get("id") in SKELETON]
        want = [s for s in SKELETON if s in ids]
        bad = ids != want
        self.skeleton_warn.setText("골격 위치 규약(broll→title→hook→stinger→promise)과 순서가 다릅니다")
        self.skeleton_warn.setVisible(bad)

    def _on_reorder(self, _p, start, _e, _d, dest) -> None:
        self._mark_dirty()
        clips = self.clips
        moved = clips.pop(start)
        clips.insert(dest if dest < start else dest - 1, moved)
        self._refresh_list(select=self.clip_list.currentRow())

    def _on_select(self, row: int) -> None:
        if self._loading or row < 0:
            return
        self._selected = row
        self._render_clip()

    # ── 클립 추가·삭제 (id 골격 관례 자동 제안 — 3A) ─────────────────────────
    def _next_id(self, kind: str) -> str:
        ids = {c.get("id") for c in self.clips}
        if kind == "chapter":
            n = 1
            while f"ch{n}" in ids:
                n += 1
            return f"ch{n}"
        if kind == "diagram":
            n = 1
            while True:
                for suf in "abc":
                    if f"s{n}{suf}" not in ids:
                        return f"s{n}{suf}"
                n += 1
        n = 1
        while ("broll" if n == 1 else f"broll{n}") in ids:
            n += 1
        return "broll" if n == 1 else f"broll{n}"

    def _add_clip(self, kind: str) -> None:
        self._mark_dirty()
        cid = self._next_id(kind)
        clip = ({"id": cid, "video": "", "videoStart": 0, "shade": 0.35,
                 "duration": 2.0, "before": "end"} if kind == "broll" else
                {"id": cid, "file": "chapter.html" if kind == "chapter" else "",
                 "before": "end", "narration": "", "params": {"wipe": "off"}})
        pos = self._selected + 1 if self._selected >= 0 else len(self.clips)
        self.clips.insert(pos, clip)
        self._refresh_list(select=pos)

    def _remove_clip(self) -> None:
        c = self.cur
        if not c:
            return
        narr = len(spoken(c))
        msg = f"{kinds.role_label(c.get('id'))} ({c.get('id')}) 클립을 삭제할까요?"
        if narr:
            msg += f"\n\n쓴 내레이션 {narr}자도 함께 지워집니다."
        if QMessageBox.warning(self, "클립 삭제", msg,
                               QMessageBox.Yes | QMessageBox.Cancel,
                               QMessageBox.Cancel) != QMessageBox.Yes:
            return
        self._mark_dirty()
        self.clips.pop(self._selected)
        self._refresh_list(select=max(0, self._selected - 1))

    # ── 클립 편집 렌더 ──────────────────────────────────────────────────────
    def _accepted_keys(self) -> list[str]:
        c = self.cur
        f = c.get("file") if c else None
        if not f:
            return []
        t = (self._inspect.get("templates") or {}).get(f)
        if t:
            return t.get("params", [])
        g = next((x for x in self._gallery if x["file"] == f), None)
        return g.get("params", []) if g else []

    def stop_media(self) -> None:
        """B롤 영상·음성 미리듣기를 멈춘다.

        55회차 실측: B롤을 재생한 채 다른 클립으로 옮기면 **영상 위젯만 숨고 재생은
        계속됐다**(위치가 계속 늘었다). [← 프로젝트]로 화면을 떠나도 마찬가지 —
        보이지도 않는 소재가 계속 돌고, 소리 있는 B롤이면 소리가 남는다.
        음성 미리듣기(AudioPreview)도 같은 구멍이었다. 종류를 바꾸면 미리듣기를
        초기화하는 라이브러리(11회차)와 같은 규칙을 여기에도 적용한다.
        """
        from PySide6.QtMultimedia import QMediaPlayer

        if self.broll_player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.broll_player.stop()
        self.audio.stop()

    def _render_clip(self) -> None:
        c = self.cur
        if c is None:
            return
        # 다른 클립으로 옮기는 중 — 앞 클립의 소리·영상을 끌고 가지 않는다
        self.stop_media()
        self._loading = True
        self.cur_id.setText(f'{kinds.role_label(c.get("id"))} ({c.get("id", "?")})')
        is_broll = "video" in c
        self.screen_label.setText(
            kinds.screen_label(c["file"]) if c.get("file")
            else c.get("video") or "(미선택 — 오른쪽 버튼으로 고르세요)")
        self.tpl_btn.setVisible(not is_broll)
        self.broll_btn.setVisible(is_broll)
        self.broll_row.setVisible(is_broll)
        if is_broll:
            self.video_start.setValue(float(c.get("videoStart") or 0))
            self.shade.setValue(float(c.get("shade", 0.35) or 0))
        self.narration.setPlainText(c.get("narration", ""))
        self._render_narr_info()
        self._render_params_form()
        self._render_broll_check()
        self._render_voice()
        self._refresh_preview()
        self._loading = False

    def _render_params_form(self) -> None:
        while self.params_form.rowCount():
            self.params_form.removeRow(0)
        while self.unknown_box.count():
            item = self.unknown_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        c = self.cur
        accepted = self._accepted_keys()
        has_form = bool(c and c.get("file") and accepted)
        self.params_form_holder.setVisible(has_form)
        self.params_title.setText(
            "화면 문구 — 적은 글이 그대로 화면에 나옵니다" if has_form else "")
        # 자리표시자뿐이면 누를 것이 없다 — 눌린 뒤 실패하게 두지 않는다 (71회차 P20)
        real_broll = any(x.get("video") and _PLACEHOLDER not in str(x["video"])
                         for x in self.clips)
        self.extract_btn.setVisible(has_form and "src" in accepted
                                    and any(x.get("video") for x in self.clips))
        self.extract_btn.setEnabled(real_broll)
        self.extract_btn.setToolTip("" if real_broll else
                                    "B롤을 먼저 고르세요 — 가져올 소재가 없습니다")
        if not has_form:
            self.inherit_label.setText("")
            return
        # 제목이 맨 아래로 밀리지 않게 뜻 순서로 정렬 — 템플릿 내부 순서는 구현이다
        # (10 지적 11). 목록에 없는 키(t1 등)는 템플릿 순서 그대로 뒤에 붙는다.
        editable = sorted(
            (k for k in accepted if k not in AUTO_KEYS and k != "wipe"),
            key=lambda k: PARAM_ORDER.index(k) if k in PARAM_ORDER else len(PARAM_ORDER))
        params = c.get("params") or {}
        for k in editable:  # ① 받는 키만 폼 생성 — 자유 키 입력 자체가 없음
            field = QLineEdit(str(params.get(k, "")))
            field.setMaximumWidth(420)
            # 빈 칸이 무슨 뜻인지 칸이 스스로 말한다 — _params.js 는 빈 값이면 그 줄을 지운다
            if k == "src":
                field.setPlaceholderText("이미지 경로 — 위의 [B롤 프레임 가져오기]가 채워 줍니다")
            elif TIME_KEY_RE.match(k):
                field.setPlaceholderText("등장 시각(초) — 내레이션 구절을 드래그하면 계산해 줍니다")
            else:
                field.setPlaceholderText("비우면 이 줄은 화면에 나오지 않습니다")
            field.textEdited.connect(lambda v, key=k: self._set_param(key, v))
            self.params_form.addRow(kinds.param_label(k), field)
        wipe = QComboBox()
        wipe.addItem("끔 (기본)", "off")
        wipe.addItem("켬 — 다음 장면이 밝을 때 흰 면으로 덮으며 전환", "on")
        wipe.setCurrentIndex(1 if params.get("wipe") == "on" else 0)
        wipe.currentIndexChanged.connect(
            lambda i, w=wipe: self._set_param("wipe", w.currentData()))
        self.params_form.addRow(kinds.param_label("wipe"), wipe)
        inherited = [k for k in AUTO_KEYS if params.get(k)]
        self.inherit_label.setText(
            "프로젝트 상속 중 (수동 입력 불가): " + " · ".join(f"{k} ✓" for k in inherited)
            if inherited else "")
        for k in sorted(set(params) - set(accepted)):  # ① 안 받는 키 → 빨간 목록 + [제거]
            row = QHBoxLayout()
            warn = QLabel(f'"{k}" 는 {c.get("file")} 이 받지 않는 키 — 화면에서 조용히 사라집니다')
            warn.setProperty("chip", "err")
            drop = QPushButton("제거")
            drop.clicked.connect(lambda _c=False, key=k: self._drop_param(key))
            row.addWidget(warn)
            row.addWidget(drop)
            row.addStretch(1)
            holder = QWidget()
            holder.setLayout(row)
            self.unknown_box.addWidget(holder)

    def _set_param(self, key: str, value) -> None:
        self._mark_dirty()
        c = self.cur
        if c is None:
            return
        params = c.setdefault("params", {})
        if value in ("", None):
            params.pop(key, None)
        else:
            params[key] = value

    def _drop_param(self, key: str) -> None:
        c = self.cur
        if c and c.get("params"):
            c["params"].pop(key, None)
        self._render_params_form()

    # ── 내레이션·발화시각 ────────────────────────────────────────────────────
    def _on_narration(self) -> None:
        self._mark_dirty()
        if self._loading or self.cur is None:
            return
        self.cur["narration"] = self.narration.toPlainText()
        self._render_narr_info()
        self._render_budget()
        self._render_broll_check()

    def _render_narr_info(self) -> None:
        c = self.cur
        if c is None:
            return
        measured = self.audio_cache.get(c.get("id"))
        text = spoken(c)
        if not text and (c.get("narration") or "").strip():
            # 칸에 글은 있는데 0자라고만 하면 왜 그런지 모른다 — 자리표시자라고 말한다
            self.narr_info.setText("골격 안내문입니다 — 아직 쓴 글로 세지 않습니다"
                                   " (지우고 할 말을 쓰세요)")
            return
        n = len(text)
        self.narr_info.setText(
            f"{n}자 · " + (f"음성 실측 {measured:.1f}초" if measured
                           else f"음성 추정 {n / PACE:.1f}초"))

    def _on_narr_select(self) -> None:
        cur = self.narration.textCursor()
        start = min(cur.selectionStart(), cur.selectionEnd())
        text = cur.selectedText()
        while self.spoken_row.count() > 2:
            item = self.spoken_row.takeAt(2)
            if item.widget():
                item.widget().deleteLater()
        if not text:
            self.spoken_label.setText("")
            return
        at = start / PACE
        self.spoken_label.setText(f'"{text[:12]}…" 발화 ≈ {at:.2f}s')
        for k in [k for k in self._accepted_keys()
                  if k not in AUTO_KEYS and TIME_KEY_RE.match(k)]:
            b = QPushButton(f"→ {k}")
            b.clicked.connect(lambda _c=False, key=k, v=f"{at:.2f}": (
                self._set_param(key, v), self._render_params_form()))
            self.spoken_row.addWidget(b)

    # ── 피커 (결함 차단 ②) ──────────────────────────────────────────────────
    def _pick_template(self) -> None:
        rows = [[t["file"], t["scope"],
                 " · ".join(k for k in t["params"] if k not in AUTO_KEYS and k != "wipe")]
                for t in self._gallery]
        dlg = PickerDialog("도식 템플릿 선택", ["파일", "범위", "받는 키"], rows, self)
        if dlg.exec() and dlg.picked is not None:
            c = self.cur
            c["file"] = self._gallery[dlg.picked]["file"]
            c.pop("video", None)
            c.pop("videoStart", None)
            self._render_clip()
            self._refresh_list(select=self._selected)

    def _pick_broll(self) -> None:
        rows = [[a["name"], f"{a.get('duration', 0)}s · {a.get('width', 0)}×{a.get('height', 0)}",
                 a.get("license") or "없음"] for a in self._brolls]
        dlg = PickerDialog("B롤 선택 — 길이·라이선스를 보고 고른다", ["파일", "길이·해상도", "라이선스"],
                           rows, self,
                           empty_text="받아 둔 B롤이 없습니다 — 왼쪽 내비 [라이브러리]에서 "
                                      "URL 로 받아 온 뒤 다시 고르세요.")
        if dlg.exec() and dlg.picked is not None:
            a = self._brolls[dlg.picked]
            c = self.cur
            c["video"] = a["ref"]
            c.setdefault("videoStart", 0)
            c.setdefault("shade", 0.35)
            c.pop("file", None)
            c.pop("params", None)
            self._render_clip()
            self._refresh_list(select=self._selected)

    def _on_field_edit(self) -> None:
        if self._loading or self.cur is None:
            return
        self._mark_dirty()
        c = self.cur
        c["videoStart"] = self.video_start.value()
        c["shade"] = self.shade.value()
        self._render_broll_check()

    # ── B롤 길이 즉시 검사 (결함 차단 ④) ────────────────────────────────────
    def _render_broll_check(self) -> None:
        c = self.cur
        if c is None or "video" not in c:
            self.broll_check.setText("")
            return
        if not getattr(self, "_assets_ready", False):
            self.broll_check.setText("라이브러리 불러오는 중…")  # 오탐 방지 (3단계 실측 메모)
            self.broll_check.setStyleSheet("")
            return
        if _PLACEHOLDER in str(c.get("video") or ""):
            # 골격이 넣어 둔 자리표시자다 — 사용자가 아직 안 골랐을 뿐인데 예전엔
            # "소재 길이를 모릅니다 — 경로를 확인하세요"라고 했다. 확인할 경로가 없다
            # (71회차 P2). 고르라는 안내는 **빈 영상 상자를 대신해 프리뷰 열이** 하고,
            # 이 줄은 잰 것이 없으므로 비운다 — 같은 말을 두 곳에 쓰지 않는다 (P12)
            self.broll_check.setText("")
            self.broll_check.setStyleSheet("")
            return
        src = next((a for a in self._brolls if a["ref"] == c.get("video")), None)
        duration = (src or {}).get("duration") or \
            ((self._inspect.get("media") or {}).get(c.get("video"), {}) or {}).get("duration", 0)
        if not duration:
            # 예전엔 소재가 하나도 없는 라이브러리(새 클론·새 설치가 그렇다 — 미디어는
            # 커밋되지 않는다)를 **"로딩 중"으로 영원히** 표시했다 (55회차 P9·P18).
            # 왜 비었는지에 따라 할 일이 다르므로 셋을 구분해 말한다
            if getattr(self, "_assets_error", ""):
                self.broll_check.setText(f"라이브러리를 못 읽었습니다 — {self._assets_error}")
            elif not self._brolls:
                self.broll_check.setText("라이브러리에 B롤 소재가 없습니다 — "
                                         "[라이브러리] 화면에서 받아 오세요")
            else:
                self.broll_check.setText("소재 길이를 모릅니다 — 경로를 확인하세요")
            self.broll_check.setStyleSheet(f"color: {theme.DANGER};")
            return
        need = clip_seconds(c, self.audio_cache)[0]
        avail = duration - float(c.get("videoStart") or 0)
        if avail <= 0:   # "쓸 수 있는 소스 -1.1s" 음수 표기는 말이 안 된다 (23회차 P25)
            self.broll_check.setText(
                f"시작 지점이 소재 끝({duration:.1f}s)을 지났습니다 — 줄이세요")
            self.broll_check.setStyleSheet(f"color: {theme.DANGER}; font-weight: 600;")
            return
        if need > avail + 0.05:
            self.broll_check.setText(
                f"구간 {need:.1f}s > 쓸 수 있는 소스 {avail:.1f}s — 마지막 {need - avail:.1f}s 정지 프레임")
            self.broll_check.setStyleSheet(f"color: {theme.DANGER}; font-weight: 600;")
        else:
            self.broll_check.setText(f"구간 {need:.1f}s / 소스 여유 {avail:.1f}s ✓")
            self.broll_check.setStyleSheet(f"color: {theme.SUCCESS};")

    # ── title 프레임 추출 (videoStart↔프레임 일치를 한 버튼으로) ─────────────
    def _extract_frame(self) -> None:
        b = next((x for x in self.clips if x.get("video")), None)
        c = self.cur
        if not b or not c:
            return
        eid, studio = self.eid, self._make_studio()
        video, vs, cf = b["video"], b.get("videoStart", 0), c["file"]
        # ffmpeg 추출은 수 초 — 잠그지 않으면 더블클릭이 중복 실행된다 (39회차 P18)
        self.extract_btn.setEnabled(False)
        self.extract_btn.setText("가져오는 중…")

        def _extract_done() -> None:
            self.extract_btn.setEnabled(True)
            self.extract_btn.setText("B롤 프레임을 이미지(src)로 가져오기")

        def _done(out) -> None:
            _extract_done()   # 버튼 복원은 대상 무관 — 공유 위젯이라 항상
            if self.eid != eid:   # A3 — 다른 영상의 대본에 옛 프레임을 꽂지 않는다
                return
            self._set_param("src", out["src"])
            self._render_params_form()
            self.issues.setText(f"배경 프레임 가져옴 — 이미지(src)에 기입됨 (B롤 {vs}s 지점)")
            self.issues.setProperty("chip", "ok")
            self._repolish(self.issues)
            self.issues.show()

        def _failed(e) -> None:
            _extract_done()
            if self.eid == eid:   # A3 — 옛 영상의 오류를 새 화면에 붙이지 않는다
                self._show_issue(error_text(e))

        run_bg(lambda: studio.bg_frame(eid, video=video, video_start=vs, clip_file=cf),
               done=_done, fail=_failed)

    # ── B롤 재생 토글 (음성 미리듣기와 같은 문법 — 재생 중엔 "중지") ─────────
    def _toggle_broll(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        if self.broll_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.broll_player.pause()
        else:
            self.broll_player.play()

    def _sync_broll_btn(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.broll_play_btn.setText("일시정지" if playing else "▶ B롤 재생")   # 영상 재생과 같은 말 (P11)

    # ── 프리뷰 (QWebEngineView — preview.js 문서 + 질의 params) ──────────────
    def _refresh_preview(self) -> None:
        # A3-허용: 프리뷰 재렌더는 마지막 로드가 이긴다 — 클립 전환 시 새 프리뷰가 다시 불린다
        # A2-허용: [↻ 재생]의 재클릭은 곧 "다시 재생" — 중복 실행이 기능이다.
        # 겹쳐도 같은 캐시 경로에 같은 문서를 다시 쓰고 마지막 로드가 이긴다
        c = self.cur
        is_broll = bool(c and "video" in c)
        self.preview.setVisible(not is_broll)
        self.scrub.setVisible(not is_broll)
        self.scrub_label.setVisible(not is_broll)   # 템플릿 프리뷰 전용 컨트롤 —
        self.replay_btn.setVisible(not is_broll)    # B롤에선 죽은 버튼이라 숨긴다
        # B롤 위젯은 **소재가 실제로 있을 때만** 편다 (아래에서 판정)
        self.broll_video.setVisible(False)
        self.broll_play_btn.setVisible(False)
        if c is None:
            return
        if is_broll:
            ref = str(c.get("video") or "")
            source = None
            if ref and _PLACEHOLDER not in ref:
                cand = paths.invert(paths.RefKind.BROLL, ref)
                source = cand if cand.exists() else None
            # 소재가 없으면 빈 검은 상자와 [▶ B롤 재생]은 죽은 컨트롤이다 —
            # 사진·글꼴에서 미리듣기를 숨긴 43회차와 같은 원칙 (71회차 P12·P25)
            self.broll_video.setVisible(bool(source))
            self.broll_play_btn.setVisible(bool(source))
            self._preview_note("" if source else
                               "아직 B롤을 안 골랐습니다 — 오른쪽 [B롤 선택…]으로 고르세요")
            if source is not None:
                self.broll_player.setSource(QUrl.fromLocalFile(str(source)))
                # 재생 전에도 소재가 보이게 — 시작 지점 프레임에서 멈춰 둔다
                self.broll_player.play()
                self.broll_player.setPosition(
                    int(float(c.get("videoStart") or 0) * 1000))
                QTimer.singleShot(150, self.broll_player.pause)
            return
        f = c.get("file")
        if not f:
            self.preview.setHtml("<body style='background:#111'></body>")
            self._preview_note("아직 화면을 안 골랐습니다 — 오른쪽 [템플릿 선택…]으로 고르세요")
            return
        if _PLACEHOLDER in f:
            # 골격이 넣어 둔 자리표시자 파일명이다 — 그런 파일은 없으니 렌더도 없다.
            # 예전엔 조용히 빈 화면이라 "왜 안 보이지"로 끝났다
            self.preview.setHtml("<body style='background:#111'></body>")
            self._preview_note("이 구간의 화면이 아직 정해지지 않았습니다 — "
                               "오른쪽 [템플릿 선택…]으로 고르세요")
            return
        self._preview_note("")
        eid, studio = self.eid, self._make_studio()
        secs = clip_seconds(c, self.audio_cache)[0]
        self.scrub.setRange(0, max(10, int(secs * 10)))
        self.scrub.setValue(0)

        def build():
            html = studio.template_preview(f, scope=eid)
            out = env.cache_dir() / f"preview-{hashlib.sha1((eid + f).encode()).hexdigest()[:10]}.html"
            out.write_text(html, encoding="utf-8", newline="\n")
            return out

        run_bg(build, done=lambda p: (self._preview_note(""), self._load_preview(p)),
               fail=lambda e: self._preview_note(f"미리보기를 못 만들었습니다 — {error_text(e)}"))

    def _preview_note(self, text: str) -> None:
        """프리뷰가 못 뜬 이유 — 빈 문자열이면 감춘다 (70회차 P18)."""
        self.preview_note.setText(text)
        self.preview_note.setVisible(bool(text))

    def _load_preview(self, doc_path: Path) -> None:
        c = self.cur
        if c is None or "file" not in c:
            return
        url = QUrl.fromLocalFile(str(doc_path))
        from urllib.parse import quote

        d = self._episode_dir()
        html = paths.invert(paths.RefKind.MOTION, c["file"], scenes_dir=d)
        pairs = []
        for k, v in (c.get("params") or {}).items():
            if v in ("", None):
                continue
            # 경로형 params 는 프리뷰 문서 위치 기준으로 깨진다 — 절대 file:// URL 로 치환
            if k in ("src", "fontUrl"):
                target = paths.invert(paths.RefKind.HTML_ASSET, str(v), html_file=html)
                if target.exists():
                    v = QUrl.fromLocalFile(str(target)).toString()
            pairs.append(f"{quote(k)}={quote(str(v))}")
        url.setQuery("&".join(pairs))
        self.preview.load(url)

    def _episode_dir(self) -> Path:
        return self._make_studio().episode_dir(self.eid)

    def _seek(self, v: int) -> None:
        sec = v / 10
        self.scrub_label.setText(f"{sec:.1f}s")
        self.preview.page().runJavaScript(
            "for (const a of document.getAnimations({subtree:true}))"
            f"{{ a.pause(); a.currentTime = {int(sec * 1000)}; }}")

    # ── 음성 ────────────────────────────────────────────────────────────────
    def _render_voice(self) -> None:
        c = self.cur
        cached = c is not None and self.audio_cache.get(c.get("id"))
        self.voice_btn.setEnabled(bool(cached))
        self.voice_note.setText(f"음성 {cached:.1f}초 준비됨" if cached
                                else "음성이 아직 없습니다 — [음성 다시 만들기]를 누르세요")

    def _play_voice(self) -> None:
        if self.audio.stop_if_playing(self.voice_btn):   # 두 번째 클릭 = 중지
            return
        c = self.cur
        if not c:
            return
        p = OUT_ROOT / self.eid / "audio" / f"motion-{c.get('id')}.mp3"
        if p.exists():
            self.audio.start(self.voice_btn, p)

    # ── 저장 (etag — 응답 etag 항상 채택) ───────────────────────────────────
    def _save(self) -> None:
        eid, etag, studio = self.eid, self._etag, self._make_studio()
        body = self.doc
        # 저장 중 잠금 — 안 잠그면 중복 클릭이 옛 etag 로 두 번째 저장을 보내
        # 409 충돌 에러를 띄운다 (P18·P20)
        self.save_btn.setEnabled(False)
        self.save_btn.setText("저장 중…")
        def _done(out) -> None:
            if self.eid == eid:   # A3 — 옛 영상의 etag·결과를 새 대본에 쓰지 않는다
                self._saved(out)
            else:
                self._save_done()   # 버튼 복원만 — 공유 위젯
        run_bg(lambda: studio.put_episode(eid, body, etag),
               done=_done,
               fail=lambda e: (self.eid == eid and self._show_issue(error_text(e)),
                               self._save_done()))

    def _save_done(self) -> None:
        self.save_btn.setEnabled(True)
        self.save_btn.setText("저장")

    def _saved(self, out: dict) -> None:
        self._dirty = False
        self._save_done()
        self._etag = out["etag"]  # 경로 문제가 있어도 채택 — 다음 저장 409 교착 방지
        issues = out.get("pathIssues") or []
        cons = out.get("consistency") or []
        if issues:
            self._show_issue("저장됨 — 경로 문제:\n" + "\n".join(issues))
        else:
            msg = "저장됨 ✓" + (f" — 프로젝트 일관성 {len(cons)}건 어긋남" if cons else "")
            self.issues.setText(msg)
            self.issues.setProperty("chip", "ok" if not cons else "warn")
            self._repolish(self.issues)
            self.issues.show()
        self.saved.emit()

    def _show_issue(self, text: str) -> None:
        self.issues.setText(text)
        self.issues.setProperty("chip", "err")
        self._repolish(self.issues)
        self.issues.show()

    @staticmethod
    def _repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)
