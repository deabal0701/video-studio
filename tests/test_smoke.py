"""0단계 골격 스모크 — 모듈 임포트·LocalFS·스키마 라운드트립·인덱서·엔진 inspect 계약.

paths.py 실측 5행 고정 테스트와 무손실(diff 0) 직렬화 테스트는 2단계 수용 기준
(06_roadmap "테스트 전략")이라 여기 없다.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core import ENGINE_DIR, FIXTURES_DIR
from core import engine_io, indexer, paths, schema, validate
from core.storage import LocalFS

FIXTURE_EPISODE = FIXTURES_DIR / "hr-basics-01"


def test_localfs_roundtrip_and_etag(tmp_path: Path):
    fs = LocalFS(tmp_path)
    fs.write_bytes("a/b.txt", "한글".encode())
    assert fs.read_bytes("a/b.txt").decode() == "한글"
    tag1 = fs.etag("a/b.txt")
    fs.write_bytes("a/b.txt", "바뀜".encode())
    assert fs.etag("a/b.txt") != tag1
    with pytest.raises(ValueError):
        fs.abspath("../탈출")


def test_scenes_fixture_roundtrip_semantic(tmp_path: Path):
    """load→save 가 내용·키 순서를 보존한다 (형식까지 diff 0 은 2단계)."""
    src = FIXTURE_EPISODE / "scenes.json"
    data = schema.load_json(src)
    out = tmp_path / "scenes.json"
    schema.save_json(out, data)
    again = schema.load_json(out)
    assert again == data
    assert list(again) == list(data)  # 키 순서
    assert data["id"] == "hr-basics-01"
    assert schema.Scenes.model_validate(data).id == "hr-basics-01"  # extra="allow" 통과


def test_paths_engine_bases():
    """bgm·broll 은 엔진 루트 기준 — 픽스처의 실측값과 일치해야 한다."""
    bgm = ENGINE_DIR / "assets" / "bgm" / "mixkit-623-loop.mp3"
    assert paths.compute(paths.RefKind.BGM, bgm) == "assets/bgm/mixkit-623-loop.mp3"
    intro = FIXTURES_DIR / "hr-basics" / "course-intro.html"
    got = paths.compute(paths.RefKind.MOTION, intro, scenes_dir=FIXTURE_EPISODE)
    assert got == "../hr-basics/course-intro.html"


def test_validate_budget_and_consistency():
    scenes = schema.load_json(FIXTURE_EPISODE / "scenes.json")
    course = schema.load_json(FIXTURES_DIR / "hr-basics" / "course.json")
    assert validate.narration_total(scenes) > 1500  # 실측 약 2,000자
    problems = validate.consistency(scenes, course)
    # bgm 은 회차가 루프 파생본을 쓰므로 어긋남이 보고되는 것이 맞다
    assert any("bgm" in p for p in problems)


def test_indexer_scan_fixture():
    courses, singles = indexer.scan(FIXTURES_DIR)
    assert [c.id for c in courses] == ["hr-basics"]
    assert courses[0].episodes == ["hr-basics-01"]
    assert singles == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_engine_inspect_contract():
    """inspect.js 출력이 04_api 계약 4키를 갖춘다."""
    result = engine_io.inspect(FIXTURE_EPISODE)
    assert set(result) == {"preflight", "templates", "media", "audioCache"}
    assert result["preflight"] == []  # 경로 이전 후 픽스처는 이상 없음
    assert result["media"]["assets/broll/office-talk.mp4"]["exists"] is True


def test_build_line_parser():
    e = engine_io.parse_build_line("[1] TTS (edge / ko-KR-SunHiNeural)")
    assert (e.kind, e.phase, e.title) == ("phase", 1, "TTS (edge / ko-KR-SunHiNeural)")
    e = engine_io.parse_build_line("  · 모션 hook     8.90s  이 사람은…")
    assert (e.kind, e.step_id, e.seconds) == ("step", "hook", 8.9)
    e = engine_io.parse_build_line("  · s1a    12.34s  관리자가…")
    assert (e.kind, e.step_id) == ("step", "s1a")
    assert engine_io.parse_build_line("완료 — out/hr-basics-01").kind == "log"
