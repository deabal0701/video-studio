"""첫 실행 위저드 — 설치본 전용 (07 "1 데이터 폴더 → 2 자가진단 → 3 키 → 4 소재").

모든 단계는 건너뛸 수 있다 — **키가 없어도 앱은 완결 동작**한다(원칙 2). 위저드의 목적은
"설치 직후 첫 빌드 성공"까지 데려가는 것이고, 못 채운 항목은 설정 화면에서 이어서 한다.

완료 표시는 데이터 폴더의 `.first-run-done` — 지우면 다시 뜬다(진단용).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWizard, QWizardPage)

from core import env

from .. import theme
from ..bridge import error_text, run_bg

DONE_MARK = ".first-run-done"


def needs_first_run() -> bool:
    return env.FROZEN and not (env.DATA_DIR / DONE_MARK).exists()


def mark_done() -> None:
    env.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (env.DATA_DIR / DONE_MARK).write_text("ok\n", encoding="utf-8", newline="\n")


class _DataFolderPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("1. 데이터 폴더")
        self.setSubTitle("네 단계면 첫 영상까지 갑니다. 어느 단계든 건너뛸 수 있고, "
                         "나중에 설정 화면에서 이어서 할 수 있습니다.")
        lay = QVBoxLayout(self)
        lead = QLabel("프로젝트·영상 파일과 빌드 산출물이 저장될 곳입니다. "
                      "이 폴더가 정본이니 백업 대상으로 잡으세요.")
        lead.setWordWrap(True)
        lay.addWidget(lead)
        row = QHBoxLayout()
        self.path = QLineEdit(str(env.DATA_DIR))
        self.path.setReadOnly(True)
        browse = QPushButton("변경…")
        browse.clicked.connect(self._pick)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        lay.addLayout(row)
        note = QLabel("기본값은 사용자별 로컬 폴더입니다 — 관리자 권한 없이 쓸 수 있고 "
                      "다른 사용자와 섞이지 않습니다.\n"
                      "바꾸면 다음 실행부터 적용됩니다.")
        note.setObjectName("caption")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)

    def _pick(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "데이터 폴더 선택", self.path.text())
        if d:
            self.path.setText(d)


class _DiagnosePage(QWizardPage):
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.setTitle("2. 자가진단")
        self.setSubTitle("렌더에 필요한 부품을 점검합니다. 빠진 것이 있으면 무엇을 하면 "
                         "되는지 함께 보여 줍니다.")
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["항목", "상태", "내용 · 조치"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 70)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.again = QPushButton("다시 점검")
        self.again.clicked.connect(self.refresh)
        self.summary = QLabel("")
        self.summary.setObjectName("caption")
        row.addWidget(self.again)
        row.addWidget(self.summary)
        row.addStretch(1)
        lay.addLayout(row)

    def initializePage(self) -> None:  # noqa: N802 — Qt 오버라이드
        self.refresh()

    def refresh(self) -> None:
        studio = self._make_studio()
        self.again.setEnabled(False)
        run_bg(studio.diagnose, done=self._fill,
               fail=lambda e: (self.summary.setText(error_text(e)),
                               self.again.setEnabled(True)))

    def _fill(self, checks: list[dict]) -> None:
        """한 줄씩 차례로 찍는다 — 설정 화면과 같은 문법 (10 #3b: 점검하는 동작이 보여야
        "점검했다"가 전달된다)."""
        self.again.setEnabled(True)
        self.table.setRowCount(0)
        self._queue = list(checks)
        self._bad: list[str] = []
        self._timer = QTimer(self)
        self._timer.setInterval(140)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        if not self._queue:
            self._timer.stop()
            self.summary.setText(
                "전부 준비됨 ✓" if not self._bad
                else f"빠진 것: {', '.join(self._bad)} — 없어도 계속 진행할 수 있습니다")
            return
        c = self._queue.pop(0)
        i = self.table.rowCount()
        self.table.insertRow(i)
        self.table.setItem(i, 0, QTableWidgetItem(c["name"]))
        state = QTableWidgetItem("정상" if c["ok"] else "없음")
        state.setForeground(Qt.darkGreen if c["ok"] else Qt.red)
        self.table.setItem(i, 1, state)
        self.table.setItem(i, 2, QTableWidgetItem(
            c["detail"] + ("" if c["ok"] or not c["hint"] else f"  → {c['hint']}")))
        if not c["ok"] and "키" not in c["name"]:
            self._bad.append(c["name"])


class _KeysPage(QWizardPage):
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self._fields: dict[str, QLineEdit] = {}
        self.setTitle("3. 키 설정 (선택)")
        self.setSubTitle("전부 비워도 됩니다 — 기본 TTS(edge)는 키가 필요 없고, "
                         "AI 기능만 꺼진 채 나머지는 그대로 동작합니다.")
        lay = QVBoxLayout(self)
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.setVerticalSpacing(theme.GAP_STACK)
        lay.addLayout(self.form)
        self.note = QLabel("")
        self.note.setObjectName("caption")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        lay.addStretch(1)

    def initializePage(self) -> None:  # noqa: N802
        if self._fields:
            return
        studio = self._make_studio()
        run_bg(studio.settings, done=self._build, fail=lambda e: self.note.setText(error_text(e)))

    def _build(self, cfg: dict) -> None:
        for name, label in cfg["keys"]:
            field = QLineEdit(cfg["values"].get(name, ""))
            field.setMaximumWidth(theme.RD_FIELD)
            if name in cfg["secretKeys"]:
                field.setEchoMode(QLineEdit.Password)
            field.setToolTip(label)
            self._fields[name] = field
            self.form.addRow(label.split(" — ")[0], field)
        self.note.setText(f"저장 위치: {cfg['homeFile']} — 나중에 설정 화면에서 바꿀 수 있습니다.")

    def save(self) -> None:
        """동기 저장 — 위저드가 닫히는 시점이라 백그라운드로 보내면 앱 종료와
        경주가 되고, 실패를 삼키면 입력한 키가 조용히 사라진다 (30회차 P21).
        파일 한 줄 쓰기라 즉시 끝난다."""
        if not self._fields:
            return
        updates = {k: f.text().strip() for k, f in self._fields.items()}
        try:
            self._make_studio().save_settings(updates)
        except Exception as err:  # noqa: BLE001 — 어떤 실패든 사용자에게 알린다
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "키 저장 실패",
                f"{error_text(err)}\n\n[설정] 화면에서 다시 저장할 수 있습니다.")


class _AssetsPage(QWizardPage):
    """4. 준비물 — 스톡 소재는 재배포 금지라 설치본에 없다 (R3). 목소리 샘플도 여기서 만든다.

    목소리 미리듣기는 **한 번 만들어 두면 이후 공짜·즉시**다(core/voices.py). 첫 실행에서
    무료 3종을 미리 만들어 두면 담당자가 프로젝트를 개설할 때 바로 골라 들을 수 있다.
    """

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.setTitle("4. 준비물 (선택)")
        self.setSubTitle("무료 스톡 소재는 재배포가 금지돼 설치본에 넣지 않습니다 — "
                         "원 출처에서 직접 받습니다.")
        lay = QVBoxLayout(self)
        self.have = QLabel("확인 중…")
        lay.addWidget(self.have)
        self.skip = QCheckBox("나중에 받기 — 라이브러리 화면에서 언제든 받을 수 있습니다")
        self.skip.setChecked(True)
        lay.addWidget(self.skip)
        note = QLabel("받은 소재의 출처와 라이선스는 자동으로 함께 기록됩니다 — "
                      "라이선스를 모르는 소재는 받지 않습니다.")
        note.setObjectName("caption")
        note.setWordWrap(True)
        lay.addWidget(note)

        # ── 목소리 미리듣기 (무료 3종) ───────────────────────────────────────
        voice_head = QLabel("목소리 미리듣기")
        voice_head.setObjectName("sectionTitle")
        lay.addWidget(voice_head)
        voice_note = QLabel("무료 목소리 3종을 미리 만들어 두면, 프로젝트를 만들 때 바로 골라 "
                            "들어볼 수 있습니다 (10초쯤 걸리고 비용은 없습니다).")
        voice_note.setObjectName("caption")
        voice_note.setWordWrap(True)
        lay.addWidget(voice_note)
        voice_row = QHBoxLayout()
        self.voice_btn = QPushButton("무료 목소리 3종 만들기")
        self.voice_btn.clicked.connect(self._make_voices)
        self.voice_state = QLabel("")
        self.voice_state.setObjectName("caption")
        voice_row.addWidget(self.voice_btn)
        voice_row.addWidget(self.voice_state, 1)
        lay.addLayout(voice_row)
        lay.addStretch(1)

    def _make_voices(self) -> None:
        studio = self._make_studio()
        self.voice_btn.setEnabled(False)
        self.voice_state.setText("만드는 중…")
        run_bg(lambda: studio.voice_samples_build("edge"),
               done=lambda r: (self.voice_state.setText(
                   f"준비됨 — 새로 {r['made']}종"
                   + (f" · 실패 {len(r['failed'])}종 (설정 화면에서 다시 할 수 있습니다)"
                      if r["failed"] else "")),
                   self.voice_btn.setEnabled(True)),
               fail=lambda e: (self.voice_state.setText(error_text(e)),
                               self.voice_btn.setEnabled(True)))

    def initializePage(self) -> None:  # noqa: N802
        studio = self._make_studio()

        def count():
            return len(studio.assets("bgm")), len(studio.assets("broll"))

        run_bg(count,
               done=lambda c: self.have.setText(f"현재 보유: BGM {c[0]}개 · B롤 {c[1]}개"),
               fail=lambda e: self.have.setText(error_text(e)))
        # 이미 만들어 둔 목소리가 있으면 버튼을 다시 누르게 하지 않는다
        run_bg(lambda: self._make_studio().voice_catalog("edge"),
               done=lambda info: self.voice_state.setText(
                   f"준비됨 {sum(1 for v in info['voices'] if v.get('cached'))}"
                   f" / {len(info['voices'])}종"),
               fail=lambda _e: None)


class FirstRunWizard(QWizard):
    def __init__(self, make_studio, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Studio 시작하기")
        self.resize(820, 620)
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.data_page = _DataFolderPage()
        self.keys_page = _KeysPage(make_studio)
        for p in (self.data_page, _DiagnosePage(make_studio), self.keys_page,
                  _AssetsPage(make_studio)):
            self.addPage(p)
        self.setButtonText(QWizard.FinishButton, "시작하기")
        self.setButtonText(QWizard.NextButton, "다음")
        self.setButtonText(QWizard.BackButton, "이전")
        self.setButtonText(QWizard.CancelButton, "건너뛰기")
        self.finished.connect(self._done)

    def _done(self, result: int) -> None:
        if result:  # 완료 — 건너뛰기(Cancel)면 표시하지 않아 다음 실행에 다시 뜬다
            self.keys_page.save()
            self._save_data_dir()
            mark_done()

    def _save_data_dir(self) -> None:
        """[변경…]으로 고른 폴더를 포인터(.data-dir)에 적는다 — 다음 실행부터 적용.

        안 적으면 화면의 "바꾸면 다음 실행부터 적용됩니다"가 말뿐이 된다 (P1).
        새 폴더에도 완료 표시를 함께 둬 위저드가 다시 뜨지 않는다.
        """
        from pathlib import Path

        chosen = Path(self.data_page.path.text().strip())
        if not str(chosen) or chosen == env.DATA_DIR:
            return
        base = env._default_data_dir()
        try:
            base.mkdir(parents=True, exist_ok=True)
            (base / ".data-dir").write_text(str(chosen), encoding="utf-8", newline="\n")
            chosen.mkdir(parents=True, exist_ok=True)
            (chosen / DONE_MARK).write_text("ok\n", encoding="utf-8", newline="\n")
        except OSError:
            pass   # 폴더를 못 쓰면 기본값 그대로 — 다음 실행에 위저드가 다시 안내한다
