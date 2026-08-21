"""out/ 정적 서빙 — mp4 재생용 (04_api: `GET /api/media/{id}/**`, Range 는 FileResponse 가 처리)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.status import OUT_ROOT

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{episode_id}/{rest:path}")
def media(episode_id: str, rest: str) -> FileResponse:
    base = (OUT_ROOT / episode_id).resolve()
    target = (base / rest).resolve()
    if not target.is_relative_to(base):  # 경로 탈출 차단
        raise HTTPException(403, detail={"code": "forbidden", "message": rest})
    if not target.is_file():
        raise HTTPException(404, detail={"code": "media_not_found", "message": rest})
    return FileResponse(target)
