"""④ 구성표 — plan.md 편집 (03 ④. 예산이 여기서 결정된다).

마크다운 라운드트립(사람이 에디터로 열어도 읽히는 형태 유지) + 파싱된 구간 표 미리보기 +
예산 게이지 + [대본으로 반영](없는 구간만 표 순서 자리에 골격 클립 삽입).

셀 단위 구조 편집은 후속 — 표 파싱(core.plan_apply.parse_plan_rows)이 정본이라
원문을 고치면 표·예산이 즉시 따라온다.
"""

from __future__ import annotations

import re

from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)
from PySide6.QtCore import Qt, Signal

from core.plan_apply import parse_plan_rows

from .. import theme
from ..bridge import error_text, run_bg


class PlanTab(QWidget):
    applied = Signal()  # [대본으로 반영] 성공 → ⑤ 재로드

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.eid: str | None = None
        self._etag: str | None = None
        self._budget = 1850

        lay = QVBoxLayout(self)
        self.budget_label = QLabel("")
        lay.addWidget(self.budget_label)
        self.budget_bar = QProgressBar()
        self.budget_bar.setTextVisible(False)
        self.budget_bar.setFixedHeight(6)
        lay.addWidget(self.budget_bar)

        split = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["구간", "화면", "글자수"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(2, 90)
        # 남는 폭은 "화면" 열이 먹는다 — 표가 좌측 1/3 에 몰리지 않게 (09 G2)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        split.addWidget(self.table)
        self.raw = QPlainTextEdit()
        # 마크다운 표는 고정폭이라야 열이 보인다
        self.raw.setStyleSheet("font-family: Consolas, 'D2Coding', monospace;")
        self.raw.textChanged.connect(self._on_edit)
        split.addWidget(self.raw)
        split.setSizes([420, 380])   # 표가 잘리지 않게 (09 G3)
        lay.addWidget(split, 1)

        row = QHBoxLayout()
        self.save_btn = QPushButton("plan.md 저장")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.apply_btn = QPushButton("대본으로 반영 (없는 구간 → 클립 골격)")
        self.apply_btn.clicked.connect(self._apply)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        row.addWidget(self.save_btn)
        row.addWidget(self.apply_btn)
        row.addWidget(self.result)
        row.addStretch(1)
        lay.addLayout(row)

    def load(self, eid: str, budget_text: str = "") -> None:
        self.eid = eid
        m = re.search(r"([\d,]+)\s*자", budget_text or "")
        self._budget = int(m.group(1).replace(",", "")) if m else 1850
        studio = self._make_studio()
        run_bg(lambda: studio.get_plan(eid), done=self._fill,
               fail=lambda e: (self.raw.setPlainText(""), self.result.setText(error_text(e))))

    def _fill(self, body: dict) -> None:
        self._etag = body["etag"]
        # 파일에서 읽어 넣는 것뿐이다 — setPlainText 의 textChanged 를 막지 않으면
        # 로드가 사용자 편집으로 오인된다. 표·예산은 아래 _on_edit 로 직접 갱신한다 (08 §7)
        self.raw.blockSignals(True)
        self.raw.setPlainText(body["markdown"])
        self.raw.blockSignals(False)
        self._on_edit()

    def _on_edit(self) -> None:
        rows = [r for r in parse_plan_rows(self.raw.toPlainText())
                if r["id"] and "합계" not in r["id"]]
        self.table.setRowCount(len(rows))
        total = 0
        for i, r in enumerate(rows):
            total += r["chars"] or 0
            # 마크다운 기호를 걷어내고 보여준다 — `**도식**`·백틱이 날것으로 보이면 안 된다 (09 G7)
            screen = re.sub(r"[`*]", "", r["screen"]).strip()
            for j, v in enumerate([r["id"], screen, str(r["chars"] or "")]):
                self.table.setItem(i, j, QTableWidgetItem(v))
        pct = round(total / self._budget * 100) if self._budget else 0
        self.budget_label.setText(f"예산 {total:,} / {self._budget:,}자 · {pct}%"
                                  + (" — 넘치면 압축이 아니라 영상 분할" if pct > 100 else ""))
        self.budget_label.setStyleSheet(
            f"color: {theme.DANGER}; font-weight: 700;" if pct > 100 else "")
        self.budget_bar.setValue(min(100, pct))

    def _save(self) -> None:
        eid, etag, studio = self.eid, self._etag, self._make_studio()
        md = self.raw.toPlainText()
        run_bg(lambda: studio.put_plan(eid, md, etag),
               done=lambda out: (setattr(self, "_etag", out["etag"]),
                                 self.result.setText("저장됨 ✓")),
               fail=lambda e: self.result.setText(error_text(e)))

    def _apply(self) -> None:
        eid, studio = self.eid, self._make_studio()
        run_bg(lambda: studio.plan_apply(eid), done=self._applied,
               fail=lambda e: self.result.setText(error_text(e)))

    def _applied(self, out: dict) -> None:
        added = out.get("added") or []
        QMessageBox.information(
            self, "대본으로 반영",
            f"클립 골격 추가: {', '.join(added)} — ⑤ 에서 내레이션을 채우세요"
            if added else "반영할 새 구간 없음 (기존 클립은 보존)")
        self.result.setText(f"반영 {len(added)}건")
        if added:
            self.applied.emit()
