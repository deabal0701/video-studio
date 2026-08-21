"""도식 템플릿 갤러리·프리뷰 (04_api "자산·템플릿·TTS").

프리뷰 문서의 params 적용은 iframe URL 의 질의 문자열이 담당한다 — _params.js 가
location.search 를 읽는 엔진 렌더 방식 그대로라 "프리뷰가 곧 실물"이다 (D10).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from core import engine_io
from .. import deps

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _project_dir(scope: str):
    if scope == "common":
        return None
    d = deps.projects_root() / scope
    if not d.exists():
        raise HTTPException(404, detail={"code": "episode_not_found", "message": scope})
    return d


@router.get("")
def list_templates(scope: str = "common") -> list[dict]:
    templates = engine_io.list_templates(_project_dir(scope))
    return [{"file": name, "scope": t["scope"], "params": t["params"]}
            for name, t in templates.items()]


@router.get("/preview")
def preview(file: str, scope: str = "common") -> HTMLResponse:
    """자체완결 html — iframe src 로 쓴다. 템플릿 params 는 이 URL 에 그대로 덧붙인다."""
    try:
        html = engine_io.preview(file, _project_dir(scope))
    except RuntimeError as err:
        raise HTTPException(404, detail={"code": "template_not_found",
                                         "message": str(err)[-300:]}) from err
    return HTMLResponse(html)
