"""api 라우터 테스트 — 픽스처를 프로젝트 루트로 물려 읽기 전용 콘솔 계약을 검증한다.

빌드 제출은 가짜 runner 를 주입한 JobQueue 로 — 테스트가 엔진을 돌리지 않는다.
"""

import time

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR
from core.engine_io import BuildEvent
from core.jobs import JobQueue, JobState
from api import deps
from api.main import app


@pytest.fixture(autouse=True)
def fixture_root(monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))


@pytest.fixture
def fake_queue():
    def runner(scenes_file, *, only=None, variant=None, on_proc=None):
        yield BuildEvent("phase", "[1] TTS", phase=1, title="TTS")
        yield BuildEvent("step", "  · hook 8.90s", step_id="hook", seconds=8.9)

    q = JobQueue(runner=runner, preflight=lambda _d: {"preflight": []},
                 verifier=lambda _eid: {"frames": [], "silences": 0})
    app.dependency_overrides[deps.job_queue] = lambda: q
    yield q
    app.dependency_overrides.clear()


client = TestClient(app)


def test_list_courses():
    body = client.get("/api/courses").json()
    hr = next(c for c in body if c["id"] == "hr-basics")
    assert hr["title"] == "인사 기본개념 강좌"
    assert hr["episodeCount"] == 6 and hr["scaffolded"] == 1


def test_get_course_and_board():
    body = client.get("/api/courses/hr-basics").json()
    assert body["course"]["course"] == "hr-basics" and body["etag"]
    assert body["episodes"]["hr-basics-01"]["state"] in ("wip", "done")
    assert body["episodes"]["hr-basics-02"]["state"] == "empty"  # 커리큘럼엔 있고 폴더는 없음
    board = client.get("/api/courses/hr-basics/episodes").json()
    assert len(board) == 6


def test_get_episode_and_plan():
    body = client.get("/api/episodes/hr-basics-01").json()
    assert body["scenes"]["id"] == "hr-basics-01" and body["etag"]
    assert client.get("/api/episodes/hr-basics-01/plan").status_code == 200
    assert client.get("/api/episodes/없는회차").status_code == 404


def test_build_submit_and_job_states(fake_queue):
    job_id = client.post("/api/episodes/hr-basics-01/build", json={}).json()["jobId"]
    deadline = time.time() + 5
    while time.time() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()["state"]
        if state == JobState.DONE.value:
            break
        time.sleep(0.01)
    assert state == "done"
    assert any(j["jobId"] == job_id for j in client.get("/api/jobs").json())


def test_sse_stream_replays_to_done(fake_queue):
    job_id = client.post("/api/episodes/hr-basics-01/build", json={}).json()["jobId"]
    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/events") as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if events and events[-1] in ("done", "failed"):
                break
    assert events[-1] == "done"
    assert "progress" in events


def test_media_serving_and_traversal_guard():
    r = client.get("/api/media/hr-basics-01/final/hr-basics-01-16x9.srt")
    assert r.status_code in (200, 404)  # 빌드 산출물이 있으면 200 (엔진 out/ 은 파생물)
    assert client.get("/api/media/hr-basics-01/..%2F..%2Fsecret").status_code in (403, 404)
