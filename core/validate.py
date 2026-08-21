"""validate — 기계화 가능한 검증만 (원칙 3: 제작 규약의 정본은 스킬 문서).

글자수 예산 · voice/render 일관성 대조 · params/경로 검사. 정적 검사의 본체는
engine/inspect.js(preflight)이고, 여기는 엔진이 못 보는 것(강좌 일관성·예산)을 맡는다.
1~2단계에서 채운다.
"""

from __future__ import annotations

from typing import Any

# 페이스 (02_data-model "길이·분량 계산" — build.js 규칙과 동일해야 함)
CHARS_PER_SEC_LECTURE = 6.4


def narration_total(scenes: dict[str, Any]) -> int:
    """대본 전체 내레이션 글자수 — 예산 게이지의 원천."""
    total = 0
    for clip in scenes.get("render", {}).get("motion", {}).get("clips", []):
        total += len(clip.get("narration", ""))
    for scene in scenes.get("scenes", []):
        total += len(scene.get("narration", ""))
    end_card = scenes.get("render", {}).get("endCard") or {}
    total += len(end_card.get("narration", ""))
    return total


def consistency(scenes: dict[str, Any], course: dict[str, Any]) -> list[str]:
    """규약: 회차 scenes.voice ≡ course.voice ∧ scenes.render ⊇ course.render."""
    problems: list[str] = []
    if course.get("voice") and scenes.get("voice") != course["voice"]:
        problems.append("voice 가 course.json 과 다르다")
    for key, want in (course.get("render") or {}).items():
        if scenes.get("render", {}).get(key) != want:
            problems.append(f"render.{key} 가 course.json 과 다르다")
    return problems
