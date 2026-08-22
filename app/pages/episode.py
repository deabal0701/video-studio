"""영상 화면 — 탭 ④⑤⑥⑦ (5-5 완성. 탭 순서 = 제작 순서, 빌드 버튼은 탭 밖 머리에 상주)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QScrollArea, QTabWidget, QVBoxLayout,
                               QWidget)

from core.facade import NotBuilt
from core.status import OUT_ROOT

from .. import theme
from ..bridge import JobEventPump, error_text, run_bg
from .clip_editor import ClipEditorTab
from .deploy_tab import DeployTab
from .plan_tab import PlanTab

KIND_LABEL = {"title": "타이틀", "bright": "밝은 장면", "dark": "어두운 장면",
              "motion": "모션", "last": "마지막"}
CHECK_ITEMS = ["밝은 프레임 워터마크", "어두운 프레임 자막", "타이틀 프레임",
               "마지막 프레임", "무음 리포트 확인"]


class EpisodePage(QWidget):
    job_started = Signal(str)
    back = Signal(str)   # cid — [← 프로젝트] (①②③ 탭으로 되돌아간다)

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self._studio = None
        self.eid: str | None = None
        self._pump: JobEventPump | None = None
        self._job_id: str | None = None
        self._budget_text = ""
        self._checklist: dict = {"items": {}}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PAGE_PAD, 24, theme.PAGE_PAD, 24)

        head = QHBoxLayout()
        # 이 화면의 탭이 ④부터 시작한다 — ①②③(프로젝트 설정·영상 목록·브랜드 킷)으로
        # 돌아갈 길이 화면에 있어야 한다 (09 G8: 내가 어디 있는지·어디로 가는지)
        self.back_btn = QPushButton("← 프로젝트")
        self.back_btn.setFlat(True)
        self.back_btn.clicked.connect(
            lambda: self.eid and self.back.emit(self.eid.rsplit("-", 1)[0]))
        head.addWidget(self.back_btn)
        self.title = QLabel("")
        self.title.setObjectName("pageTitle")
        head.addWidget(self.title)
        self.stale = QLabel("대본이 더 새것 — 재빌드 필요")
        self.stale.setProperty("chip", "err")
        self.stale.hide()
        head.addWidget(self.stale)
        self.consistency_chip = QLabel("")
        self.consistency_chip.setProperty("chip", "warn")
        self.consistency_chip.hide()
        head.addWidget(self.consistency_chip)
        self.sync_btn = QPushButton("프로젝트 값으로 맞추기")
        self.sync_btn.clicked.connect(self._sync_course)
        self.sync_btn.hide()
        head.addWidget(self.sync_btn)
        head.addStretch(1)
        self.build_btn = QPushButton("빌드")
        self.build_btn.setObjectName("primary")
        self.tts_only_btn = QPushButton("TTS만")
        self.compose_btn = QPushButton("합성만")
        self.ai_review_btn = QPushButton("AI 평가")
        self.ai_review_btn.setEnabled(False)
        self.ai_review_btn.clicked.connect(self._ai_review)
        self.cancel_btn = QPushButton("중단")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.hide()
        for b in (self.build_btn, self.tts_only_btn, self.compose_btn,
                  self.ai_review_btn, self.cancel_btn):
            head.addWidget(b)
        outer.addLayout(head)
        self.build_btn.clicked.connect(lambda: self._build(None))
        self.tts_only_btn.clicked.connect(lambda: self._build("tts"))
        self.compose_btn.clicked.connect(lambda: self._build("compose"))
        self.cancel_btn.clicked.connect(self._cancel)

        self.state_chip = QLabel("")
        self.state_chip.setProperty("chip", "info")
        self.state_chip.hide()
        outer.addWidget(self.state_chip, alignment=Qt.AlignLeft)

        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.hide()
        outer.addWidget(self.log)

        self.error = QLabel("")
        self.error.setProperty("chip", "err")
        self.error.setWordWrap(True)
        self.error.hide()
        outer.addWidget(self.error)

        self.tabs = QTabWidget()
        self.plan_tab = PlanTab(make_studio)
        self.plan_tab.applied.connect(lambda: self.load(self.eid))
        self.clip_tab = ClipEditorTab(make_studio)
        self.clip_tab.saved.connect(self._on_clip_saved)
        self.clip_tab.tts_requested.connect(lambda: self._build("tts"))
        self.deploy_tab = DeployTab(make_studio)
        self.tabs.addTab(self.plan_tab, "④ 구성표")
        self.tabs.addTab(self.clip_tab, "⑤ 대본")
        self.tabs.addTab(self._make_review_tab(), "⑥ 검수")
        self.tabs.addTab(self.deploy_tab, "⑦ 배포")
        self.tabs.setCurrentIndex(1)
        self.tabs.currentChanged.connect(self._on_tab)
        outer.addWidget(self.tabs, 1)

    # ── ⑥ 검수 탭 ───────────────────────────────────────────────────────────
    def _make_review_tab(self) -> QWidget:
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        page = QWidget()
        outer.setWidget(page)
        shell = QVBoxLayout(page)
        self.not_built = QLabel("아직 완성본이 없습니다 — 위 [빌드] 를 눌러 영상을 만든 뒤 "
                                "이 화면에서 눈으로 검수합니다.")
        self.not_built.setObjectName("caption")
        self.not_built.setWordWrap(True)
        shell.addWidget(self.not_built)
        # 빌드 전엔 이 아래를 통째로 감춘다 — 빈 프레임 칸·빈 체크리스트는 화면이 아니다 (09 G1)
        self.review_body = QWidget()
        shell.addWidget(self.review_body, 1)
        lay = QVBoxLayout(self.review_body)
        lay.setContentsMargins(0, 0, 0, 0)
        self.video = QVideoWidget()
        # 재생을 눌러야 펼친다 — 빈 영상 위젯이 화면 상단 1/3 을 먹고 있었다 (09 G1·G3)
        self.video.setFixedHeight(theme.VIDEO_H)
        self.video.hide()
        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.player.setVideoOutput(self.video)
        row = QHBoxLayout()
        self.play_btn = QPushButton("▶ 재생")
        self.play_btn.clicked.connect(self._toggle_play)
        row.addWidget(self.play_btn)
        self.media_label = QLabel("")
        self.media_label.setObjectName("caption")
        row.addWidget(self.media_label)
        row.addStretch(1)
        lay.addWidget(self.video)
        lay.addLayout(row)

        frames_head = QLabel("검수 프레임 — 타이틀 · 밝은 · 어두운 · 모션 · 마지막")
        frames_head.setObjectName("sectionTitle")
        lay.addWidget(frames_head)
        self.frames_row = QHBoxLayout()
        holder = QWidget()
        holder.setLayout(self.frames_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setFixedHeight(theme.THUMB_H + 72)   # 캡션·여백까지 — 세로 스크롤바가 안 뜨게
        lay.addWidget(scroll)

        # 직전 영상 타이틀 프레임 쌍 — "스팅어·타이틀은 영상마다 같아야 한다" 눈검수 재료
        self.pair_head = QLabel("타이틀 일관성 — 직전 영상과 나란히")
        self.pair_head.setObjectName("sectionTitle")
        self.pair_head.hide()
        lay.addWidget(self.pair_head)
        self.pair_row = QHBoxLayout()
        pair_holder = QWidget()
        pair_holder.setLayout(self.pair_row)
        lay.addWidget(pair_holder)

        sub_head = QLabel("자막 대조")
        sub_head.setObjectName("sectionTitle")
        lay.addWidget(sub_head)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setWordWrap(True)
        lay.addWidget(self.subtitle_label)

        check_head = QLabel("검수 체크리스트")
        check_head.setObjectName("sectionTitle")
        lay.addWidget(check_head)
        check_desc = QLabel("위 프레임을 실제로 눈으로 본 뒤 표시하세요. "
                            "다섯 항목이 모두 차야 배포로 넘어갑니다.")
        check_desc.setObjectName("caption")
        lay.addWidget(check_desc)
        self.checks: dict[str, QCheckBox] = {}
        check_row = QHBoxLayout()
        for item in CHECK_ITEMS:
            cb = QCheckBox(item)
            cb.toggled.connect(lambda on, k=item: self._on_check(k, on))
            self.checks[item] = cb
            check_row.addWidget(cb)
        check_row.addStretch(1)
        lay.addLayout(check_row)
        self.check_note = QLabel("")
        self.check_note.setObjectName("caption")
        lay.addWidget(self.check_note)

        silence_head = QLabel("무음 리포트")
        silence_head.setObjectName("sectionTitle")
        lay.addWidget(silence_head)
        self.silence_label = QLabel("")
        self.silence_label.setObjectName("caption")
        lay.addWidget(self.silence_label)
        lay.addStretch(1)
        return outer

    # ── 로드 ────────────────────────────────────────────────────────────────
    def load(self, eid: str) -> None:
        self.eid = eid
        self.title.setText(eid)
        self.error.hide()
        self._studio = self._make_studio()
        studio = self._studio

        def get():
            body = studio.get_episode(eid)
            cons = studio.consistency(eid)
            budget = ""
            if cons.get("course"):
                try:
                    budget = studio.get_course(cons["course"])["course"].get(
                        "episodeLength", "")
                except Exception:  # noqa: BLE001 — 예산 미상은 기본값으로
                    budget = ""
            return body, cons, budget

        run_bg(get, done=self._fill, fail=self._fail)
        # inspect 는 최대 60초(엔진 subprocess) — 별도 워커로 늦게 도착해도 무방
        run_bg(lambda: studio.inspect(eid), done=self._fill_inspect,
               fail=lambda _e: self._fill_inspect({}))
        # 에이전트 게이트 — 키 없으면 버튼 비활성 + 사유 툴팁 (05: 메뉴 통째로 비활성)
        run_bg(studio.agent_status, done=self._fill_agent, fail=lambda _e: None)

    def _fill_agent(self, gate: dict) -> None:
        self.ai_review_btn.setEnabled(bool(gate.get("enabled")))
        self.ai_review_btn.setToolTip(
            gate.get("reason") or f"완성본을 새 세션이 채점합니다 "
                                  f"({gate.get('provider')} · {gate.get('models', {}).get('review')})")

    def _ai_review(self) -> None:
        """AI 평가 — 같은 잡 큐·같은 진행 로그 (05: kind=agent)."""
        eid, studio = self.eid, self._studio
        self.log.clear()
        self.log.show()
        self.state_chip.setText("AI 평가 제출 중…")
        self.state_chip.setProperty("chip", "run")
        self._repolish(self.state_chip)
        self.state_chip.show()
        self._set_building(True)

        def submitted(out):
            self._job_id = out["jobId"]
            self.job_started.emit(self._job_id)
            self._pump = JobEventPump(studio, self._job_id)
            self._pump.event.connect(self._on_event, Qt.QueuedConnection)
            self._pump.finished.connect(lambda: self._set_building(False),
                                        Qt.QueuedConnection)
            self._pump.start()

        run_bg(lambda: studio.agent_submit("review", eid, {"episodeId": eid}),
               done=submitted, fail=lambda e: (self._fail(e), self._set_building(False)))

    def _fail(self, err) -> None:
        self.error.setText(error_text(err))
        self.error.show()

    def _fill(self, result) -> None:
        body, cons, budget_text = result
        self._budget_text = budget_text
        self._etag = body["etag"]
        self.stale.setVisible(bool(body.get("stale")))
        problems = cons.get("problems") or []
        self.consistency_chip.setText(f"프로젝트 일관성 {len(problems)}건 어긋남: "
                                      + " · ".join(problems[:2]))
        self.consistency_chip.setVisible(bool(problems))
        self.sync_btn.setVisible(bool(problems))
        self._title_pair = cons.get("titlePair")

        self.clip_tab.load(self.eid, body["scenes"], body["etag"], {}, budget_text)
        self.plan_tab.load(self.eid, budget_text)
        finals = body.get("final") or []
        self.not_built.setVisible(not finals)
        self.review_body.setVisible(bool(finals))
        self.video.hide()          # 영상을 바꾸면 영상은 다시 접는다
        self.play_btn.setText("▶ 재생")
        if finals:
            mp4 = OUT_ROOT / self.eid / "final" / finals[0]
            self.player.setSource(QUrl.fromLocalFile(str(mp4)))
            self.media_label.setText(finals[0])
            self._load_review()

    def _fill_inspect(self, inspect: dict) -> None:
        self.clip_tab.set_inspect(inspect)

    def _on_tab(self, idx: int) -> None:
        if idx == 3 and self.eid:
            self.deploy_tab.load(self.eid)

    def _on_clip_saved(self) -> None:
        """저장 후 파생 상태(stale·일관성)만 갱신 — 편집 중 내용은 건드리지 않는다."""
        eid, studio = self.eid, self._studio

        def get():
            return studio.get_episode(eid), studio.consistency(eid)

        def fill(result):
            body, cons = result
            self._etag = body["etag"]  # 저장·빌드 후 최신 etag 유지 (sync-course 용)
            self.stale.setVisible(bool(body.get("stale")))
            problems = cons.get("problems") or []
            self.consistency_chip.setText(f"프로젝트 일관성 {len(problems)}건 어긋남: "
                                          + " · ".join(problems[:2]))
            self.consistency_chip.setVisible(bool(problems))
            self.sync_btn.setVisible(bool(problems))
            self._title_pair = cons.get("titlePair")
            finals = body.get("final") or []
            self.not_built.setVisible(not finals)
            self.review_body.setVisible(bool(finals))
            if finals:
                mp4 = OUT_ROOT / self.eid / "final" / finals[0]
                self.player.setSource(QUrl.fromLocalFile(str(mp4)))
                self.media_label.setText(finals[0])

        run_bg(get, done=fill, fail=self._fail)

    def _sync_course(self) -> None:
        eid, studio = self.eid, self._studio
        etag = getattr(self, "_etag", None)
        run_bg(lambda: studio.sync_course(eid, etag),
               done=lambda _o: self.load(eid), fail=self._fail)

    # ── 검수 자료 ───────────────────────────────────────────────────────────
    def _load_review(self) -> None:
        eid, studio = self.eid, self._studio

        def get():
            return (studio.frames(eid, preset="review")["frames"],
                    studio.silence(eid), studio.subtitle_check(eid),
                    studio.get_review(eid))

        def fill(result):
            frames, silence, subtitle, checklist = result
            while self.frames_row.count():
                item = self.frames_row.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for f in frames:
                cell = QVBoxLayout()
                img = QLabel()
                img.setPixmap(QPixmap(f["path"]).scaledToHeight(theme.THUMB_H, Qt.SmoothTransformation))
                cap = QLabel(f"{KIND_LABEL.get(f.get('kind'), '')} {f['t']}s")
                cap.setObjectName("caption")
                cap.setAlignment(Qt.AlignCenter)
                cell.addWidget(img)
                cell.addWidget(cap)
                w = QWidget()
                w.setLayout(cell)
                self.frames_row.addWidget(w)
            self.frames_row.addStretch(1)

            n_suspect = len(silence["suspect"])
            self.silence_label.setText(
                f"총 {len(silence['silences'])}건 · {silence['total']}초 — "
                + ("전부 문장 호흡 (정상)" if not n_suspect
                   else f"클립 끝 의심 {n_suspect}건 — BGM 죽음·전환 공백을 확인하세요"))
            if subtitle.get("ok"):
                self.subtitle_label.setText(
                    f"자막이 대본과 한 글자도 다르지 않습니다 "
                    f"({subtitle.get('chars', 0):,}자) ✓")
                self.subtitle_label.setStyleSheet(f"color: {theme.SUCCESS};")
            else:
                self.subtitle_label.setText(
                    f"자막이 대본과 다릅니다 — {subtitle.get('reason', '')}\n"
                    f"srt: …{subtitle.get('srtAround', '')}…\n"
                    f"대본: …{subtitle.get('scriptAround', '')}…")
                self.subtitle_label.setStyleSheet(f"color: {theme.DANGER};")
            self._checklist = checklist or {"items": {}}
            # 저장된 값을 되그리는 것뿐이다 — 막지 않으면 setChecked 가 toggled 를 쏘고
            # _on_check 가 방금 읽은 값을 그대로 되쓴다 (08 §7)
            for k, cb in self.checks.items():
                cb.blockSignals(True)
                cb.setChecked(bool(self._checklist.get("items", {}).get(k)))
                cb.blockSignals(False)
            self._sync_check_note()
            self._fill_title_pair()

        def fail(err):
            if not isinstance(err, NotBuilt):
                self._fail(err)

        run_bg(get, done=fill, fail=fail)

    def _fill_title_pair(self) -> None:
        while self.pair_row.count():
            item = self.pair_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        pair = getattr(self, "_title_pair", None)
        has = bool(pair and pair.get("prev") and pair.get("current"))
        self.pair_head.setVisible(has)
        if not has:
            return
        for path, caption in ((pair["prev"], pair["prevId"]), (pair["current"], "이번 영상")):
            cell = QVBoxLayout()
            img = QLabel()
            img.setPixmap(QPixmap(path).scaledToHeight(120, Qt.SmoothTransformation))
            cap = QLabel(caption)
            cap.setObjectName("caption")
            cap.setAlignment(Qt.AlignCenter)
            cell.addWidget(img)
            cell.addWidget(cap)
            w = QWidget()
            w.setLayout(cell)
            self.pair_row.addWidget(w)
        self.pair_row.addStretch(1)

    def _sync_check_note(self) -> None:
        """남은 항목 수를 말한다 — 체크박스만으로는 '다 봤는지'가 안 읽힌다 (09 G8)."""
        done = sum(1 for k in CHECK_ITEMS
                   if self._checklist.get("items", {}).get(k))
        stamp = self._checklist.get("updatedAt", "")
        if done == len(CHECK_ITEMS):
            self.check_note.setText(f"검수 완료 — ⑦ 배포 탭으로 넘어가세요"
                                    + (f" (기록 {stamp})" if stamp else ""))
            self.check_note.setStyleSheet(f"color: {theme.SUCCESS};")
        else:
            self.check_note.setText(f"{done} / {len(CHECK_ITEMS)} 확인"
                                    + (f" · 기록 {stamp}" if stamp else ""))
            self.check_note.setStyleSheet("")

    def _on_check(self, key: str, on: bool) -> None:
        items = dict(self._checklist.get("items", {}))
        items[key] = on
        eid, studio = self.eid, self._studio
        run_bg(lambda: studio.put_review(eid, {"items": items,
                                               "note": self._checklist.get("note", "")}),
               done=lambda out: (self._checklist.update(out),
                                 self._sync_check_note()),
               fail=self._fail)

    # ── 재생 ────────────────────────────────────────────────────────────────
    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶ 재생")
        else:
            self.video.show()   # 여기서 처음 펼친다 (09 G1)
            self.player.play()
            self.play_btn.setText("일시정지")

    # ── 빌드 ────────────────────────────────────────────────────────────────
    def _build(self, only: str | None) -> None:
        eid, studio = self.eid, self._studio
        self.log.clear()
        self.log.show()
        self.state_chip.setText("제출 중…")
        self.state_chip.setProperty("chip", "run")
        self._repolish(self.state_chip)
        self.state_chip.show()
        self._set_building(True)

        def submitted(out):
            self._job_id = out["jobId"]
            self.job_started.emit(self._job_id)
            self._pump = JobEventPump(studio, self._job_id)
            self._pump.event.connect(self._on_event, Qt.QueuedConnection)
            self._pump.finished.connect(lambda: self._set_building(False),
                                        Qt.QueuedConnection)
            self._pump.start()

        run_bg(lambda: studio.submit_build(eid, only=only),
               done=submitted, fail=lambda e: (self._fail(e), self._set_building(False)))

    def _cancel(self) -> None:
        if self._job_id and self._studio:
            jid = self._job_id
            run_bg(lambda: self._studio.cancel_job(jid), fail=self._fail)

    def _set_building(self, on: bool) -> None:
        for b in (self.build_btn, self.tts_only_btn, self.compose_btn, self.ai_review_btn):
            b.setEnabled(not on)
        self.cancel_btn.setVisible(on)
        if not on and self.eid:
            # 편집 중인 ⑤ 를 덮지 않는다 — 파생 상태·검수 자료·TTS 실측만 갱신
            # (구 웹 구현은 여기서 에디터를 리마운트해 미저장 편집이 사라졌다)
            self._on_clip_saved()
            self._load_review()
            eid, studio = self.eid, self._studio
            run_bg(lambda: studio.inspect(eid), done=self._fill_inspect,
                   fail=lambda _e: None)

    def _on_event(self, ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "state":
            state = ev["state"]
            self.state_chip.setText(state)
            self.state_chip.setProperty(
                "chip", {"done": "ok", "failed": "err", "blocked": "err",
                         "canceled": "info"}.get(state, "run"))
            self._repolish(self.state_chip)
        elif kind in ("phase", "step", "log"):
            line = ev.get("line", "")
            if line:
                self.log.appendPlainText(line)
        elif kind == "preflight":
            findings = ev.get("findings", [])
            self.log.appendPlainText(f"[0] 사전 점검 — {len(findings)}건"
                                     + ("" if not findings else f": {findings[:3]}"))
        elif kind == "verify":
            self.log.appendPlainText(f"검수 자료 생성 — 프레임 {len(ev.get('frames', []))}장"
                                     f" · 무음 {ev.get('silences', 0)}건")

    @staticmethod
    def _repolish(w: QWidget) -> None:
        w.style().unpolish(w)
        w.style().polish(w)
