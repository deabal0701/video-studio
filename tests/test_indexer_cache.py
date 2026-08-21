"""Index(SQLite 캐시)·전역 이벤트 버스 테스트."""

import shutil
import threading
import time

import pytest
from fastapi.testclient import TestClient

from core import FIXTURES_DIR
from core.events import bus
from core.indexer import Index
from api.main import app


@pytest.fixture(autouse=True)
def fixture_root(monkeypatch):
    monkeypatch.setenv("VIDEO_STUDIO_PROJECTS", str(FIXTURES_DIR))


def test_index_builds_and_rebuilds(tmp_path):
    root = tmp_path / "projects"
    shutil.copytree(FIXTURES_DIR, root)
    idx = Index(root, cache_dir=tmp_path / "cache")
    courses = idx.courses()
    assert [c["id"] for c in courses if not c.get("single")] == ["hr-basics"]
    assert courses[0]["episodes"] == ["hr-basics-01"]

    # 캐시 삭제 → 다음 조회가 재생성 (파생 캐시는 언제나 버릴 수 있다)
    idx.db_file.unlink()
    assert idx.courses()[0]["id"] == "hr-basics"

    # 폴더 추가(외부 변경) → 시그니처 불일치 → 재스캔에 잡힌다
    d = root / "hr-basics-02"
    d.mkdir()
    (d / "scenes.json").write_text('{"id": "hr-basics-02"}', encoding="utf-8")
    assert Index(root, cache_dir=tmp_path / "cache").courses()[0]["episodes"] == [
        "hr-basics-01", "hr-basics-02"]

    # 단발 영상(패턴 밖)은 single 로 목록에만
    s = root / "one-off"
    s.mkdir()
    (s / "scenes.json").write_text('{"id": "one-off"}', encoding="utf-8")
    singles = [c for c in Index(root, cache_dir=tmp_path / "cache").courses() if c.get("single")]
    assert [c["id"] for c in singles] == ["one-off"]


def test_courses_endpoint_uses_index():
    with TestClient(app) as client:
        body = client.get("/api/courses").json()
        hr = next(c for c in body if c["id"] == "hr-basics")
        assert hr["episodeCount"] == 6 and hr["scaffolded"] == 1


def test_bus_relays_thread_publish_to_async_subscriber():
    """무한 스트림이라 SSE 왕복 대신 버스를 직접 검증한다 (엔드포인트는 얇은 릴레이)."""
    import asyncio

    async def main():
        bus.attach(asyncio.get_running_loop())
        gen = bus.subscribe()

        async def first():
            async for ev in gen:
                return ev

        fut = asyncio.create_task(first())
        await asyncio.sleep(0.05)  # 구독이 서고 나서 발행
        threading.Thread(target=lambda: bus.publish({"type": "job", "jobId": "j1"})).start()
        ev = await asyncio.wait_for(fut, 5)
        await gen.aclose()
        return ev

    assert asyncio.run(main())["jobId"] == "j1"
