"""대본 예산 — 골격의 "[…]" 안내문은 아직 쓴 글이 아니다 (54회차 P11).

시작 패널은 이 규칙으로 "대본이 아직 비어 있습니다"라고 하는데 예산 게이지만
자리표시자까지 세서 같은 화면이 "232자 (13%)"라고 말했다. 규칙을 한 함수로 모았으니
여기서 고정한다 — 화면(Qt)을 띄우지 않고 순수 함수만 검증한다.
"""

from __future__ import annotations

from app.pages.clip_editor import clip_seconds, spoken


def test_placeholder_is_not_written_script():
    assert spoken({"narration": "[회차 훅 — 콜드 오픈. 구체적 장면으로]"}) == ""
    assert spoken({"narration": "   [약속 도식 — 오늘 얻어갈 것]  "}) == ""
    assert spoken({"narration": ""}) == ""
    assert spoken({}) == ""


def test_real_narration_counts():
    assert spoken({"narration": "인사 데이터는 사람에서 시작합니다."}) == \
        "인사 데이터는 사람에서 시작합니다."
    # 대괄호가 문장 **안**에 있는 것은 자리표시자가 아니다 (시작 위치만 본다)
    assert spoken({"narration": "연차[年次]는 이렇게 쌓입니다"}) == "연차[年次]는 이렇게 쌓입니다"


def test_clip_seconds_ignores_placeholder_but_keeps_duration():
    """자리표시자는 길이 추정에 안 들어간다 — 다만 클립 자체 duration 은 남는다."""
    ph = {"id": "hook", "narration": "[회차 훅 — 콜드 오픈]", "duration": 3.0}
    assert clip_seconds(ph, {}) == (3.0, True)      # 추정할 글이 없으니 '실측'으로 본다
    real = {"id": "hook", "narration": "가" * 63, "duration": 3.0}
    secs, measured = clip_seconds(real, {})
    assert secs > 3.0 and not measured               # 63자면 3초를 넘는다
    # TTS 실측이 있으면 자리표시자든 아니든 실측이 이긴다
    assert clip_seconds(ph, {"hook": 7.0}) == (7.5, True)
