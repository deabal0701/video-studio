"""작업 큐 (03_screens "작업 큐" 행) — 전역 잡 목록·취소·AI 사용량 미터.

동시성 정책을 화면에 적어 둔다 (04_api 표): 같은 영상 직렬 · 전역 동시 2 ·
사전점검 치명이면 굽지 않음. "왜 내 빌드가 기다리는가"를 사람이 읽고 이해하게.
잡 상태 변화는 하단 상태바와 같은 신호(Bridge.job_event)로 받아 자동 갱신한다.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from .. import theme
from ..bridge import error_text, run_bg

STATE_LABEL = {"queued": ("대기", theme.INK_3), "preflight": ("사전점검", theme.WARNING),
               "running": ("진행 중", theme.WARNING), "verifying": ("검수 자료", theme.WARNING),
               "done": ("완료", theme.SUCCESS), "failed": ("실패", theme.DANGER),
               "blocked": ("차단됨", theme.DANGER), "canceled": ("취소됨", theme.INK_3)}
ACTIVE = {"queued", "preflight", "running", "verifying"}


class JobsPage(QWidget):
    open_episode = Signal(str)   # 행 더블클릭 → 해당 영상으로 (28회차 P5·P21)

    def __init__(self, make_studio):
        super().__init__()
        self._make_studio = make_studio
        self._jobs: list[dict] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PAGE_PAD, 24, theme.PAGE_PAD, 24)
        head = QHBoxLayout()
        title = QLabel("작업 큐")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.usage = QLabel("")
        self.usage.setProperty("chip", "info")
        head.addWidget(self.usage)
        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.refresh_btn)
        outer.addLayout(head)
        desc = QLabel("빌드는 동시에 2편까지 돕니다. 같은 영상은 순서대로 하나씩 굽고, "
                      "사전점검에서 치명 결함이 나오면 굽지 않고 멈춥니다.")
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["시각", "작업", "영상", "상태", "메모"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setColumnWidth(0, 80)    # 시각
        self.table.setColumnWidth(1, 90)    # 작업
        self.table.setColumnWidth(2, 340)   # 영상 — 사람 이름이 들어가므로 넉넉히
        self.table.setColumnWidth(3, 100)   # 상태
        # 남는 폭은 **메모(오류 사유)** 가 먹는다. 44회차에 "시각" 열을 0번에 끼워 넣으면서
        # 열 번호가 한 칸씩 밀렸는데 이 줄만 3 그대로라, 넓어진 것은 **상태**("실패" 두 글자)
        # 였고 정작 오류 사유는 "ffmpeg 종료 …"로 잘렸다 (60회차 P6·P13, 캡처에서 발견).
        # 번호 대신 헤더 이름으로 고른다 — 열이 또 늘어도 안 밀린다
        for i in range(self.table.columnCount()):
            if self.table.horizontalHeaderItem(i).text() == "메모":
                self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
                break
        self.table.itemSelectionChanged.connect(self._on_select)
        # 실패한 작업을 보고 "어디서 다시 하지?"가 막히면 안 된다 — 행에서 바로 간다
        self.table.cellDoubleClicked.connect(self._open_row)
        outer.addWidget(self.table, 1)
        go_hint = QLabel("행을 더블클릭하면 해당 영상 화면으로 이동합니다 — 실패한 빌드는 거기서 다시 시도하세요.")
        go_hint.setObjectName("caption")
        outer.addWidget(go_hint)

        row = QHBoxLayout()
        self.cancel_btn = QPushButton("선택한 작업 중단")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        self.result = QLabel("")
        self.result.setObjectName("caption")
        row.addWidget(self.cancel_btn)
        row.addWidget(self.result, 1)
        outer.addLayout(row)

    def refresh(self) -> None:
        studio = self._make_studio()
        # 상태가 바뀔 때마다 조회가 나간다 — 늦게 온 낡은 결과가 최신 표를 되덮지 않게
        # 번호를 매긴다 (59회차 라이브러리와 같은 처방)
        self._req = getattr(self, "_req", 0) + 1
        token = self._req

        def get():
            return studio.jobs(), studio.agent_usage()

        run_bg(get, done=lambda r: self._fill(r, token),
               fail=lambda e: (None if token != self._req
                               else self.result.setText(error_text(e))))

    def _fill(self, result, token: int | None = None) -> None:
        if token is not None and token != getattr(self, "_req", token):
            return   # 낡은 응답
        jobs, usage = result
        self._jobs = jobs
        self.table.setRowCount(len(jobs))
        for i, j in enumerate(jobs):
            label, color = STATE_LABEL.get(j["state"], (j["state"], theme.INK_2))
            state = QTableWidgetItem(label)
            state.setForeground(QColor(color))   # 진행 주황·완료 초록·실패 빨강 (P4)
            # 작업 이름은 사람 말로 — jobId 는 툴팁으로 강등 (P2)
            task = QTableWidgetItem(
                "AI 작업" if j.get("kind") == "agent"
                else {"tts": "TTS만", "compose": "합성만"}.get(j.get("only"), "빌드"))
            task.setToolTip(j["jobId"])
            when = QTableWidgetItem(
                time.strftime("%H:%M:%S", time.localtime(j["createdAt"]))
                if j.get("createdAt") else "")
            # 한 줄에서 "빌드"·"실패"는 한국어인데 영상만 폴더 id 였다 (60회차 P2)
            ep = QTableWidgetItem(j.get("episodeName") or j["episodeId"])
            ep.setToolTip(f"폴더: {j['episodeId']}")
            for col, item in enumerate([when, task, ep,
                                        state, QTableWidgetItem(j.get("error") or "")]):
                self.table.setItem(i, col, item)
        cost = usage.get("totalCostUsd") or 0
        tokens = usage.get("totalTokens") or 0
        parts = [f"AI 사용 {usage.get('count', 0)}회"]
        if tokens:
            parts.append(f"토큰 {tokens:,}")   # D18 HTTP 기록 — 비용 대신 토큰이 미터
        if cost:
            parts.append(f"${cost:.4f}")       # 구 기록의 실측 비용이 있으면 함께
        self.usage.setText(" · ".join(parts)
                           if usage.get("count") else "AI 사용 기록 없음")
        active = sum(1 for j in jobs if j["state"] in ACTIVE)
        summary = (f"진행 중 {active}건 · 전체 {len(jobs)}건" if jobs
                   else "아직 실행한 작업이 없습니다 — 영상 화면에서 [빌드] 를 누르면 여기에 쌓입니다.")
        notice = getattr(self, "_notice", "")
        self._notice = ""
        self.result.setText(f"{notice} · {summary}" if notice else summary)

    def _on_select(self) -> None:
        row = self.table.currentRow()
        ok = 0 <= row < len(self._jobs) and self._jobs[row]["state"] in ACTIVE
        self.cancel_btn.setEnabled(ok)

    def _open_row(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._jobs):
            self.open_episode.emit(self._jobs[row]["episodeId"])

    def _cancel(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._jobs)):
            return
        job = self._jobs[row]
        jid, studio = job["jobId"], self._make_studio()
        # 안내에 jobId 를 쓰면 12회차에 툴팁으로 강등한 은어가 도로 앞에 나온다 —
        # 사람이 부르는 이름으로 말한다 (60회차 P2)
        who = job.get("episodeName") or job["episodeId"]
        # 처리 중 잠금 + 즉시 피드백 (28회차 P18·P19)
        self.cancel_btn.setEnabled(False)
        self.result.setText("중단 요청 중…")

        def done(out: dict) -> None:
            # 안내를 써 놓고 곧바로 refresh 하면 목록 요약이 덮어써 **한 번도 안 보였다**
            # (60회차 P19 — 59회차 라이브러리 '받기' 와 같은 부류). 갱신 한 번까지 싣는다
            self._notice = (f"{who} 중단 요청됨" if out.get("canceled")
                            else f"{who} 는 지금 중단할 수 없는 상태입니다")
            self.refresh()

        run_bg(lambda: studio.cancel_job(jid), done=done,
               fail=lambda e: (self.result.setText(error_text(e)),
                               self._on_select()))

    def on_job_event(self, _job_id: str, _episode_id: str, ev: dict) -> None:
        """상태 변화만 반영 — 로그 줄마다 새로고침하면 표가 떨린다."""
        if ev.get("kind") == "state" and self.isVisible():
            self.refresh()
