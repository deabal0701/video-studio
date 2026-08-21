"""③ 브랜드 킷 프리셋 적용 — 카피 + 공용 참조 재계산."""

import shutil

import pytest
from fastapi.testclient import TestClient

from core import ENGINE_DIR, FIXTURES_DIR, paths
from api.main import app

client = TestClient(app)


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    return root


def test_apply_preset_overwrites_with_rewritten_refs(root):
    intro = root / "hr-basics" / "course-intro.html"
    intro.write_text("<!-- 손상된 파일 -->", encoding="utf-8")

    r = client.post("/api/courses/hr-basics/brandkit/apply")
    assert r.status_code == 200
    assert sorted(r.json()["copied"]) == ["course-intro.html", "course-stinger.html"]

    text = intro.read_text(encoding="utf-8")
    rel = paths.relpath(ENGINE_DIR / "motion", root / "hr-basics")
    assert f'"{rel}/_base.css"' in text          # 목적지 기준 재계산
    assert "손상된 파일" not in text              # 덮어쓰기
    assert client.post("/api/courses/없는강좌/brandkit/apply").status_code == 404
