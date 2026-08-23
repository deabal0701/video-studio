"""D18 — 스킬 규약 발췌 조립. 절 제목이 스킬에서 바뀌면 여기서 표류가 잡힌다."""

import pytest

from core.agents import skill_prompts


def test_all_declared_sections_resolve():
    """선언된 절 전부 발췌 성공 — 실패는 곧 스킬 제목 표류(목록을 함께 고쳐야 한다)."""
    lecture = skill_prompts.draft_rules(series=True)
    single = skill_prompts.draft_rules(series=False)
    diagram = skill_prompts.diagram_rules()
    assert all(len(t) > 500 for t in (lecture, single, diagram))


def test_series_and_single_differ():
    """강좌(6.4자/초)와 단발(6.3자/초)은 규약이 다르다 — 한쪽만 조립 (모순 주입 방지)."""
    lecture = skill_prompts.draft_rules(series=True)
    single = skill_prompts.draft_rules(series=False)
    assert "회차는 독립" in lecture and "회차는 독립" not in single
    assert "구성표" in lecture and "구성표" in single      # 공통 절은 양쪽 다
    assert "지켜야 할 선" in lecture and "지켜야 할 선" in single


def test_no_tools_preamble():
    """도구 없음 선언 — 실행 지시 오독(경로 수작업·명령 실행 시도)을 막는 핵심 한 줄."""
    for text in (skill_prompts.draft_rules(series=True),
                 skill_prompts.diagram_rules(), skill_prompts.review_rules()):
        assert "파일" in text and "없다" in text


def test_review_rules_is_full_document_without_frontmatter():
    text = skill_prompts.review_rules()
    assert not text.startswith("---")           # 프론트매터(tools: Bash…) 제거
    assert "자평" in text                        # reviewer.md 본문이 실려 있다


def test_missing_heading_raises():
    with pytest.raises(KeyError):
        skill_prompts._section("# 제목\n본문\n## 절\n내용", "없는 절")


def test_section_deep_vs_shallow():
    text = "## 상위\n도입\n### 하위\n하위 내용\n## 다음\nX"
    assert "하위 내용" in skill_prompts._section(text, "상위", deep=True)
    assert "하위 내용" not in skill_prompts._section(text, "상위", deep=False)
    assert "다음" not in skill_prompts._section(text, "상위", deep=True)


def test_health_ok():
    assert skill_prompts.health()["ok"] is True
