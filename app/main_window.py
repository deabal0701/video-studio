"""MainWindow — 단일 창 + 좌측 내비 + 페이지 스택 + 하단 상태바 (07 창 지도)."""

from __future__ import annotations

from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QStatusBar, QWidget)

from core import env

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
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(200)
        # 이모지 금지 — OS 폰트가 제각각으로 그린다 (09 G4). 텍스트만으로 충분하다
        for label in ("대시보드", "라이브러리", "작업 큐", "설정"):
            QListWidgetItem(label, self.nav)
        self.nav.setCurrentRow(0)
        lay.addWidget(self.nav)

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
        self.setCentralWidget(central)

        # 내비 ↔ 스택 (프로젝트/영상 페이지는 내비 밖 — 카드 열기로 진입)
        self.nav.currentRowChanged.connect(self._nav_to)
        self.dashboard.open_course.connect(self.show_course)
        self.dashboard.open_episode.connect(self.show_episode)
        self.course_page.open_episode.connect(self.show_episode)

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
    def _nav_to(self, row: int) -> None:
        self.stack.setCurrentIndex([0, 3, 4, 5][row] if row < 4 else 0)
        if row == 0:
            self.dashboard.refresh()
        elif row == 1:
            self.library_page.refresh()
        elif row == 2:
            self.jobs_page.refresh()
        elif row == 3:
            self.settings_page.refresh()

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
