"""validate — 기계화 가능한 검증만 (원칙 3: 제작 규약의 정본은 스킬 문서).

글자수 예산 · voice/render 일관성 대조 · params/경로 검사. 정적 검사의 본체는
engine/inspect.js(preflight)이고, 여기는 엔진이 못 보는 것(강좌 일관성·예산)을 맡는다.
1~2단계에서 채운다.
"""

from __future__ import annotations

import re
from typing import Any

from . import kinds

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
        problems.append("목소리(voice) 값이 프로젝트 설정과 다릅니다")
    for key, want in (course.get("render") or {}).items():
        if scenes.get("render", {}).get(key) != want:
            problems.append(f"{kinds.render_label(key)} 값이 프로젝트 설정과 다릅니다")
    return problems


# ── 초안 결함 — 엔진 preflight 가 못 보는 것 (빌드 제출 시점에 차단) ────────────
# 자리표시자 규칙: 골격 템플릿·AI 초안이 대괄호 [ ] 로 미확정 값을 표시한다.
# `_` 접두 키는 사람용 주석이라(라운드트립 규약) 대괄호가 있어도 결함이 아니다.
_PLACEHOLDER = re.compile(r"\[[^\[\]]+\]")

# 자리표시자를 검사하는 값 필드 — 화면·소리에 그대로 새어 나가는 것들만.
_TEXT_FIELDS = ("narration", "caption", "file", "video")


def _placeholder_fields(entry: dict[str, Any]) -> list[str]:
    hits = [f for f in _TEXT_FIELDS
            if isinstance(entry.get(f), str) and _PLACEHOLDER.search(entry[f])]
    hits += [f"params.{k}" for k, v in (entry.get("params") or {}).items()
             if not k.startswith("_") and isinstance(v, str) and _PLACEHOLDER.search(v)]
    return hits


def draft_defects(scenes: dict[str, Any]) -> list[str]:
    """빌드하면 반드시 망가지는 초안 결함 2종 — 담당자 언어로 말한다.

    ① 대본 클립이 최상위 scenes(앱 화면 녹화 씬 자리)에 있음 — 녹화 씬은 actions 로
       앱을 조작하고, 클립은 file/video 로 화면을 만든다. actions 없는 항목이 scenes 에
       있으면 클립이 잘못 들어온 것 — 엔진이 존재하지 않는 앱을 녹화하려다 실패한다.
    ② 대괄호 [자리표시자] 잔존 — TTS 가 그대로 읽고, 없는 파일 경로는 조용히 검은
       화면이 된다. (실측: AI 초안이 둘 다 낸 2026-08-23 결함.)
    """
    problems: list[str] = []
    misplaced = [s.get("id", "?") for s in scenes.get("scenes", [])
                 if not s.get("actions")]
    if misplaced:
        problems.append(
            f"대본 구간 {len(misplaced)}개({'·'.join(misplaced[:4])}"
            + (" 등" if len(misplaced) > 4 else "")
            + ")가 화면 녹화 자리(scenes)에 저장돼 있습니다 — 대본 클립(render.motion.clips)으로 옮겨야 합니다")
    for entry in list(scenes.get("scenes", [])) + list(
            scenes.get("render", {}).get("motion", {}).get("clips", [])):
        fields = _placeholder_fields(entry)
        if fields:
            problems.append(
                f"{kinds.role_label(entry.get('id'))}({entry.get('id', '?')}) 구간에 "
                f"아직 정하지 않은 [자리표시자] 값이 있습니다: {', '.join(fields)}")
    return problems
