"""템플릿 갤러리·프리뷰 — inspect.js --list-templates·preview.js 계약 + 화이트리스트."""

from pathlib import Path

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


def test_preview_allows_project_own_html(studio, copy_root):
    """타이틀 카드·로고 전환은 프로젝트 폴더에 있어 갤러리에 없다 — 그래도 프리뷰된다.

    70회차: 갤러리 화이트리스트가 이 둘을 막아 **프리뷰가 영영 안 떴고** 실패는
    조용히 삼켜졌다. 브랜드 킷이 "② 대본 탭 프리뷰에서 봅니다"라고 가리키는 그 둘이다.
    """
    studio.create_course({"course": "nc", "title": "새 강좌", "kind": "lecture"})
    studio.create_episode("nc", 1, title="첫 영상")
    gallery = {t["file"] for t in studio.templates(scope="nc-01")}
    assert "../nc/course-intro.html" not in gallery      # 갤러리에는 여전히 없다
    html = studio.template_preview("../nc/course-intro.html", scope="nc-01")
    assert "<html" in html.lower() and len(html) > 500


def test_preview_still_blocks_escapes(studio, copy_root):
    """화이트리스트의 취지는 지킨다 — 절대경로·데이터 폴더 밖은 계속 거부."""
    studio.create_course({"course": "nc2", "title": "새 강좌2", "kind": "lecture"})
    studio.create_episode("nc2", 1, title="첫 영상")
    for bad in ("../../engine/motion/_base.css", "../../../etc/passwd",
                str(Path(__file__).resolve())):
        with pytest.raises(NotFound):
            studio.template_preview(bad, scope="nc2-01")
