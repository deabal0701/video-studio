"""공용 의존성 — 프로젝트 루트·잡 큐 싱글턴.

프로젝트 루트는 `VIDEO_STUDIO_PROJECTS` 환경변수로 바꿀 수 있다 (01_architecture:
"projects/ — 로컬 모드 기본 루트, 설정으로 변경 가능"). 개발·테스트는 fixtures/projects 를 준다.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from core import PROJECTS_DIR
from core.events import bus
from core.indexer import Index
from core.jobs import JobQueue


def projects_root() -> Path:
    return Path(os.environ.get("VIDEO_STUDIO_PROJECTS", str(PROJECTS_DIR))).resolve()


_indexes: dict[Path, Index] = {}


def index() -> Index:
    root = projects_root()
    if root not in _indexes:
        _indexes[root] = Index(root)
    return _indexes[root]


@lru_cache(maxsize=1)
def job_queue() -> JobQueue:
    return JobQueue(listener=lambda job, ev: bus.publish(
        {"type": "job", "jobId": job.id, "episodeId": job.episode_id, **ev}))


def episode_dir_or_404(episode_id: str) -> Path:
    from fastapi import HTTPException

    d = projects_root() / episode_id
    if not (d / "scenes.json").exists():
        raise HTTPException(404, detail={"code": "episode_not_found", "message": episode_id})
    return d
