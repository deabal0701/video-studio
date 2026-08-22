"""공용 픽스처 — 5-2: 테스트는 HTTP 없이 core.facade.Studio 를 직접 부른다.

구 API 테스트의 계약(상태 코드)은 StudioError 위계로 승계됐다:
404=NotFound · 409=Conflict/EtagMismatch/NotBuilt · 422=Invalid · 428=EtagRequired ·
403=Forbidden/AgentDisabled · 502=UpstreamError.
"""

import shutil

import pytest

from core import FIXTURES_DIR
from core.facade import Studio


@pytest.fixture
def studio() -> Studio:
    """호출 시점의 VIDEO_STUDIO_PROJECTS 를 따르는 Studio (monkeypatch 반영)."""
    return Studio()


@pytest.fixture
def fixtures_root(monkeypatch):
    """읽기 전용 테스트 — 픽스처를 그대로 프로젝트 루트로."""
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))
    return FIXTURES_DIR


@pytest.fixture
def copy_root(tmp_path, monkeypatch):
    """쓰기 테스트 — 픽스처를 임시 루트로 복사해 원본을 더럽히지 않는다."""
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(root))
    return root
