"""A4 불변식 — 빈/신규 상태를 오류·완료로 오판하지 않는다 (11_polish-loop 모드 A, 75회차).

갓 만든 프로젝트는 사용자가 **처음 보는 화면**이다 — 여기서 오류·은어가 뜨면 앱의
첫인상이 결함이 된다. 65회차(0개인데 "전부 완료")·67회차("남은 영상이 없습니다")·
baseUrl 즉사 · 75회차(챕터 없는 골격이 node 명령줄 빨간 오류)가 전부 이 지대였다.

여기서는 파생물 계약을 고정한다 — 화면 문구는 A4 프로브(a4_probe)가 눈으로 걸렀고,
그 프로브가 걸러낸 판정 규칙을 core 가 배신하지 않는지를 본다.
"""

from __future__ import annotations

from pathlib import Path

from core import deliverables, scaffold


def _fresh(tmp_path: Path, kind: str) -> tuple[Path, Path]:
    root = tmp_path / "projects"
    root.mkdir()
    scaffold.scaffold_course(root, f"fresh-{kind}", title="신규", kind=kind)
    ep_dir = scaffold.scaffold_episode(root, f"fresh-{kind}", 1, title="신규")
    return root, ep_dir


def test_fresh_single_has_no_chapter_error(tmp_path):
    """챕터 카드 없는 골격(홍보)은 **정상 무챕터** — 오류도, 명령줄도 아니다."""
    root, ep_dir = _fresh(tmp_path, "promo")
    out = deliverables.build(ep_dir, root)
    assert out["chaptersReason"] == "no_cards"
    assert out["chaptersError"] is None          # 화면이 빨간 오류를 만들 재료가 없다
    assert "node " not in (out["chaptersError"] or "")


def test_fresh_description_has_no_empty_chapter_header(tmp_path):
    """챕터가 0개면 설명 초안에 빈 "⏱ 챕터" 섹션을 남기지 않는다."""
    root, ep_dir = _fresh(tmp_path, "promo")
    out = deliverables.build(ep_dir, root)
    assert not out["chapters"]
    assert "⏱ 챕터" not in out["description"]


def test_fresh_lecture_chapters_state(tmp_path):
    """강의 골격은 챕터 카드(course-intro 등)를 갖는다 — no_cards 로 오판하면 안 된다."""
    root, ep_dir = _fresh(tmp_path, "lecture")
    out = deliverables.build(ep_dir, root)
    # 빌드 전이라 실측 챕터는 없지만, "카드가 없다"는 판정이 나와서는 안 된다
    assert out["chaptersReason"] != "no_cards"
