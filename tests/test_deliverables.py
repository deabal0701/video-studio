"""3D — 챕터(junction 루트)·자막 대조·검수 기록·배포 산출물·plan 라운드트립."""

import pytest

from core import FIXTURES_DIR
from core.facade import EtagMismatch

BUILT = (FIXTURES_DIR.parent.parent / "engine" / "out" / "hr-basics-01" / "final").exists()


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_deliverables_assembles_all_pieces(fixtures_root, studio):
    body = studio.deliverables("hr-basics-01")
    assert body["title"] == "[인사 기본개념 강좌] 1강 — 구성원"
    # 챕터 = chapters.js 실측 (첫 챕터 00:00 규격)
    assert body["chapters"] and body["chapters"][0].startswith("00:0")
    assert any("초대 상태" in c for c in body["chapters"])
    assert "⏱ 챕터" in body["description"] and "재생목록" in body["description"]
    assert body["srt"] == ["hr-basics-01-16x9.srt"]
    assert len(body["thumbnails"]) >= 4  # 검수 프레임이 썸네일 후보


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_subtitle_check_diff_zero(fixtures_root, studio):
    body = studio.subtitle_check("hr-basics-01")
    assert body["ok"] is True, body  # srt ↔ 대본 공백 무시 완전 일치
    assert body["chars"] > 1500


def test_review_checklist_roundtrip(fixtures_root, studio):
    out = studio.put_review("hr-basics-01",
                            {"items": {"밝은프레임": True, "자막겹침": False}, "note": "ok"})
    assert out["updatedAt"]
    got = studio.get_review("hr-basics-01")
    assert got["items"]["밝은프레임"] is True and got["note"] == "ok"


def test_plan_roundtrip(copy_root, studio):
    got = studio.get_plan("hr-basics-01")
    out = studio.put_plan("hr-basics-01", got["markdown"] + "\n| 추가 | 행 |\n", got["etag"])
    assert out["etag"]
    assert "| 추가 | 행 |" in studio.get_plan("hr-basics-01")["markdown"]
    with pytest.raises(EtagMismatch):
        studio.put_plan("hr-basics-01", "x", "stale")


def test_youtube_md_save(copy_root, studio):
    out = studio.save_deliverables("hr-basics-01", title="제목",
                                   description="설명\n00:00 오프닝")
    assert out["file"] == "youtube.md"
    assert (copy_root / "hr-basics-01" / "youtube.md").read_text(encoding="utf-8").startswith("# 제목")


def test_saved_youtube_md_roundtrips(copy_root, studio):
    """고쳐 저장한 문안이 정본 — 재조회가 생성 초안으로 되돌리면 안 된다 (26회차 P21)."""
    before = studio.deliverables("hr-basics-01")
    assert before["saved"] is False          # 저장 전엔 생성 초안
    assert before["title"] == "[인사 기본개념 강좌] 1강 — 구성원"
    out = studio.save_deliverables("hr-basics-01", title="고친 제목",
                                   description="고친 설명\n둘째 줄")
    assert out["file"] == "youtube.md"
    d = studio.deliverables("hr-basics-01")
    assert d["saved"] is True
    assert d["title"] == "고친 제목"
    assert d["description"].startswith("고친 설명")
    assert "둘째 줄" in d["description"]
