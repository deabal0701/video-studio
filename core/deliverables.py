"""deliverables — 배포 산출물 (03 ⑦: youtube.md 를 수동 작성에서 자동 생성으로).

제목 = `[강좌명] n강 — 제목` · 설명 = 요약+챕터+재생목록 자리 · 챕터 = chapters.js 실측 ·
srt = final 산출물 · 썸네일 후보 = 검수 프레임. 자막 대조(.srt ↔ 대본)도 여기 —
"빌드가 도는 동안이 검증 시간" 검수 자동화의 마지막 조각.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import engine_io
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
    try:
        chapter_lines = [l for l in engine_io.chapters(eid, projects_root).splitlines()
                         if re.match(r"^\d\d:\d\d ", l)]
    except Exception as err:  # noqa: BLE001 — 캐시 없음 등은 빈 챕터로 가되, 사유는 드러낸다
        chapter_lines = []
        chapters_error = str(err)[-300:]  # 조용히 비면 배포물이 반쪽 — 화면이 사유를 보여준다 (07 결함 4)

    course_title = course.get("title", "")
    title = f"[{course_title}] {n}강 — {ep_title}" if course_title else f"{eid} — {ep_title}"
    promise = next((c.get("narration", "") for c in
                    scenes.get("render", {}).get("motion", {}).get("clips", [])
                    if c.get("id") == "promise"), "")
    description = "\n".join(filter(None, [
        promise,
        "",
        "⏱ 챕터", *chapter_lines,
        "",
        f"▶ 재생목록: {course_title} (링크 자리)" if course_title else "",
        course.get("tagline", ""),
    ]))

    final_dir = OUT_ROOT / eid / "final"
    srt = sorted(final_dir.glob("*.srt")) if final_dir.exists() else []
    frames_dir = OUT_ROOT / eid / "frames"
    thumbs = sorted(frames_dir.glob("review-*.jpg")) if frames_dir.exists() else []

    return {
        "title": title,
        "description": description,
        "chapters": chapter_lines,
        "chaptersError": chapters_error,
        "srt": [f.name for f in srt],
        "thumbnails": [f.name for f in thumbs],
        "subtitle": ep_subtitle,
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
