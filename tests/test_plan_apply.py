"""④ [대본으로 반영] + 일관성 [강좌 값으로 맞추기]."""

import pytest

from core import FIXTURES_DIR, schema, validate
from core.facade import EtagRequired
from core.plan_apply import parse_plan_rows


def test_parse_fixture_plan_rows():
    md = (FIXTURES_DIR / "hr-basics-01" / "plan.md").read_text(encoding="utf-8")
    rows = parse_plan_rows(md)
    ids = [r["id"] for r in rows]
    assert ids[:3] == ["broll", "title", "hook"]
    hook = next(r for r in rows if r["id"] == "hook")
    assert hook["chars"] and hook["chars"] > 10  # 글자수 컬럼 파싱


def test_apply_adds_only_missing_rows_in_order(copy_root, studio):
    plan = copy_root / "hr-basics-01" / "plan.md"
    md = plan.read_text(encoding="utf-8")
    # s3b 행 뒤에 새 구간 s3c 를 끼워 넣는다
    lines = md.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("| s3b"))
    lines.insert(i + 1, "| s3c | 새 설명 구간 | **도식** `billing.html` | 120 | |")
    plan.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = studio.plan_apply("hr-basics-01")
    assert out["added"] == ["s3c"]

    scenes = schema.load_json(copy_root / "hr-basics-01" / "scenes.json")
    clips = scenes["render"]["motion"]["clips"]
    ids = [c["id"] for c in clips]
    assert ids.index("s3c") == ids.index("s3b") + 1  # 표 순서 자리에 삽입
    s3c = clips[ids.index("s3c")]
    assert s3c["file"] == "motion/billing.html"      # 회차 전용 도식으로 해석
    assert s3c["_목표글자수"] == 120                  # 예산이 클립별 목표로
    assert s3c["params"]["brand"] == "#F97316"        # palette 자동 주입
    assert scenes["_경로메모"]                        # `_` 보존

    # 두 번째 반영은 무변경 (기존 클립 보존)
    assert studio.plan_apply("hr-basics-01")["added"] == []


def test_sync_course_clears_consistency(copy_root, studio):
    body = studio.get_episode("hr-basics-01")
    assert studio.consistency("hr-basics-01")["problems"]  # bgm 어긋남
    out = studio.sync_course("hr-basics-01", body["etag"])
    assert out["consistency"] == []
    scenes = schema.load_json(copy_root / "hr-basics-01" / "scenes.json")
    course = schema.load_json(copy_root / "hr-basics" / "course.json")
    assert validate.consistency(scenes, course) == []
    assert scenes["render"]["bgm"] == course["render"]["bgm"]
    assert scenes["render"]["motion"]["clips"]  # motion 은 보존
    with pytest.raises(EtagRequired):
        studio.sync_course("hr-basics-01", None)
