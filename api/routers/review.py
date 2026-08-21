"""검수 조회 라우터 — 프레임·무음·일관성 (04_api "검증·빌드·검수" GET 행들).

review 체크리스트 기록(GET/PUT /review)은 3단계 검수 자동화와 함께 붙인다.
"""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from core import deliverables as deliv
from core import media_ops, paths, schema, validate
from core.status import OUT_ROOT
from .. import deps

router = APIRouter(prefix="/api/episodes", tags=["review"])


class BgFrameRequest(BaseModel):
    video: str          # B롤 참조 (엔진 루트 기준 — clip.video 값 그대로)
    videoStart: float = 0
    clipFile: str       # title 클립의 file — src 의 기준(html 위치) 계산용


@router.post("/{eid}/bg-frame")
def bg_frame(eid: str, body: BgFrameRequest) -> dict:
    """B롤 프레임 → bg/ 저장 → 그 html 기준의 src 상대경로 반환 (⑤ title 특수 버튼)."""
    d = deps.episode_dir_or_404(eid)
    source = paths.invert(paths.RefKind.BROLL, body.video)
    if not source.exists():
        raise HTTPException(404, detail={"code": "broll_not_found", "message": body.video})
    html = paths.invert(paths.RefKind.MOTION, body.clipFile, scenes_dir=d)
    if not html.exists():
        raise HTTPException(404, detail={"code": "template_not_found", "message": body.clipFile})
    out = media_ops.extract_bg_frame(d, source, body.videoStart)
    return {"src": paths.compute(paths.RefKind.HTML_ASSET, out, html_file=html),
            "file": out.name}


@router.get("/{eid}/frames")
def frames(eid: str, preset: str | None = None, t: float | None = None) -> dict:
    d = deps.episode_dir_or_404(eid)
    try:
        if t is not None:
            picked = [{"t": t, "file": media_ops.extract_frame(eid, t).name}]
        elif preset == "review":
            picked = media_ops.review_frames(eid, d)
        else:
            raise HTTPException(422, detail={"code": "bad_request",
                                             "message": "preset=review 또는 t=<초> 필요"})
    except FileNotFoundError as err:
        raise HTTPException(409, detail={"code": "not_built",
                                         "message": str(err),
                                         "hint": "먼저 빌드하세요"}) from err
    return {"frames": [{**f, "url": f"/api/media/{eid}/frames/{f['file']}"} for f in picked]}


@router.get("/{eid}/silence")
def silence(eid: str) -> dict:
    deps.episode_dir_or_404(eid)
    try:
        silences = media_ops.detect_silence(eid)
    except FileNotFoundError as err:
        raise HTTPException(409, detail={"code": "not_built",
                                         "message": str(err),
                                         "hint": "먼저 빌드하세요"}) from err
    return {"silences": silences,
            "total": round(sum(s["duration"] for s in silences), 2),
            "suspect": [s for s in silences if s["cause"] == "clip-end"]}


@router.get("/{eid}/subtitle-check")
def subtitle_check(eid: str) -> dict:
    """자막 대조 — .srt ↔ 대본 diff 0 이 목표 (03 ⑥)."""
    return deliv.subtitle_check(deps.episode_dir_or_404(eid))


@router.get("/{eid}/review")
def get_review(eid: str) -> dict:
    """검수 체크리스트 기록 — out/<id>/review.json (파생 기록, 파일 SSOT)."""
    deps.episode_dir_or_404(eid)
    f = OUT_ROOT / eid / "review.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"items": {}}


@router.put("/{eid}/review")
def put_review(eid: str, body: dict = Body(...)) -> dict:
    deps.episode_dir_or_404(eid)
    f = OUT_ROOT / eid / "review.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    record = {"items": body.get("items", {}), "note": body.get("note", ""),
              "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
    f.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


@router.get("/{eid}/deliverables")
def get_deliverables(eid: str) -> dict:
    """배포 산출물 (03 ⑦) — 제목·설명·챕터·srt·썸네일 후보."""
    d = deps.episode_dir_or_404(eid)
    return deliv.build(d, deps.projects_root())


@router.post("/{eid}/deliverables/save")
def save_deliverables(eid: str, body: dict = Body(...)) -> dict:
    """편집한 제목·설명을 youtube.md 로 저장 — 파일 정본 유지."""
    d = deps.episode_dir_or_404(eid)
    out = deliv.write_youtube_md(d, body.get("title", ""), body.get("description", ""))
    return {"file": out.name}


def _title_frame_url(episode_dir: Path) -> str | None:
    """타이틀 카드 시각의 프레임 url — 완성본이 있어야 한다."""
    eid = episode_dir.name
    if media_ops.final_mp4(eid) is None:
        return None
    starts = media_ops.clip_start_times(episode_dir)
    scenes = schema.load_json(episode_dir / "scenes.json")
    t = None
    for clip in scenes.get("render", {}).get("motion", {}).get("clips", []):
        if str(clip.get("file", "")).endswith("course-intro.html"):
            t = starts[clip["id"]] + 1.2
            break
    if t is None:
        return None
    f = media_ops.extract_frame(eid, round(t, 1))
    return f"/api/media/{eid}/frames/{f.name}"


@router.get("/{eid}/consistency")
def consistency(eid: str) -> dict:
    """voice/render ≡ course 대조 + 직전 회차 타이틀 프레임 쌍 (04_api)."""
    d = deps.episode_dir_or_404(eid)
    course_id = eid.rsplit("-", 1)[0]  # 폴더명 관례 <강좌id>-NN
    course_file = d.parent / course_id / "course.json"
    if not course_file.exists():
        return {"course": None, "problems": [], "single": True, "titlePair": None}
    course = schema.load_json(course_file)
    problems = validate.consistency(schema.load_json(d / "scenes.json"), course)

    # 직전 회차 타이틀 프레임 쌍 — "스팅어·타이틀은 회차마다 같아야 한다" 눈검수 재료
    pair = None
    entry = next((e for e in course.get("episodes", []) if e.get("id") == eid), None)
    if entry:
        prev = next((e for e in course.get("episodes", [])
                     if e.get("n") == entry.get("n", 0) - 1), None)
        if prev and (d.parent / prev["id"] / "scenes.json").exists():
            try:
                pair = {"prevId": prev["id"],
                        "prev": _title_frame_url(d.parent / prev["id"]),
                        "current": _title_frame_url(d)}
            except Exception:  # noqa: BLE001 — 프레임 실패는 쌍 없음으로
                pair = None
    return {"course": course_id, "problems": problems, "single": False, "titlePair": pair}
