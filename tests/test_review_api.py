"""검수 API 테스트 — 빌드 산출물(engine/out)이 있으면 실측, 없으면 409 계약을 확인한다."""

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR, media_ops
from api.main import app


@pytest.fixture(autouse=True)
def fixture_root(monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))


client = TestClient(app)
BUILT = media_ops.final_mp4("hr-basics-01") is not None


def test_frames_requires_preset_or_t():
    assert client.get("/api/episodes/hr-basics-01/frames").status_code in (409, 422)


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_review_frames_4_plus_1():
    body = client.get("/api/episodes/hr-basics-01/frames", params={"preset": "review"}).json()
    assert len(body["frames"]) == 5
    for f in body["frames"]:
        assert client.get(f["url"]).status_code == 200  # 캐시 파일이 미디어 서빙으로 나온다


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_silence_report_classified():
    body = client.get("/api/episodes/hr-basics-01/silence").json()
    assert body["total"] >= 0
    for s in body["silences"]:
        assert s["cause"] in ("uniform-breath", "clip-end")


def test_consistency_against_course():
    body = client.get("/api/episodes/hr-basics-01/consistency").json()
    assert body["course"] == "hr-basics" and body["single"] is False
    # 회차는 루프 파생 bgm 을 쓰므로 course 와 어긋남이 보고되는 것이 정상 (실측 결손)
    assert any("bgm" in p for p in body["problems"])


def test_not_built_episode_returns_409(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(tmp_path))
    (tmp_path / "solo-01").mkdir()
    (tmp_path / "solo-01" / "scenes.json").write_text('{"id": "solo-01"}', encoding="utf-8")
    r = client.get("/api/episodes/solo-01/frames", params={"preset": "review"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_built"
