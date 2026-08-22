"""미디어 라이브러리 (03_screens "라이브러리" 행).

소재 목록 = 폴더 스캔 × CATALOG.md(출처·라이선스) × ffprobe 실측(길이·해상도).
**라이선스 필드가 필수**다 — 없이 받기는 core 가 거부한다. 화면은 그 규약을 눈에 보이게 한다:
라이선스가 빈 소재는 빨간 "없음" 으로 뜨고, 받기 폼도 라이선스를 비우면 못 넘어간다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import theme
from ..bridge import error_text, run_bg
from ..widgets import AudioPreview

KINDS = [("broll", "B롤 영상"), ("bgm", "배경음악"), ("photo", "사진"), ("font", "글꼴")]


class LibraryPage(QWidget):
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self._rows: list[dict] = []
        self.audio = AudioPreview()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PAGE_PAD, 24, theme.PAGE_PAD, 24)
        head = QHBoxLayout()
        title = QLabel("라이브러리")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.kind = QComboBox()
        for value, label in KINDS:
            self.kind.addItem(label, value)
        self.kind.setFixedWidth(140)
        self.kind.currentIndexChanged.connect(self.refresh)
        head.addWidget(self.kind)
        outer.addLayout(head)
        desc = QLabel("영상에 쓸 소재입니다. 출처와 라이선스는 받을 때 CATALOG.md 에 함께 "
                      "기록됩니다 — 라이선스를 모르는 소재는 받지 않습니다.")
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["파일", "길이 · 해상도", "라이선스", "출처", "메모"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 180)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_select)
        outer.addWidget(self.table, 1)

        play_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ 미리듣기")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._play)
        self.ref_label = QLabel("")
        self.ref_label.setObjectName("caption")
        play_row.addWidget(self.play_btn)
        play_row.addWidget(self.ref_label, 1)
        outer.addLayout(play_row)

        # ── 받기 (fetch.js 경유 — 허용 호스트 검증은 엔진이 한다) ────────────
        add_head = QLabel("새 소재 받기")
        add_head.setObjectName("sectionTitle")
        outer.addWidget(add_head)
        form = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("소재 URL (Pexels·Mixkit 등 허용 출처)")
        self.license = QLineEdit()
        self.license.setPlaceholderText("라이선스 (필수 — 예: Pexels License)")
        self.license.setFixedWidth(240)
        self.name = QLineEdit()
        self.name.setPlaceholderText("저장 이름 (선택)")
        self.name.setFixedWidth(180)
        self.add_btn = QPushButton("받기")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self._add)
        for w in (self.url, self.license, self.name, self.add_btn):
            form.addWidget(w, 1 if w is self.url else 0)
        outer.addLayout(form)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        self.result.setWordWrap(True)
        outer.addWidget(self.result)

    # ── 목록 ────────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        kind = self.kind.currentData()
        studio = self._make_studio()
        self.result.setText("불러오는 중…")
        run_bg(lambda: studio.assets(kind), done=self._fill,
               fail=lambda e: self.result.setText(error_text(e)))

    def _fill(self, rows: list[dict]) -> None:
        self._rows = rows
        self.table.setRowCount(len(rows))
        unlicensed = 0
        for i, a in enumerate(rows):
            size = ""
            if a.get("duration"):
                m, s = divmod(int(a["duration"]), 60)
                size = f"{m}:{s:02d}"
            if a.get("width"):
                size = f"{size} · {a['width']}×{a['height']}" if size else f"{a['width']}×{a['height']}"
            lic = QTableWidgetItem(a.get("license") or "없음")
            if not a.get("license"):
                lic.setForeground(Qt.red)
                unlicensed += 1
            for col, item in enumerate([QTableWidgetItem(a["name"]), QTableWidgetItem(size), lic,
                                        QTableWidgetItem(a.get("source", "")),
                                        QTableWidgetItem(a.get("note", ""))]):
                self.table.setItem(i, col, item)
        self.result.setText(
            f"{len(rows)}개" + (f" · 라이선스 미기재 {unlicensed}개 — CATALOG.md 를 채우세요"
                                if unlicensed else "")
            if rows else "아직 받은 소재가 없습니다 — 아래에서 URL 과 라이선스를 넣어 받으세요.")

    def _on_select(self) -> None:
        row = self.table.currentRow()
        ok = 0 <= row < len(self._rows)
        kind = self.kind.currentData()
        self.play_btn.setEnabled(ok and kind in ("bgm", "broll"))
        self.ref_label.setText(f"대본 기입값: {self._rows[row]['ref']}" if ok else "")

    def _play(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._rows)):
            return
        kind, name = self.kind.currentData(), self._rows[row]["name"]
        studio = self._make_studio()
        run_bg(lambda: studio.asset_path(kind, name), done=self.audio.play,
               fail=lambda e: self.result.setText(error_text(e)))

    # ── 받기 ────────────────────────────────────────────────────────────────
    def _add(self) -> None:
        url, lic = self.url.text().strip(), self.license.text().strip()
        if not url:
            self.result.setText("URL 을 넣으세요")
            return
        if not lic:   # core 도 거부하지만, 화면에서 먼저 막는 것이 이 앱의 1원칙
            self.result.setText("라이선스가 필요합니다 — 소재 페이지에서 확인해 적으세요")
            return
        kind, name = self.kind.currentData(), self.name.text().strip() or None
        studio = self._make_studio()
        self.add_btn.setEnabled(False)
        self.result.setText("받는 중…")
        run_bg(lambda: studio.add_asset(kind=kind, url=url, license=lic, name=name),
               done=self._added,
               fail=lambda e: (self.result.setText(error_text(e)),
                               self.add_btn.setEnabled(True)))

    def _added(self, out: dict) -> None:
        self.add_btn.setEnabled(True)
        self.url.clear()
        self.name.clear()
        self.result.setText(f"{out['name']} 받음 — CATALOG.md 에 기록됨")
        self.refresh()
