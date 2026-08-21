"""빌드 잡 라우터 — 제출·조회·취소·SSE (04_api "검증·빌드·검수" + SSE 이벤트 스키마).

core.jobs 의 블로킹 subscribe() 를 스레드로 돌려 SSE 로 릴레이한다.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core import engine_io
from core.jobs import JobQueue
from .. import deps

router = APIRouter(prefix="/api", tags=["jobs"])


class BuildRequest(BaseModel):
    only: str | None = None      # tts | record | compose
    variant: str | None = None
    force: bool = False          # 경고급만 무시 — blocker 는 무시 불가 (큐가 강제)


def _job_view(job) -> dict[str, Any]:
    return {"jobId": job.id, "episodeId": job.episode_id, "state": job.state.value,
            "error": job.error}


@router.post("/episodes/{eid}/preflight")
def preflight(eid: str) -> dict:
    d = deps.episode_dir_or_404(eid)
    return {"findings": engine_io.inspect(d)["preflight"]}


@router.get("/episodes/{eid}/inspect")
def inspect_full(eid: str) -> dict:
    """inspect.js 원본 JSON — 에디터가 쓴다 (audioCache=실측 길이·templates=받는 키·media)."""
    return engine_io.inspect(deps.episode_dir_or_404(eid))


@router.post("/episodes/{eid}/build")
def submit_build(eid: str, body: BuildRequest, queue: JobQueue = Depends(deps.job_queue)) -> dict:
    d = deps.episode_dir_or_404(eid)
    job = queue.submit(eid, d / "scenes.json", only=body.only, variant=body.variant)
    return {"jobId": job.id}


@router.post("/episodes/{eid}/tts")
def refresh_tts(eid: str, queue: JobQueue = Depends(deps.job_queue)) -> dict:
    """부분 TTS 갱신 (04: `--only tts` 부분판 — 몇 초·무료). 추정 길이 → 실측 전환용."""
    d = deps.episode_dir_or_404(eid)
    job = queue.submit(eid, d / "scenes.json", only="tts")
    return {"jobId": job.id}


@router.get("/jobs")
def list_jobs(queue: JobQueue = Depends(deps.job_queue)) -> list[dict]:
    return [_job_view(j) for j in queue.list()]


@router.get("/jobs/{jid}")
def get_job(jid: str, queue: JobQueue = Depends(deps.job_queue)) -> dict:
    job = queue.get(jid)
    if not job:
        raise HTTPException(404, detail={"code": "job_not_found", "message": jid})
    return _job_view(job)


@router.post("/jobs/{jid}/cancel")
def cancel_job(jid: str, queue: JobQueue = Depends(deps.job_queue)) -> dict:
    job = queue.get(jid)
    if not job:
        raise HTTPException(404, detail={"code": "job_not_found", "message": jid})
    return {"canceled": queue.cancel(jid)}


@router.get("/jobs/{jid}/events")
async def job_events(jid: str, queue: JobQueue = Depends(deps.job_queue)):
    """SSE — 04_api 스키마: progress·log·done·failed (+state 전환은 progress 로 흘린다)."""
    job = queue.get(jid)
    if not job:
        raise HTTPException(404, detail={"code": "job_not_found", "message": jid})

    def _translate(ev: dict[str, Any]) -> dict[str, str]:
        if ev["kind"] == "state":
            if ev["state"] == "done":
                return {"event": "done", "data": json.dumps({"jobId": jid}, ensure_ascii=False)}
            if ev["state"] in ("failed", "blocked"):
                return {"event": "failed", "data": json.dumps(
                    {"jobId": jid, "error": job.error or ev["state"]}, ensure_ascii=False)}
            return {"event": "progress", "data": json.dumps(
                {"jobId": jid, "phase": ev["state"]}, ensure_ascii=False)}
        if ev["kind"] == "phase":
            return {"event": "progress", "data": json.dumps(
                {"jobId": jid, "phase": ev.get("phase"), "msg": ev.get("line", "")}, ensure_ascii=False)}
        if ev["kind"] == "step":
            return {"event": "progress", "data": json.dumps(
                {"jobId": jid, "step": ev.get("step"), "msg": ev.get("line", "")}, ensure_ascii=False)}
        return {"event": "log", "data": json.dumps(
            {"jobId": jid, "line": ev.get("line", "")}, ensure_ascii=False)}

    async def stream():
        loop = asyncio.get_running_loop()
        it = queue.subscribe(jid)
        sentinel = object()
        while True:
            ev = await loop.run_in_executor(None, next, it, sentinel)
            if ev is sentinel:
                return
            yield _translate(ev)

    return EventSourceResponse(stream())
