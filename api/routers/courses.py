"""강좌·회차 조회·저장 라우터 (04_api REST 표).

etag = mtime+size 해시. 모든 쓰기는 If-Match — 불일치 409 + 현재 내용 동봉(클라가 diff
표시 후 사람이 병합). 파일 SSOT 라 낙관적 잠금이 유일한 정답 (04_api 원칙).
저장은 schema.Document — 무수정이면 diff 0, 수정 시 `_` 보존·키순서·2칸 (02 직렬화 규약).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import ValidationError

from core import paths, schema, status, validate
from core.schema import Document
from .. import deps


def _path_issues(body: dict[str, Any], scenes_dir: Path) -> list[str]:
    """저장 시 경로 실존 검사 — 02 규칙 5 ("사전점검의 사각을 앱이 메운다").

    params.src 가 깨져도 엔진은 조용히 검은 배경을 만들므로 저장 응답에서 바로 알린다.
    """
    issues: list[str] = []
    for clip in body.get("render", {}).get("motion", {}).get("clips", []):
        cid = clip.get("id", "?")
        if clip.get("video") and not paths.invert(paths.RefKind.BROLL, clip["video"]).exists():
            issues.append(f"{cid}: B롤 없음 — {clip['video']}")
        if clip.get("file"):
            html = paths.invert(paths.RefKind.MOTION, clip["file"], scenes_dir=scenes_dir)
            if not html.exists():
                issues.append(f"{cid}: 템플릿 없음 — {clip['file']}")
                continue
            for key in ("src", "fontUrl"):
                v = (clip.get("params") or {}).get(key)
                if v and not paths.invert(paths.RefKind.HTML_ASSET, v, html_file=html).exists():
                    issues.append(f"{cid}: params.{key} 가 가리키는 파일 없음 — {v} (조용히 검은 배경/폰트 폴백)")
    return issues

router = APIRouter(prefix="/api", tags=["courses"])


def _etag(file: Path) -> str:
    st = file.stat()
    return hashlib.sha1(f"{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()[:16]


def _save_with_ifmatch(file: Path, body: dict[str, Any], if_match: str | None) -> str:
    """If-Match 검사 → Document 저장 → 새 etag. 불일치면 409 + 현재 내용."""
    if not if_match:
        raise HTTPException(428, detail={"code": "if_match_required",
                                         "message": "If-Match 헤더가 필요합니다",
                                         "hint": "GET 응답의 etag 를 넣으세요"})
    current = _etag(file)
    if if_match != current:
        raise HTTPException(409, detail={"code": "etag_mismatch",
                                         "message": "파일이 밖에서 바뀌었습니다 — diff 를 보고 병합하세요",
                                         "etag": current,
                                         "current": schema.load_json(file)})
    doc = Document.load(file)
    doc.data = body
    doc.save()
    return _etag(file)


def _episode_summary(root: Path, episode_id: str) -> dict:
    d = root / episode_id
    return {"id": episode_id, **status.episode_status(d)}


@router.get("/courses")
def list_courses() -> list[dict]:
    """구조는 SQLite 캐시(Index)에서, 상태 배지는 계산으로 (파생 상태 저장 금지 — 02)."""
    root = deps.projects_root()
    out = []
    for c in deps.index().courses():
        if c.get("single"):  # 패턴 밖 폴더는 "단발 영상"으로 목록에만 (04_api 인덱서)
            out.append(c)
            continue
        episodes = [_episode_summary(root, e) for e in c["episodes"]]
        out.append({
            "id": c["id"],
            "title": c["title"],
            "episodeCount": c["episodeCount"],
            "scaffolded": len(episodes),
            "done": sum(1 for e in episodes if e["state"] == "done"),
        })
    return out


@router.get("/courses/{cid}")
def get_course(cid: str) -> dict:
    root = deps.projects_root()
    file = root / cid / "course.json"
    if not file.exists():
        raise HTTPException(404, detail={"code": "course_not_found", "message": cid})
    doc = schema.load_json(file)
    badges = {e["id"]: _episode_summary(root, e["id"]) if (root / e["id"]).exists()
              else {"id": e["id"], "state": "empty", "final": [], "stale": False}
              for e in doc.get("episodes", [])}
    return {"course": doc, "etag": _etag(file), "episodes": badges}


@router.get("/courses/{cid}/episodes")
def course_board(cid: str) -> list[dict]:
    """커리큘럼 보드 — course.episodes[] × 파생 상태 join."""
    return list(get_course(cid)["episodes"].values())


@router.get("/episodes/{eid}")
def get_episode(eid: str) -> dict:
    d = deps.episode_dir_or_404(eid)
    file = d / "scenes.json"
    return {
        "scenes": schema.load_json(file),
        "etag": _etag(file),
        **status.episode_status(d),
    }


@router.post("/courses", status_code=201)
def create_course(body: dict[str, Any] = Body(...)) -> dict:
    """강좌 개설 (04: 폴더 + course.json + intro/stinger 템플릿 카피)."""
    import re as _re

    cid = str(body.get("course", "")).strip()
    title = str(body.get("title", "")).strip()
    if not _re.fullmatch(r"[a-z0-9][a-z0-9-]*", cid):
        raise HTTPException(422, detail={"code": "bad_id",
                                         "message": "강좌 id 는 kebab-case (영소문자·숫자·하이픈)"})
    if not title:
        raise HTTPException(422, detail={"code": "bad_request", "message": "title 필요"})
    from core.scaffold import scaffold_course

    try:
        d = scaffold_course(deps.projects_root(), cid, title=title,
                            tagline=body.get("tagline", ""),
                            audience=body.get("audience", ""),
                            episode_length=body.get("episodeLength"),
                            voice=body.get("voice"), palette=body.get("palette"),
                            bgm=body.get("bgm"), episodes=body.get("episodes"))
    except FileExistsError as err:
        raise HTTPException(409, detail={"code": "already_exists", "message": str(err)}) from err
    deps.index().rescan()
    return {"id": d.name, "etag": _etag(d / "course.json")}


@router.post("/courses/{cid}/episodes", status_code=201)
def create_episode(cid: str, body: dict[str, Any] = Body(...)) -> dict:
    """회차 스캐폴딩 (03 ② [회차 생성]) — {n, title?, subtitle?}."""
    root = deps.projects_root()
    if not (root / cid / "course.json").exists():
        raise HTTPException(404, detail={"code": "course_not_found", "message": cid})
    n = body.get("n")
    if not isinstance(n, int) or n < 1:
        raise HTTPException(422, detail={"code": "bad_request", "message": "n(회차 번호) 필요"})
    from core.scaffold import scaffold_episode

    try:
        ep_dir = scaffold_episode(root, cid, n,
                                  title=body.get("title"), subtitle=body.get("subtitle"))
    except FileExistsError as err:
        raise HTTPException(409, detail={"code": "already_exists", "message": str(err)}) from err
    deps.index().rescan()  # 목록 캐시 즉시 갱신
    return {"id": ep_dir.name, "etag": _etag(ep_dir / "scenes.json")}


@router.post("/courses/{cid}/brandkit/apply")
def apply_brand_kit(cid: str) -> dict:
    """프리셋의 타이틀 카드·스팅어를 강좌 폴더로 (재)카피 — 기존 파일 덮어씀 (③)."""
    from core.scaffold import copy_brand_kit

    d = deps.projects_root() / cid
    if not (d / "course.json").exists():
        raise HTTPException(404, detail={"code": "course_not_found", "message": cid})
    return {"copied": copy_brand_kit(d)}


@router.put("/courses/{cid}")
def put_course(cid: str, body: dict[str, Any] = Body(...),
               if_match: str | None = Header(default=None)) -> dict:
    """course.json 저장 (If-Match) → 기존 회차들과 일관성 재검사 결과 반환 (03 ① "저장 후")."""
    root = deps.projects_root()
    file = root / cid / "course.json"
    if not file.exists():
        raise HTTPException(404, detail={"code": "course_not_found", "message": cid})
    try:
        model = schema.Course.model_validate(body)
    except ValidationError as err:
        raise HTTPException(422, detail={"code": "invalid_course",
                                         "message": str(err.errors()[:3])}) from err
    if model.course != cid:
        raise HTTPException(422, detail={"code": "id_mismatch",
                                         "message": f"course '{model.course}' ≠ 폴더명 '{cid}'"})
    etag = _save_with_ifmatch(file, body, if_match)
    # 일관성 재검사 — 어긋난 회차에 배지를 달 재료 (② 커리큘럼 보드)
    problems = {}
    for ep in body.get("episodes", []):
        scenes_file = root / ep["id"] / "scenes.json"
        if scenes_file.exists():
            found = validate.consistency(schema.load_json(scenes_file), body)
            if found:
                problems[ep["id"]] = found
    return {"etag": etag, "consistency": problems}


@router.put("/episodes/{eid}")
def put_episode(eid: str, body: dict[str, Any] = Body(...),
                if_match: str | None = Header(default=None)) -> dict:
    """scenes.json 저장 (If-Match) → `_` 보존 직렬화 → 검증 결과 동봉 (04_api).

    자산 참조 → 경로 계산 기입은 ⑤ 대본 에디터(3단계)에서 붙는다 — 지금은 경로 문자열을
    받은 그대로 저장하되, 역산 검사로 깨진 경로를 응답에 알린다.
    """
    d = deps.episode_dir_or_404(eid)
    file = d / "scenes.json"
    try:
        model = schema.Scenes.model_validate(body)
    except ValidationError as err:
        raise HTTPException(422, detail={"code": "invalid_scenes",
                                         "message": str(err.errors()[:3])}) from err
    if model.id != eid:
        raise HTTPException(422, detail={"code": "id_mismatch",
                                         "message": f"id '{model.id}' ≠ 폴더명 '{eid}' — out 폴더가 갈라진다"})
    etag = _save_with_ifmatch(file, body, if_match)
    course_id = eid.rsplit("-", 1)[0]
    course_file = d.parent / course_id / "course.json"
    problems = (validate.consistency(body, schema.load_json(course_file))
                if course_file.exists() else [])
    return {"etag": etag, "consistency": problems, "pathIssues": _path_issues(body, d)}


@router.post("/episodes/{eid}/plan/apply")
def plan_apply(eid: str) -> dict:
    """구성표 → 클립 골격 반영 (04). 기존 클립은 보존, 없는 구간만 표 순서에 삽입."""
    from core import plan_apply as pa

    d = deps.episode_dir_or_404(eid)
    try:
        out = pa.apply(d)
    except FileNotFoundError as err:
        raise HTTPException(404, detail={"code": "plan_not_found", "message": str(err)}) from err
    return {**out, "etag": _etag(d / "scenes.json")}


@router.post("/episodes/{eid}/sync-course")
def sync_course(eid: str, if_match: str | None = Header(default=None)) -> dict:
    """voice·render 를 course 값으로 맞춘다 (02: 어긋나면 경고 배지 + 이 버튼)."""
    d = deps.episode_dir_or_404(eid)
    course_file = d.parent / eid.rsplit("-", 1)[0] / "course.json"
    if not course_file.exists():
        raise HTTPException(404, detail={"code": "course_not_found", "message": eid})
    file = d / "scenes.json"
    if not if_match:
        raise HTTPException(428, detail={"code": "if_match_required",
                                         "message": "If-Match 헤더가 필요합니다"})
    if if_match != _etag(file):
        raise HTTPException(409, detail={"code": "etag_mismatch",
                                         "message": "파일이 밖에서 바뀌었습니다"})
    course = schema.load_json(course_file)
    doc = Document.load(file)
    if course.get("voice"):
        doc.data["voice"] = dict(course["voice"])
    doc.data["render"].update(course.get("render", {}))
    doc.save()
    remaining = validate.consistency(doc.data, course)
    return {"etag": _etag(file), "consistency": remaining}


@router.get("/episodes/{eid}/files")
def episode_file(eid: str, path: str):
    """회차 폴더의 원본 파일 서빙 (bg 프레임 등 — 프리뷰용). out/ 산출물은 /api/media."""
    from fastapi.responses import FileResponse

    d = deps.episode_dir_or_404(eid)
    target = (d / path).resolve()
    if not target.is_relative_to(d.resolve()):
        raise HTTPException(403, detail={"code": "forbidden", "message": path})
    if not target.is_file():
        raise HTTPException(404, detail={"code": "file_not_found", "message": path})
    return FileResponse(target)


@router.get("/episodes/{eid}/plan")
def get_plan(eid: str) -> dict:
    d = deps.episode_dir_or_404(eid)
    file = d / "plan.md"
    if not file.exists():
        raise HTTPException(404, detail={"code": "plan_not_found", "message": eid})
    return {"markdown": file.read_text(encoding="utf-8"), "etag": _etag(file)}


@router.put("/episodes/{eid}/plan")
def put_plan(eid: str, body: dict[str, Any] = Body(...),
             if_match: str | None = Header(default=None)) -> dict:
    """plan.md 저장 — 마크다운 그대로 라운드트립 (④ 구성표. 표 구조 편집기는 후속)."""
    d = deps.episode_dir_or_404(eid)
    file = d / "plan.md"
    if file.exists():
        if not if_match:
            raise HTTPException(428, detail={"code": "if_match_required",
                                             "message": "If-Match 헤더가 필요합니다"})
        if if_match != _etag(file):
            raise HTTPException(409, detail={"code": "etag_mismatch",
                                             "message": "plan.md 가 밖에서 바뀌었습니다",
                                             "current": file.read_text(encoding="utf-8")})
    file.write_text(str(body.get("markdown", "")), encoding="utf-8")
    return {"etag": _etag(file)}
