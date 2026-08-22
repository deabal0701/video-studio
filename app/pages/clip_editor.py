"""⑤ 대본 에디터 — 3열 (03 ⑤ · 구 web ClipEditor.vue 의 Qt 이식, 5-5).

결함 차단 4종 (이 앱의 1원칙):
  ① 오타 params → 템플릿이 받는 키만 폼 생성 (자유 키 입력 없음, 안 받는 키는 빨간 목록+[제거])
  ② 상대경로 오류 → 피커로만 선택, 저장 시 경로 실존 검사(pathIssues)
  ③ 브랜드 색·폰트 누락 → 자동 주입 키는 "프로젝트 상속 중" 뱃지만 (폼 비노출)
  ④ B롤 길이 초과 → duration > 소스−videoStart 즉시 빨강

저장 응답의 etag 를 항상 채택한다 — 경로 문제가 있어도 다음 저장이 409 로 교착하지 않게
(구 웹 구현의 실결함 수정 — 2026-08-21 코드리뷰 3번).
"""

from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea, QSplitter,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core import env, kinds, paths
from core.status import OUT_ROOT
# 강의 페이스(자/초)의 정본은 core.validate — 화면이 사본을 두면 갈라진다 (02 길이 계산)
from core.validate import CHARS_PER_SEC_LECTURE as PACE

from .. import theme
from ..bridge import error_text, run_bg
from ..widgets import AudioPreview

SKELETON = ["broll", "title", "hook", "stinger", "promise"]
# 프로젝트가 자동 주입하는 키 — 폼 비노출, "상속 중" 뱃지만 (03 ⑤ 표 · 결함 차단 ③)
AUTO_KEYS = ("brand", "brandSoft", "bg", "fg", "font", "fontUrl",
             "wipeAt", "wipeColor")
TIME_KEY_RE = re.compile(r"^t\d|^tterm|At$|Time$", re.I)


def clip_seconds(clip: dict, audio_cache: dict) -> tuple[float, bool]:
    """(길이 s, 실측 여부) — TTS 캐시 있으면 실측, 없으면 추정 (03 ⑤ 리스트 라벨)."""
    measured = audio_cache.get(clip.get("id"))
    if measured:
        return max(clip.get("duration") or 0, measured + 0.5), True
    if clip.get("narration"):
        return max(clip.get("duration") or 0,
                   len(clip["narration"]) / PACE + 0.5), False
    return clip.get("duration") or 0, True


class PickerDialog(QDialog):
    """피커 공용 — 행 클릭으로 선택 (경로 문자열을 만지지 않는다, 결함 차단 ②)."""

    def __init__(self, title: str, headers: list[str], rows: list[list[str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 440)
        self.picked: int | None = None
        lay = QVBoxLayout(self)
        self.table = QTableWidget(len(rows), len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(cell))
        self.table.resizeColumnsToContents()
        self.table.cellDoubleClicked.connect(self._pick)
        lay.addWidget(self.table)
        hint = QLabel("더블클릭으로 선택")
        hint.setObjectName("caption")
        lay.addWidget(hint)

    def _pick(self, row: int, _col: int) -> None:
        self.picked = row
        self.accept()


class _PreviewColumn(QWidget):
    """프리뷰를 16:9 로 잡아 두는 열.

    엔진 문서는 1920×1080 이라 위젯을 세로로 늘리면 문서 아래에 흰 띠가 남는다.
    폭이 정해질 때마다 높이를 다시 계산한다 (같은 값이면 건드리지 않는다 — 재귀 방지).
    """

    preview = None

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        if self.preview is None:
            return
        want = round(self.preview.width() * 9 / 16)
        if self.preview.height() != want:
            self.preview.setFixedHeight(want)


class ClipEditorTab(QWidget):
    saved = Signal()          # 부모가 파생 상태 재조회
    tts_requested = Signal()  # [TTS 실측 갱신] — 부모의 잡 동선 재사용

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.eid: str | None = None
        self.doc: dict = {}
        self._etag: str | None = None
        self._inspect: dict = {}
        self._gallery: list[dict] = []
        self._brolls: list[dict] = []
        self._budget = 1850
        self._selected = -1
        self._loading = False
        self.audio = AudioPreview()

        split = QSplitter(Qt.Horizontal, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.addWidget(split)
        split.addWidget(self._make_left())
        split.addWidget(self._make_center())
        split.addWidget(self._make_right())
        split.setSizes([260, 520, 420])

    # ══ 좌: 클립 리스트 + 예산 ═══════════════════════════════════════════════
    def _make_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.skeleton_warn = QLabel("")
        self.skeleton_warn.setProperty("chip", "err")
        self.skeleton_warn.setWordWrap(True)
        self.skeleton_warn.hide()
        lay.addWidget(self.skeleton_warn)

        self.clip_list = QListWidget()
        self.clip_list.setDragDropMode(QAbstractItemView.InternalMove)  # 드래그 정렬 = 배열 순서
        self.clip_list.currentRowChanged.connect(self._on_select)
        self.clip_list.model().rowsMoved.connect(self._on_reorder)
        lay.addWidget(self.clip_list, 1)

        add_row = QHBoxLayout()
        for label, kind in (("+챕터", "chapter"), ("+도식", "diagram"), ("+B롤", "broll")):
            b = QPushButton(label)
            b.clicked.connect(lambda _c=False, k=kind: self._add_clip(k))
            add_row.addWidget(b)
        self.del_btn = QPushButton("삭제")
        self.del_btn.setObjectName("danger")
        self.del_btn.clicked.connect(self._remove_clip)
        add_row.addWidget(self.del_btn)
        lay.addLayout(add_row)

        self.budget_label = QLabel("")
        lay.addWidget(self.budget_label)
        self.budget_bar = QProgressBar()
        self.budget_bar.setTextVisible(False)
        self.budget_bar.setFixedHeight(6)
        lay.addWidget(self.budget_bar)
        self.budget_note = QLabel("")
        self.budget_note.setObjectName("caption")
        self.budget_note.setWordWrap(True)
        lay.addWidget(self.budget_note)

        self.save_btn = QPushButton("저장")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        lay.addWidget(self.save_btn)
        self.issues = QLabel("")
        self.issues.setProperty("chip", "err")
        self.issues.setWordWrap(True)
        self.issues.hide()
        lay.addWidget(self.issues)
        return w

    # ══ 중: 클립 편집 (결함 차단 4종) ════════════════════════════════════════
    def _make_center(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        lay = QVBoxLayout(w)
        self.cur_id = QLabel("")
        self.cur_id.setObjectName("sectionTitle")
        lay.addWidget(self.cur_id)

        pick_row = QHBoxLayout()
        self.screen_label = QLabel("—")
        self.screen_label.setObjectName("caption")
        self.tpl_btn = QPushButton("템플릿 선택…")
        self.tpl_btn.clicked.connect(self._pick_template)
        self.broll_btn = QPushButton("B롤 선택…")
        self.broll_btn.clicked.connect(self._pick_broll)
        pick_row.addWidget(QLabel("화면"))
        pick_row.addWidget(self.screen_label, 1)
        pick_row.addWidget(self.tpl_btn)
        pick_row.addWidget(self.broll_btn)
        lay.addLayout(pick_row)

        # B롤 전용 행 (videoStart·shade + 길이 즉시 검사 — 결함 ④)
        self.broll_row = QWidget()
        br = QHBoxLayout(self.broll_row)
        br.setContentsMargins(0, 0, 0, 0)
        self.video_start = QLineEdit()
        self.video_start.setFixedWidth(70)
        self.video_start.textEdited.connect(self._on_field_edit)
        self.shade = QLineEdit()
        self.shade.setFixedWidth(70)
        self.shade.textEdited.connect(self._on_field_edit)
        br.addWidget(QLabel("videoStart"))
        br.addWidget(self.video_start)
        br.addWidget(QLabel("shade"))
        br.addWidget(self.shade)
        br.addStretch(1)
        lay.addWidget(self.broll_row)
        self.broll_check = QLabel("")
        self.broll_check.setWordWrap(True)
        lay.addWidget(self.broll_check)

        lay.addWidget(QLabel("내레이션"))
        self.narration = QPlainTextEdit()
        self.narration.setMinimumHeight(96)
        self.narration.setMaximumHeight(320)
        self.narration.textChanged.connect(self._on_narration)
        self.narration.selectionChanged.connect(self._on_narr_select)
        lay.addWidget(self.narration, 1)   # 남는 높이는 글 쓰는 칸이 먹는다 (09 G3)
        self.narr_info = QLabel("")
        self.narr_info.setObjectName("caption")
        lay.addWidget(self.narr_info)
        # 발화시각 계산기 — 구절 선택 → 글자수÷페이스 → tN 원클릭 기입 (03 ⑤)
        self.spoken_row = QHBoxLayout()
        self.spoken_label = QLabel("")
        self.spoken_label.setObjectName("caption")
        self.spoken_row.addWidget(self.spoken_label)
        self.spoken_row.addStretch(1)
        lay.addLayout(self.spoken_row)

        self.params_head = QHBoxLayout()
        self.params_title = QLabel("")
        self.params_title.setObjectName("sectionTitle")
        self.extract_btn = QPushButton("B롤 프레임 추출 → src 기입")
        self.extract_btn.clicked.connect(self._extract_frame)
        self.params_head.addWidget(self.params_title)
        self.params_head.addStretch(1)
        self.params_head.addWidget(self.extract_btn)
        lay.addLayout(self.params_head)

        self.params_form_holder = QWidget()
        self.params_form = QFormLayout(self.params_form_holder)
        self.params_form.setLabelAlignment(Qt.AlignRight)
        lay.addWidget(self.params_form_holder)

        self.inherit_label = QLabel("")
        self.inherit_label.setObjectName("caption")
        self.inherit_label.setWordWrap(True)
        lay.addWidget(self.inherit_label)
        self.unknown_box = QVBoxLayout()
        lay.addLayout(self.unknown_box)
        return scroll

    # ══ 우: 프리뷰 (D10 — 같은 문서·같은 시킹이라 프리뷰가 곧 실물) ═══════════
    def _make_right(self) -> QWidget:
        w = _PreviewColumn()
        lay = QVBoxLayout(w)
        # QApplication 이전 임포트·GPU 폴백은 app.bootstrap 이 담당 (호출자가 임포트했어야 함)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.preview = QWebEngineView()
        self.preview.setMinimumHeight(240)
        w.preview = self.preview        # 폭이 바뀌면 16:9 로 다시 잡는다
        lay.addWidget(self.preview)
        scrub_row = QHBoxLayout()
        from PySide6.QtWidgets import QSlider

        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 100)  # ×0.1s
        self.scrub.valueChanged.connect(self._seek)
        self.scrub_label = QLabel("0.0s")
        self.scrub_label.setObjectName("caption")
        self.replay_btn = QPushButton("↻ 재생")
        self.replay_btn.clicked.connect(self._refresh_preview)
        scrub_row.addWidget(self.scrub, 1)
        scrub_row.addWidget(self.scrub_label)
        scrub_row.addWidget(self.replay_btn)
        lay.addLayout(scrub_row)

        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget

        self.broll_video = QVideoWidget()
        self.broll_video.setMinimumHeight(240)
        self.broll_video.hide()
        self.broll_player = QMediaPlayer()
        self.broll_player.setVideoOutput(self.broll_video)
        lay.insertWidget(0, self.broll_video)
        self.broll_play_btn = QPushButton("▶ B롤 재생")
        self.broll_play_btn.clicked.connect(self.broll_player.play)
        self.broll_play_btn.hide()
        lay.addWidget(self.broll_play_btn)

        voice_head = QLabel("음성")
        voice_head.setObjectName("sectionTitle")
        lay.addWidget(voice_head)
        voice_row = QHBoxLayout()
        self.voice_btn = QPushButton("▶ 캐시 재생")
        self.voice_btn.clicked.connect(self._play_voice)
        self.audio.bind(self.voice_btn, "▶ 캐시 재생")
        self.tts_btn = QPushButton("음성 다시 만들기")
        self.tts_btn.clicked.connect(self.tts_requested.emit)
        voice_row.addWidget(self.voice_btn)
        voice_row.addWidget(self.tts_btn)
        voice_row.addStretch(1)
        lay.addLayout(voice_row)
        self.voice_note = QLabel("")
        self.voice_note.setObjectName("caption")
        lay.addWidget(self.voice_note)
        lay.addStretch(1)
        return w

    # ── 문맥 ────────────────────────────────────────────────────────────────
    @property
    def clips(self) -> list[dict]:
        return self.doc.get("render", {}).get("motion", {}).get("clips", [])

    @property
    def cur(self) -> dict | None:
        return self.clips[self._selected] if 0 <= self._selected < len(self.clips) else None

    def load(self, eid: str, scenes: dict, etag: str, inspect: dict,
             budget_text: str) -> None:
        self._loading = True
        self.eid = eid
        self.doc = copy.deepcopy(scenes)
        self._etag = etag
        self._inspect = inspect or {}
        m = re.search(r"([\d,]+)\s*자", budget_text or "")
        self._budget = int(m.group(1).replace(",", "")) if m else 1850
        studio = self._make_studio()
        run_bg(lambda: (studio.templates(scope=eid), studio.assets("broll")),
               done=self._assets_loaded, fail=lambda e: None)
        self._refresh_list(select=0)
        self._loading = False

    def set_inspect(self, inspect: dict) -> None:
        """[TTS 실측 갱신] 후 부모가 재조회한 inspect 를 주입 — 실측 라벨 갱신."""
        self._inspect = inspect or {}
        self._refresh_list(select=self._selected)

    def _assets_loaded(self, result) -> None:
        self._gallery, self._brolls = result
        self._render_broll_check()

    @property
    def audio_cache(self) -> dict:
        return self._inspect.get("audioCache") or {}

    # ── 리스트·예산 ─────────────────────────────────────────────────────────
    def _refresh_list(self, select: int = -1) -> None:
        # clear()/addItem() 이 selection 시그널을 쏜다 — 막지 않으면 목록을 다시 그리는
        # 동안 _on_select 가 중간 상태로 불려 편집 중인 클립이 바뀐다 (08 §7)
        self.clip_list.blockSignals(True)
        self.clip_list.clear()
        for c in self.clips:
            secs, measured = clip_seconds(c, self.audio_cache)
            # 역할을 한국어로 먼저 — id 는 괄호 보조 (10 #8)
            role = kinds.role_label(c.get("id"))
            label = f"{role} ({c.get('id', '?')})"
            item = QListWidgetItem(f"≡ {label:<16} {c.get('file') or c.get('video') or '—'}"
                                   f"  {secs:.1f}s{'' if measured else '?'}")
            item.setToolTip(c.get("narration", ""))
            self.clip_list.addItem(item)
        self.clip_list.blockSignals(False)
        if 0 <= select < len(self.clips):
            self.clip_list.setCurrentRow(select)
            self._selected = select
            self._render_clip()
        self._render_budget()
        self._render_skeleton_warn()

    def _render_budget(self) -> None:
        total = sum(len(c.get("narration", "")) for c in self.clips)
        secs = sum(clip_seconds(c, self.audio_cache)[0] for c in self.clips)
        measured_all = all(clip_seconds(c, self.audio_cache)[1] for c in self.clips)
        pct = round(total / self._budget * 100) if self._budget else 0
        self.budget_label.setText(f"내레이션 {total:,} / {self._budget:,}자 · {pct}%")
        self.budget_bar.setValue(min(100, pct))
        over = pct > 100
        self.budget_label.setStyleSheet(
            f"color: {theme.DANGER}; font-weight: 700;" if over else "")
        note = f"{'실측' if measured_all else '추정'} {int(secs // 60)}:{int(secs % 60):02d}"
        if over:
            note += " — 넘치면 압축이 아니라 영상 분할"
        self.budget_note.setText(note)

    def _render_skeleton_warn(self) -> None:
        ids = [c.get("id") for c in self.clips if c.get("id") in SKELETON]
        want = [s for s in SKELETON if s in ids]
        bad = ids != want
        self.skeleton_warn.setText("골격 위치 규약(broll→title→hook→stinger→promise)과 순서가 다릅니다")
        self.skeleton_warn.setVisible(bad)

    def _on_reorder(self, _p, start, _e, _d, dest) -> None:
        clips = self.clips
        moved = clips.pop(start)
        clips.insert(dest if dest < start else dest - 1, moved)
        self._refresh_list(select=self.clip_list.currentRow())

    def _on_select(self, row: int) -> None:
        if self._loading or row < 0:
            return
        self._selected = row
        self._render_clip()

    # ── 클립 추가·삭제 (id 골격 관례 자동 제안 — 3A) ─────────────────────────
    def _next_id(self, kind: str) -> str:
        ids = {c.get("id") for c in self.clips}
        if kind == "chapter":
            n = 1
            while f"ch{n}" in ids:
                n += 1
            return f"ch{n}"
        if kind == "diagram":
            n = 1
            while True:
                for suf in "abc":
                    if f"s{n}{suf}" not in ids:
                        return f"s{n}{suf}"
                n += 1
        n = 1
        while ("broll" if n == 1 else f"broll{n}") in ids:
            n += 1
        return "broll" if n == 1 else f"broll{n}"

    def _add_clip(self, kind: str) -> None:
        cid = self._next_id(kind)
        clip = ({"id": cid, "video": "", "videoStart": 0, "shade": 0.35,
                 "duration": 2.0, "before": "end"} if kind == "broll" else
                {"id": cid, "file": "chapter.html" if kind == "chapter" else "",
                 "before": "end", "narration": "", "params": {"wipe": "off"}})
        pos = self._selected + 1 if self._selected >= 0 else len(self.clips)
        self.clips.insert(pos, clip)
        self._refresh_list(select=pos)

    def _remove_clip(self) -> None:
        c = self.cur
        if not c:
            return
        if QMessageBox.question(self, "삭제", f"{c.get('id')} 클립을 삭제할까요?") != QMessageBox.Yes:
            return
        self.clips.pop(self._selected)
        self._refresh_list(select=max(0, self._selected - 1))

    # ── 클립 편집 렌더 ──────────────────────────────────────────────────────
    def _accepted_keys(self) -> list[str]:
        c = self.cur
        f = c.get("file") if c else None
        if not f:
            return []
        t = (self._inspect.get("templates") or {}).get(f)
        if t:
            return t.get("params", [])
        g = next((x for x in self._gallery if x["file"] == f), None)
        return g.get("params", []) if g else []

    def _render_clip(self) -> None:
        c = self.cur
        if c is None:
            return
        self._loading = True
        self.cur_id.setText(f'{kinds.role_label(c.get("id"))} ({c.get("id", "?")})')
        is_broll = "video" in c
        self.screen_label.setText(c.get("file") or c.get("video") or "(미선택)")
        self.tpl_btn.setVisible(not is_broll)
        self.broll_btn.setVisible(is_broll)
        self.broll_row.setVisible(is_broll)
        if is_broll:
            self.video_start.setText(str(c.get("videoStart", 0)))
            self.shade.setText(str(c.get("shade", "")))
        self.narration.setPlainText(c.get("narration", ""))
        self._render_narr_info()
        self._render_params_form()
        self._render_broll_check()
        self._render_voice()
        self._refresh_preview()
        self._loading = False

    def _render_params_form(self) -> None:
        while self.params_form.rowCount():
            self.params_form.removeRow(0)
        while self.unknown_box.count():
            item = self.unknown_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        c = self.cur
        accepted = self._accepted_keys()
        has_form = bool(c and c.get("file") and accepted)
        self.params_form_holder.setVisible(has_form)
        self.params_title.setText("화면 값 — 이 템플릿이 받는 키만" if has_form else "")
        self.extract_btn.setVisible(
            has_form and "src" in accepted
            and any(x.get("video") for x in self.clips))
        if not has_form:
            self.inherit_label.setText("")
            return
        editable = [k for k in accepted if k not in AUTO_KEYS and k != "wipe"]
        params = c.get("params") or {}
        for k in editable:  # ① 받는 키만 폼 생성 — 자유 키 입력 자체가 없음
            field = QLineEdit(str(params.get(k, "")))
            field.setMaximumWidth(420)
            field.textEdited.connect(lambda v, key=k: self._set_param(key, v))
            self.params_form.addRow(k, field)
        wipe = QComboBox()
        wipe.addItem("off (모션 전용 기본)", "off")
        wipe.addItem("on (밝은 앱 화면 전환 시)", "on")
        wipe.setCurrentIndex(1 if params.get("wipe") == "on" else 0)
        wipe.currentIndexChanged.connect(
            lambda i, w=wipe: self._set_param("wipe", w.currentData()))
        self.params_form.addRow("wipe", wipe)
        inherited = [k for k in AUTO_KEYS if params.get(k)]
        self.inherit_label.setText(
            "프로젝트 상속 중 (수동 입력 불가): " + " · ".join(f"{k} ✓" for k in inherited)
            if inherited else "")
        for k in sorted(set(params) - set(accepted)):  # ① 안 받는 키 → 빨간 목록 + [제거]
            row = QHBoxLayout()
            warn = QLabel(f'"{k}" 는 {c.get("file")} 이 받지 않는 키 — 화면에서 조용히 사라집니다')
            warn.setProperty("chip", "err")
            drop = QPushButton("제거")
            drop.clicked.connect(lambda _c=False, key=k: self._drop_param(key))
            row.addWidget(warn)
            row.addWidget(drop)
            row.addStretch(1)
            holder = QWidget()
            holder.setLayout(row)
            self.unknown_box.addWidget(holder)

    def _set_param(self, key: str, value) -> None:
        c = self.cur
        if c is None:
            return
        params = c.setdefault("params", {})
        if value in ("", None):
            params.pop(key, None)
        else:
            params[key] = value

    def _drop_param(self, key: str) -> None:
        c = self.cur
        if c and c.get("params"):
            c["params"].pop(key, None)
        self._render_params_form()

    # ── 내레이션·발화시각 ────────────────────────────────────────────────────
    def _on_narration(self) -> None:
        if self._loading or self.cur is None:
            return
        self.cur["narration"] = self.narration.toPlainText()
        self._render_narr_info()
        self._render_budget()
        self._render_broll_check()

    def _render_narr_info(self) -> None:
        c = self.cur
        if c is None:
            return
        n = len(c.get("narration", ""))
        measured = self.audio_cache.get(c.get("id"))
        self.narr_info.setText(
            f"{n}자 · " + (f"실측 {measured:.1f}s" if measured else f"추정 {n / PACE:.1f}s"))

    def _on_narr_select(self) -> None:
        cur = self.narration.textCursor()
        start = min(cur.selectionStart(), cur.selectionEnd())
        text = cur.selectedText()
        while self.spoken_row.count() > 2:
            item = self.spoken_row.takeAt(2)
            if item.widget():
                item.widget().deleteLater()
        if not text:
            self.spoken_label.setText("")
            return
        at = start / PACE
        self.spoken_label.setText(f'"{text[:12]}…" 발화 ≈ {at:.2f}s')
        for k in [k for k in self._accepted_keys()
                  if k not in AUTO_KEYS and TIME_KEY_RE.match(k)]:
            b = QPushButton(f"→ {k}")
            b.clicked.connect(lambda _c=False, key=k, v=f"{at:.2f}": (
                self._set_param(key, v), self._render_params_form()))
            self.spoken_row.addWidget(b)

    # ── 피커 (결함 차단 ②) ──────────────────────────────────────────────────
    def _pick_template(self) -> None:
        rows = [[t["file"], t["scope"],
                 " · ".join(k for k in t["params"] if k not in AUTO_KEYS and k != "wipe")]
                for t in self._gallery]
        dlg = PickerDialog("도식 템플릿 선택", ["파일", "범위", "받는 키"], rows, self)
        if dlg.exec() and dlg.picked is not None:
            c = self.cur
            c["file"] = self._gallery[dlg.picked]["file"]
            c.pop("video", None)
            c.pop("videoStart", None)
            self._render_clip()
            self._refresh_list(select=self._selected)

    def _pick_broll(self) -> None:
        rows = [[a["name"], f"{a.get('duration', 0)}s · {a.get('width', 0)}×{a.get('height', 0)}",
                 a.get("license") or "없음"] for a in self._brolls]
        dlg = PickerDialog("B롤 선택 — 길이·라이선스를 보고 고른다", ["파일", "길이·해상도", "라이선스"],
                           rows, self)
        if dlg.exec() and dlg.picked is not None:
            a = self._brolls[dlg.picked]
            c = self.cur
            c["video"] = a["ref"]
            c.setdefault("videoStart", 0)
            c.setdefault("shade", 0.35)
            c.pop("file", None)
            c.pop("params", None)
            self._render_clip()
            self._refresh_list(select=self._selected)

    def _on_field_edit(self) -> None:
        if self._loading or self.cur is None:
            return
        c = self.cur
        try:
            c["videoStart"] = float(self.video_start.text() or 0)
        except ValueError:
            pass
        try:
            c["shade"] = float(self.shade.text() or 0)
        except ValueError:
            pass
        self._render_broll_check()

    # ── B롤 길이 즉시 검사 (결함 차단 ④) ────────────────────────────────────
    def _render_broll_check(self) -> None:
        c = self.cur
        if c is None or "video" not in c:
            self.broll_check.setText("")
            return
        if not self._brolls:
            self.broll_check.setText("라이브러리 로딩 중…")  # 오탐 방지 (3단계 실측 메모)
            self.broll_check.setStyleSheet("")
            return
        src = next((a for a in self._brolls if a["ref"] == c.get("video")), None)
        duration = (src or {}).get("duration") or \
            ((self._inspect.get("media") or {}).get(c.get("video"), {}) or {}).get("duration", 0)
        if not duration:
            self.broll_check.setText("소재 길이를 모릅니다 — 경로를 확인하세요")
            self.broll_check.setStyleSheet(f"color: {theme.DANGER};")
            return
        need = clip_seconds(c, self.audio_cache)[0]
        avail = duration - float(c.get("videoStart") or 0)
        if need > avail + 0.05:
            self.broll_check.setText(
                f"구간 {need:.1f}s > 쓸 수 있는 소스 {avail:.1f}s — 마지막 {need - avail:.1f}s 정지 프레임")
            self.broll_check.setStyleSheet(f"color: {theme.DANGER}; font-weight: 600;")
        else:
            self.broll_check.setText(f"구간 {need:.1f}s / 소스 여유 {avail:.1f}s ✓")
            self.broll_check.setStyleSheet(f"color: {theme.SUCCESS};")

    # ── title 프레임 추출 (videoStart↔프레임 일치를 한 버튼으로) ─────────────
    def _extract_frame(self) -> None:
        b = next((x for x in self.clips if x.get("video")), None)
        c = self.cur
        if not b or not c:
            return
        eid, studio = self.eid, self._make_studio()
        video, vs, cf = b["video"], b.get("videoStart", 0), c["file"]
        run_bg(lambda: studio.bg_frame(eid, video=video, video_start=vs, clip_file=cf),
               done=lambda out: (self._set_param("src", out["src"]),
                                 self._render_params_form(),
                                 self.issues.setText(f"bg/{out['file']} 추출 — src 기입됨 "
                                                     f"(B롤 {vs}s 프레임)"),
                                 self.issues.setProperty("chip", "ok"),
                                 self._repolish(self.issues), self.issues.show()),
               fail=lambda e: self._show_issue(error_text(e)))

    # ── 프리뷰 (QWebEngineView — preview.js 문서 + 질의 params) ──────────────
    def _refresh_preview(self) -> None:
        c = self.cur
        is_broll = bool(c and "video" in c)
        self.preview.setVisible(not is_broll)
        self.scrub.setVisible(not is_broll)
        self.broll_video.setVisible(is_broll)
        self.broll_play_btn.setVisible(is_broll)
        if c is None:
            return
        if is_broll:
            if c.get("video"):
                p = paths.invert(paths.RefKind.BROLL, c["video"])
                if p.exists():
                    self.broll_player.setSource(QUrl.fromLocalFile(str(p)))
            return
        f = c.get("file")
        if not f:
            self.preview.setHtml("<body style='background:#111'></body>")
            return
        eid, studio = self.eid, self._make_studio()
        secs = clip_seconds(c, self.audio_cache)[0]
        self.scrub.setRange(0, max(10, int(secs * 10)))
        self.scrub.setValue(0)

        def build():
            html = studio.template_preview(f, scope=eid)
            out = env.cache_dir() / f"preview-{hashlib.sha1((eid + f).encode()).hexdigest()[:10]}.html"
            out.write_text(html, encoding="utf-8", newline="\n")
            return out

        run_bg(build, done=lambda p: self._load_preview(p), fail=lambda e: None)

    def _load_preview(self, doc_path: Path) -> None:
        c = self.cur
        if c is None or "file" not in c:
            return
        url = QUrl.fromLocalFile(str(doc_path))
        from urllib.parse import quote

        d = self._episode_dir()
        html = paths.invert(paths.RefKind.MOTION, c["file"], scenes_dir=d)
        pairs = []
        for k, v in (c.get("params") or {}).items():
            if v in ("", None):
                continue
            # 경로형 params 는 프리뷰 문서 위치 기준으로 깨진다 — 절대 file:// URL 로 치환
            if k in ("src", "fontUrl"):
                target = paths.invert(paths.RefKind.HTML_ASSET, str(v), html_file=html)
                if target.exists():
                    v = QUrl.fromLocalFile(str(target)).toString()
            pairs.append(f"{quote(k)}={quote(str(v))}")
        url.setQuery("&".join(pairs))
        self.preview.load(url)

    def _episode_dir(self) -> Path:
        return self._make_studio().episode_dir(self.eid)

    def _seek(self, v: int) -> None:
        sec = v / 10
        self.scrub_label.setText(f"{sec:.1f}s")
        self.preview.page().runJavaScript(
            "for (const a of document.getAnimations({subtree:true}))"
            f"{{ a.pause(); a.currentTime = {int(sec * 1000)}; }}")

    # ── 음성 ────────────────────────────────────────────────────────────────
    def _render_voice(self) -> None:
        c = self.cur
        cached = c is not None and self.audio_cache.get(c.get("id"))
        self.voice_btn.setEnabled(bool(cached))
        self.voice_note.setText(f"TTS 캐시 {cached:.1f}s" if cached
                                else "TTS 캐시 없음 — [TTS 실측 갱신]으로 만드세요")

    def _play_voice(self) -> None:
        if self.audio.stop_if_playing(self.voice_btn):   # 두 번째 클릭 = 중지
            return
        c = self.cur
        if not c:
            return
        p = OUT_ROOT / self.eid / "audio" / f"motion-{c.get('id')}.mp3"
        if p.exists():
            self.audio.start(self.voice_btn, p)

    # ── 저장 (etag — 응답 etag 항상 채택) ───────────────────────────────────
    def _save(self) -> None:
        eid, etag, studio = self.eid, self._etag, self._make_studio()
        body = self.doc
        run_bg(lambda: studio.put_episode(eid, body, etag),
               done=self._saved, fail=lambda e: self._show_issue(error_text(e)))

    def _saved(self, out: dict) -> None:
        self._etag = out["etag"]  # 경로 문제가 있어도 채택 — 다음 저장 409 교착 방지
        issues = out.get("pathIssues") or []
        cons = out.get("consistency") or []
        if issues:
            self._show_issue("저장됨 — 경로 문제:\n" + "\n".join(issues))
        else:
            msg = "저장됨 ✓" + (f" — 프로젝트 일관성 {len(cons)}건 어긋남" if cons else "")
            self.issues.setText(msg)
            self.issues.setProperty("chip", "ok" if not cons else "warn")
            self._repolish(self.issues)
            self.issues.show()
        self.saved.emit()

    def _show_issue(self, text: str) -> None:
        self.issues.setText(text)
        self.issues.setProperty("chip", "err")
        self._repolish(self.issues)
        self.issues.show()

    @staticmethod
    def _repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)
