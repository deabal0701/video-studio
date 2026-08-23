"""deliverables — 배포 산출물 (03 ⑦: youtube.md 를 수동 작성에서 자동 생성으로).

제목 = `[강좌명] n강 — 제목` · 설명 = 요약+챕터+재생목록 자리 · 챕터 = chapters.js 실측 ·
srt = final 산출물 · 썸네일 후보 = 검수 프레임. 자막 대조(.srt ↔ 대본)도 여기 —
"빌드가 도는 동안이 검증 시간" 검수 자동화의 마지막 조각.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import engine_io, kinds
from .schema import load_json
from .status import OUT_ROOT


def _episode_meta(episode_dir: Path) -> tuple[dict, dict, int, str, str]:
    scenes = load_json(episode_dir / "scenes.json")
    course_id = episode_dir.name.rsplit("-", 1)[0]
    course_file = episode_dir.parent / course_id / "course.json"
    course = load_json(course_file) if course_file.exists() else {}
    entry = next((e for e in course.get("episodes", [])
                  if e.get("id") == episode_dir.name), {})
    n = entry.get("n") or int(re.sub(r"\D", "", episode_dir.name.split("-")[-1]) or 0)
    return scenes, course, n, entry.get("title", ""), entry.get("subtitle", "")


def build(episode_dir: Path, projects_root: Path) -> dict[str, Any]:
    eid = episode_dir.name
    scenes, course, n, ep_title, ep_subtitle = _episode_meta(episode_dir)

    chapters_error = None
    chapters_reason = None   # "no_cards"(정상 — 챕터 카드 없는 대본) | "error"
    try:
        chapter_lines = [l for l in engine_io.chapters(eid, projects_root).splitlines()
                         if re.match(r"^\d\d:\d\d ", l)]
    except Exception as err:  # noqa: BLE001 — 사유를 구분해 내린다 (75회차 A4)
        chapter_lines = []
        # 챕터 카드가 대본에 없는 것은 **오류가 아니다** — 홍보·광고 골격은 원래
        # 챕터 없이 태어난다. 갓 만든 영상의 기본 상태가 빨간 오류로 보였고, node
        # 명령줄·경로가 화면에 날것으로 떴다 (75회차 A4 프로브 실측)
        if "대본에 없다" in str(err):
            chapters_reason = "no_cards"
        else:
            chapters_reason = "error"
            chapters_error = str(err)[-300:]  # 화면은 요약을 말하고 이 원문은 툴팁으로

    course_title = course.get("title", "")
    # `[강좌명] N강 — 제목` 은 **시리즈**의 문법이다 (대괄호=재생목록, N강=회차).
    # 단발 홍보·광고 영상에는 둘 다 뜻이 없고, 제목이 프로젝트 이름과 같은 것이 보통이라
    # 그대로 두면 "[인사잇 소개] — 인사잇 소개" 처럼 겹쳐 나온다 (51회차 P2)
    if not course_title:
        title = f"{eid} — {ep_title}"
    elif kinds.get(course.get("kind"))["series"]:
        title = f"[{course_title}] {kinds.counter(n, course.get('kind'))} — {ep_title}"
    else:
        title = ep_title or course_title
    promise = next((c.get("narration", "") for c in
                    scenes.get("render", {}).get("motion", {}).get("clips", [])
                    if c.get("id") == "promise"), "")
    description = "\n".join(filter(None, [
        promise,
        "",
        # 챕터가 없으면 헤더도 넣지 않는다 — 빈 "⏱ 챕터" 섹션이 초안에 남았다 (75회차 A4)
        *(["⏱ 챕터", *chapter_lines] if chapter_lines else []),
        "",
        f"▶ 재생목록: {course_title} (링크 자리)" if course_title else "",
        course.get("tagline", ""),
    ]))

    # 파일이 SSOT — 담당자가 고쳐 저장한 youtube.md 가 있으면 그것이 정본이다.
    # 안 읽으면 화면이 매번 생성 초안으로 되돌아가 저장한 문안 위에 초안을
    # 다시 저장하는 사고가 난다 (루프 26회차 P21)
    saved = False
    md = episode_dir / "youtube.md"
    if md.exists():
        lines = md.read_text(encoding="utf-8").splitlines()
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            rest = lines[1:]
            while rest and not rest[0].strip():
                rest.pop(0)
            description = "\n".join(rest).rstrip()
            saved = True

    final_dir = OUT_ROOT / eid / "final"
    srt = sorted(final_dir.glob("*.srt")) if final_dir.exists() else []
    frames_dir = OUT_ROOT / eid / "frames"
    thumbs = sorted(frames_dir.glob("review-*.jpg")) if frames_dir.exists() else []

    return {
        "title": title,
        "description": description,
        "chapters": chapter_lines,
        "chaptersError": chapters_error,
        "chaptersReason": chapters_reason,
        "srt": [f.name for f in srt],
        "thumbnails": [f.name for f in thumbs],
        "subtitle": ep_subtitle,
        "saved": saved,
    }


def write_youtube_md(episode_dir: Path, title: str, description: str) -> Path:
    """youtube.md 저장 — 배포 준비물의 파일 정본 (02 파일 지도)."""
    out = episode_dir / "youtube.md"
    out.write_text(f"# {title}\n\n{description}\n", encoding="utf-8", newline="\n")
    return out


_SRT_TEXT = re.compile(r"^(?:\d+|[\d:,]+ --> [\d:,]+)\s*$")
_NORM = re.compile(r"[\s\u00a0]+")


def subtitle_check(episode_dir: Path) -> dict[str, Any]:
    """자막 대조 — .srt 텍스트 ↔ 대본 내레이션. 공백 무시 완전 일치가 목표 (diff 0)."""
    eid = episode_dir.name
    final_dir = OUT_ROOT / eid / "final"
    srts = sorted(final_dir.glob("*.srt")) if final_dir.exists() else []
    if not srts:
        return {"ok": False, "reason": "srt 없음 — 먼저 빌드하세요"}
    lines = [l for l in srts[0].read_text(encoding="utf-8").splitlines()
             if l.strip() and not _SRT_TEXT.match(l)]
    srt_text = _NORM.sub("", "".join(lines))

    scenes = load_json(episode_dir / "scenes.json")
    parts = [c.get("narration", "") for c in
             scenes.get("render", {}).get("motion", {}).get("clips", [])]
    parts += [s.get("narration", "") for s in scenes.get("scenes", [])]
    end_card = scenes.get("render", {}).get("endCard") or {}
    parts.append(end_card.get("narration", ""))
    script_text = _NORM.sub("", "".join(parts))

    if srt_text == script_text:
        return {"ok": True, "chars": len(script_text), "srt": srts[0].name}
    # 첫 어긋남 위치의 앞뒤를 보여 준다 — 사람이 바로 찾게
    i = next((k for k, (a, b) in enumerate(zip(srt_text, script_text)) if a != b),
             min(len(srt_text), len(script_text)))
    return {"ok": False, "srt": srts[0].name,
            "reason": f"{i}번째 글자부터 다름",
            "srtAround": srt_text[max(0, i - 15):i + 15],
            "scriptAround": script_text[max(0, i - 15):i + 15],
            "srtChars": len(srt_text), "scriptChars": len(script_text)}
