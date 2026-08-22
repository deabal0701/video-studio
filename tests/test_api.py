"""facade 조회·빌드 계약 (구 api 라우터 테스트 — 5-2 에서 Studio 직호출로 전환).

빌드 제출은 가짜 runner 를 주입한 JobQueue 로 — 테스트가 엔진을 돌리지 않는다.
"""

import time

import pytest

from core.engine_io import BuildEvent
from core.facade import Forbidden, NotFound, Studio
from core.jobs import JobQueue, JobState

pytestmark = pytest.mark.usefixtures("fixtures_root")


@pytest.fixture
def fake_studio() -> Studio:
    def runner(scenes_file, *, only=None, variant=None, on_proc=None):
        yield BuildEvent("phase", "[1] TTS", phase=1, title="TTS")
        yield BuildEvent("step", "  · hook 8.90s", step_id="hook", seconds=8.9)

    q = JobQueue(runner=runner, preflight=lambda _d: {"preflight": []},
                 verifier=lambda _eid: {"frames": [], "silences": 0})
    return Studio(queue=q)


def test_list_courses(studio):
    body = studio.list_courses()
    hr = next(c for c in body if c["id"] == "hr-basics")
    assert hr["title"] == "인사 기본개념 강좌"
    assert hr["episodeCount"] == 6 and hr["scaffolded"] == 1


def test_get_course_and_board(studio):
    body = studio.get_course("hr-basics")
    assert body["course"]["course"] == "hr-basics" and body["etag"]
    assert body["episodes"]["hr-basics-01"]["state"] in ("wip", "done")
    assert body["episodes"]["hr-basics-02"]["state"] == "empty"  # 커리큘럼엔 있고 폴더는 없음
    assert len(studio.course_board("hr-basics")) == 6


def test_get_episode_and_plan(studio):
    body = studio.get_episode("hr-basics-01")
    assert body["scenes"]["id"] == "hr-basics-01" and body["etag"]
    assert studio.get_plan("hr-basics-01")["markdown"]
    with pytest.raises(NotFound):
        studio.get_episode("없는회차")


def test_build_submit_and_job_states(fake_studio):
    job_id = fake_studio.submit_build("hr-basics-01")["jobId"]
    deadline = time.time() + 5
    while time.time() < deadline:
        state = fake_studio.job(job_id)["state"]
        if state == JobState.DONE.value:
            break
        time.sleep(0.01)
    assert state == "done"
    assert any(j["jobId"] == job_id for j in fake_studio.jobs())


def test_job_events_replays_to_done(fake_studio):
    """구 SSE 계약 — 이벤트 원천(job_events)이 재생 포함·종료까지 블로킹."""
    job_id = fake_studio.submit_build("hr-basics-01")["jobId"]
    events = list(fake_studio.job_events(job_id))
    states = [e["state"] for e in events if e["kind"] == "state"]
    assert states[-1] == "done"
    assert any(e["kind"] == "phase" for e in events)   # 진행(progress) 재료
    assert any(e["kind"] == "step" and e["step"] == "hook" for e in events)


def test_media_path_and_traversal_guard(studio):
    try:
        p = studio.media_path("hr-basics-01", "final/hr-basics-01-16x9.srt")
        assert p.is_file()          # 빌드 산출물이 있으면 실파일 (엔진 out/ 은 파생물)
    except NotFound:
        pass                        # 산출물 없음도 계약상 유효
    with pytest.raises((Forbidden, NotFound)):
        studio.media_path("hr-basics-01", "../../secret")
