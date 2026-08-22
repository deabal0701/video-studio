"""모달 다이얼로그 — 새 프로젝트 위저드 (03 ①: 스킬의 "프로젝트 만들기 질문 4개"가 그대로 폼)."""

from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QRadioButton, QVBoxLayout)

from core import kinds

from .bridge import error_text, run_bg

from .pages.course_settings import VOICE_PRESETS
from .widgets import ColorButton


class NewCourseDialog(QDialog):
    """개설 위저드 — 한 번 정하면 시리즈 내내 고정된다 (수락 시 create_course 제출)."""

    def __init__(self, make_studio, parent=None):
        super().__init__(parent)
        self._make_studio = make_studio
        self.created: dict | None = None
        # 종류를 바꿀 때 **사람이 고친 값은 덮지 않는다** — 자동으로 넣었던 값만 기억한다
        self._auto_lengths: set[str] = {k["length"] for k in kinds.KINDS.values()}
        self._auto_colors: set[str] = {c for k in kinds.KINDS.values()
                                       for c in k["palette"].values()}
        self.setWindowTitle("새 프로젝트 만들기 — 한 번 정하면 시리즈 내내 고정됩니다")
        self.setMinimumWidth(520)

        form = QFormLayout(self)

        # 종류가 먼저다 — 골격·길이·색이 여기서 갈린다 (core/kinds.py)
        kind_box = QVBoxLayout()
        kind_row = QHBoxLayout()
        self.kind_group = QButtonGroup(self)
        for value, label_text, _desc in kinds.choices():
            rb = QRadioButton(label_text)
            rb.setProperty("kindId", value)
            self.kind_group.addButton(rb)
            kind_row.addWidget(rb)
            if value == kinds.DEFAULT_KIND:
                rb.setChecked(True)
        kind_row.addStretch(1)
        kind_box.addLayout(kind_row)
        self.kind_note = QLabel("")
        self.kind_note.setObjectName("caption")
        self.kind_note.setWordWrap(True)
        kind_box.addWidget(self.kind_note)
        form.addRow("종류", kind_box)
        self.kind_group.buttonToggled.connect(self._on_kind)

        self.course_id = QLineEdit()
        self.course_id.setPlaceholderText("영문 소문자와 붙임표로 (예: hr-basics) — 폴더 이름이 됩니다")
        self.title = QLineEdit()
        self.tagline = QLineEdit()
        self.tagline.setPlaceholderText("예: 개념 하나를, 5분에")
        self.audience = QPlainTextEdit()
        self.audience.setPlaceholderText("누가 보는 프로젝트인지 — 대본의 눈높이가 여기서 정해집니다")
        self.audience.setFixedHeight(72)
        form.addRow("프로젝트 id", self.course_id)
        form.addRow("프로젝트 이름", self.title)
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
        _pal = kinds.get(kinds.DEFAULT_KIND)["palette"]
        self.c_brand = ColorButton(_pal["brand"])
        self.c_soft = ColorButton(_pal["brandSoft"])
        self.c_bg = ColorButton(_pal["bg"])
        for label, btn in (("브랜드", self.c_brand), ("보조", self.c_soft),
                           ("배경", self.c_bg)):
            cap = QLabel(label)
            cap.setObjectName("caption")
            pal_row.addWidget(cap)
            pal_row.addWidget(btn)
            pal_row.addSpacing(14)
        pal_row.addStretch(1)
        form.addRow("색", pal_row)

        self.length = QLineEdit()
        form.addRow("영상 길이", self.length)
        self.bgm = QComboBox()
        form.addRow("BGM", self.bgm)
        self.error = QLabel("")
        self.error.setProperty("chip", "err")
        self.error.hide()
        form.addRow("", self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("만들기")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._on_kind()   # 기본 종류의 설명·길이·색을 처음부터 보여준다

        studio = self._make_studio()
        run_bg(lambda: studio.assets("bgm"),
               done=lambda bgms: [self.bgm.addItem(a["name"], a["ref"]) for a in bgms],
               fail=lambda _e: None)

    def body(self) -> dict:
        return {
            "kind": self.kind(),
            "episodeLength": self.length.text().strip() or None,
            "course": self.course_id.text().strip(),
            "title": self.title.text().strip(),
            "tagline": self.tagline.text().strip(),
            "audience": self.audience.toPlainText().strip(),
            "voice": dict(VOICE_PRESETS["male" if self.v_male.isChecked() else "female"][0]),
            "palette": {"brand": self.c_brand.value, "brandSoft": self.c_soft.value,
                        "bg": self.c_bg.value},
            "bgm": self.bgm.currentData(),
        }

    def kind(self) -> str:
        btn = self.kind_group.checkedButton()
        return btn.property("kindId") if btn else kinds.DEFAULT_KIND

    def _on_kind(self, *_a) -> None:
        """종류를 바꾸면 그 종류의 기본 길이·색을 넣는다 (사람이 고친 값은 안 건드린다)."""
        spec = kinds.get(self.kind())
        self.kind_note.setText(spec["desc"])
        if not self.length.text().strip() or self.length.text().strip() in self._auto_lengths:
            self.length.setText(spec["length"])
        pal = spec["palette"]
        for btn, key in ((self.c_brand, "brand"), (self.c_soft, "brandSoft"),
                         (self.c_bg, "bg")):
            if btn.value in self._auto_colors:
                btn.set_value(pal[key])
        self._auto_lengths = {spec["length"]}
        self._auto_colors = set(pal.values())

    def _create(self) -> None:
        """단발 종류(홍보·광고·매뉴얼·일반)는 **영상 1편까지 함께** 만든다.

        "새 프로젝트를 누르면 영상이 만들어지는 것인가?" (2026-08-22 사용자) — 답이
        종류마다 달라야 직관적이다: 시리즈(강의)는 빈 프로젝트를 열어 편을 추가하고,
        단발은 만들기 = 곧 영상 1편이라 빈 보드를 거치지 않고 영상 화면으로 직행한다.
        """
        studio = self._make_studio()
        payload = self.body()
        single = not kinds.get(self.kind())["series"]

        def create():
            out = studio.create_course(payload)
            if single:
                ep = studio.create_episode(out["id"], 1, title=payload["title"])
                out["episodeId"] = ep["id"]
            return out

        run_bg(create, done=self._done, fail=self._fail)

    def _done(self, out: dict) -> None:
        self.created = out
        self.accept()

    def _fail(self, err) -> None:
        self.error.setText(error_text(err))
        self.error.show()
