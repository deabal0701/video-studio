"""MainWindow — 단일 창 + 좌측 내비 + 페이지 스택 + 하단 상태바 (07 창 지도)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QStackedWidget, QStatusBar, QVBoxLayout,
                               QWidget)

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

        # 내비 열 = 브랜드 머리 + 메뉴. **창의 좌상단은 시선이 가장 먼저 닿는 자리인데**
        # 지금까지 거기 앉아 있던 것은 가장 약한 것(작은 회색 메뉴 글자)이었고, 바로 옆
        # 본문에는 28px 볼드 제목이 있어 위계가 뒤집혀 있었다 (P22). 또 설치형 앱인데
        # 클라이언트 영역 어디에도 제품 이름이 없어 "Video Studio" 를 말하는 것은 OS
        # 제목줄의 작은 회색 글자뿐이었다 (P14·P25 — 여러 창 사이에서 자기를 못 밝힌다).
        # (2026-08-23 사용자: "제목표시줄과 약간의 공백 — 다른 것을 채워 넣을 수 있나")
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(200)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(0)

        brand = QWidget()
        brand_lay = QHBoxLayout(brand)
        # 로고 왼쪽 16px = 내비 항목 아이콘의 왼쪽 여백 — 세로선이 하나로 맞는다
        brand_lay.setContentsMargins(16, 14, 14, 12)
        brand_lay.setSpacing(9)
        mark = QLabel()
        mark.setPixmap(icons.app_icon().pixmap(24, 24))
        mark.setFixedWidth(24)
        brand_lay.addWidget(mark)
        word = QLabel("Video Studio")
        word.setObjectName("brandWord")
        brand_lay.addWidget(word, 1)
        side_lay.addWidget(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        # 이모지 금지 — OS 폰트가 제각각으로 그린다 (09 G4).
        # 아이콘이 필요하면 **코드로 그린다** (app/icons.py) — 어느 PC 에서나 같은 그림이다
        # "새 영상 만들기"는 화면이 아니라 **행동** — 첫 목적(영상 하나 만들기)이
        # 대시보드 안 [+ 새 프로젝트]에 숨어 있으면 못 찾는다 (2026-08-23 사용자 지적)
        for key, label in (("dashboard", "대시보드"), ("create", "새 영상 만들기"),
                           ("library", "라이브러리"), ("jobs", "작업 큐"),
                           ("settings", "설정")):
            accent = key == "create"
            item = QListWidgetItem(
                icons.nav(key, theme.ACCENT if accent else theme.INK_2), label, self.nav)
            item.setData(Qt.UserRole, key)
            if accent:
                from PySide6.QtGui import QColor
                item.setForeground(QColor(theme.ACCENT))
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setCurrentRow(0)
        self._nav_row = 0              # 마지막 "화면" 행 — 행동 항목 클릭 후 복귀 지점
        self._new_video_open = False   # 위저드 이중 오픈 방지 (press·release 가 따로 온다)
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
    def _nav_to(self, row: int) -> None:
        if row == 1:   # "새 영상 만들기" — 화면 전환이 아니라 위저드를 연다
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(self._nav_row)
            self.nav.blockSignals(False)
            if not self._new_video_open:
                # 시그널 핸들러 안에서 exec() 하면 release 이벤트가 두 번째
                # 대화상자를 연다 — 이벤트 루프로 미룬다
                self._new_video_open = True
                QTimer.singleShot(0, self._new_video)
            return
        self._nav_row = row
        self.stack.setCurrentIndex({0: 0, 2: 3, 3: 4, 4: 5}[row])
        if row == 0:
            self.dashboard.refresh()
        elif row == 2:
            self.library_page.refresh()
        elif row == 3:
            self.jobs_page.refresh()
        elif row == 4:
            self.settings_page.refresh()

    def _new_video(self) -> None:
        """내비 [새 영상 만들기] — 위저드에서 만들면 곧장 작업 화면으로.

        단발(홍보·광고·매뉴얼·일반)은 영상 화면 ② 대본으로 직행, 시리즈(강의)는
        영상 목록으로 (대시보드 [+ 새 프로젝트]와 같은 규칙)."""
        from .dialogs import NewCourseDialog

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
