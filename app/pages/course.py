"""프로젝트 화면 — 탭 ①②③ (5-4: ① 설정 편집·② 보드+[영상 만들기]·③ 브랜드 킷)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QLabel, QPushButton,
                               QScrollArea, QTabWidget, QVBoxLayout, QWidget)

from .. import theme
from ..bridge import error_text, run_bg
from .brandkit import BrandKitTab
from .course_settings import CourseSettingsTab

# 이모지 금지 — OS 폰트가 다른 그림으로 그린다 (09 G4). 색 점 + 한국어 라벨로 말한다
STATE = {"empty": "대기", "wip": "제작 중", "done": "완료"}
EMPTY_LANE = {"empty": "남은 영상이 없습니다", "wip": "제작 중인 영상이 없습니다",
              "done": "아직 완료된 영상이 없습니다"}


class EpisodeCard(QFrame):
    opened = Signal(str)
    create = Signal(int)    # n — [영상 만들기] (03 ②)
    ai_draft = Signal(int)  # n — [✨ AI 초안] (05: 미생성 영상은 스캐폴딩 후 제출)
    delete_requested = Signal(str, str)   # eid, 표시명 — 확인은 페이지가 맡는다

    def __init__(self, entry: dict, badge: dict):
        super().__init__()
        self.setObjectName("card")
        self.eid = badge["id"]
        self.setFixedWidth(theme.CARD_W)   # 레인 폭으로 늘어나지 않게 (09 G3)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        label = f"{entry.get('n', '?')}강 {entry.get('title', '')}"
        title = QLabel(label)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600;")
        head = QHBoxLayout()
        head.addWidget(title, 1)
        if badge["state"] != "empty":
            # 영상 삭제를 카드에서 바로 — 프로젝트만 지울 수 있고 영상 하나는 못
            # 지우던 구멍 (16회차 P7. 대시보드 카드와 같은 문법)
            del_btn = QPushButton("삭제")
            del_btn.setObjectName("cardDelete")
            del_btn.setCursor(Qt.ArrowCursor)
            del_btn.setToolTip("이 영상을 삭제합니다 (확인을 거칩니다)")
            del_btn.clicked.connect(
                lambda: self.delete_requested.emit(self.eid, label))
            head.addWidget(del_btn, 0, Qt.AlignTop)
        lay.addLayout(head)
        # 레인 제목이 이미 상태다 — 카드에 상태 칩을 또 두지 않는다 (09 G5).
        # 대신 이 카드에서만 아는 것(완성본 길이·재빌드 필요)을 보여준다
        row = QHBoxLayout()
        row.setSpacing(6)
        finals = badge.get("final") or []
        if finals:
            variant = finals[0].rsplit("-", 1)[-1].replace(".mp4", "")
            info = QLabel(f"완성본 {len(finals)}개 · {variant}" if len(finals) > 1
                          else f"완성본 {variant}")   # "16x9" 날것 캡션은 뜻이 없다 (P2)
            info.setObjectName("caption")
            row.addWidget(info)
        if badge.get("stale"):
            warn = QLabel("재빌드 필요")
            warn.setProperty("chip", "err")
            row.addWidget(warn)
        row.addStretch(1)
        if row.count() > 1:
            lay.addLayout(row)
        if badge["state"] == "empty":
            row2 = QHBoxLayout()
            btn = QPushButton("영상 만들기")
            btn.clicked.connect(lambda: self.create.emit(entry.get("n", 0)))
            self.ai_btn = QPushButton("AI 초안")
            self.ai_btn.setEnabled(False)
            self.ai_btn.clicked.connect(lambda: self.ai_draft.emit(entry.get("n", 0)))
            row2.addWidget(btn)
            row2.addWidget(self.ai_btn)
            row2.addStretch(1)
            lay.addLayout(row2)
        else:
            btn = QPushButton("열기")
            btn.clicked.connect(lambda: self.opened.emit(self.eid))
            lay.addWidget(btn, alignment=Qt.AlignLeft)
            # 카드 전체 클릭도 연다 — 대시보드 카드와 같은 문법 (루프 3회차 P11)
            self.setCursor(Qt.PointingHandCursor)
            self._clickable = True

    def mouseReleaseEvent(self, e):  # noqa: N802 — Qt 오버라이드
        if getattr(self, "_clickable", False):
            self.opened.emit(self.eid)
        super().mouseReleaseEvent(e)


class CoursePage(QWidget):
    open_episode = Signal(str)
    open_episode_ai = Signal(str)   # 영상 화면을 열고 AI 대화상자까지 (진입점 단일화 — 루프 3회차 P11)
    deleted = Signal()   # 프로젝트 삭제됨 → 대시보드로

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.cid: str | None = None
        self._ai_cards: list = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PAGE_PAD, 24, theme.PAGE_PAD, 24)
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("pageTitle")
        head.addWidget(self.title)
        head.addStretch(1)
        self.add_btn = QPushButton("+ 영상 추가")
        self.add_btn.clicked.connect(self._add_episode)
        head.addWidget(self.add_btn)
        outer.addLayout(head)
        self.error = QLabel("")
        self.error.setProperty("chip", "err")
        self.error.hide()
        outer.addWidget(self.error)

        self.tabs = QTabWidget()
        self.settings = CourseSettingsTab(make_studio)
        self.settings.deleted.connect(self.deleted.emit)
        self.board_scroll = QScrollArea()
        self.board_scroll.setWidgetResizable(True)
        self.brandkit = BrandKitTab(make_studio)
        self.brandkit.go_settings.connect(lambda: self.tabs.setCurrentIndex(1))
        # 번호를 붙이지 않는다 — 이 셋은 **순서가 아니다** (10 #6: 번호가 순서를
        # 사칭해 "①부터 해야 하나"로 읽혔다). 순서인 것은 영상 안의 4단계뿐.
        self.tabs.addTab(self.board_scroll, "영상 목록")
        self.tabs.addTab(self.settings, "설정")
        self.tabs.addTab(self.brandkit, "브랜드 킷")
        self.tabs.currentChanged.connect(self._tab_changed)
        outer.addWidget(self.tabs, 1)
        self._course: dict = {}

    def load(self, cid: str) -> None:
        self.cid = cid
        studio = self._make_studio()
        run_bg(lambda: studio.get_course(cid), done=self._fill, fail=self._fail)
        self._tab_changed(self.tabs.currentIndex())

    def _reflow_board(self) -> None:
        """레인 열 수 = 보드 폭에서 계산 — 좁으면 완료 레인이 아래로 쌓인다 (P6)."""
        wraps = getattr(self, "_lane_wraps", [])
        if not wraps:
            return
        per = theme.CARD_W + 24 + theme.GAP_CARD
        cols = max(1, min(len(wraps),
                          (self.board_scroll.viewport().width() + theme.GAP_CARD) // per))
        for i, w in enumerate(wraps):
            self._board_grid.addWidget(w, i // cols, i % cols, Qt.AlignTop | Qt.AlignLeft)

    def resizeEvent(self, e):  # noqa: N802 — Qt 오버라이드
        super().resizeEvent(e)
        self._reflow_board()

    def _tab_changed(self, idx: int) -> None:
        if not self.cid:
            return
        if idx == 1:
            self.settings.load(self.cid)
        elif idx == 2:
            self.brandkit.load(self.cid)

    def _fail(self, err) -> None:
        self.error.setText(error_text(err))
        self.error.show()

    def _fill(self, body: dict) -> None:
        self.error.hide()
        self._ai_cards = []
        course = body["course"]
        self._course = course
        self.title.setText(course.get("title", self.cid))
        holder = QWidget()
        from PySide6.QtWidgets import QGridLayout

        # 레인 3개 고정 가로 배치는 1180px 에서 완료 레인이 잘렸다 (16회차 발견, P6).
        # 대시보드와 같은 처방 — 창 폭에서 열 수를 계산해 좁으면 아래로 쌓는다
        self._board_grid = QGridLayout(holder)
        self._board_grid.setSpacing(theme.GAP_CARD)
        self._board_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._lane_wraps: list[QWidget] = []
        lanes: dict[str, QVBoxLayout] = {}
        empties: dict[str, QLabel] = {}
        for state in ("empty", "wip", "done"):
            box = QVBoxLayout()
            box.setSpacing(10)
            # 레인 제목 = 색 점 + 라벨 (이모지 금지 — 09 G4)
            head_row = QHBoxLayout()
            head_row.setSpacing(8)
            marker = QLabel()
            marker.setStyleSheet(theme.dot(theme.STATE_COLORS[state]))
            head = QLabel(STATE[state])
            head.setObjectName("sectionTitle")
            head_row.addWidget(marker)
            head_row.addWidget(head)
            head_row.addStretch(1)
            box.addLayout(head_row)
            lane = QVBoxLayout()
            lane.setAlignment(Qt.AlignTop)
            lane.setSpacing(10)
            box.addLayout(lane)
            blank = QLabel(EMPTY_LANE[state])   # 빈 레인도 말을 한다 (09 G1)
            blank.setObjectName("caption")
            box.addWidget(blank)
            empties[state] = blank
            box.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(box)
            wrap.setFixedWidth(theme.CARD_W + 24)
            self._lane_wraps.append(wrap)
            lanes[state] = lane
        for entry in course.get("episodes", []):
            badge = body["episodes"].get(entry["id"],
                                         {"id": entry["id"], "state": "empty", "stale": False})
            card = EpisodeCard(entry, badge)
            card.opened.connect(self.open_episode.emit)
            card.create.connect(self._create_episode)
            card.ai_draft.connect(self._ai_draft)
            card.delete_requested.connect(self._delete_episode)
            if badge["state"] == "empty":
                self._ai_cards.append(card)
            lanes.get(badge["state"], lanes["empty"]).addWidget(card)
            empties[badge["state"] if badge["state"] in empties else "empty"].hide()
        self.board_scroll.setWidget(holder)
        self._reflow_board()
        # 에이전트 게이트 — 키 없으면 버튼 비활성 + 사유 툴팁
        studio = self._make_studio()
        run_bg(studio.agent_status, done=self._apply_gate, fail=lambda _e: None)

    def _apply_gate(self, gate: dict) -> None:
        for card in self._ai_cards:
            btn = getattr(card, "ai_btn", None)
            if btn is None:
                continue
            btn.setEnabled(bool(gate.get("enabled")))
            btn.setToolTip(gate.get("reason")
                           or f"근거를 주면 초안을 만듭니다 ({gate.get('provider')} · "
                              f"{gate.get('models', {}).get('draft')})")

    def _begin_create(self) -> bool:
        """영상 생성 계열([영상 만들기]·[AI 초안]·[+ 영상 추가]) 공통 잠금.

        더블클릭이면 같은 n 에 생성이 두 번 나가 Conflict 오류가 노출된다 (35회차 P18).
        생성은 수백 ms — 플래그 하나로 직렬화하고 done/fail 에서 푼다."""
        if getattr(self, "_creating_episode", False):
            return False
        self._creating_episode = True
        return True

    def _end_create(self) -> None:
        self._creating_episode = False

    def _ai_draft(self, n: int) -> None:
        """[AI 초안] — 영상을 만들고(필요시) 영상 화면의 **완전판 AI 대화상자**로 간다.

        예전엔 여기서 자체 입력창으로 바로 제출했는데, ② 대본의 대화상자(근거 문서·
        영상까지 한 번에)와 경험이 갈라졌다 (루프 3회차 P11). 진입점을 하나로 합친다.
        """
        if not self._begin_create():
            return
        cid, studio = self.cid, self._make_studio()

        def ensure():
            board = {b["id"]: b for b in studio.course_board(cid)}
            entry = next((e for e in studio.get_course(cid)["course"].get("episodes", [])
                          if e.get("n") == n), None)
            eid = (entry or {}).get("id") or f"{cid}-{n:02d}"
            if board.get(eid, {}).get("state", "empty") == "empty":
                eid = studio.create_episode(cid, n)["id"]
            return eid

        run_bg(ensure,
               done=lambda eid: (self._end_create(), self.open_episode_ai.emit(eid)),
               fail=lambda e: (self._end_create(), self._fail(e)))

    # ── 스캐폴딩 (03 ② — 지금 수동으로 하는 것 전부) ─────────────────────────
    def _create_episode(self, n: int) -> None:
        if not self._begin_create():
            return
        cid, studio = self.cid, self._make_studio()
        run_bg(lambda: studio.create_episode(cid, n),
               done=lambda out: (self._end_create(), self.load(cid),
                                 self.open_episode.emit(out["id"])),
               fail=lambda e: (self._end_create(), self._fail(e)))

    def _delete_episode(self, eid: str, label: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        if QMessageBox.warning(
                self, "영상 삭제",
                f'"{label}" 영상을 삭제할까요?' + chr(10) + chr(10) +
                "대본·완성본(mp4)까지 지워지고 되돌릴 수 없습니다. "
                "자리는 남아 [영상 만들기]로 다시 만들 수 있습니다.",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        cid, studio = self.cid, self._make_studio()
        run_bg(lambda: studio.delete_episode(eid),
               done=lambda _out: self.load(cid), fail=self._fail)

    def _add_episode(self) -> None:
        ns = [e.get("n", 0) for e in self._course.get("episodes", [])]
        n = max(ns, default=0) + 1
        # 정적 getText 는 창이 좁다 — 인스턴스로 만들어 폭을 준다 (10: "폭을 좀 크게")
        dlg = QInputDialog(self)
        dlg.setWindowTitle("영상 추가")
        dlg.setLabelText(f"{n}편 제목")
        dlg.setMinimumWidth(560)
        dlg.resize(560, dlg.sizeHint().height())

        def _wire():
            # 빈 제목으로 [OK]를 누르면 조용히 무시되던 결함 — 제목이 있어야
            # 눌린다 (32회차 P19·P20. QInputDialog 내부 위젯은 show 후에 생긴다)
            from PySide6.QtWidgets import QDialogButtonBox

            bb = dlg.findChild(QDialogButtonBox)
            if bb:
                okb = bb.button(QDialogButtonBox.Ok)
                okb.setEnabled(bool(dlg.textValue().strip()))
                dlg.textValueChanged.connect(
                    lambda t: okb.setEnabled(bool(t.strip())))

        QTimer.singleShot(0, _wire)
        ok = bool(dlg.exec())
        title = dlg.textValue()
        if not ok or not title.strip():
            return
        if not self._begin_create():
            return
        cid, studio = self.cid, self._make_studio()
        run_bg(lambda: studio.create_episode(cid, n, title=title.strip()),
               done=lambda out: (self._end_create(), self.load(cid),
                                 self.open_episode.emit(out["id"])),
               fail=lambda e: (self._end_create(), self._fail(e)))
