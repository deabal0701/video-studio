"""검수 유스케이스 — 빌드 산출물이 있으면 실측, 없으면 NotBuilt 계약을 확인한다."""

from pathlib import Path

import pytest

from core import media_ops
from core.facade import Invalid, NotBuilt, Studio

pytestmark = pytest.mark.usefixtures("fixtures_root")
BUILT = media_ops.final_mp4("hr-basics-01") is not None


def test_frames_requires_preset_or_t(studio):
    with pytest.raises((Invalid, NotBuilt)):
        studio.frames("hr-basics-01")


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_review_frames_4_plus_1(studio):
    body = studio.frames("hr-basics-01", preset="review")
    assert len(body["frames"]) == 5
    for f in body["frames"]:
        assert Path(f["path"]).is_file()  # 캐시 파일 실존 (화면이 이 경로를 직접 연다)


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_silence_report_classified(studio):
    body = studio.silence("hr-basics-01")
    assert body["total"] >= 0
    for s in body["silences"]:
        assert s["cause"] in ("uniform-breath", "clip-end")


def test_consistency_against_course(studio):
    body = studio.consistency("hr-basics-01")
    assert body["course"] == "hr-basics" and body["single"] is False
    # 회차는 루프 파생 bgm 을 쓰므로 course 와 어긋남이 보고되는 것이 정상 (실측 결손)
    assert any("bgm" in p for p in body["problems"])


def test_not_built_episode_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(tmp_path))
    (tmp_path / "solo-01").mkdir()
    (tmp_path / "solo-01" / "scenes.json").write_text('{"id": "solo-01"}', encoding="utf-8")
    with pytest.raises(NotBuilt) as e:
        Studio().frames("solo-01", preset="review")
    assert e.value.code == "not_built"
