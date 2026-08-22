"""대시보드 — 프로젝트 카드 (03 화면 지도. 5-3: 읽기 + 열기. [새 프로젝트]는 5-4)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import icons, theme
from ..bridge import error_text, run_bg


class CourseCard(QFrame):
    opened = Signal(str, bool)  # course_id, is_single

    def __init__(self, info: dict):
        super().__init__()
        self.setObjectName("card")
        self.info = info
        # 카드 1장일 때 화면 폭으로 늘어나지 않게 상한을 준다 (09 G3)
        self.setFixedWidth(theme.CARD_W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        # 아이콘 + 제목 한 줄 — 아이콘은 **그 프로젝트의 브랜드 색**으로 칠한다.
        # 색이 곧 정체성이라(타이틀 카드에 그대로 쓰인다) 목록에서 색만 보고 알아본다.
        head = QHBoxLayout()
        head.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(icons.project(info.get("brand") or "",
                                     series=not info.get("single")).pixmap(22, 22))
        mark.setFixedWidth(24)
        mark.setAlignment(Qt.AlignTop)
        head.addWidget(mark)
        title = QLabel(info.get("title", info["id"]))
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        head.addWidget(title, 1)
        lay.addLayout(head)
        if info.get("single"):
            sub = QLabel("단발 영상")
            sub.setObjectName("caption")
            lay.addWidget(sub)
        else:
            total, done = info["episodeCount"], info["done"]
            sub = QLabel(f"영상 {total}개 · 만든 것 {info['scaffolded']}")
            sub.setObjectName("caption")
            lay.addWidget(sub)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setValue(round(done / total * 100) if total else 0)
            lay.addWidget(bar)
            # 진행을 숫자로도 — 바만으로는 "몇 편 남았나"를 못 읽는다
            prog = QLabel(f"완료 {done} / {total}" if done < total else f"전부 완료 ({total}편)")
            prog.setObjectName("caption")
            prog.setStyleSheet(f"color: {theme.SUCCESS};" if done and done >= total else "")
            lay.addWidget(prog)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):  # noqa: N802 — Qt 오버라이드
        # 단발 프로젝트(홍보 등 1편)는 그 영상으로 직행 — 1장짜리 보드를 거치게 하지 않는다
        sole = self.info.get("soleEpisode")
        if sole:
            self.opened.emit(sole, True)
        else:
            self.opened.emit(self.info["id"], bool(self.info.get("single")))
        super().mouseReleaseEvent(e)


class DashboardPage(QWidget):
    open_course = Signal(str)
    open_episode = Signal(str)

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PAGE_PAD, 24, theme.PAGE_PAD, 24)

        head = QHBoxLayout()
        t = QLabel("프로젝트")
        t.setObjectName("pageTitle")
        head.addWidget(t)
        head.addStretch(1)
        self.new_btn = QPushButton("+ 새 프로젝트")
        self.new_btn.setObjectName("primary")
        self.new_btn.clicked.connect(self._new_course)
        head.addWidget(self.new_btn)
        outer.addLayout(head)
        desc = QLabel("시리즈와 단발 영상을 한 곳에서 — 카드를 열어 영상을 만들고 빌드하세요")
        desc.setObjectName("pageDesc")
        outer.addWidget(desc)

        self.error = QLabel("")
        self.error.setProperty("chip", "err")
        self.error.hide()
        outer.addWidget(self.error)

        self.empty = QLabel("아직 프로젝트가 없습니다 — 오른쪽 위 [+ 새 프로젝트] 로 시작하세요.\n"
                            "프로젝트를 만들면 목소리·색·BGM 이 모든 영상에 그대로 물려집니다.")
        self.empty.setObjectName("caption")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.hide()
        outer.addWidget(self.empty)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self.grid = QGridLayout(holder)
        self.grid.setSpacing(theme.GAP_CARD)
        self.grid.setContentsMargins(0, 8, 0, 0)
        # 좌상단 정렬 — 카드가 남는 폭·높이로 늘어나지 않게 (09 G3)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

    def refresh(self) -> None:
        studio = self._make_studio()
        run_bg(studio.list_courses, done=self._fill, fail=self._fail)

    def _new_course(self) -> None:
        from ..dialogs import NewCourseDialog

        dlg = NewCourseDialog(self._make_studio, self)
        if dlg.exec() and dlg.created:
            self.refresh()
            if dlg.created.get("episodeId"):   # 단발 — 빈 보드를 거치지 않는다
                self.open_episode.emit(dlg.created["episodeId"])
            else:
                self.open_course.emit(dlg.created["id"])

    def _fail(self, err) -> None:
        self.error.setText(error_text(err))
        self.error.show()

    def _fill(self, courses: list[dict]) -> None:
        self.error.hide()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.empty.setVisible(not courses)
        for i, info in enumerate(courses):
            card = CourseCard(info)
            card.opened.connect(lambda cid, single:
                                (self.open_episode.emit(cid) if single
                                 else self.open_course.emit(cid)))
            self.grid.addWidget(card, i // 4, i % 4, Qt.AlignTop | Qt.AlignLeft)
