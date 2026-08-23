"""skill_prompts — 스킬 문서에서 규약 절을 발췌해 시스템 프롬프트를 조립한다 (D18).

정본은 `.claude/skills/` 의 md 문서다 — 여기에는 **어떤 절을 어느 작업에 주입하나**(목록)만
있다. 규약을 코드로 복제하지 않는다(원칙 3) — 스킬을 고치면 에이전트가 따라온다.

절차(명령·경로·앱 조작)는 주입하지 않는다: 도구 없는 모델에게 실행 지시를 주면 지어내거나
금지된 일(경로 수작업 — 02 함정 5종)을 시도한다. 발췌는 제목(heading) 접두 매칭이라 스킬에서
제목이 바뀌면 즉시 KeyError 가 나고, tests/test_skill_prompts.py 가 그 표류를 잡는다.

주의 — 페이스 상수: develop-video 는 초당 6.3자(표준), develop-lecture 는 6.4자(강좌 —
한 단계 빠른 의도된 덮어쓰기). 두 문서를 함께 주입하면 모순으로 보이므로 **종류별로
한쪽만** 조립한다 (05_agent "규약 주입").
"""

from __future__ import annotations

import re
from pathlib import Path

from .. import env

SKILLS_DIR = env.INSTALL_DIR / ".claude" / "skills"
VIDEO_SKILL = SKILLS_DIR / "develop-video" / "SKILL.md"
LECTURE_SKILL = SKILLS_DIR / "develop-lecture" / "SKILL.md"
AUTHORING = SKILLS_DIR / "develop-video" / "references" / "authoring.md"
REVIEWER = SKILLS_DIR / "develop-video" / "agents" / "reviewer.md"

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"스킬 문서가 없습니다: {path} — 설치본 동봉물(D18)")
    return path.read_text(encoding="utf-8")


def _section(text: str, title: str, *, deep: bool = True) -> str:
    """제목이 title 로 시작하는 절을 돌려준다.

    deep=True  : 같은/상위 레벨의 다음 제목 전까지 (하위 절 포함)
    deep=False : 다음 제목(레벨 불문) 전까지 — 상위 절의 도입부만
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if not (m and m.group(2).strip().startswith(title)):
            continue
        level = len(m.group(1))
        for j in range(i + 1, len(lines)):
            m2 = _HEADING.match(lines[j])
            if m2 and (not deep or len(m2.group(1)) <= level):
                return "\n".join(lines[i:j]).strip()
        return "\n".join(lines[i:]).strip()
    raise KeyError(f"스킬에서 절을 찾지 못했습니다: {title!r} — 제목이 바뀌었으면 "
                   f"skill_prompts 의 목록을 함께 고치세요")


# ── 발췌 목록 — (파일, 제목 접두, deep). 제목이 스킬에서 바뀌면 여기도 고친다 ──
DRAFT_COMMON = [
    (VIDEO_SKILL, "대본을 쓰기 전에", True),                    # 구성표 먼저 — 화면 칸·글자수 배분
    (VIDEO_SKILL, "개념을 설명하는 구간에는 도식을 그린다", True),
    (VIDEO_SKILL, "지켜야 할 선", True),                        # 저작권·초상권·근거 없는 문구 금지
]
DRAFT_LECTURE = [
    (LECTURE_SKILL, "회차는 독립이다", True),
    (LECTURE_SKILL, "분량", True),                              # 6.4자/초 · 1,850자 예산
    (LECTURE_SKILL, "인트로", True),                            # 영상 → 제목 → 훅 → 시그니처
    (LECTURE_SKILL, "깊이", True),
    (LECTURE_SKILL, "재미", True),
    (LECTURE_SKILL, "자료조사", True),
    (LECTURE_SKILL, "일관성 점검", True),
]
DIAGRAM_SECTIONS = [
    (AUTHORING, "모션그래픽 구간", False),                       # 템플릿 계약·data-p 규칙·도식 표
    # ★ 이 절이 빠져 있었다 (2026-08-23): 공용 _base.css 참조 규칙·params 리터럴 조회·
    #   키프레임 함정 셋이 전부 여기 있다. 없이 보냈더니 모델이 경로를 지어냈고, 스킬이
    #   경고한 그대로 "스타일 없는 맨 HTML" 이 찍혀 브랜드 색이 통째로 어긋났다.
    (AUTHORING, "한 영상에서만 쓰는 전용 도식", True),
    (AUTHORING, "반드시 지켜야 할 것", True),                    # animation 단축 금지·가운데 절반 등
    (VIDEO_SKILL, "개념을 설명하는 구간에는 도식을 그린다", True),
]


def _assemble(sections: list[tuple[Path, str, bool]]) -> str:
    texts: dict[Path, str] = {}
    out = []
    for path, title, deep in sections:
        if path not in texts:
            texts[path] = _read(path)
        out.append(_section(texts[path], title, deep=deep))
    return "\n\n---\n\n".join(out)


# 발췌 앞에 붙는 역할 선언 — 도구가 없다는 사실을 명시해 실행 지시 오독을 막는다.
_NO_TOOLS = ("당신에게 파일·명령·웹 도구는 없다 — 요청된 내용(텍스트)만 반환하고, "
             "파일 기입·경로 계산·렌더는 앱이 수행한다. 아래 제작 규약 중 절차(명령 실행· "
             "폴더 규칙)는 앱이 이미 지키고 있으니, 당신은 **저작 규약**만 따른다.")


def draft_rules(*, series: bool) -> str:
    role = ("당신은 유튜브 강좌 회차의 대본 작가다. " if series
            else "당신은 단발 영상(홍보·광고·매뉴얼·일반)의 대본 작가다. ")
    body = _assemble(DRAFT_COMMON + (DRAFT_LECTURE if series else []))
    return f"{role}{_NO_TOOLS}\n\n{body}"


# 색은 **프로젝트 팔레트**에서 온다 — 공용 `_base.css` 가 CSS 변수로 정의하고 `_params.js` 가
# 클립 params(brand·brandSoft·bg)로 덮어쓴다. 모델이 색을 직접 박으면 회차마다 딴 영상이 된다
# (2026-08-23 실측: 보라·분홍 그라디언트 도식이 파랑 강좌에 섞여 나왔다).
_PALETTE_RULE = (
    "색은 **직접 정하지 마라.** 배경·강조·글자색은 공용 스타일의 CSS 변수만 쓴다 — "
    "var(--bg) 배경 · var(--brand) 강조 · var(--brand-soft) 보조 강조 · var(--fg) 글자. "
    "16진수 색 리터럴이나 linear-gradient 로 배경을 새로 만들지 마라. "
    "공용 스타일 링크는 **앱이 기입하므로 경로를 쓰지 마라** — `_base.css` 와 `_params.js` 를 "
    "그 맨이름 그대로 참조하면 앱이 올바른 상대경로로 바꾼다.")


def diagram_rules(palette: dict | None = None) -> str:
    role = ("당신은 영상 설명 구간의 모션 도식(html 1장)을 만든다. "
            "CSS 키프레임만 쓴다(rAF·`<video>`·외부 리소스 금지 — 스크럽 렌더 제약). "
            "발화 시각(초당 약 6.4자로 역산)에 요소 등장 delay 를 맞춘다. ")
    tail = ""
    if palette:
        vals = " · ".join(f"{k}={v}" for k, v in palette.items() if v)
        if vals:
            tail = f"\n\n이 프로젝트 팔레트(참고용 — 값을 박지 말고 변수를 써라): {vals}"
    return f"{role}{_NO_TOOLS}\n\n{_PALETTE_RULE}{tail}\n\n{_assemble(DIAGRAM_SECTIONS)}"


def review_rules() -> str:
    """평가는 reviewer.md 전문 — 단, 프론트매터와 도구 전제를 걷어낸다."""
    text = _read(REVIEWER)
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:].lstrip()
    role = ("당신은 완성된 영상의 평가자다. 첨부된 검수 프레임 이미지들만 보고 판단한다 — "
            "파일·명령 도구는 없다. 아래 지침의 절차(Bash·경로·기록 파일 편집)는 무시하고 "
            "**평가 기준과 원칙**만 따른다. 낮은 점수를 감추지 않는다.")
    return f"{role}\n\n{text}"


def health() -> dict:
    """자가진단용 — 스킬 동봉·발췌 성공 여부 (config.diagnose 의 한 행)."""
    try:
        draft_rules(series=True)
        draft_rules(series=False)
        diagram_rules()
        review_rules()
        return {"ok": True, "detail": str(SKILLS_DIR)}
    except (FileNotFoundError, KeyError) as err:
        return {"ok": False, "detail": str(err)}
