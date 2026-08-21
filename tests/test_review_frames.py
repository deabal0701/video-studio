"""검수 프레임 명암 선별·타이틀 시각·직전 회차 쌍."""

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR, media_ops
from api.main import app

client = TestClient(app)
EP = FIXTURES_DIR / "hr-basics-01"
BUILT = media_ops.final_mp4("hr-basics-01") is not None


@pytest.fixture(autouse=True)
def fixture_root(monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))


def test_clip_start_times_accumulate():
    starts = media_ops.clip_start_times(EP)
    assert starts["broll"] == 0.0
    assert starts["title"] == pytest.approx(2.0)   # broll 2.0s 고정 뒤
    ids = list(starts)
    assert all(starts[a] <= starts[b] for a, b in zip(ids, ids[1:]))  # 단조 증가


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_review_frames_kinds_and_brightness():
    frames = media_ops.review_frames("hr-basics-01", EP)
    kinds = {f["kind"]: f for f in frames}
    assert set(kinds) == {"title", "bright", "dark", "motion", "last"}
    # 타이틀 프레임은 title 클립 구간 안 (시작 +1.2s)
    starts = media_ops.clip_start_times(EP)
    assert starts["title"] < kinds["title"]["t"] < starts["hook"]
    # 밝은/어두운은 실측 — 두 지점이 다르다
    assert kinds["bright"]["t"] != kinds["dark"]["t"]


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_consistency_title_pair_shape():
    body = client.get("/api/episodes/hr-basics-01/consistency").json()
    # 1강은 직전 회차(0강)가 없다 — 쌍 없음이 정답
    assert body["titlePair"] is None
    # 프레임 API 는 kind 라벨을 싣는다
    frames = client.get("/api/episodes/hr-basics-01/frames?preset=review").json()["frames"]
    assert {f["kind"] for f in frames} == {"title", "bright", "dark", "motion", "last"}
