"""Index(SQLite 캐시) 테스트."""

import shutil

from core import FIXTURES_DIR
from core.indexer import Index


def test_index_builds_and_rebuilds(tmp_path):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    idx = Index(root, cache_dir=tmp_path / "cache")
    courses = idx.courses()
    assert [c["id"] for c in courses if not c.get("single")] == ["hr-basics"]
    assert courses[0]["episodes"] == ["hr-basics-01"]

    # 캐시 삭제 → 다음 조회가 재생성 (파생 캐시는 언제나 버릴 수 있다)
    idx.db_file.unlink()
    assert idx.courses()[0]["id"] == "hr-basics"

    # 폴더 추가(외부 변경) → 시그니처 불일치 → 재스캔에 잡힌다
    d = root / "hr-basics-02"
    d.mkdir()
    (d / "scenes.json").write_text('{"id": "hr-basics-02"}', encoding="utf-8")
    assert Index(root, cache_dir=tmp_path / "cache").courses()[0]["episodes"] == [
        "hr-basics-01", "hr-basics-02"]

    # 단발 영상(패턴 밖)은 single 로 목록에만
    s = root / "one-off"
    s.mkdir()
    (s / "scenes.json").write_text('{"id": "one-off"}', encoding="utf-8")
    singles = [c for c in Index(root, cache_dir=tmp_path / "cache").courses() if c.get("single")]
    assert [c["id"] for c in singles] == ["one-off"]


def test_list_courses_uses_index(fixtures_root, studio):
    body = studio.list_courses()
    hr = next(c for c in body if c["id"] == "hr-basics")
    assert hr["episodeCount"] == 6 and hr["scaffolded"] == 1
