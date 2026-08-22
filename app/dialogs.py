"""모달 다이얼로그 — 새 강좌 위저드 (03 ①: 스킬의 "강좌 개설 질문 4개"가 그대로 폼)."""

from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QRadioButton)

from .bridge import error_text, run_bg
from .pages.course_settings import VOICE_PRESETS
from .widgets import ColorButton


class NewCourseDialog(QDialog):
    """개설 위저드 — 한 번 정하면 시리즈 내내 고정된다 (수락 시 create_course 제출)."""

    def __init__(self, make_studio, parent=None):
        super().__init__(parent)
        self._make_studio = make_studio
        self.created: dict | None = None
        self.setWindowTitle("새 강좌 개설 — 한 번 정하면 시리즈 내내 고정됩니다")
        self.setMinimumWidth(520)

        form = QFormLayout(self)
        self.course_id = QLineEdit()
        self.course_id.setPlaceholderText("영문 소문자와 붙임표로 (예: hr-basics) — 폴더 이름이 됩니다")
        self.title = QLineEdit()
        self.tagline = QLineEdit()
        self.tagline.setPlaceholderText("예: 개념 하나를, 5분에")
        self.audience = QPlainTextEdit()
        self.audience.setPlaceholderText("누가 보는 강좌인지 — 대본의 눈높이가 여기서 정해집니다")
        self.audience.setFixedHeight(72)
        form.addRow("강좌 id", self.course_id)
        form.addRow("강좌명", self.title)
        form.addRow("태그라인", self.tagline)
        form.addRow("대상", self.audience)

        voice_row = QHBoxLayout()
        self.v_female = QRadioButton(VOICE_PRESETS["female"][1])
        self.v_female.setChecked(True)
        self.v_male = QRadioButton(VOICE_PRESETS["male"][1])
        voice_row.addWidget(self.v_female)
        voice_row.addWidget(self.v_male)
        voice_row.addStretch(1)
        form.addRow("목소리", voice_row)

        pal_row = QHBoxLayout()
        self.c_brand = ColorButton("#3E63DD")
        self.c_soft = ColorButton("#93A4F5")
        self.c_bg = ColorButton("#070b14")
        for label, btn in (("브랜드", self.c_brand), ("보조", self.c_soft),
                           ("배경", self.c_bg)):
            cap = QLabel(label)
            cap.setObjectName("caption")
            pal_row.addWidget(cap)
            pal_row.addWidget(btn)
            pal_row.addSpacing(14)
        pal_row.addStretch(1)
        form.addRow("색", pal_row)

        self.bgm = QComboBox()
        form.addRow("BGM", self.bgm)
        self.error = QLabel("")
        self.error.setProperty("chip", "err")
        self.error.hide()
        form.addRow("", self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("개설")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        studio = self._make_studio()
        run_bg(lambda: studio.assets("bgm"),
               done=lambda bgms: [self.bgm.addItem(a["name"], a["ref"]) for a in bgms],
               fail=lambda _e: None)

    def body(self) -> dict:
        return {
            "course": self.course_id.text().strip(),
            "title": self.title.text().strip(),
            "tagline": self.tagline.text().strip(),
            "audience": self.audience.toPlainText().strip(),
            "voice": dict(VOICE_PRESETS["male" if self.v_male.isChecked() else "female"][0]),
            "palette": {"brand": self.c_brand.value, "brandSoft": self.c_soft.value,
                        "bg": self.c_bg.value},
            "bgm": self.bgm.currentData(),
        }

    def _create(self) -> None:
        studio = self._make_studio()
        payload = self.body()
        run_bg(lambda: studio.create_course(payload),
               done=self._done, fail=self._fail)

    def _done(self, out: dict) -> None:
        self.created = out
        self.accept()

    def _fail(self, err) -> None:
        self.error.setText(error_text(err))
        self.error.show()
