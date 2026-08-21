"""미디어 라이브러리 라우터 — GET/POST /api/assets (04_api "자산·템플릿·TTS")."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import library

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/file")
def asset_file(kind: str, name: str) -> FileResponse:
    """소재 실물 서빙 — 라이브러리의 미리듣기·미리보기용 (BGM 재생 등)."""
    root = library.KIND_DIRS.get(kind)
    if root is None:
        raise HTTPException(422, detail={"code": "bad_kind", "message": kind})
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise HTTPException(404, detail={"code": "asset_not_found", "message": name})
    return FileResponse(target)


@router.get("")
def list_assets(kind: str = "broll") -> list[dict]:
    try:
        return library.list_assets(kind)
    except ValueError as err:
        raise HTTPException(422, detail={"code": "bad_kind", "message": str(err)}) from err


class AddAsset(BaseModel):
    kind: str
    url: str
    license: str = ""   # 필수 — 비면 422 (03: "라이선스 필드 필수")
    source: str | None = None
    name: str | None = None
    note: str = ""


@router.post("", status_code=201)
def add_asset(body: AddAsset) -> dict:
    try:
        return library.add_asset(body.kind, body.url, license=body.license,
                                 source=body.source, name=body.name, note=body.note)
    except ValueError as err:
        raise HTTPException(422, detail={"code": "invalid", "message": str(err)}) from err
    except RuntimeError as err:
        # fetch.js 거부(허용 밖 호스트 등)·다운로드 실패 — 메시지를 그대로 넘긴다
        raise HTTPException(502, detail={"code": "fetch_failed", "message": str(err),
                                         "hint": "허용 호스트와 URL 을 확인하세요"}) from err
