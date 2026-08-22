"""③ 브랜드 킷 프리셋 적용 — 카피 + 공용 참조 재계산."""

import pytest

from core import ENGINE_DIR, paths
from core.facade import NotFound


def test_apply_preset_overwrites_with_rewritten_refs(copy_root, studio):
    intro = copy_root / "hr-basics" / "course-intro.html"
    intro.write_text("<!-- 손상된 파일 -->", encoding="utf-8")

    out = studio.apply_brand_kit("hr-basics")
    assert sorted(out["copied"]) == ["course-intro.html", "course-stinger.html"]

    text = intro.read_text(encoding="utf-8")
    rel = paths.relpath(ENGINE_DIR / "motion", copy_root / "hr-basics")
    assert f'"{rel}/_base.css"' in text          # 목적지 기준 재계산
    assert "손상된 파일" not in text              # 덮어쓰기
    with pytest.raises(NotFound):
        studio.apply_brand_kit("없는강좌")
