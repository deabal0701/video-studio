"""⑦ 배포 산출물 — youtube.md 를 수동 작성에서 자동 생성으로 (03 ⑦).

제목 `[프로젝트 이름] n강 — 제목` · 설명(promise+챕터+재생목록 자리) · 챕터(chapters.js 실측) ·
srt · 썸네일 후보(검수 프레임). 전 항목 편집 가능 + 복사 버튼.
챕터 생성이 실패하면 사유를 드러낸다 — 조용히 비면 반쪽 배포물이 나간다 (07 결함 4).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QScrollArea, QToolButton,
                               QVBoxLayout, QWidget)

from core.status import OUT_ROOT

from .. import theme
from ..bridge import error_text, run_bg


class DeployTab(QWidget):
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.eid: str | None = None
        self._data: dict = {}
        self._loading = False   # _fill 의 setText 를 사용자 편집으로 오인하지 않게
        self._dirty = False     # 고친 문안이 있으면 탭 재진입이 덮지 않는다 (26회차 P0)

        lay = QVBoxLayout(self)
        desc = QLabel("유튜브에 올릴 문안입니다. 여기서 고친 뒤 복사하거나 파일로 저장하세요 — "
                      "챕터 시각은 완성본에서 실측합니다(빌드 전에는 추정값).")
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        lay.addWidget(desc)
        # 완성본이 없어도 이 화면은 문안·챕터를 다 내놓아 **다 된 것처럼 보였다**.
        # 그 챕터 시각은 음성 캐시가 없어 대본의 선언 duration 으로만 계산된 값이고
        # (engine/chapters.js 는 그 경우 stderr 로 경고하는데 화면은 그걸 버린다),
        # 제목도 "[챕터 제목]" 자리표시자 그대로다 — 그대로 유튜브에 올리면 틀린 시각이
        # 나간다. ③ 검수는 "아직 완성본이 없습니다"라고 말하는데 여기만 빠져 있었다
        # (58회차 P9·P18·P11)
        self.not_built = QLabel(
            "아직 완성본이 없습니다 — 아래 챕터 시각은 실측이 아니라 대본의 선언 길이로 "
            "계산한 추정값입니다. 위 [빌드] 뒤에 다시 확인하세요.")
        self.not_built.setProperty("chip", "warn")
        self.not_built.setWordWrap(True)
        self.not_built.hide()
        lay.addWidget(self.not_built)
        title_row = QHBoxLayout()
        self.title = QLineEdit()
        self.title.textEdited.connect(self._mark_dirty)   # textEdited = 사용자 입력만
        # 제목이 비면 저장을 막는다 — 15·27·32·34·52회차와 같은 비활성 primary 문법
        self.title.textEdited.connect(self._sync_save_btn)
        copy_title = QPushButton("복사")
        copy_title.clicked.connect(lambda: self._copy(self.title.text(), "제목"))
        title_row.addWidget(QLabel("제목"))
        title_row.addWidget(self.title, 1)
        title_row.addWidget(copy_title)
        lay.addLayout(title_row)

        lay.addWidget(QLabel("설명"))
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(180)
        self.description.textChanged.connect(
            lambda: None if self._loading else self._mark_dirty())
        lay.addWidget(self.description, 1)

        btn_row = QHBoxLayout()
        copy_desc = QPushButton("설명 복사")
        copy_desc.clicked.connect(
            lambda: self._copy(self.description.toPlainText(), "설명"))
        self.save_btn = QPushButton("유튜브 문안 저장")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.srt_btn = QPushButton("자막 파일 저장…")
        self.srt_btn.clicked.connect(self._save_srt)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        for w in (copy_desc, self.save_btn, self.srt_btn, self.result):
            btn_row.addWidget(w)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.chapters_note = QLabel("")
        self.chapters_note.setProperty("chip", "err")
        self.chapters_note.setWordWrap(True)
        self.chapters_note.hide()
        lay.addWidget(self.chapters_note)

        thumb_head = QLabel("썸네일 후보")
        thumb_head.setObjectName("sectionTitle")
        lay.addWidget(thumb_head)
        thumb_desc = QLabel("검수 프레임에서 고릅니다 — 쓸 그림을 눌러 파일로 저장하세요.")
        thumb_desc.setObjectName("caption")
        lay.addWidget(thumb_desc)
        self.thumb_empty = QLabel("후보가 없습니다 — 빌드하면 검수 프레임에서 만들어집니다")
        self.thumb_empty.setObjectName("caption")
        self.thumb_empty.hide()
        lay.addWidget(self.thumb_empty)
        self.thumbs_row = QHBoxLayout()
        holder = QWidget()
        holder.setLayout(self.thumbs_row)
        self.thumbs_scroll = QScrollArea()
        self.thumbs_scroll.setWidgetResizable(True)
        self.thumbs_scroll.setWidget(holder)
        # 후보 전부가 한눈에 — 좁은 창이면 로드 때 축소한다 (③ 검수와 같은 처방, P6).
        # 세로 바는 생기면 가로 바까지 연쇄라 끈다
        self.thumbs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbs_scroll.setFixedHeight(theme.THUMB_H + 52)
        lay.addWidget(self.thumbs_scroll)

    def _sync_save_btn(self, *_a) -> None:
        if getattr(self, "_busy", False):
            return   # 저장 중 잠금이 이긴다
        ok = bool(self.title.text().strip())
        self.save_btn.setEnabled(ok)
        self.save_btn.setToolTip("" if ok else "제목을 넣으세요 — 빈 제목으로는 저장할 수 없습니다")

    def _mark_dirty(self, *_a) -> None:
        self._dirty = True

    def has_unsaved(self) -> bool:
        return bool(self._dirty)

    def load(self, eid: str) -> None:
        if eid == self.eid and self._dirty:
            return   # 문안을 고치는 중 — 탭 재진입이 편집을 덮으면 안 된다 (P0)
        self.eid = eid
        studio = self._make_studio()
        run_bg(lambda: studio.deliverables(eid), done=self._fill,
               fail=lambda e: self.result.setText(error_text(e)))

    def _fill(self, data: dict) -> None:
        self._data = data
        self._loading = True
        self.title.setText(data.get("title", ""))
        self.description.setPlainText(data.get("description", ""))
        self._loading = False
        self._dirty = False
        self.result.setText("저장해 둔 문안입니다 — 고치면 다시 저장하세요"
                            if data.get("saved") else "")
        # 빌드 산출물(자막·검수 프레임)이 하나라도 있으면 완성본이 있는 것이다
        built = bool(data.get("srt") or data.get("thumbnails"))
        self.not_built.setVisible(not built)
        # 누른 뒤에 "srt 없음"이라고 설명하지 말고 애초에 못 누르게 (27회차와 같은 문법)
        self.srt_btn.setEnabled(bool(data.get("srt")))
        self.srt_btn.setToolTip("" if data.get("srt")
                                else "완성본이 없습니다 — 위 [빌드] 를 먼저 누르세요")
        self._sync_save_btn()
        err = data.get("chaptersError")
        self.chapters_note.setText(
            f"챕터 생성 실패 — {err}" if err
            else "챕터 없음 — 빌드 산출물(audio manifest)이 있어야 실측됩니다"
            if not data.get("chapters") else "")
        self.chapters_note.setVisible(bool(err) or not data.get("chapters"))
        while self.thumbs_row.count():
            item = self.thumbs_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        names = data.get("thumbnails", [])
        self.thumb_empty.setVisible(not names)
        n = max(1, len(names))
        avail = max(300, self.thumbs_scroll.viewport().width() - 24)
        thumb_h = min(theme.THUMB_H, max(80, (avail // n - 16) * 9 // 16))
        self.thumbs_scroll.setFixedHeight(thumb_h + 52)
        for name in names:
            p = OUT_ROOT / self.eid / "frames" / name
            btn = QToolButton()
            btn.setIcon(QIcon(QPixmap(str(p))))
            btn.setIconSize(QPixmap(str(p)).scaledToHeight(
                thumb_h, Qt.SmoothTransformation).size())
            btn.setAutoRaise(True)
            btn.setToolTip(f"{name} — 눌러서 저장")
            btn.clicked.connect(lambda _=False, path=p: self._save_thumb(path))
            self.thumbs_row.addWidget(btn)
        self.thumbs_row.addStretch(1)

    def _save_thumb(self, src) -> None:
        dest, _ = QFileDialog.getSaveFileName(self, "썸네일 저장", src.name, "PNG (*.png)")
        if dest:
            Path(dest).write_bytes(src.read_bytes())
            self.result.setText(f"{Path(dest).name} 저장됨")

    def _copy(self, text: str, label: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.result.setText(f"{label} 복사됨")

    def _save(self) -> None:
        # 버튼 비활성만으로는 버튼 밖 경로를 못 막는다 (52·56회차와 같은 처방)
        if getattr(self, "_busy", False):
            return
        if not self.title.text().strip():
            self.result.setText("제목을 넣으세요")
            return
        self._busy = True
        eid, studio = self.eid, self._make_studio()
        title, desc = self.title.text(), self.description.toPlainText()
        # 처리 중 잠금 (P18) + 성공하면 편집 플래그 해제 — 이후 재진입은 새로 읽는다
        self.save_btn.setEnabled(False)
        self.result.setText("저장 중…")
        run_bg(lambda: studio.save_deliverables(eid, title=title, description=desc),
               done=lambda out: (setattr(self, "_busy", False),
                                 self.result.setText(f"{out['file']} 저장됨 ✓"),
                                 setattr(self, "_dirty", False),
                                 self._sync_save_btn()),
               fail=lambda e: (setattr(self, "_busy", False),
                               self.result.setText(error_text(e)),
                               self._sync_save_btn()))

    def _save_srt(self) -> None:
        names = self._data.get("srt") or []
        if not names:
            self.result.setText("srt 없음 — 먼저 빌드하세요")
            return
        src = OUT_ROOT / self.eid / "final" / names[0]
        dest, _ = QFileDialog.getSaveFileName(self, "자막 저장", names[0], "SubRip (*.srt)")
        if dest:
            Path(dest).write_bytes(src.read_bytes())
            self.result.setText(f"{Path(dest).name} 저장됨")
