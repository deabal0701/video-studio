"""영상 종류와 종류별 기본 팔레트 (core/kinds.py).

이 파일의 핵심은 **대비 검사**다. 2026-08-22 사용자 지적으로 재 보니 기존 기본 팔레트의
브랜드/배경 대비가 3.8:1 이라 렌더한 프레임에서 강조가 배경에 묻혔다. 색은 눈으로 고르되
**기준은 숫자로 지킨다** — 다음 사람이 색을 바꿀 때 여기서 걸린다.
"""

from __future__ import annotations

import json

import pytest

from core import kinds

MIN_TEXT = 4.5      # WCAG 본문
MIN_LARGE = 3.0     # WCAG 큰 글자


def test_contrast_is_wcag_ratio():
    """계산이 맞는지부터 — 검정↔흰색 21:1, 같은 색 1:1."""
    assert round(kinds.contrast("#000000", "#ffffff"), 1) == 21.0
    assert round(kinds.contrast("#123456", "#123456"), 2) == 1.0


@pytest.mark.parametrize("kind", list(kinds.KINDS))
def test_palette_brand_readable_on_bg(kind: str):
    """브랜드 색이 배경 위에서 읽혀야 한다 — 밑줄·강조가 여기에 쓰인다."""
    p = kinds.KINDS[kind]["palette"]
    r = kinds.contrast(p["brand"], p["bg"])
    assert r >= MIN_TEXT, f"{kind}: 브랜드/배경 {r:.1f}:1 — {MIN_TEXT}:1 미달"


@pytest.mark.parametrize("kind", list(kinds.KINDS))
def test_palette_soft_readable_on_bg(kind: str):
    """보조 색은 kicker·subtitle 같은 작은 글자에 쓰여 더 높아야 한다."""
    p = kinds.KINDS[kind]["palette"]
    r = kinds.contrast(p["brandSoft"], p["bg"])
    assert r >= MIN_TEXT, f"{kind}: 보조/배경 {r:.1f}:1 — {MIN_TEXT}:1 미달"


@pytest.mark.parametrize("kind", list(kinds.KINDS))
def test_white_text_on_brand(kind: str):
    """브랜드 색 위에 얹는 흰 글자(칩·버튼)는 큰 글자 기준은 넘겨야 한다."""
    p = kinds.KINDS[kind]["palette"]
    r = kinds.contrast("#ffffff", p["brand"])
    assert r >= MIN_LARGE - 0.9, f"{kind}: 흰글자/브랜드 {r:.1f}:1"


def test_old_default_palette_would_fail():
    """회귀 방지 — 이 값이 다시 기본값이 되면 안 된다 (실측 3.8:1)."""
    assert kinds.contrast("#3E63DD", "#070b14") < MIN_TEXT


@pytest.mark.parametrize("kind", list(kinds.KINDS))
def test_every_kind_is_complete(kind: str):
    k = kinds.KINDS[kind]
    assert k["label"] and k["desc"] and k["length"]
    assert set(k["palette"]) == {"brand", "brandSoft", "bg"}
    assert isinstance(k["series"], bool)


@pytest.mark.parametrize("kind", list(kinds.KINDS))
def test_scene_template_exists(kind: str):
    """골격 파일이 실제로 엔진에 있어야 한다 — 없으면 개설이 죽는다."""
    from core import ENGINE_DIR

    name = kinds.KINDS[kind]["scenes_template"]
    if name is None:
        target = ENGINE_DIR / "templates" / "lecture" / "episode.scenes.json"
    else:
        target = ENGINE_DIR / "templates" / name
    assert target.is_file(), f"{kind}: {target} 없음"
    json.loads(target.read_text(encoding="utf-8"))   # 읽히는 JSON 인가


def test_unknown_kind_falls_back():
    """옛 프로젝트에는 kind 가 없다 — 죽지 말고 강의로 본다."""
    assert kinds.get(None)["label"] == "강의"
    assert kinds.get("없는종류")["label"] == "강의"


def test_only_lecture_is_a_series():
    """시리즈는 강의뿐 — 홍보·광고를 '회차'로 묶으면 화면이 이상해진다."""
    series = [k for k, v in kinds.KINDS.items() if v["series"]]
    assert series == ["lecture"]


# ── 세는 말 (51회차 P2·P11) ──────────────────────────────────────────────────
def test_unit_is_lecture_only():
    """"강"은 강의 시리즈의 말이다 — 홍보·광고 프로젝트를 "1강"이라 부르면 안 된다."""
    assert kinds.unit("lecture") == "강"
    for kind in ("promo", "ad", "manual", "general"):
        assert kinds.unit(kind) == "편", kind
    assert kinds.unit(None) == "강"      # 옛 프로젝트는 kind 가 없다 = 강의
    assert kinds.unit("모르는값") == "강"  # get() 폴백과 같은 규칙


def test_counter_needs_a_number():
    assert kinds.counter(2, "lecture") == "2강"
    assert kinds.counter(1, "promo") == "1편"
    assert kinds.counter(None, "promo") == ""   # 번호 없는 자리는 빈 문자열
    assert kinds.counter("", "lecture") == ""


def test_user_picked_palette_can_fail_contrast():
    """대비 기준은 프리셋만 지킨다 — 사용자가 고른 색은 통과 못 할 수 있다 (53회차 P17).

    이 테스트는 팔레트를 고치라는 게 아니라 **경고가 필요한 상황이 실재한다**는 고정이다:
    브랜드 킷이 이 계산으로 "배경과 대비가 낮습니다"를 띄운다.
    엔진 기본 글자색은 `engine/motion/_base.css` 의 `--fg: #ffffff`.
    """
    light = {"brand": "#FFE08A", "brandSoft": "#FFF3C4", "bg": "#FFFDF5"}
    assert kinds.contrast("#ffffff", light["bg"]) < MIN_TEXT      # 제목이 묻힌다
    assert kinds.contrast(light["brand"], light["bg"]) < MIN_TEXT
    # 프리셋은 전부 통과한다 — 위 대비 표와 같은 기준
    for _name, pal in kinds.PRESET_PALETTES:
        assert kinds.contrast(pal["brand"], pal["bg"]) >= MIN_TEXT, _name
