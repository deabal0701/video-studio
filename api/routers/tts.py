"""TTS 미리듣기 — POST /api/tts/sample (03 ①: "실제 TTS 합성해 재생". edge 무료·키 불요)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core import engine_io

router = APIRouter(prefix="/api/tts", tags=["tts"])


class SampleRequest(BaseModel):
    text: str = "연결 테스트입니다."
    lang: str = "ko"
    gender: str = "female"
    voice: str | None = None


@router.post("/sample")
def sample(body: SampleRequest) -> FileResponse:
    try:
        file = engine_io.tts_sample(body.text, lang=body.lang, gender=body.gender,
                                    voice=body.voice)
    except Exception as err:  # noqa: BLE001 — 네트워크·엔진 사정을 그대로 알린다
        raise HTTPException(502, detail={"code": "tts_failed", "message": str(err)[-500:],
                                         "hint": "네트워크와 edge-tts 를 확인하세요"}) from err
    return FileResponse(file, media_type="audio/mpeg", filename="sample.mp3")
