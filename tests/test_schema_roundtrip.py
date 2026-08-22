"""schema 라운드트립 — 2단계 수용 기준: 픽스처를 열고 저장했을 때 diff 0."""

from core import FIXTURES_DIR
from core.schema import Document

FIXTURE_FILES = [
    FIXTURES_DIR / "hr-basics" / "course.json",
    FIXTURES_DIR / "hr-basics-01" / "scenes.json",
]


def test_load_save_diff_zero(tmp_path):
    """수정 없이 열고 저장 → **바이트** 동일 (손서식은 물론 개행까지 — CRLF 번역 회귀 방지).

    read_text 비교는 universal newline 디코딩이 CRLF 를 지워 항상 통과했다 (07 결함 5) —
    실제 파일 바이트로 검사해야 무손실 규약이 진짜로 고정된다.
    """
    import shutil

    for src in FIXTURE_FILES:
        copy = tmp_path / src.name
        shutil.copy(src, copy)
        doc = Document.load(copy)
        assert not doc.dirty
        doc.save()
        assert copy.read_bytes() == src.read_bytes(), src.name


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
