"""MainWindow — 단일 창 + 좌측 내비 + 페이지 스택 + 하단 상태바 (07 창 지도)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QPushButton, QStackedWidget, QStatusBar,
                               QVBoxLayout, QWidget)

from core import env

from . import icons, theme
from .bridge import Bridge
from .pages.course import CoursePage
from .pages.dashboard import DashboardPage
from .pages.episode import EpisodePage
from .pages.jobs import JobsPage
from .pages.library import LibraryPage
from .pages.settings import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Studio")
        self.resize(1280, 800)
        self.bridge = Bridge()
        # 잡 큐는 앱 수명 동안 하나 — Studio 는 페이지가 필요할 때 이 큐로 만든다
        self._studio = self.bridge.make_studio()
        self.make_studio = lambda: self._studio

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 창 상단 경계선 — OS 제목줄(흰색)과 흰 내비가 맞닿아 **창의 윗변이 반쪽만
        # 그어져 있었다**: 좌측 200px 은 ffffff→ffffff 라 경계가 아예 없고, 내비가
        # 끝나는 x=200 부터서야 ffffff→f5f5f7 로 선이 생겨 상단이 계단처럼 보인다
        # (2026-08-23 사용자: "화면 상단이 매끄럽지 않다" — 실측 픽셀로 확인).
        # 하단 상태바는 border-top 으로 이미 닫혀 있었다 — 같은 문법으로 위도 닫는다.
        top_rule = QFrame()
        top_rule.setObjectName("topRule")
        top_rule.setFixedHeight(1)
        outer.addWidget(top_rule)

        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 좌측 열 = **행동 하나 + 화면 목록**.
        #
        # 제목줄 아래 좌상단이 비어 보인다는 지적(2026-08-23)에 무엇을 채울지 정한 결과다.
        # 워드마크("Video Studio" 로고+글자)를 먼저 넣어 봤으나 **캡처에서 기각** —
        # Windows 제목줄이 바로 30px 위에서 같은 아이콘·같은 글자를 이미 그리고 있어
        # 같은 로고가 두 번 쌓였다 (P12 중복). 제목줄이 정체성을 말하므로 이 자리는
        # **기능**이 가져간다.
        #
        # 그 기능은 [새 영상 만들기]다 — 이 앱의 첫 목적이고, 원래 내비 **목록의 한 행**
        # 이었다. 그런데 목록의 다른 항목은 전부 "화면"인데 이것만 "행동"이라 (a) 화면
        # 이동으로 오해되고 (b) 선택 하이라이트가 옮겨가면 안 되어 blockSignals·QTimer
        # 특례 코드를 달고 있었다 (P11·P15). 버튼으로 승격하면 둘 다 사라진다:
        # 목록에는 화면만 남고, 시선이 가장 먼저 닿는 좌상단에 Primary Action 이 앉는다.
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(200)
        side_lay = QVBoxLayout(side)
        # 좌우 여백은 **버튼에만** 준다 — 내비 항목은 열 가장자리까지 닿아야
        # 선택 하이라이트가 띠로 읽히고 좌측 3px 강조 막대가 잘리지 않는다
        side_lay.setContentsMargins(0, 12, 0, 0)
        side_lay.setSpacing(0)

        btn_row = QWidget()
        btn_row_lay = QHBoxLayout(btn_row)
        btn_row_lay.setContentsMargins(12, 0, 12, 0)
        # 글자의 "+" 는 넣지 않는다 — 아이콘이 이미 네모난 플러스다 ("+ +" 로 읽힌다)
        self.new_video_btn = QPushButton("  새 영상 만들기")
        self.new_video_btn.setObjectName("primary")
        self.new_video_btn.setIcon(icons.nav("create", "#ffffff"))
        self.new_video_btn.setIconSize(QSize(16, 16))
        self.new_video_btn.setCursor(Qt.PointingHandCursor)
        self.new_video_btn.setToolTip("영상 한 편을 새로 시작합니다 — 어느 화면에서나")
        self.new_video_btn.setFixedHeight(34)
        self.new_video_btn.clicked.connect(self._new_video)
        btn_row_lay.addWidget(self.new_video_btn)
        side_lay.addWidget(btn_row)
        side_lay.addSpacing(14)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        # 이모지 금지 — OS 폰트가 제각각으로 그린다 (09 G4).
        # 아이콘이 필요하면 **코드로 그린다** (app/icons.py) — 어느 PC 에서나 같은 그림이다
        for key, label in (("dashboard", "대시보드"), ("library", "라이브러리"),
                           ("jobs", "작업 큐"), ("settings", "설정")):
            item = QListWidgetItem(icons.nav(key, theme.INK_2), label, self.nav)
            item.setData(Qt.UserRole, key)
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setCurrentRow(0)
        self._new_video_open = False   # 위저드 이중 오픈 방지
        side_lay.addWidget(self.nav, 1)
        lay.addWidget(side)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(self.make_studio)
        self.course_page = CoursePage(self.make_studio)
        self.episode_page = EpisodePage(self.make_studio)
        self.library_page = LibraryPage(self.make_studio)
        self.jobs_page = JobsPage(self.make_studio)
        self.settings_page = SettingsPage(self.make_studio)
        for w in (self.dashboard, self.course_page, self.episode_page,
                  self.library_page, self.jobs_page, self.settings_page):
            self.stack.addWidget(w)
        lay.addWidget(self.stack, 1)
        outer.addWidget(body, 1)
        self.setCentralWidget(central)

        # 내비 ↔ 스택 (프로젝트/영상 페이지는 내비 밖 — 카드 열기로 진입)
        self.nav.currentRowChanged.connect(self._nav_to)
        # **이미 선택된 항목을 다시 클릭**해도 이동해야 한다 — 프로젝트/영상 화면에선
        # 내비가 '대시보드'에 하이라이트돼 있어 currentRowChanged 가 안 울린다
        # (2026-08-22 사용자: "대시보드 메뉴를 클릭해도 돌아가지 않는다")
        self.nav.itemClicked.connect(lambda item: self._nav_to(self.nav.row(item)))
        self.dashboard.open_course.connect(self.show_course)
        self.dashboard.open_episode.connect(self.show_episode)
        self.course_page.open_episode.connect(self.show_episode)
        self.course_page.open_episode_ai.connect(
            lambda eid: (self.episode_page.open_with_ai(eid),
                         self.stack.setCurrentWidget(self.episode_page),
                         self._mark_nav_home()))
        self.episode_page.back.connect(self._back_to_course)
        # 작업 큐 행 더블클릭 → 해당 영상 (28회차 P5·P21 — 실패한 빌드의 재시도 길)
        self.jobs_page.open_episode.connect(self.show_episode)
        self.course_page.deleted.connect(
            lambda: (self._nav_to(0), self.nav.setCurrentRow(0)))

        # 하단 상태바 — 빌드 잡 칩 (전 페이지 공통, 07 재편 결정)
        bar = QStatusBar()
        self.job_chip = QLabel("대기 중인 빌드 없음")
        self.job_chip.setProperty("chip", "info")
        bar.addWidget(self.job_chip)
        self.env_label = QLabel(f"projects: {env.projects_root()}")
        self.env_label.setObjectName("caption")
        bar.addPermanentWidget(self.env_label)
        self.setStatusBar(bar)
        self.bridge.job_event.connect(self._on_job_event)
        self.bridge.job_event.connect(self.jobs_page.on_job_event)

        self.dashboard.refresh()

    # ── 페이지 전환 ──────────────────────────────────────────────────────────
    # 내비는 이제 **화면만** 담는다 (행동 [새 영상 만들기]는 위 버튼으로 승격) —
    # 그래서 행 번호와 스택 인덱스가 다시 1:1 이고, 행동 행을 걸러내던 특례가 없다.
    NAV_STACK = {0: 0, 1: 3, 2: 4, 3: 5}     # 대시보드·라이브러리·작업 큐·설정

    def _nav_to(self, row: int) -> None:
        if row not in self.NAV_STACK:
            return
        self.stack.setCurrentIndex(self.NAV_STACK[row])
        if row == 0:
            self.dashboard.refresh()
        elif row == 1:
            self.library_page.refresh()
        elif row == 2:
            self.jobs_page.refresh()
        elif row == 3:
            self.settings_page.refresh()

    def _new_video(self) -> None:
        """좌측 열 [+ 새 영상 만들기] — 위저드에서 만들면 곧장 작업 화면으로.

        단발(홍보·광고·매뉴얼·일반)은 영상 화면 ② 대본으로 직행, 시리즈(강의)는
        영상 목록으로 (대시보드 [+ 새 프로젝트]와 같은 규칙)."""
        from .dialogs import NewCourseDialog

        if self._new_video_open:      # 모달이 이미 떠 있으면 두 번째를 열지 않는다
            return
        self._new_video_open = True
        try:
            dlg = NewCourseDialog(self.make_studio, self)
            if dlg.exec() and dlg.created:
                self.dashboard.refresh()
                if dlg.created.get("episodeId"):
                    self.show_episode(dlg.created["episodeId"])
                else:
                    self.show_course(dlg.created["id"])
        finally:
            self._new_video_open = False

    def _mark_nav_home(self) -> None:
        """프로젝트·영상은 대시보드에서 파고든 화면이다 — 내비도 그렇게 말해야 한다.

        (2026-08-22 실측: 설정에 들렀다가 영상을 열면 내비는 "설정"에 남아 있어
        지금 보는 화면과 어긋났다. 09 G8 — 내가 어디 있는지가 틀리면 안 된다.)
        `currentRowChanged` 를 막지 않으면 `_nav_to` 가 대시보드로 되돌린다.
        """
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(0)
        self.nav.blockSignals(False)

    def show_course(self, cid: str) -> None:
        self.course_page.load(cid)
        self.stack.setCurrentWidget(self.course_page)
        self._mark_nav_home()

    def _back_to_course(self, cid: str) -> None:
        """[← 프로젝트] — 부모 프로젝트가 없으면(단일 영상) 대시보드로."""
        from core import env

        if (env.projects_root() / cid / "course.json").exists():
            self.show_course(cid)
        else:
            self.nav.setCurrentRow(0)

    def show_episode(self, eid: str) -> None:
        self.episode_page.load(eid)
        self.stack.setCurrentWidget(self.episode_page)
        self._mark_nav_home()

    # ── 잡 칩 (구 상단 SSE 칩의 등가) ────────────────────────────────────────
    def _on_job_event(self, job_id: str, episode_id: str, ev: dict) -> None:
        if ev.get("kind") == "state":
            state = ev["state"]
            terminal = state in ("done", "failed", "blocked", "canceled")
            self.job_chip.setText("대기 중인 빌드 없음" if terminal
                                  else f"빌드 중 · {episode_id} — {state}")
            self.job_chip.setProperty(
                "chip", "info" if terminal else "run")
            self.job_chip.style().unpolish(self.job_chip)
            self.job_chip.style().polish(self.job_chip)
        elif ev.get("kind") == "step":
            self.job_chip.setText(f"빌드 중 · {episode_id} — {ev.get('line', '').strip()[:60]}")
