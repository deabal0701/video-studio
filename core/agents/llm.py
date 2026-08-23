"""llm — 제공자 중립 구조화 생성 1회 호출 (D18 — 순수 HTTP, CLI·에이전트 하네스 없음).

claude = `anthropic` 패키지 · openai = `openai` 패키지. 어느 쪽도 subprocess 를 띄우지
않는다 — 키만 있으면 배포본에서 그대로 동작한다 (05_agent).

계약: complete(...) → (내용, usage)
  - json_schema 가 있으면 스키마 준수 JSON 을 파싱해 돌려준다 (없으면 원문 텍스트)
  - images = [(mime, bytes), ...] — 검수 프레임·도식 렌더 확인의 vision 입력
  - usage = {"inputTokens": n, "outputTokens": n}
패키지는 선택 의존성 — 미설치면 사유를 그대로 알린다 (키가 있어도 앱은 완결 동작, 원칙 2).
"""

from __future__ import annotations

import base64
import json
from typing import Any

MAX_TOKENS = 16000  # 비스트리밍 안전 상한 — 초안 클립 전체·도식 html 이 여유 있게 들어온다


def complete(provider: str, *, key: str, model: str, system: str, user: str,
             json_schema: dict | None = None,
             images: list[tuple[str, bytes]] | None = None,
             client: Any = None) -> tuple[Any, dict]:
    if provider == "openai":
        return _openai(key=key, model=model, system=system, user=user,
                       json_schema=json_schema, images=images, client=client)
    return _claude(key=key, model=model, system=system, user=user,
                   json_schema=json_schema, images=images, client=client)


# ── claude — anthropic 패키지 ────────────────────────────────────────────────
def _claude_client(key: str):
    try:
        import anthropic
    except ImportError as err:
        raise RuntimeError(
            "anthropic 패키지가 없습니다 — conda run -n penv3.13-video pip install anthropic"
        ) from err
    return anthropic.Anthropic(api_key=key)


def _claude(*, key: str, model: str, system: str, user: str,
            json_schema: dict | None, images: list[tuple[str, bytes]] | None,
            client: Any) -> tuple[Any, dict]:
    client = client or _claude_client(key)
    content: list[dict] = [
        {"type": "image",
         "source": {"type": "base64", "media_type": mime,
                    "data": base64.b64encode(data).decode()}}
        for mime, data in (images or [])
    ]
    content.append({"type": "text", "text": user})
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        # 규약 블록은 호출 간 동일 — cache_control 로 프롬프트 캐시를 적중시킨다
        # (초안 1·2단계, 도식 생성·확인이 같은 system 을 재사용한다)
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": content}],
    }
    if json_schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema",
                                              "schema": json_schema}}
    res = client.messages.create(**kwargs)
    stop = getattr(res, "stop_reason", None)
    if stop == "refusal":
        raise RuntimeError("모델이 요청을 거절했습니다 — 근거 문서·주제를 바꿔 다시 시도하세요")
    if stop == "max_tokens":
        raise RuntimeError("응답이 길이 상한에서 잘렸습니다 — 주제 범위를 줄여 다시 시도하세요")
    text = "".join(b.text for b in res.content
                   if getattr(b, "type", None) == "text" and getattr(b, "text", None))
    usage = {}
    if getattr(res, "usage", None):
        usage = {"inputTokens": res.usage.input_tokens,
                 "outputTokens": res.usage.output_tokens}
    return (json.loads(text) if json_schema is not None else text), usage


# ── openai — 기존 openai_runner._structured 이식 ─────────────────────────────
def _openai_client(key: str):
    try:
        from openai import OpenAI
    except ImportError as err:
        raise RuntimeError(
            "openai 패키지가 없습니다 — conda run -n penv3.13-video pip install openai"
        ) from err
    return OpenAI(api_key=key)


def _openai(*, key: str, model: str, system: str, user: str,
            json_schema: dict | None, images: list[tuple[str, bytes]] | None,
            client: Any) -> tuple[Any, dict]:
    client = client or _openai_client(key)
    content: str | list = user
    if images:
        content = [{"type": "text", "text": user}] + [
            {"type": "image_url",
             "image_url": {"url": f"data:{mime};base64,"
                                  f"{base64.b64encode(data).decode()}"}}
            for mime, data in images
        ]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": content}],
    }
    if json_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": json_schema},
        }
    res = client.chat.completions.create(**kwargs)
    text = res.choices[0].message.content or ""
    usage = {}
    if getattr(res, "usage", None):
        usage = {"inputTokens": res.usage.prompt_tokens,
                 "outputTokens": res.usage.completion_tokens}
    return (json.loads(text) if json_schema is not None else text), usage
