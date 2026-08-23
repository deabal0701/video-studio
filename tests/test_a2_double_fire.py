"""A2 불변식 — 이중 실행 잠금 구멍 금지 (11_polish-loop 모드 A, 73회차).

버튼이 백그라운드 작업(run_bg)을 시작하면 **재클릭을 막는 장치**가 그 핸들러에
보여야 한다. 없으면 더블클릭이 잡을 두 번 쌓고(22회차), 프로젝트를 두 개 만들고
(34회차), 옛 etag 로 409 를 띄우고(73회차 sync), 유료 TTS 를 이중 과금한다
(73회차 미리듣기). 52·56·58·59·60·61회차가 전부 "같은 구멍"이었다 — 화면마다
사본이 생길 때마다 재발하므로 클래스로 금지한다.

기계 규칙 (ast + 소스 검사):
  `clicked.connect(self._x)` 또는 `clicked.connect(lambda…: self._x(…))` 로 연결된
  메서드의 본문에 run_bg 가 있으면, 본문에 아래 **잠금 관용구** 중 하나가 있어야
  한다. 정당하게 없어도 되는 곳(멱등 취소·재실행이 곧 기능인 버튼)은 본문 안에
  "A2-허용: <근거>" 주석을 단다.

검사 경계: self 메서드 직결만 본다 — 시그널 중계(emit)로 이어지는 핸들러는
수신부 메서드가 제 이름으로 다시 걸리므로 거기서 걸린다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
MARKER = "A2-허용"
# 이 저장소가 실제로 쓰는 잠금 관용구들 — 새 관용구를 만들면 여기 등록한다
GUARDS = ("setEnabled(False", "_busy", "_saving", "_creating", "_deleting",
          "_sampling", "_set_building(True", "_begin_create", "stop_if_playing",
          "QMessageBox", "QFileDialog", "QInputDialog", ".exec()", "self._req",
          MARKER)

CONNECT_RE = re.compile(
    r"clicked\.connect\(\s*(?:lambda[^:]*:\s*)?self\.(\w+)")


def _handlers_with_run_bg(path: Path):
    src = path.read_text(encoding="utf-8")
    names = set(CONNECT_RE.findall(src))
    if not names:
        return
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            seg = ast.get_source_segment(src, node) or ""
            if "run_bg(" in seg:
                yield node.name, node.lineno, seg


def test_clicked_handlers_that_spawn_work_are_guarded():
    holes = []
    for path in APP.rglob("*.py"):
        for name, lineno, seg in _handlers_with_run_bg(path):
            if not any(g in seg for g in GUARDS):
                holes.append(f"{path.relative_to(APP.parent)}:{lineno} {name}()")
    assert not holes, (
        "잠금 없는 작업 버튼 — 재클릭이 중복 실행된다. 잠금 관용구를 넣거나, "
        f"멱등이라 무해하면 본문에 '{MARKER}: <근거>' 주석을 달라:\n" + "\n".join(holes))
