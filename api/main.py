"""FastAPI 앱 진입점 (04_api.md) — 1단계: 조회 전부 + build + SSE.

실행: conda run -n penv3.13-insait uvicorn api.main:app --reload
개발 데이터: VIDEO_STUDIO_PROJECTS=fixtures/projects 로 픽스처를 그대로 띄운다.

기동 시 인덱스 재스캔 + watchfiles 로 projects/ 를 감시한다 — 외부 편집(Claude Code·에디터)이
파일을 바꾸면 인덱스를 갱신하고 전역 SSE 로 알린다 (02 "동시성·충돌").
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from core.events import bus
from . import deps
from .routers import agent, assets, courses, events, jobs, media, review, templates, tts


async def _watch_projects(root: Path) -> None:
    if not root.exists():
        return
    from watchfiles import awatch

    async for changes in awatch(root):
        deps.index().rescan()
        rels = []
        for _kind, p in list(changes)[:20]:
            try:
                rels.append(str(Path(p).relative_to(root)))
            except ValueError:
                rels.append(str(p))
        bus.publish({"type": "fs", "changes": rels})


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus.attach(asyncio.get_running_loop())
    deps.index().ensure_fresh()
    watcher = asyncio.create_task(_watch_projects(deps.projects_root()))
    yield
    watcher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await watcher


app = FastAPI(title="video-studio", version="0.0.1", lifespan=lifespan)
app.include_router(courses.router)
app.include_router(jobs.router)
app.include_router(media.router)
app.include_router(review.router)
app.include_router(events.router)
app.include_router(tts.router)
app.include_router(assets.router)
app.include_router(templates.router)
app.include_router(agent.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
