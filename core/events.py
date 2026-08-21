"""events — 전역 이벤트 버스 (04_api: `GET /api/events` — 상단 바 칩·보드 실시간 갱신용).

잡 상태 변화(스레드에서 발행)와 파일 외부 변경(watchfiles, async 에서 발행)을
asyncio 구독자(SSE)로 팬아웃한다. call_soon_threadsafe 로 스레드 → 루프 경계를 넘는다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """앱 기동 시(lifespan) 실행 루프를 잡아 둔다 — 스레드 발행의 목적지."""
        self._loop = loop

    def publish(self, event: dict[str, Any]) -> None:
        """어느 스레드에서든 안전. 루프가 없으면(테스트 등) 조용히 버린다 — 파생 알림일 뿐."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, event)

    def _fanout(self, event: dict[str, Any]) -> None:
        for q in list(self._subs):
            q.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs.discard(q)


bus = EventBus()
