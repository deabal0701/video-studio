"""템플릿 갤러리·프리뷰 API — inspect.js --list-templates·preview.js 계약."""

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fixture_root(monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))


def test_gallery_common_and_episode_scope():
    common = client.get("/api/templates").json()
    chapter = next(t for t in common if t["file"] == "chapter.html")
    assert {"num", "title", "progress"} <= set(chapter["params"])
    assert all(t["scope"] == "common" for t in common)

    ep = client.get("/api/templates", params={"scope": "hr-basics-01"}).json()
    files = {t["file"] for t in ep}
    assert "motion/hook-bill.html" in files and "chapter.html" in files

    assert client.get("/api/templates", params={"scope": "없는회차"}).status_code == 404


def test_preview_returns_selfcontained_html():
    r = client.get("/api/templates/preview",
                   params={"file": "motion/hook-bill.html", "scope": "hr-basics-01"})
    assert r.status_code == 200
    html = r.text
    assert "<style>" in html and "<script>" in html
    assert 'href="../../../../engine/motion/_base.css"' not in html  # 인라인됐다
    assert "data-p" in html or "URLSearchParams" in html  # _params.js 인라인 확인

    assert client.get("/api/templates/preview", params={"file": "없다.html"}).status_code == 404
