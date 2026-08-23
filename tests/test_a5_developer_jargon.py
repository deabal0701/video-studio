"""A5 불변식 — 화면 문자열에 개발자 용어 금지 (11_polish-loop 모드 A, 76회차).

파일명·내부 키·영문 상태어·경로가 화면 리터럴에 **날것으로** 들어가는 것을 막는다.
"제목 (title)"·"타이틀 카드 (intro.html)" 처럼 **한국어 뜻을 앞세우고 괄호로 원어를
보조**하는 관용구(6·7회차 키 라벨 문법)는 허용한다 — 원어는 지울 줄·파일을 찾는 데
필요해서 버리지 않는 것이 규약이다.

76회차 전수 감사 결과 위반 0건 — 이 테스트는 그 상태를 지킨다. 검사 대상은 UI 로
들어가는 호출(setText·setToolTip·QLabel·메시지 박스 등)의 문자열 리터럴이고,
dict 키 접근(`r["failed"]`)처럼 표현식 내부의 키 리터럴은 화면에 닿지 않으므로
제외한다 (Subscript slice).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
UI_CALLS = {"setText", "setPlaceholderText", "setToolTip", "setWindowTitle",
            "addItem", "setLabelText", "appendPlainText", "setTabText",
            "information", "warning", "question", "critical"}
UI_CTORS = {"QLabel", "QPushButton", "QRadioButton", "QCheckBox", "QToolButton"}
SUSPICIOUS = [
    re.compile(r"\.(html|json|js|mjs|md|py)\b"),
    re.compile(r"\b(jobId|etag|eid|cid|baseUrl)\b"),
    re.compile(r"\b(OK|Error|error|failed|running|null|None)\b"),
    re.compile(r"[A-Z]:\\\\|/out/"),
]
# "한국어 … (" — 괄호 보조 관용구. 괄호 이전에 한국어 뜻이 있으면 그 뒤 원어는 허용
KOREAN_LEAD = re.compile(r"[가-힣][^()]*\(")


def _subscript_keys(tree: ast.AST) -> set[int]:
    """dict 키 리터럴의 위치 — 화면에 닿지 않는 문자열."""
    spots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            for c in ast.walk(node.slice):
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    spots.add(id(c))
    return spots


def test_no_raw_developer_jargon_in_ui_strings():
    hits = []
    for path in APP.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        keys = _subscript_keys(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name not in UI_CALLS and name not in UI_CTORS:
                continue
            for arg in list(node.args) + [k.value for k in node.keywords]:
                for s in [n for n in ast.walk(arg)
                          if isinstance(n, ast.Constant)
                          and isinstance(n.value, str) and len(n.value) > 2
                          and id(n) not in keys]:
                    v = s.value
                    for rx in SUSPICIOUS:
                        m = rx.search(v)
                        if m and not (KOREAN_LEAD.search(v)
                                      and m.start() > v.find("(")):
                            hits.append(f"{path.relative_to(APP.parent)}:{s.lineno} "
                                        f"{' '.join(v.split())[:70]!r}")
                            break
    assert not hits, (
        "화면 문자열에 개발자 용어가 날것으로 들어갔다 — 한국어 뜻을 앞세우고 "
        "원어는 괄호 보조로 강등하라 (6·7회차 문법):\n" + "\n".join(hits))
