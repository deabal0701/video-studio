"""4단계 — 키 게이트·잡 큐 통합·사용량 미터. SDK 는 query_fn 주입으로 대체(키 불요)."""

import time

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR
from core.agents import runner
from core.jobs import JobQueue, JobState
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_key(monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))
    monkeypatch.setattr(runner, "USAGE_FILE", tmp_path / "usage.jsonl")
    # 개발 머신의 .env(실키·모델 오버라이드)와 격리 — 테스트는 프로세스 환경변수만 본다
    monkeypatch.setattr(runner, "_env_value", lambda name: os.environ.get(name) or None)
    for k in ("ANTHROPIC_API_KEY", "AGENT_MODEL_DRAFT",
              "AGENT_MODEL_DIAGRAM", "AGENT_MODEL_REVIEW"):
        monkeypatch.delenv(k, raising=False)


def test_no_key_disables_agent_menu():
    """키 없으면 에이전트만 비활성 — 나머지 앱은 정상 (수용 기준 절반)."""
    body = client.get("/api/agent/status").json()
    assert body["enabled"] is False and "ANTHROPIC_API_KEY" in body["reason"]
    # 작업별 모델 (05_agent: 초안·평가 Opus 계열 · 도식 Sonnet 급)
    assert body["models"] == {"draft": "claude-opus-5", "diagram": "claude-sonnet-5",
                              "review": "claude-opus-5"}
    r = client.post("/api/agent/review", json={"episodeId": "hr-basics-01"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "agent_disabled"
    # 키 없이도 조회·검증은 그대로 동작
    assert client.get("/api/courses").status_code == 200
    assert client.get("/api/agent/usage").json()["count"] == 0


def test_agent_job_runs_in_queue(monkeypatch, tmp_path):
    """가짜 query_fn 으로 에이전트 잡이 큐에서 돌고 SSE 이벤트·사용량이 남는다."""
    async def fake_query(kind, episode_id, payload, queue):
        await queue.put({"kind": "log", "line": "대본을 읽는다"})
        await queue.put({"kind": "log", "line": "평가를 쓴다"})
        return {"costUsd": 0.1234, "turns": 7}

    work = runner.make_agent_work("review", "hr-basics-01", {}, FIXTURES_DIR,
                                  query_fn=fake_query)
    q = JobQueue(runner=None, preflight=lambda d: {"preflight": []}, verifier=None)
    job = q.submit_agent("hr-basics-01", work)
    deadline = time.time() + 10
    while job.state not in (JobState.DONE, JobState.FAILED) and time.time() < deadline:
        time.sleep(0.05)
    assert job.state is JobState.DONE, job.error
    lines = [e.get("line", "") for e in job.events if e["kind"] == "log"]
    assert any("대본을 읽는다" in l for l in lines)
    assert any("완료" in l and "$0.1234" in l for l in lines)
    # 사용량 미터 적산
    usage = runner.usage_summary()
    assert usage["count"] == 1 and usage["totalCostUsd"] == 0.1234


def test_agent_api_submits_when_enabled(monkeypatch):
    async def fake_query(kind, episode_id, payload, queue):
        await queue.put({"kind": "log", "line": f"{kind} ok"})
        return {"costUsd": 0.0}

    from core import agents as agents_pkg
    from api.routers import agent as agent_router

    monkeypatch.setattr(agents_pkg, "agent_enabled", lambda: {"enabled": True})
    monkeypatch.setattr(
        agents_pkg, "make_agent_work",
        lambda kind, eid, payload, root: runner.make_agent_work(
            kind, eid, payload, root, query_fn=fake_query))

    r = client.post("/api/agent/draft", json={"episodeId": "hr-basics-01", "brief": "테스트"})
    assert r.status_code == 200
    job_id = r.json()["jobId"]
    deadline = time.time() + 10
    while time.time() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()["state"]
        if state in ("done", "failed"):
            break
        time.sleep(0.05)
    assert state == "done"


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        runner.make_agent_work("hack", "x", {}, FIXTURES_DIR)


def test_task_model_env_override(monkeypatch):
    assert runner.task_model("diagram") == "claude-sonnet-5"
    monkeypatch.setenv("AGENT_MODEL_DIAGRAM", "claude-haiku-4-5-20251001")
    assert runner.task_model("diagram") == "claude-haiku-4-5-20251001"
    assert runner.task_model("draft") == "claude-opus-5"  # 다른 작업은 그대로
