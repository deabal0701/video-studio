"""schema 라운드트립 — 2단계 수용 기준: 픽스처를 열고 저장했을 때 diff 0."""

from core import FIXTURES_DIR
from core.schema import Document

FIXTURE_FILES = [
    FIXTURES_DIR / "hr-basics" / "course.json",
    FIXTURES_DIR / "hr-basics-01" / "scenes.json",
]


def test_load_save_diff_zero(tmp_path):
    """수정 없이 열고 저장 → 바이트 동일 (한 줄 객체 등 손서식 보존)."""
    for src in FIXTURE_FILES:
        doc = Document.load(src)
        assert not doc.dirty
        assert doc.dumps() == src.read_text(encoding="utf-8"), src.name


def test_edit_preserves_comments_and_key_order(tmp_path):
    src = FIXTURES_DIR / "hr-basics-01" / "scenes.json"
    doc = Document.load(src)
    doc.data["render"]["crf"] = 20  # 실제 수정
    assert doc.dirty
    out = tmp_path / "scenes.json"
    doc.file = out
    doc.save()

    saved = Document.load(out)
    assert saved.data["render"]["crf"] == 20
    # `_` 주석 필드·키 순서 보존
    assert saved.data["_경로메모"] == doc.data["_경로메모"]
    assert list(saved.data) == list(doc.data)
    clip_ids = [c["id"] for c in saved.data["render"]["motion"]["clips"]]
    assert clip_ids[:4] == ["broll", "title", "hook", "stinger"]
    # 들여쓰기 2칸·끝 개행
    text = out.read_text(encoding="utf-8")
    assert text.startswith('{\n  "') and text.endswith("}\n")
