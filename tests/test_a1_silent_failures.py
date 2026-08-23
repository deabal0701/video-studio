"""A1 불변식 — 조용한 실패 금지 (11_polish-loop 모드 A, 72회차).

개별 회귀 테스트가 아니라 **클래스 자체를 금지**한다 — 새 화면·새 호출에도 자동
적용된다. 근거가 된 결함: 30회차(키 저장 실패 무시)·70회차(프리뷰 실패 삼킴)·
72회차(에이전트 게이트 3곳·한 번에 모드 상태 조회·목소리 목록이 전부
`fail=lambda _e: None` 로 조용히 죽었다).

규칙 2개:
  ① app/ 의 모든 run_bg 호출은 fail= 을 명시한다 — bridge._Task 는 fail=None 이면
     stderr 트레이스만 남기므로, 화면은 아무 말도 하지 않게 된다.
  ② fail 이 아무것도 하지 않는 lambda(본문이 None)면, 그 위 3줄 안에 "A1-허용"
     주석으로 **왜 조용해도 되는지**를 적어야 한다. 근거 없는 삼킴은 실패다.
     (스테일 토큰 가드 `None if token != ...` 는 본문이 None 이 아니라 조건식이라
     이 규칙에 걸리지 않는다 — 그건 A3 처방이다.)
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
MARKER = "A1-허용"
NEARBY = 3   # lambda 줄 위로 이만큼 안에 근거 주석이 있어야 한다


def _run_bg_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else "")
            if name == "run_bg":
                yield node


def _swallows(node: ast.Call) -> ast.Lambda | None:
    """fail=lambda …: None 이면 그 lambda — 아무것도 안 하는 실패 처리다."""
    for kw in node.keywords:
        if kw.arg == "fail" and isinstance(kw.value, ast.Lambda):
            body = kw.value.body
            if isinstance(body, ast.Constant) and body.value is None:
                return kw.value
    return None


def test_run_bg_always_declares_fail():
    missing = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _run_bg_calls(tree):
            if not any(kw.arg == "fail" for kw in call.keywords):
                missing.append(f"{path.relative_to(APP.parent)}:{call.lineno}")
    assert not missing, (
        "fail= 없는 run_bg — 실패가 stderr 로만 사라진다. 화면이 사유를 말하게 하라:\n"
        + "\n".join(missing))


def test_silent_fail_lambda_requires_rationale():
    unjustified = []
    for path in APP.rglob("*.py"):
        src_lines = path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(src_lines))
        for call in _run_bg_calls(tree):
            lam = _swallows(call)
            if lam is None:
                continue
            window = src_lines[max(0, lam.lineno - 1 - NEARBY):lam.lineno]
            if not any(MARKER in line for line in window):
                unjustified.append(f"{path.relative_to(APP.parent)}:{lam.lineno}")
    assert not unjustified, (
        f"근거 없는 조용한 실패 — 위 {NEARBY}줄 안에 '{MARKER}: <왜 조용해도 되는가>' "
        "주석을 달거나, 실패 사유를 화면에 쓰게 하라:\n" + "\n".join(unjustified))
