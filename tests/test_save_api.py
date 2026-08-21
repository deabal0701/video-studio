"""저장 API — If-Match 낙관적 잠금·무손실 저장·검증 동봉 (2단계)."""

import shutil

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR
from api.main import app

client = TestClient(app)


@pytest.fixture
def root(tmp_path, monkeypatch):
    """픽스처를 임시 루트로 복사 — 저장 테스트가 원본을 더럽히지 않는다."""
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    return root


def test_put_requires_if_match(root):
    body = client.get("/api/episodes/hr-basics-01").json()
    r = client.put("/api/episodes/hr-basics-01", json=body["scenes"])
    assert r.status_code == 428


def test_put_etag_mismatch_409_with_current(root):
    body = client.get("/api/episodes/hr-basics-01").json()
    r = client.put("/api/episodes/hr-basics-01", json=body["scenes"],
                   headers={"If-Match": "stale-etag-0000"})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "etag_mismatch" and detail["current"]["id"] == "hr-basics-01"


def test_put_unchanged_body_is_lossless(root):
    """무수정 저장 → 파일 바이트 동일 (라운드트립 diff 0 이 API 를 거쳐도 유지)."""
    before = (root / "hr-basics-01" / "scenes.json").read_text(encoding="utf-8")
    body = client.get("/api/episodes/hr-basics-01").json()
    r = client.put("/api/episodes/hr-basics-01", json=body["scenes"],
                   headers={"If-Match": body["etag"]})
    assert r.status_code == 200
    assert (root / "hr-basics-01" / "scenes.json").read_text(encoding="utf-8") == before


def test_put_edit_saves_and_reports_consistency(root):
    body = client.get("/api/episodes/hr-basics-01").json()
    scenes = body["scenes"]
    scenes["render"]["crf"] = 21
    r = client.put("/api/episodes/hr-basics-01", json=scenes,
                   headers={"If-Match": body["etag"]})
    assert r.status_code == 200
    out = r.json()
    assert out["etag"] != body["etag"]
    assert any("bgm" in p for p in out["consistency"])  # 기존 어긋남 그대로 보고
    saved = client.get("/api/episodes/hr-basics-01").json()["scenes"]
    assert saved["render"]["crf"] == 21
    assert saved["_경로메모"]  # `_` 주석 보존


def test_put_id_mismatch_422(root):
    body = client.get("/api/episodes/hr-basics-01").json()
    scenes = dict(body["scenes"], id="다른-id")
    r = client.put("/api/episodes/hr-basics-01", json=scenes,
                   headers={"If-Match": body["etag"]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "id_mismatch"


def test_put_course_reconsistency(root):
    body = client.get("/api/courses/hr-basics").json()
    course = body["course"]
    course["render"]["crf"] = 19  # 회차와 같은 값 — 새 어긋남은 없다
    r = client.put("/api/courses/hr-basics", json=course,
                   headers={"If-Match": body["etag"]})
    assert r.status_code == 200
    out = r.json()
    # 회차가 실존하는 hr-basics-01 만 검사 대상 — 기존 bgm 어긋남이 배지 재료로 나온다
    assert "hr-basics-01" in out["consistency"]
    assert any("bgm" in p for p in out["consistency"]["hr-basics-01"])
