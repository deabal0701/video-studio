"""bridge — core ↔ Qt 경계 (07_desktop 대응표의 "SSE → Qt Signal" 승계).

- Bridge.job_event: JobQueue.listener → Signal (core 무수정 — 04 의 listener 훅 그대로)
- run_bg(): facade 호출을 QThreadPool 워커로 — inspect 는 최대 60초라 **GUI 스레드에서
  facade 를 직접 부르지 않는 규율**(07 5-3)의 도구
- JobEventPump: job_events() 블로킹 제너레이터를 워커에서 소비해 Signal 로 릴레이
"""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from core.facade import Studio, StudioError
from core.jobs import JobQueue


class Bridge(QObject):
    """전역 신호 허브 — 잡 이벤트(스레드 발행)를 Qt 큐드 커넥션으로 UI 에 넘긴다."""

    job_event = Signal(str, str, dict)   # job_id, episode_id, event

    def make_studio(self) -> Studio:
        queue = JobQueue(listener=lambda job, ev: self.job_event.emit(
            job.id, job.episode_id, dict(ev)))
        return Studio(queue=queue)


class _Dispatcher(QObject):
    """워커 → GUI 스레드 콜백 중계 (영속 QObject).

    5-3 실측 함정 두 겹: ① 시그널을 클로저에 직접 연결하면 기본 direct 라 콜백이 워커
    스레드에서 돈다(위젯 접근 붕괴) ② QRunnable 은 autoDelete 라 태스크 소유 시그널로
    큐드 전달을 걸면 송신자가 먼저 파괴돼 전달이 유실된다. 그래서 앱 수명 동안 살아 있는
    QObject 하나가 (콜백, 인자) 쌍을 받아 GUI 스레드 슬롯에서 호출한다.
    """

    call = Signal(object, object)  # callback, arg

    def __init__(self) -> None:
        super().__init__()
        self.call.connect(self._run)  # 수신자=QObject(GUI) → 워커 emit 은 자동 큐드

    def _run(self, cb: Callable[[Any], None], arg: Any) -> None:
        cb(arg)


_dispatcher: _Dispatcher | None = None


def _get_dispatcher() -> _Dispatcher:
    global _dispatcher
    if _dispatcher is None:  # 첫 호출은 GUI 스레드에서 온다 (페이지 코드)
        _dispatcher = _Dispatcher()
    return _dispatcher


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], done, fail):
        super().__init__()
        self.fn = fn
        self.done = done
        self.fail = fail
        self.dispatcher = _get_dispatcher()

    def run(self) -> None:  # noqa: D102 — 워커 스레드
        try:
            result = self.fn()
        except (StudioError, Exception) as err:  # noqa: BLE001 — UI 에 사유 전달
            traceback.print_exc()
            self._emit(self.fail, err)
            return
        self._emit(self.done, result)

    def _emit(self, cb, arg) -> None:
        if cb is None:
            return
        try:
            self.dispatcher.call.emit(cb, arg)
        except RuntimeError:
            pass  # 앱 종료 중 디스패처가 먼저 파괴된 경우 — 전달할 UI 도 없다


def run_bg(fn: Callable[[], Any], done=None, fail=None) -> None:
    """facade 호출을 백그라운드로. done/fail 콜백은 GUI 스레드에서 불린다."""
    QThreadPool.globalInstance().start(_Task(fn, done, fail))


class JobEventPump(QObject):
    """한 잡의 이벤트 스트림 소비자 — 재생 포함, 종료 시 finished."""

    event = Signal(dict)
    finished = Signal()

    def __init__(self, studio: Studio, job_id: str):
        super().__init__()
        self._studio = studio
        self._job_id = job_id

    def start(self) -> None:
        dispatcher = _get_dispatcher()

        def consume():
            # 이벤트도 디스패처 경유 — self.event 를 워커에서 직접 emit 하면 클로저
            # 수신자가 워커 스레드에서 돌 수 있다 (수신자가 QObject 면 자동 큐드지만 통일)
            for ev in self._studio.job_events(self._job_id):
                dispatcher.call.emit(self.event.emit, dict(ev))
            return None

        run_bg(consume, done=lambda _r: self.finished.emit(),
               # A1-허용: 이벤트 스트림이 끊겨도 finished 를 내보내 화면이 "진행 중"에서
               # 빠져나온다. 잡 자체의 실패 사유는 잡 이벤트·상태 칩이 말한다
               fail=lambda _e: self.finished.emit())


def guard(owner, attr: str, value, cb):
    """늦은 응답 차단 — 제출 시점의 대상(owner.<attr>)이 그대로일 때만 콜백을 부른다.

    화면이 다른 프로젝트/영상으로 넘어간 뒤 도착한 응답이 새 화면을 **옛 대상의
    데이터로 되덮는** 것을 막는다 (74회차 A3). 59·60회차의 토큰 가드(self._req)와
    같은 처방을 대상 id 로 일반화한 관용구다 — 화면마다 사본을 두지 않는다.
    사용: run_bg(get, done=guard(self, "eid", eid, self._fill),
                 fail=guard(self, "eid", eid, self._fail))
    """
    def wrapped(arg=None):
        if getattr(owner, attr, None) == value and cb is not None:
            cb(arg)
    return wrapped


def agent_gate_failed(err: Exception) -> dict:
    """`agent_status` 조회가 실패했을 때 쓸 게이트 — **비활성 + 사유**.

    72회차 A1(조용한 실패) 전수 감사: 세 화면(보드 2곳·영상 화면)이 이 조회를
    `fail=lambda _e: None` 로 삼켰다. 그러면 [AI 초안]·[AI 평가]가 **이유 없이 회색**으로
    남는다 — 키가 없는 것인지, 못 물어본 것인지 화면이 구분해 주지 않았다.
    판단과 문구를 여기 하나로 두고 세 화면이 제 `_apply_gate`/`_fill_agent` 를 그대로 쓴다.
    """
    return {"enabled": False,
            "reason": f"AI 사용 가능 여부를 확인하지 못했습니다 — {error_text(err)}"}


def error_text(err: Exception) -> str:
    if isinstance(err, StudioError):
        return err.message + (f" — {err.hint}" if err.hint else "")
    return str(err)
