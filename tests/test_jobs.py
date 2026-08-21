"""jobs 큐 단위 테스트 — 엔진 없이 runner/preflight 주입으로 검증한다."""

import threading
import time
from pathlib import Path

from core.engine_io import BuildEvent
from core.jobs import JobQueue, JobState


def ok_preflight(_dir: Path) -> dict:
    return {"preflight": []}


def bad_preflight(_dir: Path) -> dict:
    return {"preflight": [{"level": "error", "clip": "x", "msg": "고장"}]}


def make_runner(log, gate: threading.Event | None = None):
    def runner(scenes_file, *, only=None, variant=None, on_proc=None):
        log.append(scenes_file.parent.name)
        if gate:
            gate.wait(timeout=5)
        yield BuildEvent("phase", "[1] TTS", phase=1, title="TTS")
        yield BuildEvent("step", "  · hook 8.90s", step_id="hook", seconds=8.9)
    return runner


def make_queue(**kw):
    kw.setdefault("verifier", lambda _eid: {"frames": [], "silences": 0})
    return JobQueue(**kw)


def wait_state(job, state, timeout=5.0):
    deadline = time.time() + timeout
    while job.state is not state and time.time() < deadline:
        time.sleep(0.01)
    assert job.state is state, f"{job.state} != {state}"


def test_preflight_blocks_fatal(tmp_path):
    q = make_queue(runner=make_runner([]), preflight=bad_preflight)
    job = q.submit("ep-01", tmp_path / "ep-01" / "scenes.json")
    wait_state(job, JobState.BLOCKED)
    kinds = [e["kind"] for e in job.events]
    assert "preflight" in kinds and "phase" not in kinds  # 치명이면 굽지 않는다


def test_success_streams_events_and_subscribe(tmp_path):
    q = make_queue(runner=make_runner([]), preflight=ok_preflight)
    job = q.submit("ep-01", tmp_path / "ep-01" / "scenes.json")
    events = list(q.subscribe(job.id))  # 종료까지 블로킹 — 재생 포함
    assert job.state is JobState.DONE
    assert [e.get("state") for e in events if e["kind"] == "state"] == [
        "preflight", "running", "verifying", "done"]
    assert any(e["kind"] == "verify" for e in events)
    assert any(e["kind"] == "step" and e["step"] == "hook" for e in events)


def test_same_episode_serialized_others_parallel(tmp_path):
    started: list[str] = []
    gate = threading.Event()
    q = make_queue(runner=make_runner(started, gate), preflight=ok_preflight)
    a1 = q.submit("ep-01", tmp_path / "ep-01" / "scenes.json")
    a2 = q.submit("ep-01", tmp_path / "ep-01" / "scenes.json")  # 같은 회차 — 대기해야 함
    b = q.submit("ep-02", tmp_path / "ep-02" / "scenes.json")   # 다른 회차 — 병렬 허용
    deadline = time.time() + 5
    while len(started) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert sorted(started) == ["ep-01", "ep-02"]  # a2 는 아직 시작 전
    assert a2.state is JobState.QUEUED
    gate.set()
    wait_state(a1, JobState.DONE)
    wait_state(a2, JobState.DONE)
    wait_state(b, JobState.DONE)
    assert started.count("ep-01") == 2


def test_cancel_queued(tmp_path):
    gate = threading.Event()
    q = make_queue(max_concurrency=1, runner=make_runner([], gate), preflight=ok_preflight)
    running = q.submit("ep-01", tmp_path / "ep-01" / "scenes.json")
    waiting = q.submit("ep-02", tmp_path / "ep-02" / "scenes.json")
    assert q.cancel(waiting.id) is True
    gate.set()
    wait_state(running, JobState.DONE)
    assert waiting.state is JobState.CANCELED
    assert q.cancel(running.id) is False  # 종료 잡은 취소 불가


def test_cancel_running(tmp_path):
    """실행 중 취소 — cancel_requested 가 서면 완료돼도 done 이 아니라 canceled 로 끝난다."""
    gate = threading.Event()
    q = make_queue(runner=make_runner([], gate), preflight=ok_preflight)
    job = q.submit("ep-01", tmp_path / "ep-01" / "scenes.json")
    wait_state(job, JobState.RUNNING)
    assert q.cancel(job.id) is True
    gate.set()
    wait_state(job, JobState.CANCELED)
    assert not any(e["kind"] == "verify" for e in job.events)  # 취소 잡은 검수 생성 안 함
