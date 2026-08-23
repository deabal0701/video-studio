"""① 프로젝트 설정 — course.json 편집 폼 (03 ①. etag 저장 → 일관성 재검사 배지).

목소리·BGM 은 "사람이 귀로 고른다" 규약 그대로: 실제 TTS 합성 미리듣기 + BGM 재생 버튼.
palette 는 render(brand·brandText·background)와 동기화해 저장한다 (개설 로직과 동일 규약).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
                               QWidget)

from core import kinds, voices

from ..bridge import error_text, run_bg
from ..widgets import AudioPreview, ColorButton

VOICE_PRESETS = {
    "female": ({"provider": "edge", "lang": "ko", "gender": "female", "rate": "+8%"},
               "선희 (여) · 말 속도 +8%"),
    "male": ({"provider": "edge", "lang": "ko", "gender": "male", "rate": "+19%"},
             "인준 (남) · 말 속도 +19%"),
}


_P = kinds.get(kinds.DEFAULT_KIND)["palette"]   # 색 폴백 (종류가 정본)

class CourseSettingsTab(QWidget):
    deleted = Signal()   # 삭제 완료 → 대시보드로
    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self.cid: str | None = None
        self._etag: str | None = None
        self._doc: dict = {}
        self.audio = AudioPreview()

        # 폼은 위로 붙인다 — QFormLayout 직접 얹으면 남는 세로 공간이 행간으로 분배돼
        # 행간이 붕괴한다 (08_qt-style §4-1). 필드 폭도 RD_FIELD 로 제한 (§4-2).
        from PySide6.QtWidgets import QVBoxLayout

        from .. import theme

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setContentsMargins(8, 16, 8, 8)
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(theme.GAP_STACK)
        form.setVerticalSpacing(theme.GAP_STACK)
        outer.addLayout(form)
        outer.addStretch(1)
        self.title = QLineEdit()
        self.tagline = QLineEdit()
        self.audience = QPlainTextEdit()
        self.audience.setFixedHeight(110)
        for w in (self.title, self.tagline, self.audience):
            w.setMaximumWidth(theme.RD_FIELD)
        form.addRow("프로젝트 이름", self.title)
        form.addRow("태그라인", self.tagline)
        form.addRow("대상", self.audience)

        # 종류는 화면 어디에도 없었다 — 위저드에서 고른 뒤로는 확인할 길이 없는데
        # 골격·기본 길이·색·세는 말("N강"/"N편")이 전부 여기서 갈린다 (52회차 P16).
        # 읽기 전용 — 만든 뒤 바꾸면 이미 깔린 대본 골격과 어긋난다
        self.kind_note = QLabel("")
        self.kind_note.setObjectName("caption")
        self.kind_note.setWordWrap(True)
        self.kind_note.setMaximumWidth(theme.RD_FIELD)
        form.addRow("종류", self.kind_note)

        # 제공자 — 엔진은 edge·azure·eleven 을 다 지원하는데 화면은 edge 2종만 내보내고
        # 있었다 (2026-08-22). 키를 받아 두고 쓸 길이 없던 것이 결함이었다.
        prov_row = QHBoxLayout()
        self.provider = QComboBox()
        for key in ("edge", "azure", "eleven"):
            self.provider.addItem(voices.PROVIDER_LABELS[key], key)
        self.provider.setFixedWidth(260)
        self.provider.currentIndexChanged.connect(self._reload_voices)
        self.prov_note = QLabel("")
        self.prov_note.setObjectName("caption")
        self.prov_note.setWordWrap(True)
        prov_row.addWidget(self.provider)
        prov_row.addWidget(self.prov_note, 1)
        form.addRow("음성 제공자", prov_row)

        voice_row = QHBoxLayout()
        self.voice = QComboBox()
        self.voice.setMinimumWidth(300)
        self.tts_btn = QPushButton("▶ 들어보기")
        self.tts_btn.clicked.connect(self._preview_tts)
        self.audio.bind(self.tts_btn, "▶ 들어보기")
        self.prefetch_btn = QPushButton("전부 미리 만들기")
        self.prefetch_btn.setToolTip("한 번 만들어 두면 이후 들어보기는 즉시 나고 과금도 없습니다")
        self.prefetch_btn.clicked.connect(self._prefetch)
        self.tts_state = QLabel("")
        self.tts_state.setObjectName("caption")
        self.tts_state.setFixedWidth(240)   # 상태 글이 늘어나도 앞 버튼이 안 밀리게
        for w in (self.voice, self.tts_btn, self.prefetch_btn, self.tts_state):
            voice_row.addWidget(w)
        voice_row.addStretch(1)
        form.addRow("목소리", voice_row)
        # 라디오는 저장 스키마의 gender 를 위해 남긴다 — 화면에는 안 보인다
        self.v_female = QRadioButton(VOICE_PRESETS["female"][1])
        self.v_male = QRadioButton(VOICE_PRESETS["male"][1])
        self.v_female.hide()
        self.v_male.hide()

        pal_row = QHBoxLayout()
        self.c_brand = ColorButton()
        self.c_soft = ColorButton()
        self.c_bg = ColorButton()
        for label, btn in (("브랜드", self.c_brand), ("보조", self.c_soft), ("배경", self.c_bg)):
            cap = QLabel(label)
            cap.setObjectName("caption")
            pal_row.addWidget(cap)
            pal_row.addWidget(btn)
            pal_row.addSpacing(14)
        pal_row.addStretch(1)
        form.addRow("색", pal_row)

        bgm_row = QHBoxLayout()
        self.bgm = QComboBox()
        self.bgm.setMinimumWidth(420)
        self.bgm_play = QPushButton("▶ 듣기")
        self.bgm_play.clicked.connect(self._play_bgm)
        self.audio.bind(self.bgm_play, "▶ 듣기")
        bgm_row.addWidget(self.bgm)
        bgm_row.addWidget(self.bgm_play)
        bgm_row.addStretch(1)
        form.addRow("배경음악", bgm_row)

        # 길이 = 콤보 + 자동 글자수 — 위저드와 같은 UX (루프 4회차 P10·P11:
        # "글자수 지정은 너무 어렵다"가 이 탭에는 남아 있었다)
        len_box = QVBoxLayout()
        self.length = QComboBox()
        self.length.setEditable(True)
        self.length.addItems(kinds.LENGTH_CHOICES)
        self.length.setFixedWidth(200)
        self.length.currentTextChanged.connect(self._sync_length_note)
        len_box.addWidget(self.length)
        self.length_note = QLabel("")
        self.length_note.setObjectName("caption")
        len_box.addWidget(self.length_note)
        form.addRow("영상 길이", len_box)

        save_row = QHBoxLayout()
        self.save_btn = QPushButton("설정 저장")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        save_row.addWidget(self.save_btn)
        save_row.addWidget(self.result)
        save_row.addStretch(1)
        form.addRow("", save_row)

        # ── 위험 구역 — 삭제는 가장 아래, 저장과 섞이지 않게 (10: "삭제는 어디에") ──
        del_row = QHBoxLayout()
        self.delete_btn = QPushButton("프로젝트 삭제…")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        del_note = QLabel("영상·설정·완성본까지 전부 지워집니다 — 되돌릴 수 없습니다")
        del_note.setObjectName("caption")
        del_row.addWidget(self.delete_btn)
        del_row.addWidget(del_note)
        del_row.addStretch(1)
        form.addRow("", del_row)

        # 사용자 편집 감지 — 탭 재진입이 편집을 덮지 않게 (36회차 P0.
        # textEdited 는 사용자 입력만, 나머지는 _loading 가드가 로드를 걸러낸다)
        self.title.textEdited.connect(self._mark_dirty)
        # 이름을 비우고도 저장이 됐다 — 저장된 뒤엔 대시보드 카드·프로젝트 헤더·삭제
        # 확인이 전부 이름 없이 뜨고 **완성본 워터마크까지 빈 문자열**이 된다 (52회차 P20).
        # 위저드 [만들기](34회차)·라이브러리 [받기](27회차)와 같은 문법 — 비활성 primary
        self.title.textEdited.connect(self._sync_save_btn)
        self.tagline.textEdited.connect(self._mark_dirty)
        self.audience.textChanged.connect(self._mark_dirty)
        self.length.currentTextChanged.connect(self._mark_dirty)
        self.provider.currentIndexChanged.connect(self._mark_dirty)
        self.voice.currentIndexChanged.connect(self._mark_dirty)
        self.bgm.currentIndexChanged.connect(self._mark_dirty)
        for btn in (self.c_brand, self.c_soft, self.c_bg):
            btn.changed.connect(self._mark_dirty)

    # ── 로드 ────────────────────────────────────────────────────────────────
    def _sync_save_btn(self, *_a) -> None:
        if getattr(self, "_saving", False):
            return   # 저장 중 잠금이 이긴다 (36회차 P18)
        ok = bool(self.title.text().strip())
        self.save_btn.setEnabled(ok)
        self.save_btn.setToolTip("" if ok else "프로젝트 이름을 넣으세요 — 빈 이름으로는 저장할 수 없습니다")

    def _mark_dirty(self, *_a) -> None:
        if not getattr(self, "_loading", False):
            self._dirty = True

    def load(self, cid: str) -> None:
        # 편집 중엔 탭 재진입이 화면을 덮으면 안 된다 (36회차 P0 — 배포 탭 26회차와
        # 같은 결함·같은 처방. 저장하거나 다른 프로젝트를 열면 새로 읽는다)
        if cid == self.cid and getattr(self, "_dirty", False):
            return
        if cid != self.cid:
            # 다른 프로젝트로 옮기면 앞 프로젝트의 상태 글을 지운다 — 안 지우면
            # "저장됨 — 일관성 어긋난 영상 1개: insait-promo-01" 이 **다른 프로젝트**
            # 화면에 그대로 남는다 (52회차 P19·P11, 캡처에서 발견).
            # 같은 프로젝트 재로드(저장 직후)에는 손대지 않는다 — "저장됨 ✓"이 남아야 한다
            self.result.setText("")
            self.tts_state.setText("")
        self.cid = cid
        studio = self._make_studio()
        run_bg(lambda: (studio.get_course(cid), studio.assets("bgm")),
               done=self._fill, fail=lambda e: self.result.setText(error_text(e)))

    def _fill(self, result) -> None:
        self._loading = True
        body, bgms = result
        self._etag = body["etag"]
        self._doc = body["course"]
        d = self._doc
        self.title.setText(d.get("title", ""))
        self.tagline.setText(d.get("tagline", ""))
        self.audience.setPlainText(d.get("audience", ""))
        self.length.setCurrentText(kinds.length_display(d.get("episodeLength", "")))
        v = d.get("voice") or {}
        (self.v_male if v.get("gender") == "male" else self.v_female).setChecked(True)
        idx = self.provider.findData(v.get("provider") or "edge")
        self.provider.blockSignals(True)   # 복원이지 사용자 선택이 아니다 (08 §7)
        self.provider.setCurrentIndex(max(0, idx))
        self.provider.blockSignals(False)
        self._reload_voices(select=v.get("voice"))
        pal = d.get("palette", {})
        self.c_brand.set_value(pal.get("brand", _P["brand"]))
        self.c_soft.set_value(pal.get("brandSoft", _P["brandSoft"]))
        self.c_bg.set_value(pal.get("bg", _P["bg"]))
        kind = d.get("kind")
        spec = kinds.get(kind)
        self.kind_note.setText(
            f"{spec['label']} · {'여러 편을 담는 시리즈' if spec['series'] else '단발 영상'}"
            f" — 만들 때 정해집니다 (골격·기본 길이·색이 여기서 따라옵니다)")
        self.bgm.clear()
        for a in bgms:
            self.bgm.addItem(a["name"], a["ref"])
        current = d.get("render", {}).get("bgm", "")
        idx = self.bgm.findData(current)
        if idx >= 0:
            self.bgm.setCurrentIndex(idx)
        self._loading = False
        self._dirty = False
        self._sync_save_btn()

    def _sync_length_note(self, *_a) -> None:
        chars = kinds.length_to_chars(self.length.currentText())
        self.length_note.setText(f"내레이션 약 {chars:,}자 분량입니다" if chars
                                 else '"3분"처럼 분·초로 적어주세요')

    # ── 미리듣기 ─────────────────────────────────────────────────────────────
    # ── 목소리 목록 ─────────────────────────────────────────────────────────
    def _reload_voices(self, _idx: int = -1, *, select: str | None = None) -> None:
        prov = self.provider.currentData()
        self.voice.clear()
        self.prov_note.setText("불러오는 중…")
        studio = self._make_studio()

        def fill(info: dict) -> None:
            for v in info["voices"]:
                mark = "" if v.get("cached") else "  (아직 안 만듦)"
                sex = {"female": "여", "male": "남"}.get(v.get("gender"), "")
                label = f"{v['name']}{f' ({sex})' if sex else ''}{mark}"
                self.voice.addItem(label, v["id"])
            if select:
                i = self.voice.findData(select)
                if i >= 0:
                    self.voice.setCurrentIndex(i)
            n_cached = sum(1 for v in info["voices"] if v.get("cached"))
            paid = " · 유료(글자수 과금)" if info.get("paid") else ""
            self.prov_note.setText(
                (info.get("reason") or
                 f"{len(info['voices'])}종 · 미리듣기 준비됨 {n_cached}종{paid}"))
            ok = info["available"] and bool(info["voices"])
            for w in (self.voice, self.tts_btn, self.prefetch_btn):
                w.setEnabled(ok)

        run_bg(lambda: studio.voice_catalog(prov), done=fill,
               fail=lambda e: (self.prov_note.setText(error_text(e)),
                               self.voice.setEnabled(False)))

    # ── 미리듣기 (캐시 우선 — 같은 목소리를 두 번 합성하지 않는다) ────────────
    def _preview_tts(self) -> None:
        if self.audio.stop_if_playing(self.tts_btn):   # 두 번째 클릭 = 중지
            self.tts_state.setText("")
            return
        voice_id, prov = self.voice.currentData(), self.provider.currentData()
        if not voice_id:
            return
        gender = "male" if self.v_male.isChecked() else "female"
        studio = self._make_studio()
        self.tts_state.setText("준비 중…")
        run_bg(lambda: studio.voice_sample(prov, voice_id, gender=gender),
               done=lambda path: (self.audio.start(self.tts_btn, path),
                                  self.tts_state.setText(""),
                                  self._reload_voices(select=voice_id)),
               fail=lambda e: self.tts_state.setText(error_text(e)))

    def _prefetch(self) -> None:
        """그 제공자의 목소리를 전부 한 번씩 만들어 둔다 — 이후 공짜·즉시."""
        prov = self.provider.currentData()
        n = self.voice.count()
        if prov == "eleven":   # 유료는 얼마나 쓰는지 먼저 말하고 묻는다
            chars = n * len(voices.SAMPLE_TEXT)
            # 과금 확인의 기본 버튼은 [취소] — 엔터 연타가 결제가 되면 안 된다 (32회차 P20)
            if QMessageBox.question(
                    self, "미리듣기 만들기",
                    f"ElevenLabs 목소리 {n}종을 한 번씩 합성합니다 — "
                    f"약 {chars:,}자가 과금됩니다. "
                    "한 번 만들면 이후 들어보기는 과금 없이 즉시 납니다. 계속할까요?",
                    QMessageBox.Yes | QMessageBox.Cancel,
                    QMessageBox.Cancel) != QMessageBox.Yes:
                return
        studio = self._make_studio()
        self.prefetch_btn.setEnabled(False)
        self.tts_state.setText(f"{n}종 만드는 중…")

        def done(r: dict) -> None:
            self.prefetch_btn.setEnabled(True)
            msg = f"새로 {r['made']}종 · 이미 있던 {r['cached']}종"
            if r["failed"]:
                msg += f" · 실패 {len(r['failed'])}종"
            self.tts_state.setText(msg)
            self._reload_voices(select=self.voice.currentData())

        run_bg(lambda: studio.voice_samples_build(prov), done=done,
               fail=lambda e: (self.tts_state.setText(error_text(e)),
                               self.prefetch_btn.setEnabled(True)))

    def _play_bgm(self) -> None:
        if self.audio.stop_if_playing(self.bgm_play):   # 두 번째 클릭 = 중지
            return
        ref = self.bgm.currentData()
        if not ref:
            return
        studio = self._make_studio()
        name = ref.split("/")[-1]
        run_bg(lambda: studio.asset_path("bgm", name),
               done=lambda path: self.audio.start(self.bgm_play, path),
               fail=lambda e: self.result.setText(error_text(e)))

    # ── 삭제 ────────────────────────────────────────────────────────────────
    def _delete(self) -> None:
        title = self.title.text().strip() or self.cid
        if QMessageBox.warning(
                self, "프로젝트 삭제",
                f'"{title}" 프로젝트를 삭제할까요?\n\n'
                "영상·대본·설정·완성본(mp4)까지 전부 지워지고 되돌릴 수 없습니다.\n"
                "완성본이 필요하면 먼저 ④ 배포에서 저장해 두세요.",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel) != QMessageBox.Yes:
            return
        cid, studio = self.cid, self._make_studio()
        # 삭제 중 잠금 (48회차 P18) — 성공하면 화면을 떠나므로 복원은 실패 시만
        self.delete_btn.setEnabled(False)
        self.result.setText("삭제 중…")
        run_bg(lambda: studio.delete_course(cid),
               done=lambda _out: self.deleted.emit(),
               fail=lambda e: (self.result.setText(error_text(e)),
                               self.delete_btn.setEnabled(True)))

    # ── 저장 (etag) ──────────────────────────────────────────────────────────
    def _save(self) -> None:
        # 잠금은 버튼만이 아니라 **동작 자체**가 건다 — 버튼을 비활성으로 두는 것만으로는
        # 버튼 밖 경로(단축키·프로그램 호출)가 옛 etag 로 두 번째 저장을 보낸다
        # (52회차 실측. 보드 생성 3경로의 _begin_create 와 같은 문법 — 35회차)
        if getattr(self, "_saving", False):
            return
        if not self.title.text().strip():
            self.result.setText("프로젝트 이름을 넣으세요")
            return
        body = dict(self._doc)
        body["title"] = self.title.text().strip()
        body["tagline"] = self.tagline.text().strip()
        body["audience"] = self.audience.toPlainText().strip()
        length = kinds.length_value(self.length.currentText())
        if length:
            body["episodeLength"] = length
        # 엔진 스키마 그대로 (engine/lib/tts.js resolveVoiceFor):
        # provider + lang/gender/rate, 그리고 voice 가 있으면 그 id 가 이긴다
        voice_cfg = dict(VOICE_PRESETS["male" if self.v_male.isChecked()
                                       else "female"][0])
        voice_cfg["provider"] = self.provider.currentData() or "edge"
        if self.voice.currentData():
            voice_cfg["voice"] = self.voice.currentData()
        body["voice"] = voice_cfg
        body["palette"] = {"brand": self.c_brand.value, "brandSoft": self.c_soft.value,
                           "bg": self.c_bg.value}
        render = dict(body.get("render", {}))
        render.update({"brand": self.c_brand.value, "brandText": self.c_soft.value,
                       "background": self.c_bg.value,
                       "watermark": {**render.get("watermark", {}), "text": body["title"]}})
        if self.bgm.currentData():
            render["bgm"] = self.bgm.currentData()
        body["render"] = render

        cid, etag, studio = self.cid, self._etag, self._make_studio()
        # 처리 중 잠금 (P18 공통 문법) — 중복 클릭이 옛 etag 로 409 를 낸다
        self._saving = True
        self.save_btn.setEnabled(False)
        self.result.setText("저장 중…")
        run_bg(lambda: studio.put_course(cid, body, etag),
               done=self._saved,
               fail=lambda e: (setattr(self, "_saving", False),
                               self.result.setText(error_text(e)),
                               self._sync_save_btn()))

    def _saved(self, out: dict) -> None:
        self._saving = False
        self._sync_save_btn()
        self._dirty = False   # 저장됨 — 다음 재진입은 새로 읽는다
        self._etag = out["etag"]
        problems = out.get("consistency", {})
        self.result.setText("저장됨 ✓" if not problems
                            else f"저장됨 — 일관성 어긋난 영상 {len(problems)}개: "
                                 f"{', '.join(problems)}")
        self.load(self.cid)
