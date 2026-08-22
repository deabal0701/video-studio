"""영상 종류 — 이 앱은 강의만 만들지 않는다.

엔진은 처음부터 여러 골격을 갖고 있었는데(`engine/templates/`) **앱이 강의 하나만 쓰고
있었다**(2026-08-22 사용자 지적). 종류를 고르면 골격·길이·색이 함께 따라온다.

## 왜 종류마다 색이 다른가

기본 팔레트가 `#3E63DD/#93A4F5/#070b14`(파랑) 하나였는데, **브랜드 색과 배경의 대비가
3.8:1** 로 WCAG 본문 기준(4.5:1)에 미달했다. 실제로 렌더한 프레임에서 밑줄·강조가 배경에
묻히고, "밝은 장면" 검수 프레임조차 어두웠다. 아래 값은 전부 **대비를 먼저 맞추고**
성격을 입힌 것이다 — `tests/test_kinds.py` 가 4.5:1 을 지킨다.

| 종류 | 브랜드/배경 | 보조/배경 |
|---|---|---|
| 강의 | 5.8:1 | 10.9:1 |
| 홍보 | 6.9:1 | 11.5:1 |
| 광고 | 6.2:1 | 10.9:1 |
| 매뉴얼 | 5.8:1 | 10.9:1 |
| 일반 | 8.2:1 | 13.3:1 |
"""

from __future__ import annotations

from typing import Any

# 엔진 템플릿 (engine/templates/) 기준 상대 경로. 강의만 폴더 구조를 쓴다.
KINDS: dict[str, dict[str, Any]] = {
    "lecture": {
        "label": "강의",
        "desc": "여러 편을 담는 프로젝트가 만들어집니다 — 영상은 안에서 편마다 추가합니다",
        "series": True,                       # 여러 영상을 묶는다
        "scenes_template": None,              # lecture/episode.scenes.json (기본)
        "length": "5분 (약 1,850자)",
        "palette": {"brand": "#5B8DEF", "brandSoft": "#A9C6FF", "bg": "#0B1220"},
    },
    "promo": {
        "label": "홍보",
        "desc": "영상 1편이 바로 만들어집니다 — 제품·서비스 소개, 짧고 선명하게",
        "series": False,
        "scenes_template": "scenes.promo.json",
        "length": "30초 (약 190자)",
        "palette": {"brand": "#F97316", "brandSoft": "#FDBA74", "bg": "#140B05"},
    },
    "ad": {
        "label": "광고",
        "desc": "영상 1편이 바로 만들어집니다 — 한 가지만 각인시키는 아주 짧게",
        "series": False,
        "scenes_template": "scenes.promo.json",   # 골격은 홍보와 같고 길이가 다르다
        "length": "15초 (약 95자)",
        "palette": {"brand": "#FF4D6D", "brandSoft": "#FFA8B8", "bg": "#12060A"},
    },
    "manual": {
        "label": "사용 매뉴얼",
        "desc": "영상 1편이 바로 만들어집니다 — 단계마다 챕터 카드가 들어갑니다",
        "series": False,
        "scenes_template": "scenes.manual.json",
        "length": "2분 (약 760자)",
        "palette": {"brand": "#5B8DEF", "brandSoft": "#A9C6FF", "bg": "#0B1220"},
    },
    "general": {
        "label": "일반 영상",
        "desc": "영상 1편이 바로 만들어집니다 — 타이틀·마무리만 깔리고 나머지는 직접",
        "series": False,
        "scenes_template": None,
        # 강의 골격에서 이것만 남긴다 — 정해진 구성이 없는 영상이므로 (설명과 동작을 맞춘다)
        "keep_clips": ("title", "stinger", "outro"),
        "length": "1분 (약 380자)",
        "palette": {"brand": "#22C55E", "brandSoft": "#86EFAC", "bg": "#0A1410"},
    },
}

DEFAULT_KIND = "lecture"

# 위저드의 원클릭 팔레트 (2026-08-22 사용자: "청·주황·검정·초록 4가지 선택 + 필요시 추가").
# 전부 대비 검증값 — tests/test_kinds.py 가 종류 팔레트와 같은 기준(4.5:1)으로 지킨다.
PRESET_PALETTES = [
    ("파랑", {"brand": "#5B8DEF", "brandSoft": "#A9C6FF", "bg": "#0B1220"}),
    ("주황", {"brand": "#F97316", "brandSoft": "#FDBA74", "bg": "#140B05"}),
    ("초록", {"brand": "#22C55E", "brandSoft": "#86EFAC", "bg": "#0A1410"}),
    ("검정", {"brand": "#F4F4F5", "brandSoft": "#A1A1AA", "bg": "#09090B"}),
]

# 종류 → 기본 프리셋 이름 (위저드 초기 선택)
KIND_PRESET = {"lecture": "파랑", "promo": "주황", "ad": "주황",
               "manual": "파랑", "general": "초록"}


# 영상 길이 — 화면 공용 (위저드·프로젝트 설정이 같은 UX 를 쓴다. 루프 4회차 P11).
# 글자 예산은 약 6.3자/초 실측 페이스로 **계산해서 보여준다** — 고르게 하지 않는다.
LENGTH_CHOICES = ["1분", "2분", "5분", "10분", "15분"]


def length_to_chars(text: str) -> int | None:
    """"15초"·"5분"·"1분 30초" → 글자 예산. 못 읽으면 None."""
    import re

    sec = 0
    for num, unit in re.findall(r"(\d+)\s*(분|초)", str(text or "")):
        sec += int(num) * (60 if unit == "분" else 1)
    return round(sec * 6.3 / 5) * 5 if sec else None


def length_value(text: str) -> str | None:
    """저장값 "5분 (약 1,890자)" — 예산 게이지가 "N자" 를 파싱한다 (plan_tab)."""
    t = str(text or "").strip()
    if not t:
        return None
    chars = length_to_chars(t)
    return f"{t} (약 {chars:,}자)" if chars else t


def length_display(stored: str) -> str:
    """저장값에서 표시부만 — "5분 (약 1,850자 — 초당 6.4자)" → "5분"."""
    return str(stored or "").split(" (")[0].strip()


# 클립 id → 역할 한국어 (10 #8: "broll·hook·ch2 가 뭔지 모르겠다").
# id 는 엔진·대본 규약이라 못 바꾼다 — 화면이 역할을 함께 말해준다.
ROLE_LABELS = {
    "broll": "실사 도입", "title": "타이틀", "hook": "도입 훅",
    "stinger": "로고 전환", "promise": "오늘의 약속", "recap": "정리",
    "outro": "마무리", "intro": "도입", "proof": "핵심 근거",
}


def role_label(clip_id: str | None) -> str:
    """"도입 훅" 같은 역할 이름 — 모르는 id 는 그대로 돌려준다 (죽지 않는다)."""
    cid = str(clip_id or "")
    if cid in ROLE_LABELS:
        return ROLE_LABELS[cid]
    base = cid.rstrip("0123456789ab")
    num = cid[len(base):]
    if base == "ch":
        return f"챕터 {num}" if num else "챕터"
    if base == "s":
        return f"본문 {num}" if num else "본문"
    if base == "b":
        return f"B롤 {num}" if num else "B롤"
    return cid


# 템플릿 파라미터 키 → 한국어 라벨 (루프 6회차 P2 — "progress·wipe 가 뭔가").
# 키 이름은 엔진 계약이라 못 바꾼다 — 화면이 뜻을 함께 말한다. 모르는 키는 그대로.
PARAM_LABELS = {
    "title": "제목", "subtitle": "부제", "kicker": "상단 소제목", "num": "번호",
    "src": "이미지", "progress": "진행 표시", "shade": "어둡기", "wipe": "와이프 전환",
    "caption": "캡션", "label": "라벨", "text": "본문",
}


def param_label(key: str) -> str:
    """"제목 (title)" — 아는 키는 뜻을 앞세우고, 모르는 키는 그대로."""
    k = str(key or "")
    return f"{PARAM_LABELS[k]} ({k})" if k in PARAM_LABELS else k


# 공용 템플릿 html → 표시명 (10: "사용자가 intro.html 을 어떻게 알 수 있는가").
# 파일명은 구현이고, 화면에는 무엇이 그려지는지가 보여야 한다.
TEMPLATE_LABELS = {
    "intro.html": "타이틀 카드", "chapter.html": "챕터 카드", "outro.html": "마무리 카드",
    "course-intro.html": "프로젝트 타이틀 카드", "course-stinger.html": "로고 전환",
}


def screen_label(text: str | None) -> str:
    """구성표 '화면' 칸 — 아는 파일명이면 표시명을 앞세운다 (파일명은 괄호 보조)."""
    t = str(text or "").strip()
    for fname, label in TEMPLATE_LABELS.items():
        if t == fname or t.endswith("/" + fname):
            return f"{label} ({fname})"
    return t


def get(kind: str | None) -> dict[str, Any]:
    """모르는 값이 와도 죽지 않는다 — 옛 프로젝트에는 kind 가 없다."""
    return KINDS.get(kind or DEFAULT_KIND, KINDS[DEFAULT_KIND])


def label(kind: str | None) -> str:
    return get(kind)["label"]


def choices() -> list[tuple[str, str, str]]:
    """(값, 라벨, 설명) — 화면 콤보/라디오가 그대로 쓴다."""
    return [(k, v["label"], v["desc"]) for k, v in KINDS.items()]


# ── 대비 (팔레트를 고칠 때 이 함수로 먼저 재 본다) ───────────────────────────
def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    """WCAG 대비비 — 1(같은 색) ~ 21(검정↔흰색)."""
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
