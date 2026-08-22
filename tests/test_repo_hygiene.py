"""저장소 위생 — 사람이 계속 잊는 규칙을 기계가 대신 지킨다.

두 규칙 다 08_qt-style 에 적혀 있는데도 **눈으로는 계속 새어 나갔다**:

1. `.ps1` BOM(§9) — 문서화 뒤에도 세 번 재발 (setup-qt-venv.ps1 → run.ps1 재작성 →
   5-8 신규 3종). PowerShell 5.1 이 BOM 없는 파일을 ANSI 로 읽어 한글이 깨지고,
   깨진 문자가 구문에 걸리면 `Unexpected token '}'` 로 파서까지 죽는다.
2. 화면 문자열의 이모지(§5) — 전 화면 정리 스윕을 하고도 4건이 남았다. 정규식으로 훑고
   "주석이라 무해"로 넘긴 것이 실은 화면에 뜨는 리터럴이었다(`'밝은☀'`·`'어두운🌙'`).
   **그래서 주석이 아니라 AST 의 문자열 리터럴만 본다.**

기억에 의존하는 규칙은 재발한다. 이 테스트가 규칙의 집행자다.
(CLAUDE.md "기계화 가능한 검증만 옮긴다" — 규약 자체는 08 문서가 정본)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BOM = b"\xef\xbb\xbf"
# 우리가 쓴 스크립트만 본다 — vendoring·빌드 산출물의 남의 스크립트는 대상이 아니다
SKIP_PARTS = {".qt-venv", "node_modules", "dist", "build", ".git"}


def _our_scripts() -> list[Path]:
    return sorted(p for p in REPO.rglob("*.ps1")
                  if not SKIP_PARTS & set(p.relative_to(REPO).parts))


def test_scripts_exist() -> None:
    """대상이 0개면 이 테스트가 조용히 무력해진다 — 빈 통과를 막는다."""
    assert _our_scripts(), "저장소의 .ps1 을 하나도 못 찾았다 — 수집 규칙을 확인하라"


@pytest.mark.parametrize("script", _our_scripts(), ids=lambda p: p.name)
def test_ps1_has_utf8_bom(script: Path) -> None:
    head = script.read_bytes()[:3]
    assert head == BOM, (
        f"{script.relative_to(REPO)} 에 UTF-8 BOM 이 없다 — PowerShell 5.1 이 ANSI 로 읽어 "
        f"한글 출력이 깨지고 구문 오류까지 난다 (docs/design/08_qt-style.md §9). "
        f"고치기: 파일 맨 앞에 EF BB BF 를 붙인다"
    )


# ── 화면 문자열의 이모지 (08_qt-style §5) ────────────────────────────────────
# 이모지는 OS 폰트가 제멋대로 대체 렌더한다 — 실측(2026-08-22): 상태 기호로 쓴 것들이
# 체크박스 아이콘·"END" 화살표·초록 체크로 바뀌어 뜻과 무관한 그림이 됐다.
# 상태는 색 점(theme.dot)+한국어 라벨로 말한다.
#
# 차단: 아스트랄 이모지 전 범위 + 이 저장소가 실제로 데인 BMP 기호.
# 허용: `✓`(U+2713)·`▶`(U+25B6) — Segoe UI 에서 텍스트 글리프로 안정 렌더된다.
EMOJI_BLOCK = set(range(0x1F000, 0x20000)) | {
    0x2600, 0x2601, 0x26A0, 0x26A1, 0x2705, 0x274C, 0x2B1B, 0x2B1C,
    0x2B50, 0x2757, 0x2753, 0x23F0, 0x23F3,
}
UI_DIR = REPO / "app"


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """모듈·클래스·함수의 독스트링 노드 id — 설명문에는 실측 예시를 적을 수 있어야 한다."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.add(id(first.value))
    return out


def _emoji_in_ui_strings() -> list[str]:
    hits: list[str] = []
    for path in sorted(UI_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in skip:
                continue
            bad = sorted({c for c in node.value if ord(c) in EMOJI_BLOCK})
            if bad:
                chars = " ".join(f"{c} (U+{ord(c):04X})" for c in bad)
                hits.append(f"{path.relative_to(REPO)}:{node.lineno}: {chars} — {node.value[:50]!r}")
    return hits


def test_ui_dir_is_scannable() -> None:
    """수집이 0개가 되면 검사가 조용히 무력해진다 — 빈 통과를 막는다."""
    assert list(UI_DIR.rglob("*.py")), "app/ 에서 파이썬 파일을 못 찾았다 — 경로를 확인하라"


def test_no_emoji_in_ui_strings() -> None:
    hits = _emoji_in_ui_strings()
    assert not hits, (
        "화면 문자열에 이모지가 있다 — OS 폰트가 다른 그림으로 대체 렌더한다 "
        "(docs/design/08_qt-style.md §5). 상태는 theme.dot(색)+한국어 라벨로, "
        "경고는 텍스트로 쓴다:\n  " + "\n  ".join(hits)
    )
