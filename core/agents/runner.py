"""에이전트 러너 — 3종(draft·diagram·review) 단발 세션 (05_agent.md).

작업 하나 = query 하나 = 잡 하나. 상태는 전부 파일로 남는다.
잡 큐(kind=agent)에 실리는 work 제너레이터를 만든다 — SSE 릴레이·취소는 큐가 담당.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable

from .. import REPO_ROOT, env
from . import providers

# 사용량 미터는 파생물 — 설치 모드에선 데이터 폴더에 쌓인다 (설치 폴더 무쓰기)
USAGE_FILE = env.cache_dir() / "agent-usage.jsonl"

# ── 환경 설정 조회 — 셸 → 저장소 .env → 홈 공용 파일 순 (engine util 과 같은 규약) ──
def _env_value(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    for env_file in (REPO_ROOT / ".env",
                     Path.home() / ".claude" / "develop-video.env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith(f"{name}="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    return None


# ── 제공자·모델 (D15 — 선택·해석은 providers 가 정본) ─────────────────────────
def provider() -> str:
    return providers.provider(_env_value)


def test_mode() -> bool:
    return providers.test_mode(_env_value)


# ── 키 게이트 — 선택한 제공자의 키만 검사 (앱의 다른 전부는 키 없이 동작) ──────
def _find_key(prov: str | None = None) -> str | None:
    return _env_value(providers.KEY_ENV[prov or provider()])


def task_model(kind: str) -> str:
    return providers.task_model(_env_value, kind)


def agent_enabled() -> dict[str, Any]:
    return providers.status(_env_value)


# ── 작업 3종 규칙 — 상세 규약은 스킬 문서가 정본, 여기는 과업 지시만 ────────────
KINDS = providers.KINDS

TASK_RULES = {
    "draft": (
        "당신은 develop-lecture 스킬 규약대로 강좌 회차 초안을 만든다. "
        "회차 폴더에 plan.md(구성표)·facts.md(주장—출처URL—확인날짜)·scenes.json"
        "(골격 broll→title→hook→stinger→promise→ch/s→recap→outro, 예산 약 1,850자)을 저장한다. "
        "voice·render 는 강좌 course.json 을 그대로 복사한다. 근거 없는 수치를 쓰지 않는다. "
        "회차는 독립이다 — 앞 회차 참조 금지. 회차 폴더와 스킬(읽기) 밖에 쓰지 않는다."
    ),
    "diagram": (
        "당신은 develop-video 스킬의 도식 규약대로 모션 html 1장을 만든다. "
        "회차 motion/ 에 저장하고 공용 _base.css·_params.js 를 상대 참조한다. "
        "CSS 키프레임만 쓴다(rAF·<video> 금지 — 스크럽 렌더 제약). "
        "연출 팔레트(데이터 흐름·줌·그래프·계층·상태변화) 중 기법 하나만. "
        "발화시각에 등장 delay 를 맞춘다. 생성 후 node engine/preview.js 로 렌더해 확인한다."
    ),
    "review": (
        "당신은 제작 컨텍스트가 없는 평가자다 — .claude/skills 의 reviewer 지침을 읽고 "
        "완성본(out/<id>/final)과 검수 프레임만 보고 6항목(1~5) 점수와 고칠 것 목록을 만들어 "
        "out/<id>/review-agent.json 에 저장한다. 평가 기록 외에는 아무것도 쓰지 않는다."
    ),
}


def _task_prompt(kind: str, episode_id: str, payload: dict[str, Any],
                 projects_root: Path) -> str:
    ep = projects_root / episode_id
    if kind == "draft":
        return (f"회차 초안을 만들어라. 회차 폴더: {ep}\n"
                f"주제(brief): {payload.get('brief', '')}\n"
                f"근거 문서: {payload.get('sourceDocs', [])}\n"
                f"강좌 정체성: {ep.parent / episode_id.rsplit('-', 1)[0] / 'course.json'}")
    if kind == "diagram":
        return (f"도식 html 을 만들어라. 회차 폴더: {ep}\n"
                f"클립: {payload.get('clipId', '')}\n"
                f"설명하려는 것: {payload.get('describe', '')}\n"
                f"해당 내레이션: {payload.get('narration', '')}")
    return f"완성본을 평가하라. 회차 폴더: {ep}\n산출물: engine/out/{episode_id}/"


def _record_usage(kind: str, episode_id: str, usage: dict[str, Any]) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "kind": kind, "episodeId": episode_id, **usage},
                           ensure_ascii=False) + "\n")


def usage_summary() -> dict[str, Any]:
    """토큰·비용 미터 (04_api: GET /api/agent/usage)."""
    runs: list[dict[str, Any]] = []
    if USAGE_FILE.exists():
        for line in USAGE_FILE.read_text(encoding="utf-8").splitlines():
            try:
                runs.append(json.loads(line))
            except ValueError:
                continue
    return {"runs": runs[-50:],
            "totalCostUsd": round(sum(r.get("costUsd", 0) or 0 for r in runs), 4),
            "count": len(runs)}


def make_agent_work(kind: str, episode_id: str, payload: dict[str, Any],
                    projects_root: Path,
                    query_fn: Callable | None = None) -> Callable[[], Iterator[dict]]:
    """잡 큐에 실을 work 제너레이터 팩토리. query_fn 주입으로 SDK 없이 테스트한다.

    제공자에 따라 갈린다 (D15): openai 는 구조화 생성 + 결정적 파일 기입(openai_runner),
    claude 는 아래 에이전틱 SDK 경로. query_fn 주입은 claude 경로 테스트용이다.
    """
    if kind not in KINDS:
        raise ValueError(f"모르는 에이전트 작업: {kind}")

    if query_fn is None and provider() == "openai":
        from . import openai_runner

        return openai_runner.make_work(kind, episode_id, payload, projects_root,
                                       key=_find_key("openai") or "",
                                       model=task_model(kind))

    def work() -> Iterator[dict[str, Any]]:
        yield {"kind": "log", "line": f"에이전트 {kind} 시작 — {episode_id}"}
        queue: asyncio.Queue = asyncio.Queue()

        async def run() -> dict[str, Any]:
            if query_fn is not None:
                return await query_fn(kind, episode_id, payload, queue)
            # 실 SDK 경로 — 05_agent.md 실행 설계 그대로
            # 키는 .env 에서 찾아 자식(CLI) 환경으로 넘긴다 — 셸에 없어도 동작
            key = _find_key()
            if key:
                os.environ.setdefault("ANTHROPIC_API_KEY", key)
            from claude_agent_sdk import ClaudeAgentOptions, query

            options = ClaudeAgentOptions(
                cwd=str(REPO_ROOT),
                setting_sources=["project"],       # .claude/skills 네이티브 로드
                system_prompt={"type": "preset", "preset": "claude_code",
                               "append": TASK_RULES[kind]},
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebSearch"],
                disallowed_tools=["Bash(git commit*)", "Bash(git push*)", "Bash(rm -rf*)"],
                permission_mode="acceptEdits",
                max_turns=120,
                model=task_model(kind),            # 작업별 모델 (05_agent 모델 행)
            )
            usage: dict[str, Any] = {}
            async for message in query(
                    prompt=_task_prompt(kind, episode_id, payload, projects_root),
                    options=options):
                name = type(message).__name__
                if name == "AssistantMessage":
                    for block in getattr(message, "content", []) or []:
                        text = getattr(block, "text", None)
                        if text:
                            await queue.put({"kind": "log", "line": text[:500]})
                elif name == "ResultMessage":
                    usage = {"costUsd": getattr(message, "total_cost_usd", None),
                             "turns": getattr(message, "num_turns", None)}
            return usage

        # 스레드 잡 안에서 async SDK 를 돌리고, 진행 메시지를 동기 제너레이터로 릴레이
        loop = asyncio.new_event_loop()
        task = loop.create_task(run())

        async def drain() -> list[dict[str, Any]]:
            out = []
            while not queue.empty():
                out.append(queue.get_nowait())
            return out

        try:
            while not task.done():
                loop.run_until_complete(asyncio.sleep(0.2))
                for ev in loop.run_until_complete(drain()):
                    yield ev
            for ev in loop.run_until_complete(drain()):
                yield ev
            usage = task.result()
            _record_usage(kind, episode_id,
                          {"provider": "claude", "model": task_model(kind), **(usage or {})})
            yield {"kind": "log", "line": f"에이전트 {kind} 완료"
                   + (f" — ${usage.get('costUsd'):.4f}" if usage.get("costUsd") else "")}
        finally:
            loop.close()

    return work
