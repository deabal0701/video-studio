"""모달 다이얼로그 — 새 프로젝트 위저드.

**묻는 것은 셋뿐이다: 종류·이름·색** (10_ux-plan #4 — 점진적 노출: 기본만 보이고
고급은 요청 시). 나머지(id·태그라인·대상·목소리·색 직접 고르기)는 "자세한 설정"
접기 안에 있고, 전부 만든 뒤 [설정] 탭에서 바꿀 수 있다.

- **id 는 자동 생성** — 종류+날짜(+abc…)로 짓고, 이미 있으면 다음 글자로 물러난다.
  폴더명이 필요할 뿐 사용자가 지을 이유가 없다 ("프로젝트 id 꼭 필요한가?" — 사용자).
- **색은 프리셋 4종 원클릭** (파랑·주황·초록·검정 — 전부 대비 검증값). 직접 고르면
  프리셋 선택이 풀린다.
- BGM 은 여기서 묻지 않는다 — 기본 BGM 이 깔리고 [설정] 탭에서 바꾼다.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QRadioButton, QToolButton,
                               QVBoxLayout, QWidget)

from core import kinds
from core.facade import Conflict

from .bridge import error_text, run_bg
from .pages.course_settings import VOICE_PRESETS
from .widgets import ColorButton

# 길이 도우미는 core.kinds 공용 — 프로젝트 설정 탭과 같은 UX (루프 4회차 P11)
LENGTH_CHOICES = kinds.LENGTH_CHOICES
_length_to_chars = kinds.length_to_chars


def _palette_icon(pal: dict, size: int = 22) -> QIcon:
    """프리셋 견본 — 배경 위에 브랜드·보조 점. 말로 설명하지 않고 보여준다."""
    px = QPixmap(size * 2, size)
    px.setDevicePixelRatio(1.0)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QColor("#d2d2d7"))
    p.setBrush(QColor(pal["bg"]))
    p.drawRoundedRect(QRectF(0.5, 0.5, size * 2 - 1, size - 1), 6, 6)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(pal["brand"]))
    p.drawEllipse(QRectF(size * 0.35, size * 0.28, size * 0.44, size * 0.44))
    p.setBrush(QColor(pal["brandSoft"]))
    p.drawEllipse(QRectF(size * 1.05, size * 0.36, size * 0.28, size * 0.28))
    p.end()
    return QIcon(px)


def confirm_delete_course(parent, title: str) -> bool:
    """프로젝트 삭제 확인 — 대시보드 카드와 설정 탭이 **같은 말**을 쓴다 (64회차 P11).

    같은 파괴적 동작인데 대시보드에는 "완성본이 필요하면 먼저 저장해 두세요"가 빠져
    있었다. 기본 버튼은 [취소] (16회차 문법).
    """
    from PySide6.QtWidgets import QMessageBox

    return QMessageBox.warning(
        parent, "프로젝트 삭제",
        f'"{title}" 프로젝트를 삭제할까요?\n\n'
        "영상·대본·설정·완성본(mp4)까지 전부 지워지고 되돌릴 수 없습니다.\n"
        "완성본이 필요하면 먼저 ④ 배포에서 저장해 두세요.",
        QMessageBox.Yes | QMessageBox.Cancel,
        QMessageBox.Cancel) == QMessageBox.Yes


class NewCourseDialog(QDialog):
    """만들기 위저드 — 수락 시 create_course(+단발이면 영상 1편까지) 제출."""

    def __init__(self, make_studio, parent=None):
        super().__init__(parent)
        self._make_studio = make_studio
        self.created: dict | None = None
        self._custom_palette = False   # 직접 고르기를 쓰면 프리셋 추종을 멈춘다
        self.setWindowTitle("새 프로젝트 만들기")
        # 고급 설정을 펼친 크기로 **처음부터** 잡는다 — 펼칠 때 창이 널뛰지 않고,
        # 접힌 상태에선 내용이 위에 붙고 버튼이 바닥에 고정된다 (10: "이 크기로, 배치도")
        self.setMinimumSize(980, 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 22)
        body = QHBoxLayout()
        body.setSpacing(28)
        left = QVBoxLayout()
        formw = QWidget()
        form = QFormLayout(formw)
        form.setContentsMargins(0, 0, 0, 0)
        # 숨 쉴 간격 — 좁으면 폼이 벽처럼 읽힌다 (10: "위/아래 간격도 좀 넓게")
        form.setVerticalSpacing(22)
        form.setHorizontalSpacing(18)
        left.addWidget(formw)
        left.addStretch(1)   # 남는 높이는 여기 — 폼 행간이 벌어지지 않게 (08 §4-1)
        body.addLayout(left, 1)
        # 우측 — **실시간 미리보기**: 빈 공간을 의미로 채운다 (루프 2회차 P13 —
        # "화면 사이즈에 비해 배치가 안 맞는다"). 고른 색·이름이 타이틀 카드에 앉는 모습
        body.addWidget(self._make_preview_column(), 0)
        outer.addLayout(body, 1)

        # ── 종류 — 골격·길이·색이 여기서 갈린다 ────────────────────────────
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

        # ── 이름 — 유일한 필수 입력 ─────────────────────────────────────────
        self.title = QLineEdit()
        self.title.setPlaceholderText("예: 여름 신제품 소개")
        self.title.textChanged.connect(self._update_preview)   # 미리보기에 실시간 반영
        form.addRow("프로젝트 이름", self.title)

        # ── 색 — 프리셋 4종 원클릭 ──────────────────────────────────────────
        pal_box = QVBoxLayout()
        pal_row = QHBoxLayout()
        self.preset_group = QButtonGroup(self)
        self._preset_buttons: dict[str, QPushButton] = {}
        for name, pal in kinds.PRESET_PALETTES:
            b = QPushButton(name)
            b.setObjectName("palettePreset")   # 선택 상태 스타일 (theme)
            b.setCheckable(True)
            b.setIcon(_palette_icon(pal))
            b.setIconSize(_palette_icon(pal).availableSizes()[0])
            b.setProperty("presetName", name)
            self.preset_group.addButton(b)
            self._preset_buttons[name] = b
            pal_row.addWidget(b)
        pal_row.addStretch(1)
        pal_box.addLayout(pal_row)
        pal_note = QLabel("영상의 바탕·강조 색입니다 — 다른 색은 아래 [고급 설정]에서 직접 고릅니다.")
        pal_note.setObjectName("caption")
        pal_note.setWordWrap(True)
        pal_box.addWidget(pal_note)
        form.addRow("색", pal_box)
        self.preset_group.buttonToggled.connect(self._on_preset)

        # ── 길이 — 콤보 + 직접 입력 ─────────────────────────────────────────
        len_box = QVBoxLayout()
        self.length = QComboBox()
        self.length.setEditable(True)
        self.length.addItems(LENGTH_CHOICES)
        self.length.setFixedWidth(200)
        self.length.currentTextChanged.connect(self._sync_length_note)
        len_box.addWidget(self.length)
        self.length_note = QLabel("")
        self.length_note.setObjectName("caption")
        len_box.addWidget(self.length_note)
        form.addRow("영상 길이", len_box)

        # ── 자세한 설정 (접기 — 펼치지 않으면 전부 기본값) ──────────────────
        self.adv_btn = QToolButton()
        self.adv_btn.setText("고급 설정 — 태그라인·목소리·폴더·색 직접 고르기")
        self.adv_btn.setCheckable(True)
        self.adv_btn.setArrowType(Qt.RightArrow)
        self.adv_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        form.addRow("", self.adv_btn)

        self.adv = QWidget()
        adv_form = QFormLayout(self.adv)
        adv_form.setContentsMargins(0, 0, 0, 0)
        adv_form.setVerticalSpacing(12)

        self.tagline = QLineEdit()
        self.tagline.setPlaceholderText("한 줄 소개 (선택 — 예: 개념 하나를, 5분에)")
        adv_form.addRow("태그라인", self.tagline)
        self.audience = QPlainTextEdit()
        self.audience.setPlaceholderText("누가 보는 영상인지 — 대본의 눈높이가 여기서 정해집니다 (선택)")
        self.audience.setFixedHeight(60)
        adv_form.addRow("대상", self.audience)

        # 긴 라벨("선희 (여) · 말 속도 +8%") 두 개는 폼 폭을 넘어 잘린다 (18회차 P6)
        # — 이름만 보이고 상세는 툴팁, 안내문은 별도 폼 행(행 높이 눌림 방지)
        voice_row = QHBoxLayout()
        self.v_female = QRadioButton(VOICE_PRESETS["female"][1].split(" · ")[0])
        self.v_female.setToolTip(VOICE_PRESETS["female"][1])
        self.v_female.setChecked(True)
        self.v_male = QRadioButton(VOICE_PRESETS["male"][1].split(" · ")[0])
        self.v_male.setToolTip(VOICE_PRESETS["male"][1])
        voice_row.addWidget(self.v_female)
        voice_row.addWidget(self.v_male)
        voice_row.addStretch(1)
        adv_form.addRow("목소리", voice_row)
        voice_note = QLabel("만든 뒤 [설정] 탭에서 제공자·목소리를 자세히 고를 수 있습니다")
        voice_note.setObjectName("caption")
        voice_note.setWordWrap(True)   # 폭이 모자라면 줄바꿈 — 끝 글자 잘림 방지
        adv_form.addRow("", voice_note)

        self.course_id = QLineEdit()
        self.course_id.setPlaceholderText("비우면 자동 (예: summer-promo — 영문 소문자·붙임표, 폴더 이름)")
        # 규약을 placeholder 로만 말하지 않는다 — 어긋난 글자는 입력 자체가 안 된다
        # (50회차 P20. 폴더명은 경로 규약이라 사후 오류보다 사전 차단)
        from PySide6.QtCore import QRegularExpression
        from PySide6.QtGui import QRegularExpressionValidator

        self.course_id.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[a-z0-9-]*")))
        adv_form.addRow("폴더 이름", self.course_id)

        custom_row = QHBoxLayout()
        _pal = kinds.get(kinds.DEFAULT_KIND)["palette"]
        self.c_brand = ColorButton(_pal["brand"])
        self.c_soft = ColorButton(_pal["brandSoft"])
        self.c_bg = ColorButton(_pal["bg"])
        for cap_text, btn in (("브랜드", self.c_brand), ("보조", self.c_soft),
                              ("배경", self.c_bg)):
            cap = QLabel(cap_text)
            cap.setObjectName("caption")
            custom_row.addWidget(cap)
            custom_row.addWidget(btn)
            custom_row.addSpacing(14)
            btn.changed.connect(self._on_custom_color)
        custom_row.addStretch(1)
        adv_form.addRow("색 직접", custom_row)

        # 앱 화면 녹화 (I-2) — 주소를 넣으면 그 화면을 찍어 영상에 넣는다.
        # 비밀번호는 여기 두지 않는다: .env 의 **이름**만 적는다 (대본·설정은 공유 대상 — I-5)
        self.capture_url = QLineEdit()
        self.capture_url.setPlaceholderText(
            "예: http://내앱.example.com:8080 (선택 — 넣으면 그 화면을 녹화합니다)")
        adv_form.addRow("앱 주소", self.capture_url)
        login_row = QHBoxLayout()
        self.capture_user = QLineEdit()
        self.capture_user.setPlaceholderText("로그인 아이디 (필요할 때만)")
        self.capture_pw_env = QLineEdit()
        self.capture_pw_env.setPlaceholderText("비밀번호가 든 .env 이름 (예: MYAPP_PW)")
        login_row.addWidget(self.capture_user)
        login_row.addWidget(self.capture_pw_env)
        adv_form.addRow("로그인", login_row)
        pw_note = QLabel("비밀번호 자체는 저장하지 않습니다 — 설정의 .env 에 두고 그 이름만 적습니다")
        pw_note.setObjectName("caption")
        pw_note.setWordWrap(True)
        adv_form.addRow("", pw_note)

        self.adv.hide()
        form.addRow("", self.adv)
        self.adv_btn.toggled.connect(self._toggle_adv)

        self.error = QLabel("")
        self.error.setProperty("chip", "err")
        self.error.setWordWrap(True)
        self.error.hide()
        outer.addWidget(self.error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.create_btn = buttons.button(QDialogButtonBox.Ok)
        self.create_btn.setText("만들기")
        self.create_btn.setObjectName("primary")
        # 이름이 있어야 눌린다 (P20) — 그리고 만드는 동안 잠근다: 중복 클릭이면
        # 자동 id 가 a·b… 로 물러나며 프로젝트가 2개 생긴다 (34회차 P18)
        self._creating = False
        self.create_btn.setEnabled(False)
        self.title.textChanged.connect(self._sync_create_btn)
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._on_kind()   # 기본 종류의 설명·길이·프리셋을 처음부터 보여준다
        self._update_preview()

    # ── 미리보기 (P13 — 남는 폭의 쓸모) ─────────────────────────────────────
    def _make_preview_column(self) -> QWidget:
        col = QWidget()
        col.setFixedWidth(400)
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        head = QLabel("미리보기")
        head.setObjectName("sectionTitle")
        lay.addWidget(head)
        self.pv = QWidget()
        self.pv.setObjectName("wizPreview")
        self.pv.setFixedSize(384, 216)
        pv_lay = QVBoxLayout(self.pv)
        pv_lay.setAlignment(Qt.AlignCenter)
        self.pv_kicker = QLabel("")
        self.pv_kicker.setAlignment(Qt.AlignCenter)
        self.pv_title = QLabel("")
        self.pv_title.setAlignment(Qt.AlignCenter)
        self.pv_title.setWordWrap(True)
        pv_lay.addWidget(self.pv_kicker)
        pv_lay.addWidget(self.pv_title)
        lay.addWidget(self.pv)
        note = QLabel("고른 색과 이름이 타이틀 카드에 이렇게 앉습니다 — 만든 뒤에도 바꿀 수 있습니다.")
        note.setObjectName("caption")
        note.setWordWrap(True)
        lay.addWidget(note)
        # 색을 **고르는 곳**에서 대비를 말한다 — 53회차는 결과를 보는 브랜드 킷에만 넣어,
        # 여기서 밝은 배경을 골라도 아무 말이 없었다 (66회차 실측: 흰 글자/배경 1.0:1 —
        # 위 미리보기가 백지가 되는데 경고 0건). 판정은 core.kinds 가 갖는다
        self.contrast_note = QLabel("")
        self.contrast_note.setWordWrap(True)
        self.contrast_note.setMaximumWidth(384)
        lay.addWidget(self.contrast_note)
        lay.addStretch(1)
        return col

    def _sync_contrast(self) -> None:
        ok, text = kinds.contrast_report(self.c_bg.value, self.c_brand.value,
                                         self.c_soft.value)
        self.contrast_note.setObjectName("caption" if ok else "")
        self.contrast_note.setProperty("chip", None if ok else "err")
        self.contrast_note.setText(text if ok else f"{text} — 다른 색을 고르세요")
        self.contrast_note.style().unpolish(self.contrast_note)
        self.contrast_note.style().polish(self.contrast_note)

    def _update_preview(self, *_a) -> None:
        """색 버튼 값 + 이름을 카드 구도로 — 선택자 필수 (자식 오염 방지, 08 §5)."""
        brand, soft, bg = self.c_brand.value, self.c_soft.value, self.c_bg.value
        self.pv.setStyleSheet(f"#wizPreview {{ background: {bg}; border-radius: 12px; }}")
        name = self.title.text().strip() or "프로젝트 이름"
        self.pv_kicker.setText(kinds.label(self.kind()))
        self.pv_kicker.setStyleSheet(
            f"color: {soft}; font-size: 12px; letter-spacing: 2px; background: transparent;")
        self.pv_title.setText(name)
        self.pv_title.setStyleSheet(
            f"color: white; font-size: 22px; font-weight: 700; background: transparent;"
            f" border-bottom: 2px solid {brand}; padding-bottom: 6px;")
        if hasattr(self, "contrast_note"):
            self._sync_contrast()

    # ── 상태 ────────────────────────────────────────────────────────────────
    def kind(self) -> str:
        btn = self.kind_group.checkedButton()
        return btn.property("kindId") if btn else kinds.DEFAULT_KIND

    def _sync_length_note(self, *_a) -> None:
        chars = _length_to_chars(self.length.currentText())
        self.length_note.setText(f"내레이션 약 {chars:,}자 분량입니다" if chars
                                 else '"3분"처럼 분·초로 적어주세요')

    def _toggle_adv(self, on: bool) -> None:
        self.adv.setVisible(on)
        self.adv_btn.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        if on:
            # 2회차에 "펼친 크기로 처음부터" 잡아 둔 760px 이, 그 뒤 [앱 주소]·[로그인] 행이
            # 늘면서 모자라졌다 — 창이 안 늘어나니 폼이 눌려 **"대상" 칸과 "목소리" 행이
            # 21px 겹쳤다** (66회차 실측: 필요 844 vs 창 760, 고급 블록 408 자리에 324).
            # 숫자를 다시 박으면 또 썩는다 — 내용이 요구하는 높이를 그때 재서 늘린다
            need = self.sizeHint().height()
            if need > self.height():
                self.resize(self.width(), need)

    def _on_kind(self, *_a) -> None:
        """종류를 바꾸면 설명·길이·프리셋이 따라온다 (직접 고른 색은 안 건드린다)."""
        spec = kinds.get(self.kind())
        self.kind_note.setText(spec["desc"])
        if hasattr(self, "pv"):
            self._update_preview()
        plain = spec["length"].split(" (")[0]   # "15초 (약 95자)" → "15초"
        if self.length.currentText().strip() in ("", *LENGTH_CHOICES):
            self.length.setCurrentText(plain)
        self._sync_length_note()
        if not self._custom_palette:
            preset = kinds.KIND_PRESET.get(self.kind())
            btn = self._preset_buttons.get(preset)
            if btn:
                btn.setChecked(True)

    def _on_preset(self, btn, on: bool) -> None:
        if not on:
            return
        name = btn.property("presetName")
        pal = dict(kinds.PRESET_PALETTES)[name]
        self._custom_palette = False
        for cb, key in ((self.c_brand, "brand"), (self.c_soft, "brandSoft"),
                        (self.c_bg, "bg")):
            cb.blockSignals(True)   # 프리셋 반영이지 사용자 직접 선택이 아니다 (08 §7)
            cb.set_value(pal[key])
            cb.blockSignals(False)
        self._update_preview()

    def _on_custom_color(self, *_a) -> None:
        """직접 고르면 프리셋 추종을 멈추고 선택 표시를 푼다."""
        self._update_preview()
        self._custom_palette = True
        self.preset_group.setExclusive(False)
        for b in self._preset_buttons.values():
            b.setChecked(False)
        self.preset_group.setExclusive(True)

    # ── 제출 ────────────────────────────────────────────────────────────────
    def body(self) -> dict:
        return {
            "kind": self.kind(),
            "episodeLength": self._length_value(),
            "course": self.course_id.text().strip(),   # 비면 _create 가 자동 생성
            "title": self.title.text().strip(),
            "tagline": self.tagline.text().strip(),
            "audience": self.audience.toPlainText().strip(),
            "voice": dict(VOICE_PRESETS["male" if self.v_male.isChecked() else "female"][0]),
            "palette": {"brand": self.c_brand.value, "brandSoft": self.c_soft.value,
                        "bg": self.c_bg.value},
            "bgm": None,   # 기본 BGM — [설정] 탭에서 바꾼다
            "capture": self._capture(),
        }

    def _capture(self) -> dict | None:
        """앱 화면 녹화 설정 — 주소가 없으면 None(지금까지처럼 모션그래픽 전용)."""
        url = self.capture_url.text().strip()
        if not url:
            return None
        out: dict = {"baseUrl": url}
        user, pw_env = self.capture_user.text().strip(), self.capture_pw_env.text().strip()
        if user:
            out["login"] = {"user": user, **({"passwordEnv": pw_env} if pw_env else {})}
        return out

    def _length_value(self) -> str | None:
        """저장값은 "15초 (약 95자)" — 예산 게이지가 "N자" 를 파싱한다 (plan_tab)."""
        return kinds.length_value(self.length.currentText())

    def _create(self) -> None:
        """이름만 있으면 만든다. id 는 자동, 단발 종류는 영상 1편까지 함께.

        단발(홍보·광고·매뉴얼·일반)은 만들기 = 곧 영상 1편이라 빈 보드를 거치지 않고
        영상 화면으로 직행한다 (시리즈인 강의만 편 목록을 거친다).
        """
        if not self.title.text().strip():
            self.error.setText("프로젝트 이름을 넣으세요 — 나머지는 전부 나중에 바꿀 수 있습니다")
            self.error.show()
            return
        self._creating = True
        self.create_btn.setEnabled(False)
        self.create_btn.setText("만드는 중…")
        studio = self._make_studio()
        payload = self.body()
        single = not kinds.get(self.kind())["series"]
        auto_id = not payload["course"]
        base = f"{self.kind()}-{date.today():%m%d}"

        def create():
            if not auto_id:
                out = studio.create_course(payload)
            else:
                # 자동 id — 이미 있으면 a·b·c… 로 물러난다 (같은 날 여러 개)
                last_err = None
                for suffix in ("", "a", "b", "c", "d", "e", "f", "g"):
                    payload["course"] = base + suffix
                    try:
                        out = studio.create_course(payload)
                        break
                    except Conflict as err:
                        last_err = err
                else:
                    raise last_err
            if single:
                ep = studio.create_episode(out["id"], 1, title=payload["title"])
                out["episodeId"] = ep["id"]
            return out

        run_bg(create, done=self._done, fail=self._fail)

    def _sync_create_btn(self, *_a) -> None:
        if not self._creating:
            self.create_btn.setEnabled(bool(self.title.text().strip()))

    def _done(self, out: dict) -> None:
        self.created = out
        self.accept()

    def _fail(self, err) -> None:
        self._creating = False
        self.create_btn.setText("만들기")
        self._sync_create_btn()
        self.error.setText(error_text(err))
        self.error.show()
