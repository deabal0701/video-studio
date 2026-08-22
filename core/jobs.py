"""jobs — 빌드 잡 큐 (D8: 처음부터 잡 큐. 로컬은 in-process 동시 2).

상태머신 (04_api): queued → preflight → running(tts→record?→compose) → verifying → done
                        └ blocked(사전점검 치명) · failed(로그 보존) · canceled

동시성 정책 (04_api 표):
  · 같은 회차(episodeId) 동시 빌드 금지 — 큐 키 직렬화 (+ 엔진 .lock 이중 방어)
  · 화면 녹화 잡(scenes[] 비어있지 않음)은 전역 직렬 — 앱 상태 오염 방지
  · 전역 동시 상한 2 (Chromium+ffmpeg 부하)

구현: in-process 스레드 워커. 이벤트는 잡별 리스트에 쌓고(Condition 브로드캐스트)
구독자는 subscribe() 제너레이터로 받는다 — app/bridge 의 JobEventPump 가 Qt Signal 로 릴레이한다.
상용 전환 시 이 클래스만 큐 서비스+워커 구현으로 교체한다 (인터페이스 유지 — D8).
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from . import engine_io


class JobState(str, Enum):
    QUEUED = "queued"
    PREFLIGHT = "preflight"
    RUNNING = "running"
    VERIFYING = "verifying"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELED = "canceled"


MAX_CONCURRENCY = 2  # Chromium+ffmpeg 부하 — 설정 가능, 상용은 워커 수
MAX_FINISHED = 100   # 종료 잡 보존 상한 — 무한 누적 방지 (07 결함 6. 이벤트도 함께 버려진다)

TERMINAL = {JobState.DONE, JobState.BLOCKED, JobState.FAILED, JobState.CANCELED}


@dataclass
class Job:
    id: str
    episode_id: str
    scenes_file: Path
    only: str | None = None
    variant: str | None = None
    state: JobState = JobState.QUEUED
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    cancel_requested: bool = False
    proc: Any = None  # 실행 중인 엔진 Popen — 취소용
    kind: str = "build"          # build | agent (05_agent: 에이전트도 같은 잡 큐)
    work: Any = None             # kind=agent 의 이벤트 제너레이터 팩토리


def default_verifier(episode_id: str) -> dict[str, Any]:
    """verifying 단계 — 완료 직후 검수 프레임 4+1종·무음 리포트를 자동 생성한다.

    사람이 검수 화면을 열면 이미 준비돼 있게 ("빌드가 도는 동안이 검증 시간" 규약의 자동화).
    """
    from . import media_ops

    frames = media_ops.review_frames(episode_id)
    silences = media_ops.detect_silence(episode_id)
    return {"frames": [f["file"] for f in frames],
            "silences": len(silences),
            "suspectSilences": sum(1 for s in silences if s["cause"] == "clip-end")}


class JobQueue:
    """빌드 잡 큐. runner·preflight·verifier 를 주입할 수 있어 엔진 없이 단위 테스트가 된다."""

    def __init__(self, *, max_concurrency: int = MAX_CONCURRENCY,
                 runner: Callable[..., Iterator[engine_io.BuildEvent]] | None = None,
                 preflight: Callable[[Path], dict] | None = None,
                 verifier: Callable[[str], dict[str, Any]] | None = default_verifier,
                 listener: Callable[[Job, dict[str, Any]], None] | None = None):
        self._runner = runner or engine_io.build_stream
        self._preflight = preflight or engine_io.inspect
        self._verifier = verifier
        self._listener = listener  # 잡 이벤트 릴레이 훅 (app/bridge.Bridge → Qt Signal)
        self._max = max_concurrency
        self._lock = threading.Condition()
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []          # FIFO 대기열
        self._active: set[str] = set()       # 실행 중 job id
        self._active_episodes: set[str] = set()
        self._seq = itertools.count(1)

    # ── 제출·조회 ────────────────────────────────────────────────────────────
    def submit(self, episode_id: str, scenes_file: Path, *,
               only: str | None = None, variant: str | None = None) -> Job:
        with self._lock:
            job = Job(id=f"j{next(self._seq)}", episode_id=episode_id,
                      scenes_file=Path(scenes_file), only=only, variant=variant)
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._pump()
            return job

    def submit_agent(self, episode_id: str, work) -> Job:
        """에이전트 잡 (05_agent: 같은 큐·같은 SSE·같은 취소). 회차 직렬화가 편집 잠금을 겸한다."""
        with self._lock:
            job = Job(id=f"j{next(self._seq)}", episode_id=episode_id,
                      scenes_file=Path(episode_id), kind="agent", work=work)
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._pump()
            return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return [self._jobs[j] for j in self._order]

    def cancel(self, job_id: str) -> bool:
        """대기 중이면 즉시 취소, 실행 중이면 SIGTERM→(5초 뒤)SIGKILL.

        엔진 .lock 은 SIGTERM 정리 루틴이 스스로 풀고, 못 풀어도 다음 실행이 이어받는다 (04_api).
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            if job.state is JobState.QUEUED:
                self._set(job, JobState.CANCELED)
                return True
            if job.state not in (JobState.PREFLIGHT, JobState.RUNNING):
                return False  # verifying 은 곧 done — 그 시점 취소는 의미가 없다
            job.cancel_requested = True
            proc = job.proc
        if proc is not None:
            proc.terminate()
            threading.Timer(5.0, proc.kill).start()
        return True

    # ── 이벤트 구독 (SSE 릴레이) ─────────────────────────────────────────────
    def subscribe(self, job_id: str) -> Iterator[dict[str, Any]]:
        """지나간 이벤트부터 재생하고, 종료 상태까지 블로킹 스트림."""
        sent = 0
        while True:
            with self._lock:
                job = self._jobs[job_id]
                while sent >= len(job.events) and job.state not in TERMINAL:
                    self._lock.wait(timeout=1.0)
                chunk = job.events[sent:]
                sent += len(chunk)
                finished = job.state in TERMINAL and sent >= len(job.events)
            yield from chunk
            if finished:
                return

    # ── 내부 ────────────────────────────────────────────────────────────────
    def _emit(self, job: Job, event: dict[str, Any]) -> None:
        with self._lock:
            job.events.append(event)
            self._lock.notify_all()
        if self._listener is not None:
            try:
                self._listener(job, event)
            except Exception:  # noqa: BLE001 — 알림 실패가 빌드를 죽이면 안 된다
                pass

    def _set(self, job: Job, state: JobState) -> None:
        # 상태 대입과 이벤트 추가를 같은 락 안에서 — 밖에서 대입하면 구독자가 "터미널인데
        # 이벤트는 아직"인 틈을 보고 마지막 이벤트 없이 조기 종료한다 (5-1 실측 레이스)
        event = {"kind": "state", "state": state.value}
        with self._lock:
            job.state = state
            job.events.append(event)
            self._lock.notify_all()
        if self._listener is not None:
            try:
                self._listener(job, event)
            except Exception:  # noqa: BLE001
                pass

    def _can_start(self, job: Job) -> bool:
        return len(self._active) < self._max and job.episode_id not in self._active_episodes

    def _pump(self) -> None:
        """호출 시점에 시작 가능한 대기 잡을 전부 시작한다. self._lock 보유 상태에서 호출."""
        for job_id in self._order:
            job = self._jobs[job_id]
            if job.state is not JobState.QUEUED or not self._can_start(job):
                continue
            self._active.add(job.id)
            self._active_episodes.add(job.episode_id)
            threading.Thread(target=self._run, args=(job,), daemon=True).start()

    def _run_agent(self, job: Job) -> None:
        self._set(job, JobState.RUNNING)
        for ev in job.work():
            self._emit(job, ev)
            if job.cancel_requested:
                self._set(job, JobState.CANCELED)
                return
        self._set(job, JobState.DONE)

    def _run(self, job: Job) -> None:
        try:
            if job.kind == "agent":
                self._run_agent(job)
                return
            # 1. preflight 는 잡의 1단계로 강제 — 치명이면 굽지 않는다 (blocked)
            self._set(job, JobState.PREFLIGHT)
            findings = self._preflight(job.scenes_file.parent).get("preflight", [])
            self._emit(job, {"kind": "preflight", "findings": findings})
            if any(f.get("level") == "error" for f in findings):
                self._set(job, JobState.BLOCKED)
                return
            if job.cancel_requested:
                self._set(job, JobState.CANCELED)
                return
            # 2. 빌드 스트림 릴레이 (on_proc 로 Popen 을 받아 취소에 쓴다)
            self._set(job, JobState.RUNNING)
            for ev in self._runner(job.scenes_file, only=job.only, variant=job.variant,
                                   on_proc=lambda p: setattr(job, "proc", p)):
                self._emit(job, {"kind": ev.kind, "line": ev.line,
                                 "phase": ev.phase, "step": ev.step_id})
            if job.cancel_requested:
                self._set(job, JobState.CANCELED)
                return
            # 3. verifying — 완료 직후 검수 자료 자동 생성. 실패해도 빌드는 done (로그만 남긴다)
            if job.only is None and self._verifier is not None:
                self._set(job, JobState.VERIFYING)
                try:
                    self._emit(job, {"kind": "verify", **self._verifier(job.episode_id)})
                except Exception as err:  # noqa: BLE001
                    self._emit(job, {"kind": "log", "line": f"검수 자동 생성 실패: {err}"})
            self._set(job, JobState.DONE)
        except Exception as err:  # noqa: BLE001 — 로그 보존이 목적
            if job.cancel_requested:
                self._set(job, JobState.CANCELED)
                return
            job.error = str(err)
            self._set(job, JobState.FAILED)
        finally:
            with self._lock:
                self._active.discard(job.id)
                self._active_episodes.discard(job.episode_id)
                self._prune()
                self._pump()
                self._lock.notify_all()

    def _prune(self) -> None:
        """종료 잡을 오래된 것부터 버려 MAX_FINISHED 만 남긴다. self._lock 보유 상태에서 호출."""
        finished = [j for j in self._order if self._jobs[j].state in TERMINAL]
        for job_id in finished[:max(0, len(finished) - MAX_FINISHED)]:
            self._order.remove(job_id)
            del self._jobs[job_id]
