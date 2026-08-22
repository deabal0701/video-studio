"""③ 브랜드 킷 — 프리셋 (재)적용 + 간이 프리뷰 (03 ③.

여기 프리뷰는 palette 가 타이틀 카드에 어떻게 앉는지 보여주는 축소판이다.
실물(엔진이 실제로 그리는 화면)은 ⑤ 대본 탭의 프리뷰가 정본 — 같은 문서·같은 시킹이라
그쪽이 곧 완성본이다 (D10).
"일관성 규약 노출: 스팅어는 회차마다 동일" — 회차별 편집 진입점을 두지 않는다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFormLayout, QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..bridge import error_text, run_bg


class BrandKitTab(QWidget):
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.cid: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 16, 8, 8)

        note = QLabel("타이틀 카드·스팅어는 강좌 정체성 — 회차마다 동일해야 합니다. "
                      "색은 ① 설정의 브랜드 팔레트가 정본입니다.")
        note.setObjectName("caption")
        lay.addWidget(note)

        # 간이 프리뷰 — palette 를 타이틀 카드 구도로
        self.preview = QFrame()
        self.preview.setFixedSize(480, 270)
        pv = QVBoxLayout(self.preview)
        pv.setAlignment(Qt.AlignCenter)
        self.pv_kicker = QLabel("")
        self.pv_kicker.setAlignment(Qt.AlignCenter)
        self.pv_title = QLabel("")
        self.pv_title.setAlignment(Qt.AlignCenter)
        pv.addWidget(self.pv_kicker)
        pv.addWidget(self.pv_title)
        pv_col = QVBoxLayout()
        pv_col.addWidget(self.preview)
        cap = QLabel("축소판입니다 — 엔진이 실제로 그리는 화면은 회차의 ⑤ 대본 탭 프리뷰에서 봅니다.")
        cap.setObjectName("caption")
        cap.setWordWrap(True)
        cap.setFixedWidth(480)
        pv_col.addWidget(cap)
        pv_col.addStretch(1)

        # '브랜드 킷' 인데 정작 킷(색·글꼴)이 안 보였다 — 프리뷰 옆에 편다 (09 G1·G3)
        kit_col = QVBoxLayout()
        kit_head = QLabel("이 강좌의 색과 글꼴")
        kit_head.setObjectName("sectionTitle")
        kit_col.addWidget(kit_head)
        self.kit_form = QFormLayout()
        self.kit_form.setLabelAlignment(Qt.AlignRight)
        kit_col.addLayout(self.kit_form)
        self.swatches: dict[str, tuple[QFrame, QLabel]] = {}
        for key, label in (("brand", "브랜드"), ("brandSoft", "보조"), ("bg", "배경")):
            chip = QFrame()
            chip.setFixedSize(30, 20)
            code = QLabel("")
            code.setObjectName("caption")
            cell = QHBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.addWidget(chip)
            cell.addWidget(code)
            cell.addStretch(1)
            holder = QWidget()
            holder.setLayout(cell)
            self.kit_form.addRow(label, holder)
            self.swatches[key] = (chip, code)
        self.font_label = QLabel("")
        self.font_label.setObjectName("caption")
        self.font_label.setWordWrap(True)
        self.kit_form.addRow("글꼴", self.font_label)
        edit_hint = QLabel("값은 ① 설정 탭에서 고칩니다 — 여기는 결과를 보는 곳입니다.")
        edit_hint.setObjectName("caption")
        edit_hint.setWordWrap(True)
        kit_col.addWidget(edit_hint)
        kit_col.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(28)
        body.addLayout(pv_col)
        body.addLayout(kit_col, 1)
        lay.addLayout(body)

        row = QHBoxLayout()
        self.apply_btn = QPushButton("타이틀·스팅어를 기본 디자인으로 되돌리기")
        self.apply_btn.clicked.connect(self._apply)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        row.addWidget(self.apply_btn)
        row.addWidget(self.result)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

    def load(self, cid: str) -> None:
        self.cid = cid
        studio = self._make_studio()
        run_bg(lambda: studio.get_course(cid), done=self._fill,
               fail=lambda e: self.result.setText(error_text(e)))

    def _fill(self, body: dict) -> None:
        d = body["course"]
        pal = d.get("palette", {})
        bg = pal.get("bg", "#070b14")
        brand = pal.get("brand", "#3E63DD")
        soft = pal.get("brandSoft", "#93A4F5")
        self.preview.setStyleSheet(f"background: {bg}; border-radius: 12px;")
        self.pv_kicker.setText(d.get("title", ""))
        self.pv_kicker.setStyleSheet(f"color: {soft}; font-size: 12px; letter-spacing: 2px;")
        self.pv_title.setText("1강 — 회차 제목 자리")
        self.pv_title.setStyleSheet(
            f"color: white; font-size: 24px; font-weight: 700;"
            f"border-bottom: 2px solid {brand}; padding-bottom: 6px;")
        for key, value in (("brand", brand), ("brandSoft", soft), ("bg", bg)):
            chip, code = self.swatches[key]
            chip.setStyleSheet(f"background: {value}; border: 1px solid #d7dae0;"
                               " border-radius: 4px;")
            code.setText(value)
        font = d.get("fontUrl") or d.get("font") or ""
        self.font_label.setText(font.rsplit("/", 1)[-1] if font else "강좌 기본 글꼴")

    def _apply(self) -> None:
        if QMessageBox.question(
                self, "프리셋 적용",
                "이 강좌의 타이틀 카드와 스팅어를 기본 디자인으로 덮어씁니다.\n"
                "직접 고친 내용이 있으면 사라집니다 — 계속할까요?") != QMessageBox.Yes:
            return
        cid, studio = self.cid, self._make_studio()
        run_bg(lambda: studio.apply_brand_kit(cid),
               done=lambda out: self.result.setText(f"적용됨 ✓ — {', '.join(out['copied'])}"),
               fail=lambda e: self.result.setText(error_text(e)))
