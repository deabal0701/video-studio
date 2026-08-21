"""에이전트 라우터 (04_api "에이전트" + 05_agent.md).

키 없으면 403 agent_disabled — 앱의 다른 전부는 키 없이 동작한다 (4단계 수용 기준).
에이전트 실행은 같은 잡 큐(kind=agent) — SSE·취소·회차 직렬화(=편집 잠금)를 그대로 얻는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from core import agents
from core.jobs import JobQueue
from .. import deps

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/status")
def status() -> dict:
    return agents.agent_enabled()


@router.get("/usage")
def usage() -> dict:
    return agents.usage_summary()


def _submit(kind: str, episode_id: str, payload: dict, queue: JobQueue) -> dict:
    gate = agents.agent_enabled()
    if not gate["enabled"]:
        raise HTTPException(403, detail={"code": "agent_disabled", "message": gate["reason"]})
    deps.episode_dir_or_404(episode_id)
    work = agents.make_agent_work(kind, episode_id, payload, deps.projects_root())
    job = queue.submit_agent(episode_id, work)
    return {"jobId": job.id}


@router.post("/draft")
def draft(body: dict = Body(...), queue: JobQueue = Depends(deps.job_queue)) -> dict:
    return _submit("draft", body.get("episodeId", ""), body, queue)


@router.post("/diagram")
def diagram(body: dict = Body(...), queue: JobQueue = Depends(deps.job_queue)) -> dict:
    return _submit("diagram", body.get("episodeId", ""), body, queue)


@router.post("/review")
def review(body: dict = Body(...), queue: JobQueue = Depends(deps.job_queue)) -> dict:
    return _submit("review", body.get("episodeId", ""), body, queue)
