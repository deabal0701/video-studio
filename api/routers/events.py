"""전역 SSE — 잡 상태 변화 + 파일 외부 변경 알림 (04_api: `GET /api/events`)."""

from __future__ import annotations

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from core.events import bus

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def global_events():
    async def stream():
        async for ev in bus.subscribe():
            yield {"event": ev.get("type", "event"),
                   "data": json.dumps(ev, ensure_ascii=False)}

    return EventSourceResponse(stream())
