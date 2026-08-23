"""A3 불변식 — 늦은 응답 되덮기 금지 (11_polish-loop 모드 A, 74회차).

대상(프로젝트 cid·영상 eid)을 바꿔 가며 쓰는 화면에서, 비동기 응답이 도착했을 때
화면은 이미 **다른 대상**을 보고 있을 수 있다. 가드 없이 done/fail 이 화면을 쓰면
옛 대상의 대본·설정·문안·오류가 새 화면에 그 대상의 것처럼 얹힌다 — 58회차(배포
문안)·59회차(라이브러리 표)·60회차(작업 큐)가 산발로 고친 그 부류다. 74회차에
`bridge.guard` 관용구로 승격하고 이 클래스로 금지한다.

기계 규칙: `def load(self, <대상>...)` 을 가진 클래스(대상 전환 화면) 안의 모든
run_bg 는, **그 호출을 둘러싼 메서드** 소스에 아래 중 하나가 보여야 한다:
  - `guard(`             — bridge.guard 로 감쌈 (표준)
  - `self.eid ==`·`self.eid !=`·`self.cid ==`·`self.cid !=` — 명시 비교
    (콜백이 여러 일을 하나로 묶을 때 — 잠금 해제는 항상, 화면 기록은 대상 확인 후)
  - `self._req`          — 59회차 토큰 가드 (조회 세대 비교)
  - "A3-허용: <근거>"     — 대상 무관(전역 상태·소재 재생)이거나 완료 동선이
                           화면 이탈이라 되덮을 것이 없는 곳
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
MARKER = "A3-허용"
TOKENS = ("guard(", "self.eid ==", "self.eid !=", "self.cid ==", "self.cid !=",
          "self._req", "_pump_eid", MARKER)
# _pump_eid — 잡 제출 3곳(빌드·AI 초안·AI 평가)의 처방: 제출 시점 eid 를 기록해 두고
# load() 가 다른 영상으로 넘어갈 때 펌프(진행 이벤트)를 통째로 뗀다. 콜백 개별 가드가
# 아니라 이벤트 소스를 자르는 방식이라 이 토큰이 곧 가드다 (episode.load 참조)


def _target_classes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for m in node.body:
                if (isinstance(m, ast.FunctionDef) and m.name == "load"
                        and len(m.args.args) >= 2):   # self + 대상
                    yield node
                    break


def test_target_switching_screens_guard_stale_responses():
    holes = []
    for path in APP.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for cls in _target_classes(tree):
            for m in ast.walk(cls):
                if not isinstance(m, ast.FunctionDef):
                    continue
                seg = ast.get_source_segment(src, m) or ""
                if "run_bg(" not in seg:
                    continue
                if not any(t in seg for t in TOKENS):
                    holes.append(
                        f"{path.relative_to(APP.parent)}:{m.lineno} "
                        f"{cls.name}.{m.name}()")
    assert not holes, (
        "가드 없는 비동기 콜백 — 대상을 옮긴 뒤 도착한 응답이 새 화면을 되덮는다. "
        f"bridge.guard 로 감싸거나 대상을 비교하거나, 무해하면 '{MARKER}: 근거' "
        "주석을 달라:\n" + "\n".join(holes))
