"""설정 — 키·에이전트 제공자·데이터 폴더·자가진단 (07 ★신규 화면).

키 정본은 `~/.claude/develop-video.env` (엔진과 공용 규약) — 이 화면은 그 파일의 편집기다.
셸 환경변수나 저장소 `.env` 가 이기고 있으면 그 사실을 그대로 보여 준다 (조용한 무시 금지).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.agents import PROVIDERS

from .. import theme
from ..bridge import error_text, run_bg


class SettingsPage(QWidget):
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self._fields: dict[str, QLineEdit] = {}
        self._loaded = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PAGE_PAD, 24, theme.PAGE_PAD, 24)
        title = QLabel("설정")
        title.setObjectName("pageTitle")
        outer.addWidget(title)
        desc = QLabel("키는 이 PC 공용 파일에 저장됩니다 — 엔진과 앱이 같은 파일을 읽습니다. "
                      "키가 없어도 앱의 편집·빌드·검수·배포는 그대로 동작합니다.")
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        outer.addWidget(desc)
        outer.addWidget(scroll, 1)
        lay = QVBoxLayout(body)

        # ── 에이전트 (D15) ───────────────────────────────────────────────────
        agent_head = QLabel("AI 에이전트")
        agent_head.setObjectName("sectionTitle")
        lay.addWidget(agent_head)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(theme.GAP_STACK)
        form.setVerticalSpacing(theme.GAP_STACK)
        self.provider = QComboBox()
        # 저장값은 원시 id(claude·openai) 그대로 — 화면 표기만 사람 말 (P2)
        provider_labels = {"claude": "Claude — 기본 (Anthropic)", "openai": "OpenAI"}
        for p in PROVIDERS:
            self.provider.addItem(provider_labels.get(p, p), p)
        self.provider.setMaximumWidth(260)   # 두 항목짜리 콤보가 키 칸 폭을 흉내낼 이유가 없다
        self.provider.currentIndexChanged.connect(self._sync_provider_rows)
        form.addRow("제공자", self.provider)
        self.test_mode = QCheckBox("테스트 모드 — 제공자 불문 최저가 모델 강제")
        form.addRow("", self.test_mode)
        self.openai_model = QLineEdit()
        self.openai_model.setMaximumWidth(theme.RD_FIELD)
        self.openai_model.setPlaceholderText("계정에서 쓸 수 있는 모델 id (예: gpt-4o-mini)")
        self.openai_label = QLabel("OpenAI 모델")
        form.addRow(self.openai_label, self.openai_model)
        self.agent_state = QLabel("")
        self.agent_state.setObjectName("caption")
        self.agent_state.setWordWrap(True)
        form.addRow("현재", self.agent_state)
        lay.addLayout(form)
        self._sync_provider_rows()

        # ── 키 ───────────────────────────────────────────────────────────────
        key_head = QLabel("키")
        key_head.setObjectName("sectionTitle")
        lay.addWidget(key_head)
        self.key_form = QFormLayout()
        self.key_form.setLabelAlignment(Qt.AlignRight)
        self.key_form.setHorizontalSpacing(theme.GAP_STACK)
        self.key_form.setVerticalSpacing(theme.GAP_STACK)
        lay.addLayout(self.key_form)
        self.source_note = QLabel("")
        self.source_note.setObjectName("caption")
        self.source_note.setWordWrap(True)
        lay.addWidget(self.source_note)
        self.override_note = QLabel("")   # 저장해도 안 먹는다 — 회색으로 흘리면 안 된다
        self.override_note.setProperty("chip", "warn")
        self.override_note.setWordWrap(True)
        self.override_note.hide()
        lay.addWidget(self.override_note)

        save_row = QHBoxLayout()
        self.save_btn = QPushButton("키 저장")   # 무엇을 저장하는지 버튼이 말한다 (10 #1)
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        save_row.addWidget(self.save_btn)
        save_row.addWidget(self.result)
        save_row.addStretch(1)
        lay.addLayout(save_row)

        # ── 자가진단 ─────────────────────────────────────────────────────────
        diag_head = QLabel("환경 점검")
        diag_head.setObjectName("sectionTitle")
        lay.addWidget(diag_head)
        diag_desc = QLabel("영상을 만들 준비가 됐는지 확인합니다 — 빠진 것이 있으면 "
                           "무엇을 하면 되는지 함께 보여줍니다.")
        diag_desc.setObjectName("caption")
        diag_desc.setWordWrap(True)
        lay.addWidget(diag_desc)
        diag_row = QHBoxLayout()
        self.diag_btn = QPushButton("다시 점검")
        self.diag_btn.clicked.connect(self._diagnose)
        self.tts_btn = QPushButton("목소리 합성 테스트 (한 문장을 실제로 만들어 봅니다)")
        self.tts_btn.clicked.connect(self._check_tts)
        self.tts_result = QLabel("")
        self.tts_result.setObjectName("caption")
        diag_row.addWidget(self.diag_btn)
        diag_row.addWidget(self.tts_btn)
        diag_row.addWidget(self.tts_result)
        diag_row.addStretch(1)
        lay.addLayout(diag_row)
        self.diag_table = QTableWidget(0, 3)
        self.diag_table.setHorizontalHeaderLabels(["항목", "상태", "내용 · 조치"])
        self.diag_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diag_table.setColumnWidth(0, 140)
        self.diag_table.setColumnWidth(1, 70)
        self.diag_table.horizontalHeader().setStretchLastSection(True)
        self.diag_table.verticalHeader().hide()
        self.diag_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self.diag_table)
        lay.addStretch(1)

        # 사용자 편집 감지 — 재클릭 refresh·내비 이탈이 편집을 덮지 않게 (45회차 P20.
        # 키 필드는 _fill 에서 생성되며 그때 연결된다)
        self.provider.currentIndexChanged.connect(self._mark_dirty)
        self.test_mode.toggled.connect(self._mark_dirty)
        self.openai_model.textEdited.connect(self._mark_dirty)

    def _sync_provider_rows(self) -> None:
        """제공자가 openai 일 때만 OpenAI 모델 칸을 보여준다 (09 G3)."""
        on = self.provider.currentData() == "openai"
        self.openai_label.setVisible(on)
        self.openai_model.setVisible(on)

    # ── 로드 ────────────────────────────────────────────────────────────────
    def _mark_dirty(self, *_a) -> None:
        if not getattr(self, "_loading", False):
            self._dirty = True

    def has_unsaved(self) -> bool:
        return bool(getattr(self, "_dirty", False))

    def refresh(self) -> None:
        studio = self._make_studio()
        # 키를 입력하는 중이면 값은 안 덮는다 — 내비 재클릭이 refresh 를 부른다
        # (45회차 P20. 진단은 값과 무관하니 항상 다시 돈다)
        if not self.has_unsaved():
            run_bg(lambda: (studio.settings(), studio.agent_status()), done=self._fill,
                   fail=lambda e: self.result.setText(error_text(e)))
        self._diagnose()

    def _fill(self, result) -> None:
        self._loading = True
        cfg, agent = result
        values, sources = cfg["values"], cfg["sources"]
        if not self._fields:  # 폼은 한 번만 짓는다
            for name, label in cfg["keys"]:
                field = QLineEdit()
                field.setMaximumWidth(theme.RD_FIELD)
                if name in cfg["secretKeys"]:
                    field.setEchoMode(QLineEdit.Password)
                field.setToolTip(label)
                self._fields[name] = field
                field.textEdited.connect(self._mark_dirty)
                self.key_form.addRow(label.split(" — ")[0], field)
        for name, field in self._fields.items():
            field.setText(values.get(name, ""))
        idx = self.provider.findData(agent.get("provider", "claude"))
        self.provider.setCurrentIndex(max(0, idx))
        self.test_mode.setChecked(bool(agent.get("testMode")))
        self.openai_model.setText(values.get("OPENAI_MODEL", ""))

        models = agent.get("models", {})
        used = {models.get(k) for k in ("draft", "diagram", "review")} - {None}
        # 세 자리가 같은 모델이면 한 번만 말한다 — 같은 문자열 3연속은 안 읽힌다 (09 G3)
        model_text = (f"모델 {used.pop()}" if len(used) == 1 else
                      " · ".join(f"{k}={models.get(k)}"
                                 for k in ("draft", "diagram", "review")))
        self.agent_state.setText(
            ("사용 가능 ✓" if agent.get("enabled") else "비활성 — " + agent.get("reason", ""))
            + f" · {model_text}"
            + ("  (테스트 모드 — 최저가 강제)" if agent.get("testMode") else ""))
        overrides = [n for n in self._fields
                     if sources.get(n) and sources[n] != "~/.claude/develop-video.env"]
        self.source_note.setText(f"저장 위치: {cfg['homeFile']}")
        self.override_note.setVisible(bool(overrides))
        if overrides:
            self.override_note.setText(
                f"다음 값은 {', '.join(sorted({sources[n] for n in overrides}))} 에 설정돼 "
                f"있어 그 값이 우선 적용됩니다 — 여기서 바꾸려면 그 파일에서 지우세요: "
                f"{', '.join(overrides)}")
        self._loading = False
        self._dirty = False
        self._loaded = True

    # ── 저장 ────────────────────────────────────────────────────────────────
    def _save(self) -> None:
        if not self._loaded:
            return
        updates = {name: f.text().strip() for name, f in self._fields.items()}
        updates["AGENT_PROVIDER"] = self.provider.currentData()
        updates["AGENT_TEST_MODE"] = "1" if self.test_mode.isChecked() else ""
        updates["OPENAI_MODEL"] = self.openai_model.text().strip()
        studio = self._make_studio()
        # 처리 중 잠금 + 즉시 피드백 (29회차 P18 — 저장/반영 버튼 공통 문법)
        self.save_btn.setEnabled(False)
        self.result.setText("저장 중…")
        run_bg(lambda: studio.save_settings(updates),
               done=lambda out: (self.result.setText(f"저장됨 ✓ — {out['file']}"),
                                 self.save_btn.setEnabled(True),
                                 self.refresh()),
               fail=lambda e: (self.result.setText(error_text(e)),
                               self.save_btn.setEnabled(True)))

    # ── 진단 ────────────────────────────────────────────────────────────────
    def _diagnose(self) -> None:
        studio = self._make_studio()
        self.diag_btn.setEnabled(False)
        run_bg(studio.diagnose, done=self._fill_diag,
               fail=lambda e: (self.result.setText(error_text(e)),
                               self.diag_btn.setEnabled(True)))

    def _fill_diag(self, checks: list[dict]) -> None:
        """점검 결과를 **한 줄씩** 채운다 — OK 가 차례로 찍히는 것이 보여야
        "점검했다"가 전달된다 (10 #3b: "체크를 하는 동작을 보여주면 좋겠다")."""
        self.diag_btn.setEnabled(True)
        self.diag_table.setRowCount(0)
        self._diag_queue = list(checks)
        self._diag_timer = QTimer(self)
        self._diag_timer.setInterval(140)
        self._diag_timer.timeout.connect(self._diag_tick)
        self._diag_timer.start()

    def _diag_tick(self) -> None:
        if not self._diag_queue:
            self._diag_timer.stop()
            return
        c = self._diag_queue.pop(0)
        i = self.diag_table.rowCount()
        self.diag_table.insertRow(i)
        self.diag_table.setItem(i, 0, QTableWidgetItem(c["name"]))
        state = QTableWidgetItem("정상" if c["ok"] else "없음")
        state.setForeground(Qt.darkGreen if c["ok"] else Qt.red)
        self.diag_table.setItem(i, 1, state)
        detail = c["detail"] + ("" if c["ok"] or not c["hint"] else f"  → {c['hint']}")
        self.diag_table.setItem(i, 2, QTableWidgetItem(detail))
        # 표가 제 내용만큼 자란다 — 스크롤 안의 스크롤은 못 쓴다 (09 G3)
        self.diag_table.setFixedHeight(
            self.diag_table.horizontalHeader().height()
            + sum(self.diag_table.rowHeight(r) for r in range(i + 1)) + 4)

    def _check_tts(self) -> None:
        studio = self._make_studio()
        self.tts_btn.setEnabled(False)
        self.tts_result.setText("합성 중…")
        run_bg(studio.check_tts,
               done=lambda r: (self.tts_result.setText(
                   ("연결 OK — " if r["ok"] else "실패 — ") + r["detail"]),
                   self.tts_btn.setEnabled(True)),
               fail=lambda e: (self.tts_result.setText(error_text(e)),
                               self.tts_btn.setEnabled(True)))
