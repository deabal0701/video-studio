"""④ [대본으로 반영] + 일관성 [강좌 값으로 맞추기]."""

import shutil

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR, schema, validate
from core.plan_apply import parse_plan_rows
from api.main import app

client = TestClient(app)


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    return root


def test_parse_fixture_plan_rows():
    md = (FIXTURES_DIR / "hr-basics-01" / "plan.md").read_text(encoding="utf-8")
    rows = parse_plan_rows(md)
    ids = [r["id"] for r in rows]
    assert ids[:3] == ["broll", "title", "hook"]
    hook = next(r for r in rows if r["id"] == "hook")
    assert hook["chars"] and hook["chars"] > 10  # 글자수 컬럼 파싱


def test_apply_adds_only_missing_rows_in_order(root):
    plan = root / "hr-basics-01" / "plan.md"
    md = plan.read_text(encoding="utf-8")
    # s3b 행 뒤에 새 구간 s3c 를 끼워 넣는다
    lines = md.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("| s3b"))
    lines.insert(i + 1, "| s3c | 새 설명 구간 | **도식** `billing.html` | 120 | |")
    plan.write_text("\n".join(lines) + "\n", encoding="utf-8")

    r = client.post("/api/episodes/hr-basics-01/plan/apply")
    assert r.status_code == 200
    assert r.json()["added"] == ["s3c"]

    scenes = schema.load_json(root / "hr-basics-01" / "scenes.json")
    clips = scenes["render"]["motion"]["clips"]
    ids = [c["id"] for c in clips]
    assert ids.index("s3c") == ids.index("s3b") + 1  # 표 순서 자리에 삽입
    s3c = clips[ids.index("s3c")]
    assert s3c["file"] == "motion/billing.html"      # 회차 전용 도식으로 해석
    assert s3c["_목표글자수"] == 120                  # 예산이 클립별 목표로
    assert s3c["params"]["brand"] == "#F97316"        # palette 자동 주입
    assert scenes["_경로메모"]                        # `_` 보존

    # 두 번째 반영은 무변경 (기존 클립 보존)
    assert client.post("/api/episodes/hr-basics-01/plan/apply").json()["added"] == []


def test_sync_course_clears_consistency(root):
    body = client.get("/api/episodes/hr-basics-01").json()
    assert client.get("/api/episodes/hr-basics-01/consistency").json()["problems"]  # bgm 어긋남
    r = client.post("/api/episodes/hr-basics-01/sync-course",
                    headers={"If-Match": body["etag"]})
    assert r.status_code == 200
    assert r.json()["consistency"] == []
    scenes = schema.load_json(root / "hr-basics-01" / "scenes.json")
    course = schema.load_json(root / "hr-basics" / "course.json")
    assert validate.consistency(scenes, course) == []
    assert scenes["render"]["bgm"] == course["render"]["bgm"]
    assert scenes["render"]["motion"]["clips"]  # motion 은 보존
    # If-Match 없으면 428
    assert client.post("/api/episodes/hr-basics-01/sync-course").status_code == 428
