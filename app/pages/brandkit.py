"""③ 브랜드 킷 — 프리셋 (재)적용 + 간이 프리뷰 (03 ③.

여기 프리뷰는 palette 가 타이틀 카드에 어떻게 앉는지 보여주는 축소판이다.
실물(엔진이 실제로 그리는 화면)은 ⑤ 대본 탭의 프리뷰가 정본 — 같은 문서·같은 시킹이라
그쪽이 곧 완성본이다 (D10).
"일관성 규약 노출: 스팅어는 영상마다 동일" — 영상별 편집 진입점을 두지 않는다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout, QFrame, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from core import kinds

from ..bridge import error_text, run_bg


_P = kinds.get(kinds.DEFAULT_KIND)["palette"]   # 색 폴백 (종류가 정본)

class BrandKitTab(QWidget):
    go_settings = Signal()   # [설정 탭에서 색 바꾸기] (루프 5회차 P1)
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.cid: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 16, 8, 8)

        note = QLabel("타이틀 카드·스팅어는 프로젝트 정체성 — 영상마다 동일해야 합니다. "
                      "색은 [설정] 탭의 브랜드 팔레트가 정본입니다.")
        note.setObjectName("caption")
        lay.addWidget(note)

        # 간이 프리뷰 — palette 를 타이틀 카드 구도로
        self.preview = QFrame()
        self.preview.setObjectName("kitPreview")
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
        cap = QLabel("축소판입니다 — 엔진이 실제로 그리는 화면은 영상의 ② 대본 탭 프리뷰에서 봅니다.")
        cap.setObjectName("caption")
        cap.setWordWrap(True)
        cap.setFixedWidth(480)
        pv_col.addWidget(cap)
        pv_col.addStretch(1)

        # '브랜드 킷' 인데 정작 킷(색·글꼴)이 안 보였다 — 프리뷰 옆에 편다 (09 G1·G3)
        kit_col = QVBoxLayout()
        kit_head = QLabel("이 프로젝트의 색과 글꼴")
        kit_head.setObjectName("sectionTitle")
        kit_col.addWidget(kit_head)
        self.kit_form = QFormLayout()
        self.kit_form.setLabelAlignment(Qt.AlignRight)
        kit_col.addLayout(self.kit_form)
        self.swatches: dict[str, tuple[QFrame, QLabel]] = {}
        for key, label in (("brand", "브랜드"), ("brandSoft", "보조"), ("bg", "배경")):
            chip = QFrame()
            chip.setObjectName("swatch")
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
        # 대비 검사는 **프리셋 팔레트에만** 있었다 (core/kinds.py 의 4.5:1 — tests 가 지킨다).
        # 설정 화면은 아무 색이나 고르게 하는데 아무 데서도 재지 않아, 밝은 배경을 고르면
        # 흰 제목 글자가 그대로 묻힌 채 영상이 나갔다 (53회차 P17·P20. 실측 1.0:1).
        # 브랜드 킷이 "결과를 보는 곳"이니 여기가 말할 자리다
        self.contrast_label = QLabel("")
        self.contrast_label.setWordWrap(True)
        self.contrast_label.setMaximumWidth(460)
        self.kit_form.addRow("대비", self.contrast_label)
        # 말로만 안내하지 않는다 — 가는 버튼을 준다 (루프 5회차 P1)
        edit_row = QHBoxLayout()
        self.edit_btn = QPushButton("설정 탭에서 색 바꾸기 →")
        self.edit_btn.setFlat(True)
        self.edit_btn.clicked.connect(self.go_settings.emit)
        edit_hint = QLabel("여기는 결과를 보는 곳입니다.")
        edit_hint.setObjectName("caption")
        edit_row.addWidget(self.edit_btn)
        edit_row.addWidget(edit_hint)
        edit_row.addStretch(1)
        kit_col.addLayout(edit_row)
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
        if cid != self.cid:
            # "적용됨 ✓ — …" 이 **다른 프로젝트** 브랜드 킷에 그대로 남아 있었다
            # (53회차 P19·P11 — 52회차 설정 탭과 같은 결함·같은 처방)
            self.result.setText("")
        self.cid = cid
        studio = self._make_studio()
        run_bg(lambda: studio.get_course(cid), done=self._fill,
               fail=lambda e: self.result.setText(error_text(e)))

    def _fill(self, body: dict) -> None:
        d = body["course"]
        pal = d.get("palette", {})
        bg = pal.get("bg", _P["bg"])
        brand = pal.get("brand", _P["brand"])
        soft = pal.get("brandSoft", _P["brandSoft"])
        # 선택자 필수 — 자식 라벨까지 물들이지 않게 (Qt 스타일시트는 자식에 전파된다)
        self.preview.setStyleSheet(f"#kitPreview {{ background: {bg};"
                                   " border-radius: 12px; }")
        self.pv_kicker.setText(d.get("title", ""))
        self.pv_kicker.setStyleSheet(f"color: {soft}; font-size: 12px; letter-spacing: 2px;")
        # 견본도 그 프로젝트의 말로 — 홍보 프로젝트 미리보기가 "1강"이었다 (51회차 P2)
        self.pv_title.setText(
            " — ".join(p for p in (kinds.counter(1, d.get("kind"))
                                   if kinds.get(d.get("kind"))["series"] else "",
                                   "영상 제목 자리") if p))
        self.pv_title.setStyleSheet(
            f"color: white; font-size: 24px; font-weight: 700;"
            f"border-bottom: 2px solid {brand}; padding-bottom: 6px;")
        for key, value in (("brand", brand), ("brandSoft", soft), ("bg", bg)):
            chip, code = self.swatches[key]
            chip.setStyleSheet(f"#swatch {{ background: {value};"
                               " border: 1px solid #d7dae0; border-radius: 4px; }")
            code.setText(value)
        font = d.get("fontUrl") or d.get("font") or ""
        self.font_label.setText(font.rsplit("/", 1)[-1] if font else "프로젝트 기본 글꼴")
        self._show_contrast(bg, brand, soft)

    # 엔진 기본 글자색 — engine/motion/_base.css 의 `--fg: #ffffff` (제목·본문이 이 색이다)
    FG = "#ffffff"
    MIN_CONTRAST = 4.5   # WCAG 본문 — core/kinds.py 가 프리셋에 쓰는 기준과 같다

    def _show_contrast(self, bg: str, brand: str, soft: str) -> None:
        pairs = (("제목 글자", self.FG), ("브랜드", brand), ("보조", soft))
        try:
            ratios = [(name, kinds.contrast(color, bg)) for name, color in pairs]
        except Exception:  # noqa: BLE001 — 색 형식이 이상해도 화면은 떠야 한다
            self.contrast_label.setText("")
            self.contrast_label.setProperty("chip", None)
            self._repolish(self.contrast_label)
            return
        detail = " · ".join(f"{name} {r:.1f}:1" for name, r in ratios)
        low = [name for name, r in ratios if r < self.MIN_CONTRAST]
        if low:
            # 칩 스타일이 이기게 objectName 을 비운다 — "caption" 이 남아 있으면
            # 다음 로드에서 err 칩이 캡션 색으로 덮인다
            self.contrast_label.setObjectName("")
            self.contrast_label.setProperty("chip", "err")
            self.contrast_label.setText(
                f"배경과 대비가 낮습니다 — {detail} (권장 {self.MIN_CONTRAST}:1 이상). "
                f"영상에서 {'·'.join(low)}가 묻힙니다 — [설정] 탭에서 색을 바꾸세요")
        else:
            self.contrast_label.setProperty("chip", None)
            self.contrast_label.setObjectName("caption")
            self.contrast_label.setText(f"배경 대비 {detail} — 권장({self.MIN_CONTRAST}:1) 이상입니다")
        self._repolish(self.contrast_label)

    @staticmethod
    def _repolish(w) -> None:
        w.style().unpolish(w)
        w.style().polish(w)

    def _apply(self) -> None:
        # 덮어쓰기는 파괴적 — 기본 버튼은 [취소] (16회차 소형 대화상자와 같은 문법)
        if QMessageBox.warning(
                self, "프리셋 적용",
                "이 프로젝트의 타이틀 카드와 스팅어를 기본 디자인으로 덮어씁니다.\n"
                "직접 고친 내용이 있으면 사라집니다 — 계속할까요?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        cid, studio = self.cid, self._make_studio()
        # 처리 중 상태 — 안 잠그면 중복 클릭이 두 번 실행된다 (P18·P20)
        self.apply_btn.setEnabled(False)
        self.result.setText("적용 중…")
        run_bg(lambda: studio.apply_brand_kit(cid),
               done=lambda out: (self.result.setText(
                   "적용됨 ✓ — "   # 파일명 날것 대신 표시명 (37회차 P2)
                   + " · ".join(kinds.screen_label(f) for f in out["copied"])),
                                 self.apply_btn.setEnabled(True)),
               fail=lambda e: (self.result.setText(error_text(e)),
                               self.apply_btn.setEnabled(True)))
