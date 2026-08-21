"""plan_apply — 구성표(plan.md)의 구간 행 → 클립 골격 반영 (04: POST plan/apply, 03 ④).

표의 행이 ⑤ 의 클립 골격이 된다. 이미 있는 클립은 건드리지 않는다(사람 편집 우선) —
없는 구간만 표의 순서 자리에 골격 클립으로 끼워 넣고, 글자수 컬럼은 `_목표글자수`
주석 필드로 넘긴다 (글자수 예산이 클립별 목표로 넘어가는 규약).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .scaffold import _inject_params
from .schema import Document, load_json

SECTION = "## 구간 배분"
_TOKEN = re.compile(r"`([^`]+)`")


def parse_plan_rows(markdown: str) -> list[dict[str, Any]]:
    """구간 배분 섹션의 첫 표를 [{id, screen, chars}] 로. 헤더에 '구간'과 '화면'이 있어야 한다."""
    lines = markdown.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().startswith(SECTION))
    except StopIteration:
        return []
    header: list[str] = []
    rows: list[dict[str, Any]] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if header and rows:
                break  # 표가 끝났다
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= {"-", " ", ":"} for c in cells):
            continue
        if not header:
            if any("구간" in c for c in cells) and any("화면" in c for c in cells):
                header = cells
            continue
        row = dict(zip(header, cells))
        rid = re.sub(r"[`* ]", "", next((v for k, v in row.items() if "구간" in k), ""))
        chars_raw = re.sub(r"\D", "", next((v for k, v in row.items() if "글자수" in k), ""))
        rows.append({
            "id": rid,
            "screen": next((v for k, v in row.items() if "화면" in k), ""),
            "chars": int(chars_raw) if chars_raw else None,
        })
    return rows


def _screen_to_clip(cell: str, ep_dir: Path) -> dict[str, Any]:
    m = _TOKEN.search(cell)
    token = m.group(1) if m else ""
    if not token or "<" in token:
        return {"file": ""}
    if token.endswith(".html"):
        local = ep_dir / "motion" / token
        return {"file": f"motion/{token}" if local.exists() else token}
    if re.search(r"\.(mp4|mov|webm)$", token):
        # B롤/실사 — 엔진 루트 기준 참조 (02 경로 표)
        return {"video": f"assets/broll/{Path(token).name}", "videoStart": 0,
                "shade": 0.35, "duration": 2.0}
    return {"file": ""}


def apply(ep_dir: Path) -> dict[str, Any]:
    plan_file = ep_dir / "plan.md"
    if not plan_file.exists():
        raise FileNotFoundError("plan.md 없음")
    rows = [r for r in parse_plan_rows(plan_file.read_text(encoding="utf-8"))
            if r["id"] and "합계" not in r["id"] and "<" not in r["id"]]

    doc = Document.load(ep_dir / "scenes.json")
    clips: list[dict[str, Any]] = doc.data["render"]["motion"]["clips"]
    ids = {c["id"]: i for i, c in enumerate(clips)}

    course_id = ep_dir.name.rsplit("-", 1)[0]
    course_file = ep_dir.parent / course_id / "course.json"
    palette = (load_json(course_file).get("palette", {}) if course_file.exists() else {})

    added: list[str] = []
    prev = -1
    for row in rows:
        if row["id"] in ids:
            prev = ids[row["id"]]
            continue
        clip: dict[str, Any] = {"id": row["id"], **_screen_to_clip(row["screen"], ep_dir),
                                "before": "end", "narration": ""}
        if row["chars"]:
            clip["_목표글자수"] = row["chars"]  # 예산이 클립별 목표로 (주석 필드 — 엔진 무관)
        if "video" not in clip:
            _inject_params(clip, palette, ep_dir)
        clips.insert(prev + 1, clip)
        ids = {c["id"]: i for i, c in enumerate(clips)}
        prev = ids[row["id"]]
        added.append(row["id"])
    if added:
        doc.save()
    return {"added": added, "rows": len(rows)}
