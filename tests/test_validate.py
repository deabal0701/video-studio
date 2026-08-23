"""draft_defects — 엔진 preflight 가 못 보는 초안 결함 2종 (2026-08-23 실측 결함).

AI 초안이 클립을 최상위 scenes(녹화 씬 자리)에 쓰고 [자리표시자] 를 남긴 채 빌드해
localhost 녹화 시도로 죽었다 — 그 두 결함을 빌드 제출 전에 잡는다.
"""

import pytest

from core import FIXTURES_DIR, schema, validate
from core.facade import Invalid


def test_fixture_is_clean():
    scenes = schema.load_json(FIXTURES_DIR / "hr-basics-01" / "scenes.json")
    assert validate.draft_defects(scenes) == []


def test_clips_in_scenes_array_flagged():
    scenes = {"scenes": [{"id": "ch1", "narration": "본문", "duration": 3.0}],
              "render": {"motion": {"clips": []}}}
    problems = validate.draft_defects(scenes)
    assert len(problems) == 1
    assert "녹화 자리(scenes)" in problems[0] and "ch1" in problems[0]


def test_recording_scenes_with_actions_pass():
    # 홍보 골격의 진짜 녹화 씬(actions 보유)은 결함이 아니다.
    scenes = {"scenes": [{"id": "s1", "narration": "문제 제기",
                          "actions": [{"goto": "/"}]}],
              "render": {"motion": {"clips": []}}}
    assert validate.draft_defects(scenes) == []


def test_placeholder_flagged_but_comment_fields_pass():
    scenes = {"scenes": [], "render": {"motion": {"clips": [
        {"id": "title", "file": "intro.html",
         "narration": "[한 문장 — 주제 선언]",
         "_": "대괄호 [주석] 은 사람용이라 결함이 아니다",
         "params": {"src": "bg/[B롤과 같은 파일명].jpg", "title": "금리란"}},
        {"id": "outro", "file": "outro.html", "narration": "인사말",
         "params": {"title": "한 줄 각인"}},
    ]}}}
    problems = validate.draft_defects(scenes)
    assert len(problems) == 1
    assert "title" in problems[0]
    assert "narration" in problems[0] and "params.src" in problems[0]


def test_submit_build_blocked_on_defects(copy_root, studio):
    f = copy_root / "hr-basics-01" / "scenes.json"
    scenes = schema.load_json(f)
    scenes["scenes"] = [{"id": "ch1", "narration": "잘못 들어온 클립"}]
    schema.save_json(f, scenes)
    with pytest.raises(Invalid) as e:
        studio.submit_build("hr-basics-01")
    assert e.value.code == "draft_defects"
