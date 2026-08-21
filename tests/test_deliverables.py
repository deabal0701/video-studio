"""3D — 챕터(심링크 루트)·자막 대조·검수 기록·배포 산출물·plan 라운드트립."""

import shutil

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_root(monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))


BUILT = (FIXTURES_DIR.parent.parent / "engine" / "out" / "hr-basics-01" / "final").exists()


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_deliverables_assembles_all_pieces():
    body = client.get("/api/episodes/hr-basics-01/deliverables").json()
    assert body["title"] == "[인사 기본개념 강좌] 1강 — 구성원"
    # 챕터 = chapters.js 실측 (첫 챕터 00:00 규격)
    assert body["chapters"] and body["chapters"][0].startswith("00:0")
    assert any("초대 상태" in c for c in body["chapters"])
    assert "⏱ 챕터" in body["description"] and "재생목록" in body["description"]
    assert body["srt"] == ["hr-basics-01-16x9.srt"]
    assert len(body["thumbnails"]) >= 4  # 검수 프레임이 썸네일 후보


@pytest.mark.skipif(not BUILT, reason="픽스처 빌드 산출물 없음")
def test_subtitle_check_diff_zero():
    body = client.get("/api/episodes/hr-basics-01/subtitle-check").json()
    assert body["ok"] is True, body  # srt ↔ 대본 공백 무시 완전 일치
    assert body["chars"] > 1500


def test_review_checklist_roundtrip():
    r = client.put("/api/episodes/hr-basics-01/review",
                   json={"items": {"밝은프레임": True, "자막겹침": False}, "note": "ok"})
    assert r.status_code == 200 and r.json()["updatedAt"]
    got = client.get("/api/episodes/hr-basics-01/review").json()
    assert got["items"]["밝은프레임"] is True and got["note"] == "ok"


def test_plan_roundtrip(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    got = client.get("/api/episodes/hr-basics-01/plan").json()
    r = client.put("/api/episodes/hr-basics-01/plan",
                   json={"markdown": got["markdown"] + "\n| 추가 | 행 |\n"},
                   headers={"If-Match": got["etag"]})
    assert r.status_code == 200
    assert "| 추가 | 행 |" in client.get("/api/episodes/hr-basics-01/plan").json()["markdown"]
    assert client.put("/api/episodes/hr-basics-01/plan", json={"markdown": "x"},
                      headers={"If-Match": "stale"}).status_code == 409


def test_youtube_md_save(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    r = client.post("/api/episodes/hr-basics-01/deliverables/save",
                    json={"title": "제목", "description": "설명\n00:00 오프닝"})
    assert r.status_code == 200
    assert (root / "hr-basics-01" / "youtube.md").read_text(encoding="utf-8").startswith("# 제목")
