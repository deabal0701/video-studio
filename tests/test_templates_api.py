"""템플릿 갤러리·프리뷰 — inspect.js --list-templates·preview.js 계약 + 화이트리스트."""

import pytest

from core.facade import NotFound

pytestmark = pytest.mark.usefixtures("fixtures_root")


def test_gallery_common_and_episode_scope(studio):
    common = studio.templates()
    chapter = next(t for t in common if t["file"] == "chapter.html")
    assert {"num", "title", "progress"} <= set(chapter["params"])
    assert all(t["scope"] == "common" for t in common)

    ep = studio.templates(scope="hr-basics-01")
    files = {t["file"] for t in ep}
    assert "motion/hook-bill.html" in files and "chapter.html" in files

    with pytest.raises(NotFound):
        studio.templates(scope="없는회차")


def test_preview_returns_selfcontained_html(studio):
    html = studio.template_preview("motion/hook-bill.html", scope="hr-basics-01")
    assert "<style>" in html and "<script>" in html
    assert 'href="../../../../engine/motion/_base.css"' not in html  # 인라인됐다
    assert "data-p" in html or "URLSearchParams" in html  # _params.js 인라인 확인

    with pytest.raises(NotFound):
        studio.template_preview("없다.html")


def test_preview_whitelist_blocks_arbitrary_paths(studio, tmp_path):
    """5-2 신설 — 갤러리 밖 경로(절대경로 포함)는 읽지 않는다 (구 HTTP 시절 결함 봉쇄)."""
    secret = tmp_path / "secret.html"
    secret.write_text("<p>비밀</p>", encoding="utf-8")
    with pytest.raises(NotFound):
        studio.template_preview(str(secret))
    with pytest.raises(NotFound):
        studio.template_preview("../fixtures/projects/hr-basics/course.json")
